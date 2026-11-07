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
