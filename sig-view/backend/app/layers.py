"""Descoberta e leitura das camadas (layers).

As camadas ficam numa pasta local (ou de rede, se você configurar
assim) — o backend só lê o que encontrar ali. Formatos suportados:
`.geojson` (nativo) e `.kml`/`.kmz` (convertidos na hora de servir).

Um `.kml` pode ter `<Folder>` aninhadas — a listagem devolve uma árvore
(igual ao painel "Locais" do Google Earth): cada pasta pode ter sua
própria camada de pontos/linhas/polígonos E/OU conter outras pastas
dentro, expansíveis independentemente.
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


def _grupos_do_arquivo(path: Path) -> list[tuple[tuple[str, ...], dict]]:
    """Devolve [(caminho_da_pasta, geojson), ...] para um arquivo. Para
    .geojson é sempre 1 grupo (caminho ()); para .kml/.kmz respeita as
    <Folder> encontradas (inclusive aninhadas)."""
    suffix = path.suffix.lower()
    if suffix == ".geojson":
        with path.open("r", encoding="utf-8") as fh:
            return [((), json.load(fh))]
    if suffix == ".kml":
        return kml_module.parse_kml_grouped(path.read_bytes())
    if suffix == ".kmz":
        return kml_module.parse_kmz_grouped(path.read_bytes())
    raise LayerReadError(f"Formato não suportado: {suffix}")


def _layer_id(stem: str, caminho: tuple[str, ...]) -> str:
    if not caminho:
        return stem
    return f"{stem}{_GROUP_SEP}{'--'.join(_slug(p) for p in caminho)}"


def _nome_arquivo_exibicao(stem: str) -> str:
    return stem.replace("_", " ").replace("-", " ").title()


def _layer_info(layer_id: str, geojson: dict, formato: str, mtime: float) -> dict:
    features = geojson.get("features", [])
    return {
        "id": layer_id,
        "formato": formato,
        "feature_count": len(features),
        "geometry_type": features[0].get("geometry", {}).get("type") if features else None,
        "cor_padrao": cor_padrao_da_camada(layer_id),
        "atualizado_em": mtime,
    }


def _montar_arvore(stem: str, formato: str, mtime: float, grupos: list[tuple[tuple[str, ...], dict]]) -> dict | None:
    """Monta a árvore de nós (pastas expansíveis) a partir da lista plana
    de (caminho, geojson) devolvida pelo parser de KML."""
    por_caminho = {caminho: geojson for caminho, geojson in grupos}

    # Todo prefixo de todo caminho vira um nó (mesmo que essa pasta em si
    # não tenha placemarks diretos, só subpastas) — assim como no Google
    # Earth, uma pasta pode existir só como "container" de outras pastas.
    todos_caminhos: set[tuple[str, ...]] = {()}
    for caminho in por_caminho:
        for i in range(len(caminho) + 1):
            todos_caminhos.add(caminho[:i])

    filhos_de: dict[tuple[str, ...], list[tuple[str, ...]]] = {}
    for caminho in todos_caminhos:
        if not caminho:
            continue
        pai = caminho[:-1]
        filhos_de.setdefault(pai, []).append(caminho)
    for pai in filhos_de:
        filhos_de[pai].sort(key=lambda c: c[-1].lower())

    def construir_no(caminho: tuple[str, ...]) -> dict:
        layer_id = _layer_id(stem, caminho)
        nome = caminho[-1] if caminho else _nome_arquivo_exibicao(stem)
        geojson = por_caminho.get(caminho)
        camada = _layer_info(layer_id, geojson, formato, mtime) if geojson is not None else None
        criancas = [construir_no(filho) for filho in filhos_de.get(caminho, [])]
        return {"nome": nome, "camada": camada, "criancas": criancas}

    raiz = construir_no(())
    # Arquivo sem nenhuma <Folder>: vira um nó folha simples (sem seta de
    # expandir), igual ao comportamento de antes.
    if not raiz["criancas"]:
        return raiz
    return raiz


def list_layers() -> list[dict]:
    """Devolve a árvore de camadas disponíveis: um nó por arquivo, cada
    um podendo ter uma camada própria (```"camada"```) e/ou subpastas
    (```"criancas"```) — igual ao painel "Locais" do Google Earth."""
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

        formato = path.suffix.lstrip(".").lower()
        mtime = path.stat().st_mtime
        no = _montar_arvore(stem, formato, mtime, grupos)
        if no is not None:
            result.append(no)
    return result


def get_layer(layer_id: str) -> dict:
    if _GROUP_SEP in layer_id:
        stem, resto = layer_id.split(_GROUP_SEP, 1)
        slugs_pedidos = resto.split("--")
    else:
        stem, slugs_pedidos = layer_id, []

    path = _find_source_file(stem)
    if path is None:
        raise LayerNotFound(layer_id)

    try:
        grupos = _grupos_do_arquivo(path)
    except kml_module.KmlParseError as exc:
        raise LayerReadError(str(exc)) from exc

    if not slugs_pedidos:
        for caminho, geojson in grupos:
            if not caminho:
                return geojson
        raise LayerNotFound(layer_id)

    for caminho, geojson in grupos:
        if [_slug(p) for p in caminho] == slugs_pedidos:
            return geojson

    raise LayerNotFound(layer_id)
