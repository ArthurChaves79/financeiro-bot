"""Reconhecimento automático de nomes de propriedade "conhecidos" numa
feature GeoJSON/KML — mesma ideia (e mesmas listas de candidatos, onde
existem dos dois lados) do `CAMPOS_CONHECIDOS` do frontend
(frontend/static/js/app.js), portado pra cá porque
scripts/indexar_camadas.py roda no backend, sem acesso ao JS do
navegador. As duas listas não compartilham arquivo (Python x
JavaScript) — se um dia mudar candidatos de um lado, considere mudar do
outro também.

Aceita variações comuns de nome de propriedade (sem acento/maiúscula/
separador) em vez de exigir bater exatamente um nome fixo de coluna —
funciona tanto com o que o SIG Editor de Lotes (irmão deste programa)
exporta (setor/quadra/lote/contribuinte/matricula/transcricoes/
loteamento/enderecos/observacoes) quanto com GeoJSON/KML de outras
origens (QGIS, ArcGIS, banco relacional etc.).

Usado por scripts/indexar_camadas.py pra indexar uma camada pro busca
SEM precisar que o usuário digite, na tela de Manutenção, o nome exato
de cada propriedade da própria camada — algo que, na prática, quase
ninguém sabe de cabeça (é preciso abrir o .geojson num editor de texto
ou usar scripts/ver_propriedades.py pra descobrir)."""
from __future__ import annotations

import re
import unicodedata

# "bairro"/"cidade" são candidatos NOVOS aqui — não existem no
# CAMPOS_CONHECIDOS do frontend porque a barra de detalhes de
# Imóveis/Loteamento nunca mostra essas 2 (não fazem parte do que o SIG
# Editor de Lotes exporta), mas fazem sentido pra indexação de busca de
# camadas vindas de outra origem (ex: um GeoJSON de bairros do
# GeoSampa).
CAMPOS_CONHECIDOS: dict[str, list[str]] = {
    "setor": ["setor"],
    "quadra": ["quadra"],
    "lote": ["lote"],
    "contribuinte": ["contribuinte", "numerocontribuinte", "numcontribuinte", "inscricaoimobiliaria", "inscricao"],
    "matricula": ["matricula", "nmatricula", "numeromatricula"],
    "transcricao": ["transcricao", "transcricoes", "ntranscricao", "numerotranscricao"],
    "enderecoCompleto": ["enderecos", "endereco", "enderecocompleto", "endereco_completo"],
    "tipoLogradouro": ["tipologradouro", "tipoendereco", "tipo"],
    "logradouro": ["logradouro", "rua", "nomelogradouro"],
    "numeroEndereco": ["numeroendereco", "nendereco", "numero", "num"],
    "loteamento": ["loteamento", "nomeloteamento"],
    "bairro": ["bairro", "nomebairro"],
    "cidade": ["cidade", "municipio", "nomecidade"],
    "observacoes": ["observacoes", "observacao", "obs"],
}


def normalizar_chave(chave: str) -> str:
    """Sem acento/maiúscula/separador — mesma normalização de
    normalizarChave() no frontend, pra "Número Contribuinte" e
    "numero_contribuinte" baterem com o mesmo candidato."""
    sem_acento = unicodedata.normalize("NFKD", chave).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def texto_de(valor: object) -> str:
    """Converte qualquer valor de propriedade pra texto pesquisável —
    inclusive lista/tupla (comum quando uma feature tem mais de um
    endereço/transcrição), juntando com vírgula em vez do repr cru do
    Python."""
    if valor is None:
        return ""
    if isinstance(valor, (list, tuple)):
        return ", ".join(t for t in (texto_de(v) for v in valor) if t)
    return str(valor).strip()


def indexar_propriedades(props: dict) -> dict[str, str]:
    """chave normalizada -> nome ORIGINAL da propriedade (a primeira, em
    caso de colisão após normalizar)."""
    indice: dict[str, str] = {}
    for chave in props:
        indice.setdefault(normalizar_chave(str(chave)), chave)
    return indice


