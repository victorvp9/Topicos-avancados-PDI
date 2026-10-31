"""Ponto de entrada unico: `--inspect`, `--tau`, `--posse` e `--tau-posse`.

`python -m src.run --inspect` imprime, por jogo: numero de quadros, periodos,
fracao de bola morta, jogadores por quadro, `attack_dir`, e as contagens de
evento por tipo interno e por `Type` cru. A saida tem de bater com
docs/inspecao-metrica.md -- e a conferencia manual do Victor (plano §8.6).

`python -m src.run --tau` mede a defasagem da anotacao nos passes dos tres jogos
e diz se o GATILHO DE G3 disparou (docs/fatias/02-plano.md §6 e §9.5). Grava
`outputs/tau.csv`.

`python -m src.run --posse` roda o Passo 1 nos tres jogos, imprime as contagens
estruturais, a TABELA DE TEMPO DE PAREDE por jogo e por `R_pz` (orcamento do G4
da Fatia 8) e o diagnostico das constantes `eps_s`, `eps_v` e `eps_theta`
(docs/fatias/03-plano.md §7). O diagnostico e SO diagnostico: mudar qualquer um
dos tres depois de ver a distribuicao seria mudanca declarada (D9c).

`python -m src.run --tau-posse` mede `tau_posse` e aplica a escada
pre-registrada que decide a janela do criterio principal (plano 03 §6). Grava
`outputs/tau_posse.csv`.
"""

import argparse
import copy
import time

import numpy as np
import pandas as pd

