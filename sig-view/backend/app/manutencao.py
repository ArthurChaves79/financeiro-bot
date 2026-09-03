"""Painel de manutenção — roda, de dentro do próprio programa, os
scripts de `scripts/` que antes só davam pra rodar via linha de
comando (reindexar camadas, reconstruir o índice de busca, vincular
polígonos a um banco existente). Pensado pra quem administra o SIG
View não precisar abrir um terminal nem lembrar os nomes/parâmetros
exatos de cada script.

Cada tarefa roda numa thread separada (podem demorar — dezenas de
milhares de registros), uma de cada vez (ver `_lock_execucao`), e o
frontend acompanha o andamento perguntando o status a cada ~1s — ver
as rotas /api/manutencao/* em app/main.py.

As funções de cada script (build_geocoder_index.build,
indexar_camadas.indexar, vincular_poligonos.vincular etc.) já eram
"puras" o bastante (recebem parâmetros, não leem argv) pra serem
chamadas direto daqui, sem duplicar a lógica — só a parte de
"argparse + imprimir no terminal" fica de fora, substituída pelo
catálogo de campos abaixo e pelo log capturado por
_StreamParaLog.
"""
from __future__ import annotations

import contextlib
import csv as csv_module
import io
import json
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from . import campos_conhecidos as _campos_conhecidos_para_empacotar  # noqa: F401
from . import geoutil as _geoutil_para_empacotar  # noqa: F401
from .config import settings

# Os imports "mortos" acima (geoutil/campos_conhecidos, sem uso direto
# aqui) são de propósito: indexar_camadas.py e vincular_poligonos.py
# (importados mais abaixo) fazem "from app.geoutil import
# centroide_aproximado" / "from app import campos_conhecidos", mas como
# eles são carregados dinamicamente (via sys.path, não um "import"
# literal que o PyInstaller consiga seguir), a análise estática do
# PyInstaller nunca descobre sozinha que esses módulos precisam ir no
# .exe — sem isso ele falha em runtime com "ImportError: cannot import
# name ... from 'app'", só ao tentar rodar uma tarefa do painel de
# Manutenção (não na subida do programa, então passa despercebido até
# alguém usar o painel — foi exatamente assim que o de campos_conhecidos
# escapou: só apareceu depois de gerar um novo .exe, não durante o
# desenvolvimento). Um "import ... as _algo_para_empacotar" aqui, no
# arquivo que o PyInstaller SEGUE de verdade (é importado por
# app/main.py), força ele a empacotar o módulo mesmo sem uso direto.

# Em modo normal, scripts/ é uma pasta irmã de app/ (backend/scripts).
# No .exe empacotado (PyInstaller), ela é distribuída como dado
# (--add-data, ver gerar_executavel.bat) e extraída em sys._MEIPASS —
# mesma ideia já usada em main.py para FRONTEND_DIR.
if getattr(sys, "frozen", False):
    SCRIPTS_DIR = Path(getattr(sys, "_MEIPASS")) / "scripts"
else:
    SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_geocoder_index  # noqa: E402
import indexar_camadas  # noqa: E402
import vincular_poligonos  # noqa: E402


class TarefaInvalida(ValueError):
    """Parâmetro faltando/errado, ou id de tarefa/execução desconhecido —
    vira HTTP 400/404 em app/main.py, com a mensagem mostrada direto no
    painel (por isso sempre em português, explicando o que corrigir)."""


def _campo(
    nome: str,
    rotulo: str,
    *,
    obrigatorio: bool = True,
    padrao: str = "",
    ajuda: str = "",
    lista: bool = False,
) -> dict[str, Any]:
    return {
        "nome": nome,
        "rotulo": rotulo,
        "obrigatorio": obrigatorio,
        "padrao": padrao,
        "ajuda": ajuda,
        "lista": lista,  # campo "lista" aceita vários valores separados por vírgula
    }


