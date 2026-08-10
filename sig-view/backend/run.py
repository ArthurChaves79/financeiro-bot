"""Ponto de entrada usado para gerar o SigView.exe (via PyInstaller) e
também como alternativa a `uvicorn app.main:app` na linha de comando.

Sobe o servidor e já abre o navegador padrão automaticamente — pensado
para quem só quer dar dois cliques e usar, sem lidar com terminal.
"""
from __future__ import annotations

import threading
import time
import webbrowser

import uvicorn

from app.config import settings
from app.main import app


def _open_browser() -> None:
    time.sleep(1.5)  # dá tempo do servidor subir antes de abrir a aba
    host = "localhost" if settings.host == "0.0.0.0" else settings.host
    webbrowser.open(f"http://{host}:{settings.port}")


def main() -> None:
    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
