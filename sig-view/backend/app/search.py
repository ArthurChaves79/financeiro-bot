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

# "Rua Natal 974" -> ("Rua Natal", "974"). Exige espaço antes do número
# (não só "não-dígito") pra não confundir com um código tipo
# "045.123.0045-6" (que termina em dígito colado num "-", sem espaço) —
# esse continua indo pra busca normal por texto, sem tentar separar
# número nenhum.
_ENDERECO_COM_NUMERO_RE = re.compile(r"^(.+?)\s+(\d{1,6})$")


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
    numero_buscado: int | None = None  # nº de porta digitado na busca, quando achou o trecho certo

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
        logradouro = self.logradouro
        if logradouro and self.numero_buscado is not None:
            # É o centro aproximado do TRECHO da rua onde esse número
            # cai (achado pela faixa de numeração do GeoSampa), não a
            # porta exata — "aprox." deixa isso claro pro usuário.
            logradouro = f"{logradouro}, nº {self.numero_buscado} (aprox.)"
        partes = [p for p in (logradouro, self.bairro, self.cidade) if p]
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


def _match_expr(texto: str) -> str | None:
    """Cada termo vira um prefixo FTS5 (ex: "av paulista" -> "av* paulista*").
    Separa por QUALQUER pontuação, não só espaço — o FTS5 (tokenizer
    unicode61) já quebra o texto indexado assim (ex: "045.123.0045"
    vira os tokens "045", "123", "0045" separados); se a busca não
    separar do mesmo jeito, digitar um código com pontos/traços (SQL de
    imóvel, matrícula etc.) não encontra nada mesmo estando indexado."""
    terms = [t for t in re.split(r"[^a-z0-9]+", _normalize(texto)) if t]
    if not terms:
        return None
    return " ".join(f"{_escape_fts(t)}*" for t in terms)


def _search_fts(conn: sqlite3.Connection, query: str, limit: int) -> list[SearchResult]:
    m = _ENDERECO_COM_NUMERO_RE.match(query.strip())
    if m:
        nome_rua, numero = m.group(1), int(m.group(2))
        resultados = _search_por_numero(conn, nome_rua, numero, limit)
        if resultados:
            return resultados
        # Não achou nenhum trecho com esse número na faixa (rua sem
        # numeração cadastrada, número fora do que existe, etc.) — cai
        # pra busca normal só pelo nome da rua, sem o número, em vez de
        # devolver "nada encontrado" pro usuário.
        query = nome_rua

    match_expr = _match_expr(query)
    if match_expr is None:
        return []

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


def _search_por_numero(conn: sqlite3.Connection, nome_rua: str, numero: int, limit: int) -> list[SearchResult]:
    """Acha o(s) trecho(s) da rua cuja faixa de numeração (par/ímpar,
    vinda do Eixo de Logradouro do GeoSampa) contém o número buscado —
    o resultado é o centro aproximado daquele TRECHO, não a porta
    exata (a camada não tem a posição de cada número, só a faixa de
    cada pedaço de rua)."""
    match_expr = _match_expr(nome_rua)
    if match_expr is None:
        return []

    par = numero % 2 == 0
    coluna_ini, coluna_fim = ("numero_par_ini", "numero_par_fim") if par else ("numero_impar_ini", "numero_impar_fim")

    rows = conn.execute(
        f"""
        SELECT enderecos.*
        FROM enderecos_fts
        JOIN enderecos ON enderecos.id = enderecos_fts.rowid
        WHERE enderecos_fts MATCH ?
          AND {coluna_ini} IS NOT NULL AND {coluna_fim} IS NOT NULL
          AND ? BETWEEN min({coluna_ini}, {coluna_fim}) AND max({coluna_ini}, {coluna_fim})
        ORDER BY rank
        LIMIT ?
        """,
        (match_expr, numero, limit),
    ).fetchall()
    return [_row_to_result(r, numero_buscado=numero) for r in rows]


def _escape_fts(term: str) -> str:
    # remove caracteres que quebram a sintaxe de MATCH do FTS5
    return re.sub(r"[^a-z0-9]", "", term)


def _row_to_result(row: sqlite3.Row, numero_buscado: int | None = None) -> SearchResult:
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
        numero_buscado=numero_buscado,
    )
