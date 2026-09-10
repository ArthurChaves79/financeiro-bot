#!/usr/bin/env python3
"""Mostra as colunas e as primeiras linhas de uma planilha .xlsx — só
pra dar uma olhada no que tem dentro antes de escrever um conversor
específico (ex: o "Índice de Logradouros" do GeoSampa, que costuma vir
só em .xlsx, sem a geometria da rua).

Lê o .xlsx sem precisar instalar nada (um .xlsx é só um .zip com XML por
dentro — mesma ideia usada em app/kml.py pro KML/KMZ), então funciona
até numa máquina sem internet.

Uso:
    python scripts/ver_planilha.py indice_logradouros.xlsx
    python scripts/ver_planilha.py indice_logradouros.xlsx --linhas 20
    python scripts/ver_planilha.py indice_logradouros.xlsx --aba 2
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def _texto_de_si(si_el: ET.Element) -> str:
    """Um item de shared string pode ser <t>texto</t> direto, ou
    <r><t>pedaço</t></r> repetido (texto com formatação mista) — junta
    tudo, na ordem."""
    partes = [t.text or "" for t in si_el.iter(f"{{{_NS['m']}}}t")]
    return "".join(partes)


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return [_texto_de_si(si) for si in root.findall("m:si", _NS)]


def _abas_disponiveis(z: zipfile.ZipFile) -> list[tuple[str, str]]:
    """Lista (nome_da_aba, caminho_do_arquivo_dentro_do_zip), na ordem
    em que aparecem na planilha."""
    workbook = ET.fromstring(z.read("xl/workbook.xml"))
    rels_root = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    rid_para_target = {
        rel.get("Id"): rel.get("Target")
        for rel in rels_root.findall(f"{{{rel_ns}}}Relationship")
    }

    abas = []
    for sheet in workbook.findall("m:sheets/m:sheet", _NS):
        nome = sheet.get("name", "")
        rid = sheet.get(f"{{{_NS['r']}}}id")
        target = rid_para_target.get(rid, "")
        caminho = target if target.startswith("xl/") else f"xl/{target}"
        abas.append((nome, caminho))
    return abas


def _coluna_para_indice(referencia_celula: str) -> int:
    """'C7' -> 2 (índice da coluna, começando em 0). Ignora o número da
    linha, só usa as letras iniciais."""
    letras = re.match(r"[A-Z]+", referencia_celula).group()
    indice = 0
    for letra in letras:
        indice = indice * 26 + (ord(letra) - ord("A") + 1)
    return indice - 1


def ler_planilha(xlsx_path: Path, indice_aba: int = 0) -> tuple[str, list[list[str]]]:
    """Devolve (nome_da_aba, linhas) — cada linha é uma lista de células
    em texto, já alinhadas por posição (célula vazia vira "")."""
    with zipfile.ZipFile(xlsx_path) as z:
        strings = _shared_strings(z)
        abas = _abas_disponiveis(z)
        if not abas:
            sys.exit("Não achei nenhuma aba nessa planilha (arquivo .xlsx corrompido ou em formato inesperado?).")
        if indice_aba >= len(abas):
            sys.exit(f"A planilha só tem {len(abas)} aba(s) (pedido: aba nº {indice_aba + 1}).")
        nome_aba, caminho_aba = abas[indice_aba]

        sheet_root = ET.fromstring(z.read(caminho_aba))
        linhas_xml = sheet_root.findall("m:sheetData/m:row", _NS)

        linhas = []
        for row_el in linhas_xml:
            celulas = row_el.findall("m:c", _NS)
            if not celulas:
                linhas.append([])
                continue
            max_col = max(_coluna_para_indice(c.get("r", "A1")) for c in celulas)
            linha = [""] * (max_col + 1)
            for c in celulas:
                idx = _coluna_para_indice(c.get("r", "A1"))
                tipo = c.get("t")
                v_el = c.find("m:v", _NS)
                if tipo == "s":  # referência pra shared string
                    valor = strings[int(v_el.text)] if v_el is not None and v_el.text else ""
                elif tipo == "inlineStr":
                    is_el = c.find("m:is", _NS)
                    valor = _texto_de_si(is_el) if is_el is not None else ""
                else:  # número, booleano ou fórmula com resultado em texto — pega bruto
                    valor = v_el.text if v_el is not None else ""
                linha[idx] = valor or ""
            linhas.append(linha)
        return nome_aba, linhas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xlsx_path", type=Path, help="Planilha .xlsx a inspecionar")
    parser.add_argument("--aba", type=int, default=1, metavar="N", help="Número da aba a ler, começando em 1 (padrão: 1, a primeira)")
    parser.add_argument("--linhas", type=int, default=10, metavar="N", help="Quantas linhas de dados mostrar além do cabeçalho (padrão: 10)")
    args = parser.parse_args()

    if not args.xlsx_path.exists():
        sys.exit(f"Arquivo não encontrado: {args.xlsx_path}")

    nome_aba, linhas = ler_planilha(args.xlsx_path, args.aba - 1)
    if not linhas:
        sys.exit(f"A aba '{nome_aba}' está vazia.")

    cabecalho = linhas[0]
    dados = linhas[1:]

    print(f"Aba: {nome_aba}")
    print(f"Total de linhas de dados (sem contar o cabeçalho): {len(dados)}")
    print()
    print("Colunas encontradas (na ordem):")
    for i, nome_coluna in enumerate(cabecalho):
        print(f"  {i + 1}. {nome_coluna!r}")
    print()
    print(f"Primeiras {min(args.linhas, len(dados))} linha(s) de dados:")
    for linha in dados[: args.linhas]:
        pares = ", ".join(f"{cabecalho[i] if i < len(cabecalho) else f'col{i}'}={v!r}" for i, v in enumerate(linha))
        print(f"  {{{pares}}}")


if __name__ == "__main__":
    main()
