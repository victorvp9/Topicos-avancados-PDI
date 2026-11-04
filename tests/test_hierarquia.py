"""A hierarquia principal: a ORDEM, o `else` do tiro livre e a conservacao das
transicoes.

Criterios e CAMINHO de cada teste: docs/fatias/04-plano.md §7.2.

O teste da ordem roda com **escanteio E lateral completos ao mesmo tempo** -- o
que nao e artificio: o vertice do campo esta alem da linha lateral auxiliar,
logo o cobrador de escanteio ativa os dois gatilhos de verdade. Se a ordem fosse
a inversa, sairia lateral. O segundo caso do mesmo teste mostra que a ordem nao
atropela o padrao: com a bola no jogador do lateral, sai lateral.

O teste do penalti antes do escanteio roda no **problema 3 do S1** (so gatilhos,
sem padrao), porque e o unico caminho em que os dois tipos podem estar ativos ao
mesmo tempo: o padrao exige a bola na `R_pz` do jogador, e ha uma bola so.
"""

import numpy as np
import pandas as pd

from src.events import bola_parada, hierarquia
from src.io import schema

BOLA_MORTA = [(0.0, 0.0)] + [(np.nan, np.nan)] * 8


def _periods(dir_home: int = 1) -> pd.DataFrame:
    """`periods` sintetico do jogo 1, periodo 1 (esquema PERIODS)."""
    return pd.DataFrame(
        [(1, 1, "away", -dir_home, 40.0 * dir_home),
         (1, 1, "home", dir_home, -40.0 * dir_home)],
        columns=list(schema.PERIODS),
    ).astype(schema.PERIODS)


def _passes(*pares) -> pd.DataFrame:
    """`passes` sintetico: pares `(player_id, quadro)`. Quem passa importa --
    o problema 1 do S1 mede o deslocamento do jogador que passa a bola."""
    return pd.DataFrame(
        {
            "player_id": pd.Series([p for p, _ in pares], dtype="str"),
            "frame": pd.Series([f for _, f in pares], dtype="int64"),
        }
    )


def _detectar(cenario, bola, jogadores, passes=(), dir_home=1):
    frames, tracking, cfg = cenario(bola, jogadores)
    return bola_parada.detectar(
        frames, tracking, _periods(dir_home), _passes(*passes), cfg
    )


def _cena_de_penalti(cfg):
    """Cena de penalti valida: `home` ataca +x, goleiro `away` na linha, cobrador
    `home` 1 m atras da marca, mais um de cada time longe."""
    campo = cfg["campo"]
    meio = campo["comprimento_m"] / 2.0
    marca = meio - campo["marca_penal_m"]
    return {
        "g1_home_9": ("home", [(marca - 1.0, 0.0)] * 10),     # cobrador
        "g1_home_8": ("home", [(10.0, 0.0)] * 10),
        "g1_away_1": ("away", [(meio, 0.0)] * 10),            # goleiro na linha
        "g1_away_2": ("away", [(10.0, 10.0)] * 10),
    }


def test_ordem_escanteio_antes_de_lateral(cenario, cfg):
    """SINTETICO, os dois gatilhos completos AO MESMO TEMPO: sai escanteio."""
    meia = cfg["campo"]["largura_m"] / 2.0
    canto = cfg["campo"]["comprimento_m"] / 2.0
    no_canto = [(canto, meia)] * 10
    det = _detectar(
        cenario,
        BOLA_MORTA + [(canto, meia)],
        {"g1_home_1": ("home", no_canto),
         "g1_away_1": ("away", [(-20.0, -20.0)] * 10)},
        passes=[("g1_home_1", 10)],
    )
    assert det["gatilhos_completos"].iloc[0] == "corner_kick|throw_in"
    assert det["type"].iloc[0] == "corner_kick"
    assert det["via"].iloc[0] == "padrao"


def test_a_ordem_nao_atropela_o_padrao(cenario, cfg):
    """SINTETICO, os dois completos, mas a bola esta no jogador do LATERAL.

    O escanteio vem antes na hierarquia, e mesmo assim sai lateral: o gatilho
    completo so vale com o padrao confirmado.
    """
    meia = cfg["campo"]["largura_m"] / 2.0
    canto = cfg["campo"]["comprimento_m"] / 2.0
    det = _detectar(
        cenario,
        BOLA_MORTA + [(0.0, meia - 0.1)],
        {"g1_home_1": ("home", [(canto, meia)] * 10),
         "g1_home_2": ("home", [(0.0, meia - 0.1)] * 10),
         "g1_away_1": ("away", [(-20.0, -20.0)] * 10)},
        passes=[("g1_home_2", 10)],
    )
    assert det["gatilhos_completos"].iloc[0] == "corner_kick|throw_in"
    assert det["type"].iloc[0] == "throw_in"
    assert det["player_id"].iloc[0] == "g1_home_2"


