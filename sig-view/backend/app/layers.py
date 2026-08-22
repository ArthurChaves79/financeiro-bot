"""Descoberta e leitura das camadas (layers).

As camadas ficam numa pasta local (ou de rede, se você configurar
assim) — o backend só lê o que encontrar ali. Formatos suportados:
`.geojson` (nativo) e `.kml`/`.kmz` (convertidos na hora de servir).

Um `.kml` pode ter `<Folder>` aninhadas — a listagem devolve uma árvore
(igual ao painel "Locais" do Google Earth): cada pasta pode ter sua
própria camada de pontos/linhas/polígonos E/OU conter outras pastas
dentro, expansíveis independentemente.

Também suporta `<NetworkLink>` — o mesmo recurso do Google Earth pra
"indexar" outro arquivo (tipicamente numa pasta de rede) por um link
que é resolvido (e opcionalmente atualizado de tempos em tempos, via
`refreshMode=onInterval`/`refreshInterval`) toda vez que a árvore de
camadas é montada. O arquivo apontado pode estar em qualquer lugar do
sistema de arquivos — não precisa estar dentro de `layers_dir` — porque
quem decide isso é o conteúdo de um KML que você mesmo colocou lá, não
uma requisição externa.
"""
from __future__ import annotations

import base64
import json
import re
import unicodedata
import zlib
from pathlib import Path

from . import kml as kml_module
from .config import settings

_SUPPORTED_EXTENSIONS = (".geojson", ".kml", ".kmz")

# Cores padrão usadas quando a camada (ou pasta do KML) não define a
# própria cor via <Style> — escolhidas por serem bem distinguíveis entre
# si sobre um mapa escuro.
_PALETA_CORES = [
    "#3fa9f5",  # azul
    "#f5a93f",  # laranja
    "#5fd576",  # verde
    "#e05fd5",  # magenta
    "#f5e03f",  # amarelo
    "#5fc9d5",  # ciano
    "#e0605f",  # vermelho
    "#9d6fe0",  # roxo
    "#d59a5f",  # marrom claro
    "#6f9de0",  # azul claro
]

_GROUP_SEP = "~grupo~"  # "~" nunca aparece em base64 urlsafe nem no slug, evita colisão com ids de link
_LINK_PREFIX = "link_"
_MAX_PROFUNDIDADE_LINKS = 8  # evita loop infinito se um NetworkLink apontar pra si mesmo (direta ou indiretamente)


class LayerNotFound(FileNotFoundError):
    pass


class LayerReadError(ValueError):
    pass


def cor_padrao_da_camada(layer_id: str) -> str:
    """Cor determinística por camada (mesma camada = mesma cor sempre,
    mesmo depois de reiniciar o programa)."""
    indice = zlib.crc32(layer_id.encode("utf-8")) % len(_PALETA_CORES)
    return _PALETA_CORES[indice]


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower()
    return slug or "camada"


def _find_source_file(stem: str) -> Path | None:
    """Acha o arquivo (.geojson/.kml/.kmz) correspondente ao stem dentro
    de layers_dir, sem permitir escapar da pasta (path traversal) — usado
    só pra resolver camadas "normais" (não vindas de NetworkLink)."""
    layers_dir = settings.layers_dir.resolve()
    for ext in _SUPPORTED_EXTENSIONS:
        candidate = (layers_dir / f"{stem}{ext}").resolve()
        if layers_dir not in candidate.parents and candidate != layers_dir:
            continue
        if candidate.is_file():
            return candidate
    return None


def _encode_link_id(path: Path) -> str:
    raw = str(path.resolve()).encode("utf-8")
    return _LINK_PREFIX + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_link_id(token: str) -> Path:
    raw = token[len(_LINK_PREFIX):]
    raw += "=" * (-len(raw) % 4)
    return Path(base64.urlsafe_b64decode(raw).decode("utf-8"))


def _resolver_href(href: str, base_dir: Path) -> Path | None:
    """Resolve o href de um <NetworkLink> pra um caminho de arquivo.
    Aceita caminho absoluto (inclusive UNC, ex: \\\\servidor\\pasta) ou
    relativo ao arquivo que contém o link. URLs http(s) não são
    suportadas por enquanto (só caminho de arquivo/rede)."""
    href = href.strip()
    if not href or href.lower().startswith(("http://", "https://")):
        return None
    caminho = Path(href)
    return caminho if caminho.is_absolute() else (base_dir / caminho)


