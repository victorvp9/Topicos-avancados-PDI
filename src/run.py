"""Ponto de entrada unico: `--inspect`, `--tau`, `--posse`, `--tau-posse`,
`--bola-parada` e `--passes`.

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

`python -m src.run --bola-parada` roda o Passo 2 nos tres jogos e imprime, nesta
ordem: a TABELA CONTRA OS TETOS PREVISTOS do plano 04 §2 (numero de deteccoes,
teto de precisao, revocacao de gatilho dos jogos 1+2 e a sensibilidade de 1 s),
a primeira tabela de F1 real do projeto nos tres criterios e nas duas ancoras,
a matriz de confusao de bola parada, a distribuicao da coluna `via`, a curva
F1(`eps_c`) da grade de D9b -- **sem escolher um otimo** -- e os dois requisitos
que vem da revisao da Fatia 3 (com e sem as perdas `so_por_lacuna_5`, e o
contador de trocas de dono por duelo). Grava `outputs/deteccoes.csv`.

`python -m src.run --passes` rotula as perdas de posse como passes, avalia nos
tres criterios contra o gabarito principal (`PASS`) e o secundario, e decompoe
os falsos negativos do principal por causa (docs/fatias/05-plano.md §6). Grava
`outputs/passes.csv`.
"""

import argparse
import copy
import time

import numpy as np
import pandas as pd

from src import evaluate, gabarito, possession, tau as tau_mod, tau_posse as tau_posse_mod
from src.config import RAIZ_REPO, carregar_config, carregar_mapeamento
from src.events import bola_parada, gatilhos, hierarquia, passes as passes_mod
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


def trocas_de_dono_por_duelo(control: pd.DataFrame, sequencias: pd.DataFrame) -> dict:
    """Donos distintos e trocas de dono DENTRO de cada duelo, num jogo.

    Entrada: `control` e `sequencias` de `src.possession.calcular`.
    Saida: dict com `duelos`, `duelos_2_mais_donos`, `frac_2_mais`, `trocas` e
    `trocas_por_duelo`.

    Em quadro de duelo o `control` nao traz dono (em duelo nao existe dono, por
    construcao do Passo 1), mas o `sequencias` traz: o jogador "em controle" --
    o mais proximo com a bola na propria PZ -- e unico por quadro, inclusive em
    duelo (revisao de 2026-10-31). Os intervalos `[frame_f0, frame_fn]` nao se
    sobrepoem exatamente por isso, e e o que permite a busca binaria abaixo.

    Requisito da revisao da Fatia 3, registrado em `decisoes.md`: a 3,00 m, 62 a
    65 % dos duelos tem 2+ donos e um deles tem 9, o que e a origem provavel de
    recepcao espuria -- de uma recepcao que a Fatia 5 vai medir. **Diagnostico**:
    nada aqui entra no detector de bola parada.

    Uma troca = par de quadros CONSECUTIVOS do mesmo duelo com donos diferentes
    e nenhum deles vazio. O criterio esta aqui porque o numero depende dele.
    """
    frames_duelo = control.loc[
        control["ball_control"] == possession.DUEL, "frame"
    ].to_numpy()
    if frames_duelo.size == 0:
        return {"duelos": 0, "duelos_2_mais_donos": 0, "frac_2_mais": np.nan,
                "trocas": 0, "trocas_por_duelo": np.nan}
    duelo_id = np.cumsum(np.r_[True, np.diff(frames_duelo) > 1])
    f0 = sequencias["frame_f0"].to_numpy()
    fn = sequencias["frame_fn"].to_numpy()
    jogador = sequencias["player_id"].to_numpy()
    k = np.searchsorted(f0, frames_duelo, side="right") - 1
    seguro = np.maximum(k, 0)
    tem = (k >= 0) & (frames_duelo <= fn[seguro])
    dono = np.where(tem, jogador[seguro], "")
    mesmo = duelo_id[1:] == duelo_id[:-1]
    troca = mesmo & (dono[1:] != dono[:-1]) & (dono[1:] != "") & (dono[:-1] != "")
    tabela = pd.DataFrame({"duelo": duelo_id, "dono": dono})
    donos = tabela[tabela["dono"] != ""].groupby("duelo")["dono"].nunique()
    n_duelos = int(duelo_id[-1])
    return {
        "duelos": n_duelos,
        "duelos_2_mais_donos": int((donos >= 2).sum()),
        "frac_2_mais": float((donos >= 2).sum()) / n_duelos,
        "trocas": int(troca.sum()),
        "trocas_por_duelo": float(troca.sum()) / n_duelos,
    }


def revocacao_de_gatilho(base: dict, cfg: dict, jogos) -> pd.DataFrame:
    """Teto de revocacao POR GATILHO: o executor anotado ativa o gatilho do seu
    proprio tipo no primeiro quadro em jogo?

    Entrada: `base` de `_carregar_base`. Saida: DataFrame com `game`, `type`,
    `n`, `ativa` e a fracao.

    E a replica da medicao de `docs/inspecao-metrica.md` §6.2, que o plano 04 §2
    usa como teto previsto: mede a GEOMETRIA contra o gabarito, sem hierarquia,
    sem posse e sem padrao. Evento nao detectado e perda de revocacao, nunca
    exclusao: o denominador e o gabarito inteiro, inclusive os eventos com
    `no_dead_ball_before` (decisoes.md, G3 da Fatia 1).
    """
    linhas = []
    for game in jogos:
        dados = base[game]
        ativo = gatilhos.ativacoes(
            dados["px"], dados["py"], dados["times"], dados["lado"], cfg
        )
        eventos = dados["eventos"]
        for tipo in gatilhos.TIPOS:
            sub = eventos[eventos["type"] == tipo]
            if sub.empty:
                continue
            p = dados["jogadores"].get_indexer(sub["player_id"])
            f = sub["frame"].to_numpy() - 1
            if (p < 0).any():
                raise ValueError("gabarito com player_id fora do tracking")
            linhas.append({"game": game, "type": tipo, "n": len(sub),
                           "ativa": int(ativo[tipo][p, f].sum())})
    tabela = pd.DataFrame(linhas)
    tabela["fracao"] = tabela["ativa"] / tabela["n"]
    return tabela