def _tarefas_catalogo() -> dict[str, dict[str, Any]]:
    # Função (não uma constante) porque os valores "padrão" usam a
    # configuração ATUAL (ex: caminho de hoje do geocoder.db) — ela
    # pode mudar em ⚙ Configurações sem reiniciar o programa.
    return {
        "reindexar_camadas": {
            "nome": "Reindexar camadas da pasta",
            "descricao": (
                "Varre a pasta de camadas (e subpastas) e recoloca, no "
                "índice de busca, os atributos de cada .geojson/.kml/"
                ".kmz encontrado — pra buscar por Setor-Quadra-Lote, "
                "Matrícula, Transcrição, número do contribuinte etc. na "
                "caixa de busca do mapa (e já mostrar o lote encontrado, "
                "não só um marcador solto). Rode depois de adicionar ou "
                "atualizar camadas na pasta. Os campos são reconhecidos "
                "AUTOMATICAMENTE (mesmos nomes que a barra de detalhes já "
                "reconhece) — normalmente não precisa preencher nada além "
                "da Pasta/Banco abaixo, que já vêm com o valor configurado."
            ),
            "campos": [
                _campo("pasta", "Pasta de camadas", padrao=str(settings.layers_dir)),
                _campo("db", "Banco de busca (geocoder.db)", padrao=str(settings.geocoder_db)),
                _campo("tipo", "Tipo", obrigatorio=False, padrao="imovel"),
                _campo(
                    "rotulo", "Forçar campos pesquisáveis (rótulo)", obrigatorio=False, lista=True,
                    ajuda=(
                        "Deixe em branco — o reconhecimento automático já pega contribuinte (ou "
                        "Setor.Quadra.Lote), matrícula, transcrição, loteamento e endereço sozinho, pelos "
                        "nomes de propriedade mais comuns (inclusive os que o SIG Editor de Lotes exporta). "
                        "Só preencha se sua camada usar nomes de campo bem fora do comum e o automático não "
                        "estiver achando o que você esperava — nesse caso, liste os nomes das propriedades da "
                        "feature separados por vírgula (ex: numero_contribuinte, setor, quadra, lote)."
                    ),
                ),
                _campo(
                    "logradouro", "Forçar campo de endereço", obrigatorio=False,
                    ajuda="Deixe em branco pro automático reconhecer (endereço pronto, ou tipo+logradouro+número). Só preencha pra forçar um nome de propriedade específico.",
                ),
                _campo("bairro", "Forçar campo de bairro", obrigatorio=False, ajuda="Deixe em branco pro automático reconhecer."),
                _campo("cidade", "Forçar campo de cidade", obrigatorio=False, ajuda="Deixe em branco pro automático reconhecer."),
            ],
        },
        "reconstruir_indice_busca": {
            "nome": "Reconstruir índice de busca (a partir de CSV)",
            "descricao": (
                "Apaga e reconstrói data/geocoder.db do zero, a partir de "
                "um ou mais CSVs de endereço/CEP/bairro (ex: os gerados "
                "por converter_geosampa_logradouros.py ou "
                "converter_geopackage_geosampa.py). CUIDADO: isso também "
                "apaga os dados de camadas já indexados por 'Reindexar "
                "camadas' — rode aquela tarefa de novo depois, se "
                "precisar deles de volta. Uma cópia do banco anterior é "
                "sempre guardada antes, em data/backups."
            ),
            "campos": [
                _campo(
                    "csv_paths", "CSV(s) de entrada", lista=True,
                    ajuda="Um ou mais caminhos, separados por vírgula (ex: um de ruas e outro de bairros).",
                ),
                _campo("db", "Banco de busca de saída", padrao=str(settings.geocoder_db)),
            ],
        },
        "vincular_poligonos": {
            "nome": "Vincular polígonos a um banco existente",
            "descricao": (
                "Junta um arquivo de polígonos (.geojson/.kml/.kmz) com um "
                "CSV exportado do banco relacional existente, casando "
                "pela chave em comum (padrão: número do contribuinte), e "
                "gera uma camada .geojson pronta pra colocar na pasta de "
                "camadas — junto com um CSV de pendências, para os "
                "polígonos que não deu pra casar."
            ),
            "campos": [
                _campo("poligonos", "Arquivo de polígonos (.geojson/.kml/.kmz)"),
                _campo("atributos_csv", "CSV de atributos (exportado do banco)"),
                _campo("chave", "Coluna-chave", obrigatorio=False, padrao="numero_contribuinte"),
                _campo("complemento", "CSV de complemento (opcional)", obrigatorio=False),
                _campo("vinculos_manuais", "CSV de vínculos manuais (opcional)", obrigatorio=False),
                _campo("saida", "Camada .geojson de saída", padrao=str(settings.layers_dir / "imoveis.geojson")),
                _campo("pendencias", "CSV de pendências", padrao=str(settings.layers_dir.parent / "pendencias.csv")),
            ],
        },
    }


