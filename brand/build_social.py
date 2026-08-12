#!/usr/bin/env python3
"""Genera pack de logos listos para redes sociales + ZIP + página de descarga."""

from __future__ import annotations

import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "logo-source-dark.png"
OUT = ROOT / "redes"
BG = (6, 8, 13, 255)
RED = (180, 20, 35, 255)


def trim_black(im: Image.Image, thresh: int = 18, pad: int = 24) -> Image.Image:
    im = im.convert("RGBA")
    gray = ImageOps.grayscale(im)
    mask = gray.point(lambda p: 255 if p > thresh else 0)
    bbox = mask.getbbox()
    if not bbox:
        return im
    l, t, r, b = bbox
    return im.crop(
        (max(0, l - pad), max(0, t - pad), min(im.width, r + pad), min(im.height, b + pad))
    )


def to_transparent_light_fg(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r < 40 and g < 40 and b < 40:
                px[x, y] = (0, 0, 0, 0)
                continue
            if r > 90 and r > g * 1.35 and r > b * 1.35:
                px[x, y] = (min(255, int(r * 1.15)), max(0, int(g * 0.35)), max(0, int(b * 0.35)), 255)
                continue
            if (r + g + b) / 3 > 90:
                px[x, y] = (255, 255, 255, 255)
    return im


def to_dark_fg(im_rgba: Image.Image) -> Image.Image:
    im = im_rgba.copy()
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 10:
                continue
            if r > 90 and r > g * 1.35 and r > b * 1.35:
                px[x, y] = RED
                continue
            px[x, y] = (15, 23, 42, a)
    return im


def fit_centered(im: Image.Image, size: tuple[int, int], bg, margin_ratio: float = 0.18) -> Image.Image:
    canvas = Image.new("RGBA", size, bg if bg is not None else (0, 0, 0, 0))
    box_w = int(size[0] * (1 - margin_ratio * 2))
    box_h = int(size[1] * (1 - margin_ratio * 2))
    ratio = min(box_w / im.width, box_h / im.height)
    nw, nh = max(1, int(im.width * ratio)), max(1, int(im.height * ratio))
    scaled = im.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (size[0] - nw) // 2
    y = (size[1] - nh) // 2
    canvas.paste(scaled, (x, y), scaled)
    return canvas


def save_rgb(im: Image.Image, path: Path) -> None:
    im.convert("RGB").save(path, optimize=True)


def save_rgba(im: Image.Image, path: Path) -> None:
    im.save(path, optimize=True)


def make_banner(logo: Image.Image, size: tuple[int, int], tagline: str | None = None) -> Image.Image:
    w, h = size
    canvas = Image.new("RGBA", size, BG)
    # subtle red accent line
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, h - 8, w, h], fill=RED[:3])

    target_w = int(w * 0.42)
    ratio = target_w / logo.width
    logo_r = logo.resize((target_w, max(1, int(logo.height * ratio))), Image.Resampling.LANCZOS)
    x = (w - logo_r.width) // 2
    y = (h - logo_r.height) // 2 - (18 if tagline else 0)
    canvas.paste(logo_r, (x, y), logo_r)
    return canvas


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = Image.open(SRC)
    trimmed = trim_black(raw)
    white = to_transparent_light_fg(trimmed)
    dark = to_dark_fg(white)

    files: list[Path] = []

    def track(path: Path) -> Path:
        files.append(path)
        return path

    # --- Transparent masters (para editar / Canva / Photoshop) ---
    save_rgba(white, track(OUT / "01-logo-blanco-transparente.png"))
    save_rgba(dark, track(OUT / "02-logo-oscuro-transparente.png"))
    save_rgba(
        white.resize((1600, max(1, int(white.height * 1600 / white.width))), Image.Resampling.LANCZOS),
        track(OUT / "03-logo-blanco-transparente-1600.png"),
    )
    save_rgba(
        dark.resize((1600, max(1, int(dark.height * 1600 / dark.width))), Image.Resampling.LANCZOS),
        track(OUT / "04-logo-oscuro-transparente-1600.png"),
    )

    # --- Avatar / foto de perfil (recomendado para todas las redes) ---
    for size in (1080, 800, 400):
        save_rgb(
            fit_centered(white, (size, size), BG, margin_ratio=0.16),
            track(OUT / f"avatar-negro-{size}.png"),
        )
        save_rgb(
            fit_centered(dark, (size, size), (243, 245, 249, 255), margin_ratio=0.16),
            track(OUT / f"avatar-claro-{size}.png"),
        )

    # Alias claros por red
    save_rgb(fit_centered(white, (1080, 1080), BG, 0.16), track(OUT / "instagram-perfil-1080.png"))
    save_rgb(fit_centered(white, (1080, 1080), BG, 0.16), track(OUT / "tiktok-perfil-1080.png"))
    save_rgb(fit_centered(white, (1080, 1080), BG, 0.16), track(OUT / "threads-perfil-1080.png"))
    save_rgb(fit_centered(white, (400, 400), BG, 0.16), track(OUT / "x-twitter-perfil-400.png"))

    # --- Banners / portadas ---
    save_rgb(make_banner(white, (1500, 500)), track(OUT / "x-twitter-portada-1500x500.png"))
    save_rgb(make_banner(white, (1584, 396)), track(OUT / "linkedin-portada-1584x396.png"))
    save_rgb(make_banner(white, (820, 312)), track(OUT / "facebook-portada-820x312.png"))
    save_rgb(make_banner(white, (2560, 1440)), track(OUT / "youtube-banner-2560x1440.png"))
    save_rgb(make_banner(white, (1080, 1920)), track(OUT / "instagram-story-1080x1920.png"))
    save_rgb(make_banner(white, (1080, 1080)), track(OUT / "instagram-post-1080.png"))

    # --- Cuadrado marca con fondo negro / claro (alta resolución) ---
    save_rgb(fit_centered(white, (2048, 2048), BG, 0.14), track(OUT / "marca-cuadrado-negro-2048.png"))
    save_rgb(
        fit_centered(dark, (2048, 2048), (255, 255, 255, 255), 0.14),
        track(OUT / "marca-cuadrado-blanco-2048.png"),
    )

    # README
    readme = OUT / "LEE-PRIMERO.txt"
    readme.write_text(
        """IFLXI — Pack de logos para redes sociales
========================================

RECOMENDADO (todas las redes):
  avatar-negro-1080.png     → foto de perfil Instagram / TikTok / Threads / X
  avatar-claro-1080.png     → si la red o el fondo es claro

POR RED:
  instagram-perfil-1080.png
  tiktok-perfil-1080.png
  threads-perfil-1080.png
  x-twitter-perfil-400.png
  x-twitter-portada-1500x500.png

TRANSPARENTES (para Canva / edición):
  01-logo-blanco-transparente.png
  02-logo-oscuro-transparente.png
  03-logo-blanco-transparente-1600.png
  04-logo-oscuro-transparente-1600.png

PORTADAS:
  x-twitter-portada-1500x500.png
  linkedin-portada-1584x396.png
  facebook-portada-820x312.png
  youtube-banner-2560x1440.png
  instagram-story-1080x1920.png
  instagram-post-1080.png

Marca @iflxi_official / @IFLXI_Official
""",
        encoding="utf-8",
    )
    files.append(readme)

    # ZIP
    zip_path = ROOT / "IFLXI-logos-redes.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, arcname=f"IFLXI-logos-redes/{p.name}")
    print("ZIP ->", zip_path)
    print("DIR ->", OUT)
    for p in sorted(OUT.iterdir()):
        if p.is_file():
            print(f"  {p.name:42} {p.stat().st_size:8} bytes")


if __name__ == "__main__":
    main()
