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
import threading
from pathlib import Path

from .config import BASE_DIR, settings

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


class FontNotFound(RuntimeError):
    pass


# Onde ficam os glyphs (fonte pros rótulos do mapa) — um download único
# (ver README) de arquivos .pbf pré-gerados, organizados em
# data/fonts/{fontstack}/{range}.pbf (mesmo layout que qualquer servidor
# de tiles usa). Sem esses arquivos, os rótulos simplesmente não
# aparecem — o resto do mapa funciona normal.
FONTS_DIR = BASE_DIR / "data" / "fonts"


def get_font_range(fontstack: str, intervalo: str) -> bytes:
    """Lê um arquivo de glyphs (.pbf) de FONTS_DIR, sem permitir escapar
    da pasta (path traversal) — mesmo esquema de proteção usado em
    layers.py pras camadas."""
    fonts_dir = FONTS_DIR.resolve()
    candidato = (fonts_dir / fontstack / f"{intervalo}.pbf").resolve()
    if fonts_dir not in candidato.parents:
        raise FontNotFound(f"{fontstack}/{intervalo}")
    if not candidato.is_file():
        raise FontNotFound(f"{fontstack}/{intervalo}")
    return candidato.read_bytes()


# FastAPI roda cada requisição síncrona numa thread de um pool — em vez
# de abrir uma conexão SQLite nova a cada tile (caro, principalmente com
# antivírus vigiando cada abertura de um arquivo de centenas de MB),
# cada thread mantém sua própria conexão aberta e reaproveita entre
# requisições. Reabre sozinho se o caminho configurado mudar (⚙ Configurações).
_local = threading.local()

# Metadados não mudam com o arquivo parado — cacheia por (caminho,
# data de modificação), assim continua correto se o .mbtiles for
# regenerado enquanto o programa está rodando.
_metadata_cache: tuple[Path, float, dict[str, str]] | None = None


def _get_connection() -> sqlite3.Connection:
    path = settings.mbtiles_path
    if not path.exists():
        raise MbtilesUnavailable(
            f"Arquivo de mapa não encontrado: {path}. "
            "Gere um .mbtiles (veja gerar_e_subir_mapa.bat) e configure o caminho em ⚙ Configurações."
        )

    conn: sqlite3.Connection | None = getattr(_local, "conn", None)
    conn_path: Path | None = getattr(_local, "conn_path", None)
    if conn is not None and conn_path == path:
        return conn

    if conn is not None:
        conn.close()

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _local.conn = conn
    _local.conn_path = path
    return conn


def _metadata(conn: sqlite3.Connection, path: Path) -> dict[str, str]:
    global _metadata_cache
    mtime = path.stat().st_mtime
    if _metadata_cache is not None and _metadata_cache[0] == path and _metadata_cache[1] == mtime:
        return _metadata_cache[2]

    try:
        rows = conn.execute("SELECT name, value FROM metadata").fetchall()
    except sqlite3.OperationalError as exc:
        raise MbtilesUnavailable(f"Arquivo .mbtiles inválido (sem tabela metadata): {exc}") from exc

    meta = {r["name"]: r["value"] for r in rows}
    _metadata_cache = (path, mtime, meta)
    return meta


def get_metadata() -> dict[str, str]:
    conn = _get_connection()
    return _metadata(conn, settings.mbtiles_path)


def get_tile(z: int, x: int, y: int) -> tuple[bytes, str]:
    """Devolve (bytes_do_tile_já_descomprimido, content_type)."""
    conn = _get_connection()
    meta = _metadata(conn, settings.mbtiles_path)
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


def build_default_style(base_url: str) -> dict:
    """Monta um style.json básico (MapLibre) pro conteúdo do .mbtiles
    configurado: raster vira um estilo raster simples; vetorial (o caso
    comum, gerado pelo Planetiler no esquema OpenMapTiles) vira um
    estilo com ruas, água, quadras, limites administrativos e rótulos
    de nome de rua/bairro/cidade (aparecem conforme se aproxima —
    exatamente os dados que o .mbtiles já tem, não precisa gerar de
    novo). O tema de cores usado é o configurado em `settings.map_style`
    (⚙ Configurações) — ver PALETAS abaixo.

    `base_url` (ex: "http://localhost:8000/") é usado pra montar a URL
    dos tiles e das fontes (glyphs) **completa** (com http://host:porta),
    não só o caminho relativo — janelas embutidas tipo pywebview/WebView2
    processam os tiles em Web Workers que, em alguns casos, não
    conseguem resolver URLs relativas e falham silenciosamente.
    """
    meta = get_metadata()
    formato = (meta.get("format") or "pbf").lower()
    bounds, center = _bounds_center(meta)
    minzoom = int(float(meta["minzoom"])) if meta.get("minzoom") else 0
    maxzoom = int(float(meta["maxzoom"])) if meta.get("maxzoom") else 14
    tiles_url = base_url.rstrip("/") + "/tiles/{z}/{x}/{y}"
    glyphs_url = base_url.rstrip("/") + "/fonts/{fontstack}/{range}.pbf"

    if formato in ("png", "jpg", "jpeg", "webp"):
        return _raster_style(tiles_url, bounds, center, minzoom, maxzoom)
    return _vector_style(tiles_url, glyphs_url, bounds, center, minzoom, maxzoom, settings.map_style)


