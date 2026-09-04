#!/usr/bin/env python3
"""Vincula polígonos (KML/KMZ/GeoJSON) a dados já existentes num banco,
gerando uma camada pronta para o SIG View — sem precisar digitar os
atributos manualmente para quem já tem número de contribuinte batendo.

Pensado para o caso: os polígonos já existem, os atributos já existem
num banco relacional (SQL Server, Postgres, MySQL, o que for), e o
vínculo entre os dois é feito por uma chave em comum (por padrão, o
número do contribuinte) — mas nem todo polígono tem essa chave
preenchida.

Fluxo:
  1. Exporte a tabela de atributos do banco para um CSV (qualquer SGBD
     faz isso com um SELECT). Ex: numero_contribuinte, proprietario,
     area_construida, uso, ...
  2. (Opcional) Um segundo CSV com campos que só existem no SIG View
     (que ainda não têm lugar no banco antigo), na mesma chave.
  3. (Opcional) Um terceiro CSV de "vínculos manuais", para os polígonos
     que não têm o número do contribuinte no arquivo original — você
     preenche esse arquivo aos poucos, aumentando a cobertura sem
     precisar re-processar tudo.
  4. Rode este script -> ele gera:
       - a camada .geojson pronta (geometria + atributos do banco +
         complemento), pra colocar na pasta de camadas.
       - um pendencias.csv com os polígonos que NÃO foi possível
         vincular (nem pela chave original, nem pelo arquivo de
         vínculos manuais) — pra você ir resolvendo aos poucos.

Uso:
    python scripts/vincular_poligonos.py poligonos.kml atributos.csv \\
        --saida ../data/layers/imoveis.geojson \\
        --pendencias pendencias_imoveis.csv \\
        --chave numero_contribuinte \\
        --complemento complemento_sigview.csv \\
        --vinculos-manuais vinculos_manuais.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import kml as kml_module  # noqa: E402
from app.geoutil import centroide_aproximado as _centroide_aproximado  # noqa: E402


def _normaliza_chave(valor: str | None) -> str | None:
    """Deixa a chave de vínculo comparável mesmo com pequenas
    diferenças de formatação (espaços, zeros à esquerda, maiúsculas)."""
    if valor is None:
        return None
    v = str(valor).strip()
    if not v:
        return None
    return v.lstrip("0") or "0"


def carregar_poligonos(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".geojson":
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix == ".kml":
        return kml_module.parse_kml_bytes(path.read_bytes())
    if suffix == ".kmz":
        return kml_module.parse_kmz_bytes(path.read_bytes())
    raise SystemExit(f"Formato de polígonos não suportado: {suffix} (use .geojson, .kml ou .kmz)")


def carregar_csv_por_chave(path: Path | None, coluna_chave: str) -> dict[str, dict]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if coluna_chave not in (reader.fieldnames or []):
            raise SystemExit(
                f"Coluna '{coluna_chave}' não encontrada em {path}. "
                f"Colunas disponíveis: {reader.fieldnames}"
            )
        result = {}
        for row in reader:
            chave = _normaliza_chave(row.get(coluna_chave))
            if chave:
                result[chave] = row
        return result


def carregar_vinculos_manuais(path: Path | None) -> dict[str, str]:
    """CSV com duas colunas: identificador_poligono, numero_contribuinte
    — usado para os polígonos que não trazem a chave no arquivo original."""
    if path is None:
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        cols = reader.fieldnames or []
        if len(cols) < 2:
            raise SystemExit(f"{path} precisa ter 2 colunas: identificador_poligono, chave")
        id_col, chave_col = cols[0], cols[1]
        return {
            row[id_col].strip(): _normaliza_chave(row[chave_col])
            for row in reader
            if row.get(id_col, "").strip()
        }


def _identificador_poligono(feature: dict, indice: int) -> str:
    """Um identificador estável o suficiente para usar no CSV de
    vínculos manuais — usa o "nome" do KML se existir, senão o índice."""
    props = feature.get("properties") or {}
    nome = props.get("nome") or props.get("name")
    return nome if nome else f"poligono-{indice}"


def vincular(
    poligonos_geojson: dict,
    coluna_chave: str,
    atributos_por_chave: dict[str, dict],
    complemento_por_chave: dict[str, dict],
    vinculos_manuais: dict[str, str],
) -> tuple[dict, list[dict]]:
    features_saida = []
    pendencias = []

    for i, feature in enumerate(poligonos_geojson.get("features", [])):
        props = dict(feature.get("properties") or {})
        identificador = _identificador_poligono(feature, i)

        chave = _normaliza_chave(props.get(coluna_chave))
        origem_chave = "poligono"
        if not chave:
            chave = vinculos_manuais.get(identificador)
            origem_chave = "vinculo_manual"

        if not chave:
            centro = _centroide_aproximado(feature.get("geometry") or {})
            pendencias.append(
                {
                    "identificador_poligono": identificador,
                    "motivo": "sem numero de chave no poligono nem em vinculos-manuais",
                    "lon_aproximado": centro[0] if centro else "",
                    "lat_aproximado": centro[1] if centro else "",
                }
            )
            props["_vinculado"] = False
            features_saida.append({**feature, "properties": props})
            continue

        atributos = atributos_por_chave.get(chave)
        complemento = complemento_por_chave.get(chave)

        if atributos is None:
            pendencias.append(
                {
                    "identificador_poligono": identificador,
                    "motivo": f"chave '{chave}' ({origem_chave}) não encontrada no CSV de atributos",
                    "lon_aproximado": "",
                    "lat_aproximado": "",
                }
            )

        merged_props = {**props, **(atributos or {}), **(complemento or {})}
        merged_props["_vinculado"] = atributos is not None
        merged_props["_origem_chave"] = origem_chave
        features_saida.append({**feature, "properties": merged_props})

    return {"type": "FeatureCollection", "features": features_saida}, pendencias


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("poligonos", type=Path, help="Arquivo .geojson, .kml ou .kmz com os polígonos")
    parser.add_argument("atributos_csv", type=Path, help="CSV exportado do banco existente")
    parser.add_argument("--chave", default="numero_contribuinte", help="Nome da coluna/propriedade usada para vincular (padrão: numero_contribuinte)")
    parser.add_argument("--complemento", type=Path, default=None, help="CSV opcional com campos novos, exclusivos do SIG View, na mesma chave")
    parser.add_argument("--vinculos-manuais", type=Path, default=None, help="CSV opcional (identificador_poligono, chave) para polígonos sem a chave original")
    parser.add_argument("--saida", type=Path, required=True, help="Caminho do .geojson de saída (ex: ../data/layers/imoveis.geojson)")
    parser.add_argument("--pendencias", type=Path, default=Path("pendencias.csv"), help="Caminho do CSV de pendências (padrão: pendencias.csv)")
    args = parser.parse_args()

    poligonos = carregar_poligonos(args.poligonos)
    atributos = carregar_csv_por_chave(args.atributos_csv, args.chave)
    complemento = carregar_csv_por_chave(args.complemento, args.chave) if args.complemento else {}
    vinculos_manuais = carregar_vinculos_manuais(args.vinculos_manuais)

    resultado, pendencias = vincular(poligonos, args.chave, atributos, complemento, vinculos_manuais)

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(resultado["features"])
    vinculados = sum(1 for f in resultado["features"] if f["properties"].get("_vinculado"))
    print(f"Camada gerada: {args.saida}")
    print(f"  {vinculados}/{total} polígonos vinculados a um registro do banco")

    if pendencias:
        with args.pendencias.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["identificador_poligono", "motivo", "lon_aproximado", "lat_aproximado"])
            writer.writeheader()
            writer.writerows(pendencias)
        print(f"  {len(pendencias)} pendências salvas em {args.pendencias} (revise e preencha vinculos-manuais.csv aos poucos)")
    else:
        print("  Nenhuma pendência — tudo vinculado!")


if __name__ == "__main__":
    main()
