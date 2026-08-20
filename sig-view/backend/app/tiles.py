"""Servidor de tiles embutido — lê direto de um arquivo `.mbtiles`
(que é só um banco SQLite) e serve pro MapLibre, sem precisar de nenhum
servidor externo (TileServer GL/Docker).

Um `.mbtiles` guarda os tiles numa tabela `tiles(zoom_level, tile_column,
tile_row, tile_data)` e metadados numa tabela `metadata(name, value)`.
Isso é o formato que o Planetiler (ou qualquer outra ferramenta de tiles)
gera — basta colocar o arquivo no caminho configurado
(`SIGVIEW_MBTILES_PATH`, ou ⚙ Configurações) que o SIG View passa a
servir o mapa sozinho.
"""
from __future__ import annotations

import gzip
import sqlite3

from .config import settings

_FORMATO_CONTENT_TYPE = {
    "pbf": "application/x-protobuf",
    "mvt": "application/x-protobuf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


class MbtilesUnavailable(RuntimeError):
    pass


class TileNotFound(RuntimeError):
    pass


def _connect() -> sqlite3.Connection:
    path = settings.mbtiles_path
    if not path.exists():
        raise MbtilesUnavailable(
            f"Arquivo de mapa não encontrado: {path}. "
            "Gere um .mbtiles (veja gerar_e_subir_mapa.bat) e configure o caminho em ⚙ Configurações."
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _metadata(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        rows = conn.execute("SELECT name, value FROM metadata").fetchall()
    except sqlite3.OperationalError as exc:
        raise MbtilesUnavailable(f"Arquivo .mbtiles inválido (sem tabela metadata): {exc}") from exc
    return {r["name"]: r["value"] for r in rows}


def get_metadata() -> dict[str, str]:
    conn = _connect()
    try:
        return _metadata(conn)
    finally:
        conn.close()


def get_tile(z: int, x: int, y: int) -> tuple[bytes, str]:
    """Devolve (bytes_do_tile_ja_descomprimido, content_type)."""
    conn = _connect()
    try:
        meta = _metadata(conn)
        formato = (meta.get("format") or "pbf").lower()
        content_type = _FORMATO_CONTENT_TYPE.get(formato, "application/octet-stream")

        # .mbtiles usa o esquema TMS (linha 0 = sul do mundo), mas o
        # padrão XYZ usado pelo MapLibre tem linha 0 = norte -> inverte.
        y_tms = (2**z - 1) - y
        if y_tms < 0:
            raise TileNotFound(f"{z}/{x}/{y}")

        row = conn.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
            (z, x, y_tms),
        ).fetchone()
        if row is None:
            raise TileNotFound(f"{z}/{x}/{y}")

        data = bytes(row["tile_data"])
        if data[:2] == b"\x1f\x8b":  # gzip magic bytes — comum em tiles vetoriais (.pbf)
            data = gzip.decompress(data)
        return data, content_type
    finally:
        conn.close()


def _bounds_center(meta: dict[str, str]) -> tuple[list[float] | None, list[float] | None]:
    bounds = None
    if meta.get("bounds"):
        try:
            valores = [float(v) for v in meta["bounds"].split(",")]
            if len(valores) == 4:
                bounds = valores
        except ValueError:
            pass

    center = None
    if meta.get("center"):
        try:
            valores = [float(v) for v in meta["center"].split(",")]
            if len(valores) >= 2:
                center = valores[:2]
        except ValueError:
            pass

    return bounds, center


def build_default_style() -> dict:
    """Monta um style.json básico (MapLibre) pro conteúdo do .mbtiles
    configurado: raster vira um estilo raster simples; vetorial (o caso
    comum, gerado pelo Planetiler no esquema OpenMapTiles) vira um
    estilo enxuto com ruas, água, quadras e limites administrativos —
    sem rótulos de texto nem ícones (dispensa fontes/sprites, mantendo
    tudo 100% autocontido)."""
    meta = get_metadata()
    formato = (meta.get("format") or "pbf").lower()
    bounds, center = _bounds_center(meta)
    minzoom = int(float(meta["minzoom"])) if meta.get("minzoom") else 0
    maxzoom = int(float(meta["maxzoom"])) if meta.get("maxzoom") else 14

    if formato in ("png", "jpg", "jpeg", "webp"):
        return _raster_style(bounds, center, minzoom, maxzoom)
    return _vector_style(bounds, center, minzoom, maxzoom)


def _raster_style(bounds, center, minzoom, maxzoom) -> dict:
    style = {
        "version": 8,
        "name": "SIG View (raster local)",
        "sources": {
            "base": {
                "type": "raster",
                "tiles": ["/tiles/{z}/{x}/{y}"],
                "tileSize": 256,
                "minzoom": minzoom,
                "maxzoom": maxzoom,
            }
        },
        "layers": [
            {"id": "background", "type": "background", "paint": {"background-color": "#101418"}},
            {"id": "base", "type": "raster", "source": "base"},
        ],
    }
    if bounds:
        style["sources"]["base"]["bounds"] = bounds
    if center:
        style["center"] = center
    return style


def _vector_style(bounds, center, minzoom, maxzoom) -> dict:
    source = {
        "type": "vector",
        "tiles": ["/tiles/{z}/{x}/{y}"],
        "minzoom": minzoom,
        "maxzoom": maxzoom,
    }
    if bounds:
        source["bounds"] = bounds

    style = {
        "version": 8,
        "name": "SIG View (vetorial local — OpenMapTiles)",
        "sources": {"openmaptiles": source},
        "layers": [
            {"id": "background", "type": "background", "paint": {"background-color": "#101418"}},
            {
                "id": "landcover",
                "type": "fill",
                "source": "openmaptiles",
                "source-layer": "landcover",
                "paint": {"fill-color": "#182028", "fill-opacity": 0.6},
            },
            {
                "id": "landuse",
                "type": "fill",
                "source": "openmaptiles",
                "source-layer": "landuse",
                "paint": {"fill-color": "#1c2530", "fill-opacity": 0.5},
            },
            {
                "id": "water",
                "type": "fill",
                "source": "openmaptiles",
                "source-layer": "water",
                "paint": {"fill-color": "#12303f"},
            },
            {
                "id": "waterway",
                "type": "line",
                "source": "openmaptiles",
                "source-layer": "waterway",
                "paint": {"line-color": "#12303f", "line-width": 1},
            },
            {
                "id": "building",
                "type": "fill",
                "source": "openmaptiles",
                "source-layer": "building",
                "minzoom": 14,
                "paint": {"fill-color": "#232c36", "fill-outline-color": "#2c3644"},
            },
            {
                "id": "boundary",
                "type": "line",
                "source": "openmaptiles",
                "source-layer": "boundary",
                "filter": ["<=", ["get", "admin_level"], 6],
                "paint": {"line-color": "#5a6472", "line-width": 1, "line-dasharray": [2, 2]},
            },
            {
                "id": "road-minor",
                "type": "line",
                "source": "openmaptiles",
                "source-layer": "transportation",
                "filter": ["in", ["get", "class"], ["literal", ["minor", "service", "track", "path"]]],
                "paint": {"line-color": "#3a4552", "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.5, 18, 3]},
            },
            {
                "id": "road-major",
                "type": "line",
                "source": "openmaptiles",
                "source-layer": "transportation",
                "filter": [
                    "in",
                    ["get", "class"],
                    ["literal", ["primary", "secondary", "tertiary", "trunk", "motorway"]],
                ],
                "layout": {"line-cap": "round", "line-join": "round"},
                "paint": {
                    "line-color": "#8fa3bf",
                    "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.6, 12, 1.6, 18, 8],
                },
            },
            {
                "id": "rail",
                "type": "line",
                "source": "openmaptiles",
                "source-layer": "transportation",
                "filter": ["==", ["get", "class"], "rail"],
                "paint": {"line-color": "#5a6472", "line-width": 1},
            },
        ],
    }
    if center:
        style["center"] = center
    return style
