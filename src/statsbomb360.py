"""Fatia 12: visibilidade real (StatsBomb 360, Copa 2022) contra o simulador,
no instante dos eventos. DESCRITIVO: sem F1, sem parametro livre, o detector
nao roda. Plano normativo: `docs/fatias/12-plano.md` (§5 prevalece).

- `rodar_copa` (`--statsbomb360`): medidas do §2.1 por tipo nos 64 jogos.
- `rodar_simulador` (`--visibilidade-eventos`): o §2.2 sobre os eventos da
  Metrica, com `broadcast.degradar` e `reconstruct` como estao, condicao
  `reconstruido`, sementes `[simulador.semente_base, jogo, rep]`.
- `comparar`: `comparacao.csv`, as duas tabelas lado a lado por tipo (§2.3),
  so numeros.

Saidas em `statsbomb360.saida`: `copa2022_por_tipo.csv`, `copa2022_por_jogo.csv`,
`simulador_por_tipo.csv`, `comparacao.csv` e `manifesto.json` (uma secao por
modo: `copa2022` e `simulador`).
"""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src import broadcast, experiment, run
from src.config import RAIZ_REPO
from src.io import statsbomb


def tipos(cfg: dict) -> list:
    """Os 6 tipos do plano 12 §5: o passe em jogo corrido e as 5 bolas paradas."""
    sb = cfg["statsbomb360"]
    return [sb["tipo_corrido"]] + list(sb["pass_type_bola_parada"].values())


def _percentis(v: np.ndarray, percentis, prefixo: str, sufixo: str = "") -> dict:
    v = v[np.isfinite(v)]
    return {f"{prefixo}_p{p:02d}{sufixo}": (float(np.percentile(v, p)) if v.size else np.nan) for p in percentis}


def _frac(n: int, d: int) -> float:
    return n / d if d else np.nan


# --- Copa 2022 (§2.1) ----------------------------------------------------------

def resumo_copa(tab: pd.DataFrame, por: list, cfg: dict) -> pd.DataFrame:
    """Uma linha por grupo de `por` (sempre com `tipo`; os 6 tipos aparecem
    mesmo sem evento). Entrada: linhas de `statsbomb.COLUNAS`. Colunas:
    `n_eventos`, `n_sem_360`, `frac_sem_360` (denominador: todos os eventos);
    e, so entre os com 360: `n_com_360`, `visiveis_pNN`, `n_0_visiveis`,
    `frac_0_visiveis`, `n_actor_visivel`, `frac_actor_visivel`, `area_media`,
    `area_pNN` (fracao do campo)."""
    pcs = cfg["statsbomb360"]["percentis"]
    outros = [c for c in por if c != "tipo"]
    grupos = tab[outros].drop_duplicates().sort_values(outros).to_dict("records") if outros else [{}]
    linhas = []
    for g in grupos:
        sub_g = tab
        for c, v in g.items():
            sub_g = sub_g[sub_g[c] == v]
        for t in tipos(cfg):
            s = sub_g[sub_g["tipo"] == t]
            c360 = s[s["tem_360"]]
            nv = c360["n_visiveis"].to_numpy()
            linhas.append({**g, "tipo": t, "n_eventos": len(s), "n_sem_360": int((~s["tem_360"]).sum()),
                           "frac_sem_360": _frac(int((~s["tem_360"]).sum()), len(s)),
                           "n_com_360": len(c360), **_percentis(nv, pcs, "visiveis"),
                           "n_0_visiveis": int((nv == 0).sum()), "frac_0_visiveis": _frac(int((nv == 0).sum()), len(c360)),
                           "n_actor_visivel": int(c360["actor_visivel"].sum()),
                           "frac_actor_visivel": _frac(int(c360["actor_visivel"].sum()), len(c360)),
                           "area_media": float(c360["frac_area"].mean()) if len(c360) else np.nan,
                           **_percentis(c360["frac_area"].to_numpy(), pcs, "area")})
    return pd.DataFrame(linhas)[por + [c for c in linhas[0] if c not in por]]


# --- simulador (§2.2) ----------------------------------------------------------

