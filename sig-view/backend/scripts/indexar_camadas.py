#!/usr/bin/env python3
"""Indexa os atributos de uma camada (.geojson, .kml ou .kmz — ex: o
imoveis.geojson gerado por vincular_poligonos.py, ou um KML exportado
direto do seu editor de polígonos com os atributos já preenchidos) no
mesmo índice de busca usado pra endereço/CEP/bairro — assim dá pra
digitar um Setor-Quadra-Lote, Matrícula, Transcrição etc. na caixa de
busca e o mapa vai direto pro polígono.

Complementa o índice existente (não apaga o que já tem de endereços);
rodar de novo para a mesma --layer-id substitui só os registros dessa
camada, sem duplicar.

Por padrão, os campos são reconhecidos AUTOMATICAMENTE (mesma lista de
nomes conhecidos que a barra de detalhes do mapa já usa — ver
app/campos_conhecidos.py) — não precisa digitar --rotulo/--logradouro/
--bairro/--cidade pra uma camada com nomes de campo comuns (ex: as que
o SIG Editor de Lotes exporta: setor/quadra/lote/contribuinte/
matricula/transcricoes/loteamento/enderecos). Use essas opções só se a
sua camada tiver nomes de campo fora do comum que o reconhecimento
automático não pegou (rode uma vez sem elas e confira o resultado
antes de complicar).

Uso:
    python scripts/indexar_camadas.py data/layers/Geo4RI.kml --layer-id Geo4RI --tipo imovel

    # forçando campos especificos (sobrepõe o reconhecimento automático):
    python scripts/indexar_camadas.py data/layers/Geo4RI.kml \\
        --layer-id Geo4RI \\
        --rotulo setor quadra lote matricula transcricao \\
        --logradouro endereco \\
        --tipo imovel

`--layer-id` é só um rótulo pra saber de onde veio o resultado — não
precisa ser idêntico ao id exato da camada no painel (que pode ter
sufixos de pasta); usar o nome do arquivo já é suficiente.

`--rotulo` lista as propriedades da feature que devem virar o texto
pesquisável (concatenadas), ex: setor + quadra + lote + matrícula.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import campos_conhecidos as cc  # noqa: E402
from app import kml as kml_module  # noqa: E402
from app.geoutil import centroide_aproximado  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_geocoder_index import DEFAULT_DB, ensure_schema, rebuild_fts  # noqa: E402


def _carregar_features(path: Path) -> list[dict]:
    """Lê .geojson, .kml ou .kmz e devolve a lista de features (achatando
    pastas do KML, já que pra indexar busca não importa em qual pasta a
    feature estava)."""
    suffix = path.suffix.lower()
    if suffix == ".geojson":
        geojson = json.loads(path.read_text(encoding="utf-8"))
        return geojson.get("features", [])
    if suffix == ".kml":
        grupos, _ = kml_module.parse_kml_full(path.read_bytes())
    elif suffix == ".kmz":
        grupos, _ = kml_module.parse_kmz_full(path.read_bytes())
    else:
        raise SystemExit(f"Formato não suportado: {suffix} (use .geojson, .kml ou .kmz)")

    features = []
    for _caminho, geojson in grupos:
        features.extend(geojson.get("features", []))
    return features


def indexar(
    camada_path: Path,
    db_path: Path,
    layer_id: str,
    campos_rotulo: list[str] | None,
    tipo: str,
    campo_logradouro: str | None = None,
    campo_bairro: str | None = None,
    campo_cidade: str | None = None,
) -> tuple[int, int]:
    """`campos_rotulo`/`campo_logradouro`/`campo_bairro`/`campo_cidade`
    são OPCIONAIS — quando não informados (None/lista vazia), cada um
    é reconhecido automaticamente por feature, a partir dos nomes de
    propriedade conhecidos em app/campos_conhecidos.py (a mesma lista
    que a barra de detalhes do mapa já usa). Informe-os só pra FORÇAR
    campos específicos numa camada com nomes fora do comum."""
    features = _carregar_features(camada_path)
    conn = ensure_schema(db_path)

    conn.execute("DELETE FROM enderecos WHERE layer_id = ?", (layer_id,))

    def campo(props: dict, nome: str | None) -> str | None:
        return (cc.texto_de(props.get(nome)) or None) if nome else None

    inseridos = 0
    ignorados = 0
    linhas = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        centro = centroide_aproximado(geometry)
        if centro is None:
            ignorados += 1
            continue
        lon, lat = centro

        props = feature.get("properties") or {}

        if campos_rotulo:
            partes_rotulo = [t for t in (cc.texto_de(props.get(c)) for c in campos_rotulo) if t]
            rotulo = " — ".join(partes_rotulo) or None
        else:
            rotulo = cc.rotulo_pesquisavel_de(props) or None

        logradouro_valor = campo(props, campo_logradouro) if campo_logradouro else (cc.endereco_de(props) or None)
        bairro_valor = campo(props, campo_bairro) if campo_bairro else (cc.bairro_de(props) or None)
        cidade_valor = campo(props, campo_cidade) if campo_cidade else (cc.cidade_de(props) or None)

        linhas.append(
            (
                tipo,
                logradouro_valor,
                bairro_valor,
                cidade_valor,
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
    parser.add_argument("camada_path", type=Path, help="Camada .geojson, .kml ou .kmz (ex: data/layers/Geo4RI.kml)")
    parser.add_argument("--layer-id", required=True, help="Id da camada no SIG View (geralmente o nome do arquivo sem extensão)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Caminho do banco de busca")
    parser.add_argument("--tipo", default="imovel", help="Valor da coluna 'tipo' pra estes registros (padrão: imovel)")
    parser.add_argument(
        "--rotulo",
        nargs="+",
        default=None,
        metavar="PROPRIEDADE",
        help="Propriedades da feature usadas como texto pesquisável (padrão: reconhece sozinho — ver app/campos_conhecidos.py)",
    )
    parser.add_argument("--logradouro", default=None, metavar="PROPRIEDADE", help="Propriedade a usar como logradouro (padrão: reconhece sozinho)")
    parser.add_argument("--bairro", default=None, metavar="PROPRIEDADE", help="Propriedade a usar como bairro (padrão: reconhece sozinho)")
    parser.add_argument("--cidade", default=None, metavar="PROPRIEDADE", help="Propriedade a usar como cidade (padrão: reconhece sozinho)")
    args = parser.parse_args()

    if not args.camada_path.exists():
        sys.exit(f"Arquivo não encontrado: {args.camada_path}")

    inseridos, ignorados = indexar(
        args.camada_path,
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