def _carregar_base(cfg: dict, mapeamento: dict, jogos) -> dict:
    """Carrega uma vez por jogo tudo o que o Passo 2 consome.

    Saida: `game -> dict` com `frames`, `tracking`, `periods`, `eventos`,
    `perdas` (Passo 1 no `R_pz` do config), `control`, `sequencias` e as
    matrizes de posicao, para que a varredura de `eps_c` e as variantes nao
    repitam carga nem Passo 1.
    """
    base = {}
    for game in jogos:
        frames, tracking, periods = carregar_jogo(game, cfg)
        passo1 = possession.calcular(frames, tracking, cfg)
        crus = gabarito.carregar_eventos_crus(game, cfg, mapeamento)
        jogadores, px, py, _, _ = tau_mod.grade_de_posicoes(frames, tracking)
        times = (
            tracking.drop_duplicates("player_id")
            .set_index("player_id")["team"]
            .reindex(jogadores)
            .to_numpy()
        )
        base[game] = {
            "frames": frames,
            "tracking": tracking,
            "periods": periods,
            "eventos": gabarito.construir_gabarito(game, crus, frames, cfg),
            "perdas": passo1["perdas"],
            "ganhos": passo1["ganhos"],
            "control": passo1["control"],
            "sequencias": passo1["sequencias"],
            "jogadores": jogadores,
            "px": px,
            "py": py,
            "times": times,
            "lado": bola_parada.attack_dir_por_jogador(frames, periods, times),
        }
    return base


def detectar_jogos(base: dict, cfg: dict, jogos, sem_lacuna_5: bool = False):
    """Roda o detector nos jogos e concatena. `sem_lacuna_5` filtra as perdas
    que existem apenas pela lacuna 5 da Fatia 3 (plano 04 §3.6.1)."""
    saida = []
    for game in jogos:
        perdas = base[game]["perdas"]
        if sem_lacuna_5:
            perdas = perdas[~perdas["so_por_lacuna_5"]]
        saida.append(
            bola_parada.detectar(
                base[game]["frames"],
                base[game]["tracking"],
                base[game]["periods"],
                perdas,
                cfg,
            )
        )
    return pd.concat(saida, ignore_index=True)


def deteccoes_na_ancora(deteccoes: pd.DataFrame, eventos: pd.DataFrame, cfg: dict) -> np.ndarray:
    """(n_deteccoes,) bool: o (`game`, `frame`) da deteccao e a ancora `frame`
    de algum reinicio do gabarito (grupo `bola_parada`).

    So essas podem ser acerto, logo `soma / n` e o teto de PRECISAO. As demais
    sao os intervalos mortos sem reinicio anotado ("espurios")."""
    tipos = cfg["avaliacao"]["grupos"]["bola_parada"]
    ancoras = eventos.loc[eventos["type"].isin(tipos), ["game", "frame"]]
    return pd.MultiIndex.from_frame(deteccoes[["game", "frame"]]).isin(
        pd.MultiIndex.from_frame(ancoras))


def _tabela_f1(eventos: pd.DataFrame, deteccoes: pd.DataFrame, cfg: dict,
               criterios=None, ancoras=None):
    """Imprime P/R/F1 e contagem absoluta por tipo de bola parada, agregado nos
    tres jogos (`game = 0`), em cada criterio e ancora pedidos.

    `penalty` sai com a contagem absoluta e **nunca** entra no micro: `micro()`
    levanta `ValueError` se receber (n = 1 nos tres jogos). `free_kick?` e
    categoria propria e **nunca** e somado em `free_kick`.

    `tp` ("casou") e o numero de eventos daquele tipo que casaram com ALGUMA
    deteccao, ignorando o tipo detectado; `tp_diag` e a diagonal da matriz e e o
    unico numerador de P/R/F1 nos tres criterios. Em `estrito` e `mills` os dois
    sao iguais por construcao; em `vidal_codina`, que nao casa por tipo, a
    diferenca e exatamente a confusao de tipo.
    """
    resultado, confusao = evaluate.avaliar(
        eventos, bola_parada.para_casador(deteccoes), cfg
    )
    tipos = cfg["avaliacao"]["grupos"]["bola_parada"]
    for criterio in criterios or cfg["avaliacao"]["criterios"]:
        for ancora in ancoras or cfg["avaliacao"]["ancoras"]:
            bloco = resultado[
                (resultado["criterio"] == criterio)
                & (resultado["ancora"] == ancora)
                & (resultado["game"] == 0)
                & (resultado["type"].isin(tipos))
            ]
            print("  criterio {:14s} ancora {:16s}".format(criterio, ancora)
                  + "{:>6s}{:>6s}{:>6s}{:>7s}{:>8s}{:>8s}{:>8s}".format(
                      "n_gab", "n_det", "tp", "casou", "P", "R", "F1"))
            indexado = bloco.set_index("type")
            for tipo in tipos:
                linha = indexado.loc[tipo]
                print("    {:28s}".format(tipo)
                      + "{:6d}{:6d}{:6d}{:7d}".format(
                          linha["n_gabarito"], linha["n_detectado"], linha["tp_diag"],
                          linha["tp"])
                      + "".join("{:8.3f}".format(linha[c])
                               for c in ("precisao", "revocacao", "f1")))
            agregado = evaluate.micro(bloco[bloco["type"] != "penalty"])
            print("    {:28s}".format("MICRO (sem penalty)")
                  + "{:6d}{:6d}{:6d}{:7s}".format(
                      agregado["n_gabarito"], agregado["n_detectado"],
                      agregado["tp_diag"], "")
                  + "".join("{:8.3f}".format(agregado[c])
                            for c in ("precisao", "revocacao", "f1")))
    return resultado, confusao