from src import gabarito, possession, tau as tau_mod, tau_posse as tau_posse_mod
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
    resumo = tau_mod.resumir(tabela, cfg).set_index("game")
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
    for faixa in cfg["tau"]["faixas_tau_s"]:
        linha(
            "|tau| > {:g} s".format(faixa),
            "frac_tau_gt_{:g}s".format(faixa),
            "{:11.2%} ",
        )
    for faixa in cfg["tau"]["faixas_d_m"]:
        linha(
            "d_min < {:g} m".format(faixa),
            "frac_d_min_lt_{:g}m".format(faixa),
            "{:11.2%} ",
        )
    sanidade = cfg["tau"]["faixa_sanidade_d_m"]
    linha(
        "d no quadro anotado < {:g} m".format(sanidade),
        "frac_d_anotado_lt_{:g}m".format(sanidade),
        "{:11.2%} ",
    )
    linha("mediana de d no quadro anotado (m)", "mediana_d_anotado_m", "{:12.4f}")

    print("")
    print("  Reproducao de docs/inspecao-metrica.md 6.4 (distancia no quadro anotado),")
    print("  nas DUAS populacoes, que nao sao a mesma:")
    def populacao(game, rotulo, d):
        faixas = "".join(
            "< {:g} m {:6.2%}  ".format(f, (d < f).mean())
            for f in cfg["tau"]["faixas_d_m"][:2]
        )
        print(
            "    jogo {} {:<20s} n = {:4d}  {}mediana {:.4f} m".format(
                game, rotulo, d.size, faixas, float(np.nanmedian(d))
            )
        )

    for game, bruta in zip(jogos, cruas):
        populacao(game, "linhas cruas PASS", bruta["d_no_quadro_anotado_m"].to_numpy())
        populacao(
            game,
            "passes do gabarito",
            tabela[tabela["game"] == game]["d_no_quadro_anotado_m"].to_numpy(),
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


def com_r_pz(cfg: dict, r_pz: float, politica: str = None) -> dict:
    """Copia do `cfg` com `R_pz` trocado, e opcionalmente a politica de `R_dz`.

    O `R_dz` efetivo sai de `src.possession.raios`: com `acompanha_r_pz` (o
    padrao) e `max(r_dz_m; R_pz)`, que e o D3.
    """
    novo = copy.deepcopy(cfg)
    novo["posse"]["r_pz_m"] = r_pz
    if politica is not None:
        novo["posse"]["r_dz_politica"] = politica
    return novo


def _percentis(valores: np.ndarray, cfg: dict) -> str:
    """Linha de percentis de `valores`, nos percentis de `relatorio.percentis`.

    Apresentacao, nao limiar: nenhuma regra de deteccao depende destes valores.
    """
    v = np.asarray(valores, dtype="float64")
    if not np.isfinite(v).any():
        return "sem medida"
    return "  ".join(
        "p{:02d} {:9.4f}".format(q, np.nanpercentile(v, q))
        for q in cfg["relatorio"]["percentis"]
    )


def reinicio_depois_da_perda(perdas: pd.DataFrame, eventos: pd.DataFrame,
                             cfg: dict) -> pd.Series:
    """Tipo do PROXIMO reinicio do gabarito depois de cada perda.

    Entrada: `perdas` no esquema `src.possession.PERDAS` e `eventos` no esquema
    `src.io.schema.EVENTS`, do mesmo jogo ou jogos.
    Saida: Series com a contagem por `type` de bola parada, mais `nenhum` para a
    perda que nao tem reinicio depois dela (fim de jogo).

    Serve ao diagnostico da lacuna 5 pedido na revisao de 2026-10-31: se a perda
    forcada do fim da corrida precede sobretudo tiro livre, ela esta medindo
    FALTA, e falta sofrida em posse deveria terminar em ganho, nao em perda. Os
    tipos de reinicio sao os de `avaliacao.grupos.bola_parada`, que ja existe.

    **Diagnostico, nao detector**: nada aqui entra no Passo 1, logo nao ha
    circularidade com o gabarito.
    """
    tipos = cfg["avaliacao"]["grupos"]["bola_parada"]
    reinicios = (
        eventos[eventos["type"].isin(tipos)][["game", "frame", "type"]]
        .sort_values("frame", kind="stable")
    )
    casado = pd.merge_asof(
        perdas[["game", "frame"]].sort_values("frame", kind="stable"),
        reinicios,
        on="frame",
        by="game",
        direction="forward",
        allow_exact_matches=True,
    )
    return casado["type"].fillna("nenhum").value_counts()


def rodar_posse(cfg: dict, mapeamento: dict, jogos) -> dict:
    """Roda o Passo 1 nos jogos, imprime contagens, tempo de parede e o §7.

    Saida: dict `game -> resultado de src.possession.calcular` no `R_pz` do
    `config.yaml` (nao o da varredura).
    """
    print("=" * 78)
    print("PASSO 1 -- POSSE  (R_pz = {:g} m, R_dz = {:g} m, suavizar = {})".format(
        cfg["posse"]["r_pz_m"], cfg["posse"]["r_dz_m"], cfg["posse"]["suavizar"]
    ))
    resultados, eventos, tempos = {}, {}, {}
    for game in jogos:
        frames, tracking, _ = carregar_jogo(game, cfg)
        t0 = time.perf_counter()
        resultados[game] = possession.calcular(frames, tracking, cfg)
        tempos[game] = time.perf_counter() - t0
        crus = gabarito.carregar_eventos_crus(game, cfg, mapeamento)
        eventos[game] = gabarito.construir_gabarito(game, crus, frames, cfg)

    chaves = [k for k in resultados[jogos[0]]["contagens"] if k != "game"]
    print("  {:38s}".format("") + "".join("{:>12s}".format("jogo %d" % g) for g in jogos))
    for chave in chaves:
        valores = [resultados[g]["contagens"][chave] for g in jogos]
        formato = "{:12g}" if isinstance(valores[0], float) else "{:12d}"
        print("  {:38s}".format(chave) + "".join(formato.format(v) for v in valores))
    print("  {:38s}".format("tempo de parede (s)")
          + "".join("{:12.2f}".format(tempos[g]) for g in jogos))

    print("")
    print("  TEMPO DE PAREDE E SAIDA POR R_pz, NAS DUAS POLITICAS DE R_dz")
    print("  `acompanha_r_pz` = max(1,0; R_pz), que e o D3 e o principal.")
    print("  `fixo_1m` = R_dz sempre 1,00 m: desconfunde o efeito de R_pz do")
    print("  efeito de arrastar o R_dz junto (o duelo prevalece sobre a posse).")
    print("  `s_calc` = so `possession.calcular`; `s_cel` = CELULA COMPLETA, com")
    print("  o `carregar_jogo`, que e o que vale para o orcamento do G4.")
    colunas = (("posse", "possession"), ("duel", "duel"),
               ("control", "control_frames"), ("perdas", "perdas"),
               ("fim_corr", "perdas_termina_corrida"),
               ("so_lac5", "perdas_so_por_lacuna_5"), ("ganhos", "ganhos"))
    lentos = []
    for game in jogos:
        for politica in possession.POLITICAS_R_DZ:
            print("  jogo {} {:14s} {:>5s} {:>5s}".format(game, politica, "r_pz", "r_dz")
                  + "".join("{:>9s}".format(r) for r, _ in colunas)
                  + "{:>7s}{:>7s}".format("s_calc", "s_cel"))
            for r_pz in cfg["posse"]["grade_r_pz_m"]:
                cfg_r = com_r_pz(cfg, r_pz, politica)
                t0 = time.perf_counter()
                frames, tracking, _ = carregar_jogo(game, cfg_r)
                t1 = time.perf_counter()
                k = possession.calcular(frames, tracking, cfg_r)["contagens"]
                t2 = time.perf_counter()
                if t2 - t0 > cfg["relatorio"]["limiar_celula_lenta_s"]:
                    lentos.append((game, politica, r_pz, t2 - t0))
                print("  {:22s}{:6.2f}{:6.2f}".format("", r_pz, k["r_dz_m"])
                      + "".join("{:9d}".format(k[c]) for _, c in colunas)
                      + "{:7.2f}{:7.2f}".format(t2 - t1, t2 - t0))
    print("  (jogo, politica, R_pz) acima de {:g} s: {}".format(
        cfg["relatorio"]["limiar_celula_lenta_s"], lentos if lentos else "nenhum"))

    print("")
    print("  PESO DA LACUNA 5: tipo do PROXIMO reinicio do gabarito depois de")
    print("  cada perda `so_por_lacuna_5`. Se a maioria preceder tiro livre, a")
    print("  lacuna esta medindo FALTA, que deveria terminar em ganho e nao em")
    print("  perda -- a Fatia 4 teria de reportar com e sem. Diagnostico.")
    for r_pz in (cfg["posse"]["grade_r_pz_m"][0], cfg["posse"]["grade_r_pz_m"][-1]):
        cfg_r = com_r_pz(cfg, r_pz)
        for game in jogos:
            frames, tracking, _ = carregar_jogo(game, cfg_r)
            perdas = possession.calcular(frames, tracking, cfg_r)["perdas"]
            so_lac5 = perdas[perdas["so_por_lacuna_5"]]
            contagem = reinicio_depois_da_perda(so_lac5, eventos[game], cfg)
            print("    R_pz {:4.2f} jogo {}  n = {:3d}  {}".format(
                r_pz, game, len(so_lac5),
                "  ".join("{} {}".format(t, n) for t, n in contagem.items())))

    print("")
    print("  SUAVIZACAO LIGADA x DESLIGADA (lacuna 6; o teto roda DESLIGADA)")
    print("  {:>4s} {:>9s}".format("jogo", "suavizar")
          + "".join("{:>9s}".format(c) for c in
                    ("control", "perdas", "ganhos", "suavizad", "curtas")))
    for game in jogos:
        for ligada in (False, True):
            cfg_s = copy.deepcopy(cfg)
            cfg_s["posse"]["suavizar"] = ligada
            frames, tracking, _ = carregar_jogo(game, cfg_s)
            k = possession.calcular(frames, tracking, cfg_s)["contagens"]
            print("  {:4d} {:>9s}".format(game, str(ligada))
                  + "".join("{:9d}".format(k[c]) for c in
                            ("control_frames", "perdas", "ganhos", "corridas_suavizadas",
                             "corridas_curtas_sem_suavizar")))

    print("")
    print("  DIAGNOSTICO DAS CONSTANTES (plano 03 sec. 7) -- DIAGNOSTICO, NAO AJUSTE.")
    print("  Mudar eps_s, eps_v ou eps_theta depois de ver isto seria MUDANCA")
    print("  DECLARADA (D9c) e tornaria exploratorio tudo o que dependesse.")
    p = cfg["posse"]
    for game in jogos:
        r = resultados[game]
        ds = r["control"]["ds_m"].to_numpy()
        dv = r["sequencias"]["dv_max"].to_numpy()
        d0d1 = r["sequencias"]["d0d1"].to_numpy()
        anotado = eventos[game].loc[eventos[game]["type"] == "pass", "annotated_frame"]
        ds_anotado = r["ds_m"][anotado.to_numpy() - 1]
        print("  jogo {}".format(game))
        print("    ds_m nos control frames        n={:6d}  {}".format(ds.size, _percentis(ds, cfg)))
        print("      > eps_s = {:g} m: {:6.2%}   > {:g} m: {:6.2%}   (NaN: {:6.2%})".format(
            p["eps_s_m"], np.mean(ds > p["eps_s_m"]),
            p["diagnostico_eps_s_alt_m"], np.mean(ds > p["diagnostico_eps_s_alt_m"]),
            np.mean(np.isnan(ds))))
        print("    ds_m no quadro anotado (passe) n={:6d}  {}".format(
            ds_anotado.size, _percentis(ds_anotado, cfg)))
        print("      > eps_s = {:g} m: {:6.2%}   > {:g} m: {:6.2%}   (NaN: {:6.2%})".format(
            p["eps_s_m"], np.mean(ds_anotado > p["eps_s_m"]),
            p["diagnostico_eps_s_alt_m"], np.mean(ds_anotado > p["diagnostico_eps_s_alt_m"]),
            np.mean(np.isnan(ds_anotado))))
        print("    dv_max por sequencia           n={:6d}  {}".format(dv.size, _percentis(dv, cfg)))
        print("      > eps_v = {:g} m/s: {:6.2%}  > {:g} m/s: {:6.2%}  (NaN: {:6.2%})".format(
            p["eps_v_ms"], np.mean(dv > p["eps_v_ms"]),
            p["diagnostico_eps_v_alt_ms"], np.mean(dv > p["diagnostico_eps_v_alt_ms"]),
            np.mean(np.isnan(dv))))
        print("    d0d1 por sequencia             n={:6d}  {}".format(
            d0d1.size, _percentis(d0d1, cfg)))
        print("      < eps_theta = {:.6f}: {:6.2%}   (NaN: {:6.2%})".format(
            p["eps_theta"], np.mean(d0d1 < p["eps_theta"]), np.mean(np.isnan(d0d1))))
    print("=" * 78)
    return resultados


def medir_tau_posse(cfg: dict, mapeamento: dict, jogos, gravar_em=None) -> pd.DataFrame:
    """Mede `tau_posse`, aplica a escada pre-registrada e grava o CSV.

    A decisao usa `tau_posse.r_pz_da_decisao_m` (0,50 m), travado de proposito:
    senao a escolha da janela passaria a depender de `R_pz`, que e a variavel
    independente do projeto (plano 03 §6.2). A sensibilidade em
    `r_pz_sensibilidade_m` e impressa e NAO decide.
    """
    def medir(r_pz):
        """Devolve (tabela TAU_POSSE, control, perdas) dos jogos, no `R_pz` dado."""
        cfg_r = com_r_pz(cfg, r_pz)
        eventos, perdas, control = [], [], []
        for game in jogos:
            frames, tracking, _ = carregar_jogo(game, cfg_r)
            crus = gabarito.carregar_eventos_crus(game, cfg_r, mapeamento)
            eventos.append(gabarito.construir_gabarito(game, crus, frames, cfg_r))
            resultado = possession.calcular(frames, tracking, cfg_r)
            perdas.append(resultado["perdas"])
            control.append(resultado["control"])
        perdas = pd.concat(perdas, ignore_index=True)
        return (
            tau_posse_mod.medir(pd.concat(eventos, ignore_index=True), perdas, cfg_r),
            pd.concat(control, ignore_index=True),
            perdas,
        )

    r_decisao = cfg["tau_posse"]["r_pz_da_decisao_m"]
    tabela, control, perdas = medir(r_decisao)
    resumo = tau_posse_mod.resumir(tabela, cfg).set_index("game")
    colunas = [int(g) for g in jogos] + [0]
    rotulos = ["jogo {}".format(g) for g in jogos] + ["AGRUPADO"]

    def linha(titulo, chave, formato):
        print("  {:36s}".format(titulo)
              + "".join(formato.format(resumo.loc[c, chave]) for c in colunas))

    print("=" * 78)
    print("tau_posse = (annotated_frame - loss_frame) / fps   [R_pz = {:g} m, travado]".format(
        r_decisao))
    print("  tau > 0: a anotacao veio DEPOIS da perda de posse detectada")
    print("  janela de busca: +-{:g} s".format(cfg["tau_posse"]["janela_busca_s"]))
    print("  {:36s}".format("") + "".join("{:>12s}".format(r) for r in rotulos))
    print("  -- (a) TETO DE REVOCACAO: denominador = todos os passes")
    linha("passes anotados", "n", "{:12.0f}")
    linha("sem perda nenhuma na janela", "n_sem_perda", "{:12.0f}")
    linha("fracao SEM PERDA", "frac_sem_perda", "{:11.2%} ")
    print("  -- (b) O PORTAO: denominador = so os passes COM perda")
    linha("passes com perda", "n_com_perda", "{:12.0f}")
    linha("media de tau (s)", "media_tau_s", "{:12.3f}")
    linha("mediana de tau (s)", "mediana_tau_s", "{:12.3f}")
    linha("media de |tau| (s)", "media_abs_tau_s", "{:12.3f}")
    for faixa in [c for c in resumo.columns if c.startswith("frac_tau_gt_")]:
        linha("|tau| > " + faixa[len("frac_tau_gt_"):], faixa, "{:11.2%} ")
    abs_tau = tabela.loc[tabela["tem_perda"], "tau_posse_s"].abs().to_numpy()
    print("  |tau| entre os que tem perda (s): {}".format(_percentis(abs_tau, cfg)))

    print("  -- (c) DECOMPOSICAO DOS SEM PERDA: qual restricao morde (diagnostico)")
    dec = tau_posse_mod.decompor_sem_perda(tabela, control, perdas, cfg).set_index("game")
    for titulo, chave in (
        ("(i) nao foi dono de control frame", "sem_control_frame"),
        ("(ii) foi dono, nenhuma perda saiu", "com_control_sem_perda"),
        ("(iii) casou perda de outro (=0)", "casou_outro_jogador"),
    ):
        print("  {:36s}".format(titulo)
              + "".join("{:12.0f}".format(dec.loc[c, chave]) for c in colunas))
    print("  (i) aponta para a PZ (R_pz); (ii) para a regra de perda (eps_s ou a")
    print("  condicao 2). (i) inclui quem so participou de duelo, onde nao ha dono.")

    d = tau_posse_mod.decidir_janela(tabela, cfg)
    print("")
    print("  " + "#" * 74)
    print("  ##  ESCADA PRE-REGISTRADA  {} s, limiar {:.0%} dos passes COM perda".format(
        d["escada"], d["limiar_fracao"]))
    for degrau in d["escada"]:
        print("  ##    {:4.1f} s: {:7.2%} acima  -> {}".format(
            degrau, d["fracoes"][float(degrau)],
            "satisfaz" if d["fracoes"][float(degrau)] <= d["limiar_fracao"] else "nao satisfaz"))
    print("  ##  JANELA RECOMENDADA: {}".format(
        "{:g} s".format(d["janela_s"]) if d["janela_s"] is not None
        else "NENHUMA -- escada ESGOTADA"))
    print("  ##  fracao sem perda {:.2%} (limiar de G3: {:.0%}) -> {}".format(
        d["frac_sem_perda"], d["limiar_sem_perda_g3"],
        "ACIMA" if d["sem_perda_acima_do_limiar"] else "abaixo"))
    print("  ##  G3: {}".format("SIM -- PARAR" if d["g3"] else "nao"))
    print("  ##  Quem aplica a escada e registra em decisoes.md e o orquestrador")
    print("  ##  (plano 03 sec. 6.3). Este comando mede e para.")
    print("  " + "#" * 74)

    print("")
    print("  SENSIBILIDADE em R_pz (NAO decide, plano sec. 6.2 -- a decisao e")
    print("  travada em {:g} m de proposito):".format(r_decisao))
    for r_sens in cfg["tau_posse"]["r_pz_sensibilidade_m"]:
        sens = tau_posse_mod.decidir_janela(medir(r_sens)[0], cfg)
        print("    R_pz = {:4.2f} m | sem perda {:6.2%} | acima dos degraus: {} | "
              "escada daria: {}".format(
                  r_sens, sens["frac_sem_perda"],
                  "  ".join("{:g}s {:5.2%}".format(k, v)
                            for k, v in sens["fracoes"].items()),
                  "{:g} s".format(sens["janela_s"]) if sens["janela_s"] is not None
                  else "nenhuma (esgotada)"))
    print("=" * 78)

    destino = RAIZ_REPO / "outputs" / "tau_posse.csv" if gravar_em is None else gravar_em
    destino.parent.mkdir(parents=True, exist_ok=True)
    tabela.to_csv(destino, index=False)
    print("gravado: {} ({} linhas)".format(destino, len(tabela)))
    return tabela


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.run", description=__doc__)
    parser.add_argument("--inspect", action="store_true", help="imprime o resumo dos jogos")
    parser.add_argument("--tau", action="store_true", help="mede a defasagem da anotacao")
    parser.add_argument("--posse", action="store_true", help="roda o Passo 1 (posse)")
    parser.add_argument("--tau-posse", action="store_true",
                        help="mede tau_posse e aplica a escada pre-registrada")
    parser.add_argument("--config", default=None, help="caminho alternativo do config.yaml")
    args = parser.parse_args(argv)

    cfg = carregar_config(args.config)
    if not (args.inspect or args.tau or args.posse or args.tau_posse):
        parser.error("escolha --inspect, --tau, --posse ou --tau-posse")
    mapeamento = carregar_mapeamento(cfg)
    if args.inspect:
        inspecionar(cfg, mapeamento, cfg["dados"]["jogos"])
    if args.tau:
        medir_tau(cfg, mapeamento, cfg["dados"]["jogos"])
    if args.posse:
        rodar_posse(cfg, mapeamento, cfg["dados"]["jogos"])
    if args.tau_posse:
        medir_tau_posse(cfg, mapeamento, cfg["dados"]["jogos"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
