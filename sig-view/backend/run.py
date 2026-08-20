"""Ponto de entrada usado para gerar o SigView.exe (via PyInstaller) e
também como alternativa a `uvicorn app.main:app` na linha de comando.

Sobe o servidor e abre a interface numa janela própria do programa (via
pywebview, usando o WebView2 que já vem no Windows — sem precisar
instalar nem embutir um navegador inteiro). Se o pywebview não estiver
disponível por algum motivo, cai de volta pro modo antigo: abre no
navegador padrão e mantém o terminal aberto.
"""
from __future__ import annotations

import threading
import time
import webbrowser

import uvicorn

from app.config import settings
from app.main import app


def _run_server() -> None:
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


def main() -> None:
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()
    time.sleep(1.5)  # dá tempo do servidor subir antes de abrir a janela/aba

    host = "localhost" if settings.host == "0.0.0.0" else settings.host
    url = f"http://{host}:{settings.port}"

    try:
        import webview
    except ImportError:
        webview = None

    if webview is not None:
        webview.create_window("SIG View", url, width=1366, height=850, min_size=(900, 600))
        webview.start()  # bloqueia até a janela ser fechada; o programa encerra junto
    else:
        webbrowser.open(url)
        # sem janela própria, o processo precisa continuar vivo servindo o
        # backend enquanto a aba do navegador estiver aberta — só encerra
        # se fecharem esta janela de terminal (Ctrl+C).
        server_thread.join()


if __name__ == "__main__":
    main()
