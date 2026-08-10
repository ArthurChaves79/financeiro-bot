# Configurar o mapa base local (ruas) — guia para quem for preparar o servidor

Esta etapa gera o "mapa de fundo" (as ruas desenhadas) e o deixa disponível
na rede da empresa, para todo mundo que rodar o SIG View usar. **É feita
uma vez** (e repetida periodicamente para atualizar), num único
computador/servidor — não em cada máquina de usuário.

> Se você é leigo em TI, o ideal é pedir para alguém do TI ou um
> colega mais técnico rodar esta parte. Ela precisa instalar o Docker, o
> que normalmente exige permissão de administrador.

## Pré-requisitos

- **Docker Desktop** instalado nesse computador/servidor: https://www.docker.com/products/docker-desktop/
  (no Windows, pede reiniciar e às vezes habilitar "virtualização" na BIOS —
  é por isso que recomendamos que o TI faça essa parte).
- Uns **4 GB de espaço livre em disco** e uma conexão de internet (só
  nesta etapa, para baixar o mapa do OpenStreetMap uma vez).

## Passo a passo

### 1. Gerar o arquivo do mapa (tiles) da região de São Paulo

Na pasta `sig-view`, dê dois cliques em **`gerar_e_subir_mapa.bat`**.

Isso vai, automaticamente:
1. Baixar os dados de ruas da região Sudeste (OpenStreetMap, fonte aberta e gratuita) e recortar só a área do estado de São Paulo.
2. Gerar o arquivo `tiles/ruas-sp.mbtiles` (o "mapa" propriamente dito).
3. Subir um servidor local (`TileServer GL`, via Docker) que serve esse mapa.

A primeira vez demora (baixa uns 300-600 MB e processa) — pode levar de
10 a 40 minutos dependendo da internet/computador. Da próxima vez que
quiser **atualizar** o mapa (ruas novas, etc.), é só rodar o mesmo
arquivo `.bat` de novo.

### 2. Conferir se o servidor subiu

Abra no navegador: `http://localhost:8080` — deve aparecer a página do
TileServer GL com um mapa de exemplo.

Se outras pessoas da empresa forem acessar esse mapa (não só quem gerou
os tiles), troque `localhost` pelo **IP desse computador na rede** (ex:
`http://192.168.1.50:8080`) — pergunte pro TI qual é, ou rode `ipconfig`
no Prompt de Comando e procure "Endereço IPv4".

### 3. Apontar o SIG View para esse servidor

Na página `http://localhost:8080` que abriu no passo 2, tem uma lista de
"styles" disponíveis — clique no mapa listado lá e copie a URL do
`style.json` dele (geralmente algo como
`http://localhost:8080/styles/basic-preview/style.json`, mas o nome pode
variar conforme a versão do TileServer GL).

Em `sig-view/backend/.env` (o arquivo criado pelo `instalar.bat`), ajuste:

```
SIGVIEW_TILE_SOURCE_URL=http://<IP-DO-SERVIDOR>:8080/styles/<nome-do-style>/style.json
SIGVIEW_TILE_SOURCE_TYPE=vector
```

Troque `<IP-DO-SERVIDOR>` pelo IP do computador que está rodando o
`gerar_e_subir_mapa.bat` (ou `localhost` se for o mesmo computador), e
`<nome-do-style>` pelo que você copiou da página.

Depois é só reabrir o `iniciar.bat` do SIG View — o mapa já aparece com
as ruas desenhadas, e as camadas locais (bairros, pontos etc.) ficam por
cima dele, exatamente como no Google Earth.

## Deixando o servidor de tiles sempre ligado

Para o mapa funcionar para todo mundo, o computador/servidor que rodou o
`gerar_e_subir_mapa.bat` precisa continuar com o Docker Desktop aberto (o
container `sigview-tileserver` fica rodando em segundo plano). O ideal é
isso rodar numa máquina que fica ligada o dia todo (um servidor da
empresa), não no notebook de alguém que desliga à noite.

## Atualizando o mapa periodicamente

Sempre que quiser atualizar as ruas (a prefeitura mudou algo, por
exemplo), rode `gerar_e_subir_mapa.bat` de novo — ele baixa os dados mais
recentes do OpenStreetMap e substitui o arquivo de tiles. Pode agendar
isso (ex: uma vez por mês) usando o **Agendador de Tarefas do Windows**.
