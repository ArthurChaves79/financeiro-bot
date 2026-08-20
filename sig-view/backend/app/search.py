"""Busca de endereço, CEP, bairro e imóvel usando um índice local SQLite
(FTS5).

O índice é construído por dois scripts, que gravam no mesmo banco:
  - scripts/build_geocoder_index.py: endereços/CEP/bairro, a partir de
    um CSV (ex: GeoSampa, Correios, IBGE CNEFE).
  - scripts/indexar_camadas.py: dados vinculados aos polígonos das
    camadas (ex: número de contribuinte, proprietário), a partir do
    .geojson gerado por vincular_poligonos.py.
Tudo roda localmente — nenhuma chamada é feita à internet.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import settings

_CEP_RE = re.compile(r"^\d{5}-?\d{3}$")


@dataclass
class SearchResult:
    id: int
    tipo: str  # "endereco" | "bairro" | "cep" | "imovel" | ...
    logradouro: str | None
    bairro: str | None
    cidade: str | None
    cep: str | None
    rotulo: str | None  # texto extra pesquisável (ex: "num. contrib. 1234 — João da Silva")
    layer_id: str | None  # id da camada de origem, se veio de uma camada vinculada
    lat: float
    lon: float

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "logradouro": self.logradouro,
            "bairro": self.bairro,
            "cidade": self.cidade,
            "cep": self.cep,
            "rotulo": self.rotulo,
            "layer_id": self.layer_id,
            "lat": self.lat,
            "lon": self.lon,
            "label": self.label,
        }

    @property
    def label(self) -> str:
        partes = [p for p in (self.logradouro, self.bairro, self.cidade) if p]
        texto = ", ".join(partes)
        if self.rotulo:
            texto = f"{texto} — {self.rotulo}" if texto else self.rotulo
        if self.cep:
            texto = f"{texto} — CEP {self.cep}" if texto else f"CEP {self.cep}"
        return texto or "Resultado"


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _normalize(text: str) -> str:
    return _strip_accents(text).lower().strip()


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


class GeocoderUnavailable(RuntimeError):
    """Levantado quando o índice de busca ainda não foi construído."""


def search(query: str, limit: int = 10) -> list[SearchResult]:
    query = query.strip()
    if not query:
        return []

    db_path = settings.geocoder_db
    if not db_path.exists():
        raise GeocoderUnavailable(
            f"Índice de geocoding não encontrado em {db_path}. "
            "Rode scripts/build_geocoder_index.py para gerá-lo."
        )

    conn = _connect(db_path)
    try:
        cep_digits = re.sub(r"\D", "", query)
        if _CEP_RE.match(query) or len(cep_digits) == 8:
            return _search_by_cep(conn, cep_digits, limit)
        return _search_fts(conn, query, limit)
    finally:
        conn.close()


def _search_by_cep(conn: sqlite3.Connection, cep_digits: str, limit: int) -> list[SearchResult]:
    formatted = f"{cep_digits[:5]}-{cep_digits[5:]}"
    rows = conn.execute(
        "SELECT * FROM enderecos WHERE cep = ? OR cep = ? LIMIT ?",
        (formatted, cep_digits, limit),
    ).fetchall()
    return [_row_to_result(r) for r in rows]


def _search_fts(conn: sqlite3.Connection, query: str, limit: int) -> list[SearchResult]:
    normalized = _normalize(query)
    # Cada termo vira um prefixo FTS5 (ex: "av paulista" -> "av* paulista*")
    terms = [t for t in re.split(r"\s+", normalized) if t]
    if not terms:
        return []
    match_expr = " ".join(f"{_escape_fts(t)}*" for t in terms)

    rows = conn.execute(
        """
        SELECT enderecos.*
        FROM enderecos_fts
        JOIN enderecos ON enderecos.id = enderecos_fts.rowid
        WHERE enderecos_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (match_expr, limit),
    ).fetchall()
    return [_row_to_result(r) for r in rows]


def _escape_fts(term: str) -> str:
    # remove caracteres que quebram a sintaxe de MATCH do FTS5
    return re.sub(r"[^a-z0-9]", "", term)


def _row_to_result(row: sqlite3.Row) -> SearchResult:
    colunas = row.keys()
    return SearchResult(
        id=row["id"],
        tipo=row["tipo"],
        logradouro=row["logradouro"],
        bairro=row["bairro"],
        cidade=row["cidade"],
        cep=row["cep"],
        rotulo=row["rotulo"] if "rotulo" in colunas else None,
        layer_id=row["layer_id"] if "layer_id" in colunas else None,
        lat=row["lat"],
        lon=row["lon"],
    )
