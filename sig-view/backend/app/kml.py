"""Conversão de KML/KMZ para GeoJSON.

Permite que camadas exportadas do Google Earth / Google My Maps (.kml,
ou .kmz que é um .kml compactado em zip) sejam colocadas direto na pasta
de camadas, do mesmo jeito que um .geojson — o backend converte na hora
de servir.

Só usa a biblioteca padrão do Python (xml.etree, zipfile), sem
dependências extras. Cobre os casos mais comuns de Placemark: Point,
LineString, Polygon (com buracos) e MultiGeometry (é "achatado" em várias
features, já que o GeoJSON não tem um equivalente direto tão bem
suportado pelo MapLibre).
"""
from __future__ import annotations

import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET

# "{*}tag" casa com "tag" em qualquer namespace (ou nenhum) — os arquivos
# KML variam entre "http://www.opengis.net/kml/2.2", 2.1, 2.0, ou às
# vezes nenhum namespace declarado.
_ANY_NS = "{*}"


class KmlParseError(ValueError):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(elem: ET.Element, path: str) -> str | None:
    found = elem.find(path)
    if found is not None and found.text:
        return found.text.strip()
    return None


def _parse_coordinates(text: str) -> list[list[float]]:
    coords: list[list[float]] = []
    for chunk in text.split():
        parts = chunk.split(",")
        if len(parts) < 2:
            continue
        try:
            lon, lat = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        if len(parts) >= 3 and parts[2]:
            try:
                coords.append([lon, lat, float(parts[2])])
                continue
            except ValueError:
                pass
        coords.append([lon, lat])
    return coords


def _ring(boundary_elem: ET.Element) -> list[list[float]] | None:
    coords_el = boundary_elem.find(f"{_ANY_NS}LinearRing/{_ANY_NS}coordinates")
    if coords_el is None or not coords_el.text:
        return None
    coords = _parse_coordinates(coords_el.text)
    return coords or None


def _geometry(elem: ET.Element) -> dict | None:
    tag = _local(elem.tag)

    if tag == "Point":
        coords_el = elem.find(f"{_ANY_NS}coordinates")
        if coords_el is None or not coords_el.text:
            return None
        coords = _parse_coordinates(coords_el.text)
        return {"type": "Point", "coordinates": coords[0]} if coords else None

    if tag == "LineString":
        coords_el = elem.find(f"{_ANY_NS}coordinates")
        if coords_el is None or not coords_el.text:
            return None
        coords = _parse_coordinates(coords_el.text)
        return {"type": "LineString", "coordinates": coords} if coords else None

    if tag == "Polygon":
        outer = elem.find(f"{_ANY_NS}outerBoundaryIs")
        if outer is None:
            return None
        outer_ring = _ring(outer)
        if not outer_ring:
            return None
        rings = [outer_ring]
        for inner in elem.findall(f"{_ANY_NS}innerBoundaryIs"):
            ring = _ring(inner)
            if ring:
                rings.append(ring)
        return {"type": "Polygon", "coordinates": rings}

    return None


def _placemark_geometries(placemark: ET.Element) -> list[dict]:
    geometries: list[dict] = []
    for child in placemark:
        tag = _local(child.tag)
        if tag == "MultiGeometry":
            for sub in child:
                geom = _geometry(sub)
                if geom:
                    geometries.append(geom)
        elif tag in ("Point", "LineString", "Polygon"):
            geom = _geometry(child)
            if geom:
                geometries.append(geom)
    return geometries


def _extended_data(placemark: ET.Element) -> dict:
    props: dict[str, str | None] = {}
    ext = placemark.find(f"{_ANY_NS}ExtendedData")
    if ext is None:
        return props
    for data in ext.findall(f"{_ANY_NS}Data"):
        key = data.get("name")
        value_el = data.find(f"{_ANY_NS}value")
        if key:
            props[key] = value_el.text if value_el is not None else None
    for simple in ext.findall(f".//{_ANY_NS}SimpleData"):
        key = simple.get("name")
        if key:
            props[key] = simple.text
    return props


def _placemark_to_features(placemark: ET.Element) -> list[dict]:
    props = _extended_data(placemark)
    name = _text(placemark, f"{_ANY_NS}name")
    description = _text(placemark, f"{_ANY_NS}description")
    if name:
        props.setdefault("nome", name)
    if description:
        props.setdefault("descricao", description)

    geometries = _placemark_geometries(placemark)
    return [{"type": "Feature", "properties": dict(props), "geometry": g} for g in geometries]


def parse_kml_bytes(data: bytes) -> dict:
    """Converte o conteúdo de um arquivo .kml (bytes) para um dict GeoJSON
    (FeatureCollection)."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise KmlParseError(f"KML inválido: {exc}") from exc

    # Nota: Element.iter() só faz correspondência exata de tag (sem
    # suporte a wildcard de namespace) — por isso usamos findall() com
    # ".//", que passa pelo resolvedor de XPath do ElementTree.
    features: list[dict] = []
    for placemark in root.findall(f".//{_ANY_NS}Placemark"):
        features.extend(_placemark_to_features(placemark))
    return {"type": "FeatureCollection", "features": features}


def parse_kmz_bytes(data: bytes) -> dict:
    """Converte o conteúdo de um arquivo .kmz (bytes, é um .kml dentro de
    um .zip) para um dict GeoJSON."""
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            names = zf.namelist()
            kml_name = next((n for n in names if n.lower() == "doc.kml"), None)
            if kml_name is None:
                kml_name = next((n for n in names if n.lower().endswith(".kml")), None)
            if kml_name is None:
                raise KmlParseError("Nenhum arquivo .kml encontrado dentro do .kmz")
            return parse_kml_bytes(zf.read(kml_name))
    except zipfile.BadZipFile as exc:
        raise KmlParseError(f"KMZ inválido (não é um zip válido): {exc}") from exc