def listar_tarefas() -> list[dict[str, Any]]:
    return [{"id": tarefa_id, **dados} for tarefa_id, dados in _tarefas_catalogo().items()]


# --- Execução em segundo plano ------------------------------------------

_execucoes: dict[str, dict[str, Any]] = {}
_execucoes_lock = threading.Lock()

# Só uma tarefa de manutenção por vez — evita duas mexendo no mesmo
# geocoder.db ao mesmo tempo, e evita o problema de contextlib.
# redirect_stdout ser global ao processo (não por thread): com uma só
# tarefa rodando, não tem risco de uma "roubar" o log da outra.
_execucao_atual_id: str | None = None


class _StreamParaLog(io.TextIOBase):
    """Recebe o que a tarefa dá de print() e guarda linha a linha no log
    da execução, pra aparecer no painel progressivamente (sem esperar
    terminar pra ver alguma coisa)."""

    def __init__(self, execucao_id: str) -> None:
        self._execucao_id = execucao_id
        self._buffer = ""

    def write(self, texto: str) -> int:
        self._buffer += texto
        while "\n" in self._buffer:
            linha, self._buffer = self._buffer.split("\n", 1)
            if linha:
                _adicionar_log(self._execucao_id, linha)
        return len(texto)

    def flush(self) -> None:
        if self._buffer:
            _adicionar_log(self._execucao_id, self._buffer)
            self._buffer = ""


def _adicionar_log(execucao_id: str, linha: str) -> None:
    with _execucoes_lock:
        execucao = _execucoes.get(execucao_id)
        if execucao is not None:
            execucao["log"].append(linha)


def _lista_de(valor: Any) -> list[str]:
    """Campos "lista" chegam do frontend como uma única string separada
    por vírgula (ex: "setor, quadra, lote") — normaliza pra list[str]."""
    if isinstance(valor, list):
        return [str(item).strip() for item in valor if str(item).strip()]
    return [pedaco.strip() for pedaco in str(valor or "").split(",") if pedaco.strip()]


def _caminho_opcional(valor: Any) -> Path | None:
    texto = str(valor or "").strip()
    return Path(texto) if texto else None


