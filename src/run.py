"""Ponto de entrada unico: `--inspect` (Fatia 1) e `--tau` (Fatia 2).

`python -m src.run --inspect` imprime, por jogo: numero de quadros, periodos,
fracao de bola morta, jogadores por quadro, `attack_dir`, e as contagens de
evento por tipo interno e por `Type` cru. A saida tem de bater com
docs/inspecao-metrica.md -- e a conferencia manual do Victor (plano §8.6).

`python -m src.run --tau` mede a defasagem da anotacao nos passes dos tres jogos
e diz se o GATILHO DE G3 disparou (docs/fatias/02-plano.md §6 e §9.5). Grava
`outputs/tau.csv`.
"""

import argparse

import numpy as np
import pandas as pd

from src import gabarito, tau as tau_mod
from src.config import RAIZ_REPO, carregar_config, carregar_mapeamento
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


def medir_tau(cfg: dict, mapeamento: dict, jogos, gravar_em=None) -> pd.DataFrame:
    """Mede `tau` nos passes de cada jogo, imprime o relatorio e grava o CSV.

    Saida impressa (plano §9.5): por jogo e no total, `n`, media, mediana, as
    quatro fracoes de `|tau|`, as tres faixas de `d_min`, a reproducao da §6.4 da
    inspecao e, EM DESTAQUE, se o gatilho de G3 disparou.

    A reproducao da §6.4 e medida duas vezes de proposito, porque sao duas
    populacoes: as linhas cruas `PASS` da Metrica (o que a inspecao mediu) e os
    passes do gabarito depois da fusao do `SET PIECE` e da reclassificacao do
    `PASS/GOAL KICK` (o que esta fatia avalia).
    """
    tabelas, cruas = [], []
    for game in jogos:
        frames, tracking, _ = carregar_jogo(game, cfg)
        crus = gabarito.carregar_eventos_crus(game, cfg, mapeamento)
        eventos = gabarito.construir_gabarito(game, crus, frames, cfg)
        tabelas.append(tau_mod.medir(game, eventos, frames, tracking, cfg))
        linhas_pass = crus[crus["metrica_type"] == "PASS"].assign(type="pass")
        cruas.append(tau_mod.medir(game, linhas_pass, frames, tracking, cfg))

    tabela = pd.concat(tabelas, ignore_index=True)
    resumo = tau_mod.resumir(tabela).set_index("game")
    colunas = [int(g) for g in jogos] + [0]
    rotulos = ["jogo {}".format(g) for g in jogos] + ["TOTAL"]

    def linha(titulo, chave, formato):
        print(
            "  {:34s}".format(titulo)
            + "".join(formato.format(resumo.loc[c, chave]) for c in colunas)
        )

    print("=" * 78)
    print("DEFASAGEM DA ANOTACAO  tau = (annotated_frame - frame_d) / fps")
    print("  tau > 0: a anotacao veio DEPOIS do quadro de minima distancia (S3, p. 5)")
    print("  janela de busca: +-{:g} s".format(cfg["tau"]["janela_s"]))
    print("  {:34s}".format("") + "".join("{:>12s}".format(r) for r in rotulos))
    linha("passes (denominador)", "n", "{:12.0f}")
    linha("com medida", "n_medidos", "{:12.0f}")
    linha("media de tau (s)", "media_tau_s", "{:12.3f}")
    linha("mediana de tau (s)", "mediana_tau_s", "{:12.3f}")
    for faixa in tau_mod.FAIXAS_TAU_S:
        linha(
            "|tau| > {:g} s".format(faixa),
            "frac_tau_gt_{:g}s".format(faixa),
            "{:11.2%} ",
        )
    for faixa in tau_mod.FAIXAS_D_M:
        linha(
            "d_min < {:g} m".format(faixa),
            "frac_d_min_lt_{:g}m".format(faixa),
            "{:11.2%} ",
        )
    linha("d no quadro anotado < 0,5 m", "frac_d_anotado_lt_0.5m", "{:11.2%} ")
    linha("mediana de d no quadro anotado (m)", "mediana_d_anotado_m", "{:12.4f}")

    print("")
    print("  Reproducao de docs/inspecao-metrica.md 6.4 (distancia no quadro anotado),")
    print("  nas DUAS populacoes, que nao sao a mesma:")
    for game, bruta in zip(jogos, cruas):
        d = bruta["d_no_quadro_anotado_m"].to_numpy()
        print(
            "    jogo {} linhas cruas PASS   n = {:4d}  < 0,5 m {:6.2%}  < 1 m {:6.2%}  "
            "mediana {:.4f} m".format(
                game, d.size, (d < 0.5).mean(), (d < 1.0).mean(), float(np.nanmedian(d))
            )
        )
        bloco = tabela[tabela["game"] == game]["d_no_quadro_anotado_m"].to_numpy()
        print(
            "    jogo {} passes do gabarito  n = {:4d}  < 0,5 m {:6.2%}  < 1 m {:6.2%}  "
            "mediana {:.4f} m".format(
                game,
                bloco.size,
                (bloco < 0.5).mean(),
                (bloco < 1.0).mean(),
                float(np.nanmedian(bloco)),
            )
        )

    g3 = tau_mod.gatilho_g3(tabela, cfg)
    acima = int(round(g3["fracao"] * g3["n"]))
    print("")
    print("  " + "#" * 74)
    print(
        "  ##  GATILHO DE G3: {}".format(
            "DISPAROU" if g3["disparou"] else "nao disparou"
        )
    )
    print(
        "  ##  |tau| > {:g} s em {} de {} passes = {:.2%}".format(
            g3["limiar_tau_s"], acima, g3["n"], g3["fracao"]
        )
    )
    print(
        "  ##  limiar escrito antes de medir: {:.2%} | faixa ambigua {:.0%}-{:.0%}".format(
            g3["limiar_fracao"], *cfg["tau"]["faixa_ambigua"]
        )
    )
    if g3["disparou"]:
        print("  ##  A janela de +-1 s do criterio principal (D8) esta CONTRADITA.")
        print("  ##  PARAR antes de qualquer detector: a decisao e do Victor, no G3.")
    elif g3["ambiguo"]:
        print("  ##  Resultado AMBIGUO: levar ao G3 de todo modo (plano 6.1).")
    print("  " + "#" * 74)
    print("=" * 78)

    destino = RAIZ_REPO / "outputs" / "tau.csv" if gravar_em is None else gravar_em
    destino.parent.mkdir(parents=True, exist_ok=True)
    tabela.to_csv(destino, index=False)
    print("gravado: {} ({} linhas)".format(destino, len(tabela)))
    return tabela


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.run", description=__doc__)
    parser.add_argument("--inspect", action="store_true", help="imprime o resumo dos jogos")
    parser.add_argument("--tau", action="store_true", help="mede a defasagem da anotacao")
    parser.add_argument("--config", default=None, help="caminho alternativo do config.yaml")
    args = parser.parse_args(argv)

    cfg = carregar_config(args.config)
    if not (args.inspect or args.tau):
        parser.error("escolha --inspect ou --tau")
    mapeamento = carregar_mapeamento(cfg)
    if args.inspect:
        inspecionar(cfg, mapeamento, cfg["dados"]["jogos"])
    if args.tau:
        medir_tau(cfg, mapeamento, cfg["dados"]["jogos"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
