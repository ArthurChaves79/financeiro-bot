#!/usr/bin/env python3
"""Diagnóstico rápido de um arquivo .mbtiles: mostra os metadados e
quantos tiles existem por nível de zoom, pra descobrir por que o mapa
não está aparecendo (arquivo vazio? só zoom alto? etc).

Uso:
    python scripts/diagnosticar_mbtiles.py
    python scripts/diagnosticar_mbtiles.py caminho\para\outro.mbtiles
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "mapa.mbtiles"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    print(f"Arquivo: {path}")

    if not path.exists():
        print("[ERRO] Esse arquivo não existe.")
        sys.exit(1)

    tamanho_mb = path.stat().st_size / (1024 * 1024)
    print(f"Tamanho: {tamanho_mb:.1f} MB")

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    print("\n=== metadata ===")
    try:
        for row in conn.execute("SELECT name, value FROM metadata ORDER BY name"):
            valor = row["value"]
            if len(valor) > 120:
                valor = valor[:120] + "... (cortado)"
            print(f"  {row['name']}: {valor}")
    except sqlite3.OperationalError as exc:
        print(f"  [ERRO] Não achou a tabela metadata: {exc}")

    print("\n=== quantidade de tiles por zoom ===")
    try:
        total = 0
        for row in conn.execute(
            "SELECT zoom_level, COUNT(*) AS n FROM tiles GROUP BY zoom_level ORDER BY zoom_level"
        ):
            print(f"  zoom {row['zoom_level']:>2}: {row['n']} tiles")
            total += row["n"]
        print(f"\n  TOTAL: {total} tiles")
        if total == 0:
            print("\n  [ATENCAO] Nao ha NENHUM tile gerado - o processamento do")
            print("  Planetiler nao produziu dados de mapa, mesmo o arquivo")
            print("  existindo (pode ter so a tabela de metadados).")
    except sqlite3.OperationalError as exc:
        print(f"  [ERRO] Não achou a tabela tiles: {exc}")
        sys.exit(1)

    print("\n=== índices na tabela tiles ===")
    indices = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='tiles'"
    ).fetchall()
    tem_indice_bom = False
    if not indices:
        print("  NENHUM índice encontrado!")
    for idx in indices:
        print(f"  {idx['name']}: {idx['sql']}")
        sql = (idx["sql"] or "").lower()
        if "zoom_level" in sql and "tile_column" in sql and "tile_row" in sql:
            tem_indice_bom = True
    if not tem_indice_bom:
        print("\n  [ATENCAO] Sem um indice cobrindo (zoom_level, tile_column, tile_row),")
        print("  cada tile pedido faz uma busca varrendo a tabela toda - e a causa")
        print("  mais provavel da lentidao. Rode:")
        print("  python scripts\\corrigir_indice_mbtiles.py")

    print("\n=== amostra de um tile ===")
    amostra = conn.execute(
        "SELECT zoom_level, tile_column, tile_row, LENGTH(tile_data) AS tam, tile_data "
        "FROM tiles ORDER BY zoom_level LIMIT 1"
    ).fetchone()
    if amostra:
        dados = bytes(amostra["tile_data"])
        eh_gzip = dados[:2] == b"\x1f\x8b"
        print(
            f"  zoom={amostra['zoom_level']} col={amostra['tile_column']} "
            f"row={amostra['tile_row']} tamanho={amostra['tam']} bytes "
            f"gzip={'sim' if eh_gzip else 'nao'}"
        )
    else:
        print("  (nenhum tile pra amostrar)")

    conn.close()


if __name__ == "__main__":
    main()
