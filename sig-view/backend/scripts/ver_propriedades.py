#!/usr/bin/env python3
"""Mostra os nomes de campo (propriedades) de uma camada — pra você
descobrir como se chamam as colunas (Setor, Quadra, Lote, Matrícula,
Endereço etc.) antes de rodar indexar_camadas.py, sem precisar abrir um
arquivo grande num editor de texto.

Funciona com .geojson, .kml e .kmz.

Uso:
    python scripts/ver_propriedades.py data/layers/imoveis.geojson
    python scripts/ver_propriedades.py data/layers/Loteamentos.kml --quantidade 5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import kml as kml_module  # noqa: E402


def carregar(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".geojson":
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix == ".kml":
        grupos, _ = kml_module.parse_kml_full(path.read_bytes())
    elif suffix == ".kmz":
        grupos, _ = kml_module.parse_kmz_full(path.read_bytes())
    else:
        raise SystemExit(f"Formato não suportado: {suffix}")

    # junta todos os grupos/pastas numa FeatureCollection só, só pra essa visualização
    features = []
    for _caminho, geojson in grupos:
        features.extend(geojson.get("features", []))
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("arquivo", type=Path, help="Camada .geojson, .kml ou .kmz")
    parser.add_argument("--quantidade", type=int, default=3, help="Quantas features mostrar (padrão: 3)")
    args = parser.parse_args()

    if not args.arquivo.exists():
        sys.exit(f"Arquivo não encontrado: {args.arquivo}")

    dados = carregar(args.arquivo)
    features = dados.get("features", [])
    print(f"Total de features: {len(features)}\n")

    if not features:
        print("(nenhuma feature encontrada)")
        return

    todos_os_campos: set[str] = set()
    for f in features:
        todos_os_campos.update((f.get("properties") or {}).keys())
    print(f"Campos encontrados (em todas as features): {sorted(todos_os_campos)}\n")

    print(f"=== Exemplo — {min(args.quantidade, len(features))} primeira(s) feature(s) ===\n")
    for f in features[: args.quantidade]:
        props = f.get("properties") or {}
        for chave, valor in props.items():
            print(f"  {chave}: {valor}")
        print()


if __name__ == "__main__":
    main()
