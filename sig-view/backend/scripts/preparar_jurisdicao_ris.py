#!/usr/bin/env python3
"""Converte o KML/KMZ de jurisdição dos Registros de Imóveis (ex: o
"Registros de Imóveis de SP.kmz" do GeoSampa) pro formato que o SIG View
espera pra camada "Jurisdição" — um .geojson por RI (Registro de
Imóveis), com todos os subdistritos daquele RI juntos no mesmo arquivo
(mesma cor, mesmo grupo no painel de camadas).

Por que um script separado, em vez de usar converter_kml_para_geojson.py:
esse tipo de arquivo (exportado do Google Earth) já vem com uma cor
própria em cada Placemark (herdada da sessão de desenho de quem montou o
KML) — geralmente uma cor DIFERENTE por subdistrito, mesmo dentro do
mesmo RI, o que ia contra o que a gente quer aqui (mesma cor por RI,
subdistritos só como "peças" do mesmo polígono lógico). Este script
ignora essas cores originais e recalcula uma cor própria, determinística,
por RI — e já deixa o contorno fino e o preenchimento discreto, do jeito
que faz sentido pra uma camada de fundo (que fica embaixo dos lotes,
loteamentos etc., só de referência).

A cor de cada RI é calculada a partir do NOME do RI (não da ordem em que
aparece no arquivo) — então adicionar/remover um RI no arquivo de origem
não embaralha a cor dos outros que já estavam lá.

Uso:
    python scripts/preparar_jurisdicao_ris.py "Registros de Imóveis de SP.kmz"
    python scripts/preparar_jurisdicao_ris.py entrada.kml --saida "\\servidor\sigview\layers\Jurisdicao"
    python scripts/preparar_jurisdicao_ris.py entrada.kmz --opacidade 0.2 --espessura-contorno 1.5
"""
from __future__ import annotations

import argparse
import colorsys
import json
import re
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import kml as kml_module  # noqa: E402

_CARACTERES_INVALIDOS_WINDOWS = re.compile(r'[<>:"/\\|?*]')

# Chaves de estilo que o parser de KML do SIG View já resolve sozinho
# (ver app/kml.py:_style_from_element) — se deixarmos elas como vieram
# do arquivo original, a cor "de sessão de desenho" de cada subdistrito
# ganharia da cor por RI que a gente calcula aqui embaixo (o front-end
# sempre prioriza a cor da própria feature, ver corComFallback em
# app.js). Por isso elas são removidas antes de aplicar a cor do RI.
_CHAVES_DE_ESTILO_A_SUBSTITUIR = (
    "_cor_preenchimento", "_opacidade_preenchimento", "_sem_preenchimento",
    "_cor_linha", "_opacidade_linha", "_largura_linha",
    "_cor_ponto",
    # padrão "simplestyle" (fill/stroke) e campos crus de cor — não
    # costumam aparecer num export do Google Earth, mas é barato garantir.
    "fill", "fill-opacity", "stroke", "stroke-width", "stroke-opacity",
    "marker-color", "cor", "Cor", "COR",
)


def _nome_do_ri(caminho: tuple[str, ...]) -> str:
    """O nome do RI é o último nível de pasta do KML (o resto, tipo
    'Registros de Imóveis de SP', é só o agrupamento raiz do arquivo)."""
    bruto = caminho[-1] if caminho else "RI desconhecido"
    if bruto.lower().endswith(".kml"):
        bruto = bruto[:-4]
    return bruto.strip()


def _nome_arquivo_seguro(nome: str) -> str:
    limpo = _CARACTERES_INVALIDOS_WINDOWS.sub("_", nome).strip().rstrip(".")
    return limpo or "RI"


