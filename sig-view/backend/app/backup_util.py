"""Backup rotativo simples — usado antes de sobrescrever um arquivo
importante (banco de busca, configuração), como proteção extra além
das validações que já existem (ex: build_geocoder_index.py recusa
apagar o índice se o CSV novo vier vazio). Guarda só as últimas N
cópias, sem crescer sem limite."""
from __future__ import annotations

import shutil
from pathlib import Path


def backup_rotativo(arquivo: Path, pasta_backups: Path, manter: int = 3) -> None:
    """Copia `arquivo` pra dentro de `pasta_backups` como `<nome>.bak1`
    (o mais recente), empurrando os backups anteriores pra .bak2,
    .bak3 etc. — o mais antigo (além de `manter`) é descartado. Não
    faz nada se `arquivo` ainda não existir (nada pra fazer backup)."""
    if not arquivo.exists():
        return

    pasta_backups.mkdir(parents=True, exist_ok=True)

    for i in range(manter, 1, -1):
        anterior = pasta_backups / f"{arquivo.name}.bak{i - 1}"
        atual = pasta_backups / f"{arquivo.name}.bak{i}"
        if anterior.exists():
            anterior.replace(atual)

    shutil.copy2(arquivo, pasta_backups / f"{arquivo.name}.bak1")
