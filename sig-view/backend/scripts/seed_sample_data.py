#!/usr/bin/env python3
"""Popula dados de exemplo para rodar o SIG View sem precisar de nenhuma
base externa: um pequeno índice de busca (bairros/CEPs de exemplo da
capital paulista) e uma camada GeoJSON de exemplo.

Isso serve só para validar a instalação — substitua depois pelos dados
reais (GeoSampa/IBGE/Correios) usando build_geocoder_index.py.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from build_geocoder_index import build

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SAMPLE_ROWS = [
    # tipo, logradouro, bairro, cidade, cep, lat, lon
    ("endereco", "Avenida Paulista", "Bela Vista", "São Paulo", "01310-100", -23.5613, -46.6563),
    ("endereco", "Praça da Sé", "Sé", "São Paulo", "01001-000", -23.5505, -46.6333),
    ("endereco", "Avenida Brigadeiro Faria Lima", "Itaim Bibi", "São Paulo", "04538-132", -23.5877, -46.6829),
    ("bairro", None, "Pinheiros", "São Paulo", None, -23.5670, -46.7020),
    ("bairro", None, "Moema", "São Paulo", None, -23.6003, -46.6647),
    ("bairro", None, "Centro", "Campinas", None, -22.9068, -47.0632),
    ("endereco", "Rua XV de Novembro", "Centro", "Santos", "11010-151", -23.9608, -46.3336),
    ("bairro", None, "Centro Histórico", "Santos", None, -23.9345, -46.3292),
    ("endereco", "Avenida Rio Branco", "Centro", "São José dos Campos", "12210-000", -23.1791, -45.8872),
]


def write_sample_csv(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["tipo", "logradouro", "bairro", "cidade", "cep", "lat", "lon"])
        writer.writerows(SAMPLE_ROWS)


def write_sample_layer(path: Path) -> None:
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"nome": bairro, "cidade": cidade},
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
            }
            for (tipo, _log, bairro, cidade, _cep, lat, lon) in SAMPLE_ROWS
            if tipo == "bairro"
        ],
    }
    path.write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    layers_dir = DATA_DIR / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)

    csv_path = DATA_DIR / "_sample_enderecos.csv"
    write_sample_csv(csv_path)
    count = build(csv_path, DATA_DIR / "geocoder.db", column_map={})
    print(f"Índice de exemplo criado com {count} registros.")

    write_sample_layer(layers_dir / "bairros_exemplo.geojson")
    print(f"Camada de exemplo criada em {layers_dir / 'bairros_exemplo.geojson'}")


if __name__ == "__main__":
    main()
