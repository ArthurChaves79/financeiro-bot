#!/usr/bin/env python3
"""Converte uma camada baixada do GeoSampa em **GeoPackage (.gpkg)** pro
CSV que scripts/build_geocoder_index.py espera — mesma ideia de
converter_geosampa_logradouros.py (que lê GeoJSON), só que lendo
GeoPackage direto.

Por que GeoPackage em vez de Shapefile: um .gpkg é só um banco SQLite
com um formato de geometria documentado — dá pra ler com `sqlite3` da
própria stdlib do Python, sem precisar de GDAL/Fiona/pyshp nem nada
externo. Shapefile (`.shp`) exigiria decodificar um formato binário à
parte (e ainda separar a projeção do `.prj`), então prefira sempre
baixar em GeoPackage ou GeoJSON quando o portal oferecer a opção.

O GeoSampa publica os dados em **SIRGAS 2000 / UTM 23S** (metros, não
graus) — o script detecta isso automaticamente (lendo
`gpkg_spatial_ref_sys`) e converte pra latitude/longitude sozinho
(`app/geoutil.utm_para_latlon`). Se a camada já vier em WGS84
(EPSG:4326, graus), também funciona sem converter nada.

Uso — primeiro descubra o nome da tabela dentro do arquivo, se não
souber (todo .gpkg pode ter mais de uma camada):

    python scripts/converter_geopackage_geosampa.py logradouros.gpkg --listar-tabelas

Depois converta (camada de ruas — logradouros):

    python scripts/converter_geopackage_geosampa.py logradouros.gpkg \\
        --tabela SIRGAS_SHP_logradouronbl --tipo endereco --saida ruas.csv

Camada de bairros/distritos:

    python scripts/converter_geopackage_geosampa.py distritos.gpkg \\
        --tabela SIRGAS_SHP_distrito --tipo bairro --saida bairros.csv

Depois junte tudo num índice só:

    python scripts/build_geocoder_index.py ruas.csv bairros.csv
"""
from __future__ import annotations

import argparse
import struct
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.geoutil import utm_para_latlon  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from converter_geosampa_logradouros import escrever_csv, linhas_de_features, parse_column_map  # noqa: E402

# EPSG conhecidos que valem a pena reconhecer sem perguntar nada ao
# usuário — os dois jeitos mais comuns de publicar dados de São Paulo
# em UTM 23S (SIRGAS 2000 é o oficial atual; WGS84/UTM já apareceu em
# alguns exports também). Formato: epsg -> (zona, hemisfério norte?).
_EPSG_UTM_CONHECIDOS = {
    31983: (23, False),  # SIRGAS 2000 / UTM zone 23S — o padrão do GeoSampa
    32723: (23, False),  # WGS 84 / UTM zone 23S
}


def _epsg_da_tabela(conn: sqlite3.Connection, tabela: str) -> int | None:
    row = conn.execute(
        "SELECT srs_id FROM gpkg_geometry_columns WHERE table_name = ?", (tabela,)
    ).fetchone()
    if row is None:
        return None
    srs_id = row[0]
    org = conn.execute(
        "SELECT organization, organization_coordsys_id FROM gpkg_spatial_ref_sys WHERE srs_id = ?", (srs_id,)
    ).fetchone()
    if org is None:
        return None
    organizacao, codigo = org
    if str(organizacao).upper() == "EPSG":
        return int(codigo)
    return None