def rodar_bola_parada(cfg: dict, mapeamento: dict, jogos, gravar_em=None):
    """Roda o Passo 2 nos jogos e imprime o relatorio do plano 04.

    Saida: (deteccoes, resultado, confusao) do caminho principal.
    """
    base = _carregar_base(cfg, mapeamento, jogos)
    eventos = pd.concat([base[g]["eventos"] for g in jogos], ignore_index=True)
    tipos_bp = cfg["avaliacao"]["grupos"]["bola_parada"]
    reinicios = eventos[eventos["type"].isin(tipos_bp)]
    principal = cfg["avaliacao"]["criterio_principal"]
    p = cfg["bola_parada"]

    print("=" * 78)
    print("PASSO 2 -- BOLAS PARADAS (R_pz = {:g} m, duracao minima morta = {:g} s)".format(
        cfg["posse"]["r_pz_m"], p["duracao_minima_morta_s"]))
    deteccoes = detectar_jogos(base, cfg, jogos)

    print("")
    print("  (1) CONTRA OS TETOS PREVISTOS (plano 04 sec. 2)")
    print("  {:>6s}{:>12s}{:>12s}{:>12s}{:>10s}{:>10s}".format(
        "jogo", "transicoes", "deteccoes", "reinicios", "na_ancora", "teto_P"))
    transicoes = {
        g: bola_parada.corridas_mortas(base[g]["frames"]["ball_live"])[0].size
        for g in jogos
    }
    na_ancora = deteccoes_na_ancora(deteccoes, eventos, cfg)
    for game in list(jogos) + [0]:
        sel = np.ones(len(deteccoes), bool) if game == 0 else (
            deteccoes["game"] == game).to_numpy()
        gab = reinicios if game == 0 else reinicios[reinicios["game"] == game]
        n_trans = sum(transicoes.values()) if game == 0 else transicoes[game]
        print("  {:>6s}{:12d}{:12d}{:12d}{:10d}{:9.1f}%".format(
            "TOTAL" if game == 0 else str(game), n_trans, int(sel.sum()), len(gab),
            int(na_ancora[sel].sum()), 100.0 * na_ancora[sel].sum() / sel.sum()))
    print("  teto de precisao = `na_ancora / deteccoes`: so a deteccao que cai na")
    print("  ancora `frame` de um reinicio anotado pode ser acerto. NAO e")
    print("  `reinicios / deteccoes` (61,5 %, superado em 2026-11-04): os 13")
    print("  `no_dead_ball_before` nao tem transicao morta -> viva, logo nenhuma")
    print("  deteccao casa com eles. O detector emite UMA bola parada por")
    print("  transicao, e a Metrica tem mais transicoes que reinicios porque a")
    print("  bola fica NaN em buracos curtos de rastreamento (plano 04 sec. 2.2).")

    print("")
    print("  REVOCACAO DE GATILHO -- a geometria contra o gabarito, sem hierarquia")
    rev = revocacao_de_gatilho(base, cfg, jogos)
    for rotulo, sub in (
        *(("jogo %d" % g, rev[rev["game"] == g]) for g in jogos),
        ("JOGOS 1+2 (o teto)", rev[rev["game"].isin([1, 2])]),
        ("os tres jogos", rev),
    ):
        soma = sub.groupby("type")[["n", "ativa"]].sum()
        print("    {:20s}".format(rotulo)
              + "  ".join("{} {}/{} = {:4.1f}%".format(
                  t, int(r["ativa"]), int(r["n"]), 100.0 * r["ativa"] / r["n"])
                  for t, r in soma.iterrows()))

    print("")
    print("  (2) F1 REAL, POR TIPO, nos tres criterios e nas duas ancoras")
    print("  o criterio `estrito` (tipo + jogador + 1 s) e NOSSO, D8, nao de artigo")
    resultado, confusao = _tabela_f1(eventos, deteccoes, cfg)

    print("")
    print("  MATRIZ DE CONFUSAO DO GRUPO `bola_parada` (criterio {}, ancora".format(
        principal))
    print("  `frame`, tres jogos somados). Linha = gabarito, coluna = detectado.")
    for criterio in (principal, "vidal_codina"):
        cel = confusao[
            (confusao["criterio"] == criterio)
            & (confusao["ancora"] == "frame")
            & (confusao["grupo"] == "bola_parada")
        ]
        print("  -- criterio {}".format(criterio))
        print(cel.pivot_table(index="type_gabarito", columns="type_detectado",
                              values="n", aggfunc="sum", fill_value=0).to_string())
    print("  `free_kick?` nunca aparece como linha: o gabarito nao o tem, logo")
    print("  toda deteccao dele e falso positivo -- e e informativo (S2, p. 3).")
    print("  A confusao de TIPO (escanteio virando tiro livre, §2.4.1, p. 8) so")
    print("  aparece no criterio `vidal_codina`: `estrito` e `mills` casam por")
    print("  tipo, logo celula fora da diagonal deles e impossivel por construcao.")

    print("")
    print("  (3) DISTRIBUICAO DE `via` -- o analogo dos 85 % -> 95 % do S1")
    print(pd.crosstab(deteccoes["type"], deteccoes["via"], margins=True).to_string())
    print("  `via` = o ESTAGIO que decidiu (ver src/events/hierarquia.py):")
    print("  `padrao` = gatilho completo confirmado por padrao, na principal.")
    # o corte vem de `sensibilidade_duracao_minima_s`, nunca hardcoded
    corte = p["sensibilidade_duracao_minima_s"][-1]
    longa = deteccoes["dur_morta_s"] >= corte
    print("  bola morta >= {:g} s: {}".format(
        corte, dict(deteccoes.loc[longa, "via"].value_counts())))
    print("  bola morta <  {:g} s: {}".format(
        corte, dict(deteccoes.loc[~longa, "via"].value_counts())))
    print("")
    print("  DECOMPOSICAO DAS {} DECISOES POR CAUSA (portao do problema 1 do S1).".format(
        len(deteccoes)))
    print("  `motivo_reserva1` e o estado do portao, independente de a principal")
    print("  ter decidido antes. `sem_passe_do_executor` e a LACUNA declarada em")
    print("  `src/events/bola_parada.py:_primeiro_passe`, que vale 14 acertos e")
    print("  acopla bola parada a revocacao de perda do Passo 1 (revisao 2026-11-02).")
    print(pd.crosstab(deteccoes["motivo_reserva1"], deteccoes["via"],
                      margins=True).to_string())
    print(pd.crosstab(deteccoes["motivo_reserva1"], deteccoes["type"]).to_string())

    print("")
    print("  (4) SENSIBILIDADE DA DURACAO MINIMA DE BOLA MORTA (plano 04 sec. 3.1)")
    print("  o principal NAO aplica minimo; o 1 s e NOSSO, do Bassek, Metodos, p. 4")
    for minimo in p["sensibilidade_duracao_minima_s"]:
        cfg_d = copy.deepcopy(cfg)
        cfg_d["bola_parada"]["duracao_minima_morta_s"] = minimo
        det_d = detectar_jogos(base, cfg_d, jogos)
        ancora_d = deteccoes_na_ancora(det_d, eventos, cfg)
        print("    minimo {:4.1f} s: {:4d} deteccoes | {:4d} na ancora | teto de precisao "
              "{:5.1f}%".format(minimo, len(det_d), int(ancora_d.sum()),
                                100.0 * ancora_d.sum() / len(det_d)))
        if minimo:
            _tabela_f1(eventos, det_d, cfg, [principal], ["frame"])

    print("")
    print("  (5) CURVA F1(eps_c) na grade de D9b -- BAIXA CONFIANCA.")
    print("  O conjunto nao visto tem 8 escanteios de 3 cobradores (decisoes.md);")
    print("  1 escanteio move a taxa em 12,5 pontos. NENHUM otimo e escolhido:")
    print("  o valor publicado, eps_c = 3 m, segue sendo o numero principal.")
    print("    {:>7s}{:>7s}{:>7s}{:>5s}{:>8s}{:>8s}{:>8s}{:>9s}".format(
        "eps_c", "n_gab", "n_det", "tp", "P", "R", "F1", "F1_micro"))
    for eps_c in p["grade_eps_c_m"]:
        cfg_e = copy.deepcopy(cfg)
        cfg_e["bola_parada"]["eps_c_m"] = eps_c
        det_e = detectar_jogos(base, cfg_e, jogos)
        res_e, _ = evaluate.avaliar(eventos, bola_parada.para_casador(det_e), cfg)
        bloco = res_e[(res_e["criterio"] == principal) & (res_e["ancora"] == "frame")
                      & (res_e["game"] == 0) & (res_e["type"].isin(tipos_bp))]
        linha = bloco[bloco["type"] == "corner_kick"].iloc[0]
        micro = evaluate.micro(bloco[bloco["type"] != "penalty"])
        print("    {:7.1f}{:7d}{:7d}{:5d}{:8.3f}{:8.3f}{:8.3f}{:9.3f}".format(
            eps_c, linha["n_gabarito"], linha["n_detectado"], linha["tp_diag"],
            linha["precisao"], linha["revocacao"], linha["f1"], micro["f1"]))

    print("")
    print("  (6) COM E SEM AS PERDAS `so_por_lacuna_5` (revisao da Fatia 3).")
    print("  So o problema 1 do S1 usa as perdas: elas dizem onde esta o primeiro")
    print("  passe depois da bola morta. Acima de R_pz = 1 m a variante `sem` nao")
    print("  e opcional, porque a lacuna 5 chega a 13-14 % de todas as perdas.")
    det_sem = detectar_jogos(base, cfg, jogos, sem_lacuna_5=True)
    diferentes = int((deteccoes["type"].to_numpy() != det_sem["type"].to_numpy()).sum())
    print("    deteccoes com rotulo diferente: {} de {}".format(
        diferentes, len(deteccoes)))
    print("    sem lacuna 5, por via: {}".format(dict(det_sem["via"].value_counts())))
    _tabela_f1(eventos, det_sem, cfg, [principal], ["frame"])

    print("")
    print("  (7) TROCAS DE DONO POR DUELO (requisito da revisao da Fatia 3).")
    print("  Diagnostico de RECEPCAO, que e da Fatia 5; aqui so o contador.")
    for r_pz in (cfg["posse"]["r_pz_m"], cfg["posse"]["grade_r_pz_m"][-1]):
        for game in jogos:
            if r_pz == cfg["posse"]["r_pz_m"]:
                passo1 = base[game]
            else:
                passo1 = possession.calcular(
                    base[game]["frames"], base[game]["tracking"], com_r_pz(cfg, r_pz)
                )
            k = trocas_de_dono_por_duelo(passo1["control"], passo1["sequencias"])
            print("    R_pz {:4.2f} jogo {}: {} duelos | 2+ donos {} ({:.1%}) | "
                  "trocas {} ({:.2f} por duelo)".format(
                      r_pz, game, k["duelos"], k["duelos_2_mais_donos"],
                      k["frac_2_mais"], k["trocas"], k["trocas_por_duelo"]))
    print("")
    print("  (8) SENSIBILIDADE: POSICAO DO `goal_kick` NO PROBLEMA 3")
    print("  Os rotulos decodificados da Fig. S1 dao `K P C T Ci Ti G F?` no")
    print("  issue 3, logo o padrao e `depois_de_cto` (correcao de leitura de")
    print("  2026-11-02). As outras duas leituras ficam como sensibilidade; a")
    print("  prosa do S1, que omite o `G`, e a `nao`.")
    alternativas = [
        posicao for posicao in hierarquia.POSICOES_GOAL_KICK_NO_PROBLEMA_3
        if posicao != p["goal_kick_no_problema_3"]
    ]
    for posicao in alternativas:
        cfg_g = copy.deepcopy(cfg)
        cfg_g["bola_parada"]["goal_kick_no_problema_3"] = posicao
        det_g = detectar_jogos(base, cfg_g, jogos)
        mudou = deteccoes["type"].to_numpy() != det_g["type"].to_numpy()
        print("  -- {} ({} deteccoes mudam de tipo, de {} | por jogo {})".format(
            posicao, int(mudou.sum()), len(det_g),
            dict(deteccoes.loc[mudou, "game"].value_counts().sort_index())))
        # linha = tipo no padrao, coluna = tipo na alternativa
        print(pd.crosstab(deteccoes.loc[mudou, "type"].rename("type_padrao"),
                          det_g.loc[mudou, "type"].rename("type_alternativa")).to_string())
        print("     via: {} | soma {}".format(
            dict(det_g["via"].value_counts()), len(det_g)))
        _tabela_f1(eventos, det_g, cfg, [principal], ["frame"])
    print("=" * 78)

    destino = RAIZ_REPO / "outputs" / "deteccoes.csv" if gravar_em is None else gravar_em
    destino.parent.mkdir(parents=True, exist_ok=True)
    deteccoes.to_csv(destino, index=False)
    print("gravado: {} ({} linhas)".format(destino, len(deteccoes)))
    return deteccoes, resultado, confusao


