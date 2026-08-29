"""Utilitários geométricos simples, compartilhados entre os scripts de
vínculo/correção de polígonos e a indexação de busca."""
from __future__ import annotations

import math


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


# Elipsoide GRS80 — o que o SIRGAS 2000 usa (praticamente idêntico ao
# WGS84 pra qualquer efeito prático, a diferença é bem menor que a
# precisão de GPS comum). São Paulo inteira cai na zona UTM 23S.
_UTM_A = 6378137.0
_UTM_F = 1 / 298.257222101
_UTM_E2 = _UTM_F * (2 - _UTM_F)
_UTM_EP2 = _UTM_E2 / (1 - _UTM_E2)
_UTM_K0 = 0.9996


def utm_para_latlon(easting: float, northing: float, zona: int, norte: bool = False) -> tuple[float, float]:
    """Converte coordenadas UTM (metros) pra latitude/longitude (graus,
    WGS84) — fórmula-padrão de Transversa de Mercator inversa (a mesma
    usada por qualquer biblioteca de projeção, ex: pyproj/proj4), sem
    precisar de nenhuma dependência externa. Testado por ida-e-volta
    com erro sub-milimétrico em vários pontos de São Paulo.

    O GeoSampa publica os dados oficiais em SIRGAS 2000 / UTM 23S
    (EPSG:31983) — é o caso de uso principal disto (zona=23,
    norte=False, hemisfério sul)."""
    x = easting - 500000.0
    y = northing if norte else northing - 10000000.0

    m = y / _UTM_K0
    mu = m / (_UTM_A * (1 - _UTM_E2 / 4 - 3 * _UTM_E2**2 / 64 - 5 * _UTM_E2**3 / 256))

    e1 = (1 - math.sqrt(1 - _UTM_E2)) / (1 + math.sqrt(1 - _UTM_E2))
    j1 = 3 * e1 / 2 - 27 * e1**3 / 32
    j2 = 21 * e1**2 / 16 - 55 * e1**4 / 32
    j3 = 151 * e1**3 / 96
    j4 = 1097 * e1**4 / 512
    fp = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)

    c1 = _UTM_EP2 * math.cos(fp) ** 2
    t1 = math.tan(fp) ** 2
    r1 = _UTM_A * (1 - _UTM_E2) / (1 - _UTM_E2 * math.sin(fp) ** 2) ** 1.5
    n1 = _UTM_A / math.sqrt(1 - _UTM_E2 * math.sin(fp) ** 2)
    d = x / (n1 * _UTM_K0)

    q1 = n1 * math.tan(fp) / r1
    q2 = d**2 / 2
    q3 = (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * _UTM_EP2) * d**4 / 24
    q4 = (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 3 * c1**2 - 252 * _UTM_EP2) * d**6 / 720
    lat = fp - q1 * (q2 - q3 + q4)

    q6 = (1 + 2 * t1 + c1) * d**3 / 6
    q7 = (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * _UTM_EP2 + 24 * t1**2) * d**5 / 120
    lon_offset = (d - q6 + q7) / math.cos(fp)

    meridiano_central = math.radians(-183 + 6 * zona)
    return math.degrees(lat), math.degrees(meridiano_central + lon_offset)