def test_penalti_antes_de_escanteio(cenario, cfg):
    """SINTETICO, penalti e escanteio completos: sai penalti.

    Roda no problema 3 do S1 (bola longe de todos no primeiro quadro em jogo),
    que e onde dois gatilhos podem estar ativos ao mesmo tempo.
    """
    meia = cfg["campo"]["largura_m"] / 2.0
    canto = cfg["campo"]["comprimento_m"] / 2.0
    jogadores = dict(_cena_de_penalti(cfg))
    jogadores["g1_home_7"] = ("home", [(canto, meia)] * 10)
    det = _detectar(cenario, BOLA_MORTA + [(0.0, 0.0)], jogadores,
                    passes=[("g1_home_9", 10)])
    completos = det["gatilhos_completos"].iloc[0].split("|")
    assert "penalty" in completos and "corner_kick" in completos
    assert det["type"].iloc[0] == "penalty"
    assert det["player_id"].iloc[0] == "g1_home_9"
    assert det["via"].iloc[0] == "reserva_3"


def test_tiro_livre_e_o_else(cenario, cfg):
    """SINTETICO, nenhum gatilho: sai `free_kick`.

    O jogador esta a 10 m do centro (nenhum candidato de pontape inicial) e no
    meio do campo (nem lateral, nem escanteio, nem pequena area). Com a bola na
    PZ dele e um passe no mesmo quadro, o rotulo e a categoria residual.
    """
    det = _detectar(
        cenario,
        BOLA_MORTA + [(0.0, 10.0)],
        {"g1_home_1": ("home", [(0.0, 10.0)] * 10),
         "g1_away_1": ("away", [(-20.0, -20.0)] * 10)},
        passes=[("g1_home_1", 10)],
    )
    assert det["gatilhos_completos"].iloc[0] == ""
    assert det["type"].iloc[0] == "free_kick"
    assert det["player_id"].iloc[0] == "g1_home_1"


def test_numero_de_deteccoes_e_o_numero_de_transicoes(jogo, posse_real, cfg):
    """DADO REAL, TRES JOGOS. Nada e silenciosamente descartado: o numero de
    deteccoes e EXATAMENTE o numero de transicoes morta -> viva, e os valores
    sao os do teto previsto do plano 04 §2.2."""
    previsto = {1: 154, 2: 168, 3: 159}
    for game in (1, 2, 3):
        frames, tracking, periods = jogo(game)
        d0, dc, _ = bola_parada.corridas_mortas(frames["ball_live"])
        det = bola_parada.detectar(
            frames, tracking, periods,
            posse_real(game)["perdas"], cfg,
        )
        assert len(det) == dc.size
        assert len(det) == previsto[game]
        # uma deteccao por intervalo morto, nenhuma repetida
        assert det["dead_run_id"].is_unique
        # `frame` e o primeiro quadro EM JOGO: indice `dc + 1`, 1-based `dc + 2`
        assert (det["frame"].to_numpy() == dc + 2).all()
        assert (det["dur_morta_s"].to_numpy()
                == (dc - d0 + 1) / cfg["tracking"]["fps"]).all()


def test_toda_deteccao_tem_via_e_tipo_do_vocabulario(jogo, posse_real, cfg):
    """DADO REAL, TRES JOGOS. `via` sempre em {padrao, reserva_1, reserva_2,
    reserva_3} e `type` sempre no vocabulario de bola parada do `config.yaml`."""
    tipos = set(cfg["avaliacao"]["grupos"]["bola_parada"])
    for game in (1, 2, 3):
        frames, tracking, periods = jogo(game)
        det = bola_parada.detectar(
            frames, tracking, periods,
            posse_real(game)["perdas"], cfg,
        )
        assert set(det["via"]) <= set(hierarquia.VIAS)
        assert set(det["type"]) <= tipos
        assert det["t"].notna().all() and np.isfinite(det["t"]).all()
        # executor vazio SO em `free_kick?`
        vazio = det["player_id"] == ""
        assert (det.loc[vazio, "type"] == hierarquia.FREE_KICK_DUVIDA).all()
        assert (det.loc[~vazio, "team"] != "").all()