def _executar_reindexar_camadas(parametros: dict[str, Any]) -> None:
    pasta = Path(str(parametros.get("pasta") or "").strip())
    db = Path(str(parametros.get("db") or "").strip())
    tipo = str(parametros.get("tipo") or "imovel").strip() or "imovel"
    campos_rotulo = _lista_de(parametros.get("rotulo"))
    logradouro = str(parametros.get("logradouro") or "").strip() or None
    bairro = str(parametros.get("bairro") or "").strip() or None
    cidade = str(parametros.get("cidade") or "").strip() or None

    if not str(pasta):
        raise TarefaInvalida("Informe a pasta de camadas.")
    if not pasta.exists():
        raise TarefaInvalida(f"Pasta não encontrada: {pasta}")
    # campos_rotulo vazio = reconhecimento automático (ver indexar_camadas.indexar
    # e app/campos_conhecidos.py) - não é mais obrigatório digitar nada aqui

    extensoes = (".geojson", ".kml", ".kmz")
    arquivos = sorted(
        p for p in pasta.rglob("*")
        if p.is_file() and p.suffix.lower() in extensoes and ".sigview_cache" not in p.parts
    )
    if not arquivos:
        raise TarefaInvalida(f"Nenhum .geojson/.kml/.kmz encontrado em {pasta}")

    total_inseridos = 0
    total_ignorados = 0
    for path in arquivos:
        layer_id = "/".join(path.relative_to(pasta).with_suffix("").parts)
        try:
            inseridos, ignorados = indexar_camadas.indexar(
                path, db, layer_id, campos_rotulo, tipo, logradouro, bairro, cidade
            )
        except Exception as exc:  # um arquivo com problema não para o resto
            print(f"[ERRO] {path}: {exc}")
            continue
        print(f"{layer_id}: {inseridos} indexado(s)" + (f", {ignorados} ignorado(s)" if ignorados else ""))
        total_inseridos += inseridos
        total_ignorados += ignorados

    print(f"\nTotal: {total_inseridos} registro(s) indexado(s) em {len(arquivos)} arquivo(s).")
    if total_ignorados:
        print(f"({total_ignorados} feature(s) ignorada(s) no total, por não terem geometria válida)")


def _executar_reconstruir_indice_busca(parametros: dict[str, Any]) -> None:
    csv_paths = [Path(p) for p in _lista_de(parametros.get("csv_paths"))]
    db = Path(str(parametros.get("db") or "").strip())

    if not str(db):
        raise TarefaInvalida("Informe o banco de busca de saída.")
    if not csv_paths:
        raise TarefaInvalida("Informe ao menos um caminho de CSV.")
    faltando = [str(p) for p in csv_paths if not p.exists()]
    if faltando:
        raise TarefaInvalida(f"Arquivo(s) não encontrado(s): {faltando}")

    try:
        count = build_geocoder_index.build(csv_paths, db, {})
    except SystemExit as exc:
        # build() usa SystemExit(mensagem) pra recusar um CSV vazio/
        # inválido sem apagar o índice existente — ver o comentário
        # dentro dela. Vira erro normal aqui, não derruba a thread.
        raise TarefaInvalida(str(exc.code) if exc.code else "CSV inválido.") from exc
    print(f"Índice construído em {db} com {count} registro(s).")