def visibilidade_eventos(eventos: pd.DataFrame, tracking: pd.DataFrame, frames: pd.DataFrame,
                         cfg: dict) -> pd.DataFrame:
    """Por evento dos 6 tipos (gabarito da Metrica de UM jogo): `tipo`,
    `quadro` (`annotated_frame` no passe, `frame` = primeiro quadro vivo na
    bola parada; plano 12 §5), `n_visiveis` (jogadores com `visible` = True no
    quadro, goleiros incluidos), `executor_visivel` (o `player_id` anotado tem
    `visible` = True no quadro; sem `player_id`, False) e `executor_anotado`.
    `tracking` com a grade 1..N contigua de `frames` (como
    `experiment.apagao_total`). Apagao total = `n_visiveis` == 0."""
    corrido = cfg["statsbomb360"]["tipo_corrido"]
    ev = eventos[eventos["type"].isin(tipos(cfg))]
    quadro = np.where(ev["type"] == corrido, ev["annotated_frame"], ev["frame"]).astype("int64")
    vis = tracking[tracking["visible"].to_numpy()]
    n = np.bincount(vis["frame"].to_numpy() - 1, minlength=len(frames))[:len(frames)]
    chave = pd.MultiIndex.from_arrays([vis["frame"].to_numpy(), vis["player_id"].to_numpy()])
    exec_vis = pd.MultiIndex.from_arrays([quadro, ev["player_id"].to_numpy()]).isin(chave)
    return pd.DataFrame({"tipo": ev["type"].to_numpy(), "quadro": quadro, "n_visiveis": n[quadro - 1],
                         "executor_visivel": exec_vis, "executor_anotado": ev["player_id"].notna().to_numpy()})


def unidades(cfg: dict) -> list:
    """`(variante, nivel, rep, jogo)`: os niveis de `statsbomb360.niveis`; rep
    0..`simulador.n_sementes`-1, ou so 0 nas `experimento.variantes_sem_semente`."""
    n = int(cfg["simulador"]["n_sementes"])
    return [(v, int(k), rep, g) for v, ks in cfg["statsbomb360"]["niveis"].items() for k in ks
            for rep in range(experiment._n_reps(cfg, v, n)) for g in cfg["dados"]["jogos"]]


def rodar_unidade(variante: str, nivel: int, rep: int, jogo: int, cfg: dict, base: dict) -> tuple:
    """Uma unidade: degrada o teto, reconstroi e mede os eventos. `cfg` ja de
    `cfg` com `simulador.semente_base`; `base` de `run._base_leve`. Saida: (tabela de
    `visibilidade_eventos` com `variante`, `nivel`, `rep`, `jogo`;
    linhas visiveis sem GK; linhas do teto sem GK)."""
    d = base[jogo]
    teto, fr = d["tracking"], d["frames"]
    deg = broadcast.degradar(teto, fr, cfg, variante, nivel, rep)
    trk = experiment.tracking_da_condicao(teto, deg, "reconstruido")
    ev = visibilidade_eventos(d["eventos"], trk, fr, cfg)
    ev.insert(0, "jogo", jogo)
    ev.insert(0, "rep", rep)
    ev.insert(0, "nivel", nivel)
    ev.insert(0, "variante", variante)
    return ev, int((~deg["is_gk"]).sum()), int((~teto["is_gk"]).sum())


