#!/usr/bin/env python3
"""Aplica correções de geometria (vindas do seu editor de polígonos) numa
camada já pronta, sem refazer o vínculo com o banco do zero.

Fluxo esperado:
  1. Você já rodou vincular_poligonos.py e tem uma camada pronta
     (ex: data/layers/imoveis.geojson), com atributos vinculados.
  2. No seu editor de polígonos, baixa um lote de trabalho, corrige a
     geometria de alguns (não precisa ser todos — é imprevisível quantos
     vão precisar de ajuste) e exporta o lote corrigido (.geojson,
     .kml ou .kmz).
  3. Roda este script: ele substitui a geometria dos polígonos
     corrigidos na camada existente, casando pelo mesmo identificador
     usado no vínculo (número de contribuinte, ou o nome/identificador
     do polígono como alternativa) — **os atributos já vinculados são
     preservados**, só a geometria muda.
  4. Polígonos do arquivo corrigido que não existiam na camada (lotes
     novos, desmembrados etc.) são adicionados como novos registros,
     ainda sem vínculo — aparecem no relatório de pendências, do mesmo
     jeito que o vincular_poligonos.py já trata.

Uso:
    python scripts/aplicar_correcoes_poligonos.py \\
        data/layers/imoveis.geojson corrigidos.kml \\
        --saida data/layers/imoveis.geojson \\
        --pendencias pendencias_correcao.csv
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
    if valor is None:
        return None
    v = str(valor).strip()
    if not v:
        return None
    return v.lstrip("0") or "0"


def _identificador(feature: dict, indice: int) -> str:
    props = feature.get("properties") or {}
    nome = props.get("nome") or props.get("name")
    return nome if nome else f"poligono-{indice}"


def carregar_geojson_generico(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".geojson":
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix == ".kml":
        return kml_module.parse_kml_bytes(path.read_bytes())
    if suffix == ".kmz":
        return kml_module.parse_kmz_bytes(path.read_bytes())
    raise SystemExit(f"Formato não suportado: {suffix} (use .geojson, .kml ou .kmz)")


def _indexar(features: list[dict], coluna_chave: str) -> tuple[dict[str, int], dict[str, int]]:
    """Devolve dois índices (posição na lista) por chave e por identificador,
    para casar os polígonos corrigidos com os já existentes."""
    por_chave: dict[str, int] = {}
    por_identificador: dict[str, int] = {}
    for i, feature in enumerate(features):
        props = feature.get("properties") or {}
        chave = _normaliza_chave(props.get(coluna_chave))
        if chave and chave not in por_chave:
            por_chave[chave] = i
        ident = _identificador(feature, i)
        if ident not in por_identificador:
            por_identificador[ident] = i
    return por_chave, por_identificador


def aplicar_correcoes(
    base: dict,
    corrigidos: dict,
    coluna_chave: str,
) -> tuple[dict, dict]:
    features_base = list(base.get("features", []))
    por_chave, por_identificador = _indexar(features_base, coluna_chave)

    substituidas = 0
    adicionadas = 0
    novas_pendentes = []

    for i, feature_corrigida in enumerate(corrigidos.get("features", [])):
        props_corrigidas = dict(feature_corrigida.get("properties") or {})
        chave = _normaliza_chave(props_corrigidas.get(coluna_chave))
        ident = _identificador(feature_corrigida, i)

        idx = None
        if chave and chave in por_chave:
            idx = por_chave[chave]
        elif ident in por_identificador:
            idx = por_identificador[ident]

        if idx is not None:
            # Só troca a geometria; preserva os atributos já vinculados.
            # Propriedades novas e não-vazias vindas do editor são
            # incorporadas por cima (ex: se o editor marcar algo como
            # "revisado"), sem apagar o que já estava resolvido.
            props_existentes = dict(features_base[idx].get("properties") or {})
            for k, v in props_corrigidas.items():
                if v not in (None, ""):
                    props_existentes[k] = v
            props_existentes["_geometria_corrigida"] = True
            features_base[idx] = {
                **features_base[idx],
                "geometry": feature_corrigida.get("geometry"),
                "properties": props_existentes,
            }
            substituidas += 1
        else:
            # Polígono novo (não existia na camada) - entra sem vínculo,
            # do mesmo jeito que vincular_poligonos.py trataria.
            props_corrigidas["_vinculado"] = bool(chave)
            props_corrigidas["_novo_da_correcao"] = True
            features_base.append({**feature_corrigida, "properties": props_corrigidas})
            adicionadas += 1
            if not chave:
                centro = _centroide_aproximado(feature_corrigida.get("geometry") or {})
                novas_pendentes.append(
                    {
                        "identificador_poligono": ident,
                        "motivo": "polígono novo (do arquivo corrigido), sem chave de vínculo",
                        "lon_aproximado": centro[0] if centro else "",
                        "lat_aproximado": centro[1] if centro else "",
                    }
                )

    resultado = {"type": "FeatureCollection", "features": features_base}
    resumo = {"substituidas": substituidas, "adicionadas": adicionadas, "pendencias": novas_pendentes}
    return resultado, resumo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("camada_base", type=Path, help="Camada .geojson já existente (com os vínculos já feitos)")
    parser.add_argument("corrigidos", type=Path, help="Arquivo .geojson/.kml/.kmz exportado do editor, com as geometrias corrigidas")
    parser.add_argument("--chave", default="numero_contribuinte", help="Nome da propriedade usada para casar os polígonos (padrão: numero_contribuinte)")
    parser.add_argument("--saida", type=Path, required=True, help="Onde salvar o resultado (pode ser o mesmo caminho de camada_base, para atualizar no lugar)")
    parser.add_argument("--pendencias", type=Path, default=Path("pendencias_correcao.csv"), help="CSV com os polígonos novos que ainda não têm vínculo")
    args = parser.parse_args()

    base = carregar_geojson_generico(args.camada_base)
    corrigidos = carregar_geojson_generico(args.corrigidos)

    resultado, resumo = aplicar_correcoes(base, corrigidos, args.chave)

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Camada atualizada: {args.saida}")
    print(f"  {resumo['substituidas']} polígono(s) com geometria substituída")
    print(f"  {resumo['adicionadas']} polígono(s) novo(s) adicionado(s)")

    if resumo["pendencias"]:
        with args.pendencias.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["identificador_poligono", "motivo", "lon_aproximado", "lat_aproximado"])
            writer.writeheader()
            writer.writerows(resumo["pendencias"])
        print(f"  {len(resumo['pendencias'])} pendência(s) salvas em {args.pendencias}")


if __name__ == "__main__":
    main()
