#!/usr/bin/env python3
"""Genera favicons / app icons / logos header desde logo-source-dark.png"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "logo-source-dark.png"
OUT = ROOT


def trim_black(im: Image.Image, thresh: int = 18, pad: int = 24) -> Image.Image:
    im = im.convert("RGBA")
    gray = ImageOps.grayscale(im)
    # mask: non-near-black
    mask = gray.point(lambda p: 255 if p > thresh else 0)
    bbox = mask.getbbox()
    if not bbox:
        return im
    l, t, r, b = bbox
    l = max(0, l - pad)
    t = max(0, t - pad)
    r = min(im.width, r + pad)
    b = min(im.height, b + pad)
    return im.crop((l, t, r, b))


def to_transparent_light_fg(im: Image.Image) -> Image.Image:
    """Fondo negro → transparente; blanco/gris claro → blanco; rojo se conserva."""
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            # casi negro
            if r < 40 and g < 40 and b < 40:
                px[x, y] = (0, 0, 0, 0)
                continue
            # rojo / burdeos de las rayas
            if r > 90 and r > g * 1.35 and r > b * 1.35:
                # saturar un poco el rojo marca
                px[x, y] = (min(255, int(r * 1.15)), max(0, int(g * 0.35)), max(0, int(b * 0.35)), 255)
                continue
            # texto claro → blanco puro
            lum = (r + g + b) / 3
            if lum > 90:
                px[x, y] = (255, 255, 255, 255)
            else:
                # gris medio raro → semi
                px[x, y] = (r, g, b, a)
    return im


def to_dark_fg(im_rgba: Image.Image) -> Image.Image:
    """Versión para fondos claros: blanco → negro casi; rojo se mantiene."""
    im = im_rgba.copy()
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 10:
                continue
            if r > 90 and r > g * 1.35 and r > b * 1.35:
                px[x, y] = (180, 20, 35, a)  # rojo marca
                continue
            # blanco/gris → negro
            px[x, y] = (15, 23, 42, a)
    return im


def fit_square(im: Image.Image, size: int, bg=None) -> Image.Image:
    """Centra el logo en un cuadrado size×size."""
    im = im.convert("RGBA")
    # scale to fit with margin
    margin = int(size * 0.12)
    box = size - margin * 2
    ratio = min(box / im.width, box / im.height)
    nw, nh = max(1, int(im.width * ratio)), max(1, int(im.height * ratio))
    scaled = im.resize((nw, nh), Image.Resampling.LANCZOS)
    if bg is None:
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    else:
        canvas = Image.new("RGBA", (size, size), bg)
    canvas.paste(scaled, ((size - nw) // 2, (size - nh) // 2), scaled)
    return canvas


def fit_width(im: Image.Image, width: int) -> Image.Image:
    ratio = width / im.width
    h = max(1, int(im.height * ratio))
    return im.resize((width, h), Image.Resampling.LANCZOS)


def make_og(im_light_on_dark: Image.Image) -> Image.Image:
    w, h = 1200, 630
    canvas = Image.new("RGB", (w, h), (6, 8, 13))
    # logo centered
    logo = im_light_on_dark.convert("RGBA")
    target_w = 720
    ratio = target_w / logo.width
    logo = logo.resize((target_w, max(1, int(logo.height * ratio))), Image.Resampling.LANCZOS)
    # solid black plate already; paste with alpha
    x = (w - logo.width) // 2
    y = (h - logo.height) // 2 - 20
    canvas.paste(logo, (x, y), logo)
    draw = ImageDraw.Draw(canvas)
    # tagline
    draw.rectangle([0, h - 90, w, h], fill=(10, 14, 22))
    return canvas


def main():
    raw = Image.open(SRC)
    trimmed = trim_black(raw)
    light_fg = to_transparent_light_fg(trimmed)  # white+red on transparent
    dark_fg = to_dark_fg(light_fg)  # black+red on transparent

    # Master exports
    light_fg.save(OUT / "logo-white.png")
    dark_fg.save(OUT / "logo-dark.png")
    fit_width(light_fg, 640).save(OUT / "logo-white-640.png")
    fit_width(dark_fg, 640).save(OUT / "logo-dark-640.png")
    fit_width(light_fg, 320).save(OUT / "logo-white-320.png")
    fit_width(dark_fg, 320).save(OUT / "logo-dark-320.png")

    # App / favicon squares — fondo negro con logo blanco (mejor en iOS)
    icon_512 = fit_square(light_fg, 512, bg=(6, 8, 13, 255))
    icon_192 = fit_square(light_fg, 192, bg=(6, 8, 13, 255))
    icon_180 = fit_square(light_fg, 180, bg=(6, 8, 13, 255))
    icon_32 = fit_square(light_fg, 32, bg=(6, 8, 13, 255))
    icon_16 = fit_square(light_fg, 16, bg=(6, 8, 13, 255))

    icon_512.convert("RGB").save(OUT / "icon-512.png")
    icon_192.convert("RGB").save(OUT / "icon-192.png")
    icon_180.convert("RGB").save(OUT / "apple-touch-icon.png")
    icon_32.convert("RGB").save(OUT / "favicon-32x32.png")
    icon_16.convert("RGB").save(OUT / "favicon-16x16.png")

    # ICO multi-size
    ico_sizes = [(16, 16), (32, 32), (48, 48)]
    icos = [fit_square(light_fg, s, bg=(6, 8, 13, 255)).convert("RGBA") for s, _ in ico_sizes]
    icos[0].save(
        OUT / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=icos[1:],
    )

    # Transparent favicon-friendly mark (for SVG-less browsers / light tabs)
    fit_square(dark_fg, 64, bg=None).save(OUT / "favicon-64-transparent.png")

    # OG
    # Reconstruct white on black plate for OG
    plate = Image.new("RGBA", trimmed.size, (6, 8, 13, 255))
    plate = Image.alpha_composite(plate, light_fg)
    make_og(plate).save(OUT / "og-image.png", quality=92)

    # Simple SVG favicon referencing concept (inline mark as text fallback style)
    # Real SVG mark: embed PNG as base64 is heavy; write a minimal geometric SVG wordmark hint
    (OUT / "site.webmanifest").write_text(
        """{
  "name": "IFLXI",
  "short_name": "IFLXI",
  "description": "Info Football Lab XI — datos de fútbol",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#06080d",
  "theme_color": "#f3f5f9",
  "icons": [
    { "src": "/brand/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/brand/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
""",
        encoding="utf-8",
    )

    print("OK ->", OUT)
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.suffix.lower() in {".png", ".ico", ".webmanifest"}:
            print(f"  {p.name:28} {p.stat().st_size:8} bytes")


if __name__ == "__main__":
    main()
