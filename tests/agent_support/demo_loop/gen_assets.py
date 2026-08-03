"""Generate chart.png and report.pdf in the current working directory.

Called by the demo loop's assets agent under ``--mock bash`` (the prompt is
executed as a shell command, so this script runs with cwd = run working dir).
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path


def make_png(path: Path) -> None:
    """1x1 red PNG (68 bytes, well-formed)."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    path.write_bytes(
        sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    )


def make_pdf(path: Path) -> None:
    """Minimal one-page PDF (well-formed, opens in viewers)."""
    content = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        b"xref\n0 4\n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n0\n%%EOF"
    )
    path.write_bytes(content)


def main() -> int:
    make_png(Path("chart.png"))
    make_pdf(Path("report.pdf"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
