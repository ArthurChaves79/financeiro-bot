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
│   │   ├── main.py          rotas da API e arquivos estáticos
│   │   ├── search.py        busca por endereço/CEP/bairro/imóvel (SQLite + FTS5)
│   │   ├── layers.py        lista/serve as camadas (GeoJSON, KML, KMZ, NetworkLink)
│   │   ├── kml.py           conversão KML/KMZ -> GeoJSON, estilos, NetworkLink
│   │   ├── tiles.py         servidor de tiles embutido (lê direto de um .mbtiles)
│   │   ├── geoutil.py       utilitário geométrico compartilhado (centroide aproximado)
│   │   ├── settings_store.py persiste config feita pela tela de Configurações
│   │   └── config.py        configuração (variáveis de ambiente)
│   ├── run.py           ponto de entrada usado para gerar o SigView.exe
│   ├── scripts/
│   │   ├── build_geocoder_index.py   gera data/geocoder.db a partir de um CSV
│   │   ├── indexar_camadas.py        indexa atributos de uma camada pra busca (ex: imóveis)
│   │   ├── vincular_poligonos.py     vincula polígonos existentes a um banco
│   │   ├── aplicar_correcoes_poligonos.py  aplica correções de geometria incrementalmente
│   │   ├── seed_sample_data.py       dados de exemplo, só para testar a instalação
│   │   └── update_layers_job.py      esqueleto do job de atualização periódica
│   └── data/            geocoder.db + mapa.mbtiles + layers/* + config.json (gerado, não versionado)
├── frontend/            HTML + MapLibre GL JS (o "globo" propriamente dito)
├── instalar.bat / iniciar.bat     instalação/uso via scripts (Windows)
├── gerar_executavel.bat           gera o SigView.exe (Windows)
├── assets/               icon.ico (executável) / icon.png (favicon) + script que os gera
└── docker-compose.yml   servidor de tiles opcional (TileServer GL)
```

Por que backend em Python mas mapa em JS? Não existe hoje uma engine de
renderização de mapa vetorial interativo (pan/zoom) madura em Python
equivalente ao que navegadores oferecem. A solução comum — e a usada
aqui — é: **toda a lógica (busca, camadas, configuração) em Python**, e
o desenho do mapa em si feito pelo MapLibre GL JS, servido pelo próprio
backend Python. Isso não significa "abrir uma aba do navegador": o
`run.py` (usado pelo `SigView.exe`) abre a interface numa **janela
própria do programa**, via `pywebview` (usa o WebView2 que já vem
instalado no Windows — não é o Chrome/Edge abrindo por fora, é uma
janela do próprio SIG View). Só cai de volta pro modo "abre no
navegador" se o `pywebview` não estiver disponível.

O `SigView.exe` é gerado com `--windowed`, então abre só a janela do
programa, sem nenhuma telinha de console/cmd atrás. Se algo impedir a
janela de abrir, o log fica em `data\sigview.log` (do lado do `.exe`)
em vez de aparecer num terminal.

## Como rodar

Duas formas — escolha pelo perfil de quem vai usar:

### Opção A — `.exe` (recomendada para distribuir na empresa)

Um arquivo único (`SigView.exe`), sem precisar instalar Python nem nada
mais no computador de quem vai usar. Ideal para PCs sem permissão de
administrador ou sem internet.

1. Numa máquina Windows com Python (a mesma onde você já rodou
   `instalar.bat`), dê dois cliques em **`gerar_executavel.bat`**. Isso
   gera `sig-view/SigView.exe` (só precisa ser feito uma vez, ou de novo
   quando o código mudar).
2. Copie `SigView.exe` para qualquer outro PC Windows da empresa e dê
   dois cliques — abre o navegador sozinho, sem instalar nada.

### Opção B — scripts `.bat` (bom para desenvolvimento/testes)

```bash
cd sig-view/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # ajuste os caminhos/URLs da sua rede

# gera dados de exemplo para já testar de ponta a ponta (opcional)
python scripts/seed_sample_data.py

uvicorn app.main:app --reload --port 8000
```
(no Windows, é o que `instalar.bat` + `iniciar.bat` fazem por você)

Em ambas, abra `http://localhost:8000` — com os dados de exemplo dá pra
buscar "paulista", "moema" ou o CEP "01310-100" e ver o marcador
aparecer no mapa, além de ligar a camada "Bairros Exemplo" no painel
lateral.

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
- **Mapa** — dropdown com os `.mbtiles` encontrados em `data\maps\`
  (veja "Escolher entre vários mapas" abaixo); sem digitar caminho nenhum
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

## Painel de manutenção (sem terminal)

Clique em **🔧 Manutenção** no topo da página para rodar, direto pela
interface, as três tarefas mais comuns do dia a dia — sem precisar
abrir um terminal nem lembrar o comando exato:

- **Reindexar camadas da pasta** — equivale a rodar
  `scripts/indexar_pasta_toda.py`.
- **Reconstruir índice de busca (a partir de CSV)** — equivale a rodar
  `scripts/build_geocoder_index.py`.
- **Vincular polígonos a um banco existente** — equivale a rodar
  `scripts/vincular_poligonos.py`.

Escolha a tarefa, preencha os campos (os mesmos parâmetros que você
digitaria na linha de comando — veja as seções abaixo para o que cada
um significa) e clique em **Rodar**. O andamento (a mesma saída que
apareceria no terminal) fica visível ali, atualizando sozinho, até
terminar com sucesso ou erro. Só uma tarefa roda por vez.

Os scripts mais específicos (conversão de GeoPackage/GeoJSON do
GeoSampa, correção de geometrias, diagnóstico de `.mbtiles` etc.)
continuam só por linha de comando mesmo — o painel cobre as tarefas
que se repetem com mais frequência depois que os dados já estão
preparados.

## Tiles de ruas (o mapa base)

O próprio SIG View serve o mapa sozinho, lendo direto de um arquivo
`.mbtiles` (`app/tiles.py`) — **não precisa de Docker, TileServer GL nem
nenhum servidor externo rodando**. É só ter o arquivo no caminho
configurado (`SIGVIEW_MBTILES_PATH`, padrão `data/mapa.mbtiles`, ou via
⚙ Configurações).

Como você só precisa de ruas (sem terreno 3D), a rota recomendada pra
gerar esse arquivo é a partir do OpenStreetMap com **Planetiler**
(usa Docker só nessa etapa pontual de gerar o arquivo, não pra servir).
Isso já está automatizado em `gerar_e_subir_mapa.bat` (Windows) — veja o
passo a passo completo, sem precisar mexer em linha de comando, em
[`CONFIGURAR_MAPA_LOCAL.md`](./CONFIGURAR_MAPA_LOCAL.md).

O estilo servido em `/tiles/style.json` é gerado automaticamente: ruas,
água, quadras, limites administrativos e rótulos de nome de
rua/bairro/cidade (aparecem conforme dá zoom — ver "Nomes de rua no
mapa" abaixo). Se quiser um servidor de tiles externo mesmo assim (ex:
pra vários SIG View compartilharem um só `.mbtiles` pela rede), o
`docker-compose.yml` (TileServer GL) continua disponível como
alternativa.

Para manter atualizado com mudanças da prefeitura, combine essa base OSM
com camadas específicas do **GeoSampa** (dados abertos da Prefeitura de
São Paulo) — essas entram como **camadas** normais (GeoJSON), não como
tile do mapa base, então atualizam independente da malha de ruas.

### Nomes de rua no mapa

Os nomes de rua/bairro/cidade já vêm no `.mbtiles` gerado pelo
Planetiler (esquema OpenMapTiles) — não precisa gerar o mapa de novo.
Só falta a **fonte** (o MapLibre chama isso de "glyphs": arquivos
`.pbf` pré-renderizados, um por faixa de caracteres — é assim que
qualquer mapa vetorial desenha texto, não tem como usar uma fonte
comum do Windows direto).

1. Acesse a aba **"Releases"** do repositório
   [openmaptiles/fonts](https://github.com/openmaptiles/fonts/releases)
   (código aberto, mantido pelo próprio projeto OpenMapTiles) — o
   código-fonte do repositório só tem as fontes originais (`.ttf`); o
   resultado já processado (`.pbf`, o que o MapLibre precisa) fica
   anexado como arquivo de download numa versão publicada ali.
2. Baixe e extraia; ache a subpasta **`Noto Sans Regular`**.
3. Copie essa subpasta pra `backend/data/fonts/Noto Sans Regular/`
   (os arquivos `.pbf` direto dentro dela, ex:
   `backend/data/fonts/Noto Sans Regular/0-255.pbf`).
4. Reinicie o SIG View — os rótulos aparecem sozinhos, sem precisar
   mexer em mais nada.

Sem essa pasta, o mapa funciona normal, só sem os nomes escritos (a
ausência do arquivo de fonte não quebra nada, os rótulos simplesmente
não desenham). Quer usar outra fonte? Baixe a pasta correspondente do
mesmo repositório e ajuste `_FONTE_PADRAO` em `app/tiles.py`.

### Escolher o estilo de cores do mapa

Em ⚙ Configurações, o campo **"Estilo de cores do mapa"** troca entre
temas prontos — todos usam o mesmo `.mbtiles`, só mudam as cores, então
não precisa baixar nem gerar nada de novo pra trocar:

- **Claro** — o padrão, fundo bege claro.
- **Escuro** — fundo escuro, bom pra ambientes com pouca luz.
- **Alto contraste** — cores mais fortes/saturadas, ruas maiores em
  vermelho — bom pra quem quer as vias bem destacadas.
- **Minimalista** — tons neutros e discretos, pra quando as suas
  próprias camadas (polígonos coloridos) são o foco e o mapa de fundo
  deve "sumir" um pouco.

Trocar e salvar recarrega a página já com o novo estilo. Pra adicionar
um tema novo, edite o dicionário `PALETAS` em `backend/app/tiles.py`
— é só copiar um bloco de cores existente e ajustar.

### Escolher entre vários mapas

Se você tem mais de um `.mbtiles` pronto (ex: um de ruas e outro de
imagem de satélite), coloque todos dentro de `backend/data/maps/`
(qualquer nome de arquivo, ex: `ruas.mbtiles`, `satelite.mbtiles`) — em
⚙ Configurações eles aparecem automaticamente como opções num dropdown
("Mapa"), sem precisar digitar caminho nenhum. Trocar a seleção e salvar
já recarrega o mapa escolhido. Um caminho de rede digitado manualmente
antes desse recurso existir continua funcionando — aparece na lista como
"(personalizado)".

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

### Populando com ruas/CEP do GeoSampa (recomendado para a capital)

`scripts/converter_geosampa_logradouros.py` transforma uma camada
baixada do GeoSampa direto no CSV acima, sem precisar montar a planilha
na mão:

1. No [GeoSampa](https://geosampa.prefeitura.sp.gov.br), ache a camada
   em **Mapa Digital da Cidade** — "Sistema Viário" > "Eixo de
   Logradouro" pras ruas, ou "Distritos"/"Bairros" pras regiões.
2. Baixe no formato **GeoJSON** ou **GeoPackage (`.gpkg`)** — nesses
   dois dá pra ler sem precisar de nenhuma biblioteca externa. Evite
   Shapefile (`.shp`) se puder escolher: exigiria decodificar um
   formato binário à parte e ainda separar a projeção do `.prj`.
3. Converta e importe (o script certo depende do formato baixado):

   ```bash
   cd backend

   # se baixou em GeoJSON:
   python scripts/converter_geosampa_logradouros.py logradouros.geojson --tipo endereco --saida ruas.csv
   python scripts/converter_geosampa_logradouros.py distritos.geojson --tipo bairro --saida bairros.csv

   # se baixou em GeoPackage (.gpkg) — primeiro descubra o nome da tabela:
   python scripts/converter_geopackage_geosampa.py logradouros.gpkg --listar-tabelas
   python scripts/converter_geopackage_geosampa.py logradouros.gpkg --tabela <nome> --tipo endereco --saida ruas.csv
   python scripts/converter_geopackage_geosampa.py distritos.gpkg --tabela <nome> --tipo bairro --saida bairros.csv

   # os dois csv entram juntos no mesmo índice (build_geocoder_index.py
   # aceita mais de um arquivo de uma vez, nenhum apaga o outro):
   python scripts/build_geocoder_index.py ruas.csv bairros.csv
   ```

Os dois scripts reconhecem sozinhos os nomes de coluna mais comuns
dessas camadas (nome do logradouro, tipo — Rua/Avenida, bairro, CEP);
se algum não for reconhecido, aponte manualmente com
`--map campo=coluna`, ex: `--map cep=CD_CEP`.

O GeoSampa publica os dados em **SIRGAS 2000 / UTM 23S** (coordenadas
em metros, não em graus) — `converter_geopackage_geosampa.py` detecta
isso sozinho e converte pra latitude/longitude automaticamente (sem
precisar de GDAL/pyproj: é uma fórmula de projeção implementada direto
em Python). Se a camada vier em WGS84 (graus) também funciona sem
converter nada.

> Nota: o CEP nas camadas de logradouro do GeoSampa costuma ser
> incompleto (nem toda rua tem CEP cadastrado na camada) — a busca por
> nome de rua e bairro funciona plenamente de qualquer forma; CEP é só
> mais um campo pesquisável quando disponível.

### Buscar por rua + número (ex: "Rua Natal 974")

A camada "Eixo de Logradouro" do GeoSampa também traz, pra cada trecho
de rua, a faixa de numeração par e ímpar daquele pedaço
(`lg_ini_par`/`lg_fim_par`/`lg_ini_imp`/`lg_fim_imp`) — os dois
conversores acima (GeoJSON e GeoPackage) já extraem isso sozinhos,
sem precisar de nada extra. Ao buscar "Rua Natal 974", o programa acha
o trecho da rua cuja faixa contém esse número e leva até o centro
aproximado daquele trecho (não é a porta exata — a camada não tem a
posição de cada número, só a faixa de cada pedaço de rua — por isso o
resultado aparece marcado como "nº 974 (aprox.)"). Se o número não
cair em nenhuma faixa conhecida, a busca cai pra mostrar a rua inteira,
em vez de não achar nada.

Isso já vem pronto ao importar pelo `converter_geosampa_logradouros.py`
ou `converter_geopackage_geosampa.py` — só rode `build_geocoder_index.py`
de novo em cima do CSV gerado. Se você já tinha um índice antigo (de
antes dessa funcionalidade existir), rodar `build_geocoder_index.py`
de novo com um CSV que tenha essas colunas atualiza tudo — não precisa
apagar nada na mão.

### Buscar imóveis pelos dados vinculados aos polígonos

Depois de rodar `vincular_poligonos.py` (veja mais abaixo), a camada
resultante (ex: `imoveis.geojson`) já tem número de contribuinte,
proprietário etc. como atributos dos polígonos — dá pra tornar isso
pesquisável na mesma caixa de busca:

```bash
python scripts/indexar_camadas.py data/layers/imoveis.geojson \
    --layer-id imoveis \
    --rotulo numero_contribuinte proprietario
```

Depois disso, buscar "1234" ou "João da Silva" encontra o imóvel, voa
pro polígono no mapa e **liga a camada automaticamente** (mesmo que
estivesse desligada). Rodar de novo para o mesmo `--layer-id` substitui
só os registros daquela camada, sem duplicar nem apagar os endereços já
indexados por `build_geocoder_index.py`.

## Adicionando camadas

Basta colocar um arquivo na pasta de camadas (`SIGVIEW_LAYERS_DIR`, ou a
que você configurou na tela ⚙ Configurações) — ele aparece
automaticamente no painel de camadas na próxima vez que a página recarrega.
Suporta pontos, linhas e polígonos (o frontend estiliza os três).

Formatos aceitos:
- **`.geojson`** — usado direto.
- **`.kml`** e **`.kmz`** — os mesmos formatos que o Google Earth/Google My
  Maps exportam. São convertidos para GeoJSON automaticamente ao serem
  servidos (a conversão roda no backend, sem dependências externas).
  `MultiGeometry` do KML é "achatado" em várias features simples, e dados
  de `ExtendedData`/`SimpleData` viram propriedades da feature (aparecem
  no popup ao clicar no mapa).

**Pastas dentro do KML (`<Folder>`)** aparecem como uma árvore
expansível no painel, igual ao painel "Locais" do Google Earth: cada
pasta tem uma seta (▶/▼) pra abrir/fechar e pode conter outras pastas
dentro (inclusive aninhadas em vários níveis). Se a pasta tem placemarks
direto nela (não só subpastas), ela também ganha seu próprio checkbox,
independente das subpastas.

**Cores**: respeita a cor do próprio polígono, na seguinte ordem de
prioridade: `<Style>`/`<StyleMap>` do KML (preenchimento, linha, ícone);
propriedades no padrão "simplestyle" comuns em GeoJSON de outras
ferramentas (`fill`, `stroke`, `marker-color`); um campo `cor` cru nas
propriedades da feature (comum em export de banco de dados). Só cai pra
cor automática da camada (sempre a mesma, mesmo depois de reiniciar)
quando a feature não define nenhuma dessas.

**Clique no mapa**: funciona em pontos, linhas e polígonos — abre uma
barra lateral com os detalhes da feature. Um conjunto de campos
"conhecidos" aparece primeiro, numa ordem fixa, reconhecendo variações
comuns de nome de coluna (sem acento/maiúscula/espaço):

| Campo na barra | Reconhece (nome da propriedade) |
|---|---|
| Contribuinte | `contribuinte`/`numero_contribuinte`/`inscricao` — ou monta a partir de `setor`+`quadra`+`lote` separados |
| Matrícula / Transcrição | `matricula` (prioridade) ou `transcricao` |
| Endereço | `tipo_logradouro` + `logradouro`/`endereco` + `numero` |
| Loteamento | `loteamento` |
| Documentos | `documentos`/`anexos`/`arquivo` — vira link clicável (aceita vários, separados por `;` ou quebra de linha) |
| Observações | `observacoes`/`obs` |

Qualquer outra propriedade que a feature tiver aparece depois, com o
nome da coluna como rótulo. Campos sem valor (vazio/nulo) simplesmente
não aparecem — não precisa "limpar" a planilha/banco antes de exportar.
Propriedades internas do SIG View (usadas só pra estilo/controle, como a
cor ou se foi vinculada a um banco) começam com `_` e nunca aparecem.

## Índice com atualização automática (`<NetworkLink>`)

Se você já mantém seus KMLs numa pasta de rede separada (fora da pasta
de camadas do SIG View), não precisa copiá-los toda vez — crie um KML
"índice" com um `<NetworkLink>` apontando pra lá, do mesmo jeito que se
faz no Google Earth:

```xml
<?xml version="1.0"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <NetworkLink>
    <name>Zoneamento (rede)</name>
    <Link>
      <href>\\servidor\camadas\zoneamento.kml</href>
      <refreshMode>onInterval</refreshMode>
      <refreshInterval>300</refreshInterval>
    </Link>
  </NetworkLink>
</Document>
</kml>
```

Coloque esse `indice.kml` na sua pasta de camadas normal. O SIG View
resolve o link (o arquivo apontado pode estar em qualquer pasta/rede
acessível, não precisa estar dentro da pasta de camadas), mostra o
conteúdo dele na árvore no lugar onde o link apareceu, e — com
`refreshMode=onInterval` — busca o arquivo de novo automaticamente a
cada `refreshInterval` segundos enquanto a camada estiver ligada,
atualizando o mapa sem precisar recarregar a página (ícone 🔄 ao lado da
camada indica que ela atualiza sozinha).

Um `<NetworkLink>` pode ficar dentro de qualquer `<Folder>` (inclusive
aninhado), e o arquivo apontado pode ele mesmo ter suas próprias
`<Folder>`/`<NetworkLink>`. Links quebrados (arquivo não encontrado) ou
circulares (A aponta pra B que aponta de volta pra A) aparecem com um
aviso (⚠) na árvore em vez de travar o carregamento das outras camadas.

**Limitação atual**: só é suportado `href` de caminho de arquivo/rede
(local ou UNC, ex: `\\servidor\pasta\arquivo.kml`) — links `http://`/
`https://` ainda não são resolvidos (avisa com erro na árvore se
encontrar um).

## Vinculando polígonos já existentes a um banco de dados

Se você já tem os polígonos (KML/KMZ/GeoJSON) e os atributos já existem
num banco relacional, **não é preciso digitar nada na mão** — use
`scripts/vincular_poligonos.py` para juntar os dois automaticamente por
uma chave em comum (por padrão, número do contribuinte):

```bash
cd backend
python scripts/vincular_poligonos.py poligonos.kml atributos.csv \
    --saida data/layers/imoveis.geojson \
    --pendencias pendencias_imoveis.csv
```

- `atributos.csv` é um export do banco existente (qualquer SGBD gera
  isso com um `SELECT`) — precisa ter uma coluna com a mesma chave que
  identifica o polígono (ex: `numero_contribuinte`).
- Polígonos que **têm** a chave e ela **existe** no CSV são vinculados
  automaticamente — nenhum trabalho manual.
- Polígonos sem a chave, ou com uma chave que não bate com nada no CSV,
  entram no `pendencias_imoveis.csv` (com o motivo e a posição
  aproximada) em vez de travar o processo — eles continuam aparecendo
  no mapa, só sem os atributos, até você resolver.
- Para os que ficaram pendentes, crie um `vinculos_manuais.csv` (duas
  colunas: identificador do polígono, chave correta) e passe com
  `--vinculos-manuais` — assim seu trabalho manual fica registrado num
  arquivo pequeno e é reaplicado toda vez que rodar o script de novo
  (não precisa refazer nada já resolvido).
- Campos que só existem no SIG View (ainda não têm lugar no banco
  antigo) entram por um CSV separado, com `--complemento`, também pela
  mesma chave.

Rode `python scripts/vincular_poligonos.py --help` para ver todas as opções.

## Corrigindo geometrias aos poucos (fluxo com editor de polígonos)

Nem todos os polígonos originais batem com a realidade — é normal
precisar corrigir a geometria de parte deles no seu editor de polígonos,
e é impossível saber de antemão quantos serão. Para isso, use
`scripts/aplicar_correcoes_poligonos.py` **depois** de já ter uma camada
gerada pelo `vincular_poligonos.py`:

```bash
cd backend
python scripts/aplicar_correcoes_poligonos.py \
    data/layers/imoveis.geojson corrigidos.kml \
    --saida data/layers/imoveis.geojson \
    --pendencias pendencias_correcao.csv
```

- Baixe um lote do seu editor, corrija o que precisar, exporte
  (`.geojson`/`.kml`/`.kmz`) — só os que você de fato mexeu, não precisa
  reexportar tudo.
- O script casa cada polígono corrigido com o já existente (pelo número
  de contribuinte ou pelo nome/identificador) e **só troca a
  geometria** — os atributos já vinculados ao banco continuam intactos.
- Polígonos que não existiam antes (ex: um lote desmembrado durante a
  correção) entram como novos registros, sem vínculo, e caem no
  relatório de pendências — do mesmo jeito que no `vincular_poligonos.py`.
- Pode rodar isso quantas vezes precisar, a cada novo lote corrigido —
  é incremental, não refaz o que já está pronto.

## Performance com KMLs grandes/muitos arquivos

Converter KML pra GeoJSON (ler o XML, resolver estilos, montar as
geometrias) tem um custo — o programa guarda esse resultado em memória
enquanto está aberto, mas isso se perde a cada reinício, deixando a
**primeira** abertura de cada camada lenta de novo.

`scripts/pre_converter_camadas.py` resolve isso adiantando esse
processamento e salvando o resultado pronto em disco (numa subpasta
oculta `.sigview_cache`, do lado dos KMLs originais). O programa passa
a ler esse resultado já pronto em vez de reprocessar o XML — inclusive
logo depois de abrir o programa pela primeira vez.

```bash
cd backend
python scripts/pre_converter_camadas.py
```

- Roda **uma vez** depois de colocar/atualizar KMLs na pasta de
  camadas — arquivos sem mudança são pulados automaticamente da
  próxima vez (compara a data de modificação).
- Use `--forcar` pra reconverter tudo, mesmo o que já está atualizado.
- Se o arquivo original mudar depois (nova exportação, correção etc.),
  o programa detecta sozinho que o cache ficou desatualizado e
  reprocessa — rodar o script de novo é só pra não pagar esse custo na
  hora que alguém está usando o mapa.
- Vale colocar isso num agendamento (Agendador de Tarefas do Windows),
  rodando pouco depois de qualquer atualização automática das camadas.

### Camadas com muitos polígonos (clique até aparecer no mapa)

Se o `.geojson` de uma camada é grande (muitas centenas/milhares de
polígonos), duas coisas de alto impacto e baixo risco atacam a
demora entre clicar na camada e ela aparecer no mapa:

1. **Compressão das respostas (gzip)** — já ativo, não precisa fazer
   nada. O servidor comprime automaticamente qualquer resposta grande
   (`GZipMiddleware`), reduzindo bastante o tamanho transferido até o
   navegador — JSON comprime muito bem, é bastante texto repetido.

2. **Reduzir a precisão das coordenadas** — Google Earth/QGIS costumam
   exportar coordenadas com 14-15 casas decimais, mas 7 casas já dão
   ~1cm de precisão no chão (de sobra pra um lote urbano). O resto é
   peso morto: mais bytes pra ler do disco, mandar pro navegador e o
   MapLibre processar. `scripts/compactar_camadas.py` arredonda as
   coordenadas dos `.geojson` já existentes, sem mexer em mais nada
   (propriedades, pastas e nomes de arquivo continuam iguais):

   ```bash
   cd backend
   python scripts/compactar_camadas.py data/layers --dry-run   # só mostra a redução
   python scripts/compactar_camadas.py data/layers             # aplica de verdade
   ```

   - Roda **uma vez** em cima dos arquivos que já existem (ou de novo
     depois de gerar/atualizar camadas grandes).
   - `--dry-run` mostra quanto cada arquivo reduziria sem alterar nada.
   - `--casas N` ajusta a precisão (padrão 7 = ~1cm); não precisa mexer
     nisso a menos que note diferença visual no mapa.
   - É seguro rodar de novo em cima de um arquivo já compactado.

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
| `GET /api/maps` | mapas (`.mbtiles`) disponíveis em `data/maps/`, para o dropdown de Configurações |
| `GET /api/map-styles` | temas de cor disponíveis pro mapa vetorial, para o dropdown de Configurações |
| `PUT /api/settings` | atualiza e persiste as configurações |
| `GET /tiles/style.json` | estilo do mapa embutido (lido do `.mbtiles`) |
| `GET /tiles/{z}/{x}/{y}` | um tile do mapa embutido |
| `GET /fonts/{fontstack}/{range}.pbf` | glyphs pros rótulos do mapa (ver `data/fonts/`) |
