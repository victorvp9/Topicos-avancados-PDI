"""Fatia 11a: leitor do IDSSE. Os 6 testes do docs/fatias/11-plano.md §5, mais a
guarda da ancoragem em quadro morto (lacuna decidida) e os parametros do config.

Tudo sintetico, salvo o teste 6, que roda o caminho da Metrica."""

import copy

import numpy as np
import pandas as pd
import pytest

from src import experiment as ex
from src.config import RAIZ_REPO
from src.io import idsse, schema

PONTOS_EXP = RAIZ_REPO / "outputs" / "experimento" / "pontos.csv"
HOME, AWAY = "DFL-CLU-H", "DFL-CLU-A"


def _ficha(tmp_path, pitch=("105.00", "68.00")):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<PutDataRequest><MatchInformation>
<Environment PitchX="{pitch[0]}" PitchY="{pitch[1]}"/>
<Teams>
 <Team TeamId="{AWAY}" Role="guest"><Players>
  <Player PersonId="P-A1" PlayingPosition="STZ"/></Players></Team>
 <Team TeamId="{HOME}" Role="home"><Players>
  <Player PersonId="P-H1" PlayingPosition="TW"/></Players></Team>
</Teams></MatchInformation></PutDataRequest>"""
    p = tmp_path / "ficha.xml"
    p.write_text(xml, encoding="utf-8")
    return p


def _t(segundos):
    """T UTC no formato da DFL, a partir de 13:30:12.600."""
    base = pd.Timestamp("2023-05-27T13:30:12.600Z") + pd.Timedelta(seconds=segundos)
    return base.strftime("%Y-%m-%dT%H:%M:%S.") + f"{base.microsecond // 1000:03d}+00:00"


def _frameset(secao, team, pessoa, linhas):
    corpo = "\n".join(linhas)
    return f'<FrameSet GameSection="{secao}" TeamId="{team}" PersonId="{pessoa}">\n{corpo}\n</FrameSet>'


def _posicoes(tmp_path, bola_x0=0.5):
    """2 jogadores, bola e arbitro, 2 tempos. 1o tempo N 10000..10003, 2o tempo
    N 100000..100002 (T 60 s depois). P-A1 sai no ultimo quadro do 2o tempo e
    tem X = NaN no 2o quadro do 1o tempo; a bola tem X = NaN num quadro VIVO."""
    status = {1: [0, 1, 1, 0], 2: [1, 1, 0]}
    fs = []
    for secao, n0, t0, n, p in (("firstHalf", 10000, 0.0, 4, 1), ("secondHalf", 100000, 60.0, 3, 2)):
        bola, h1, a1, ref = [], [], [], []
        for k in range(n):
            t = _t(t0 + 0.04 * k)
            bx = "NaN" if (p, k) == (2, 1) else f"{bola_x0 + k:.2f}"
            bola.append(f'<Frame N="{n0 + k}" T="{t}" X="{bx}" Y="-1.00" Z="0.00" '
                        f'BallPossession="1" BallStatus="{status[p][k]}"/>')
            h1.append(f'<Frame N="{n0 + k}" T="{t}" X="{-40.0 - k:.2f}" Y="{2.0 * p:.2f}"/>')
            if not (p == 2 and k == n - 1):
                ax = "NaN" if (p, k) == (1, 1) else f"{10.0 + k:.2f}"
                a1.append(f'<Frame N="{n0 + k}" T="{t}" X="{ax}" Y="-5.00"/>')
            ref.append(f'<Frame N="{n0 + k}" T="{t}" X="99.00" Y="99.00"/>')
        fs += [_frameset(secao, "referee", "R1", ref), _frameset(secao, HOME, "P-H1", h1),
               _frameset(secao, AWAY, "P-A1", a1), _frameset(secao, "BALL", "B", bola)]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<PutDataRequest><Positions>\n'
           '<MetaData><PitchSize X="105.00" Y="68.00"/></MetaData>\n' + "\n".join(fs) +
           "\n</Positions></PutDataRequest>")
    p = tmp_path / "posicoes.xml"
    p.write_text(xml, encoding="utf-8")
    return p


def _eventos(tmp_path, corpos):
    """`corpos`: lista de (EventTime, xml do filho)."""
    evs = "\n".join(f'<Event EventId="E{i}" EventTime="{t}">{c}</Event>' for i, (t, c) in enumerate(corpos))
    p = tmp_path / "eventos.xml"
    p.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<PutDataRequest>\n{evs}\n</PutDataRequest>',
                 encoding="utf-8")
    return p


PASSE = f'<Play Player="P-H1" Team="{HOME}" Evaluation="successfullyCompleted"><Pass/></Play>'


@pytest.fixture(scope="module")
def sintetico(tmp_path_factory, cfg):
    d = tmp_path_factory.mktemp("idsse")
    ficha = idsse.ler_ficha(_ficha(d), cfg)
    return d, ficha, idsse.converter_posicoes(_posicoes(d), ficha, 9, cfg)


# --- 1. esquema interno ------------------------------------------------------------

def test_1_xml_sintetico_da_o_esquema_interno(sintetico):
    _, _, (frames, tracking, t_utc, nan) = sintetico
    schema.validar(frames, schema.FRAMES, "frames")
    schema.validar(tracking, schema.TRACKING, "tracking")
    assert frames["frame"].tolist() == list(range(1, 8))                  # contiguos entre os tempos
    assert frames["period"].tolist() == [1, 1, 1, 1, 2, 2, 2]
    assert np.allclose(frames["t"], frames["frame"] / 25)
    assert frames["ball_live"].tolist() == [False, True, True, False, True, True, False]   # BallStatus
    assert np.isnan(frames["ball_x"].iloc[5]) and frames["ball_live"].iloc[5]   # NaN nao decide ball_live
    assert frames["ball_x"].iloc[[0, 4]].tolist() == [0.5, 0.5] and (frames["ball_y"].dropna() == -1.0).all()
    assert nan == {"jogador_linhas": 1, "bola_quadros": 1}
    assert set(tracking["player_id"]) == {"g9_home_P-H1", "g9_away_P-A1"}   # arbitro pulado
    h = tracking[tracking["player_id"] == "g9_home_P-H1"]
    assert h["frame"].tolist() == list(range(1, 8)) and h["is_gk"].all() and (h["team"] == "home").all()
    assert h["x"].tolist() == [-40.0, -41.0, -42.0, -43.0, -40.0, -41.0, -42.0]
    assert h["y"].tolist() == [2.0] * 4 + [4.0] * 3
    a = tracking[tracking["player_id"] == "g9_away_P-A1"]
    assert a["frame"].tolist() == [1, 3, 4, 5, 6]                          # NaN e saida: sem linha
    assert not a["is_gk"].any() and tracking["visible"].all()
    assert np.diff(t_utc).tolist()[:3] == [40_000_000] * 3


def test_1_parametros_do_config_mudam_a_saida(tmp_path, cfg):
    """Cada chave lida na conversao muda o resultado se for trocada."""
    pos, ficha_p = _posicoes(tmp_path), _ficha(tmp_path)
    c = copy.deepcopy(cfg)
    c["idsse"]["ball_status_vivo"] = 0
    fr = idsse.converter_posicoes(pos, idsse.ler_ficha(ficha_p, c), 9, c)[0]
    assert fr["ball_live"].tolist() == [True, False, False, True, False, False, True]
    c = copy.deepcopy(cfg)
    c["idsse"]["posicao_goleiro"] = "STZ"
    tr = idsse.converter_posicoes(pos, idsse.ler_ficha(ficha_p, c), 9, c)[1]
    assert set(tr.loc[tr["is_gk"], "player_id"]) == {"g9_away_P-A1"}
    c = copy.deepcopy(cfg)
    c["idsse"]["team_ids_ignorados"] = []
    with pytest.raises(ValueError, match="fora da ficha"):
        idsse.converter_posicoes(pos, idsse.ler_ficha(ficha_p, c), 9, c)
    c = copy.deepcopy(cfg)
    c["tracking"]["fps"] = 50
    with pytest.raises(ValueError, match="nao avanca"):
        idsse.converter_posicoes(pos, idsse.ler_ficha(ficha_p, c), 9, c)
    with pytest.raises(ValueError, match="PitchX"):
        idsse.ler_ficha(_ficha(tmp_path, pitch=("100.00", "68.00")), cfg)


# --- 2. mapeamento -----------------------------------------------------------------

T0 = "2023-05-27T15:30:12.640+02:00"     # = quadro 2 do sintetico


def test_2_tipo_desconhecido_estoura(sintetico, cfg):
    d, ficha, _ = sintetico
    with pytest.raises(ValueError, match="tipo DFL 'Inventado'"):
        idsse.ler_eventos(_eventos(d, [(T0, "<Inventado/>")]), ficha, 9, cfg)
    with pytest.raises(ValueError, match="passe.filhos"):
        idsse.ler_eventos(_eventos(d, [(T0, f'<Play Player="P-H1" Team="{HOME}" Evaluation="successful">'
                                            '<Chute/></Play>')]), ficha, 9, cfg)
    with pytest.raises(ValueError, match="executor"):
        idsse.ler_eventos(_eventos(d, [(T0, f'<ThrowIn Team="{HOME}"><Outro Player="P-H1"/></ThrowIn>')]),
                          ficha, 9, cfg)


def test_2_delete_descartado_e_contado(sintetico, cfg):
    d, ficha, _ = sintetico
    crus, n_delete = idsse.ler_eventos(
        _eventos(d, [(T0, "<Delete/>"), (T0, PASSE), (T0, '<Delete Reason="foul"/>'),
                     (T0, f'<TacklingGame Winner="P-A1" WinnerTeam="{AWAY}"/>')]), ficha, 9, cfg)
    assert n_delete == 2
    assert crus["type"].tolist() == ["pass", "fora_do_escopo"]
    assert crus["event_id"].tolist() == ["E1", "E3"]
    c = copy.deepcopy(cfg)
    c["idsse"]["descartar"] = []
    assert idsse.ler_eventos(_eventos(d, [(T0, "<Delete/>")]), ficha, 9, c)[1] == 0


# --- 3. executor -------------------------------------------------------------------

def test_3_executor_vem_do_play_filho_e_nao_vira_passe(sintetico, cfg):
    d, ficha, (frames, _, t_utc, _) = sintetico
    crus, _ = idsse.ler_eventos(_eventos(d, [
        (T0, f'<ThrowIn Team="{AWAY}"><Play Player="P-A1" Team="{AWAY}"><Cross/></Play></ThrowIn>'),
        (T0, f'<FreeKick Team="{HOME}"><ShotAtGoal Player="P-H1" Team="{HOME}"><SavedShot/></ShotAtGoal>'
             '</FreeKick>'),
        (T0, f'<Play Player="P-A1" Team="{AWAY}" Evaluation="successfullyCompleted"><Cross/></Play>'),
    ]), ficha, 9, cfg)
    ev = idsse.construir_gabarito(9, crus, frames, t_utc, cfg)
    assert ev["type"].tolist() == ["throw_in", "free_kick", "pass"]       # 3 eventos, so 1 passe
    assert ev["player_id"].tolist() == ["g9_away_P-A1", "g9_home_P-H1", "g9_away_P-A1"]
    assert ev["metrica_subtype"].tolist()[0] == "ThrowIn/Play/Cross"
    assert ev["pass_secundario"].tolist() == [False, False, True]


def test_3_passe_principal_so_completo_secundario_todo_play(sintetico, cfg):
    """I1 (decisoes.md 2026-11-07): completo -> `pass`; `unsuccessful` ->
    `fora_do_escopo` e `pass_secundario`; `Evaluation` desconhecido estoura."""
    d, ficha, (frames, _, t_utc, _) = sintetico
    play = '<Play Player="P-H1" Team="' + HOME + '" Evaluation="{}"><Pass/></Play>'
    crus, _ = idsse.ler_eventos(_eventos(d, [(T0, play.format(v)) for v in
                                             ("successfullyCompleted", "successful", "unsuccessful")]), ficha, 9, cfg)
    ev = idsse.construir_gabarito(9, crus, frames, t_utc, cfg)
    assert ev["type"].tolist() == ["pass", "pass", "fora_do_escopo"]
    assert ev["pass_secundario"].all()
    for mau in ("inventado", None):
        corpo = play.format(mau) if mau else f'<Play Player="P-H1" Team="{HOME}"><Pass/></Play>'
        with pytest.raises(ValueError, match="Evaluation"):
            idsse.ler_eventos(_eventos(d, [(T0, corpo)]), ficha, 9, cfg)
    c = copy.deepcopy(cfg)                       # as duas chaves sao lidas
    c["idsse"]["passe"]["evaluation_completo"] = ["successfullyCompleted"]
    c["idsse"]["passe"]["evaluation_incompleto"] = ["unsuccessful", "successful"]
    assert idsse.ler_eventos(_eventos(d, [(T0, play.format("successful"))]), ficha, 9, c)[0]["type"].tolist()         == ["fora_do_escopo"]
    c = copy.deepcopy(cfg)
    c["idsse"]["bola_parada"] = {k: v for k, v in cfg["idsse"]["bola_parada"].items() if k != "ThrowIn"}
    crus, _ = idsse.ler_eventos(_eventos(d, [(T0, f'<ThrowIn Team="{AWAY}"><Play Player="P-A1" Team="{AWAY}">'
                                                  '<Pass/></Play></ThrowIn>')]), ficha, 9, c)
    assert crus["type"].tolist() == ["fora_do_escopo"]   # sem a chave, ThrowIn sai do escopo


# --- 4. EventTime -> quadro --------------------------------------------------------

def _quadro_e_dt(sintetico, cfg, event_time):
    d, ficha, (frames, _, t_utc, _) = sintetico
    crus, _ = idsse.ler_eventos(_eventos(d, [(event_time, PASSE)]), ficha, 9, cfg)
    ev = idsse.construir_gabarito(9, crus, frames, t_utc, cfg)
    return int(ev["annotated_frame"].iloc[0]), float(ev["dt_sync_s"].iloc[0]), int(ev["period"].iloc[0])


def test_4_eventtime_com_fuso_bate_com_o_t_utc(sintetico, cfg):
    # 15:30:12.680+02:00 = 13:30:12.680Z = T do 3o quadro; 2o tempo comeca 60 s depois
    assert _quadro_e_dt(sintetico, cfg, "2023-05-27T15:30:12.680+02:00") == (3, 0.0, 1)
    assert _quadro_e_dt(sintetico, cfg, "2023-05-27T15:31:12.640+02:00") == (6, 0.0, 2)
    f, dt, _ = _quadro_e_dt(sintetico, cfg, "2023-05-27T15:30:12.690+02:00")   # 10 ms depois
    assert f == 3 and dt == pytest.approx(0.01)
    # o fuso trocado (+01:00) cai uma hora depois, longe da grade: o caso falha
    f, dt, _ = _quadro_e_dt(sintetico, cfg, "2023-05-27T15:30:12.680+01:00")
    assert f != 3 and abs(dt) > 3000


def test_4_quadro_do_instante_empate_e_bordas():
    t = np.array([0, 40, 80], dtype="int64")
    f, dt = idsse.quadro_do_instante(np.array([20, -5, 200, 41]), t)
    assert f.tolist() == [1, 1, 3, 2]                                     # empate: o mais antigo
    assert dt.tolist() == pytest.approx([20e-9, -5e-9, 120e-9, 1e-9])


# --- ancoragem (lacuna decidida) ---------------------------------------------------

def test_ancoragem_anotado_em_morto_avanca_com_guarda():
    vivo = np.array([True, False, False, True, True, False, False, False, False, True])
    frames, sem_morto, em_morto = idsse.ancorar_idsse(np.array([5, 2, 6, 8]), vivo, guarda_quadros=3)
    # 5: vivo -> recua ao 4 (regra da Metrica); 2: morto -> avanca ao 4; 6: morto, 4 quadros > guarda -> fica;
    # 8: morto -> avanca ao 10
    assert frames.tolist() == [4, 4, 6, 10]
    assert sem_morto.tolist() == [False, False, True, False]
    assert em_morto.tolist() == [False, True, True, True]
    frames, sem_morto, _ = idsse.ancorar_idsse(np.array([6]), vivo, guarda_quadros=4)   # guarda varrida
    assert frames.tolist() == [10] and not sem_morto[0]
    frames, sem_morto, _ = idsse.ancorar_idsse(np.array([2]), np.array([True, False, False]), 10)
    assert frames.tolist() == [2] and sem_morto[0]                        # sem quadro vivo depois


# --- 5. cache ----------------------------------------------------------------------

def test_5_cache_invalida_quando_o_sha256_muda(tmp_path, cfg, monkeypatch):
    pos, ficha_p, cache = _posicoes(tmp_path), _ficha(tmp_path), tmp_path / "cache"
    r1 = idsse.posicoes_cacheadas(pos, ficha_p, 9, cfg, cache)
    assert r1[-1] == "miss"
    chamadas = []
    original = idsse.converter_posicoes
    monkeypatch.setattr(idsse, "converter_posicoes", lambda *a: chamadas.append(1) or original(*a))
    r2 = idsse.posicoes_cacheadas(pos, ficha_p, 9, cfg, cache)
    assert r2[-1] == "hit" and not chamadas
    pd.testing.assert_frame_equal(r1[0], r2[0])
    pd.testing.assert_frame_equal(r1[1], r2[1])
    _posicoes(tmp_path, bola_x0=7.0)                                      # mesmo caminho, outro conteudo
    r3 = idsse.posicoes_cacheadas(pos, ficha_p, 9, cfg, cache)
    assert r3[-1] == "miss" and chamadas == [1]
    assert r3[0]["ball_x"].iloc[0] == 7.0
    assert len(list(cache.glob("idsse_*.pkl"))) == 2
    assert idsse.posicoes_cacheadas(pos, ficha_p, 9, cfg, None)[-1] == "desligado"


# --- 6. caminho da Metrica bit a bit -----------------------------------------------

@pytest.mark.parametrize("u", [("reconstruido", "AB", 1, 0), ("reconstruido", "B", 8, 0)])
def test_6_metrica_padrao_reproduz_a_rodada_final(jogo, eventos, cfg, u):
    """Com o config padrao (dados da Metrica), AB1 e uma unidade B8 do jogo 1 em
    R0 reproduzem `outputs/experimento/pontos.csv` bit a bit (texto CSV)."""
    if not PONTOS_EXP.exists():
        pytest.skip("outputs/experimento/pontos.csv ausente")
    frames, tracking, periods = jogo(1)
    base = {1: {"frames": frames, "tracking": tracking, "periods": periods, "eventos": eventos(1)[1]}}
    c = ex._trocar(cfg, posse__grade_r_pz_m=[cfg["experimento"]["r0_m"]])
    tab = ex._ler_tabela(ex.rodar_unidade(1, u[1], u[2], u[3], u[0], c, base).to_csv(index=False))
    assert ex.conferir_linha_base(tab, PONTOS_EXP, cfg) == len(tab) > 0


# --- Fatia 11b: teto no IDSSE ------------------------------------------------------

def _jogo_sintetico(d):
    """Ficha + posicoes + eventos de um jogo minimo para o `--teto-idsse`: 2
    goleiros e 2 de linha, 100 quadros por tempo, bola morta nos 10 primeiros
    do 1o tempo e nos 5 primeiros do 2o; um lateral anotado em quadro morto
    (avanca, D1), um passe completo e um errado."""
    ficha = f"""<?xml version="1.0" encoding="UTF-8"?>
