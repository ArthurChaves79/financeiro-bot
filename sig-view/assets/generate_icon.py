#!/usr/bin/env python3
"""Gera o ícone do SIG View (icon.ico para o executável, icon.png para o
favicon do navegador) — sem depender de nenhuma biblioteca externa
(Pillow etc.), só a biblioteca padrão do Python (zlib, struct).

Desenho: um marcador de localização (pin) azul sobre um quadrado
arredondado escuro, no mesmo estilo visual do app (cores de style.css).
Roda uma vez; os arquivos gerados são versionados (não precisam ser
regenerados a cada build).

Uso: python3 assets/generate_icon.py
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent

BG = (16, 20, 24)  # --bg
PANEL = (23, 28, 34)  # --panel-bg
ACCENT = (63, 169, 245)  # --accent
WHITE = (255, 255, 255)


# --------------------------------------------------------------------------
# Desenho vetorial simples (avaliado por pixel, com supersampling p/ anti-aliasing)
# --------------------------------------------------------------------------

def _rounded_rect_mask(x: float, y: float, size: float, radius: float) -> bool:
    half = size / 2
    dx = abs(x) - (half - radius)
    dy = abs(y) - (half - radius)
    if dx <= 0 or dy <= 0:
        return abs(x) <= half and abs(y) <= half
    return dx * dx + dy * dy <= radius * radius


def _pin_mask(x: float, y: float, scale: float) -> tuple[bool, bool]:
    """Retorna (dentro_do_pin, dentro_do_furo_branco), em coordenadas
    normalizadas onde a figura toda ocupa aproximadamente [-1, 1]."""
    px, py = x / scale, y / scale
    # A "cabeça" do pin é um círculo, a "cauda" é um triângulo apontando
    # para baixo, unidos para formar o formato clássico de marcador.
    head_cy = -0.15
    head_r = 0.62

    dist_head = math.hypot(px, py - head_cy)
    in_head = dist_head <= head_r

    # Cauda: triângulo entre o centro do círculo e a ponta inferior.
    tip_y = 1.05
    tail_half_width_at_top = head_r * 0.62
    in_tail = False
    if py > head_cy:
        t = (py - head_cy) / (tip_y - head_cy)
        if 0 <= t <= 1:
            half_w = tail_half_width_at_top * (1 - t)
            in_tail = abs(px) <= half_w

    in_pin = in_head or in_tail

    hole_r = head_r * 0.42
    in_hole = math.hypot(px, py - head_cy) <= hole_r

    return in_pin, in_hole


def _pixel_color(nx: float, ny: float, canvas: float) -> tuple[int, int, int, int]:
    """nx, ny em pixels relativos ao centro do canvas (canvas = tamanho em px)."""
    half = canvas / 2

    if not _rounded_rect_mask(nx, ny, canvas, canvas * 0.22):
        return (0, 0, 0, 0)  # fora do fundo arredondado: transparente

    bg = PANEL

    pin_scale = half * 0.72
    in_pin, in_hole = _pin_mask(nx, ny, pin_scale)

    if in_pin and not in_hole:
        return (*ACCENT, 255)
    if in_hole:
        return (*WHITE, 255)
    return (*bg, 255)


def render(size: int, supersample: int = 4) -> list[list[tuple[int, int, int, int]]]:
    big = size * supersample
    pixels_big = [[(0, 0, 0, 0)] * big for _ in range(big)]
    for j in range(big):
        for i in range(big):
            nx = (i + 0.5) - big / 2
            ny = (j + 0.5) - big / 2
            pixels_big[j][i] = _pixel_color(nx, ny, big)

    # downsample (media do bloco supersample x supersample) para anti-aliasing
    pixels = [[(0, 0, 0, 0)] * size for _ in range(size)]
    for j in range(size):
        for i in range(size):
            r = g = b = a = 0
            for dj in range(supersample):
                for di in range(supersample):
                    pr, pg, pb, pa = pixels_big[j * supersample + dj][i * supersample + di]
                    r += pr
                    g += pg
                    b += pb
                    a += pa
            n = supersample * supersample
            pixels[j][i] = (r // n, g // n, b // n, a // n)
    return pixels


# --------------------------------------------------------------------------
# Codificador PNG mínimo (RGBA 8 bits, sem filtro, comprimido com zlib)
# --------------------------------------------------------------------------

def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


def encode_png(pixels: list[list[tuple[int, int, int, int]]]) -> bytes:
    height = len(pixels)
    width = len(pixels[0])

    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filtro "None" por linha
        for r, g, b, a in row:
            raw += bytes((r, g, b, a))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 9)

    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", idat)
        + _png_chunk(b"IEND", b"")
    )


# --------------------------------------------------------------------------
# Empacotador ICO (entradas em PNG, suportado desde o Windows Vista)
# --------------------------------------------------------------------------

def encode_ico(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = b""
    data = b""
    offset = 6 + 16 * len(images)
    for size, png_bytes in images:
        dim = size if size < 256 else 0
        entries += struct.pack(
            "<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png_bytes), offset
        )
        data += png_bytes
        offset += len(png_bytes)
    return header + entries + data


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    ico_sizes = [16, 32, 48, 64, 128, 256]
    images = []
    for size in ico_sizes:
        pixels = render(size)
        images.append((size, encode_png(pixels)))

    ico_path = ASSETS_DIR / "icon.ico"
    ico_path.write_bytes(encode_ico(images))
    print(f"Gerado {ico_path} ({len(ico_sizes)} tamanhos: {ico_sizes})")

    # favicon do navegador (PNG único, 64x64 é um bom equilíbrio de nitidez/tamanho)
    favicon_png = encode_png(render(64))
    favicon_path = ASSETS_DIR / "icon.png"
    favicon_path.write_bytes(favicon_png)
    print(f"Gerado {favicon_path}")


if __name__ == "__main__":
    main()
