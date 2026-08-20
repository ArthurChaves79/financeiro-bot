#!/usr/bin/env python3
"""Constrói (ou reconstrói) o índice SQLite/FTS5 usado na busca.

Lê um CSV de endereços e gera `data/geocoder.db`. O CSV precisa ter (pelo
menos) estas colunas — os nomes podem ser remapeados com --map:

    tipo,logradouro,bairro,cidade,cep,lat,lon

  tipo: "endereco", "bairro" ou "cep"

Fontes sugeridas para popular o CSV de São Paulo:
  - GeoSampa (geosampa.prefeitura.sp.gov.br) — logradouros e bairros da
    capital, dados abertos, atualizados periodicamente.
  - IBGE CNEFE (Cadastro Nacional de Endereços para Fins Estatísticos) —
    cobre o estado inteiro.
  - Base de CEPs dos Correios / e-SIC, para os municípios do interior.

Uso:
    python scripts/build_geocoder_index.py caminho/para/enderecos.csv
    python scripts/build_geocoder_index.py enderecos.csv --db ../data/geocoder.db
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "geocoder.db"

REQUIRED_COLUMNS = ["tipo", "logradouro", "bairro", "cidade", "cep", "lat", "lon"]

# Schema compartilhado com scripts/indexar_camadas.py (que grava no
# mesmo banco os dados vinculados às camadas/polígonos) — por isso é
# todo "IF NOT EXISTS", idempotente independente de qual script roda
# primeiro.
SCHEMA = """
CREATE TABLE IF NOT EXISTS enderecos (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL,
    logradouro TEXT,
    bairro TEXT,
    cidade TEXT,
    cep TEXT,
    rotulo TEXT,     -- texto extra pesquisável (ex: "num. contrib. 1234 — João da Silva")
    layer_id TEXT,   -- id da camada de origem, se este registro veio de uma camada vinculada
    lat REAL NOT NULL,
    lon REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_enderecos_cep ON enderecos(cep);
CREATE INDEX IF NOT EXISTS idx_enderecos_layer_id ON enderecos(layer_id);

CREATE VIRTUAL TABLE IF NOT EXISTS enderecos_fts USING fts5(
    logradouro, bairro, cidade, rotulo,
    content='enderecos', content_rowid='id',
    tokenize = "unicode61 remove_diacritics 2"
);

CREATE TRIGGER IF NOT EXISTS enderecos_ai AFTER INSERT ON enderecos BEGIN
    INSERT INTO enderecos_fts(rowid, logradouro, bairro, cidade, rotulo)
    VALUES (new.id, new.logradouro, new.bairro, new.cidade, new.rotulo);
END;
"""


def ensure_schema(db_path: Path) -> sqlite3.Connection:
    """Abre (criando se preciso) o banco com o schema compartilhado, sem
    apagar dados que já existam — usado por indexar_camadas.py, que
    complementa o índice em vez de reconstruí-lo do zero."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO enderecos_fts(enderecos_fts) VALUES('rebuild')")
    conn.commit()


def build(csv_path: Path, db_path: Path, column_map: dict[str, str]) -> int:
    """Reconstrói o índice de endereços DO ZERO (apaga o banco anterior,
    inclusive dados de camadas indexados por indexar_camadas.py — rode-o
    de novo depois se precisar deles de volta)."""
    if db_path.exists():
        db_path.unlink()

    conn = ensure_schema(db_path)

    count = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if column_map.get(c, c) not in reader.fieldnames]
        if missing:
            raise SystemExit(
                f"Colunas ausentes no CSV: {missing}. "
                f"Colunas encontradas: {reader.fieldnames}. Use --map para remapear."
            )

        rows = []
        for row in reader:
            def col(name: str) -> str:
                return (row.get(column_map.get(name, name)) or "").strip()

            try:
                lat = float(col("lat"))
                lon = float(col("lon"))
            except ValueError:
                continue  # ignora linhas sem coordenada válida

            rows.append(
                (
                    col("tipo") or "endereco",
                    col("logradouro") or None,
                    col("bairro") or None,
                    col("cidade") or None,
                    _format_cep(col("cep")),
                    lat,
                    lon,
                )
            )

        conn.executemany(
            """INSERT INTO enderecos (tipo, logradouro, bairro, cidade, cep, lat, lon)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        count = len(rows)

    conn.commit()
    rebuild_fts(conn)
    conn.close()
    return count


def _format_cep(raw: str) -> str | None:
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) != 8:
        return raw or None
    return f"{digits[:5]}-{digits[5:]}"


def parse_column_map(pairs: list[str]) -> dict[str, str]:
    result = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--map inválido: '{pair}' (use coluna_padrao=coluna_no_csv)")
        key, value = pair.split("=", 1)
        result[key] = value
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", type=Path, help="CSV de entrada com os endereços")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Caminho do banco SQLite de saída")
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="coluna_padrao=coluna_no_csv",
        help="Remapeia nomes de coluna, ex: --map cidade=municipio",
    )
    args = parser.parse_args()

    if not args.csv_path.exists():
        sys.exit(f"Arquivo não encontrado: {args.csv_path}")

    column_map = parse_column_map(args.map)
    count = build(args.csv_path, args.db, column_map)
    print(f"Índice construído em {args.db} com {count} registros.")


if __name__ == "__main__":
    main()
