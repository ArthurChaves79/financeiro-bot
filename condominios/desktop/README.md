# SIG Condomínios — versão desktop (.exe)

Empacota o SIG Condomínios (que é HTML/CSS/JS puro) como um aplicativo
Windows nativo, usando [pywebview](https://pywebview.flowrl.com/) +
[PyInstaller](https://pyinstaller.org/) — o mesmo caminho usado para gerar
o `.exe` do SIG Editor.

Não precisa de navegador nem de servidor: o `pywebview` abre o app numa
janela própria, usando o WebView2 (o motor do Edge) que já vem instalado
no Windows 10/11. Se faltar, o Windows pede para instalar automaticamente
na primeira execução (ou baixe em
https://developer.microsoft.com/microsoft-edge/webview2/).

## Pré-requisitos

- **Python 3.10+** instalado (marque "Add Python to PATH" no instalador).
- Rodar os comandos abaixo com o **Prompt de Comando** dentro desta pasta
  (`condominios\desktop`).

## Rodar em modo desenvolvimento (sem gerar .exe)

```bat
pip install -r requirements.txt
python app.py
```

Abre a janela do SIG Condomínios direto do código-fonte — útil para
testar antes de gerar o executável.

## Gerar o .exe

```bat
build.bat
```

O script instala as dependências, roda o PyInstaller e deixa o executável
pronto em:

```
condominios\desktop\dist\SIG Condominios.exe
```

Esse único arquivo já contém tudo (Python, pywebview, HTML/CSS/JS do app)
— pode copiar só ele para outro computador ou para a área de trabalho,
não precisa levar o restante da pasta junto.

### Ícone personalizado (opcional)

Por padrão o `.exe` usa o ícone genérico do Python. Para usar o ícone do
app, converta `condominios/icons/icon-192.png` para `.ico` (ex.: em
https://convertio.co/png-ico/ ou com o Pillow) e adicione ao comando do
PyInstaller em `build.bat`:

```
--icon "..\icons\icon.ico"
```

## Onde ficam os dados

Os condomínios cadastrados ficam salvos num único arquivo, sempre ao lado
do `.exe`:

```
condominios-dados.json
```

Isso é proposital: se o `.exe` (ou um atalho para ele) estiver numa pasta
de rede compartilhada, todo mundo que abrir esse mesmo `.exe` vê e edita
os mesmos condomínios — sem precisar escolher arquivo nem configurar
nada na primeira vez. Não existe mais nenhuma tela de "escolher onde
salvar": o app sempre usa o arquivo ao lado de onde o `.exe` está
rodando.

Se antes de existir esse arquivo o programa já tinha sido usado (dados
salvos no perfil do navegador embutido), na primeira abertura com a nova
versão esses dados antigos são migrados automaticamente para o
`condominios-dados.json`.

Use o botão ⚙ → **🔄 Recarregar dados** se outro computador acabou de
salvar uma alteração e ela ainda não apareceu na sua tela. Use o botão de
backup (⚙ → Exportar backup) para ter uma cópia de segurança à parte.

## Atualizando o app

Sempre que o código em `condominios/` (index.html, app.js, styles.css)
mudar, rode `build.bat` de novo para gerar um `.exe` atualizado — o
executável antigo não se atualiza sozinho.
