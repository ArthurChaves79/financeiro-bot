#!/usr/bin/env python3
"""Indexa os atributos de uma camada (ex: o imoveis.geojson gerado por
vincular_poligonos.py) no mesmo índice de busca usado pra endereço/CEP/
bairro — assim dá pra digitar um número de contribuinte, proprietário
etc. na caixa de busca e o mapa vai direto pro polígono.

Complementa o índice existente (não apaga o que já tem de endereços);
rodar de novo para a mesma --layer-id substitui só os registros dessa
camada, sem duplicar.

Uso:
    python scripts/indexar_camadas.py data/layers/imoveis.geojson \\
        --layer-id imoveis \\
        --rotulo numero_contribuinte proprietario \\
        --tipo imovel

`--layer-id` precisa ser o mesmo id que a camada tem no SIG View — pra
um arquivo simples direto em data/layers (sem pastas dentro), é o nome
do arquivo sem extensão (ex: "imoveis.geojson" -> "imoveis").

`--rotulo` lista as propriedades da feature que devem virar o texto
pesquisável (concatenadas), ex: número de contribuinte + proprietário.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.geoutil import centroide_aproximado  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_geocoder_index import DEFAULT_DB, ensure_schema, rebuild_fts  # noqa: E402


def indexar(
    geojson_path: Path,
    db_path: Path,
    layer_id: str,
    campos_rotulo: list[str],
    tipo: str,
    campo_logradouro: str | None,
    campo_bairro: str | None,
    campo_cidade: str | None,
) -> tuple[int, int]:
    geojson = json.loads(geojson_path.read_text(encoding="utf-8"))
    conn = ensure_schema(db_path)

    conn.execute("DELETE FROM enderecos WHERE layer_id = ?", (layer_id,))

    inseridos = 0
    ignorados = 0
    linhas = []
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry") or {}
        centro = centroide_aproximado(geometry)
        if centro is None:
            ignorados += 1
            continue
        lon, lat = centro

        props = feature.get("properties") or {}
        partes_rotulo = [str(props[c]) for c in campos_rotulo if props.get(c) not in (None, "")]
        rotulo = " — ".join(partes_rotulo) or None

        linhas.append(
            (
                tipo,
                props.get(campo_logradouro) if campo_logradouro else None,
                props.get(campo_bairro) if campo_bairro else None,
                props.get(campo_cidade) if campo_cidade else None,
                None,  # cep
                rotulo,
                layer_id,
                lat,
                lon,
            )
        )

    conn.executemany(
        """INSERT INTO enderecos (tipo, logradouro, bairro, cidade, cep, rotulo, layer_id, lat, lon)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        linhas,
    )
    inseridos = len(linhas)

    conn.commit()
    rebuild_fts(conn)
    conn.close()
    return inseridos, ignorados


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("geojson_path", type=Path, help="Camada .geojson já vinculada (ex: data/layers/imoveis.geojson)")
    parser.add_argument("--layer-id", required=True, help="Id da camada no SIG View (geralmente o nome do arquivo sem extensão)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Caminho do banco de busca")
    parser.add_argument("--tipo", default="imovel", help="Valor da coluna 'tipo' pra estes registros (padrão: imovel)")
    parser.add_argument(
        "--rotulo",
        nargs="+",
        default=["numero_contribuinte", "proprietario"],
        metavar="PROPRIEDADE",
        help="Propriedades da feature usadas como texto pesquisável (padrão: numero_contribuinte proprietario)",
    )
    parser.add_argument("--logradouro", default=None, metavar="PROPRIEDADE", help="Propriedade a usar como logradouro, se existir")
    parser.add_argument("--bairro", default=None, metavar="PROPRIEDADE", help="Propriedade a usar como bairro, se existir")
    parser.add_argument("--cidade", default=None, metavar="PROPRIEDADE", help="Propriedade a usar como cidade, se existir")
    args = parser.parse_args()

    if not args.geojson_path.exists():
        sys.exit(f"Arquivo não encontrado: {args.geojson_path}")

    inseridos, ignorados = indexar(
        args.geojson_path,
        args.db,
        args.layer_id,
        args.rotulo,
        args.tipo,
        args.logradouro,
        args.bairro,
        args.cidade,
    )
    print(f"Indexado(s) {inseridos} registro(s) da camada '{args.layer_id}' em {args.db}.")
    if ignorados:
        print(f"  {ignorados} feature(s) ignorada(s) por não terem geometria válida.")


if __name__ == "__main__":
    main()
