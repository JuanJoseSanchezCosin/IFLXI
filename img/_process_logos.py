"""Descarga escudos/ligas conservando transparencia y el blanco del diseño.

API-Sports ya entrega PNG con alpha. Solo se normaliza a 150x150 sobre
lienzo transparente (nunca blanco).
"""
from pathlib import Path
import urllib.request
from PIL import Image

CLUBS = {
    "real-madrid": 541,
    "barcelona": 529,
    "atletico": 530,
    "man-city": 50,
    "arsenal": 42,
    "liverpool": 40,
    "chelsea": 49,
    "man-united": 33,
    "bayern": 157,
    "psg": 85,
    "inter": 505,
    "milan": 489,
    "dortmund": 165,
    "sevilla": 536,
    "newcastle": 34,
    "tottenham": 47,
    "leverkusen": 168,
    "atalanta": 499,
    "girona": 547,
    "monaco": 91,
    "palmeiras": 121,
    "rennes": 94,
    "river-plate": 435,
    "marseille": 81,
}

LEAGUES = {
    "laliga": 140,
    "premier": 39,
    "seriea": 135,
    "bundesliga": 78,
    "ligue1": 61,
}

ROOT = Path(__file__).resolve().parent
CLUB_DIR = ROOT / "clubs"
LEAGUE_DIR = ROOT / "leagues"
CLUB_DIR.mkdir(parents=True, exist_ok=True)
LEAGUE_DIR.mkdir(parents=True, exist_ok=True)

opener = urllib.request.build_opener()
opener.addheaders = [("User-Agent", "IFLXI/1.0")]
urllib.request.install_opener(opener)


def normalize(src: Image.Image, side: int = 150) -> Image.Image:
    im = src.convert("RGBA")
    # recorta solo transparencia exterior (no toca blanco del escudo)
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    w, h = im.size
    scale = side / max(w, h, 1)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - nw) // 2, (side - nh) // 2), im)
    return canvas


def fetch(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=30) as r:
        dest.write_bytes(r.read())
    normalize(Image.open(dest)).save(dest, "PNG", optimize=True)


for slug, afid in CLUBS.items():
    dest = CLUB_DIR / f"{slug}.png"
    try:
        fetch(f"https://media.api-sports.io/football/teams/{afid}.png", dest)
        print("OK", slug)
    except Exception as e:
        print("FAIL", slug, e)

for slug, lid in LEAGUES.items():
    dest = LEAGUE_DIR / f"{slug}.png"
    try:
        fetch(f"https://media.api-sports.io/football/leagues/{lid}.png", dest)
        print("league", slug)
    except Exception as e:
        print("FAIL league", slug, e)
