#!/usr/bin/env python3
"""Indexa TODOS os .geojson/.kml/.kmz de uma pasta (e subpastas) de uma
vez, usando os mesmos campos de busca (--rotulo/--logradouro/etc.) —
pra quando os dados estão espalhados em várias camadas/pastas, em vez
de rodar scripts/indexar_camadas.py um arquivo de cada vez.

Uso:
    python scripts/indexar_pasta_toda.py data/layers \\
        --rotulo setor quadra lote matricula transcricao \\
        --logradouro endereco \\
        --tipo imovel

Cada arquivo vira um --layer-id próprio (baseado no caminho relativo à
pasta), então rodar de novo atualiza cada um sem duplicar nem misturar
com os outros.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_geocoder_index import DEFAULT_DB  # noqa: E402
from indexar_camadas import indexar  # noqa: E402

_EXTENSOES = (".geojson", ".kml", ".kmz")


def _layer_id_para(caminho_relativo: Path) -> str:
    partes = caminho_relativo.with_suffix("").parts
    return "/".join(partes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pasta", type=Path, help="Pasta com as camadas (ex: data/layers)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Caminho do banco de busca")
    parser.add_argument("--tipo", default="imovel", help="Valor da coluna 'tipo' pra estes registros (padrão: imovel)")
    parser.add_argument(
        "--rotulo",
        nargs="+",
        required=True,
        metavar="PROPRIEDADE",
        help="Propriedades da feature usadas como texto pesquisável (ex: setor quadra lote matricula)",
    )
    parser.add_argument("--logradouro", default=None, metavar="PROPRIEDADE")
    parser.add_argument("--bairro", default=None, metavar="PROPRIEDADE")
    parser.add_argument("--cidade", default=None, metavar="PROPRIEDADE")
    args = parser.parse_args()

    if not args.pasta.exists():
        sys.exit(f"Pasta não encontrada: {args.pasta}")

    arquivos = sorted(
        p for p in args.pasta.rglob("*")
        if p.is_file() and p.suffix.lower() in _EXTENSOES and ".sigview_cache" not in p.parts
    )
    if not arquivos:
        sys.exit(f"Nenhum .geojson/.kml/.kmz encontrado em {args.pasta}")

    total_inseridos = 0
    total_ignorados = 0
    for path in arquivos:
        layer_id = _layer_id_para(path.relative_to(args.pasta))
        try:
            inseridos, ignorados = indexar(
                path, args.db, layer_id, args.rotulo, args.tipo, args.logradouro, args.bairro, args.cidade
            )
        except Exception as exc:  # um arquivo com problema nao para o resto
            print(f"[ERRO] {path}: {exc}")
            continue
        print(f"{layer_id}: {inseridos} indexado(s)" + (f", {ignorados} ignorado(s)" if ignorados else ""))
        total_inseridos += inseridos
        total_ignorados += ignorados

    print(f"\nTotal: {total_inseridos} registro(s) indexado(s) em {len(arquivos)} arquivo(s).")
    if total_ignorados:
        print(f"({total_ignorados} feature(s) ignorada(s) no total, por não terem geometria válida)")


if __name__ == "__main__":
    main()