def _tabelas_de_features(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT table_name FROM gpkg_contents WHERE data_type = 'features'").fetchall()
    return [r[0] for r in rows]


def _ler_uint32(blob: bytes, offset: int, little_endian: bool) -> int:
    return struct.unpack_from("<I" if little_endian else ">I", blob, offset)[0]


def _geometria_do_gpkg_blob(blob: bytes) -> dict | None:
    """Decodifica o cabeçalho binário do GeoPackage (magic "GP" + flags
    + srs_id + envelope opcional) e devolve o WKB puro que vem depois,
    já convertido pra um dict {"type", "coordinates"} estilo GeoJSON
    (nas unidades originais — metros, se a camada estiver em UTM)."""
    if len(blob) < 8 or blob[0:2] != b"GP":
        return None
    flags = blob[3]
    little_endian_header = bool(flags & 0x01)
    indicador_envelope = (flags >> 1) & 0x07
    tamanho_envelope = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get(indicador_envelope, 0)
    inicio_wkb = 8 + tamanho_envelope
    return _wkb_para_geometria(blob, inicio_wkb)


def _wkb_para_geometria(blob: bytes, offset: int) -> dict | None:
    if offset >= len(blob):
        return None
    little_endian = blob[offset] == 1
    fmt_uint = "<I" if little_endian else ">I"
    fmt_dbl = "<d" if little_endian else ">d"
    tipo_bruto = struct.unpack_from(fmt_uint, blob, offset + 1)[0]
    tipo_base = tipo_bruto % 1000  # ignora sufixo Z/M (1000/2000/3000) — só usa X/Y
    tem_z = 1000 <= tipo_bruto < 4000 and (tipo_bruto % 2000) >= 1000
    tem_m = tipo_bruto >= 2000
    dims = 2 + (1 if tem_z else 0) + (1 if tem_m else 0)
    pos = offset + 5

    def ler_ponto():
        nonlocal pos
        x, y = struct.unpack_from(fmt_dbl, blob, pos)[0], struct.unpack_from(fmt_dbl, blob, pos + 8)[0]
        pos += 8 * dims
        return [x, y]

    def ler_pontos(n):
        return [ler_ponto() for _ in range(n)]

    def ler_anel():
        nonlocal pos
        n = struct.unpack_from(fmt_uint, blob, pos)[0]
        pos += 4
        return ler_pontos(n)

    def ler_poligono():
        nonlocal pos
        n_aneis = struct.unpack_from(fmt_uint, blob, pos)[0]
        pos += 4
        return [ler_anel() for _ in range(n_aneis)]

    if tipo_base == 1:  # Point
        return {"type": "Point", "coordinates": ler_ponto()}
    if tipo_base == 2:  # LineString
        n = struct.unpack_from(fmt_uint, blob, pos)[0]
        pos += 4
        return {"type": "LineString", "coordinates": ler_pontos(n)}
    if tipo_base == 3:  # Polygon
        return {"type": "Polygon", "coordinates": ler_poligono()}
    if tipo_base == 4:  # MultiPoint — cada membro é um WKB Point completo (com seu próprio header)
        n = struct.unpack_from(fmt_uint, blob, pos)[0]
        pos += 4
        pontos = []
        for _ in range(n):
            sub = _wkb_para_geometria(blob, pos)
            pos += 5 + 8 * dims
            if sub:
                pontos.append(sub["coordinates"])
        return {"type": "MultiPoint", "coordinates": pontos}
    if tipo_base == 5:  # MultiLineString
        n = struct.unpack_from(fmt_uint, blob, pos)[0]
        pos += 4
        linhas = []
        for _ in range(n):
            sub_le = blob[pos] == 1
            sub_fmt = "<I" if sub_le else ">I"
            pos += 5  # byte-order + tipo do sub-WKB
            n_pts = struct.unpack_from(sub_fmt, blob, pos)[0]
            pos += 4
            linhas.append(ler_pontos(n_pts))
        return {"type": "MultiLineString", "coordinates": linhas}
    if tipo_base == 6:  # MultiPolygon
        n = struct.unpack_from(fmt_uint, blob, pos)[0]
        pos += 4
        poligonos = []
        for _ in range(n):
            pos += 5  # byte-order + tipo do sub-WKB (Polygon)
            n_aneis = struct.unpack_from(fmt_uint, blob, pos)[0]
            pos += 4
            poligonos.append([ler_anel() for _ in range(n_aneis)])
        return {"type": "MultiPolygon", "coordinates": poligonos}
    return None  # GeometryCollection ou tipo não suportado — feature é ignorada mais adiante


def _reprojetar(geometry: dict, zona: int, norte: bool) -> dict:
    """Converte todas as coordenadas X/Y (UTM, metros) da geometria pra
    longitude/latitude — percorre a mesma estrutura aninhada que
    geoutil.centroide_aproximado entende."""

    def ponto(p):
        lat, lon = utm_para_latlon(p[0], p[1], zona, norte)
        return [lon, lat]

    def rec(coords, tipo):
        if tipo == "Point":
            return ponto(coords)
        if tipo in ("LineString", "MultiPoint"):
            return [ponto(p) for p in coords]
        if tipo in ("Polygon", "MultiLineString"):
            return [[ponto(p) for p in parte] for parte in coords]
        if tipo == "MultiPolygon":
            return [[[ponto(p) for p in anel] for anel in poligono] for poligono in coords]
        return coords

    return {"type": geometry["type"], "coordinates": rec(geometry["coordinates"], geometry["type"])}


def ler_features(gpkg_path: Path, tabela: str) -> list[tuple[dict, dict]]:
    conn = sqlite3.connect(gpkg_path)
    try:
        col_geom_row = conn.execute(
            "SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?", (tabela,)
        ).fetchone()
        if col_geom_row is None:
            tabelas = _tabelas_de_features(conn)
            sys.exit(
                f"Tabela '{tabela}' não encontrada (ou não é uma camada de features). "
                f"Tabelas disponíveis: {tabelas or '(nenhuma)'} — use --tabela pra escolher."
            )
        col_geom = col_geom_row[0]

        epsg = _epsg_da_tabela(conn, tabela)
        reprojetar = _EPSG_UTM_CONHECIDOS.get(epsg) if epsg else None
        if epsg == 4326:
            reprojetar = None  # já é lat/lon, não precisa converter
        elif reprojetar is None and epsg is not None:
            sys.exit(
                f"Projeção EPSG:{epsg} não reconhecida por este script (só sei tratar EPSG:4326 e "
                f"UTM 23S — 31983/32723). Me avise qual é essa projeção que eu adiciono o suporte."
            )

        cursor = conn.execute(f'SELECT * FROM "{tabela}"')
        colunas = [d[0] for d in cursor.description]
        idx_geom = colunas.index(col_geom)

        features = []
        total = 0
        sem_blob = 0
        blob_nao_decodificado = 0
        exemplo_blob = None
        for row in cursor:
            total += 1
            blob = row[idx_geom]
            if blob is None:
                sem_blob += 1
                continue
            geometry = _geometria_do_gpkg_blob(blob)
            if geometry is None:
                blob_nao_decodificado += 1
                if exemplo_blob is None:
                    exemplo_blob = blob
                continue
            if reprojetar is not None:
                zona, norte = reprojetar
                geometry = _reprojetar(geometry, zona, norte)
            props = {colunas[i]: row[i] for i in range(len(colunas)) if i != idx_geom}
            features.append((props, geometry))

        if blob_nao_decodificado:
            print(f"[aviso] {blob_nao_decodificado} de {total} feature(s) com geometria em formato não "
                  f"reconhecido (tipo de geometria não suportado por este script).")
            if exemplo_blob:
                print(f"        Cabeçalho de uma delas, pra diagnosticar: {exemplo_blob[:16].hex()}")
        if sem_blob:
            print(f"[aviso] {sem_blob} de {total} feature(s) sem geometria (coluna nula).")
        return features
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gpkg_path", type=Path, help="Arquivo .gpkg baixado do GeoSampa")
    parser.add_argument("--tabela", default=None, help="Nome da tabela/camada dentro do .gpkg (veja --listar-tabelas)")
    parser.add_argument("--listar-tabelas", action="store_true", help="Só lista as tabelas de features do arquivo e sai")
    parser.add_argument("--saida", type=Path, default=None, help="CSV de saída (padrão: mesmo nome, extensão .csv)")
    parser.add_argument("--tipo", choices=["endereco", "bairro", "cep"], default="endereco",
                         help="O que esta camada representa (padrão: endereco)")
    parser.add_argument("--cidade", default="São Paulo", help="Valor fixo da coluna cidade (padrão: São Paulo)")
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="campo=coluna_na_tabela",
        help="Força qual coluna usar pra um campo (tipo_logradouro/nome/bairro/distrito/cep). Ex: --map cep=CD_CEP",
    )
    args = parser.parse_args()

    if not args.gpkg_path.exists():
        sys.exit(f"Arquivo não encontrado: {args.gpkg_path}")

    conn = sqlite3.connect(args.gpkg_path)
    tabelas = _tabelas_de_features(conn)
    conn.close()

    if args.listar_tabelas or not args.tabela:
        print("Tabelas de features encontradas neste .gpkg:")
        for t in tabelas:
            print(f"  - {t}")
        if not args.tabela:
            sys.exit("Use --tabela <nome> pra escolher qual converter.")
        return

    mapeamento = parse_column_map(args.map)
    features = ler_features(args.gpkg_path, args.tabela)
    if not features:
        sys.exit(f"Nenhuma feature com geometria válida na tabela '{args.tabela}'.")

    linhas = linhas_de_features(features, args.tipo, args.cidade, mapeamento)
    if not linhas:
        sys.exit(
            "Nenhuma linha aproveitável — confira se a tabela tem as colunas esperadas "
            "(rode com --map pra apontar manualmente, ex: --map nome=NM_LOGR)."
        )

    saida = args.saida or args.gpkg_path.with_suffix(".csv")
    escrever_csv(linhas, saida)
    print(f"Gerado {saida} com {len(linhas)} registro(s).")
    print(f"Agora rode: python scripts/build_geocoder_index.py {saida}")


if __name__ == "__main__":
    main()
