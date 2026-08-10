# SIG View

Visualizador de mapas estilo Google Earth para o **estado de São Paulo**:
mapa de ruas, camadas ligáveis/desligáveis e busca por endereço, CEP e
bairro. Roda localmente (na sua máquina) e busca os dados (tiles,
camadas, índice de busca) numa **rede local** — nada depende de serviços
externos na internet.

## Arquitetura

```
sig-view/
├── backend/            Python (FastAPI) — API + serve o frontend
│   ├── app/
│   │   ├── main.py      rotas da API e arquivos estáticos
│   │   ├── search.py    busca por endereço/CEP/bairro (SQLite + FTS5)
│   │   ├── layers.py    lista/serve as camadas GeoJSON
│   │   └── config.py    configuração (variáveis de ambiente)
│   ├── scripts/
│   │   ├── build_geocoder_index.py   gera data/geocoder.db a partir de um CSV
│   │   ├── seed_sample_data.py       dados de exemplo, só para testar a instalação
│   │   └── update_layers_job.py      esqueleto do job de atualização periódica
│   └── data/            geocoder.db + layers/*.geojson (gerado, não versionado)
├── frontend/            HTML + MapLibre GL JS (o "globo" propriamente dito)
└── docker-compose.yml   servidor de tiles opcional (TileServer GL)
```

Por que backend em Python mas mapa em JS no navegador? Não existe hoje
uma engine de renderização de mapa vetorial interativo (pan/zoom) madura
em Python equivalente ao que navegadores oferecem. A solução comum — e a
usada aqui — é: **toda a lógica (busca, camadas, configuração) em
Python**, e o desenho do mapa em si feito pelo MapLibre GL JS, servido
pelo próprio backend Python e aberto no navegador (`localhost`). Do ponto
de vista de quem usa, é um programa só: você roda um comando e abre uma
janela do navegador local.

## Como rodar

```bash
cd sig-view/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # ajuste os caminhos/URLs da sua rede

# gera dados de exemplo para já testar de ponta a ponta (opcional)
python scripts/seed_sample_data.py

uvicorn app.main:app --reload --port 8000
```

Abra `http://localhost:8000`. Com os dados de exemplo, dá pra buscar
"paulista", "moema" ou o CEP "01310-100" e ver o marcador aparecer no
mapa, além de ligar a camada "Bairros Exemplo" no painel lateral.

> Nota sobre acesso totalmente offline: o `frontend/index.html` carrega a
> biblioteca MapLibre GL JS via CDN (unpkg) para simplificar o setup
> inicial. Se a rede onde isso vai rodar não tem saída para a internet,
> baixe `maplibre-gl.js` e `maplibre-gl.css` uma vez e sirva-os de
> `frontend/static/vendor/`, trocando as tags `<link>`/`<script>` no
> `index.html` para apontar pra lá.

## Configurando a rede local

Há duas formas, e elas se complementam:

### Pela interface (recomendado para quem não mexe com arquivos de config)

Dentro do próprio SIG View, clique em **⚙ Configurações** no topo da
página. Dá pra apontar, sem editar nenhum arquivo:

- **Pasta de camadas** — onde ficam os `.geojson` (local ou rede, ex: `\\servidor\sigview\layers`)
- **Banco de busca** — caminho do `geocoder.db`
- **URL do servidor de mapas (tiles)** — endereço do TileServer GL na rede
- **Tipo do mapa** — vetorial ou raster

Ao salvar, a página recarrega já usando os novos caminhos. Isso é
persistido em `backend/data/config.json` (não versionado — é específico
de cada instalação) e continua valendo mesmo depois de fechar e abrir o
programa de novo.

### Por variáveis de ambiente (valores padrão/iniciais)

`backend/.env` (veja `.env.example`) define os valores usados **antes**
de qualquer configuração ser salva pela interface — útil para uma
instalação automatizada já sair configurada:

| Variável | O que é |
|---|---|
| `SIGVIEW_LAYERS_DIR` | pasta com os `.geojson` de camadas — pode ser um compartilhamento de rede montado no SO |
| `SIGVIEW_GEOCODER_DB` | caminho do banco SQLite de busca |
| `SIGVIEW_TILE_SOURCE_URL` | URL do servidor de tiles das ruas (na rede local) |
| `SIGVIEW_TILE_SOURCE_TYPE` | `vector` (style.json) ou `raster` (template XYZ) |

Se `data/config.json` existir (porque alguém já salvou algo pela tela de
Configurações), ele tem prioridade sobre o `.env`.

## Tiles de ruas (o mapa base)

Como você só precisa de ruas (sem terreno 3D), a rota recomendada é
gerar um `.mbtiles` vetorial a partir do OpenStreetMap (com **Planetiler**)
e servi-lo com o `docker-compose.yml` deste projeto (**TileServer GL**)
numa máquina da rede local.

Isso já está automatizado em `gerar_e_subir_mapa.bat` (Windows) — veja o
passo a passo completo, sem precisar mexer em linha de comando, em
[`CONFIGURAR_MAPA_LOCAL.md`](./CONFIGURAR_MAPA_LOCAL.md).

Para manter atualizado com mudanças da prefeitura, combine essa base OSM
com camadas específicas do **GeoSampa** (dados abertos da Prefeitura de
São Paulo) — essas entram como **camadas** normais (GeoJSON), não como
tile do mapa base, então atualizam independente da malha de ruas.

## Busca (endereço, CEP, bairro)

O índice de busca é local (SQLite + FTS5, sem serviço externo). Para
popular com dados reais:

```bash
python scripts/build_geocoder_index.py caminho/para/enderecos.csv
```

O CSV precisa ter as colunas `tipo,logradouro,bairro,cidade,cep,lat,lon`
(nomes remapeáveis com `--map coluna_padrao=coluna_no_csv`). Fontes
sugeridas para montar esse CSV:

- **GeoSampa** — logradouros/bairros da capital, dados abertos da prefeitura.
- **IBGE CNEFE** — endereços de todo o estado.
- **Correios** — base de CEPs, útil para o interior.

## Adicionando camadas

Basta colocar um arquivo `.geojson` em `SIGVIEW_LAYERS_DIR` — ele aparece
automaticamente no painel de camadas na próxima vez que a página recarrega.
Suporta pontos, linhas e polígonos (o frontend estiliza os três).

## Atualização periódica

`scripts/update_layers_job.py` é o esqueleto do job que deve rodar
agendado (cron/systemd timer) num servidor da rede — não na máquina de
quem usa o mapa. Ele busca dados novos e publica na pasta de camadas de
forma atômica. Implemente `fetch_new_data()` com a chamada real à sua
fonte (GeoSampa/OSM/etc.); o restante (log, publicação atômica) já
funciona.

## API

| Rota | Descrição |
|---|---|
| `GET /api/config` | centro/zoom/bounds do mapa e config do tile source |
| `GET /api/search?q=...` | busca por endereço, CEP ou bairro |
| `GET /api/layers` | lista camadas disponíveis |
| `GET /api/layers/{id}` | GeoJSON de uma camada |
| `GET /api/settings` | configurações editáveis atuais (pastas/URL) |
| `PUT /api/settings` | atualiza e persiste as configurações |