def _grupos_e_links_do_arquivo_sem_cache(
    path: Path,
) -> tuple[list[tuple[tuple[str, ...], dict]], dict[tuple[str, ...], list[dict]]]:
    """Devolve (grupos, network_links) pra um arquivo. Para .geojson é
    sempre 1 grupo sem links; para .kml/.kmz respeita <Folder> e
    <NetworkLink> (inclusive aninhados)."""
    suffix = path.suffix.lower()
    if suffix == ".geojson":
        with path.open("r", encoding="utf-8") as fh:
            return [((), json.load(fh))], {}
    if suffix == ".kml":
        return kml_module.parse_kml_full(path.read_bytes())
    if suffix == ".kmz":
        return kml_module.parse_kmz_full(path.read_bytes())
    raise LayerReadError(f"Formato não suportado: {suffix}")


# Reprocessar um KML/KMZ grande (XML inteiro + geometrias) é caro — sem
# isso, listar as camadas (que abre TODOS os arquivos da pasta pra
# montar a árvore) e depois clicar em uma camada específica reprocessam
# tudo de novo do zero, mesmo que nada tenha mudado. O cache guarda o
# resultado por arquivo, e só reprocessa se o arquivo realmente mudou
# (pela data de modificação) — assim editar/atualizar um KML na pasta
# continua funcionando normalmente, sem precisar reiniciar o programa.
_cache_arquivos: dict[Path, tuple[float, tuple[list, dict]]] = {}

# Cache em DISCO (além do de memória acima) — o de memória se perde
# toda vez que o programa reinicia, então a primeira abertura de cada
# arquivo depois de reiniciar volta a ser lenta. Rodando
# scripts/pre_converter_camadas.py, o processamento já fica pronto num
# arquivo `.json` guardado ao lado do KML original (numa subpasta
# oculta), e o programa só precisa ler esse JSON — nunca reprocessa o
# XML, mesmo recém-aberto.
_CACHE_DISCO_SUBPASTA = ".sigview_cache"


def _caminho_cache_disco(path: Path) -> Path:
    return path.parent / _CACHE_DISCO_SUBPASTA / f"{path.name}.json"


def _serializar_resultado(
    grupos: list[tuple[tuple[str, ...], dict]], network_links: dict[tuple[str, ...], list[dict]]
) -> dict:
    return {
        "grupos": [{"caminho": list(caminho), "geojson": geojson} for caminho, geojson in grupos],
        "network_links": [
            {"caminho": list(caminho), "links": links} for caminho, links in network_links.items()
        ],
    }


def _desserializar_resultado(
    data: dict,
) -> tuple[list[tuple[tuple[str, ...], dict]], dict[tuple[str, ...], list[dict]]]:
    grupos = [(tuple(item["caminho"]), item["geojson"]) for item in data["grupos"]]
    network_links = {tuple(item["caminho"]): item["links"] for item in data["network_links"]}
    return grupos, network_links


def cache_disco_atualizado(path: Path) -> bool:
    """True se já existe um cache em disco pra esse arquivo e ele
    corresponde à versão atual (mesma data de modificação)."""
    cache_path = _caminho_cache_disco(path)
    if not cache_path.is_file():
        return False
    try:
        with cache_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return False
    return data.get("mtime_origem") == path.stat().st_mtime


