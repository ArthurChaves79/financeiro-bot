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

import base64
import binascii
import os
import threading
import time
import webbrowser

import uvicorn

from app.config import settings
from app.main import app

# No backend WebView2 (Windows), debug=True do pywebview não só habilita
# o "Inspecionar" pelo botão direito — em várias versões ele já abre a
# janela do DevTools sozinho, junto com o programa. Isso é útil enquanto
# se está desenvolvendo, mas não faz sentido ir pros 78 computadores da
# empresa assim. Fica desligado por padrão; quem precisar diagnosticar
# algo é só abrir com a variável de ambiente SIGVIEW_DEBUG=1 antes.
DEBUG = os.environ.get("SIGVIEW_DEBUG") == "1"


def _run_server() -> None:
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


class JsApi:
    """Ponte JS -> Python usada pelo pywebview (`window.pywebview.api.*`
    do lado do navegador). Só tem o que precisa de um recurso nativo do
    Windows que o navegador embutido sozinho não dá pra fazer direito
    — aqui, abrir a janela "Salvar como" de verdade (o download comum
    de navegador é inconsistente numa janela sem toda a interface de um
    navegador de verdade em volta)."""

    def _abrir_dialogo_salvar(self, nome_sugerido: str, file_types: tuple[str, ...]) -> str | None:
        import webview  # import local: só existe quando esta classe é usada (modo janela própria)

        janela = webview.windows[0]
        caminho_escolhido = janela.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=nome_sugerido,
            file_types=file_types,
        )
        if not caminho_escolhido:
            return None
        return caminho_escolhido if isinstance(caminho_escolhido, str) else caminho_escolhido[0]

    def salvar_imagem_png(self, data_url: str, nome_sugerido: str) -> dict:
        try:
            _cabecalho, base64_dados = data_url.split(",", 1)
            dados = base64.b64decode(base64_dados)
        except (ValueError, binascii.Error) as exc:
            return {"ok": False, "erro": f"Imagem inválida: {exc}"}

        destino = self._abrir_dialogo_salvar(nome_sugerido, ("Imagem PNG (*.png)",))
        if destino is None:
            return {"ok": False, "cancelado": True}

        try:
            Path(destino).write_bytes(dados)
        except OSError as exc:
            return {"ok": False, "erro": str(exc)}
        return {"ok": True, "caminho": destino}

    def salvar_texto(self, conteudo: str, nome_sugerido: str) -> dict:
        """Salva texto puro (ex: CSV) num arquivo escolhido pelo usuário.
        Grava com BOM UTF-8 (utf-8-sig) — sem isso, o Excel no Windows
        interpreta acento errado ao abrir um CSV com "Ç"/"Á"/etc."""
        destino = self._abrir_dialogo_salvar(nome_sugerido, ("Planilha CSV (*.csv)", "Texto (*.txt)"))
        if destino is None:
            return {"ok": False, "cancelado": True}

        try:
            Path(destino).write_text(conteudo, encoding="utf-8-sig", newline="")
        except OSError as exc:
            return {"ok": False, "erro": str(exc)}
        return {"ok": True, "caminho": destino}


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
        webview.create_window("SIG View", url, width=1366, height=850, min_size=(900, 600), js_api=JsApi())
        # debug=True (só com SIGVIEW_DEBUG=1) habilita clicar com o botao
        # direito -> "Inspecionar" dentro da propria janela do programa
        # (equivalente ao F12 do navegador) - util pra diagnosticar
        # problemas de carregamento, mas fica desligado por padrão (ver
        # comentário da constante DEBUG acima).
        webview.start(debug=DEBUG)  # bloqueia até a janela ser fechada; o programa encerra junto
    else:
        webbrowser.open(url)
        # sem janela própria, o processo precisa continuar vivo servindo o
        # backend enquanto a aba do navegador estiver aberta — só encerra
        # se fecharem esta janela de terminal (Ctrl+C).
        server_thread.join()


if __name__ == "__main__":
    main()
