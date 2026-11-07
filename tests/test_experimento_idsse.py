"""Fatia 11c: a maquina da Fatia 8 parametrizada por conjunto de dados
(docs/fatias/11-plano.md §4b e §7). A Metrica (padrao) fica bit a bit igual; o
IDSSE muda so por `experiment.cfg_idsse`."""

import copy
import json

import numpy as np
import pandas as pd
import pytest

from src import broadcast, experiment as ex
from src.config import RAIZ_REPO
from src.io import idsse, schema

PONTOS_EXP = RAIZ_REPO / "outputs" / "experimento" / "pontos.csv"
JOGOS_I = tuple(range(1, 8))


# --- a Metrica bit a bit, pelo caminho da maquina (rodar_unidades) ---------------------

@pytest.mark.parametrize("u", [("reconstruido", 1, "AB", 1, 0), ("reconstruido", 1, "B", 8, 0)])
def test_metrica_padrao_pela_maquina_reproduz_a_rodada_final(cfg, mapeamento, u):
    """`rodar_unidades` com o config padrao (n_workers 1, sem cache) reproduz
    `outputs/experimento/pontos.csv` em R0, linha a linha (texto CSV)."""
    if not PONTOS_EXP.exists():
        pytest.skip("outputs/experimento/pontos.csv ausente")
    assert cfg["dados"]["conjunto"] == "metrica"
    c = ex._trocar(cfg, posse__grade_r_pz_m=[cfg["experimento"]["r0_m"]])
    pontos, lista = ex.rodar_unidades([u], c, mapeamento, 1, None)
    assert ex.conferir_linha_base(pontos, PONTOS_EXP, cfg) == len(pontos) > 0
    assert lista[0]["semente_efetiva"] == ("nenhuma" if u[3] == 1 else "20261104;1;0")


# --- cfg_idsse: o perfil B, as sementes, as trocas ------------------------------------

def test_cfg_idsse_a_e_b(cfg):
    a, b = ex.cfg_idsse(cfg), ex.cfg_idsse(cfg, "provedor_b")
    for c in (a, b):
        assert c["dados"]["conjunto"] == "idsse" and c["dados"]["jogos"] == list(JOGOS_I)
        assert c["simulador"]["semente_base"] == 20261107
        assert c["simulador"]["calibrado"] == cfg["simulador"]["calibrado"]       # congelado
        assert c["avaliacao"]["criterio_principal"] == "vidal_codina" == cfg["idsse"]["criterio_principal"]
        assert c["experimento"]["condicoes"] == ["reconstruido"] and not c["experimento"]["curva_eps_c"]
        assert (c["experimento"]["min_jogos_candidato"], c["experimento"]["min_jogos_compensa"]) == (4, 5)
        assert c["posse"]["grade_r_pz_m"] == cfg["posse"]["grade_r_pz_m"]        # a grade da Fatia 8
        assert broadcast.semente_efetiva(c, 3, 4) == [20261107, 3, 4]
    assert (a["experimento"]["r0_m"], a["posse"]["eps_s_m"], a["posse"]["eps_v_ms"]) == (0.5, 0.05, 1.0)
    assert (b["experimento"]["r0_m"], b["posse"]["eps_s_m"], b["posse"]["eps_v_ms"]) == (1.0, 0.10, 5.0)
    assert 1.0 in b["posse"]["grade_r_pz_m"]
    assert (a["dados"]["rotulo"], b["dados"]["rotulo"]) == ("LIMPO", "EXPLORATORIO")
    assert (a["dados"]["perfil"], b["dados"]["perfil"]) == (None, "provedor_b")
    assert ex.saida_idsse(cfg).name == "experimento_A" and ex.saida_idsse(cfg, "provedor_b").name == "experimento_B"
    # o cfg da Metrica nao muda
    assert cfg["dados"]["conjunto"] == "metrica" and cfg["simulador"]["semente_base"] == 20261104
    assert cfg["avaliacao"]["criterio_principal"] == "estrito" and cfg["experimento"]["r0_m"] == 0.5
    assert cfg["experimento"]["condicoes"] == ["reconstruido", "bruto"] and cfg["experimento"]["curva_eps_c"]
    # troca com chave fora de `experimento` estoura (erro de digitacao no config)
    c = copy.deepcopy(cfg)
    c["idsse_experimento"]["trocas"]["min_jogos_candidatos"] = 4
    with pytest.raises(ValueError, match="fora de"):
        ex.cfg_idsse(c)