def _executar_vincular_poligonos(parametros: dict[str, Any]) -> None:
    poligonos_path = Path(str(parametros.get("poligonos") or "").strip())
    atributos_path = Path(str(parametros.get("atributos_csv") or "").strip())
    chave = str(parametros.get("chave") or "numero_contribuinte").strip() or "numero_contribuinte"
    complemento_path = _caminho_opcional(parametros.get("complemento"))
    vinculos_path = _caminho_opcional(parametros.get("vinculos_manuais"))
    saida = Path(str(parametros.get("saida") or "").strip())
    pendencias_path = Path(str(parametros.get("pendencias") or "pendencias.csv").strip())

    for rotulo, caminho in (("polígonos", poligonos_path), ("atributos", atributos_path)):
        if not str(caminho):
            raise TarefaInvalida(f"Informe o arquivo de {rotulo}.")
        if not caminho.exists():
            raise TarefaInvalida(f"Arquivo de {rotulo} não encontrado: {caminho}")
    if not str(saida):
        raise TarefaInvalida("Informe o caminho da camada .geojson de saída.")
    for rotulo, caminho in (("complemento", complemento_path), ("vínculos manuais", vinculos_path)):
        if caminho is not None and not caminho.exists():
            raise TarefaInvalida(f"Arquivo de {rotulo} não encontrado: {caminho}")

    try:
        poligonos = vincular_poligonos.carregar_poligonos(poligonos_path)
        atributos = vincular_poligonos.carregar_csv_por_chave(atributos_path, chave)
        complemento = vincular_poligonos.carregar_csv_por_chave(complemento_path, chave) if complemento_path else {}
        vinculos_manuais = vincular_poligonos.carregar_vinculos_manuais(vinculos_path)
    except SystemExit as exc:
        raise TarefaInvalida(str(exc.code) if exc.code else "Arquivo de entrada inválido.") from exc

    resultado, pendencias = vincular_poligonos.vincular(poligonos, chave, atributos, complemento, vinculos_manuais)

    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(resultado["features"])
    vinculados = sum(1 for feature in resultado["features"] if feature["properties"].get("_vinculado"))
    print(f"Camada gerada: {saida}")
    print(f"  {vinculados}/{total} polígono(s) vinculado(s) a um registro do banco")

    if pendencias:
        with pendencias_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv_module.DictWriter(fh, fieldnames=["identificador_poligono", "motivo", "lon_aproximado", "lat_aproximado"])
            writer.writeheader()
            writer.writerows(pendencias)
        print(f"  {len(pendencias)} pendência(s) salva(s) em {pendencias_path} (revise e preencha vínculos manuais aos poucos)")
    else:
        print("  Nenhuma pendência — tudo vinculado!")


_EXECUTORES: dict[str, Callable[[dict[str, Any]], None]] = {
    "reindexar_camadas": _executar_reindexar_camadas,
    "reconstruir_indice_busca": _executar_reconstruir_indice_busca,
    "vincular_poligonos": _executar_vincular_poligonos,
}


def iniciar_execucao(tarefa_id: str, parametros: dict[str, Any]) -> str:
    global _execucao_atual_id

    executor = _EXECUTORES.get(tarefa_id)
    if executor is None:
        raise TarefaInvalida(f"Tarefa desconhecida: {tarefa_id}")

    with _execucoes_lock:
        em_andamento = _execucao_atual_id is not None and _execucoes.get(_execucao_atual_id, {}).get("status") == "executando"
        if em_andamento:
            raise TarefaInvalida("Já tem uma tarefa de manutenção em andamento — aguarde terminar antes de iniciar outra.")

        execucao_id = uuid.uuid4().hex
        _execucoes[execucao_id] = {
            "tarefa_id": tarefa_id,
            "status": "executando",
            "log": [],
            "erro": None,
            "inicio": time.time(),
        }
        _execucao_atual_id = execucao_id

    def _rodar() -> None:
        stream = _StreamParaLog(execucao_id)
        try:
            with contextlib.redirect_stdout(stream):
                executor(parametros)
            stream.flush()
            with _execucoes_lock:
                _execucoes[execucao_id]["status"] = "concluido"
        except TarefaInvalida as exc:
            stream.flush()
            with _execucoes_lock:
                _execucoes[execucao_id]["status"] = "erro"
                _execucoes[execucao_id]["erro"] = str(exc)
        except Exception as exc:  # nunca deixa uma tarefa travar o programa
            stream.flush()
            with _execucoes_lock:
                _execucoes[execucao_id]["status"] = "erro"
                _execucoes[execucao_id]["erro"] = f"{type(exc).__name__}: {exc}"

    threading.Thread(target=_rodar, daemon=True).start()
    return execucao_id


def obter_status(execucao_id: str) -> dict[str, Any]:
    with _execucoes_lock:
        execucao = _execucoes.get(execucao_id)
        if execucao is None:
            raise TarefaInvalida(f"Execução não encontrada: {execucao_id}")
        return {
            "status": execucao["status"],
            "log": list(execucao["log"]),
            "erro": execucao["erro"],
        }
