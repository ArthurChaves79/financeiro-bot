# Configurar o mapa base local (ruas)

Esta etapa gera o "mapa de fundo" (as ruas desenhadas). O próprio SIG
View sabe servir esse mapa sozinho (lendo um arquivo `.mbtiles`) — não
precisa de nenhum servidor rodando no dia a dia, nem Docker, nem
internet, uma vez que o arquivo esteja pronto.

## Passo 1 — Gerar o arquivo do mapa (feito uma vez, ou quando quiser atualizar)

Isso usa Docker só nesta etapa (pra rodar o Planetiler, a ferramenta que
processa os dados do OpenStreetMap) — não fica rodando depois.

**Pré-requisitos**: Docker Desktop instalado (https://www.docker.com/products/docker-desktop/)
e uns 4 GB de espaço livre + internet (só pra baixar os dados do mapa
uma vez).

Na pasta `sig-view`, dê dois cliques em **`gerar_e_subir_mapa.bat`**.
Isso baixa os dados de ruas da região Sudeste (OpenStreetMap) e recorta
só a área do estado de São Paulo, gerando o arquivo em
`backend/data/mapa.mbtiles` — já no lugar certo pro SIG View usar.

A primeira vez demora (baixa uns 300-600 MB e processa) — pode levar de
10 a 40 minutos dependendo da internet/computador.

## Passo 2 — Usar

Não precisa de mais nada! Ao abrir o SIG View (`iniciar.bat`, ou o
`.exe`), se `backend/data/mapa.mbtiles` existir, o mapa já aparece com
as ruas desenhadas — a configuração padrão já aponta pra esse arquivo.

Se você guardou o `.mbtiles` em outro lugar, aponte pra ele em
**⚙ Configurações → Arquivo do mapa (.mbtiles)**.

## Levando pra outros computadores (o `.exe`)

Ao gerar o `SigView.exe` (`gerar_executavel.bat`), copie também o
`backend/data/mapa.mbtiles` pra perto do `.exe` (mesma pasta, dentro de
uma subpasta `data/`) — assim o executável já sai com o mapa embutido,
e quem receber só o `.exe` (sem o resto do projeto) já vê as ruas sem
precisar gerar nada.

## Atualizando o mapa periodicamente

Sempre que quiser atualizar as ruas (a prefeitura mudou algo, por
exemplo), rode `gerar_e_subir_mapa.bat` de novo — ele baixa os dados
mais recentes do OpenStreetMap e substitui `mapa.mbtiles`. Pode agendar
isso (ex: uma vez por mês) usando o **Agendador de Tarefas do Windows**.

## Alternativa: servidor de tiles externo (TileServer GL)

Se preferir manter um servidor de tiles separado rodando na rede (por
exemplo, pra vários SIG View apontarem pro mesmo lugar em vez de cada
um ter sua própria cópia do `.mbtiles`), o `docker-compose.yml` deste
projeto continua funcionando: suba o TileServer GL com o `.mbtiles`
gerado, e aponte `SIGVIEW_TILE_SOURCE_URL` (ou o campo correspondente em
⚙ Configurações) pra URL desse servidor. Isso é opcional — o caminho
recomendado agora é o mapa embutido descrito acima.
