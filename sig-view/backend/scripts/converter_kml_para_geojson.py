#!/usr/bin/env python3
"""Converte um KML/KMZ pra GeoJSON — útil pra quem vai parar de usar o
Google Earth e quer migrar os dados existentes pro formato mais simples
e rápido que o SIG View usa.

Por padrão, cada <Folder> do KML vira uma SUBPASTA de verdade em disco
(ex: "Encerrados/2020/Geo4RI.geojson"), espelhando a mesma organização
em pastas que você já tinha no KML — o SIG View mostra pastas de disco
no painel do mesmo jeito que mostrava as <Folder> do KML, então você
não perde a árvore organizada ao converter. Use --tudo-junto se
preferir um único arquivo com tudo misturado, sem pastas.

Uso:
    python scripts/converter_kml_para_geojson.py data/layers/Geo4RI.kml
    python scripts/converter_kml_para_geojson.py data/layers/Geo4RI.kml --saida data/layers --tudo-junto
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import kml as kml_module  # noqa: E402

_CARACTERES_INVALIDOS_WINDOWS = re.compile(r'[<>:"/\\|?*]')


def _nome_pasta_seguro(nome: str) -> str:
    """Remove só os caracteres que o Windows não aceita em nome de
    pasta/arquivo — mantém o nome legível (acentos, espaços etc.),
    diferente de um "slug" agressivo."""
    limpo = _CARACTERES_INVALIDOS_WINDOWS.sub("_", nome).strip().rstrip(".")
    return limpo or "pasta"


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

        destino_dir = pasta_saida
        for parte in caminho:
            destino_dir = destino_dir / _nome_pasta_seguro(parte)
        destino_dir.mkdir(parents=True, exist_ok=True)

        destino = destino_dir / f"{base_nome}.geojson"
        destino.write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")
        nome_pasta = " / ".join(caminho) if caminho else "(sem pasta)"
        print(f"Gerado {destino.relative_to(pasta_saida)} — {nome_pasta} — {len(features)} feature(s)")
        gerados += 1

    print(f"\n{gerados} arquivo(s) .geojson gerado(s) em {pasta_saida}, organizados nas mesmas pastas do KML.")
    print("Pode apagar o .kml original quando conferir que está tudo certo no painel.")


if __name__ == "__main__":
    main()
