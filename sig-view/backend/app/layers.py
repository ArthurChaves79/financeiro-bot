"""Descoberta e leitura das camadas (layers) GeoJSON.

As camadas ficam em uma pasta que pode estar na rede local
(compartilhamento SMB/NFS montado no SO, ou sincronizada por outro
processo). O backend só lê o que encontrar ali — adicionar uma camada é
simplesmente colocar um novo arquivo `.geojson` na pasta.
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import settings


class LayerNotFound(FileNotFoundError):
    pass


def _safe_layer_path(name: str) -> Path:
    """Resolve o nome da camada para um caminho dentro de layers_dir,
    impedindo path traversal (ex: "../../etc/passwd")."""
    layers_dir = settings.layers_dir.resolve()
    candidate = (layers_dir / f"{name}.geojson").resolve()
    if layers_dir not in candidate.parents and candidate != layers_dir:
        raise LayerNotFound(name)
    if not candidate.is_file():
        raise LayerNotFound(name)
    return candidate


def list_layers() -> list[dict]:
    layers_dir = settings.layers_dir
    if not layers_dir.exists():
        return []

    result = []
    for path in sorted(layers_dir.glob("*.geojson")):
        result.append(_layer_metadata(path))
    return result


def _layer_metadata(path: Path) -> dict:
    name = path.stem
    feature_count = None
    geometry_type = None
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        features = data.get("features", [])
        feature_count = len(features)
        if features:
            geometry_type = features[0].get("geometry", {}).get("type")
    except (json.JSONDecodeError, OSError):
        pass

    return {
        "id": name,
        "nome": name.replace("_", " ").replace("-", " ").title(),
        "feature_count": feature_count,
        "geometry_type": geometry_type,
        "atualizado_em": path.stat().st_mtime,
    }


def get_layer(name: str) -> dict:
    path = _safe_layer_path(name)
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)
