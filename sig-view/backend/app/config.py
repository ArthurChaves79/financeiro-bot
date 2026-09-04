"""Configuração do SIG View.

Todas as opções podem ser definidas por variáveis de ambiente (prefixo
SIGVIEW_) ou num arquivo `.env` na raiz de `backend/`. Isso permite apontar
o programa para os recursos da rede local (servidor de tiles, pasta de
camadas, banco de geocoding) sem alterar código.
"""
from __future__ import annotations

import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Quando rodando como .exe empacotado (PyInstaller), os dados (config,
# banco de busca, camadas) precisam ficar ao lado do .exe — não dentro do
# pacote temporário que o PyInstaller extrai, que é somente leitura e
# descartado a cada execução. Em modo normal (python app/main.py, ou
# `python -m uvicorn ...`), continua sendo a pasta backend/.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SIGVIEW_", env_file=BASE_DIR / ".env", extra="ignore"
    )

    # Pasta com os arquivos GeoJSON de camadas. Pode ser um caminho local
    # ou um compartilhamento de rede montado no sistema operacional
    # (ex: /mnt/rede/sig-view/layers, \\servidor\sig-view\layers).
    layers_dir: Path = BASE_DIR / "data" / "layers"

    # Banco SQLite (FTS5) com o índice de endereços/CEP/bairros.
    geocoder_db: Path = BASE_DIR / "data" / "geocoder.db"

    # Arquivo .mbtiles com o mapa de ruas (gerado por gerar_e_subir_mapa.bat
    # ou qualquer outra ferramenta). Se existir nesse caminho, o próprio
    # SIG View serve os tiles (rotas /tiles/*), sem precisar de nenhum
    # servidor externo — é o que o "/tiles/style.json" (default de
    # tile_source_url abaixo) usa.
    mbtiles_path: Path = BASE_DIR / "data" / "mapa.mbtiles"

    # URL do servidor de tiles (ruas). Por padrão aponta pro servidor
    # embutido do próprio SIG View (usa o mbtiles_path acima). Também
    # aceita um servidor externo na rede local, ex TileServer GL:
    #  - um style.json do MapLibre (tiles vetoriais)
    #  - um template XYZ raster, ex: http://servidor:8080/tiles/{z}/{x}/{y}.png
    tile_source_url: str = "/tiles/style.json"
    tile_source_type: str = "vector"  # "vector" (style.json) ou "raster" (template XYZ)

    # Tema de cores do mapa embutido (vetorial) — ver app/tiles.py PALETAS.
    # Todos usam o mesmo .mbtiles, só mudam as cores; trocar não exige
    # gerar o mapa de novo.
    map_style: str = "claro"

    # Visão inicial do mapa: estado de São Paulo.
    map_center_lat: float = -22.19
    map_center_lon: float = -48.79
    map_zoom: int = 7
    # bounds: oeste, sul, leste, norte
    map_bounds: tuple[float, float, float, float] = (-53.11, -25.31, -44.16, -19.78)

    # Arquivo de rede (opcional) onde o TI/quem administra deixa o
    # número da versão mais nova disponível — ver app/versao.py. Vazio
    # (padrão) desliga a checagem, sem nenhum aviso.
    versao_check_path: Path | None = None

    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