<PutDataRequest><MatchInformation><Environment PitchX="105.00" PitchY="68.00"/><Teams>
 <Team TeamId="{HOME}" Role="home"><Players><Player PersonId="H1" PlayingPosition="TW"/>
  <Player PersonId="H2" PlayingPosition="STZ"/></Players></Team>
 <Team TeamId="{AWAY}" Role="guest"><Players><Player PersonId="A1" PlayingPosition="TW"/>
  <Player PersonId="A2" PlayingPosition="STZ"/></Players></Team>
</Teams></MatchInformation></PutDataRequest>"""
    (d / "ficha.xml").write_text(ficha, encoding="utf-8")
    pos = {"H1": (HOME, -50.0, 0.0), "H2": (HOME, 10.0, 34.0), "A1": (AWAY, 50.0, 0.0), "A2": (AWAY, 20.0, 10.0)}
    fs = []
    for secao, n0, t0, mortos in (("firstHalf", 10000, 0.0, 10), ("secondHalf", 100000, 60.0, 5)):
        bola = []
        for k in range(100):
            x = 10.0 + 0.2 * max(k - mortos, 0)
            bola.append(f'<Frame N="{n0 + k}" T="{_t(t0 + 0.04 * k)}" X="{x:.2f}" Y="34.00" '
                        f'BallStatus="{0 if k < mortos else 1}"/>')
        for pessoa, (team, x, y) in pos.items():
            fs.append(_frameset(secao, team, pessoa, [f'<Frame N="{n0 + k}" T="{_t(t0 + 0.04 * k)}" X="{x:.2f}" '
                                                      f'Y="{y:.2f}"/>' for k in range(100)]))
        fs.append(_frameset(secao, "BALL", "B", bola))
    (d / "posicoes.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<PutDataRequest><Positions>\n'
                                    + "\n".join(fs) + "\n</Positions></PutDataRequest>", encoding="utf-8")
    _eventos(d, [
        ("2023-05-27T15:30:12.800+02:00",       # quadro 6, morto
         f'<ThrowIn Team="{HOME}"><Play Player="H2" Team="{HOME}"><Pass/></Play></ThrowIn>'),
        ("2023-05-27T15:30:13.200+02:00",
         f'<Play Player="H2" Team="{HOME}" Evaluation="successfullyCompleted"><Pass/></Play>'),
        ("2023-05-27T15:30:14.000+02:00",
         f'<Play Player="A2" Team="{AWAY}" Evaluation="unsuccessful"><Pass/></Play>'),
    ])
    return {"ficha": d / "ficha.xml", "posicoes": d / "posicoes.xml", "eventos": d / "eventos.xml"}


@pytest.fixture
def teto_sintetico(tmp_path, cfg, monkeypatch):
    """(rodar, cfg_1jogo): `rodar(cfg)` roda o `--teto-idsse` inteiro no jogo sintetico."""
    from src import teto_idsse
    arq = _jogo_sintetico(tmp_path)
    monkeypatch.setattr(idsse, "caminhos", lambda c, g: arq)
    c = copy.deepcopy(cfg)
    c["idsse"]["jogos"] = ["SINT"]
    return (lambda cc, **kw: teto_idsse.rodar_teto_idsse(cc, saida=tmp_path / "teto", **kw)), c, tmp_path


def test_11b_ponta_a_ponta_no_xml_sintetico(teto_sintetico):
    rodar, c, d = teto_sintetico
    r = rodar(c)
    for nome in ("pontos", "pontos_h2", "eps_c", "tabela", "via", "mortos", "hipoteses"):
        assert (d / "teto" / (nome + ".csv")).exists()
    t = r["tabela"].set_index(["criterio", "alvo"])
    assert set(t.index.get_level_values(0)) == set(c["avaliacao"]["criterios"])
    for crit in c["avaliacao"]["criterios"]:                 # nenhum evento descartado
        assert t.loc[(crit, "throw_in"), "n_gabarito"] == 1
        assert t.loc[(crit, "passe_principal"), "n_gabarito"] == 1      # so o completo
        assert t.loc[(crit, "passe_secundario"), "n_gabarito"] == 2     # completo + errado
    assert (t["tp_diag"] <= t[["n_detectado", "n_gabarito"]].min(axis=1)).all()
    p = r["pontos"]
    assert p.loc[p["alvo"] == "throw_in", "n_gabarito"].eq(1).all()
    assert sorted(r["curva"]["eps_c_m"].unique()) == sorted(c["bola_parada"]["grade_eps_c_m"])
    assert set(r["hipoteses"]["hipotese"]) == {"H1", "H2", "H3"}
    assert c["avaliacao"]["criterio_principal"] == "estrito"         # a Metrica nao muda


def test_11b_criterio_principal_do_idsse_muda_o_resultado(teto_sintetico):
    """`idsse.criterio_principal` decide onde caem as colunas R9 e de onde sai a H1."""
    rodar, c, _ = teto_sintetico
    linhas_r9 = {}
    for crit in ("vidal_codina", "estrito"):
        cc = copy.deepcopy(c)
        cc["idsse"]["criterio_principal"] = crit
        p = rodar(cc)["pontos"]
        com_r9 = p.loc[p["gab_exec_visivel"].notna(), ["criterio", "ancora"]].drop_duplicates()
        linhas_r9[crit] = sorted(map(tuple, com_r9.to_numpy()))
    assert linhas_r9 == {"vidal_codina": [("vidal_codina", "frame")], "estrito": [("estrito", "frame")]}


def test_11b_cfg_teto_nao_mexe_na_metrica(cfg):
    from src import teto_idsse
    antes = copy.deepcopy(cfg)
    c, h2 = teto_idsse.cfg_teto(cfg), teto_idsse.cfg_teto(cfg, h2=True)
    assert cfg == antes and cfg["avaliacao"]["criterio_principal"] == "estrito"
    assert c["avaliacao"]["criterio_principal"] == cfg["idsse"]["criterio_principal"] == "vidal_codina"
    assert c["posse"]["grade_r_pz_m"] == [cfg["experimento"]["r0_m"]]
    assert not any(c["exploratorio"][k] for k in ex.EXPLORATORIO_LIDO)
    assert h2["exploratorio"]["supressao_exige_executor"] and not h2["exploratorio"]["bola_some_no_apagao"]


def test_11b_hipoteses_limiares_do_config():
    """H1 e H2 leem os limiares do config; NaN nunca passa."""
    from src import teto_idsse
    base = pd.DataFrame([dict(condicao="reconstruido", jogo=g, variante="AB", nivel=1, rep=0, r_pz=0.5,
                              politica="acompanha_r_pz", lacuna5="com", criterio="vidal_codina", ancora="frame",
                              alvo=a, n_gabarito=10, n_detectado=10, tp_diag=tp, tp=tp)
                         for g in (1, 2) for a, tp in (("bola_parada_micro", 8), ("passe_principal", 5))])
    h2 = base.assign(tp_diag=np.where(base["alvo"] == "passe_principal", [6, 6, 4, 4][:len(base)], base["tp_diag"]))
    h2.loc[(h2["jogo"] == 2) & (h2["alvo"] == "passe_principal"), "tp_diag"] = 4
    h2.loc[(h2["jogo"] == 1) & (h2["alvo"] == "passe_principal"), "tp_diag"] = 7
    via = pd.DataFrame({"via": ["padrao", "reserva_1", "reserva_2", "reserva_3"], "n_detectado": [4, 2, 0, 2],
                        "tp_diag": [4, 1, 0, 1]})
    cfg = {"idsse": {"criterio_principal": "vidal_codina",
                     "hipoteses": {"h1_precisao_micro_min": 0.75, "h2_min_jogos": 1}},
           "posse": {"r_dz_politica": "acompanha_r_pz"}}
    h = teto_idsse.hipoteses(base, h2, via, cfg).set_index("medida")
    assert h.loc["precisao_micro", "valor"] == 0.8 and h.loc["precisao_micro", "passa"]
    assert h.loc["delta_f1_passe_agregado", "valor"] == pytest.approx(0.05)
    assert h.loc["jogos_com_delta_pos", "valor"] == 1 and h.loc["jogos_com_delta_pos", "passa"]
    assert np.isnan(h.loc["precisao_via_reserva_2", "valor"])
    assert h.loc["padrao_maior_que_reserva_1_e_3", "passa"] and not h.loc["padrao_maior_de_todas", "passa"]
    cfg["idsse"]["hipoteses"] = {"h1_precisao_micro_min": 0.85, "h2_min_jogos": 2}
    h = teto_idsse.hipoteses(base, h2, via, cfg).set_index("medida")
    assert not h.loc["precisao_micro", "passa"] and not h.loc["jogos_com_delta_pos", "passa"]


# --- revisao da 11b: mutantes -------------------------------------------------------

def _pontos_h(linhas):
    """`linhas`: [(jogo, criterio, alvo, n_gab, n_det, tp)] -> pontos do teto."""
    return pd.DataFrame([dict(condicao="reconstruido", jogo=g, variante="AB", nivel=1, rep=0, r_pz=0.5,
                              politica="acompanha_r_pz", lacuna5="com", criterio=cr, ancora="frame", alvo=a,
                              n_gabarito=ng, n_detectado=nd, tp_diag=tp, tp=tp)
                         for g, cr, a, ng, nd, tp in linhas])


def _cfg_h(principal="vidal_codina", h1=0.75, h2=1):
    return {"idsse": {"criterio_principal": principal,
                      "hipoteses": {"h1_precisao_micro_min": h1, "h2_min_jogos": h2}},
            "posse": {"r_dz_politica": "acompanha_r_pz"}}


VIA_OK = pd.DataFrame({"via": ["padrao", "reserva_1", "reserva_2", "reserva_3"], "n_detectado": [4, 2, 0, 2],
                       "tp_diag": [4, 1, 0, 1]})
VC, ES, MI, PP = "vidal_codina", "estrito", "bola_parada_micro", "passe_principal"


def test_11b_hipoteses_leem_o_criterio_principal_do_config():
    """(a) H1 e H2 saem das linhas de `idsse.criterio_principal`, nao de um nome fixo."""
    from src import teto_idsse
    base = _pontos_h([(1, VC, MI, 10, 10, 9), (1, ES, MI, 10, 10, 6), (1, VC, PP, 10, 10, 5), (1, ES, PP, 10, 10, 5)])
    h2 = base.copy()
    h2.loc[(h2["criterio"] == ES) & (h2["alvo"] == PP), "tp_diag"] = 4
    for principal, h1, dh2 in ((VC, 0.9, 0.0), (ES, 0.6, -0.1)):
        h = teto_idsse.hipoteses(base, h2, VIA_OK, _cfg_h(principal)).set_index("medida")
        assert h.loc["precisao_micro", "valor"] == pytest.approx(h1)
        assert h.loc["delta_f1_passe_agregado", "valor"] == pytest.approx(dh2)


def test_11b_h2_exige_delta_agregado_positivo():
    """(c) Simpson: Delta > 0 nos dois jogos e < 0 no agregado -> H2 nao passa."""
    from src import teto_idsse
    base = _pontos_h([(1, VC, PP, 50, 50, 1), (2, VC, PP, 100, 100, 90), (1, VC, MI, 1, 1, 1), (2, VC, MI, 1, 1, 1)])
    h2 = _pontos_h([(1, VC, PP, 50, 950, 50), (2, VC, PP, 100, 100, 91), (1, VC, MI, 1, 1, 1), (2, VC, MI, 1, 1, 1)])
    h = teto_idsse.hipoteses(base, h2, VIA_OK, _cfg_h(h2=1)).set_index("medida")
    assert h.loc["jogos_com_delta_pos", "valor"] == 2
    assert h.loc["delta_f1_passe_agregado", "valor"] < 0
    assert not h.loc["jogos_com_delta_pos", "passa"]


def test_11b_h3_exige_as_duas_reservas():
    """(d) `padrao` acima de uma reserva e abaixo da outra -> H3 nao passa."""
    from src import teto_idsse
    base = _pontos_h([(1, VC, PP, 10, 10, 5), (1, VC, MI, 10, 10, 8)])
    for tps in ([6, 5, 0, 7], [6, 7, 0, 5]):
        via = VIA_OK.assign(n_detectado=[10, 10, 0, 10], tp_diag=tps)
        h = teto_idsse.hipoteses(base, base, via, _cfg_h()).set_index("medida")
        assert not h.loc["padrao_maior_que_reserva_1_e_3", "passa"]


def _espiao(monkeypatch, mexe=None):
    """Troca `experiment.rodar_unidade` por um espiao que registra
    (supressao_exige_executor, eps_c_m, r0_m) de cada chamada e, se `mexe`,
    altera a saida."""
    chamadas, original = [], ex.rodar_unidade

    def espiao(jogo, variante, nivel, rep, condicao, c, base):
        chamadas.append((c["exploratorio"]["supressao_exige_executor"], c["bola_parada"]["eps_c_m"],
                         c["experimento"]["r0_m"]))
        out = original(jogo, variante, nivel, rep, condicao, c, base)
        return mexe(out) if mexe else out
    monkeypatch.setattr(ex, "rodar_unidade", espiao)
    return chamadas


def test_11b_h2_liga_a_chave_e_a_curva_varre_eps_c(teto_sintetico, monkeypatch, cfg):
    """(b) a unidade da H2 tem `supressao_exige_executor` ligada; (f) cada ponto
    da curva roda com o seu `eps_c`, e a coluna `eps_c_m` e o valor rodado."""
    rodar, c, _ = teto_sintetico
    chamadas = _espiao(monkeypatch)
    r = rodar(c)
    eps0, r0 = cfg["bola_parada"]["eps_c_m"], cfg["experimento"]["r0_m"]
    grade = cfg["bola_parada"]["grade_eps_c_m"]
    assert chamadas == [(False, eps0, r0), (True, eps0, r0)] + [(False, e, r0) for e in grade]
    assert sorted(r["eps_c"]["eps_c_m"].unique()) == sorted(grade)


def test_11b_conferencia_do_gabarito_estoura(teto_sintetico, monkeypatch):
    """(e) `n_gabarito` diferente do gabarito, mas igual em todas as rodadas (o
    `conferir_n_gabarito` nao pega), estoura no `conferir_gabarito`."""
    rodar, c, _ = teto_sintetico
    _espiao(monkeypatch, lambda p: p.assign(n_gabarito=p["n_gabarito"] + 1))
    with pytest.raises(RuntimeError, match="!= gabarito"):
        rodar(c)


def test_11b_guarda_tp_diagnostico_contra_unidade_estoura(teto_sintetico, monkeypatch):
    """(e) o `tp_diag` micro da unidade diferente do da deteccao refeita estoura."""
    rodar, c, _ = teto_sintetico
    _espiao(monkeypatch, lambda p: p.assign(tp_diag=p["tp_diag"] + 1, tp=p["tp"] + 1,
                                            n_detectado=p["n_detectado"] + 1))
    with pytest.raises(RuntimeError, match="tp micro"):
        rodar(c)


def test_11b_via_exclui_o_penalti(teto_sintetico, monkeypatch):
    """(e) a populacao da H3 e a do micro: a deteccao de penalti (acerto) nao
    entra em `via` nem em `tp_micro`."""
    from src import run as run_mod, teto_idsse
    _, c, _ = teto_sintetico
    j = idsse.carregar_jogo(1, c)
    ev = j["eventos"]
    lat = ev[ev["type"] == "throw_in"].iloc[0]
    pen = lat.copy()
    pen[["type", "frame", "annotated_frame", "source_rows"]] = ["penalty", 50, 50, "PEN"]
    ev_diag = pd.concat([ev, pen.to_frame().T], ignore_index=True).astype(ev.dtypes.to_dict())
    base = {1: {"frames": j["frames"], "tracking": j["tracking"], "periods": j["periods"],
                "eventos": ev_diag[list(schema.EVENTS)]}}
    det = pd.DataFrame({"game": 1, "period": 1, "frame": [int(lat["frame"]), 50], "t": [lat["frame"] / 25, 2.0],
                        "type": ["throw_in", "penalty"], "team": "home", "player_id": lat["player_id"],
                        "via": ["reserva_3", "padrao"]})
    monkeypatch.setattr(run_mod, "detectar_jogos", lambda b, cc, jogos, **k: det)
    via, _, conf = teto_idsse.diagnostico_jogo(1, base, ev_diag, teto_idsse.cfg_teto(c))
    v = via.set_index("via")
    assert v["n_detectado"].sum() == 1 and v.loc["reserva_3", "tp_diag"] == 1
    assert v.loc["padrao", "n_detectado"] == 0 and conf["tp_micro"] == 1


# --- sensibilidade EXPLORATORIA do provedor B --------------------------------------

def test_perfil_provedor_b_troca_r0_e_eps(cfg):
    from src import teto_idsse
    p = cfg["idsse"]["perfil_provedor_b"]
    assert (p["r_pz_m"], p["eps_s_m"], p["eps_v_ms"]) == (1.0, 0.10, 5.0)
    assert (p["eps_s_m"], p["eps_v_ms"]) == (cfg["posse"]["diagnostico_eps_s_alt_m"],
                                             cfg["posse"]["diagnostico_eps_v_alt_ms"])
    c = teto_idsse.cfg_teto(teto_idsse.aplicar_perfil(cfg, "provedor_b"))
    assert c["posse"]["grade_r_pz_m"] == [1.0] and c["experimento"]["r0_m"] == 1.0
    assert (c["posse"]["eps_s_m"], c["posse"]["eps_v_ms"]) == (0.10, 5.0)
    assert cfg["experimento"]["r0_m"] == 0.5 and cfg["posse"]["eps_s_m"] == 0.05      # o cfg nao muda


def test_perfil_provedor_b_ponta_a_ponta(teto_sintetico, monkeypatch):
    rodar, c, d = teto_sintetico
    chamadas = _espiao(monkeypatch)
    r = rodar(c, perfil="provedor_b")
    assert chamadas == [(False, c["bola_parada"]["eps_c_m"], 1.0)]      # so a base: sem H2, sem curva
    assert (r["pontos"]["r_pz"] == 1.0).all()
    for nome in ("pontos", "tabela", "via", "mortos"):
        assert (r[nome]["rotulo"] == "EXPLORATORIO").all()
        assert (d / "teto" / (nome + ".csv")).exists()
    assert not (d / "teto" / "hipoteses.csv").exists()
