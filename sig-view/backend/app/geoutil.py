"""Utilitários geométricos simples, compartilhados entre os scripts de
vínculo/correção de polígonos e a indexação de busca."""
from __future__ import annotations


def centroide_aproximado(geometry: dict) -> tuple[float, float] | None:
    """Centroide aproximado (média dos vértices) — usado só pra localizar
    visualmente/buscar um polígono, não é o centroide geométrico exato
    (que ponderaria por área)."""

    def pontos(coords, tipo):
        if tipo == "Point":
            yield coords
        elif tipo in ("LineString", "MultiPoint"):
            yield from coords
        elif tipo in ("Polygon", "MultiLineString"):
            for parte in coords:
                yield from parte
        elif tipo == "MultiPolygon":
            for poligono in coords:
                for anel in poligono:
                    yield from anel

    tipo = geometry.get("type")
    coords = geometry.get("coordinates")
    if tipo is None or coords is None:
        return None
    xs, ys, n = 0.0, 0.0, 0
    for p in pontos(coords, tipo):
        xs += p[0]
        ys += p[1]
        n += 1
    return (xs / n, ys / n) if n else None