def rotular_jogos(base: dict, deteccoes: pd.DataFrame, jogos) -> pd.DataFrame:
    """Tabela `src.events.passes.PASSES` dos jogos, concatenada.

    `deteccoes` sao as de bola parada de `detectar_jogos`, no mesmo `cfg`.
    """
    return pd.concat(
        [
            passes_mod.rotular(
                base[g]["perdas"], base[g]["ganhos"], base[g]["control"],
                base[g]["frames"], deteccoes[deteccoes["game"] == g],
            )
            for g in jogos
        ],
        ignore_index=True,
    )


def decompor_fn(eventos: pd.DataFrame, passes: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Cada `PASS` nao casado no criterio PRINCIPAL (ancora `frame`) em
    EXATAMENTE uma causa, nesta ordem (plano 05 §6, bloco 6):

      `a` nenhuma perda do jogador anotado a <= janela;
      `b` ha perda, mas todas foram suprimidas como bola parada;
      `c` ha perda nao suprimida, mas nenhuma e `completo`;
      `d` ha perda `completo`, e o casamento um-para-um a deu a outro `PASS`.

    Entrada: `eventos` (esquema `EVENTS`) e `passes` (esquema `PASSES`).
    Saida: DataFrame com `game`, `frame`, `player_id`, `causa` e `desfecho`
    (so na causa `c`: o da perda nao suprimida mais proxima no tempo, empate
    com a anterior -- regra de apresentacao, nao de deteccao; vazio nas
    demais).

    `d` e exata por maximalidade do casamento: uma perda `completo` livre na
    janela aumentaria o numero de pares. Isso e CONFERIDO aqui, nao assumido:
    estoura se alguma perda `completo` de um caso `d` nao estiver casada.
    """
    principal = cfg["avaliacao"]["criterio_principal"]
    eixos = cfg["avaliacao"]["criterios"][principal]
    janela = eixos["janela_s"]
    grupo = evaluate.grupo_por_tipo(cfg)["pass"]
    gab = eventos[eventos["type"] == "pass"].reset_index(drop=True)
    gab = gab.assign(grupo=grupo, t=gab["frame"] / cfg["tracking"]["fps"])
    det = passes_mod.para_casador(passes, so_completo=True).assign(grupo=grupo)
    i_gab, i_det = evaluate.casar(
        gab, det, janela, eixos["casa_tipo"], eixos["casa_jogador"]
    )

    sem_par = (
        gab.drop(index=i_gab)[["game", "frame", "t", "player_id"]]
        .reset_index(names="i_gab")
    )
    cand = sem_par.merge(
        passes[["game", "player_id", "frame", "t", "e_bola_parada", "desfecho"]]
        .rename(columns={"frame": "frame_p", "t": "t_p"}),
        on=["game", "player_id"],
    )
    cand["dt"] = (cand["t_p"] - cand["t"]).abs()
    cand = cand[cand["dt"] <= janela]       # mesma janela inclusiva do casador
    livre = cand[~cand["e_bola_parada"]]
    completo = livre[livre["desfecho"] == "completo"]
    i = sem_par["i_gab"]
    causa = np.select(
        [~i.isin(cand["i_gab"]), ~i.isin(livre["i_gab"]), ~i.isin(completo["i_gab"])],
        ["a", "b", "c"],
        default="d",
    )
    proxima = (
        livre.sort_values(["i_gab", "dt", "frame_p"], kind="stable")
        .drop_duplicates("i_gab")
        .set_index("i_gab")["desfecho"]
    )
    desfecho = np.where(causa == "c", i.map(proxima).fillna(""), "")

    casadas = det.iloc[i_det][["game", "player_id", "frame"]]
    de_d = completo[completo["i_gab"].isin(i[causa == "d"])]
    conferido = de_d.merge(
        casadas.rename(columns={"frame": "frame_p"}),
        on=["game", "player_id", "frame_p"], how="left", indicator=True,
    )
    if (conferido["_merge"] != "both").any():
        raise RuntimeError("decompor_fn: perda `completo` livre num caso (d); casamento nao maximo")

    return pd.DataFrame(
        {
            "game": sem_par["game"].to_numpy(),
            "frame": sem_par["frame"].to_numpy(),
            "player_id": sem_par["player_id"].to_numpy(),
            "causa": causa,
            "desfecho": desfecho,
        }
    )


def _tabela_passe(resultado: pd.DataFrame, cfg: dict, jogos) -> None:
    """P/R/F1 e contagem absoluta de `pass`, ancora `frame`, por criterio e por
    jogo, mais o agregado (`game = 0`, soma). So `frame`: para passe
    `anchor_shift = 0` e as duas ancoras coincidem (plano 05 §3.4; ha teste)."""
    print("    {:14s}{:>7s}{:>7s}{:>7s}{:>7s}{:>7s}{:>8s}{:>8s}{:>8s}".format(
        "criterio", "jogo", "n_gab", "n_det", "tp", "fp", "P", "R", "F1"))
    for criterio in cfg["avaliacao"]["criterios"]:
        for game in list(jogos) + [0]:
            linha = resultado[
                (resultado["criterio"] == criterio) & (resultado["ancora"] == "frame")
                & (resultado["game"] == game) & (resultado["type"] == "pass")
            ].iloc[0]
            print("    {:14s}{:>7s}{:7d}{:7d}{:7d}{:7d}".format(
                criterio, "TOTAL" if game == 0 else str(game), linha["n_gabarito"],
                linha["n_detectado"], linha["tp_diag"], linha["fp"])
                + "".join("{:8.3f}".format(linha[c]) for c in ("precisao", "revocacao", "f1")))


def _bloco_9(base: dict, deteccoes: pd.DataFrame, passes: pd.DataFrame,
             eventos: pd.DataFrame, cfg: dict, jogos) -> None:
    """Supressao alternativa "so se a perda for do executor detectado".

    Leitura implementada: a MESMA perda que o principal suprime (a primeira da
    corrida viva) so sai se o seu jogador for o executor da deteccao; senao ela
    volta a ser passe. `free_kick?` nao tem executor, logo nada suprime. E a
    alternativa descartada no plano 05 §3.1, pedida como sensibilidade na
    revisao de 2026-11-04. Nao altera `passes` (trabalha numa copia).
    """
    executor = np.full(len(passes), "", dtype=object)
    for game in jogos:
        sel = np.flatnonzero((passes["game"] == game).to_numpy())
        det_g = deteccoes[deteccoes["game"] == game].reset_index(drop=True)
        origem = passes_mod.suprimir(passes.iloc[sel], det_g, base[game]["frames"])
        executor[sel[origem >= 0]] = det_g["player_id"].to_numpy()[origem[origem >= 0]]
    alt = passes.assign(
        e_bola_parada=passes["e_bola_parada"] & (passes["player_id"].to_numpy() == executor))
    gab_sec = evaluate.gabarito_secundario(eventos, cfg)
    principal = cfg["avaliacao"]["criterio_principal"]
    print("")
    print("  (9) EXPLORATÓRIO — decidido depois de ver o resultado; o principal não muda")
    print("  supressao so se a perda de reinicio for do EXECUTOR detectado")
    print("    passes: {} (principal: {})".format(
        len(passes_mod.para_casador(alt)), len(passes_mod.para_casador(passes))))
    print("    {:11s}{:9s}{:>7s}{:>7s}{:>7s}{:>7s}{:>8s}{:>8s}{:>8s}".format(
        "gabarito", "criterio", "jogo", "n_gab", "n_det", "tp", "P", "R", "F1"))
    for rotulo, gab, det in (
        ("principal", eventos, passes_mod.para_casador(alt, so_completo=True)),
        ("secundario", gab_sec, passes_mod.para_casador(alt)),
    ):
        res, _ = evaluate.avaliar(gab, det, cfg)
        for game in list(jogos) + [0]:
            linha = res[(res["criterio"] == principal) & (res["ancora"] == "frame")
                        & (res["game"] == game) & (res["type"] == "pass")].iloc[0]
            print("    {:11s}{:9s}{:>7s}{:7d}{:7d}{:7d}".format(
                rotulo, principal, "TOTAL" if game == 0 else str(game),
                linha["n_gabarito"], linha["n_detectado"], linha["tp_diag"])
                + "".join("{:8.3f}".format(linha[c]) for c in ("precisao", "revocacao", "f1")))


def rodar_passes(cfg: dict, mapeamento: dict, jogos, gravar_em=None, exploratorio=True):
    """Rotula as perdas como passes e imprime os 8 blocos do plano 05 §6, mais o
    bloco 9 exploratorio se `exploratorio` (ele so imprime; nao altera nada).

    Saida: (passes, resultado_principal, resultado_secundario).
    """
    base = _carregar_base(cfg, mapeamento, jogos)
    eventos = pd.concat([base[g]["eventos"] for g in jogos], ignore_index=True)
    deteccoes = detectar_jogos(base, cfg, jogos)
    passes = rotular_jogos(base, deteccoes, jogos)
    janela = cfg["avaliacao"]["criterios"][cfg["avaliacao"]["criterio_principal"]]["janela_s"]
    gab_passe = eventos[eventos["type"] == "pass"]
    nao_supr = passes[~passes["e_bola_parada"]]

    # Diagnostico da supressao: quem e o executor da bola parada de cada perda
    # suprimida, e se o intervalo morto e espurio.
    espuria_det = ~deteccoes_na_ancora(deteccoes, eventos, cfg)
    supr = []
    for game in jogos:
        det_g = deteccoes[deteccoes["game"] == game].reset_index(drop=True)
        perdas = base[game]["perdas"]
        origem = passes_mod.suprimir(perdas, det_g, base[game]["frames"])
        s = origem >= 0
        supr.append(pd.DataFrame({
            "game": game,
            "t": perdas["t"].to_numpy()[s],
            "player_id": perdas["player_id"].to_numpy()[s],
            "executor": det_g["player_id"].to_numpy()[origem[s]],
            "frame_bp": det_g["frame"].to_numpy()[origem[s]],
            "espuria": espuria_det[(deteccoes["game"] == game).to_numpy()][origem[s]],
        }))
    supr = pd.concat(supr, ignore_index=True)
    # Intervalo morto ESPURIO = deteccao de bola parada cujo quadro nao e a
    # ancora (`frame`) de nenhum reinicio do gabarito no mesmo jogo: 198 =
    # 481 - 283, isto e os 185 de `481 - 296` mais os 13 `no_dead_ball_before`
    # (revisao da Fatia 5, 2026-11-04).
    perto = supr.reset_index(names="i").merge(
        gab_passe[["game", "player_id", "t"]].rename(columns={"t": "t_g"}),
        on=["game", "player_id"])
    supr["perto_de_pass"] = supr.index.isin(
        perto.loc[(perto["t_g"] - perto["t"]).abs() <= janela, "i"])

    print("=" * 78)
    print("PASSES DE JOGO CORRIDO (R_pz = {:g} m)".format(cfg["posse"]["r_pz_m"]))
    print("")
    print("  (1) CONTAGENS. Passe = perda de posse que nao e a perda de reinicio")
    print("  de uma bola parada (plano 05 sec. 3.1, independe do jogador).")
    print("  {:>6s}{:>9s}{:>11s}{:>12s}{:>14s}{:>9s}{:>10s}".format(
        "jogo", "perdas", "suprimidas", "!= executor", "(free_kick?)", "passes",
        "identid."))
    for game in list(jogos) + [0]:
        p = passes if game == 0 else passes[passes["game"] == game]
        s = supr if game == 0 else supr[supr["game"] == game]
        n_passes = int((~p["e_bola_parada"]).sum())
        print("  {:>6s}{:9d}{:11d}{:12d}{:14d}{:9d}{:>10s}".format(
            "TOTAL" if game == 0 else str(game), len(p), len(s),
            int((s["player_id"] != s["executor"]).sum()), int((s["executor"] == "").sum()),
            n_passes, "ok" if n_passes == len(p) - len(s) else "FALHOU"))
    print("  deteccoes de bola parada: {} | suprimidas <= deteccoes: {}".format(
        len(deteccoes), len(supr) <= len(deteccoes)))
    print("  `!= executor` inclui os `free_kick?`, que nao tem executor (coluna")
    print("  seguinte). Diagnostico, nao decisao (plano 05 sec. 3.1).")

    print("")
    print("  (2) DESFECHO dos passes (nao suprimidos), por jogo")
    # Categoria explicita: desfecho com contagem zero aparece como 0, nao some.
    desfecho = pd.Categorical(nao_supr["desfecho"], categories=passes_mod.DESFECHOS)
    print(pd.crosstab(nao_supr["game"], desfecho, margins=True, dropna=False,
                      colnames=["desfecho"]).to_string())
    print("  recepcao em quadro de duelo, por desfecho:")
    print(pd.crosstab(desfecho, nao_supr["recepcao_em_duelo"].to_numpy(), margins=True,
                      dropna=False, rownames=["desfecho"],
                      colnames=["recepcao_em_duelo"]).to_string())

    print("")
    print("  (3) PRINCIPAL: passes `completo` x `PASS`. `estrito` e NOSSO (D8).")
    res_principal, _ = evaluate.avaliar(
        eventos, passes_mod.para_casador(passes, so_completo=True), cfg)
    _tabela_passe(res_principal, cfg, jogos)

    print("")
    print("  (4) SECUNDARIO: todos os passes x uniao sem tiro de meta (D10).")
    gab_sec = evaluate.gabarito_secundario(eventos, cfg)
    res_secundario, _ = evaluate.avaliar(gab_sec, passes_mod.para_casador(passes), cfg)
    _tabela_passe(res_secundario, cfg, jogos)

    print("")
    print("  (5) DIAGNOSTICO: todos os passes x `PASS` (sem o filtro de desfecho).")
    res_diag, _ = evaluate.avaliar(eventos, passes_mod.para_casador(passes), cfg)
    _tabela_passe(res_diag, cfg, jogos)

    print("")
    print("  (6) DECOMPOSICAO DOS FN DO PRINCIPAL, criterio {}, ancora `frame`".format(
        cfg["avaliacao"]["criterio_principal"]))
    print("  a = sem perda do jogador a <= {:g} s | b = perda suprimida como bola".format(janela))
    print("  parada | c = perda com desfecho != completo | d = perda `completo`")
    print("  consumida por outro PASS no casamento um-para-um")
    dec = decompor_fn(eventos, passes, cfg)
    fn = res_principal[
        (res_principal["criterio"] == cfg["avaliacao"]["criterio_principal"])
        & (res_principal["ancora"] == "frame") & (res_principal["type"] == "pass")
    ].set_index("game")["fn"]
    tabela = pd.crosstab(dec["game"], pd.Categorical(dec["causa"], categories=list("abcd")),
                         margins=True, margins_name="TOTAL", dropna=False, colnames=["causa"])
    tabela["fn_avaliar"] = [int(fn.loc[g]) for g in list(jogos) + [0]]
    print(tabela.to_string())
    print("  causa c por desfecho da perda mais proxima:")
    c = dec[dec["causa"] == "c"]
    print(pd.crosstab(c["game"], pd.Categorical(c["desfecho"], categories=[
        d for d in passes_mod.DESFECHOS if d != "completo"]), margins=True, dropna=False,
        colnames=["desfecho"]).to_string())

    print("")
    print("  (7) TABELAS 3 E 4 SEM AS PERDAS `de_lacuna_5` (requisito das Fatias 3-4)")
    sem = passes[~passes["de_lacuna_5"]]
    print("    passes sem lacuna 5: {} (com: {}; perdas de lacuna 5 nao suprimidas: {})".format(
        int((~sem["e_bola_parada"]).sum()), len(nao_supr), int(nao_supr["de_lacuna_5"].sum())))
    print("  -- principal")
    _tabela_passe(evaluate.avaliar(
        eventos, passes_mod.para_casador(sem, so_completo=True), cfg)[0], cfg, jogos)
    print("  -- secundario")
    _tabela_passe(evaluate.avaliar(
        gab_sec, passes_mod.para_casador(sem), cfg)[0], cfg, jogos)

    print("")
    print("  (8) CUSTO DOS INTERVALOS MORTOS ESPURIOS (D1 sem duracao minima)")
    print("  espurio = deteccao cujo quadro nao e ancora de reinicio do gabarito")
    print("  `perto de PASS` = a perda suprimida esta a <= {:g} s de um `PASS`".format(janela))
    print("  anotado do MESMO jogador: e o passe verdadeiro que a supressao custou.")
    print("    deteccoes espurias: {} de {}".format(int(espuria_det.sum()), len(deteccoes)))
    print(pd.crosstab(supr["espuria"].rename("espuria"),
                      supr["perto_de_pass"].rename("perto_de_PASS"), margins=True).to_string())
    if exploratorio:
        _bloco_9(base, deteccoes, passes, eventos, cfg, jogos)
    print("=" * 78)

    destino = RAIZ_REPO / "outputs" / "passes.csv" if gravar_em is None else gravar_em
    destino.parent.mkdir(parents=True, exist_ok=True)
    passes.to_csv(destino, index=False)
    print("gravado: {} ({} linhas)".format(destino, len(passes)))
    return passes, res_principal, res_secundario


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.run", description=__doc__)
    parser.add_argument("--inspect", action="store_true", help="imprime o resumo dos jogos")
    parser.add_argument("--tau", action="store_true", help="mede a defasagem da anotacao")
    parser.add_argument("--posse", action="store_true", help="roda o Passo 1 (posse)")
    parser.add_argument("--tau-posse", action="store_true",
                        help="mede tau_posse e aplica a escada pre-registrada")
    parser.add_argument("--bola-parada", action="store_true",
                        help="roda o Passo 2 (bolas paradas) e o relatorio do plano 04")
    parser.add_argument("--passes", action="store_true",
                        help="rotula e avalia os passes (relatorio do plano 05)")
    parser.add_argument("--config", default=None, help="caminho alternativo do config.yaml")
    args = parser.parse_args(argv)

    cfg = carregar_config(args.config)
    if not (args.inspect or args.tau or args.posse or args.tau_posse
            or args.bola_parada or args.passes):
        parser.error("escolha --inspect, --tau, --posse, --tau-posse, --bola-parada ou --passes")
    mapeamento = carregar_mapeamento(cfg)
    if args.inspect:
        inspecionar(cfg, mapeamento, cfg["dados"]["jogos"])
    if args.tau:
        medir_tau(cfg, mapeamento, cfg["dados"]["jogos"])
    if args.posse:
        rodar_posse(cfg, mapeamento, cfg["dados"]["jogos"])
    if args.tau_posse:
        medir_tau_posse(cfg, mapeamento, cfg["dados"]["jogos"])
    if args.bola_parada:
        rodar_bola_parada(cfg, mapeamento, cfg["dados"]["jogos"])
    if args.passes:
        rodar_passes(cfg, mapeamento, cfg["dados"]["jogos"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
