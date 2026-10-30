"""Leitura do config.yaml e do mapeamento de eventos.

Toda constante do projeto vive em config.yaml (CLAUDE.md). Nada aqui tem valor
padrao: se a chave faltar, estoura.
"""

from pathlib import Path

import yaml

RAIZ_REPO = Path(__file__).resolve().parents[1]


def carregar_config(caminho: Path | str | None = None) -> dict:
    """Carrega config.yaml e resolve os caminhos relativos a raiz do repositorio."""
    caminho = Path(caminho) if caminho is not None else RAIZ_REPO / "config.yaml"
    cfg = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    cfg["dados"]["raiz"] = (RAIZ_REPO / cfg["dados"]["raiz"]).resolve()
    cfg["gabarito"]["mapeamento"] = (RAIZ_REPO / cfg["gabarito"]["mapeamento"]).resolve()
    return cfg


def carregar_mapeamento(cfg: dict) -> dict:
    """Carrega mapeamento-eventos.yaml (caminho vem de cfg['gabarito']['mapeamento'])."""
    return yaml.safe_load(Path(cfg["gabarito"]["mapeamento"]).read_text(encoding="utf-8"))
