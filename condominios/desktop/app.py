"""
SIG Condomínios — lançador desktop.

Abre o app (index.html / app.js / styles.css) numa janela nativa usando
pywebview, sem precisar de navegador nem de servidor local. Pensado para
ser empacotado com PyInstaller em um único .exe (veja build.bat).

Os dados ficam sempre num arquivo "condominios-dados.json" ao lado do
.exe (mesmo esquema do SIG Editor) — sem nenhuma tela de configuração.
Isso permite que várias pessoas, cada uma com sua cópia/atalho do .exe
apontando pra mesma pasta de rede, compartilhem os mesmos condomínios.

Uso em desenvolvimento:
    pip install -r requirements.txt
    python app.py
"""

import json
import os
import sys
import tempfile

import webview

APP_TITLE = "SIG Condomínios"
NOME_ARQUIVO_DADOS = "condominios-dados.json"


def resource_path(relative_path):
    """Caminho para um arquivo do app, tanto rodando do código-fonte
    quanto rodando de dentro do .exe gerado pelo PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", None)
    if base_path is None:
        # desktop/app.py -> desktop/ -> condominios/
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def pasta_do_executavel():
    """Pasta onde o .exe (ou, em desenvolvimento, este script) está
    realmente localizado — nunca a pasta temporária do PyInstaller."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def caminho_dados_padrao():
    return os.path.join(pasta_do_executavel(), NOME_ARQUIVO_DADOS)


def storage_dir():
    """Pasta onde o perfil do navegador embutido (cache, etc.) fica —
    não é mais onde os dados dos condomínios são salvos, mas ainda é
    usada para o navegador manter configurações entre uma abertura e
    outra."""
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(appdata, "SIGCondominios")
    os.makedirs(path, exist_ok=True)
    return path


class Api:
    """Ponte exposta ao JavaScript como window.pywebview.api.*"""

    def caminho_dados_atual(self):
        return json.dumps({"caminho": caminho_dados_padrao()})

    def carregar_dados(self):
        caminho = caminho_dados_padrao()
        vazio = json.dumps({"condominios": []})
        try:
            with open(caminho, "r", encoding="utf-8-sig") as f:
                conteudo = f.read()
        except FileNotFoundError:
            pasta = pasta_do_executavel()
            if not os.path.isdir(pasta):
                # A pasta nem existe agora (ex.: unidade de rede
                # momentaneamente fora do ar) — não é seguro assumir
                # "arquivo não existe" e criar um vazio por cima do que
                # pode ser só uma falha de acesso transitória.
                return json.dumps({"erro": "pasta_inacessivel", "detalhe": pasta})
            try:
                with open(caminho, "w", encoding="utf-8") as f:
                    f.write(vazio)
            except OSError as e:
                return json.dumps({"erro": "falha_ao_criar", "detalhe": str(e)})
            return json.dumps({"ok": True, "conteudo": vazio})
        except OSError as e:
            return json.dumps({"erro": "falha_ao_ler", "detalhe": str(e)})

        if not conteudo.strip():
            conteudo = vazio
        else:
            try:
                json.loads(conteudo)
            except json.JSONDecodeError as e:
                return json.dumps({"erro": "arquivo_invalido", "detalhe": str(e)})

        return json.dumps({"ok": True, "conteudo": conteudo})

    def salvar_dados(self, conteudo):
        try:
            json.loads(conteudo)
        except json.JSONDecodeError as e:
            return json.dumps({"erro": "conteudo_invalido", "detalhe": str(e)})

        caminho = caminho_dados_padrao()
        pasta = pasta_do_executavel()
        if not os.path.isdir(pasta):
            return json.dumps({"erro": "pasta_inacessivel", "detalhe": pasta})

        try:
            fd, tmp_path = tempfile.mkstemp(dir=pasta, prefix=".condominios-", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(conteudo)
            os.replace(tmp_path, caminho)
        except OSError as e:
            return json.dumps({"erro": "falha_ao_salvar", "detalhe": str(e)})

        return json.dumps({"ok": True})

    def escolher_arquivo_documento(self):
        janela = webview.windows[0]
        resultado = janela.create_file_dialog(webview.OPEN_DIALOG)
        if not resultado:
            return json.dumps({"ok": False})
        return json.dumps({"ok": True, "caminho": resultado[0]})


def _geometria_janela_inicial():
    """Meia tela de largura, quase toda a altura disponível — grande o
    bastante pra nenhum diálogo de cadastro precisar de rolagem lateral."""
    try:
        tela = webview.screens[0]
        largura = max(760, tela.width // 2)
        altura = max(760, tela.height - 60)
        return {"width": largura, "height": altura}
    except Exception:
        return {"width": 820, "height": 900}


def main():
    index_path = resource_path("index.html")
    geometria = _geometria_janela_inicial()

    webview.create_window(
        APP_TITLE,
        index_path,
        js_api=Api(),
        min_size=(760, 640),
        **geometria,
    )
    # private_mode=False + storage_path faz o perfil do navegador embutido
    # persistir entre uma abertura e outra (cache, etc.) — os dados dos
    # condomínios em si ficam no condominios-dados.json, não aqui.
    webview.start(storage_path=storage_dir(), private_mode=False)


if __name__ == "__main__":
    main()
