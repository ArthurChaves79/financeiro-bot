"""
SIG Condomínios — lançador desktop.

Abre o app (index.html / app.js / styles.css) numa janela nativa usando
pywebview, sem precisar de navegador nem de servidor local. Pensado para
ser empacotado com PyInstaller em um único .exe (veja build.bat).

Uso em desenvolvimento:
    pip install -r requirements.txt
    python app.py
"""

import os
import sys

import webview

APP_TITLE = "SIG Condomínios"


def resource_path(relative_path):
    """Caminho para um arquivo do app, tanto rodando do código-fonte
    quanto rodando de dentro do .exe gerado pelo PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", None)
    if base_path is None:
        # desktop/app.py -> desktop/ -> condominios/
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def storage_dir():
    """Pasta onde os dados do app (localStorage do navegador embutido)
    ficam salvos entre uma execução e outra."""
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(appdata, "SIGCondominios")
    os.makedirs(path, exist_ok=True)
    return path


def main():
    index_path = resource_path("index.html")

    webview.create_window(
        APP_TITLE,
        index_path,
        width=440,
        height=880,
        min_size=(380, 640),
    )
    # private_mode=False + storage_path faz o localStorage persistir
    # entre uma abertura e outra do programa.
    webview.start(storage_path=storage_dir(), private_mode=False)


if __name__ == "__main__":
    main()
