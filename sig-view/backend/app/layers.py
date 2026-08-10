"""Descoberta e leitura das camadas (layers).

As camadas ficam em uma pasta que pode estar na rede local
(compartilhamento SMB/NFS montado no SO, ou sincronizada por outro
processo). O backend só lê o que encontrar ali — adicionar uma camada é
simplesmente colocar um novo arquivo na pasta.

Formatos suportados: `.geojson` (nativo) e `.kml` / `.kmz` (exportados do
Google Earth / Google My Maps — convertidos para GeoJSON na hora de
servir).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import kml as kml_module
from .config import settings

# Ordem de preferência quando há mais de um arquivo com o mesmo nome
# (ex: "bairros.geojson" e "bairros.kml") — o primeiro que existir vence.
_SUPPORTED_EXTENSIONS = (".geojson", ".kml", ".kmz")


class LayerNotFound(FileNotFoundError):
    pass


class LayerReadError(ValueError):
    pass


def _safe_layer_path(name: str) -> Path:
    """Resolve o nome da camada para um arquivo dentro de layers_dir,
    impedindo path traversal (ex: "../../etc/passwd")."""
    layers_dir = settings.layers_dir.resolve()
    for ext in _SUPPORTED_EXTENSIONS:
        candidate = (layers_dir / f"{name}{ext}").resolve()
        if layers_dir not in candidate.parents and candidate != layers_dir:
            continue  # tentativa de escapar da pasta, ignora
        if candidate.is_file():
            return candidate
    raise LayerNotFound(name)


def list_layers() -> list[dict]:
    layers_dir = settings.layers_dir
    if not layers_dir.exists():
        return []

    result = []
    for path in sorted(layers_dir.iterdir()):
        if path.suffix.lower() in _SUPPORTED_EXTENSIONS and path.is_file():
            result.append(_layer_metadata(path))
    return result


def _layer_metadata(path: Path) -> dict:
    name = path.stem
    feature_count = None
    geometry_type = None
    try:
        geojson = _read_as_geojson(path)
        features = geojson.get("features", [])
        feature_count = len(features)
        if features:
            geometry_type = features[0].get("geometry", {}).get("type")
    except (json.JSONDecodeError, OSError, kml_module.KmlParseError):
        pass

    return {
        "id": name,
        "nome": name.replace("_", " ").replace("-", " ").title(),
        "formato": path.suffix.lstrip(".").lower(),
        "feature_count": feature_count,
        "geometry_type": geometry_type,
        "atualizado_em": path.stat().st_mtime,
    }


def get_layer(name: str) -> dict:
    path = _safe_layer_path(name)
    try:
        return _read_as_geojson(path)
    except kml_module.KmlParseError as exc:
        raise LayerReadError(str(exc)) from exc


def _read_as_geojson(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".geojson":
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    if suffix == ".kml":
        return kml_module.parse_kml_bytes(path.read_bytes())
    if suffix == ".kmz":
        return kml_module.parse_kmz_bytes(path.read_bytes())
    raise LayerReadError(f"Formato não suportado: {suffix}")