def _cor_para_ri(nome_ri: str) -> str:
    """Cor determinística por nome de RI (mesmo RI = mesma cor sempre,
    mesmo rodando de novo ou depois de editar o arquivo de origem).
    Usa matizes espalhadas (HSL) em vez da paleta fixa de 10 cores do
    resto do programa porque aqui pode ter bem mais de 10 RIs."""
    matiz = (zlib.crc32(nome_ri.encode("utf-8")) % 360) / 360.0
    r, g, b = colorsys.hls_to_rgb(matiz, 0.48, 0.6)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("arquivo", type=Path, help="Arquivo .kml ou .kmz de entrada (jurisdição dos RIs)")
    parser.add_argument(
        "--saida", type=Path, default=None,
        help="Pasta de saída (padrão: uma subpasta 'Jurisdicao' do lado do arquivo de entrada). "
             "Coloque essa pasta dentro da 'Pasta de camadas' configurada no SIG View.",
    )
    parser.add_argument(
        "--opacidade", type=float, default=0.15,
        help="Opacidade do preenchimento, de 0 a 1 (padrão: 0.15 — discreto mas visível)",
    )
    parser.add_argument(
        "--espessura-contorno", type=float, default=1,
        help="Espessura do contorno em pixels (padrão: 1 — o mais fino que ainda fica visível)",
    )
    args = parser.parse_args()

    if not args.arquivo.exists():
        sys.exit(f"Arquivo não encontrado: {args.arquivo}")
    if not 0 <= args.opacidade <= 1:
        sys.exit("--opacidade precisa estar entre 0 e 1")

    suffix = args.arquivo.suffix.lower()
    if suffix == ".kml":
        grupos, network_links = kml_module.parse_kml_full(args.arquivo.read_bytes())
    elif suffix == ".kmz":
        grupos, network_links = kml_module.parse_kmz_full(args.arquivo.read_bytes())
    else:
        sys.exit(f"Formato não suportado: {suffix} (use .kml ou .kmz)")

    if network_links:
        total_links = sum(len(v) for v in network_links.values())
        print(f"[aviso] {total_links} <NetworkLink> encontrado(s) no arquivo — não são seguidos por este "
              "script (só converte o conteúdo que já está no próprio arquivo).")

    pasta_saida = args.saida or (args.arquivo.parent / "Jurisdicao")
    pasta_saida.mkdir(parents=True, exist_ok=True)

    gerados = 0
    avisos_nome = []
    for caminho, geojson in grupos:
        features = geojson.get("features", [])
        if not features:
            continue

        nome_ri = _nome_do_ri(caminho)
        cor = _cor_para_ri(nome_ri)

        # "Oficial de Registro" aparecendo mais de uma vez no nome é
        # sinal de que duas pastas do KML original ficaram coladas sem
        # separador (já vi isso acontecer no arquivo do GeoSampa) — não
        # dá pra saber automaticamente onde cortar, então só avisa pra
        # conferir/corrigir manualmente o nome da pasta no KML de origem.
        if nome_ri.count("Oficial de Registro") > 1:
            avisos_nome.append(nome_ri)

        for feature in features:
            props = feature.get("properties", {})
            for chave in _CHAVES_DE_ESTILO_A_SUBSTITUIR:
                props.pop(chave, None)
            props["_cor_preenchimento"] = cor
            props["_opacidade_preenchimento"] = args.opacidade
            props["_cor_linha"] = cor
            props["_largura_linha"] = args.espessura_contorno
            props["ri"] = nome_ri

            # No arquivo do GeoSampa, o <name> de cada Placemark quase
            # sempre repete o nome do RI inteiro (ou vem em branco, tipo
            # "Polígono sem título") — quem realmente identifica o
            # subdistrito é o campo "ID" (extraído da tabela dentro do
            # <description>, ex: "9° SUBDISTRITO - VILA MARIANA" ou
            # "DISTRITO - GUAIANASES"). Por isso o "nome" da feature é
            # recalculado a partir do ID, pra mostrar um nome útil no
            # painel em vez do nome do RI repetido.
            id_bruto = props.get("ID")
            if id_bruto:
                nome_subdistrito = str(id_bruto).rsplit(" - ", 1)[-1].strip().title()
                if nome_subdistrito:
                    props["nome"] = nome_subdistrito
            elif not props.get("nome") or props.get("nome") == "Polígono sem título":
                props["nome"] = "(sem identificação)"

        destino = pasta_saida / f"{_nome_arquivo_seguro(nome_ri)}.geojson"
        destino.write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")
        print(f"Gerado {destino.relative_to(pasta_saida)} — {nome_ri} — {len(features)} subdistrito(s) — cor {cor}")
        gerados += 1

    print(f"\n{gerados} arquivo(s) .geojson gerado(s) em {pasta_saida}, um por RI.")
    print("Coloque essa pasta dentro da 'Pasta de camadas' do SIG View (ex: como 'Jurisdicao') "
          "pra ela aparecer como um grupo próprio no painel de camadas.")
    if avisos_nome:
        print("\n[aviso] Nome de RI com 'Oficial de Registro' repetido (provável colagem de duas pastas "
              "sem separador no KML de origem) — confira/corrija manualmente:")
        for nome in avisos_nome:
            print(f"  - {nome}")


if __name__ == "__main__":
    main()
