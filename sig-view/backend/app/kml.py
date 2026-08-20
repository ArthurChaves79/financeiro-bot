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


def _placemark_to_features(
    placemark: ET.Element,
    styles: dict[str, dict],
    style_maps: dict[str, str],
    estilo_ja_resolvido: dict | None = None,
) -> list[dict]:
    props = _extended_data(placemark)
    name = _text(placemark, f"{_ANY_NS}name")
    description = _text(placemark, f"{_ANY_NS}description")
    if name:
        props.setdefault("nome", name)
    if description:
        props.setdefault("descricao", description)

    estilo = estilo_ja_resolvido if estilo_ja_resolvido is not None else _resolve_style(placemark, styles, style_maps)
    props = {**estilo, **props}  # atributos do próprio Placemark sempre vencem, se colidirem

    geometries = _placemark_geometries(placemark)
    return [{"type": "Feature", "properties": dict(props), "geometry": g} for g in geometries]


def parse_kml_bytes(data: bytes) -> dict:
    """Converte o conteúdo de um arquivo .kml (bytes) para um dict GeoJSON
    (FeatureCollection), com todos os Placemarks juntos numa lista só
    (ignora a estrutura de pastas — use parse_kml_grouped para respeitar
    as pastas do KML como camadas separadas)."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise KmlParseError(f"KML inválido: {exc}") from exc

    styles, style_maps = _parse_styles(root)

    # Nota: Element.iter() só faz correspondência exata de tag (sem
    # suporte a wildcard de namespace) — por isso usamos findall() com
    # ".//", que passa pelo resolvedor de XPath do ElementTree.
    features: list[dict] = []
    for placemark in root.findall(f".//{_ANY_NS}Placemark"):
        features.extend(_placemark_to_features(placemark, styles, style_maps))
    return {"type": "FeatureCollection", "features": features}


def parse_kmz_bytes(data: bytes) -> dict:
    """Converte o conteúdo de um arquivo .kmz (bytes, é um .kml dentro de
    um .zip) para um dict GeoJSON."""
    return parse_kml_bytes(_extrair_kml_do_kmz(data))


# --------------------------------------------------------------------------
# Estilos (<Style>/<StyleMap>) — cores/espessuras que o próprio KML define
# --------------------------------------------------------------------------

def _parse_color_kml(value: str) -> tuple[str, float] | None:
    """KML usa a ordem aabbggrr (alpha, azul, verde, vermelho), 2 dígitos
    hex cada. Devolve (cor no formato #rrggbb, opacidade de 0 a 1)."""
    v = value.strip()
    if len(v) != 8:
        return None
    try:
        a = int(v[0:2], 16)
        b = int(v[2:4], 16)
        g = int(v[4:6], 16)
        r = int(v[6:8], 16)
    except ValueError:
        return None
    return f"#{r:02x}{g:02x}{b:02x}", round(a / 255, 3)


def _style_from_element(style_el: ET.Element) -> dict:
    props: dict = {}

    line = style_el.find(f"{_ANY_NS}LineStyle")
    if line is not None:
        color_el = line.find(f"{_ANY_NS}color")
        width_el = line.find(f"{_ANY_NS}width")
        if color_el is not None and color_el.text:
            parsed = _parse_color_kml(color_el.text)
            if parsed:
                props["_cor_linha"], props["_opacidade_linha"] = parsed
        if width_el is not None and width_el.text:
            try:
                props["_largura_linha"] = float(width_el.text)
            except ValueError:
                pass

    poly = style_el.find(f"{_ANY_NS}PolyStyle")
    if poly is not None:
        color_el = poly.find(f"{_ANY_NS}color")
        fill_el = poly.find(f"{_ANY_NS}fill")
        if color_el is not None and color_el.text:
            parsed = _parse_color_kml(color_el.text)
            if parsed:
                props["_cor_preenchimento"], props["_opacidade_preenchimento"] = parsed
        if fill_el is not None and fill_el.text is not None and fill_el.text.strip() == "0":
            props["_sem_preenchimento"] = True

    icon = style_el.find(f"{_ANY_NS}IconStyle")
    if icon is not None:
        color_el = icon.find(f"{_ANY_NS}color")
        if color_el is not None and color_el.text:
            parsed = _parse_color_kml(color_el.text)
            if parsed:
                props["_cor_ponto"] = parsed[0]

    return props


def _parse_styles(root: ET.Element) -> tuple[dict[str, dict], dict[str, str]]:
    """Lê todo <Style id="..."> do documento, e resolve <StyleMap>
    (usando sempre o par "normal", ignorando o de "highlight" no hover)."""
    styles: dict[str, dict] = {}
    for style_el in root.findall(f".//{_ANY_NS}Style"):
        style_id = style_el.get("id")
        if not style_id:
            continue
        props = _style_from_element(style_el)
        if props:
            styles[style_id] = props

    style_maps: dict[str, str] = {}
    for sm_el in root.findall(f".//{_ANY_NS}StyleMap"):
        sm_id = sm_el.get("id")
        if not sm_id:
            continue
        for pair in sm_el.findall(f"{_ANY_NS}Pair"):
            key_el = pair.find(f"{_ANY_NS}key")
            url_el = pair.find(f"{_ANY_NS}styleUrl")
            if key_el is not None and key_el.text == "normal" and url_el is not None and url_el.text:
                style_maps[sm_id] = url_el.text.strip().lstrip("#")

    return styles, style_maps


def _resolve_style(placemark: ET.Element, styles: dict[str, dict], style_maps: dict[str, str]) -> dict:
    style_url_el = placemark.find(f"{_ANY_NS}styleUrl")
    if style_url_el is not None and style_url_el.text:
        ref = style_url_el.text.strip().lstrip("#")
        ref = style_maps.get(ref, ref)  # StyleMap -> id do Style "normal"
        if ref in styles:
            return styles[ref]

    inline = placemark.find(f"{_ANY_NS}Style")
    if inline is not None:
        return _style_from_element(inline)

    return {}


# --------------------------------------------------------------------------
# Pastas (<Folder>) — cada uma vira uma camada separada, ligável à parte
# --------------------------------------------------------------------------

def _extrair_kml_do_kmz(data: bytes) -> bytes:
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            names = zf.namelist()
            kml_name = next((n for n in names if n.lower() == "doc.kml"), None)
            if kml_name is None:
                kml_name = next((n for n in names if n.lower().endswith(".kml")), None)
            if kml_name is None:
                raise KmlParseError("Nenhum arquivo .kml encontrado dentro do .kmz")
            return zf.read(kml_name)
    except zipfile.BadZipFile as exc:
        raise KmlParseError(f"KMZ inválido (não é um zip válido): {exc}") from exc


def _walk_folders(
    elem: ET.Element,
    path: tuple[str, ...],
    styles: dict[str, dict],
    style_maps: dict[str, str],
    groups: dict[tuple[str, ...], list[dict]],
) -> None:
    for child in elem:
        tag = _local(child.tag)
        if tag == "Folder":
            name = _text(child, f"{_ANY_NS}name") or "Sem nome"
            _walk_folders(child, path + (name,), styles, style_maps, groups)
        elif tag == "Document":
            # Document é um contêiner "transparente" — o nome do arquivo
            # já identifica a camada raiz, não precisa virar mais um nível.
            _walk_folders(child, path, styles, style_maps, groups)
        elif tag == "Placemark":
            style_props = _resolve_style(child, styles, style_maps)
            features = _placemark_to_features(child, styles={}, style_maps={}, estilo_ja_resolvido=style_props)
            groups.setdefault(path, []).extend(features)


def _parse_kml_grouped_from_root(root: ET.Element) -> list[tuple[tuple[str, ...], dict]]:
    styles, style_maps = _parse_styles(root)
    groups: dict[tuple[str, ...], list[dict]] = {}
    _walk_folders(root, (), styles, style_maps, groups)

    result = []
    for path, features in groups.items():
        if not features:
            continue
        result.append((path, {"type": "FeatureCollection", "features": features}))
    return result


def parse_kml_grouped(data: bytes) -> list[tuple[tuple[str, ...], dict]]:
    """Como parse_kml_bytes, mas respeita as <Folder> do KML (inclusive
    aninhadas): devolve uma lista de (caminho_da_pasta, geojson), onde
    caminho_da_pasta é uma tupla, ex: ("Zoneamento", "Residencial").
    Placemarks que não estão dentro de nenhuma pasta ficam sob o
    caminho vazio (). Se o KML não tem nenhuma <Folder>, devolve uma
    lista com 1 item só (caminho ()), equivalente a parse_kml_bytes."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise KmlParseError(f"KML inválido: {exc}") from exc
    return _parse_kml_grouped_from_root(root)


def parse_kmz_grouped(data: bytes) -> list[tuple[tuple[str, ...], dict]]:
    kml_bytes = _extrair_kml_do_kmz(data)
    try:
        root = ET.fromstring(kml_bytes)
    except ET.ParseError as exc:
        raise KmlParseError(f"KML inválido: {exc}") from exc
    return _parse_kml_grouped_from_root(root)
