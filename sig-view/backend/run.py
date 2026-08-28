"""Ponto de entrada usado para gerar o SigView.exe (via PyInstaller) e
também como alternativa a `uvicorn app.main:app` na linha de comando.

Sobe o servidor e abre a interface numa janela própria do programa (via
pywebview, usando o WebView2 que já vem no Windows — sem precisar
instalar nem embutir um navegador inteiro). Se o pywebview não estiver
disponível por algum motivo, cai de volta pro modo antigo: abre no
navegador padrão e mantém o terminal aberto.
"""
from __future__ import annotations

import sys
from pathlib import Path

# O .exe é gerado com --windowed (sem a telinha de console/cmd atrás da
# janela do programa) — no Windows isso deixa sys.stdout/stderr como
# None, e qualquer coisa que tente escrever neles (incluindo o próprio
# log do uvicorn) quebra com AttributeError. Redireciona pra um arquivo
# de log ao lado do .exe antes de mais nada, só quando isso realmente
# acontece — rodando via `python run.py` (modo terminal normal, com
# console) continua imprimindo no terminal, sem mudar nada.
if sys.stdout is None or sys.stderr is None:
    _base_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    _log_dir = _base_dir / "data"
    _log_dir.mkdir(parents=True, exist_ok=True)
    _log_file = open(_log_dir / "sigview.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _log_file
    sys.stderr = sys.stderr or _log_file

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
        # debug=True habilita clicar com o botao direito -> "Inspecionar"
        # dentro da propria janela do programa (equivalente ao F12 do
        # navegador) - util pra diagnosticar problemas de carregamento.
        webview.start(debug=True)  # bloqueia até a janela ser fechada; o programa encerra junto
    else:
        webbrowser.open(url)
        # sem janela própria, o processo precisa continuar vivo servindo o
        # backend enquanto a aba do navegador estiver aberta — só encerra
        # se fecharem esta janela de terminal (Ctrl+C).
        server_thread.join()


if __name__ == "__main__":
    main()
