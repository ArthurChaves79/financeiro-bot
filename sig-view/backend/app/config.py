"""Configuração do SIG View.

Todas as opções podem ser definidas por variáveis de ambiente (prefixo
SIGVIEW_) ou num arquivo `.env` na raiz de `backend/`. Isso permite apontar
o programa para os recursos da rede local (servidor de tiles, pasta de
camadas, banco de geocoding) sem alterar código.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIGVIEW_", env_file=".env", extra="ignore")

    # Pasta com os arquivos GeoJSON de camadas. Pode ser um caminho local
    # ou um compartilhamento de rede montado no sistema operacional
    # (ex: /mnt/rede/sig-view/layers, \\servidor\sig-view\layers).
    layers_dir: Path = BASE_DIR / "data" / "layers"

    # Banco SQLite (FTS5) com o índice de endereços/CEP/bairros.
    geocoder_db: Path = BASE_DIR / "data" / "geocoder.db"

    # URL do servidor de tiles (ruas) na rede local. Aceita:
    #  - um style.json do MapLibre (tiles vetoriais, ex TileServer GL)
    #  - um template XYZ raster, ex: http://servidor:8080/tiles/{z}/{x}/{y}.png
    tile_source_url: str = "http://localhost:8080/styles/ruas-sp/style.json"
    tile_source_type: str = "vector"  # "vector" (style.json) ou "raster" (template XYZ)

    # Visão inicial do mapa: estado de São Paulo.
    map_center_lat: float = -22.19
    map_center_lon: float = -48.79
    map_zoom: int = 7
    # bounds: oeste, sul, leste, norte
    map_bounds: tuple[float, float, float, float] = (-53.11, -25.31, -44.16, -19.78)

    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