def test_grade_idsse(cfg):
    g = ex.grade(ex.cfg_idsse(cfg))
    n = cfg["simulador"]["n_sementes"]
    assert len(g) == 7 + 7 * n * 7 + 7 * 1 * 7 == 301
    assert {u[0] for u in g} == {"reconstruido"} and {u[1] for u in g} == set(JOGOS_I)
    assert {u[4] for u in g if u[2] == "B"} == set(range(5)) and {u[4] for u in g if u[2] == "A"} == {0}
    assert {u[3] for u in g if u[2] in "AB" and u[2] != "AB"} == set(range(2, 9))


# --- LOGO: k de n do config -------------------------------------------------------------

def _pontos(tabela, criterio, nivel=8, alvo=ex.ALVO_PASSE):
    """`tabela`: {jogo: {r_pz: (tp, n_det, n_gab)}} -> pontos do principal."""
    linhas = [dict(condicao="reconstruido", jogo=j, variante="AB" if nivel == 1 else "B", nivel=nivel, rep=0,
                   r_pz=r, politica="acompanha_r_pz", lacuna5="com", criterio=criterio, ancora="frame",
                   alvo=alvo, taxa_todos=0.5, taxa_sem_gk=0.5, tp_diag=tp, tp=tp, n_detectado=nd, n_gabarito=ng)
              for j, por_r in tabela.items() for r, (tp, nd, ng) in por_r.items()]
    return pd.DataFrame(linhas)


GANHA = {0.5: (500, 1000, 1000), 1.0: (600, 1000, 1000)}
PERDE = {0.5: (500, 1000, 1000), 1.0: (499, 1000, 1000)}


def test_logo_candidato_k_de_n_do_config(cfg):
    """IDSSE (k = 4): 1,0 m ganha nos jogos 1-4 e perde de leve nos 5-7. Com o
    jogo de teste em 5, 6 ou 7, o treino tem 4 ganhos em 6 -> candidato; com o
    teste em 1-4, so 3 em 6 -> R0. Mutantes que morrem: "2 de 2 fixo" (`.all`,
    tudo R0) e k fixo em 2 (3 de 6 passaria)."""
    ci = ex.cfg_idsse(cfg)
    s = ex.selecionar_logo(_pontos({j: GANHA if j <= 4 else PERDE for j in JOGOS_I}, "vidal_codina"), ci)
    r = s.set_index("jogo_teste")["r_estrela"]
    assert r.to_dict() == {1: 0.5, 2: 0.5, 3: 0.5, 4: 0.5, 5: 1.0, 6: 1.0, 7: 1.0}
    # F1 NaN no treino nunca conta como ganho: o jogo 4 em 1,0 m sem contagem
    tab = {j: GANHA if j <= 4 else PERDE for j in JOGOS_I}
    tab[4] = {0.5: (500, 1000, 1000), 1.0: (0, 0, 0)}
    s = ex.selecionar_logo(_pontos(tab, "vidal_codina"), ci)
    assert (s["r_estrela"] == 0.5).all()