def gerar_cache_disco(path: Path) -> tuple[list[tuple[tuple[str, ...], dict]], dict[tuple[str, ...], list[dict]]]:
    """Processa o arquivo (do zero, ignorando qualquer cache) e salva o
    resultado em disco — usado por scripts/pre_converter_camadas.py."""
    resultado = _grupos_e_links_do_arquivo_sem_cache(path)
    grupos, network_links = resultado

    cache_path = _caminho_cache_disco(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    dados = _serializar_resultado(grupos, network_links)
    dados["mtime_origem"] = path.stat().st_mtime
    with cache_path.open("w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False)

    return resultado


def _ler_cache_disco(
    path: Path,
) -> tuple[list[tuple[tuple[str, ...], dict]], dict[tuple[str, ...], list[dict]]] | None:
    if not cache_disco_atualizado(path):
        return None
    cache_path = _caminho_cache_disco(path)
    try:
        with cache_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return _desserializar_resultado(data)
    except (json.JSONDecodeError, OSError, KeyError):
        return None


def _grupos_e_links_do_arquivo(
    path: Path,
) -> tuple[list[tuple[tuple[str, ...], dict]], dict[tuple[str, ...], list[dict]]]:
    resolvido = path.resolve()
    mtime = path.stat().st_mtime
    em_cache = _cache_arquivos.get(resolvido)
    if em_cache is not None and em_cache[0] == mtime:
        return em_cache[1]

    do_disco = _ler_cache_disco(path)
    if do_disco is not None:
        _cache_arquivos[resolvido] = (mtime, do_disco)
        return do_disco

    resultado = _grupos_e_links_do_arquivo_sem_cache(path)
    _cache_arquivos[resolvido] = (mtime, resultado)
    return resultado


def _layer_id(base: str, caminho: tuple[str, ...]) -> str:
    if not caminho:
        return base
    return f"{base}{_GROUP_SEP}{'--'.join(_slug(p) for p in caminho)}"


def _nome_arquivo_exibicao(stem: str) -> str:
    return stem.replace("_", " ").replace("-", " ").title()


def _layer_info(layer_id: str, nome: str, geojson: dict, formato: str, mtime: float, intervalo: float | None) -> dict:
    features = geojson.get("features", [])
    info = {
        "id": layer_id,
        "nome": nome,
        "formato": formato,
        "feature_count": len(features),
        "geometry_type": features[0].get("geometry", {}).get("type") if features else None,
        "cor_padrao": cor_padrao_da_camada(layer_id),
        "atualizado_em": mtime,
    }
    if intervalo:
        info["intervalo_atualizacao_segundos"] = intervalo
    return info


def _montar_arvore(
    id_base: str,
    nome_raiz: str,
    formato: str,
    mtime: float,
    grupos: list[tuple[tuple[str, ...], dict]],
    network_links: dict[tuple[str, ...], list[dict]],
    base_dir: Path,
    visitados: frozenset[Path],
    intervalo_herdado: float | None,
) -> dict:
    por_caminho = {caminho: geojson for caminho, geojson in grupos}

    todos_caminhos: set[tuple[str, ...]] = {()}
    for caminho in por_caminho:
        for i in range(len(caminho) + 1):
            todos_caminhos.add(caminho[:i])
    for caminho in network_links:
        for i in range(len(caminho) + 1):
            todos_caminhos.add(caminho[:i])

    filhos_de: dict[tuple[str, ...], list[tuple[str, ...]]] = {}
    for caminho in todos_caminhos:
        if not caminho:
            continue
        pai = caminho[:-1]
        filhos_de.setdefault(pai, []).append(caminho)
    for pai in filhos_de:
        filhos_de[pai].sort(key=lambda c: c[-1].lower())

    def construir_no(caminho: tuple[str, ...]) -> dict:
        layer_id = _layer_id(id_base, caminho)
        nome = caminho[-1] if caminho else nome_raiz
        geojson = por_caminho.get(caminho)
        camada = _layer_info(layer_id, nome, geojson, formato, mtime, intervalo_herdado) if geojson is not None else None
        criancas = [construir_no(filho) for filho in filhos_de.get(caminho, [])]

        for link in network_links.get(caminho, []):
            criancas.append(_resolver_networklink(link, base_dir, visitados))

        return {"nome": nome, "camada": camada, "criancas": criancas}

    return construir_no(())


def _resolver_networklink(link: dict, base_dir: Path, visitados: frozenset[Path]) -> dict:
    nome = link["nome"]
    alvo = _resolver_href(link["href"], base_dir)

    if alvo is None:
        return {"nome": nome, "camada": None, "criancas": [], "erro": "só é suportado link para arquivo local/rede (não http)"}
    if len(visitados) >= _MAX_PROFUNDIDADE_LINKS:
        return {"nome": nome, "camada": None, "criancas": [], "erro": "muitos links encadeados (possível ciclo) — ignorado"}
    if not alvo.is_file():
        return {"nome": nome, "camada": None, "criancas": [], "erro": f"arquivo não encontrado: {alvo}"}
    if alvo.suffix.lower() not in _SUPPORTED_EXTENSIONS:
        return {"nome": nome, "camada": None, "criancas": [], "erro": f"formato não suportado: {alvo.suffix}"}

    alvo_resolvido = alvo.resolve()
    if alvo_resolvido in visitados:
        return {"nome": nome, "camada": None, "criancas": [], "erro": "link circular detectado — ignorado"}

    try:
        grupos, network_links = _grupos_e_links_do_arquivo(alvo)
    except (json.JSONDecodeError, OSError, kml_module.KmlParseError, LayerReadError) as exc:
        return {"nome": nome, "camada": None, "criancas": [], "erro": str(exc)}

    no = _montar_arvore(
        id_base=_encode_link_id(alvo_resolvido),
        nome_raiz=nome,
        formato=alvo.suffix.lstrip(".").lower(),
        mtime=alvo.stat().st_mtime,
        grupos=grupos,
        network_links=network_links,
        base_dir=alvo.parent,
        visitados=visitados | {alvo_resolvido},
        intervalo_herdado=link.get("intervalo_atualizacao_segundos"),
    )
    no["de_network_link"] = True
    return no


def _processar_arquivo_da_camada(path: Path) -> dict | None:
    """Processa um arquivo de camada (achado na pasta ou em subpastas) e
    devolve o nó de árvore correspondente — mesma lógica usada tanto pra
    arquivos na pasta de camadas quanto pra arquivos apontados por
    <NetworkLink> (por isso o id usa o caminho absoluto codificado, do
    mesmo jeito nos dois casos)."""
    try:
        grupos, network_links = _grupos_e_links_do_arquivo(path)
    except (json.JSONDecodeError, OSError, kml_module.KmlParseError, LayerReadError):
        return None

    return _montar_arvore(
        id_base=_encode_link_id(path.resolve()),
        nome_raiz=_nome_arquivo_exibicao(path.stem),
        formato=path.suffix.lstrip(".").lower(),
        mtime=path.stat().st_mtime,
        grupos=grupos,
        network_links=network_links,
        base_dir=path.parent,
        visitados=frozenset({path.resolve()}),
        intervalo_herdado=None,
    )


def _construir_arvore_pasta(diretorio: Path) -> list[dict]:
    """Monta a lista de nós (arquivos e subpastas) dentro de uma pasta —
    subpastas de verdade no disco viram pastas no painel, do mesmo jeito
    que você organizaria qualquer arquivo no Windows. Assim dá pra
    manter camadas GeoJSON organizadas em grupos, já que o GeoJSON (ao
    contrário do KML) não tem esse conceito de pasta embutido."""
    nos: list[dict] = []
    stems_vistos: set[str] = set()

    try:
        entradas = sorted(diretorio.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return nos

    for entrada in entradas:
        if entrada.name.startswith("."):
            continue  # pastas/arquivos ocultos (ex: .sigview_cache)

        if entrada.is_dir():
            criancas = _construir_arvore_pasta(entrada)
            if criancas:
                nos.append({"nome": entrada.name, "camada": None, "criancas": criancas})
            continue

        if entrada.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            continue
        stem = entrada.stem
        if stem in stems_vistos:
            continue  # evita duplicar se existir ex: bairros.geojson E bairros.kml
        stems_vistos.add(stem)

        no = _processar_arquivo_da_camada(entrada)
        if no is not None:
            nos.append(no)

    return nos


def list_layers() -> list[dict]:
    """Devolve a árvore de camadas disponíveis: subpastas de verdade no
    disco viram pastas no painel, e cada arquivo pode ter sua própria
    camada e/ou sub-pastas internas do KML — igual ao painel "Locais" do
    Google Earth. <NetworkLink> são resolvidos recursivamente e entram
    na árvore no lugar onde apareceram."""
    layers_dir = settings.layers_dir
    if not layers_dir.exists():
        return []
    return _construir_arvore_pasta(layers_dir)


def _resolver_grupo(grupos: list[tuple[tuple[str, ...], dict]], slugs_pedidos: list[str], layer_id: str) -> dict:
    if not slugs_pedidos:
        for caminho, geojson in grupos:
            if not caminho:
                return geojson
        raise LayerNotFound(layer_id)
    for caminho, geojson in grupos:
        if [_slug(p) for p in caminho] == slugs_pedidos:
            return geojson
    raise LayerNotFound(layer_id)


def get_layer(layer_id: str) -> dict:
    base_id, _, resto = layer_id.partition(_GROUP_SEP)
    slugs_pedidos = resto.split("--") if resto else []

    if base_id.startswith(_LINK_PREFIX):
        try:
            path = _decode_link_id(base_id)
        except Exception as exc:  # id malformado/adulterado
            raise LayerNotFound(layer_id) from exc
        if not path.is_file():
            raise LayerNotFound(layer_id)
    else:
        path = _find_source_file(base_id)
        if path is None:
            raise LayerNotFound(layer_id)

    try:
        grupos, _ = _grupos_e_links_do_arquivo(path)
    except kml_module.KmlParseError as exc:
        raise LayerReadError(str(exc)) from exc

    return _resolver_grupo(grupos, slugs_pedidos, layer_id)
