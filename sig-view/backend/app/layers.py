"""Descoberta e leitura das camadas (layers).

As camadas ficam em uma pasta que pode estar na rede local
(compartilhamento SMB/NFS montado no SO, ou sincronizada por outro
processo). O backend só lê o que encontrar ali — adicionar uma camada é
simplesmente colocar um novo arquivo na pasta.

Formatos suportados: `.geojson` (nativo) e `.kml` / `.kmz` (exportados do
Google Earth / Google My Maps — convertidos para GeoJSON na hora de
servir). Um único arquivo `.kml` pode conter várias `<Folder>` — cada
uma vira uma camada própria, ligável separadamente no painel.
"""
from __future__ import annotations

import json
import re
import unicodedata
import zlib
from pathlib import Path

from . import kml as kml_module
from .config import settings

_SUPPORTED_EXTENSIONS = (".geojson", ".kml", ".kmz")

# Cores padrão usadas quando a camada (ou pasta do KML) não define a
# própria cor via <Style> — escolhidas por serem bem distinguíveis entre
# si sobre um mapa escuro.
_PALETA_CORES = [
    "#3fa9f5",  # azul
    "#f5a93f",  # laranja
    "#5fd576",  # verde
    "#e05fd5",  # magenta
    "#f5e03f",  # amarelo
    "#5fc9d5",  # ciano
    "#e0605f",  # vermelho
    "#9d6fe0",  # roxo
    "#d59a5f",  # marrom claro
    "#6f9de0",  # azul claro
]

_GROUP_SEP = "__grupo__"


class LayerNotFound(FileNotFoundError):
    pass


class LayerReadError(ValueError):
    pass


def cor_padrao_da_camada(layer_id: str) -> str:
    """Cor determinística por camada (mesma camada = mesma cor sempre,
    mesmo depois de reiniciar o programa)."""
    indice = zlib.crc32(layer_id.encode("utf-8")) % len(_PALETA_CORES)
    return _PALETA_CORES[indice]


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower()
    return slug or "camada"


def _find_source_file(stem: str) -> Path | None:
    """Acha o arquivo (.geojson/.kml/.kmz) correspondente ao stem dentro
    de layers_dir, sem permitir escapar da pasta (path traversal)."""
    layers_dir = settings.layers_dir.resolve()
    for ext in _SUPPORTED_EXTENSIONS:
        candidate = (layers_dir / f"{stem}{ext}").resolve()
        if layers_dir not in candidate.parents and candidate != layers_dir:
            continue
        if candidate.is_file():
            return candidate
    return None


def _grupos_do_arquivo(path: Path) -> list[tuple[str, dict]]:
    """Devolve [(nome_do_grupo, geojson), ...] para um arquivo. Para
    .geojson é sempre 1 grupo (nome ""); para .kml/.kmz respeita as
    <Folder> encontradas."""
    suffix = path.suffix.lower()
    if suffix == ".geojson":
        with path.open("r", encoding="utf-8") as fh:
            return [("", json.load(fh))]
    if suffix == ".kml":
        return kml_module.parse_kml_grouped(path.read_bytes())
    if suffix == ".kmz":
        return kml_module.parse_kmz_grouped(path.read_bytes())
    raise LayerReadError(f"Formato não suportado: {suffix}")


def _layer_id(stem: str, grupos: list[tuple[str, dict]], nome_grupo: str) -> str:
    if len(grupos) == 1 and nome_grupo == "":
        return stem  # arquivo sem pastas: camada única, id = nome do arquivo (compatível com antes)
    return f"{stem}{_GROUP_SEP}{_slug(nome_grupo)}"


def _nome_exibicao(stem: str, nome_grupo: str) -> str:
    base = stem.replace("_", " ").replace("-", " ").title()
    if not nome_grupo:
        return base
    return f"{base} — {nome_grupo}"


def list_layers() -> list[dict]:
    layers_dir = settings.layers_dir
    if not layers_dir.exists():
        return []

    result = []
    stems_vistos: set[str] = set()
    for path in sorted(layers_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            continue
        stem = path.stem
        if stem in stems_vistos:
            continue  # evita duplicar se existir ex: bairros.geojson E bairros.kml
        stems_vistos.add(stem)

        try:
            grupos = _grupos_do_arquivo(path)
        except (json.JSONDecodeError, OSError, kml_module.KmlParseError, LayerReadError):
            continue

        mtime = path.stat().st_mtime
        for nome_grupo, geojson in grupos:
            layer_id = _layer_id(stem, grupos, nome_grupo)
            features = geojson.get("features", [])
            result.append(
                {
                    "id": layer_id,
                    "nome": _nome_exibicao(stem, nome_grupo),
                    "formato": path.suffix.lstrip(".").lower(),
                    "feature_count": len(features),
                    "geometry_type": features[0].get("geometry", {}).get("type") if features else None,
                    "cor_padrao": cor_padrao_da_camada(layer_id),
                    "atualizado_em": mtime,
                }
            )
    return result


def get_layer(layer_id: str) -> dict:
    if _GROUP_SEP in layer_id:
        stem, slug_grupo = layer_id.split(_GROUP_SEP, 1)
    else:
        stem, slug_grupo = layer_id, None

    path = _find_source_file(stem)
    if path is None:
        raise LayerNotFound(layer_id)

    try:
        grupos = _grupos_do_arquivo(path)
    except kml_module.KmlParseError as exc:
        raise LayerReadError(str(exc)) from exc

    if slug_grupo is None:
        # id "simples": só é válido se o arquivo realmente tiver 1 grupo sem nome
        if len(grupos) == 1 and grupos[0][0] == "":
            return grupos[0][1]
        raise LayerNotFound(layer_id)

    for nome_grupo, geojson in grupos:
        if nome_grupo and _slug(nome_grupo) == slug_grupo:
            return geojson

    raise LayerNotFound(layer_id)
