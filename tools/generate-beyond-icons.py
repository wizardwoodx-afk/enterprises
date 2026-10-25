#!/usr/bin/env python3
"""Generate the Beyond app icon set.

One geometric source of truth — a rounded squircle with a double chevron
pointing forward — rendered deterministically at every size and container the
build needs. No external art, no fonts: the mark is pure geometry, so it stays
crisp from 16 px favicons to 1024 px mac icons and is reproducible.

Requires: pillow  (python3 -m venv .venv && .venv/bin/pip install pillow)

Usage:
    .venv/bin/python tools/generate-beyond-icons.py            # write
    .venv/bin/python tools/generate-beyond-icons.py --check    # verify presence
"""
from __future__ import annotations

import argparse
import io
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "apps/desktop"

# Brand palette. Indigo -> violet gradient; the mark itself stays white so it
# holds up on both light and dark platform chrome.
LIGHT_TOP = (99, 91, 255)
LIGHT_BOTTOM = (43, 27, 107)
DARK_TOP = (124, 116, 255)
DARK_BOTTOM = (24, 16, 64)
TILE_LIGHT = (255, 255, 255)
TILE_DARK = (13, 17, 23)

SUPERSAMPLE = 4


def _gradient(size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (1, size))
    px = img.load()
    for y in range(size):
        t = y / max(size - 1, 1)
        px[0, y] = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return img.resize((size, size), Image.BILINEAR)


def _squircle_mask(size: int, radius_ratio: float = 0.232) -> Image.Image:
    """Rounded-rectangle silhouette, supersampled then downscaled for clean edges."""
    big = size * SUPERSAMPLE
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, big - 1, big - 1), radius=int(big * radius_ratio), fill=255
    )
    return mask.resize((size, size), Image.LANCZOS)


def _chevron(draw: ImageDraw.ImageDraw, cx: float, cy: float, w: float, h: float, thickness: int, fill):
    """A forward chevron '>' centred on (cx, cy)."""
    half_w, half_h = w / 2, h / 2
    pts = [(cx - half_w, cy - half_h), (cx + half_w, cy), (cx - half_w, cy + half_h)]
    draw.line(pts, fill=fill, width=thickness, joint="curve")
    # Round the two open ends so the stroke terminates cleanly.
    r = thickness / 2
    for x, y in (pts[0], pts[2]):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def _mark_layers(size: int, fill: tuple[int, int, int, int]):
    """Draw the two-chevron mark at `size` on a transparent canvas."""
    big = size * SUPERSAMPLE
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    thickness = int(big * 0.082)
    # Leading (larger, brighter) chevron + trailing echo -> "onward".
    _chevron(d, big * 0.585, big * 0.50, big * 0.26, big * 0.40, thickness, fill)
    trailing = (fill[0], fill[1], fill[2], int(fill[3] * 0.5))
    _chevron(d, big * 0.375, big * 0.50, big * 0.20, big * 0.31, thickness, trailing)
    return layer.resize((size, size), Image.LANCZOS)


def app_icon(size: int, dark: bool = False, mono: bool = False) -> Image.Image:
    """Full app icon: squircle tile + mark."""
    if mono:
        # Single-ink variant for macOS Clear/Tinted layers.
        return _mark_layers(size, (255, 255, 255, 255))
    tile = _gradient(size, DARK_TOP if dark else LIGHT_TOP, DARK_BOTTOM if dark else LIGHT_BOTTOM)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(tile, (0, 0), _squircle_mask(size))
    canvas.alpha_composite(_mark_layers(size, (255, 255, 255, 255)))
    return canvas


