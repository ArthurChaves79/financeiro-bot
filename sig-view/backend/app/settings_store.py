"""Persistência das configurações editáveis pela tela de Configurações.

O `.env` continua definindo os valores padrão/iniciais (bom para quem
prefere configurar por arquivo, ex: instalação automatizada). Já as
alterações feitas pela interface do programa (aba Configurações) são
salvas em `data/config.json`, que é lido por cima do `.env` na próxima
vez que o programa abre — e aplicado imediatamente em memória quando
salvo, sem precisar reiniciar.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import BASE_DIR, settings

CONFIG_FILE = BASE_DIR / "data" / "config.json"

# Campos que a tela de Configurações pode alterar.
EDITABLE_FIELDS = {
    "layers_dir": Path,
    "geocoder_db": Path,
    "tile_source_url": str,
    "tile_source_type": str,
}


def load_overrides_into_settings() -> None:
    """Lê data/config.json (se existir) e aplica por cima dos valores
    atuais de `settings`. Chamado uma vez, na subida do programa."""
    if not CONFIG_FILE.exists():
        return
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    _apply(data)


def get_editable_settings() -> dict[str, Any]:
    return {
        "layers_dir": str(settings.layers_dir),
        "geocoder_db": str(settings.geocoder_db),
        "tile_source_url": settings.tile_source_url,
        "tile_source_type": settings.tile_source_type,
    }


class InvalidSettings(ValueError):
    pass


def update_settings(data: dict[str, Any]) -> dict[str, Any]:
    """Valida, aplica em memória e persiste as configurações editáveis."""
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        raise InvalidSettings(f"Campos desconhecidos: {sorted(unknown)}")

    if "tile_source_type" in data and data["tile_source_type"] not in ("vector", "raster"):
        raise InvalidSettings("tile_source_type deve ser 'vector' ou 'raster'")

    for field in ("layers_dir", "geocoder_db"):
        if field in data and not str(data[field]).strip():
            raise InvalidSettings(f"{field} não pode ficar vazio")

    for field in ("tile_source_url",):
        if field in data and not str(data[field]).strip():
            raise InvalidSettings(f"{field} não pode ficar vazio")

    _apply(data)

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    current = get_editable_settings()
    CONFIG_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current


def _apply(data: dict[str, Any]) -> None:
    for field, cast in EDITABLE_FIELDS.items():
        if field in data and data[field] is not None:
            setattr(settings, field, cast(data[field]))