def resumo_simulador(ev: pd.DataFrame, taxas: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Nivel x tipo, somado nos jogos e nas sementes. `taxas`: uma linha por
    unidade com `variante`, `nivel`, `vis_sem_gk`, `teto_sem_gk`. Colunas:
    `n_unidades`, `taxa_sem_gk` (soma / soma), `n_eventos`, `n_apagao`,
    `frac_apagao`, `visiveis_pNN`, `visiveis_pNN_cond` (so eventos com >= 1
    visivel, fora do apagao total: o analogo do 360, condicionado a existir
    entrada), `n_executor_visivel`, `frac_executor_visivel`,
    `n_sem_executor_anotado`."""
    pcs = cfg["statsbomb360"]["percentis"]
    linhas = []
    for (v, k), t_vk in taxas.groupby(["variante", "nivel"], sort=False):
        e_vk = ev[(ev["variante"] == v) & (ev["nivel"] == k)]
        for t in tipos(cfg):
            s = e_vk[e_vk["tipo"] == t]
            nv = s["n_visiveis"].to_numpy(dtype="float64")
            linhas.append({"variante": v, "nivel": k, "tipo": t, "n_unidades": len(t_vk),
                           "taxa_sem_gk": t_vk["vis_sem_gk"].sum() / t_vk["teto_sem_gk"].sum(),
                           "n_eventos": len(s), "n_apagao": int((nv == 0).sum()),
                           "frac_apagao": _frac(int((nv == 0).sum()), len(s)), **_percentis(nv, pcs, "visiveis"),
                           **_percentis(nv[nv > 0], pcs, "visiveis", "_cond"),
                           "n_executor_visivel": int(s["executor_visivel"].sum()),
                           "frac_executor_visivel": _frac(int(s["executor_visivel"].sum()), len(s)),
                           "n_sem_executor_anotado": int((~s["executor_anotado"]).sum())})
    return pd.DataFrame(linhas)


# --- comparacao (§2.3) ----------------------------------------------------------

def comparar(copa: pd.DataFrame, sim: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por tipo: `copa2022_n_eventos`, `copa2022_frac_sem_360`,
    `copa2022_visiveis_p50` (com 360) e, por nivel `<V><k>_*`, `n_eventos`,
    `frac_apagao`, `visiveis_p50`, `visiveis_p50_cond`, `frac_executor_visivel`.
    So numeros. `frac_actor_visivel` e `frac_0_visiveis` do 360 ficam so em
    `copa2022_por_tipo.csv`: saem fixos em 1 e 0 pelo formato do dado (o
    `actor` sempre vem no `freeze_frame`), logo nao se comparam ao simulador."""
    out = copa[["tipo", "n_eventos", "frac_sem_360", "visiveis_p50"]].set_index("tipo").add_prefix("copa2022_")
    for (v, k), s in sim.groupby(["variante", "nivel"], sort=False):
        out = out.join(s.set_index("tipo")[["n_eventos", "frac_apagao", "visiveis_p50", "visiveis_p50_cond",
                                            "frac_executor_visivel"]]
                       .add_prefix(f"{v}{k}_"))
    return out.reset_index()


# --- modos ----------------------------------------------------------------------

def _saida(cfg: dict) -> Path:
    return RAIZ_REPO / cfg["statsbomb360"]["saida"]


def _gravar_secao(cfg: dict, caminho_config: Path, secao: str, extra: dict, unidades_info: list) -> None:
    """Atualiza a `secao` de `manifesto.json` (a outra secao fica como esta).
    `extra` sobrescreve chaves do `experiment.manifesto` (na Copa, `dados`);
    `unidades_info` None tira a chave `unidades`."""
    m = experiment.manifesto(cfg, caminho_config, unidades_info)
    m.update(extra)
    if unidades_info is None:
        m.pop("unidades")
    destino = _saida(cfg) / "manifesto.json"
    tudo = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {}
    tudo[secao] = m
    destino.write_text(json.dumps(tudo, indent=1, default=str), encoding="utf-8")
    print("gravado: {} (secao {})".format(destino, secao))


def _comparacao_se_puder(cfg: dict) -> None:
    pasta = _saida(cfg)
    a, b = pasta / "copa2022_por_tipo.csv", pasta / "simulador_por_tipo.csv"
    if a.exists() and b.exists():
        experiment._gravar(comparar(pd.read_csv(a), pd.read_csv(b)), pasta / "comparacao.csv")


def rodar_copa(cfg: dict, caminho_config: Path) -> pd.DataFrame:
    """`--statsbomb360`: os 64 jogos, sha256 conferido, as duas tabelas da Copa."""
    ids = statsbomb.partidas(cfg)
    conferencia = statsbomb.conferir_sha(cfg, ids)
    tab = pd.concat([statsbomb.ler_jogo(m, cfg) for m in ids], ignore_index=True)
    por_tipo = resumo_copa(tab, ["tipo"], cfg)
    pasta = _saida(cfg)
    experiment._gravar(por_tipo, pasta / "copa2022_por_tipo.csv")
    experiment._gravar(resumo_copa(tab, ["match_id", "tipo"], cfg), pasta / "copa2022_por_jogo.csv")
    _gravar_secao(cfg, caminho_config, "copa2022",
                  {"conjunto": cfg["statsbomb360"]["conjunto"],
                   "dados": {"raiz": cfg["statsbomb360"]["raiz"], "n_jogos": len(ids), **conferencia},
                   "n_eventos": len(tab)}, None)
    _comparacao_se_puder(cfg)
    return por_tipo


def rodar_simulador(cfg: dict, mapeamento: dict, caminho_config: Path, so=None) -> pd.DataFrame:
    """`--visibilidade-eventos`: todas as `unidades` (ou so as de `so`), em
    sequencia; grava `simulador_por_tipo.csv` e a secao `simulador` do
    manifesto, com semente e tempo por unidade. O detector nao roda."""
    lista = unidades(cfg) if so is None else so
    base = run._base_leve(cfg, mapeamento, sorted({u[3] for u in lista}))
    blocos, taxas, info = [], [], []
    for v, k, rep, g in lista:
        t0 = time.perf_counter()
        ev, n_vis, n_teto = rodar_unidade(v, k, rep, g, cfg, base)
        dt = time.perf_counter() - t0
        blocos.append(ev)
        taxas.append({"variante": v, "nivel": k, "vis_sem_gk": n_vis, "teto_sem_gk": n_teto})
        info.append({"variante": v, "nivel": k, "rep": rep, "jogo": g,
                     "semente_efetiva": ";".join(str(s) for s in broadcast.semente_efetiva(cfg, g, rep)),
                     "tempo_s": dt})
        print("unidade {}{} rep {} jogo {}: {:.1f} s".format(v, k, rep, g, dt))
    sim = resumo_simulador(pd.concat(blocos, ignore_index=True), pd.DataFrame(taxas), cfg)
    if so is None:
        experiment._gravar(sim, _saida(cfg) / "simulador_por_tipo.csv")
        _gravar_secao(cfg, caminho_config, "simulador",
                      {"semente_base": cfg["simulador"]["semente_base"], "condicao": "reconstruido"}, info)
        _comparacao_se_puder(cfg)
    return sim
