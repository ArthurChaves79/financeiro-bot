"""Re-sincronização automática/agendada das tarefas de manutenção (ver
app/manutencao.py) — item 6 do roteiro de melhorias.

Como o SIG View não fica rodando o tempo todo em cada um dos 78
computadores (cada pessoa abre e fecha o programa quando usa), a
"agenda" aqui é bem mais simples que uma Tarefa Agendada do Windows:
enquanto o programa estiver aberto, uma thread em segundo plano
verifica a cada minuto se alguma tarefa marcada como "automática" já
passou do intervalo configurado e, se sim, dispara ela sozinha —
igual ao NetworkLink de camadas (app.js: refreshTimers), só que do
lado do backend e pras tarefas de manutenção.

Pensado principalmente pra "Vincular polígonos a um banco existente"
(scripts/vincular_poligonos.py): quem administra deixa o CSV exportado
do banco relacional sendo atualizado periodicamente numa pasta de
rede (por outro processo, fora do SIG View), e agenda aqui pra
reprocessar esse CSV a cada N horas, sem precisar lembrar de clicar
"Rodar" toda vez.

Os parâmetros (caminhos dos CSVs etc.) ficam salvos em
`data/agendamentos.json` — persistem entre reinícios do programa,
igual ao config.json de Configurações.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import manutencao as manutencao_module
from .backup_util import backup_rotativo
from .config import BASE_DIR

AGENDAMENTOS_FILE = BASE_DIR / "data" / "agendamentos.json"
BACKUPS_DIR = BASE_DIR / "data" / "backups"

# De quanto em quanto tempo a thread de fundo acorda pra conferir se
# alguma tarefa automática já venceu — não precisa ser fino, é só uma
# verificação de "já passou da hora?", não uma execução em si.
INTERVALO_VERIFICACAO_SEGUNDOS = 60

_lock = threading.Lock()
_agendamentos: dict[str, dict[str, Any]] = {}
_carregado = False


class AgendamentoInvalido(ValueError):
    pass


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _carregar_do_disco() -> dict[str, dict[str, Any]]:
    if not AGENDAMENTOS_FILE.exists():
        return {}
    try:
        return json.loads(AGENDAMENTOS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _garantir_carregado() -> None:
    global _carregado
    if not _carregado:
        _agendamentos.update(_carregar_do_disco())
        _carregado = True


def _persistir() -> None:
    AGENDAMENTOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    backup_rotativo(AGENDAMENTOS_FILE, BACKUPS_DIR)
    AGENDAMENTOS_FILE.write_text(json.dumps(_agendamentos, ensure_ascii=False, indent=2), encoding="utf-8")


def listar_agendamentos() -> list[dict[str, Any]]:
    catalogo = {t["id"]: t["nome"] for t in manutencao_module.listar_tarefas()}
    with _lock:
        _garantir_carregado()
        resultado = []
        for tarefa_id, dados in _agendamentos.items():
            resultado.append(
                {
                    "tarefa_id": tarefa_id,
                    "nome": catalogo.get(tarefa_id, tarefa_id),
                    "ativo": bool(dados.get("ativo")),
                    "intervalo_horas": dados.get("intervalo_horas"),
                    "parametros": dados.get("parametros") or {},
                    "ultima_execucao": dados.get("ultima_execucao"),
                    "ultimo_status": dados.get("ultimo_status"),
                }
            )
        return resultado


def salvar_agendamento(tarefa_id: str, ativo: bool, intervalo_horas: float, parametros: dict[str, Any]) -> dict[str, Any]:
    ids_validos = {t["id"] for t in manutencao_module.listar_tarefas()}
    if tarefa_id not in ids_validos:
        raise AgendamentoInvalido(f"Tarefa desconhecida: {tarefa_id}")
    if ativo and (intervalo_horas is None or intervalo_horas <= 0):
        raise AgendamentoInvalido("Informe um intervalo (em horas) maior que zero para ligar a repetição automática.")

    with _lock:
        _garantir_carregado()
        anterior = _agendamentos.get(tarefa_id, {})
        _agendamentos[tarefa_id] = {
            "ativo": bool(ativo),
            "intervalo_horas": intervalo_horas,
            "parametros": parametros,
            # Preserva o histórico de quando rodou pela última vez —
            # só zera ao criar o agendamento pela primeira vez, não
            # toda vez que o usuário mexe no formulário e salva de novo.
            "ultima_execucao": anterior.get("ultima_execucao"),
            "ultimo_status": anterior.get("ultimo_status"),
        }
        _persistir()
        return dict(_agendamentos[tarefa_id])


def remover_agendamento(tarefa_id: str) -> None:
    with _lock:
        _garantir_carregado()
        if tarefa_id in _agendamentos:
            del _agendamentos[tarefa_id]
            _persistir()


def _registrar_disparo(tarefa_id: str, status: str) -> None:
    with _lock:
        if tarefa_id in _agendamentos:
            _agendamentos[tarefa_id]["ultima_execucao"] = _agora_iso()
            _agendamentos[tarefa_id]["ultimo_status"] = status
            _persistir()


def _deve_rodar_agora(dados: dict[str, Any]) -> bool:
    if not dados.get("ativo"):
        return False
    intervalo_horas = dados.get("intervalo_horas")
    if not intervalo_horas or intervalo_horas <= 0:
        return False
    ultima = dados.get("ultima_execucao")
    if not ultima:
        return True  # nunca rodou ainda -> roda na primeira verificação
    try:
        ultima_dt = datetime.fromisoformat(ultima)
    except ValueError:
        return True
    decorrido_horas = (datetime.now(timezone.utc) - ultima_dt).total_seconds() / 3600
    return decorrido_horas >= intervalo_horas


def _verificar_e_disparar() -> None:
    with _lock:
        _garantir_carregado()
        pendentes = [(tid, dict(dados)) for tid, dados in _agendamentos.items() if _deve_rodar_agora(dados)]

    for tarefa_id, dados in pendentes:
        try:
            manutencao_module.iniciar_execucao(tarefa_id, dados.get("parametros") or {})
        except manutencao_module.TarefaInvalida:
            # Outra tarefa (manual ou de outro agendamento) já está
            # rodando — não marca "ultima_execucao" pra tentar de novo
            # já na próxima verificação, em vez de esperar o intervalo
            # inteiro de novo.
            continue
        # Marca o disparo já aqui (não espera terminar) — a tarefa roda
        # em segundo plano por conta própria (ver manutencao.py); o que
        # importa pra agenda é não disparar de novo antes da hora.
        _registrar_disparo(tarefa_id, "disparado")


def _loop_verificacao() -> None:
    while True:
        try:
            _verificar_e_disparar()
        except Exception:
            # Nunca deixa um erro aqui derrubar a thread de agendamento
            # (ela precisa continuar rodando pro resto da vida do
            # programa) — na pior das hipóteses, uma tarefa agendada
            # simplesmente não dispara numa verificação específica.
            pass
        time.sleep(INTERVALO_VERIFICACAO_SEGUNDOS)


_thread_iniciada = False


def iniciar_verificacao_em_segundo_plano() -> None:
    """Chamado uma vez, na subida do programa (ver main.py, evento de
    startup). Idempotente — chamar de novo não cria uma segunda
    thread."""
    global _thread_iniciada
    if _thread_iniciada:
        return
    _thread_iniciada = True
    threading.Thread(target=_loop_verificacao, daemon=True).start()
