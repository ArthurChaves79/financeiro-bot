#!/usr/bin/env python3
"""Constrói (ou reconstrói) o índice SQLite/FTS5 usado na busca.

Lê um CSV de endereços e gera `data/geocoder.db`. O CSV precisa ter (pelo
menos) estas colunas — os nomes podem ser remapeados com --map:

    tipo,logradouro,bairro,cidade,cep,lat,lon

  tipo: "endereco", "bairro" ou "cep"

Colunas opcionais (deixe de fora se não tiver): numero_par_ini,
numero_par_fim, numero_impar_ini, numero_impar_fim — faixa de
numeração (par/ímpar) do trecho de rua, usada pra achar o trecho certo
quando a busca inclui um número de porta (ex: "Rua Natal 974"). É o
que `scripts/converter_geopackage_geosampa.py` já preenche sozinho, a
partir do "Eixo de Logradouro" do GeoSampa.

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
import math
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

# Faixa de numeração (par/ímpar) do trecho de rua — vem do "Eixo de
# Logradouro" do GeoSampa (lg_ini_par/lg_fim_par/lg_ini_imp/lg_fim_imp),
# usada pra achar o trecho certo quando a busca inclui um número (ex:
# "Rua Natal 974"). Colunas novas, adicionadas numa tabela que já
# existia antes delas — por isso são ALTER TABLE, não fazem parte do
# CREATE TABLE acima (que só roda se a tabela ainda não existe).
_COLUNAS_FAIXA_NUMERACAO = [
    "numero_par_ini",
    "numero_par_fim",
    "numero_impar_ini",
    "numero_impar_fim",
]


def _migrar_colunas_faixa_numeracao(conn: sqlite3.Connection) -> None:
    colunas_existentes = {row[1] for row in conn.execute("PRAGMA table_info(enderecos)")}
    for coluna in _COLUNAS_FAIXA_NUMERACAO:
        if coluna not in colunas_existentes:
            conn.execute(f"ALTER TABLE enderecos ADD COLUMN {coluna} INTEGER")


def ensure_schema(db_path: Path) -> sqlite3.Connection:
    """Abre (criando se preciso) o banco com o schema compartilhado, sem
    apagar dados que já existam — usado por indexar_camadas.py, que
    complementa o índice em vez de reconstruí-lo do zero."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    _migrar_colunas_faixa_numeracao(conn)
    return conn


def rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO enderecos_fts(enderecos_fts) VALUES('rebuild')")
    conn.commit()


def _ler_linhas(csv_path: Path, column_map: dict[str, str]) -> tuple[list[tuple], int]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if column_map.get(c, c) not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(
                f"Colunas ausentes em {csv_path}: {missing}. "
                f"Colunas encontradas: {reader.fieldnames}. Use --map para remapear."
            )

        rows = []
        ignoradas = 0
        for row in reader:
            def col(name: str) -> str:
                return (row.get(column_map.get(name, name)) or "").strip()

            def col_int(name: str) -> int | None:
                # Colunas de faixa de numeração são opcionais — CSVs sem
                # elas (ex: um de bairros) simplesmente não têm a coluna,
                # e um valor que não seja um número inteiro válido vira
                # NULL em vez de dar erro (não são essenciais pra achar
                # o registro, só pra refinar a busca por número).
                bruto = col(name)
                try:
                    return int(float(bruto)) if bruto else None
                except ValueError:
                    return None

            try:
                lat = float(col("lat"))
                lon = float(col("lon"))
            except ValueError:
                ignoradas += 1
                continue  # ignora linhas sem coordenada válida

            # float() aceita "nan"/"inf" sem erro, mas o SQLite trata NaN
            # como se fosse NULL internamente — sem este checa, uma única
            # linha com coordenada inválida (geometria degenerada na
            # origem, ex: um ponto (0,0) usado como "sem dado") derrubava
            # a importação inteira com "NOT NULL constraint failed".
            if not (math.isfinite(lat) and math.isfinite(lon)):
                ignoradas += 1
                continue

            rows.append(
                (
                    col("tipo") or "endereco",
                    col("logradouro") or None,
                    col("bairro") or None,
                    col("cidade") or None,
                    _format_cep(col("cep")),
                    lat,
                    lon,
                    col_int("numero_par_ini"),
                    col_int("numero_par_fim"),
                    col_int("numero_impar_ini"),
                    col_int("numero_impar_fim"),
                )
            )
        return rows, ignoradas


def build(csv_paths: Path | list[Path], db_path: Path, column_map: dict[str, str]) -> int:
    """Reconstrói o índice de endereços DO ZERO (apaga o banco anterior,
    inclusive dados de camadas indexados por indexar_camadas.py — rode-o
    de novo depois se precisar deles de volta). Aceita mais de um CSV de
    uma vez (ex: um de ruas e outro de bairros) — todos entram no mesmo
    índice, sem um sobrescrever o outro."""
    if isinstance(csv_paths, Path):
        csv_paths = [csv_paths]

    # Lê e valida TODOS os CSVs antes de tocar no banco existente — se
    # algum caminho estiver errado/vazio (aponta pra um arquivo sem
    # linha aproveitável), aborta sem apagar um índice que já
    # funcionava. Rodar o comando de novo por engano, ou com um caminho
    # errado, não deve conseguir zerar um índice de centenas de
    # milhares de registros.
    lidos = []
    for csv_path in csv_paths:
        rows, ignoradas = _ler_linhas(csv_path, column_map)
        if ignoradas:
            print(f"[aviso] {ignoradas} linha(s) de {csv_path} ignorada(s) por não terem coordenada válida.")
        lidos.append((csv_path, rows))

    total = sum(len(rows) for _, rows in lidos)
    if total == 0:
        raise SystemExit(
            "Nenhum registro válido em nenhum dos CSVs informados — nada foi alterado "
            f"no banco existente ({db_path}), pra não apagar um índice que já funcionava. "
            "Confira o caminho do(s) CSV(s)."
        )

    if db_path.exists():
        db_path.unlink()

    conn = ensure_schema(db_path)

    count = 0
    for csv_path, rows in lidos:
        conn.executemany(
            """INSERT INTO enderecos (
                   tipo, logradouro, bairro, cidade, cep, lat, lon,
                   numero_par_ini, numero_par_fim, numero_impar_ini, numero_impar_fim
               )
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        count += len(rows)

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
    parser.add_argument("csv_path", type=Path, nargs="+", help="CSV(s) de entrada com os endereços (ex: um de ruas e outro de bairros — todos entram no mesmo índice)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Caminho do banco SQLite de saída")
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="coluna_padrao=coluna_no_csv",
        help="Remapeia nomes de coluna, ex: --map cidade=municipio (vale pra todos os CSVs passados)",
    )
    args = parser.parse_args()

    faltando = [p for p in args.csv_path if not p.exists()]
    if faltando:
        sys.exit(f"Arquivo(s) não encontrado(s): {faltando}")

    column_map = parse_column_map(args.map)
    count = build(args.csv_path, args.db, column_map)
    print(f"Índice construído em {args.db} com {count} registros.")


if __name__ == "__main__":
    main()
