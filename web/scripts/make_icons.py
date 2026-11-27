"""Рисует значки PWA в цвет каталога. Запуск из каталога web: python scripts/make_icons.py"""

import struct
import zlib
from pathlib import Path

BG = (0x12, 0x10, 0x0E)
ACCENT = (0xE2, 0xA1, 0x5A)
OUT = Path(__file__).resolve().parents[1] / "public"


def in_round_rect(nx, ny, left, top, right, bottom, radius):
    if nx < left or nx > right or ny < top or ny > bottom:
        return False
    cx = left + radius if nx < left + radius else right - radius if nx > right - radius else nx
    cy = top + radius if ny < top + radius else bottom - radius if ny > bottom - radius else ny
    if cx == nx or cy == ny:
        return True
    dx, dy = nx - cx, ny - cy
    return dx * dx + dy * dy <= radius * radius


def covered(nx, ny, maskable):
    if maskable:
        nx = 0.5 + (nx - 0.5) / 0.86
        ny = 0.5 + (ny - 0.5) / 0.86
    if not in_round_rect(nx, ny, 0.14, 0.30, 0.86, 0.70, 0.045):
        return False
    holes = []
    for px in (0.26, 0.42, 0.58, 0.74):
        holes.append((px, 0.355))
        holes.append((px, 0.645))
    for px, py in holes:
        dx, dy = nx - px, ny - py
        if dx * dx + dy * dy <= 0.028 * 0.028:
            return False
    if 0.40 <= ny <= 0.60 and (abs(nx - 0.38) <= 0.012 or abs(nx - 0.62) <= 0.012):
        return False
    return True


def pixel(x, y, size, maskable):
    hits = 0
    for ox in (0.25, 0.75):
        for oy in (0.25, 0.75):
            if covered((x + ox) / size, (y + oy) / size, maskable):
                hits += 1
    if hits == 0:
        return BG
    if hits == 4:
        return ACCENT
    mix = hits / 4
    return tuple(round(BG[i] + (ACCENT[i] - BG[i]) * mix) for i in range(3))


def write_png(path, size, maskable):
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            raw.extend(pixel(x, y, size, maskable))
            raw.append(255)
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    write_png(OUT / "pwa-192x192.png", 192, False)
    write_png(OUT / "pwa-512x512.png", 512, False)
    write_png(OUT / "pwa-maskable-512x512.png", 512, True)
    write_png(OUT / "apple-touch-icon.png", 180, False)


if __name__ == "__main__":
    main()
