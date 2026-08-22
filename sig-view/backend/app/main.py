"""SIG View — backend FastAPI.

Serve a interface web (frontend/) e expõe a API usada por ela:
  GET  /api/config           -> configuração inicial do mapa (centro, bounds, fonte de tiles)
  GET  /api/search?q=...     -> busca por endereço, CEP ou bairro
  GET  /api/layers           -> lista de camadas disponíveis
  GET  /api/layers/{id}      -> GeoJSON de uma camada específica

Rode com:  uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from . import layers as layers_module
from . import search as search_module
from . import settings_store
from . import tiles as tiles_module
from .config import settings

settings_store.load_overrides_into_settings()

app = FastAPI(title="SIG View", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "PUT"],
    allow_headers=["*"],
)

# Camadas grandes (milhares de polígonos) viram um JSON de vários MB —
# comprimir a resposta reduz bastante o tamanho transferido (JSON
# comprime muito bem, é bastante texto repetido) e ajuda o "clique até
# aparecer no mapa" a ficar mais rápido, sem precisar de nada externo
# (vem pronto no Starlette).
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.get("/api/config")
def get_config() -> dict:
    return {
        "center": {"lat": settings.map_center_lat, "lon": settings.map_center_lon},
        "zoom": settings.map_zoom,
        "bounds": settings.map_bounds,
        "tile_source": {
            "url": settings.tile_source_url,
            "type": settings.tile_source_type,
        },
    }


@app.get("/api/search")
def api_search(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=50)) -> dict:
    try:
        results = search_module.search(q, limit=limit)
    except search_module.GeocoderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"query": q, "results": [r.to_dict() for r in results]}


@app.get("/api/layers")
def api_list_layers() -> dict:
    return {"layers": layers_module.list_layers()}


@app.get("/api/layers/{layer_id}")
def api_get_layer(layer_id: str) -> dict:
    try:
        return layers_module.get_layer(layer_id)
    except layers_module.LayerNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Camada '{layer_id}' não encontrada") from exc
    except layers_module.LayerReadError as exc:
        raise HTTPException(status_code=422, detail=f"Erro ao ler a camada '{layer_id}': {exc}") from exc


@app.get("/api/settings")
def api_get_settings() -> dict:
    return settings_store.get_editable_settings()


@app.put("/api/settings")
def api_update_settings(data: dict) -> dict:
    try:
        return settings_store.update_settings(data)
    except settings_store.InvalidSettings as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- Servidor de tiles embutido (lê direto de um .mbtiles) ------------------

@app.get("/tiles/style.json")
def tiles_style(request: Request) -> dict:
    try:
        return tiles_module.build_default_style(str(request.base_url))
    except tiles_module.MbtilesUnavailable as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/tiles/{z}/{x}/{y}")
def tile(z: int, x: int, y: int) -> Response:
    try:
        data, content_type = tiles_module.get_tile(z, x, y)
    except tiles_module.MbtilesUnavailable as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except tiles_module.TileNotFound:
        # Fora da área coberta pelo mapa — normal enquanto navega, não é erro.
        return Response(status_code=204)
    return Response(content=data, media_type=content_type)


# --- Frontend estático (index.html, css, js) --------------------------------
if getattr(sys, "frozen", False):
    # PyInstaller extrai os arquivos empacotados (--add-data) para uma
    # pasta temporária apontada por sys._MEIPASS.
    FRONTEND_DIR = Path(getattr(sys, "_MEIPASS")) / "frontend"
else:
    FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
