#!/usr/bin/env python3
"""Garante que a tabela `tiles` do .mbtiles tem um índice em
(zoom_level, tile_column, tile_row) — sem ele, cada tile pedido faz uma
busca varrendo a tabela inteira, o que fica bem lento com muitos tiles
(dezenas/centenas de milhares).

Idempotente: se o índice já existir, não faz nada.

Uso:
    python scripts/corrigir_indice_mbtiles.py
    python scripts/corrigir_indice_mbtiles.py caminho\\para\\outro.mbtiles
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "mapa.mbtiles"


def tem_indice_adequado(conn: sqlite3.Connection) -> bool:
    rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='tiles'"
    ).fetchall()
    for (sql,) in rows:
        sql = (sql or "").lower()
        if "zoom_level" in sql and "tile_column" in sql and "tile_row" in sql:
            return True
    return False


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    if not path.exists():
        sys.exit(f"Arquivo não encontrado: {path}")

    print(f"Arquivo: {path}")
    conn = sqlite3.connect(path)  # leitura E escrita, pra poder criar o índice

    if tem_indice_adequado(conn):
        print("Já existe um índice adequado — nada a fazer.")
        conn.close()
        return

    print("Criando índice em (zoom_level, tile_column, tile_row)...")
    print("Isso pode demorar um pouco num arquivo grande, só dessa vez.")
    inicio = time.time()
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS tile_index ON tiles (zoom_level, tile_column, tile_row)"
    )
    conn.commit()
    duracao = time.time() - inicio
    print(f"Pronto em {duracao:.1f}s. O mapa deve carregar bem mais rápido agora.")
    conn.close()


if __name__ == "__main__":
    main()
