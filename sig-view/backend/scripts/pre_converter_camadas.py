#!/usr/bin/env python3
"""Pré-converte os KML/KMZ da pasta de camadas, salvando o resultado já
processado em disco — evita que o programa precise reprocessar o XML
inteiro na primeira vez que alguém abre cada camada depois de reiniciar
(o cache do programa em si é só em memória, e se perde a cada reinício).

Rode isso uma vez, e de novo sempre que os KMLs originais mudarem (ex:
depois de rodar vincular_poligonos.py / aplicar_correcoes_poligonos.py,
ou substituir um arquivo manualmente). Arquivos já convertidos e sem
mudança são pulados automaticamente — só reconverte o que realmente
mudou (compara a data de modificação).

Uso:
    python scripts/pre_converter_camadas.py
    python scripts/pre_converter_camadas.py --forcar   (reconverte tudo, mesmo sem mudança)
    python scripts/pre_converter_camadas.py --pasta caminho\\para\\outras\\camadas
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import layers as layers_module  # noqa: E402
from app.config import settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--forcar", action="store_true", help="Reconverte mesmo os arquivos já atualizados")
    parser.add_argument("--pasta", type=Path, default=None, help="Pasta de camadas (padrão: a configurada no programa)")
    args = parser.parse_args()

    layers_dir = args.pasta or settings.layers_dir
    if not layers_dir.exists():
        sys.exit(f"Pasta de camadas não encontrada: {layers_dir}")

    print(f"Pasta: {layers_dir}\n")

    convertidos = 0
    pulados = 0
    erros = 0

    for path in sorted(layers_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in (".kml", ".kmz"):
            continue

        if not args.forcar and layers_module.cache_disco_atualizado(path):
            print(f"[já atualizado, pulando] {path.name}")
            pulados += 1
            continue

        print(f"[convertendo] {path.name} ...", end=" ", flush=True)
        inicio = time.time()
        try:
            grupos, _ = layers_module.gerar_cache_disco(path)
        except Exception as exc:  # arquivo corrompido, etc — não trava o resto
            print(f"ERRO: {exc}")
            erros += 1
            continue
        duracao = time.time() - inicio
        total_features = sum(len(geojson.get("features", [])) for _, geojson in grupos)
        print(f"ok ({len(grupos)} camada(s), {total_features} feature(s), {duracao:.1f}s)")
        convertidos += 1

    print(f"\n{convertidos} convertido(s), {pulados} já estavam atualizados, {erros} com erro.")
    if convertidos or pulados:
        print("O programa vai usar essa versão pré-processada automaticamente — não precisa configurar nada.")


if __name__ == "__main__":
    main()