def test_logo_k_n_da_metrica_e_do_idsse(cfg):
    """Metrica: 2 de 2 (candidato) e 2 de 3 (ajuda); IDSSE: 4 de 6 e 5 de 7.
    k > numero de jogos de treino estoura (nunca vira 'sem candidato' calado)."""
    assert (cfg["experimento"]["min_jogos_candidato"], cfg["experimento"]["min_jogos_compensa"]) == (2, 2)
    ci = ex.cfg_idsse(cfg)
    assert ex.conclusoes(2, 0.05, 0.0, cfg) == ("sim", "sim")
    assert ex.conclusoes(4, 0.05, 0.0, ci) == ("nao", "nao")
    assert ex.conclusoes(5, 0.05, 0.0, ci) == ("sim", "sim")
    tres = _pontos({j: GANHA for j in (1, 2, 3)}, "vidal_codina")
    with pytest.raises(ValueError, match="min_jogos_candidato"):
        ex.selecionar_logo(tres, ci)
    # na Metrica, ganho num so jogo de treino continua excluido (2 de 2)
    s = ex.selecionar_logo(_pontos({1: GANHA, 2: PERDE, 3: GANHA}, "estrito"), cfg).set_index("jogo_teste")
    assert s["r_estrela"].to_dict() == {1: 0.5, 2: 1.0, 3: 0.5}


# --- maquina no IDSSE: sementes no manifesto, carga sob demanda, cache ------------------

@pytest.fixture
def xml_falso(tmp_path, monkeypatch):
    """`idsse.caminhos` -> 3 arquivos pequenos por jogo (so para o sha256)."""
    def caminhos(c, g):
        d = tmp_path / f"j{g}"
        d.mkdir(exist_ok=True)
        out = {}
        for nome in ("ficha", "eventos", "posicoes"):
            p = d / f"{nome}_{g}.xml"
            if not p.exists():
                p.write_text(f"<{nome} jogo='{g}'/>", encoding="utf-8")
            out[nome] = p
        return out
    monkeypatch.setattr(idsse, "caminhos", caminhos)
    return tmp_path


def test_sementes_do_idsse_no_manifesto_e_um_jogo_por_vez(cfg, xml_falso, monkeypatch):
    cargas, vistos = [], []

    def carregar(jogo, c, pasta_cache=None):
        cargas.append(jogo)
        vazio = pd.DataFrame({k: pd.Series(dtype=t) for k, t in schema.EVENTS.items()})
        return {"frames": f"frames{jogo}", "tracking": None, "periods": None, "eventos": vazio}

    def unidade(jogo, variante, nivel, rep, condicao, c, base):
        vistos.append((jogo, sorted(base), c["simulador"]["semente_base"], c["experimento"]["r0_m"]))
        return pd.DataFrame({"jogo": [jogo], "rep": [rep]})

    monkeypatch.setattr(idsse, "carregar_jogo", carregar)
    monkeypatch.setattr(ex, "rodar_unidade", unidade)
    for perfil, rotulo, r0 in ((None, "LIMPO", 0.5), ("provedor_b", "EXPLORATORIO", 1.0)):
        cargas.clear()
        vistos.clear()
        ci = ex.cfg_idsse(cfg, perfil)
        unid = [("reconstruido", 2, "B", 8, 4), ("reconstruido", 1, "B", 8, 0), ("reconstruido", 1, "A", 5, 0),
                ("reconstruido", 1, "AB", 1, 0)]
        pontos, lista = ex.rodar_unidades(unid, ci, None, 1, None)
        assert cargas == [1, 2]                                  # cada jogo uma vez, um por vez
        assert [v[1] for v in vistos] == [[1], [1], [1], [2]]
        assert {(v[2], v[3]) for v in vistos} == {(20261107, r0)}
        m = json.loads(json.dumps(ex.manifesto(ci, RAIZ_REPO / "config.yaml", lista), default=str))
        assert (m["conjunto"], m["perfil"], m["rotulo"]) == ("idsse", perfil, rotulo)
        assert [u["semente_efetiva"] for u in m["unidades"]] == [
            "20261107;1;0", "nenhuma", "20261107;1;0", "20261107;2;4"]      # A5, AB1, B8 do jogo 1; B8 do 2
        assert set(m["dados"]) == {f"jogo_{g}" for g in JOGOS_I}
    assert "conjunto" in ex.manifesto(cfg, RAIZ_REPO / "config.yaml", [])     # Metrica tambem declara


