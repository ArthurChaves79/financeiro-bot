#!/usr/bin/env python3
"""Converte um KML/KMZ pra GeoJSON — útil pra quem vai parar de usar o
Google Earth e quer migrar os dados existentes pro formato mais simples
e rápido que o SIG View usa.

Por padrão, cada <Folder> do KML vira um arquivo .geojson separado
(mesmo comportamento de camadas independentes que o KML já tinha no
painel) — assim você não perde a organização em grupos. Use
--tudo-junto se preferir um único arquivo com tudo misturado.

Uso:
    python scripts/converter_kml_para_geojson.py data/layers/Geo4RI.kml
    python scripts/converter_kml_para_geojson.py data/layers/Geo4RI.kml --saida data/layers --tudo-junto
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import kml as kml_module  # noqa: E402


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", sem_acento).strip("_")
    return slug or "camada"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("arquivo", type=Path, help="Arquivo .kml ou .kmz de entrada")
    parser.add_argument("--saida", type=Path, default=None, help="Pasta de saída (padrão: a mesma do arquivo de entrada)")
    parser.add_argument(
        "--tudo-junto",
        action="store_true",
        help="Gera um único .geojson com todas as features juntas, ignorando as pastas do KML",
    )
    args = parser.parse_args()

    if not args.arquivo.exists():
        sys.exit(f"Arquivo não encontrado: {args.arquivo}")

    suffix = args.arquivo.suffix.lower()
    if suffix == ".kml":
        grupos, network_links = kml_module.parse_kml_full(args.arquivo.read_bytes())
    elif suffix == ".kmz":
        grupos, network_links = kml_module.parse_kmz_full(args.arquivo.read_bytes())
    else:
        sys.exit(f"Formato não suportado: {suffix} (use .kml ou .kmz)")

    if network_links:
        total_links = sum(len(v) for v in network_links.values())
        print(f"[aviso] {total_links} <NetworkLink> encontrado(s) no arquivo — não são seguidos por este "
              "conversor (só converte o conteúdo que já está no próprio arquivo).")

    pasta_saida = args.saida or args.arquivo.parent
    pasta_saida.mkdir(parents=True, exist_ok=True)
    base_nome = args.arquivo.stem

    if args.tudo_junto:
        todas_features = []
        for _caminho, geojson in grupos:
            todas_features.extend(geojson.get("features", []))
        destino = pasta_saida / f"{base_nome}.geojson"
        destino.write_text(
            json.dumps({"type": "FeatureCollection", "features": todas_features}, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Gerado {destino} com {len(todas_features)} feature(s).")
        return

    gerados = 0
    for caminho, geojson in grupos:
        features = geojson.get("features", [])
        if not features:
            continue
        sufixo = "_" + "_".join(_slug(p) for p in caminho) if caminho else ""
        destino = pasta_saida / f"{base_nome}{sufixo}.geojson"
        destino.write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")
        nome_pasta = " / ".join(caminho) if caminho else "(sem pasta)"
        print(f"Gerado {destino.name} — {nome_pasta} — {len(features)} feature(s)")
        gerados += 1

    print(f"\n{gerados} arquivo(s) .geojson gerado(s) em {pasta_saida}")
    print("Cada um vira uma camada própria no painel — pode apagar o .kml original quando conferir que está tudo certo.")


if __name__ == "__main__":
    main()
