#!/usr/bin/env python3
"""Reduz o tamanho dos .geojson já convertidos, arredondando a precisão
das coordenadas — Google Earth/QGIS costumam exportar com 14-15 casas
decimais, mas 7 casas já dão ~1cm de precisão no chão (muito mais do que
precisa pra desenhar um lote), então o resto é peso morto: mais bytes pra
ler do disco, mais bytes pra mandar pro navegador, mais bytes pro
MapLibre processar. Isso soma com o GZipMiddleware (item 1) — arquivo
menor + resposta comprimida = "clique até aparecer no mapa" bem mais
rápido em camadas com muitos polígonos.

Não mexe em nada além das coordenadas: propriedades, estrutura de
pastas e o próprio nome do arquivo continuam iguais. É seguro rodar de
novo em cima de um arquivo já compactado (não perde precisão de novo,
só confirma que já está no tamanho certo).

Uso:
    python scripts/compactar_camadas.py data/layers
    python scripts/compactar_camadas.py data/layers --casas 6 --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_CASAS_PADRAO = 7


def _arredondar(coords, casas: int):
    """Percorre a estrutura de coordenadas do GeoJSON (que é uma lista
    aninhada em profundidade variável dependendo do tipo de geometria —
    Point, LineString, Polygon, MultiPolygon etc.) e arredonda os
    números, recursivamente, sem depender de saber a profundidade."""
    if isinstance(coords, (int, float)):
        return round(coords, casas)
    return [_arredondar(item, casas) for item in coords]


def compactar_arquivo(path: Path, casas: int, dry_run: bool) -> tuple[int, int]:
    tamanho_antes = path.stat().st_size
    geojson = json.loads(path.read_text(encoding="utf-8"))

    for feature in geojson.get("features", []):
        geometry = feature.get("geometry")
        if not geometry or "coordinates" not in geometry:
            continue
        geometry["coordinates"] = _arredondar(geometry["coordinates"], casas)

    texto_novo = json.dumps(geojson, ensure_ascii=False, separators=(",", ":"))
    tamanho_depois = len(texto_novo.encode("utf-8"))

    if not dry_run:
        path.write_text(texto_novo, encoding="utf-8")

    return tamanho_antes, tamanho_depois


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pasta", type=Path, help="Pasta com as camadas .geojson (ex: data/layers)")
    parser.add_argument("--casas", type=int, default=_CASAS_PADRAO, help=f"Casas decimais a manter (padrão: {_CASAS_PADRAO}, ~1cm de precisão)")
    parser.add_argument("--dry-run", action="store_true", help="Só mostra quanto reduziria, sem alterar os arquivos")
    args = parser.parse_args()

    if not args.pasta.exists():
        sys.exit(f"Pasta não encontrada: {args.pasta}")

    arquivos = sorted(
        p for p in args.pasta.rglob("*.geojson")
        if ".sigview_cache" not in p.parts
    )
    if not arquivos:
        sys.exit(f"Nenhum .geojson encontrado em {args.pasta}")

    total_antes = 0
    total_depois = 0
    for path in arquivos:
        try:
            antes, depois = compactar_arquivo(path, args.casas, args.dry_run)
        except Exception as exc:  # um arquivo com problema nao para o resto
            print(f"[ERRO] {path}: {exc}")
            continue
        reducao = 100 * (1 - depois / antes) if antes else 0
        print(f"{path.relative_to(args.pasta)}: {antes/1024:.0f} KB -> {depois/1024:.0f} KB ({reducao:.0f}% menor)")
        total_antes += antes
        total_depois += depois

    reducao_total = 100 * (1 - total_depois / total_antes) if total_antes else 0
    verbo = "reduziria" if args.dry_run else "reduziu"
    print(f"\nTotal: {total_antes/1024/1024:.1f} MB -> {total_depois/1024/1024:.1f} MB "
          f"({verbo} {reducao_total:.0f}%) em {len(arquivos)} arquivo(s).")
    if args.dry_run:
        print("(--dry-run: nada foi alterado; rode sem essa opção pra aplicar de verdade)")


if __name__ == "__main__":
    main()