def _raster_style(tiles_url, bounds, center, minzoom, maxzoom) -> dict:
    style = {
        "version": 8,
        "name": "SIG View (raster local)",
        "sources": {
            "base": {
                "type": "raster",
                "tiles": [tiles_url],
                "tileSize": 256,
                "minzoom": minzoom,
                "maxzoom": maxzoom,
            }
        },
        "layers": [
            {"id": "background", "type": "background", "paint": {"background-color": "#f7f6f2"}},
            {"id": "base", "type": "raster", "source": "base"},
        ],
    }
    if bounds:
        style["sources"]["base"]["bounds"] = bounds
    if center:
        style["center"] = center
    return style


# Temas de cor pro mapa vetorial — todos leem o mesmo .mbtiles, só
# mudam as cores/opacidades. Escolhido em ⚙ Configurações
# (settings.map_style); "claro" é o padrão de sempre. Adicionar um tema
# novo é só copiar um bloco e ajustar as cores, sem mexer em mais nada.
PALETAS = {
    "claro": {
        "nome": "Claro",
        "background": "#f7f6f2",
        "landcover": "#e9ecdf",
        "landuse": "#eae6d8",
        "water": "#a9cbe0",
        "building_fill": "#e3ded1",
        "building_outline": "#d2cab8",
        "boundary": "#a8a49a",
        "road_minor": "#d8d4c6",
        "road_major": "#c9a13b",
        "rail": "#9a9488",
        "label_text": "#2b2b2b",
        "label_halo": "#f7f6f2",
        "label_text_dim": "#6b6b6b",
    },
    "escuro": {
        "nome": "Escuro",
        "background": "#1b1e22",
        "landcover": "#20241f",
        "landuse": "#23211a",
        "water": "#163449",
        "building_fill": "#2b2924",
        "building_outline": "#38352c",
        "boundary": "#49463c",
        "road_minor": "#302e29",
        "road_major": "#c9a13b",
        "rail": "#49463c",
        "label_text": "#e7ecf1",
        "label_halo": "#1b1e22",
        "label_text_dim": "#9aa7b4",
    },
    "contraste": {
        "nome": "Alto contraste",
        "background": "#ffffff",
        "landcover": "#eef2ea",
        "landuse": "#f1efe4",
        "water": "#4f8fc0",
        "building_fill": "#dcd6c5",
        "building_outline": "#8f8060",
        "boundary": "#5a5646",
        "road_minor": "#9a9488",
        "road_major": "#c1272d",
        "rail": "#3a3a3a",
        "label_text": "#111111",
        "label_halo": "#ffffff",
        "label_text_dim": "#3a3a3a",
    },
    "minimalista": {
        "nome": "Minimalista",
        "background": "#fbfbfa",
        "landcover": "#f2f2f0",
        "landuse": "#f2f2f0",
        "water": "#cfd8dc",
        "building_fill": "#eceae5",
        "building_outline": "#dedad0",
        "boundary": "#c8c5bc",
        "road_minor": "#e6e3d9",
        "road_major": "#b8b2a1",
        "rail": "#d8d4c6",
        "label_text": "#4a4a4a",
        "label_halo": "#fbfbfa",
        "label_text_dim": "#8a8a8a",
    },
}

_FONTE_PADRAO = "Noto Sans"

# Causa raiz da tela em branco encontrada e corrigida: a rota /fonts/
# devolvia um erro 404 com corpo em JSON quando a fonte não estava
# baixada — o MapLibre esperava protobuf binário ali, e travava o
# processamento do estilo inteiro. Corrigido pra devolver vazio (204,
# igual à rota de tiles) nesse caso. Confirmado com o usuário: com
# "place" ligado e a fonte ainda não baixada, o mapa funciona normal
# (só sem o texto, como esperado). Religando os rótulos de rua também.
_ROTULO_PLACE_ATIVO = True
_ROTULO_ROAD_MAJOR_ATIVO = True
_ROTULO_ROAD_MINOR_ATIVO = True
_ALGUM_ROTULO_ATIVO = _ROTULO_PLACE_ATIVO or _ROTULO_ROAD_MAJOR_ATIVO or _ROTULO_ROAD_MINOR_ATIVO