def test_cache_inclui_conjunto_e_perfil(cfg, xml_falso):
    u = ("reconstruido", 1, "B", 8, 0)
    src = ex.hashes_src()
    ma, a = ex.chave_unidade(ex.cfg_idsse(cfg), u, src)
    mb, b = ex.chave_unidade(ex.cfg_idsse(cfg, "provedor_b"), u, src)
    mm, m = ex.chave_unidade(cfg, u, src)
    assert len({a, b, m}) == 3
    assert (ma["config"]["dados"]["conjunto"], ma["config"]["dados"]["perfil"]) == ("idsse", None)
    assert (mb["config"]["dados"]["conjunto"], mb["config"]["dados"]["perfil"]) == ("idsse", "provedor_b")
    assert mm["config"]["dados"]["conjunto"] == "metrica" and "idsse" not in mm["config"]
    assert set(ma["dados"]["jogo_1"]) == {"ficha_1.xml", "eventos_1.xml", "posicoes_1.xml"}
    # o leitor do IDSSE le `idsse:`: mudar uma chave dela muda a chave do IDSSE, nao a da Metrica
    c = copy.deepcopy(cfg)
    c["idsse"]["posicao_goleiro"] = "XX"
    assert ex.chave_unidade(ex.cfg_idsse(c), u, src)[1] != a and ex.chave_unidade(c, u, src)[1] == m
    # a saida nao e lida pela unidade
    c = copy.deepcopy(cfg)
    c["idsse_experimento"]["saida"] = "outro"
    assert ex.chave_unidade(ex.cfg_idsse(c), u, src)[1] == a
    # o dado entra: outro conteudo no XML, outra chave
    (xml_falso / "j1" / "posicoes_1.xml").write_text("<posicoes jogo='1' outro='sim'/>", encoding="utf-8")
    assert ex.chave_unidade(ex.cfg_idsse(cfg), u, src)[1] != a


# --- tabelas e figuras no IDSSE ---------------------------------------------------------

def test_tabelas_figuras_idsse_rotulo_sem_eps_c_e_papel(cfg, tmp_path):
    ci = ex.cfg_idsse(cfg, "provedor_b")
    r0 = ci["experimento"]["r0_m"]
    blocos = []
    for nivel in (1, 5, 8):
        for alvo in ex.ALVOS_PRIMARIOS:
            for crit in ("vidal_codina", "estrito"):
                blocos.append(_pontos({j: {r0: (500, 1000, 1000), 2.0: (510 + j, 1000, 1000)} for j in JOGOS_I},
                                      crit, nivel, alvo))
    pontos = pd.concat(blocos, ignore_index=True)
    pontos.to_csv(tmp_path / "pontos.csv", index=False)
    ex.selecionar_logo(pontos, ci).to_csv(tmp_path / "selecao_logo.csv", index=False)
    ex.tabelas_figuras(ci, tmp_path)
    assert not (tmp_path / "tabelas" / "tabela4.csv").exists()
    for k in (1, 2, 3, 5):
        t = pd.read_csv(tmp_path / "tabelas" / f"tabela{k}.csv")
        assert (t["rotulo"] == "EXPLORATORIO").all()
        resp = t[t["papel"] == "responde"]
        assert set(resp["nivel"]) == {5, 8} and set(resp["alvo"]) == set(ex.ALVOS_PRIMARIOS)
        if "criterio" in t.columns:
            assert set(resp["criterio"]) == {"vidal_codina"}
    t1 = pd.read_csv(tmp_path / "tabelas" / "tabela1.csv").set_index(["nivel", "alvo"])
    assert t1.loc[(8, ex.ALVO_PASSE), "n_gabarito"] == 7000 and np.isclose(t1.loc[(8, ex.ALVO_PASSE), "f1"], 0.5)
    for k in (1, 2):
        assert (tmp_path / "figuras" / f"figura{k}.png").stat().st_size > 0


# modos leves de proposito: se a guarda falhar, o teste nao dispara uma rodada pesada
@pytest.mark.parametrize("argv", [["--dados", "idsse", "--inspect"], ["--inspect", "--perfil", "provedor_b"]])
def test_cli_recusa_combinacoes_fora_do_11c(argv):
    from src import run
    with pytest.raises(SystemExit):
        run.main(argv)
