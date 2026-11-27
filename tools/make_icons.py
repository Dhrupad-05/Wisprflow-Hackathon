"""Generate the two PWA icons with the standard library only."""

from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "apps/web/icons"
BRAND = (30, 58, 138)
ACCENT = (15, 118, 110)
PAPER = (255, 255, 255)


def pixel(x: int, y: int, size: int) -> tuple[int, int, int]:
    center = size / 2
    radius = size * 0.34
    dx, dy = x - center, y - center
    if (dx * dx + dy * dy) ** 0.5 <= radius:
        return PAPER
    if (dx * dx + dy * dy) ** 0.5 <= radius * 0.42:
        return ACCENT
    return BRAND


def png(size: int) -> bytes:
    rows = bytearray()
    for y in range(size):
        rows.append(0)  # filter byte
        for x in range(size):
            rows.extend(pixel(x, y, size))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        (OUT / f"icon-{size}.png").write_bytes(png(size))
        print(f"wrote apps/web/icons/icon-{size}.png")


if __name__ == "__main__":
    main()
