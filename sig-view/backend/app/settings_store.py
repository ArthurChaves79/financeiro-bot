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

from . import tiles as tiles_module
from .backup_util import backup_rotativo
from .config import BASE_DIR, settings

CONFIG_FILE = BASE_DIR / "data" / "config.json"
BACKUPS_DIR = BASE_DIR / "data" / "backups"

# Pasta onde o usuário pode colocar um ou mais .mbtiles prontos (ex:
# ruas.mbtiles, satelite.mbtiles) pra escolher entre eles direto pela
# tela de Configurações, em vez de digitar o caminho completo.
MAPS_DIR = BASE_DIR / "data" / "maps"

# Campos que a tela de Configurações pode alterar.
EDITABLE_FIELDS = {
    "layers_dir": Path,
    "geocoder_db": Path,
    "mbtiles_path": Path,
    "tile_source_url": str,
    "tile_source_type": str,
    "map_style": str,
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


def list_available_maps() -> list[dict[str, str]]:
    """Lista os .mbtiles prontos pra escolher (pasta data/maps/) — cada
    um vira uma opção no dropdown de Configurações, com o nome do
    arquivo (sem extensão) como rótulo. Inclui também o mapa
    atualmente configurado, mesmo que esteja fora dessa pasta (ex: um
    caminho de rede digitado manualmente antes desse recurso existir),
    pra não "sumir" a seleção atual do dropdown."""
    mapas: list[dict[str, str]] = []
    vistos: set[str] = set()

    if MAPS_DIR.is_dir():
        for arquivo in sorted(MAPS_DIR.glob("*.mbtiles")):
            caminho = str(arquivo.resolve())
            mapas.append({"nome": arquivo.stem, "caminho": caminho})
            vistos.add(caminho)

    atual = str(settings.mbtiles_path.resolve()) if str(settings.mbtiles_path) else ""
    if atual and atual not in vistos and Path(atual).exists():
        mapas.append({"nome": f"{Path(atual).stem} (personalizado)", "caminho": atual})

    return mapas


def list_available_map_styles() -> list[dict[str, str]]:
    """Temas de cor disponíveis pro mapa vetorial embutido (ver
    app/tiles.py PALETAS) — todos usam o mesmo .mbtiles, só mudam as
    cores, então aparecem sempre, sem depender de nenhum arquivo extra."""
    return [{"id": chave, "nome": paleta["nome"]} for chave, paleta in tiles_module.PALETAS.items()]


def get_editable_settings() -> dict[str, Any]:
    return {
        "layers_dir": str(settings.layers_dir),
        "geocoder_db": str(settings.geocoder_db),
        "mbtiles_path": str(settings.mbtiles_path),
        "tile_source_url": settings.tile_source_url,
        "tile_source_type": settings.tile_source_type,
        "map_style": settings.map_style,
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

    if "map_style" in data and data["map_style"] not in tiles_module.PALETAS:
        raise InvalidSettings(f"map_style deve ser um de: {sorted(tiles_module.PALETAS)}")

    for field in ("layers_dir", "geocoder_db", "mbtiles_path"):
        if field in data and not str(data[field]).strip():
            raise InvalidSettings(f"{field} não pode ficar vazio")

    for field in ("tile_source_url",):
        if field in data and not str(data[field]).strip():
            raise InvalidSettings(f"{field} não pode ficar vazio")

    _apply(data)

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    backup_rotativo(CONFIG_FILE, BACKUPS_DIR)  # guarda a versão anterior antes de sobrescrever
    current = get_editable_settings()
    CONFIG_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current


def _apply(data: dict[str, Any]) -> None:
    for field, cast in EDITABLE_FIELDS.items():
        if field in data and data[field] is not None:
            setattr(settings, field, cast(data[field]))