def pegar_propriedade(props: dict, indice: dict[str, str], conceito: str) -> str:
    """Primeiro valor não-vazio de `props` cujo nome (normalizado) bate
    com algum candidato de `conceito` (ex: "contribuinte") em
    CAMPOS_CONHECIDOS. "" se nenhum candidato existir ou tiver valor."""
    for candidato in CAMPOS_CONHECIDOS.get(conceito, ()):
        nome_original = indice.get(candidato)
        if nome_original is not None:
            valor = texto_de(props.get(nome_original))
            if valor:
                return valor
    return ""


def contribuinte_de(props: dict, indice: dict[str, str] | None = None) -> str:
    """Número do contribuinte pronto, ou montado a partir de
    Setor.Quadra.Lote quando não há um campo de contribuinte direto —
    mesma prioridade de montarLinhasPainel() no frontend."""
    indice = indice if indice is not None else indexar_propriedades(props)
    direto = pegar_propriedade(props, indice, "contribuinte")
    if direto:
        return direto
    setor = pegar_propriedade(props, indice, "setor")
    quadra = pegar_propriedade(props, indice, "quadra")
    lote = pegar_propriedade(props, indice, "lote")
    return ".".join(p for p in (setor, quadra, lote) if p) if setor else ""


def endereco_de(props: dict, indice: dict[str, str] | None = None) -> str:
    """Endereço pronto pra exibir/buscar — mesma prioridade de
    _enderecoResumo() no frontend, MENOS o fallback pro nome do
    Loteamento de lá — aqui o valor vai pra coluna "logradouro" do
    índice de busca, que fica concatenada com "rotulo" (ver
    app/search.py); "rotulo" (rotulo_pesquisavel_de, abaixo) já inclui
    o nome do Loteamento por conta própria — sem essa diferença, uma
    Quadra de Loteamento apareceria com o nome REPETIDO duas vezes na
    busca ("Meu Loteamento — Meu Loteamento")."""
    indice = indice if indice is not None else indexar_propriedades(props)
    pronto = pegar_propriedade(props, indice, "enderecoCompleto")
    if pronto:
        return pronto
    tipo = pegar_propriedade(props, indice, "tipoLogradouro")
    logradouro = pegar_propriedade(props, indice, "logradouro")
    numero = pegar_propriedade(props, indice, "numeroEndereco")
    endereco = " ".join(p for p in (tipo, logradouro) if p).strip()
    if numero:
        endereco = f"{endereco}, {numero}" if endereco else numero
    return endereco


def rotulo_pesquisavel_de(props: dict) -> str:
    """Texto pesquisável EXTRA pra uma feature (contribuinte/setor.
    quadra.lote, matrícula, transcrição, loteamento) — usado como
    "rotulo" na indexação automática (ver scripts/indexar_camadas.py).
    NÃO inclui o endereço (endereco_de) de propósito: ele já vai pra
    coluna "logradouro" própria, que a busca (FTS) já cobre sozinha —
    juntar aqui de novo faria o mesmo endereço aparecer REPETIDO no
    resultado da busca (ver app/search.py, que concatena
    logradouro+bairro+cidade com "rotulo" pra montar o texto exibido)."""
    indice = indexar_propriedades(props)
    partes = [
        contribuinte_de(props, indice),
        pegar_propriedade(props, indice, "matricula"),
        pegar_propriedade(props, indice, "transcricao"),
        pegar_propriedade(props, indice, "loteamento"),
    ]
    vistos: list[str] = []
    for parte in partes:
        if parte and parte not in vistos:
            vistos.append(parte)
    return " — ".join(vistos)


def bairro_de(props: dict) -> str:
    return pegar_propriedade(props, indexar_propriedades(props), "bairro")


def cidade_de(props: dict) -> str:
    return pegar_propriedade(props, indexar_propriedades(props), "cidade")
