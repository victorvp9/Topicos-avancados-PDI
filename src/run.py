"""Ponto de entrada unico. Nesta fatia implementa apenas `--inspect`.

`python -m src.run --inspect` imprime, por jogo: numero de quadros, periodos,
fracao de bola morta, jogadores por quadro, `attack_dir`, e as contagens de
evento por tipo interno e por `Type` cru. A saida tem de bater com
docs/inspecao-metrica.md -- e a conferencia manual do Victor (plano §8.6).
"""

import argparse

from src import gabarito
from src.config import carregar_config, carregar_mapeamento
from src.io import carregar_jogo


def inspecionar(cfg: dict, mapeamento: dict, jogos) -> None:
    """Imprime o resumo de cada jogo."""
    for game in jogos:
        frames, tracking, periods = carregar_jogo(game, cfg)
        crus = gabarito.carregar_eventos_crus(game, cfg, mapeamento)
        eventos = gabarito.construir_gabarito(game, crus, frames, cfg)

        print("=" * 64)
        print("JOGO {}".format(game))
        print("  quadros: {}".format(len(frames)))
        for period, bloco in frames.groupby("period", sort=True):
            print(
                "  periodo {}: {} quadros, t de {:.2f} a {:.2f} s".format(
                    period, len(bloco), bloco["t"].min(), bloco["t"].max()
                )
            )
        mortos = int((~frames["ball_live"]).sum())
        print(
            "  bola morta (NaN): {} quadros ({:.2f} %)".format(
                mortos, 100.0 * mortos / len(frames)
            )
        )
        por_quadro = tracking.groupby("frame", sort=True).size().value_counts().sort_index()
        print("  jogadores por quadro:")
        for n_jog, n_quadros in por_quadro.items():
            print("    {} jogadores: {} quadros".format(n_jog, n_quadros))
        print("  linhas de tracking: {} | visible todos True: {}".format(
            len(tracking), bool(tracking["visible"].all())
        ))
        print("  attack_dir:")
        for linha in periods.sort_values(["period", "team"]).itertuples():
            print(
                "    periodo {} {:5s}: {:+d}  (x medio do goleiro {:+.3f} m)".format(
                    linha.period, linha.team, linha.attack_dir, linha.gk_mean_x
                )
            )
        print("  eventos no gabarito: {} (linhas cruas: {})".format(len(eventos), len(crus)))
        print("  por tipo interno:")
        for tipo, n in eventos["type"].value_counts().sort_index().items():
            print("    {:16s} {}".format(tipo, n))
        print("  por Type cru (linhas cruas):")
        for tipo, n in crus["metrica_type"].value_counts().sort_index().items():
            print("    {:16s} {}".format(tipo, n))
        print(
            "  pass_secundario: {} em `events` (normativo) | {} nas linhas cruas".format(
                int(eventos["pass_secundario"].sum()), int(crus["pass_secundario"].sum())
            )
        )
        cortados = eventos["no_dead_ball_before"] & (eventos["annotated_frame"] > 1)
        print(
            "  no_dead_ball_before: {} (dos quais {} cortados pela guarda de {} s) "
            "| anchor_shift min {} max {}".format(
                int(eventos["no_dead_ball_before"].sum()),
                int(cortados.sum()),
                cfg["gabarito"]["guarda_ancora_s"],
                int(eventos["anchor_shift"].min()),
                int(eventos["anchor_shift"].max()),
            )
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.run", description=__doc__)
    parser.add_argument("--inspect", action="store_true", help="imprime o resumo dos jogos")
    parser.add_argument("--config", default=None, help="caminho alternativo do config.yaml")
    args = parser.parse_args(argv)

    cfg = carregar_config(args.config)
    if not args.inspect:
        parser.error("nesta fatia so --inspect esta implementado")
    inspecionar(cfg, carregar_mapeamento(cfg), cfg["dados"]["jogos"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
