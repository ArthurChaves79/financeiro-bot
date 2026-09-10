"""Checagem de versão nova do SIG View — 100% via rede local, sem
internet (os 78 computadores rodam offline).

Pra usar: peça pro TI/quem administra deixar, junto com o `.exe` mais
novo numa pasta de rede, um arquivo `versao.txt` só com o número da
versão (ex: "1.1.0") — ou um `versao.json` com `{"versao": "1.1.0"}`,
se quiser incluir notas também. Aponte "Verificar versão em" (⚙
Configurações) pra esse arquivo. O programa só AVISA que tem uma
versão mais nova — não baixa nem substitui nada sozinho (trocar um
.exe rodando é arriscado, melhor deixar pra quem instala fazer isso
manualmente ou redistribuir a pasta como sempre foi feito).
"""
from __future__ import annotations

import json
from pathlib import Path

# Atualize isso a cada nova versão distribuída (junto com o arquivo de
# versão que fica na pasta de rede, pra checagem funcionar).
VERSAO_ATUAL = "1.0.0"


def _versao_para_tupla(versao: str) -> tuple[int, ...]:
    partes = []
    for pedaco in versao.strip().split("."):
        digitos = "".join(c for c in pedaco if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    return tuple(partes)


def versao_mais_nova(a: str, b: str) -> bool:
    """True se a versão `a` for mais nova que `b` (ex: "1.2.0" > "1.1.9")."""
    ta, tb = _versao_para_tupla(a), _versao_para_tupla(b)
    tamanho = max(len(ta), len(tb))
    ta = ta + (0,) * (tamanho - len(ta))
    tb = tb + (0,) * (tamanho - len(tb))
    return ta > tb


def checar_versao_disponivel(caminho_arquivo_versao: Path | None) -> dict:
    """Lê o arquivo de versão na pasta de rede (se configurado) e
    compara com VERSAO_ATUAL. Nunca levanta exceção — pasta de rede
    fora do ar, caminho errado, arquivo ausente etc. só resultam em
    "sem atualização disponível", sem quebrar o programa nem aparecer
    como erro pro usuário."""
    resultado = {
        "versao_atual": VERSAO_ATUAL,
        "versao_disponivel": None,
        "atualizacao_disponivel": False,
    }
    if not caminho_arquivo_versao:
        return resultado

    try:
        texto = Path(caminho_arquivo_versao).read_text(encoding="utf-8").strip()
    except OSError:
        return resultado

    versao_disponivel = texto
    if texto.startswith("{"):
        try:
            versao_disponivel = json.loads(texto).get("versao", "")
        except json.JSONDecodeError:
            return resultado

    if not versao_disponivel:
        return resultado

    resultado["versao_disponivel"] = versao_disponivel
    resultado["atualizacao_disponivel"] = versao_mais_nova(versao_disponivel, VERSAO_ATUAL)
    return resultado
