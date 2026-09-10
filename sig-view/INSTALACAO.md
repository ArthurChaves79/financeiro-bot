# SIG View — Instalação e atualização

Guia rápido pra instalar o SIG View num computador novo, ou atualizar
um que já tem o programa instalado. Pensado pra rodar sem depender de
ninguém de TI — mas se aparecer um erro que este guia não cobre, veja
a seção "Problemas comuns" no fim.

---

## 1. Instalando num computador novo

### Passo 1 — Instalar o Python

Se o computador ainda não tem Python instalado:

1. Baixe em <https://www.python.org/downloads/> (qualquer versão 3.11
   ou mais nova).
2. Na tela de instalação, **marque a caixa "Add python.exe to PATH"**
   antes de clicar em instalar — sem isso, os próximos passos não
   funcionam.

### Passo 2 — Pegar os arquivos do programa

O código do SIG View está no repositório `financeiro-bot`, dentro da
pasta `sig-view` — mas **numa branch específica**, não na principal.
Isso muda como você baixa:

**Se usar `git`:**
```
git clone https://github.com/arthurchaves79/financeiro-bot.git
cd financeiro-bot
git checkout claude/sao-paulo-earth-viewer-khb93y
```

**Se preferir baixar pelo navegador (sem usar `git`):**
1. Acesse:
   `https://github.com/arthurchaves79/financeiro-bot/tree/claude/sao-paulo-earth-viewer-khb93y`
2. Botão verde **"Code"** → **"Download ZIP"**.
3. Extraia o ZIP num lugar **fora de pastas sincronizadas**
   (OneDrive, SharePoint, Google Drive) — ver "Problemas comuns" no
   fim sobre isso.

> ⚠️ Se baixar direto da página principal do repositório (sem entrar
> nessa branch específica primeiro), a pasta `sig-view` **não vem
> junto** — é o erro mais comum nessa etapa.

### Passo 3 — Instalar as dependências

Dentro da pasta `sig-view`, dê **dois cliques em `instalar.bat`**.
Ele confere o Python, cria o ambiente (`.venv`) e instala tudo que
falta. Pode demorar alguns minutos na primeira vez.

### Passo 4 — Gerar o `.exe`

Depois que o `instalar.bat` terminar sem erro, dê **dois cliques em
`gerar_executavel.bat`**. Isso gera `SigView.exe` dentro da pasta
`sig-view` (leva alguns minutos).

### Passo 5 — Rodar e configurar

Dê dois cliques no `SigView.exe` gerado. Na primeira vez, abra
**⚙ Configurações** e aponte:

- **Pasta de camadas** — onde ficam os `.geojson` (local ou rede).
- **Banco de busca** — caminho do `geocoder.db` (se já existir um
  pronto; senão, veja o `README.md` sobre como gerar um pelo painel
  de 🔧 Manutenção).
- **Mapa** — escolha um `.mbtiles` (coloque o arquivo em
  `sig-view\data\maps\` antes, pra ele aparecer na lista).

Cada campo de caminho agora tem um botão **📂** ao lado pra escolher
pela janela do Windows, sem precisar digitar/colar.

### Distribuindo pra outros computadores

Depois de gerar o `.exe` uma vez, pra levar pra outro PC da empresa
**não precisa repetir os passos acima** — só copie:

- `SigView.exe`
- a pasta `data` do lado dele (mapa `.mbtiles`, `data\maps`,
  `data\fonts` se já tiver as fontes de rótulo, e `data\geocoder.db`
  se já tiver o índice de busca pronto)

Sem precisar levar `.geojson` nenhum — o programa abre normal, só sem
camadas na lista, até você apontar a pasta certa em Configurações.

---

## 2. Atualizando uma instalação existente

Sempre que houver uma correção ou funcionalidade nova:

### Passo 1 — Atualizar os arquivos

**Com `git`** (no computador onde o código já foi clonado):
```
cd financeiro-bot
git checkout claude/sao-paulo-earth-viewer-khb93y
git pull origin claude/sao-paulo-earth-viewer-khb93y
```

**Sem `git`:** baixe o ZIP de novo (mesmo link do Passo 2 da
instalação) e extraia por cima da pasta existente.

### Passo 2 — Regerar o `.exe`

Dentro de `sig-view`, dê dois cliques em **`gerar_executavel.bat`**
de novo. Isso substitui o `SigView.exe` antigo por um com as
atualizações.

> Se apareceram avisos tipo `WARNING: Hidden import "..." not found!`
> durante esse processo, pode ignorar — são avisos normais de
> bibliotecas opcionais, não impedem o `.exe` de ser gerado
> corretamente (confirme que apareceu a mensagem final "Pronto!").

### Passo 3 — Fechar e reabrir o programa (IMPORTANTE)

Antes de abrir o `SigView.exe` novo, **feche completamente** qualquer
janela do SIG View que já estivesse aberta (não só minimizar). A
janela do programa guarda um cache local que às vezes segura a
versão antiga do site por trás — fechando e abrindo de novo, ele
sempre carrega a versão instalada de verdade.

### Passo 4 — Redistribuir (se for pra vários computadores)

Copie o `SigView.exe` novo pra cada computador, substituindo o
antigo — não precisa mexer na pasta `data` de cada um (mapas, índice
de busca e camadas continuam onde estavam).

### Atualizando o índice de busca depois de mudar dados

Se você mudou/adicionou camadas (`.geojson`) ou atualizou o CSV de
endereços, use o painel **🔧 Manutenção** (dentro do programa) pra
reconstruir o índice de busca — não precisa terminal pra isso. Cada
tarefa lá também pode ser **agendada pra repetir sozinha** enquanto
o programa estiver aberto (útil se um CSV é atualizado periodicamente
numa pasta de rede).

---

## 3. Problemas comuns

**"Acesso negado" ao rodar `gerar_executavel.bat`**
Geralmente é a pasta do projeto estar dentro de uma pasta sincronizada
(OneDrive, SharePoint, Google Drive) — o sincronizador trava arquivos
no meio da geração do `.exe`. Mova a pasta pra um lugar fora de
sincronização (ex: `C:\SIGView\`) e rode de novo. Também pode ser o
antivírus da empresa bloqueando o executável recém-gerado (comum com
PyInstaller) — se acontecer, confira se sobrou algum aviso/quarentena
do antivírus na hora.

**Erro `Could not find a version that satisfies the requirement
pythonnet==...`** durante o `instalar.bat`
Acontece com versões muito novas do Python, se o `requirements.txt`
ainda não tiver sido atualizado pra essa versão. Solução: atualizar
os arquivos (Passo 1 da seção de atualização) — isso já foi corrigido
uma vez nesse projeto pra Python 3.13, mas pode voltar a acontecer
com versões futuras do Python.

**`ModuleNotFoundError: No module named 'app.xxx'` ao usar o painel
de Manutenção**
Sinal de que o `.exe` foi gerado com uma versão desatualizada do
`gerar_executavel.bat`. Atualize os arquivos e gere o `.exe` de novo.

**Uma correção "não aparece" mesmo depois de atualizar**
Veja o Passo 3 da atualização (fechar/reabrir o programa por
completo) — é o cache do WebView2 quase sempre.

**A pasta `sig-view` não aparece depois de baixar o repositório**
Veja o aviso no Passo 2 da instalação — precisa estar na branch
`claude/sao-paulo-earth-viewer-khb93y`, não na principal.
