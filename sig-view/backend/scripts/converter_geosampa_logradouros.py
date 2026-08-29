#!/usr/bin/env python3
"""Converte uma camada baixada do GeoSampa (logradouros, bairros/distritos
ou pontos de CEP) pro CSV que scripts/build_geocoder_index.py espera —
assim dá pra alimentar a busca (endereço/CEP/bairro) com dados oficiais
da Prefeitura de São Paulo, sem precisar montar a planilha na mão.

Como baixar no GeoSampa (geosampa.prefeitura.sp.gov.br):
  1. Abra o mapa, ache a camada que quiser em "Mapa Digital da Cidade"
     (ex: "Sistema Viário" > "Eixo de Logradouro" pras ruas; "Distritos"
     ou "Bairros" pras regiões).
  2. Use a opção de download da camada e escolha o formato **GeoJSON**
     (evita ter que lidar com projeção/CRS de Shapefile — o GeoJSON já
     sai em latitude/longitude direto).
  3. Salve o arquivo e rode este script em cima dele.

Como os nomes de coluna variam de camada pra camada (e podem mudar
entre atualizações do GeoSampa), o script tenta reconhecer os nomes
mais comuns sozinho; se não achar, use --map pra apontar manualmente
(mesmo esquema do --map de build_geocoder_index.py).

Uso (camada de ruas — logradouros):
    python scripts/converter_geosampa_logradouros.py logradouros.geojson \\
        --tipo endereco --saida enderecos_ruas.csv

Uso (camada de bairros/distritos):
    python scripts/converter_geosampa_logradouros.py distritos.geojson \\
        --tipo bairro --saida enderecos_bairros.csv

Depois, junte tudo num índice só (rode build_geocoder_index.py uma vez
por CSV que quiser importar — ele COMPLEMENTA o banco se já existir só
quando chamado por indexar_camadas.py; build_geocoder_index.py sozinho
reconstrói do zero, então se tiver mais de um CSV, junte-os num só CSV
antes, ou rode build_geocoder_index.py no primeiro e depois use
scripts/indexar_camadas.py adaptado, ou simplesmente concatene os CSVs):

    python scripts/build_geocoder_index.py enderecos_ruas.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.geoutil import centroide_aproximado  # noqa: E402

# Candidatos pra cada campo, JÁ no formato normalizado (sem acento,
# maiúscula, espaço ou "_" — igual ao que _normalizar() produz) — cobre
# os nomes de coluna mais comuns usados nas camadas do GeoSampa e de
# outros portais de dados abertos municipais, sem precisar bater
# exatamente com um nome fixo.
CAMPOS_CONHECIDOS = {
    "tipo_logradouro": ["tipolog", "tipologr", "tipologradouro", "tlogrado", "dsctipologradouro"],
    "nome": ["nome", "nomecompleto", "nomelogradouro", "logradouro", "nomelog", "nmlogradouro", "dsnome"],
    "bairro": ["bairro", "nomebairro", "nmbairro", "dsbairro"],
    "distrito": ["distrito", "nomedistrito", "nmdistrito", "dsdistrito"],
    "cep": ["cep", "ceplogr", "codcep", "nucep"],
}


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def _indexar_propriedades(props: dict) -> dict[str, str]:
    """nome normalizado -> nome original da propriedade, só das que têm
    algum valor (propriedade vazia/nula não conta como presente)."""
    indice = {}
    for chave, valor in props.items():
        if valor is None or str(valor).strip() == "":
            continue
        norm = _normalizar(str(chave))
        indice.setdefault(norm, chave)
    return indice


def _campo(props: dict, indice: dict[str, str], candidatos: list[str], mapeamento: dict[str, str], nome_campo: str) -> str:
    # --map tem prioridade: se o usuário disse explicitamente qual coluna
    # usar pra este campo, usa ela (mesmo que o valor esteja vazio nessa
    # linha — não cai pros candidatos automáticos nesse caso).
    if nome_campo in mapeamento:
        return str(props.get(mapeamento[nome_campo]) or "").strip()
    for candidato in candidatos:
        chave_original = indice.get(candidato)
        if chave_original is not None:
            return str(props[chave_original]).strip()
    return ""


def linhas_de_features(
    features: list[tuple[dict, dict]],
    tipo: str,
    cidade: str,
    mapeamento: dict[str, str],
) -> list[dict[str, str]]:
    """Monta as linhas do CSV a partir de uma lista de (propriedades,
    geometria) — a geometria já precisa estar em longitude/latitude
    (GeoJSON-style: {"type": ..., "coordinates": ...}). Compartilhado
    entre a leitura de GeoJSON (aqui) e de GeoPackage
    (converter_geopackage_geosampa.py), que só difere em como lê o
    arquivo de origem, não em como interpreta as colunas."""
    linhas = []
    ignoradas = 0
    for props, geometry in features:
        centro = centroide_aproximado(geometry or {})
        if centro is None:
            ignoradas += 1
            continue
        lon, lat = centro

        indice = _indexar_propriedades(props)

        tipo_logradouro = _campo(props, indice, CAMPOS_CONHECIDOS["tipo_logradouro"], mapeamento, "tipo_logradouro")
        nome = _campo(props, indice, CAMPOS_CONHECIDOS["nome"], mapeamento, "nome")
        bairro = _campo(props, indice, CAMPOS_CONHECIDOS["bairro"], mapeamento, "bairro") or \
            _campo(props, indice, CAMPOS_CONHECIDOS["distrito"], mapeamento, "distrito")
        cep = _campo(props, indice, CAMPOS_CONHECIDOS["cep"], mapeamento, "cep")

        if tipo == "bairro":
            # Numa camada de bairros/distritos, o "nome" da feature é o
            # próprio bairro, não um logradouro.
            logradouro = None
            bairro = bairro or nome
        else:
            logradouro = f"{tipo_logradouro} {nome}".strip() if tipo_logradouro else (nome or None)

        if not (logradouro or bairro or cep):
            ignoradas += 1
            continue

        linhas.append(
            {
                "tipo": tipo,
                "logradouro": logradouro or "",
                "bairro": bairro or "",
                "cidade": cidade,
                "cep": cep or "",
                "lat": lat,
                "lon": lon,
            }
        )

    if ignoradas:
        print(f"[aviso] {ignoradas} feature(s) ignorada(s) (sem geometria válida ou sem nenhum campo reconhecido).")
    return linhas


def converter(
    geojson_path: Path,
    tipo: str,
    cidade: str,
    mapeamento: dict[str, str],
) -> list[dict[str, str]]:
    dados = json.loads(geojson_path.read_text(encoding="utf-8-sig"))
    features_geojson = dados.get("features", [])
    if not features_geojson:
        sys.exit(f"Nenhuma feature encontrada em {geojson_path} (era esperado um GeoJSON com 'features').")

    features = [(f.get("properties") or {}, f.get("geometry") or {}) for f in features_geojson]
    return linhas_de_features(features, tipo, cidade, mapeamento)


def escrever_csv(linhas: list[dict[str, str]], saida: Path) -> None:
    with saida.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["tipo", "logradouro", "bairro", "cidade", "cep", "lat", "lon"])
        writer.writeheader()
        writer.writerows(linhas)


def parse_column_map(pairs: list[str]) -> dict[str, str]:
    result = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--map inválido: '{pair}' (use campo=coluna_no_geojson)")
        key, value = pair.split("=", 1)
        result[key] = value
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("geojson_path", type=Path, help="Camada baixada do GeoSampa, em GeoJSON")
    parser.add_argument("--saida", type=Path, default=None, help="CSV de saída (padrão: mesmo nome, extensão .csv)")
    parser.add_argument("--tipo", choices=["endereco", "bairro", "cep"], default="endereco",
                         help="O que esta camada representa (padrão: endereco, pra camadas de logradouro/eixo de rua)")
    parser.add_argument("--cidade", default="São Paulo", help="Valor fixo da coluna cidade (padrão: São Paulo)")
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="campo=coluna_no_geojson",
        help="Força qual coluna do GeoJSON usar pra um campo (tipo_logradouro/nome/bairro/distrito/cep), "
             "caso o reconhecimento automático não ache. Ex: --map cep=CD_CEP",
    )
    args = parser.parse_args()

    if not args.geojson_path.exists():
        sys.exit(f"Arquivo não encontrado: {args.geojson_path}")

    mapeamento = parse_column_map(args.map)
    linhas = converter(args.geojson_path, args.tipo, args.cidade, mapeamento)
    if not linhas:
        sys.exit(
            "Nenhuma linha aproveitável — confira se o GeoJSON tem as colunas esperadas "
            "(rode com --map pra apontar manualmente, ex: --map nome=NM_LOGR)."
        )

    saida = args.saida or args.geojson_path.with_suffix(".csv")
    escrever_csv(linhas, saida)

    print(f"Gerado {saida} com {len(linhas)} registro(s).")
    print(f"Agora rode: python scripts/build_geocoder_index.py {saida}")


if __name__ == "__main__":
    main()