def flat_mark(size: int, ink: tuple[int, int, int] = (23, 23, 28), tile: tuple[int, int, int] | None = None):
    """Mark-only PNG used in-app as the brand badge."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if tile is not None:
        canvas.paste(Image.new("RGB", (size, size), tile), (0, 0), _squircle_mask(size))
    canvas.alpha_composite(_mark_layers(size, (*ink, 255)))
    return canvas


# ---------------------------------------------------------------- containers
def write_png(path: Path, image: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")


def write_icns(path: Path, image: Image.Image) -> None:
    """ICNS container with PNG payloads (the format macOS 10.7+ accepts)."""
    specs = [
        (b"icp4", 16), (b"icp5", 32), (b"icp6", 64),
        (b"ic07", 128), (b"ic08", 256), (b"ic09", 512),
        (b"ic10", 1024), (b"ic11", 32), (b"ic12", 64),
        (b"ic13", 256), (b"ic14", 512),
    ]
    chunks = b""
    for code, size in specs:
        buf = io.BytesIO()
        image.resize((size, size), Image.LANCZOS).save(buf, "PNG")
        payload = buf.getvalue()
        chunks += code + struct.pack(">I", len(payload) + 8) + payload
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"icns" + struct.pack(">I", len(chunks) + 8) + chunks)


def write_ico(path: Path, image: Image.Image) -> None:
    """ICO container with PNG payloads (Vista+)."""
    sizes = [16, 24, 32, 48, 64, 128, 256]
    blobs = []
    for s in sizes:
        buf = io.BytesIO()
        image.resize((s, s), Image.LANCZOS).save(buf, "PNG")
        blobs.append((s, buf.getvalue()))
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries = b""
    data = b""
    for s, blob in blobs:
        entries += struct.pack("<BBBBHHII", s if s < 256 else 0, s if s < 256 else 0, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
        data += blob
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entries + data)


APPX_SIZES = {
    "Square44x44Logo": 44,
    "Square150x150Logo": 150,
    "Square310x310Logo": 310,
    "Square71x71Logo": 71,
    "Wide310x150Logo": None,
    "StoreLogo": 50,
}


def appx_pixels(path: Path, base: int | None) -> int:
    """Keep whatever pixel size the file already had, so manifests stay valid."""
    try:
        with Image.open(path) as img:
            return img.size[0] if img.size[0] else (base or 44)
    except Exception:
        return base or 44


def main() -> int:
    check = "--check" in sys.argv[1:]
    assets = DESKTOP / "assets"
    public = DESKTOP / "public"
    packaging = DESKTOP / "packaging"
    icon_dir = assets / "icon.icon"

    targets: list[Path] = []

    def emit(path: Path, image: Image.Image) -> None:
        targets.append(path)
        if not check:
            write_png(path, image)

    if check:
        expected = [
            assets / "icon.png", assets / "icon-dark.png", assets / "icon-mac.png",
            assets / "icon.icns", assets / "icon-dark.icns",
            assets / "icon.ico", assets / "icon-dark.ico",
            packaging / "dmg-volume.icns",
            public / "apple-touch-icon.png",
            public / "beyond-mark.png", public / "beyond-mark-dark.png",
            public / "beyond.png", public / "beyond-sprite.png",
        ]
        missing = [p for p in expected if not p.exists()]
        for p in expected:
            print(("  ok   " if p.exists() else "  MISS ") + str(p.relative_to(ROOT)))
        return 1 if missing else 0

    # --- app icons --------------------------------------------------------
    master = app_icon(1024)
    master_dark = app_icon(1024, dark=True)
    emit(assets / "icon.png", master)
    emit(assets / "icon-dark.png", master_dark)
    emit(assets / "icon-mac.png", master)
    write_icns(assets / "icon.icns", master)
    write_icns(assets / "icon-dark.icns", master_dark)
    write_ico(assets / "icon.ico", master)
    write_ico(assets / "icon-dark.ico", master_dark)
    write_icns(packaging / "dmg-volume.icns", master)
    targets += [assets / "icon.icns", assets / "icon-dark.icns",
                assets / "icon.ico", assets / "icon-dark.ico", packaging / "dmg-volume.icns"]

    # --- macOS 26 Icon Composer package -----------------------------------
    emit(icon_dir / "Assets" / "art-light.png", _mark_layers(1024, (255, 255, 255, 255)))
    emit(icon_dir / "Assets" / "art-dark.png", _mark_layers(1024, (255, 255, 255, 255)))
    emit(icon_dir / "Assets" / "mono.png", _mark_layers(1024, (255, 255, 255, 255)))

    # --- Windows appx tiles ----------------------------------------------
    for path in sorted((assets / "appx").glob("*.png")):
        px = appx_pixels(path, APPX_SIZES.get(path.name.split(".")[0]))
        if "Wide" in path.name:
            wide = Image.new("RGBA", (px, max(int(px * 150 / 310), 1)), (0, 0, 0, 0))
            tile = app_icon(px).resize((wide.width, wide.height), Image.LANCZOS)
            wide.alpha_composite(tile)
            emit(path, wide)
        else:
            emit(path, app_icon(px))

    # --- web / in-app -----------------------------------------------------
    emit(public / "apple-touch-icon.png", app_icon(180))
    emit(public / "beyond-mark.png", flat_mark(256, ink=(23, 23, 28), tile=TILE_LIGHT))
    emit(public / "beyond-mark-dark.png", flat_mark(256, ink=(236, 236, 245), tile=TILE_DARK))
    emit(public / "beyond.png", app_icon(512))
    emit(public / "beyond-sprite.png", app_icon(256))
    frames = public / "beyond-frames"
    if frames.is_dir():
        for f in sorted(frames.glob("*.png")):
            emit(f, app_icon(128))

    print(f"wrote {len(targets)} icon files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
