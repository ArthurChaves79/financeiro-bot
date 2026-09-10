#!/usr/bin/env python3
"""Job de atualização periódica das camadas e do índice de busca.

Pensado para ser agendado (cron, Agendador de Tarefas do Windows, ou um
serviço systemd timer) rodando num servidor da rede local — não no PC de
quem usa o mapa. Ele deixa os arquivos prontos (GeoJSON das camadas +
geocoder.db) na pasta compartilhada que o backend do SIG View lê.

Este script é um ESQUELETO: os endpoints exatos de download variam
conforme a fonte de dados que você configurar (GeoSampa, IBGE, um WFS
próprio da prefeitura etc.). Implemente `fetch_new_data()` com a
requisição real; o resto (log, atualização atômica dos arquivos) já
funciona.

Exemplo de agendamento (Linux, roda toda madrugada às 3h):
    0 3 * * *  /caminho/venv/bin/python /caminho/sig-view/backend/scripts/update_layers_job.py

Exemplo systemd timer: ver update_layers_job.service.example / .timer.example
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sig-view.update")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LAYERS_DIR = DATA_DIR / "layers"


def fetch_new_data(tmp_dir: Path) -> None:
    """Baixe/gere aqui os arquivos GeoJSON atualizados dentro de tmp_dir.

    TODO: implementar a chamada real, por exemplo:
      - requisição a um serviço WFS/REST da prefeitura (GeoSampa)
      - download de um extrato OSM (Geofabrik) + conversão para GeoJSON
        com uma ferramenta como ogr2ogr (GDAL) ou osmium
      - leitura de um export que já cai periodicamente numa pasta de rede

    Por enquanto isso é um no-op para não quebrar quem só clonou o
    projeto sem configurar uma fonte de dados ainda.
    """
    log.info("fetch_new_data() ainda não está implementado — configure a fonte real de dados.")


def publish_atomically(tmp_dir: Path) -> None:
    """Move os arquivos novos para LAYERS_DIR de forma atômica, evitando
    que o frontend leia um arquivo pela metade durante a atualização."""
    files = list(tmp_dir.glob("*.geojson"))
    if not files:
        log.info("Nenhum arquivo novo gerado, nada a publicar.")
        return

    LAYERS_DIR.mkdir(parents=True, exist_ok=True)
    for f in files:
        destino = LAYERS_DIR / f.name
        shutil.move(str(f), str(destino))
        log.info("Camada atualizada: %s", destino)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sigview-update-") as tmp:
        tmp_dir = Path(tmp)
        fetch_new_data(tmp_dir)
        publish_atomically(tmp_dir)
    log.info("Atualização concluída.")


if __name__ == "__main__":
    main()