def _vector_style(tiles_url, glyphs_url, bounds, center, minzoom, maxzoom, nome_paleta: str) -> dict:
    cores = PALETAS.get(nome_paleta, PALETAS["claro"])

    source = {
        "type": "vector",
        "tiles": [tiles_url],
        "minzoom": minzoom,
        "maxzoom": maxzoom,
    }
    if bounds:
        source["bounds"] = bounds

    def rotulo_texto(cor_dim=False):
        return {
            "text-color": cores["label_text_dim"] if cor_dim else cores["label_text"],
            "text-halo-color": cores["label_halo"],
            "text-halo-width": 1.2,
        }

    style = {
        "version": 8,
        "name": f"SIG View ({cores['nome']} — OpenMapTiles)",
        "sources": {"openmaptiles": source},
        "layers": [
            {"id": "background", "type": "background", "paint": {"background-color": cores["background"]}},
            {
                "id": "landcover",
                "type": "fill",
                "source": "openmaptiles",
                "source-layer": "landcover",
                "paint": {"fill-color": cores["landcover"], "fill-opacity": 0.6},
            },
            {
                "id": "landuse",
                "type": "fill",
                "source": "openmaptiles",
                "source-layer": "landuse",
                "paint": {"fill-color": cores["landuse"], "fill-opacity": 0.5},
            },
            {
                "id": "water",
                "type": "fill",
                "source": "openmaptiles",
                "source-layer": "water",
                "paint": {"fill-color": cores["water"]},
            },
            {
                "id": "waterway",
                "type": "line",
                "source": "openmaptiles",
                "source-layer": "waterway",
                "paint": {"line-color": cores["water"], "line-width": 1},
            },
            {
                "id": "building",
                "type": "fill",
                "source": "openmaptiles",
                "source-layer": "building",
                "minzoom": 14,
                "paint": {"fill-color": cores["building_fill"], "fill-outline-color": cores["building_outline"]},
            },
            {
                "id": "boundary",
                "type": "line",
                "source": "openmaptiles",
                "source-layer": "boundary",
                "filter": ["<=", ["get", "admin_level"], 6],
                "paint": {"line-color": cores["boundary"], "line-width": 1, "line-dasharray": [2, 2]},
            },
            {
                "id": "road-minor",
                "type": "line",
                "source": "openmaptiles",
                "source-layer": "transportation",
                "filter": ["in", ["get", "class"], ["literal", ["minor", "service", "track", "path"]]],
                "paint": {"line-color": cores["road_minor"], "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.5, 18, 3]},
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
                    "line-color": cores["road_major"],
                    "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.6, 12, 1.6, 18, 8],
                },
            },
            {
                "id": "rail",
                "type": "line",
                "source": "openmaptiles",
                "source-layer": "transportation",
                "filter": ["==", ["get", "class"], "rail"],
                "paint": {"line-color": cores["rail"], "line-width": 1},
            },
        ],
    }

    if _ALGUM_ROTULO_ATIVO:
        # Sem "glyphs" no estilo, qualquer camada com text-field é
        # inválida (a spec exige essa chave se algum layer usa texto) —
        # só entra quando pelo menos um rótulo está ligado.
        style["glyphs"] = glyphs_url

        novas_camadas = []

        if _ROTULO_PLACE_ATIVO:
            novas_camadas.append({
                "id": "place-label",
                "type": "symbol",
                "source": "openmaptiles",
                "source-layer": "place",
                "filter": ["in", ["get", "class"], ["literal", ["city", "town", "village", "suburb", "neighbourhood"]]],
                "layout": {
                    "text-field": ["coalesce", ["get", "name"], ["get", "name:latin"]],
                    "text-font": [_FONTE_PADRAO],
                    "text-size": ["interpolate", ["linear"], ["zoom"], 8, 11, 14, 15],
                    "text-transform": "uppercase",
                    "text-letter-spacing": 0.05,
                },
                "paint": rotulo_texto(),
            })

        if _ROTULO_ROAD_MAJOR_ATIVO:
            novas_camadas.append({
                "id": "road-major-label",
                "type": "symbol",
                "source": "openmaptiles",
                "source-layer": "transportation_name",
                "filter": [
                    "in",
                    ["get", "class"],
                    ["literal", ["primary", "secondary", "tertiary", "trunk", "motorway"]],
                ],
                "minzoom": 10,
                "layout": {
                    "symbol-placement": "line",
                    "text-field": ["coalesce", ["get", "name"], ["get", "name:latin"]],
                    "text-font": [_FONTE_PADRAO],
                    "text-size": ["interpolate", ["linear"], ["zoom"], 10, 10, 16, 13],
                },
                "paint": rotulo_texto(),
            })

        if _ROTULO_ROAD_MINOR_ATIVO:
            novas_camadas.append({
                "id": "road-minor-label",
                "type": "symbol",
                "source": "openmaptiles",
                "source-layer": "transportation_name",
                "filter": ["in", ["get", "class"], ["literal", ["minor", "service"]]],
                "minzoom": 14,
                "layout": {
                    "symbol-placement": "line",
                    "text-field": ["coalesce", ["get", "name"], ["get", "name:latin"]],
                    "text-font": [_FONTE_PADRAO],
                    "text-size": 11,
                },
                "paint": rotulo_texto(cor_dim=True),
            })

        style["layers"].extend(novas_camadas)

    if center:
        style["center"] = center
    return style
