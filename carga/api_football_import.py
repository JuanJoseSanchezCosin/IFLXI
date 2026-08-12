#!/usr/bin/env python3
"""
IFLXI — Importador API-Football → PostgreSQL (liga piloto)

Cuota Free: 100 requests/día. Este script es austero.

Uso:
  $env:API_FOOTBALL_KEY = "..."
  $env:PGPASSWORD = "..."
  $env:PGDATABASE = "iflxi"

  py api_football_import.py --league laliga --season 2024 --dry-run
  py api_football_import.py --league laliga --season 2024 --apply
  py api_football_import.py --league laliga --season 2026 --apply --with-players
  py api_football_import.py --league laliga --season 2026 --apply --with-players --players-mode squads

Si /players (stats) viene vacío (temporada nueva), --players-mode auto usa /players/squads.
Por defecto (sin flags extra): solo competición + temporada + equipos + inscripciones.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import date
from pathlib import Path

import urllib.error
import urllib.parse
import urllib.request

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print('Instala: py -m pip install "psycopg[binary]"')
    sys.exit(1)

BASE = "https://v3.football.api-sports.io"
ROOT = Path(__file__).resolve().parent
MAP_PATH = ROOT / ".api_football_map.json"
EXCEL_MAP_PATH = ROOT / ".import_map.json"

# IDs oficiales API-Football (v3)
LEAGUES = {
    "laliga": {"api_id": 140, "code": "LALIGA", "name": "LaLiga", "country": "Spain", "iso2": "ES"},
    "premier": {"api_id": 39, "code": "PREMIER_LEAGUE", "name": "Premier League", "country": "England", "iso2": "GB"},
    "seriea": {"api_id": 135, "code": "SERIE_A", "name": "Serie A", "country": "Italy", "iso2": "IT"},
    "bundesliga": {"api_id": 78, "code": "BUNDESLIGA", "name": "Bundesliga", "country": "Germany", "iso2": "DE"},
    "ligue1": {"api_id": 61, "code": "LIGUE_1", "name": "Ligue 1", "country": "France", "iso2": "FR"},
    # Lote nocturno / expansión (season 2025 con events=true)
    "championship": {"api_id": 40, "code": "CHAMPIONSHIP", "name": "Championship", "country": "England", "iso2": "GB"},
    "segunda": {"api_id": 141, "code": "SEGUNDA", "name": "Segunda División", "country": "Spain", "iso2": "ES"},
    "serieb": {"api_id": 136, "code": "SERIE_B", "name": "Serie B", "country": "Italy", "iso2": "IT"},
    "bundesliga2": {"api_id": 79, "code": "BUNDESLIGA_2", "name": "2. Bundesliga", "country": "Germany", "iso2": "DE"},
    "ligue2": {"api_id": 62, "code": "LIGUE_2", "name": "Ligue 2", "country": "France", "iso2": "FR"},
    "eredivisie": {"api_id": 88, "code": "EREDIVISIE", "name": "Eredivisie", "country": "Netherlands", "iso2": "NL"},
    "ligaportugal": {"api_id": 94, "code": "LIGA_PORTUGAL", "name": "Primeira Liga", "country": "Portugal", "iso2": "PT"},
    "proleague": {"api_id": 144, "code": "PRO_LEAGUE", "name": "Jupiler Pro League", "country": "Belgium", "iso2": "BE"},
    "superlig": {"api_id": 203, "code": "SUPER_LIG", "name": "Süper Lig", "country": "Turkey", "iso2": "TR"},
    "premership": {"api_id": 179, "code": "PREMIERSHIP", "name": "Premiership", "country": "Scotland", "iso2": "GB"},
    "seriea_br": {"api_id": 71, "code": "SERIE_A_BR", "name": "Serie A Brazil", "country": "Brazil", "iso2": "BR"},
    "liga_ar": {"api_id": 128, "code": "LIGA_AR", "name": "Liga Profesional Argentina", "country": "Argentina", "iso2": "AR"},
    "mls": {"api_id": 253, "code": "MLS", "name": "Major League Soccer", "country": "USA", "iso2": "US"},
    "liga_mx": {"api_id": 262, "code": "LIGA_MX", "name": "Liga MX", "country": "Mexico", "iso2": "MX"},
    "j1": {"api_id": 98, "code": "J1", "name": "J1 League", "country": "Japan", "iso2": "JP"},
    "saudi_pro": {"api_id": 307, "code": "SAUDI_PRO", "name": "Saudi Pro League", "country": "Saudi-Arabia", "iso2": "SA"},
}

COUNTRY_ISO = {
    "Spain": "ES",
    "England": "GB",
    "Italy": "IT",
    "Germany": "DE",
    "France": "FR",
    "Portugal": "PT",
    "Netherlands": "NL",
    "Belgium": "BE",
    "Brazil": "BR",
    "Argentina": "AR",
    "Uruguay": "UY",
    "Colombia": "CO",
    "Mexico": "MX",
    "USA": "US",
    "United-States": "US",
    "Morocco": "MA",
    "Senegal": "SN",
    "Ghana": "GH",
    "Nigeria": "NG",
    "Croatia": "HR",
    "Serbia": "RS",
    "Switzerland": "CH",
    "Austria": "AT",
    "Poland": "PL",
    "Denmark": "DK",
    "Sweden": "SE",
    "Norway": "NO",
    "Turkey": "TR",
    "Türkiye": "TR",
    "Japan": "JP",
    "Korea Republic": "KR",
    "South Korea": "KR",
    "Australia": "AU",
    "Scotland": "SC",
    "Wales": "WA",
    "Northern Ireland": "NX",
    "Ireland": "IE",
    "Republic of Ireland": "IE",
    "Monaco": "MC",
    "Algeria": "DZ",
    "Egypt": "EG",
    "Cameroon": "CM",
    "Ivory Coast": "CI",
    "Côte d'Ivoire": "CI",
    "Paraguay": "PY",
    "Chile": "CL",
    "Ecuador": "EC",
    "Peru": "PE",
    "Canada": "CA",
    "Ukraine": "UA",
    "Russia": "RU",
    "Czech Republic": "CZ",
    "Czechia": "CZ",
    "Hungary": "HU",
    "Greece": "GR",
    "Romania": "RO",
    "Slovenia": "SI",
    "Slovakia": "SK",
    "Bosnia and Herzegovina": "BA",
    "Mali": "ML",
    "Guinea": "GN",
    "Tunisia": "TN",
    "South Africa": "ZA",
    "Wales": "GB",
    "Northern-Ireland": "GB",
    "Ivory-Coast": "CI",
    "Korea-Republic": "KR",
    "United-Arab-Emirates": "AE",
    "Saudi-Arabia": "SA",
    "Costa-Rica": "CR",
    "New-Zealand": "NZ",
    "Czech-Republic": "CZ",
    "Bosnia-Herzegovina": "BA",
    "Bosnia-And-Herzegovina": "BA",
    "North-Macedonia": "MK",
    "Macedonia": "MK",
    "Trinidad-And-Tobago": "TT",
    "Trinidad and Tobago": "TT",
    "El-Salvador": "SV",
    "El Salvador": "SV",
    "Cape-Verde": "CV",
    "Cabo Verde": "CV",
    "Hong-Kong": "HK",
    "Hong Kong": "HK",
    "Faroe-Islands": "FO",
    "Faroe Islands": "FO",
    "Dominican-Republic": "DO",
    "Dominican Republic": "DO",
    "Burkina-Faso": "BF",
    "Burkina Faso": "BF",
    "DR Congo": "CD",
    "Congo DR": "CD",
    "Congo-DR": "CD",
    "Cote D'Ivoire": "CI",
    "Cote d'Ivoire": "CI",
    "China": "CN",
    "Chinese-Taipei": "TW",
    "Taiwan": "TW",
    "Palestine": "PS",
    "Kosovo": "XK",
    "Curacao": "CW",
    "Curaçao": "CW",
}

POSITION_MAP = {
    "Goalkeeper": "GK",
    "Defender": "CB",
    "Midfielder": "CM",
    "Attacker": "ST",
}


class ApiError(Exception):
    pass


def load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_json(path: Path, data: dict, *, retries: int = 8) -> None:
    """Escritura atómica + reintentos (OneDrive / antivirus a menudo bloquean .json)."""
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            tmp.write_text(payload, encoding="utf-8")
            # En Windows, replace falla si el destino está bloqueado
            os.replace(tmp, path)
            return
        except PermissionError as e:
            last_err = e
            wait = min(2.0 * attempt, 10.0)
            print(f"  aviso: no se pudo guardar {path.name} (intento {attempt}/{retries}), espera {wait:.0f}s…")
            time.sleep(wait)
        except OSError as e:
            last_err = e
            time.sleep(min(1.5 * attempt, 8.0))
    # último recurso: escritura directa
    try:
        path.write_text(payload, encoding="utf-8")
        return
    except Exception as e:
        last_err = e
    raise PermissionError(
        f"No se pudo guardar {path}. Cierra el archivo si lo tienes abierto "
        f"(Excel/editor) y pausa sync de OneDrive un momento. Detalle: {last_err}"
    ) from last_err


def slug_code(text: str, fallback: str) -> str:
    text = (text or fallback).upper()
    text = re.sub(r"[^A-Z0-9]+", "_", text).strip("_")
    return (text[:12] or fallback)[:12]


def api_get(path: str, params: dict, key: str, counters: dict, *, max_retries: int = 5) -> dict:
    if counters["used"] >= counters["soft_limit"]:
        raise ApiError(
            f"Tope de seguridad alcanzado ({counters['soft_limit']} req). "
            "Para no quemar el plan Free, paramos."
        )
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{BASE}{path}?{qs}" if qs else f"{BASE}{path}"

    attempt = 0
    while True:
        req = urllib.request.Request(
            url,
            headers={
                "x-apisports-key": key,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
                remaining = resp.headers.get("x-ratelimit-requests-remaining")
                data = json.loads(raw)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code in (429, 500, 502, 503) and attempt < max_retries:
                attempt += 1
                wait = 65 if e.code == 429 else min(30, 5 * attempt)
                print(f"  HTTP {e.code} → espera {wait}s (reintento {attempt}/{max_retries})")
                time.sleep(wait)
                continue
            raise ApiError(f"HTTP {e.code}: {body[:300]}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            # DNS caído, red intermitente (p. ej. getaddrinfo failed) — reintentar
            if attempt < max_retries:
                attempt += 1
                wait = min(60, 5 * attempt)
                print(f"  red/DNS ({e}) → espera {wait}s (reintento {attempt}/{max_retries})")
                time.sleep(wait)
                continue
            raise ApiError(f"Red/DNS tras {max_retries} reintentos: {e}") from e

        errors = data.get("errors") or {}
        # API-Sports a veces devuelve 200 con errors.rateLimit
        rate_hit = False
        if errors:
            err_txt = str(errors).lower()
            if "ratelimit" in err_txt or "too many requests" in err_txt:
                rate_hit = True
        if rate_hit and attempt < max_retries:
            attempt += 1
            wait = 65
            print(f"  rateLimit → espera {wait}s (reintento {attempt}/{max_retries})")
            time.sleep(wait)
            continue

        counters["used"] += 1
        if remaining is not None:
            counters["remaining_header"] = remaining
        if errors:
            raise ApiError(f"API errors: {errors}")
        print(f"  API {path} params={params} -> results={data.get('results')} (req #{counters['used']})")
        # Ritmo para no pegar rateLimit/minuto (Pro suele ser estricto en ráfagas)
        if path.startswith("/players/squads"):
            time.sleep(2.0)
        else:
            time.sleep(0.35)
        return data


def normalize_founded_year(value) -> int | None:
    """API a veces manda 0; el CHECK exige NULL o 1800–2100."""
    if value is None or value == "":
        return None
    try:
        y = int(value)
    except (TypeError, ValueError):
        return None
    if y < 1800 or y > 2100:
        return None
    return y


def connect():
    password = os.environ.get("PGPASSWORD")
    if not password:
        raise SystemExit("Falta PGPASSWORD")
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        user=os.environ.get("PGUSER", "postgres"),
        password=password,
        dbname=os.environ.get("PGDATABASE", "iflxi"),
        row_factory=dict_row,
    )


def mid(store: dict, entity: str, code: str) -> uuid.UUID:
    bucket = store.setdefault(entity, {})
    if code in bucket:
        return uuid.UUID(bucket[code])
    new_id = uuid.uuid4()
    bucket[code] = str(new_id)
    return new_id


def normalize_iso2(iso2: str | None, fallback: str = "XX") -> str:
    """country.iso2 es character(2); la API a veces manda códigos raros o nombres."""
    if not iso2:
        return fallback
    s = str(iso2).strip().upper()
    if len(s) == 2 and s.isalpha():
        return s
    # Algunos mapas usan códigos no ISO (p.ej. England→GB ya está en COUNTRY_ISO)
    mapped = COUNTRY_ISO.get(iso2) or COUNTRY_ISO.get(str(iso2).strip())
    if mapped and len(mapped) == 2:
        return mapped.upper()
    return fallback


def ensure_country(cur, store, iso2: str, name: str) -> uuid.UUID:
    iso2 = normalize_iso2(iso2)
    # Si el "iso" era inválido y caímos a XX, guardar el nombre real
    display = name or iso2
    cur.execute("SELECT id FROM country WHERE iso2 = %s", (iso2,))
    row = cur.fetchone()
    if row:
        store.setdefault("country", {})[iso2] = str(row["id"])
        return row["id"]
    cid = mid(store, "country", iso2)
    cur.execute(
        """
        INSERT INTO country (id, iso2, name_default, is_active)
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT (iso2) DO UPDATE SET name_default = EXCLUDED.name_default
        RETURNING id
        """,
        (cid, iso2, display),
    )
    rid = cur.fetchone()["id"]
    store.setdefault("country", {})[iso2] = str(rid)
    return rid


def ensure_city(cur, store, city_code: str, city_name: str, country_id: uuid.UUID) -> uuid.UUID | None:
    if not city_name:
        return None
    city_code = slug_code(city_code or city_name, "CITY")
    # try map first
    if city_code in store.get("city", {}):
        return uuid.UUID(store["city"][city_code])
    cur.execute(
        "SELECT id FROM city WHERE country_id = %s AND lower(name_default) = lower(%s) LIMIT 1",
        (country_id, city_name),
    )
    row = cur.fetchone()
    if row:
        store.setdefault("city", {})[city_code] = str(row["id"])
        return row["id"]
    cid = mid(store, "city", city_code)
    cur.execute(
        """
        INSERT INTO city (id, country_id, name_default, is_active)
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT (id) DO UPDATE SET name_default = EXCLUDED.name_default
        RETURNING id
        """,
        (cid, country_id, city_name),
    )
    rid = cur.fetchone()["id"]
    store.setdefault("city", {})[city_code] = str(rid)
    return rid


def parse_height_cm(h):
    if not h:
        return None
    # "178 cm"
    m = re.search(r"(\d+)", str(h))
    return int(m.group(1)) if m else None


def parse_weight_kg(w):
    if not w:
        return None
    m = re.search(r"(\d+)", str(w))
    return int(m.group(1)) if m else None


def foot_from_api(_):
    return None  # API players endpoint no trae pie de forma fiable aquí


def fetch_players_by_league(key: str, counters: dict, league_api_id: int, season_year: int, max_pages: int) -> list:
    """Estadísticas por liga+temporada. A menudo vacío al inicio de temporada nueva."""
    players: list = []
    page = 1
    while True:
        pdata = api_get(
            "/players",
            {"league": league_api_id, "season": season_year, "page": page},
            key,
            counters,
        )
        batch = pdata.get("response") or []
        players.extend(batch)
        paging = pdata.get("paging") or {}
        total = int(paging.get("total") or 1)
        current = int(paging.get("current") or page)
        print(f"  jugadores página {current}/{total} (+{len(batch)})")
        if current >= total or not batch:
            break
        page += 1
        if page > max_pages:
            print(f"  corte por --max-player-pages={max_pages}")
            break
    return players


def fetch_players_from_squads(key: str, counters: dict, teams: list) -> list:
    """
    Plantilla actual por equipo: /players/squads?team=ID
    Normaliza a forma compatible con /players (player + statistics[0].team/position).
    """
    normalized: list = []
    for item in teams:
        t = item.get("team") or {}
        api_tid = t.get("id")
        if not api_tid:
            continue
        sdata = api_get("/players/squads", {"team": api_tid}, key, counters)
        for block in sdata.get("response") or []:
            team_block = block.get("team") or t
            team_id = team_block.get("id") or api_tid
            for pl in block.get("players") or []:
                # Squads trae menos campos (sin birth/height a veces)
                normalized.append(
                    {
                        "player": {
                            "id": pl.get("id"),
                            "name": pl.get("name"),
                            "firstname": None,
                            "lastname": None,
                            "age": pl.get("age"),
                            "nationality": None,
                            "height": None,
                            "weight": None,
                            "photo": pl.get("photo"),
                            "birth": {},
                        },
                        "statistics": [
                            {
                                "team": {"id": team_id},
                                "games": {"position": pl.get("position")},
                            }
                        ],
                    }
                )
        print(f"  plantilla team={api_tid} ({t.get('name')}): acumulado={len(normalized)}")
    return normalized


def import_league(args):
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise SystemExit("Falta API_FOOTBALL_KEY")

    league = LEAGUES[args.league]
    season_year = args.season
    season_code = f"{league['code']}_{str(season_year)[2:]}{str(season_year+1)[2:]}"
    # 2025 -> 2526
    season_code = f"{league['code']}_{str(season_year)[2:]}{str(season_year + 1)[2:]}"

    counters = {"used": 0, "soft_limit": args.max_requests, "remaining_header": None}
    api_map = load_json(MAP_PATH)
    store = load_json(EXCEL_MAP_PATH)  # reutiliza mapa de códigos si existe

    print(f"Liga: {league['name']} (api_id={league['api_id']}) season={season_year}")
    print(f"Modo: {'DRY-RUN' if args.dry_run else 'APPLY'}")
    print(f"Tope requests este run: {args.max_requests}")

    # 1) teams
    teams_data = api_get(
        "/teams",
        {"league": league["api_id"], "season": season_year},
        key,
        counters,
    )
    teams = teams_data.get("response") or []
    print(f"Equipos API: {len(teams)}")

    players = []
    if args.with_players:
        mode = args.players_mode
        if mode in ("stats", "auto"):
            players = fetch_players_by_league(
                key, counters, league["api_id"], season_year, args.max_player_pages
            )
            if players:
                print(f"Jugadores API (stats liga): {len(players)}")
            elif mode == "stats":
                print("Jugadores API (stats liga): 0 — sin fallback (players-mode=stats)")
        if mode == "squads" or (mode == "auto" and not players):
            if mode == "auto" and not players:
                print(
                    "Stats liga vacías → fallback /players/squads por equipo "
                    "(plantilla actual; típico al inicio de temporada)"
                )
            players = fetch_players_from_squads(key, counters, teams)
            print(f"Jugadores API (squads): {len(players)}")
        elif mode == "auto":
            pass  # ya contados arriba
        if not players and mode != "stats":
            print("Jugadores API: 0 (ni stats ni squads)")

    fixtures = []
    if args.with_fixtures:
        fdata = api_get(
            "/fixtures",
            {"league": league["api_id"], "season": season_year},
            key,
            counters,
        )
        fixtures = fdata.get("response") or []
        print(f"Partidos API: {len(fixtures)}")

    if args.dry_run:
        print("\nDRY-RUN OK (sin escribir en BD)")
        print(f"Requests usados en este run: {counters['used']}")
        if counters.get("remaining_header"):
            print(f"Remaining (header): {counters['remaining_header']}")
        print("Siguiente: añade --apply  (y opcional --with-players)")
        return

    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                # country + competition + season
                country_id = ensure_country(cur, store, league["iso2"], league["country"])
                comp_code = league["code"]
                comp_id = mid(store, "competition", comp_code)
                cur.execute(
                    """
                    INSERT INTO competition (
                      id, name_default, short_name, competition_type, scope,
                      country_id, gender, age_category, is_active
                    ) VALUES (%s,%s,%s,'league','domestic',%s,'male','senior',TRUE)
                    ON CONFLICT (id) DO UPDATE SET
                      name_default = EXCLUDED.name_default,
                      country_id = EXCLUDED.country_id,
                      updated_at = now()
                    """,
                    (comp_id, league["name"], league["name"], country_id),
                )
                api_map.setdefault("competition", {})[str(league["api_id"])] = comp_code

                season_id = mid(store, "season", season_code)
                # No marcar is_current por defecto: piloto 2025 no debe tumbar
                # la season current 2026. Solo con --mark-current.
                is_current = bool(getattr(args, "mark_current", False))
                if is_current:
                    cur.execute(
                        "UPDATE season SET is_current = FALSE, updated_at = now() WHERE competition_id = %s",
                        (comp_id,),
                    )
                cur.execute(
                    """
                    INSERT INTO season (
                      id, competition_id, name_default, year_start, year_end, is_current
                    ) VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                      name_default = EXCLUDED.name_default,
                      year_start = EXCLUDED.year_start,
                      year_end = EXCLUDED.year_end,
                      is_current = CASE
                        WHEN EXCLUDED.is_current THEN TRUE
                        ELSE season.is_current
                      END,
                      updated_at = now()
                    """,
                    (
                        season_id,
                        comp_id,
                        f"{season_year}/{str(season_year + 1)[2:]}",
                        season_year,
                        season_year + 1,
                        is_current,
                    ),
                )
                api_map.setdefault("season", {})[f"{league['api_id']}:{season_year}"] = season_code

                team_api_to_code = {}
                for item in teams:
                    t = item.get("team") or {}
                    v = item.get("venue") or {}
                    api_tid = str(t.get("id"))
                    code = (t.get("code") or slug_code(t.get("name"), f"T{api_tid}")).upper()
                    # evitar colisiones simples
                    if code in store.get("team", {}) and api_map.get("team", {}).get(api_tid) != code:
                        code = f"{code}{api_tid[-2:]}"
                    team_api_to_code[api_tid] = code
                    api_map.setdefault("team", {})[api_tid] = code

                    cname = t.get("country") or league["country"]
                    iso = COUNTRY_ISO.get(cname, league["iso2"])
                    cid = ensure_country(cur, store, iso, cname)
                    city_id = ensure_city(cur, store, v.get("city"), v.get("city"), cid)
                    tid = mid(store, "team", code)
                    cur.execute(
                        """
                        INSERT INTO team (
                          id, name_default, short_name, code, team_kind, gender,
                          age_category, country_id, city_id, founded_year, is_active
                        ) VALUES (%s,%s,%s,%s,'club','male','senior',%s,%s,%s,TRUE)
                        ON CONFLICT (id) DO UPDATE SET
                          name_default = EXCLUDED.name_default,
                          short_name = EXCLUDED.short_name,
                          code = EXCLUDED.code,
                          country_id = EXCLUDED.country_id,
                          city_id = EXCLUDED.city_id,
                          founded_year = EXCLUDED.founded_year,
                          updated_at = now()
                        """,
                        (
                            tid,
                            t.get("name"),
                            t.get("name"),
                            t.get("code"),
                            cid,
                            city_id,
                            normalize_founded_year(t.get("founded")),
                        ),
                    )
                    # team_competition
                    tc_code = f"{code}__{season_code}"
                    tcid = mid(store, "team_competition", tc_code)
                    cur.execute(
                        """
                        INSERT INTO team_competition (id, team_id, season_id, status)
                        VALUES (%s,%s,%s,'registered')
                        ON CONFLICT (team_id, season_id) DO UPDATE SET
                          status = 'registered', updated_at = now()
                        """,
                        (tcid, tid, season_id),
                    )

                # players
                if args.with_players:
                    for item in players:
                        p = item.get("player") or {}
                        stats = item.get("statistics") or []
                        api_pid = str(p.get("id"))
                        pcode = slug_code(
                            (p.get("lastname") or p.get("name") or api_pid).replace(" ", ""),
                            f"P{api_pid}",
                        )
                        # uniqueness
                        if pcode in store.get("player", {}) and api_map.get("player", {}).get(api_pid) != pcode:
                            pcode = f"{pcode}{api_pid[-3:]}"
                        api_map.setdefault("player", {})[api_pid] = pcode
                        person_code = f"{pcode}_P"
                        person_id = mid(store, "person", person_code)
                        nat = p.get("nationality")
                        nat_iso = COUNTRY_ISO.get(nat) if nat else None
                        nat_id = ensure_country(cur, store, nat_iso, nat) if nat_iso else None
                        birth = (p.get("birth") or {})
                        bcountry = birth.get("country")
                        b_iso = COUNTRY_ISO.get(bcountry) if bcountry else None
                        b_cid = ensure_country(cur, store, b_iso, bcountry) if b_iso else None
                        birth_date = None
                        if birth.get("date"):
                            try:
                                birth_date = date.fromisoformat(birth["date"][:10])
                            except ValueError:
                                birth_date = None
                        if birth_date is None and p.get("age") is not None:
                            try:
                                age_i = int(p["age"])
                                if 15 <= age_i <= 50:
                                    birth_date = date(date.today().year - age_i, 7, 1)
                            except (TypeError, ValueError):
                                pass

                        cur.execute(
                            """
                            INSERT INTO person (
                              id, full_name, display_name, first_name, last_name,
                              birth_date, birth_country_id
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (id) DO UPDATE SET
                              full_name = EXCLUDED.full_name,
                              display_name = EXCLUDED.display_name,
                              first_name = EXCLUDED.first_name,
                              last_name = EXCLUDED.last_name,
                              birth_date = EXCLUDED.birth_date,
                              birth_country_id = EXCLUDED.birth_country_id,
                              updated_at = now()
                            """,
                            (
                                person_id,
                                p.get("name") or f"{p.get('firstname')} {p.get('lastname')}",
                                p.get("name") or p.get("lastname") or pcode,
                                p.get("firstname"),
                                p.get("lastname"),
                                birth_date,
                                b_cid,
                            ),
                        )

                        pos = None
                        team_api = None
                        if stats:
                            pos = (stats[0].get("games") or {}).get("position")
                            team_api = str(((stats[0].get("team") or {}).get("id") or ""))
                        primary = POSITION_MAP.get(pos)
                        player_id = mid(store, "player", pcode)
                        cur.execute(
                            """
                            INSERT INTO player (
                              id, person_id, nationality_country_id, primary_position,
                              height_cm, weight_kg, shirt_name, status
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,'active')
                            ON CONFLICT (id) DO UPDATE SET
                              nationality_country_id = EXCLUDED.nationality_country_id,
                              primary_position = COALESCE(EXCLUDED.primary_position, player.primary_position),
                              height_cm = EXCLUDED.height_cm,
                              weight_kg = EXCLUDED.weight_kg,
                              shirt_name = EXCLUDED.shirt_name,
                              updated_at = now()
                            """,
                            (
                                player_id,
                                person_id,
                                nat_id,
                                primary,
                                parse_height_cm(p.get("height")),
                                parse_weight_kg(p.get("weight")),
                                p.get("name"),
                            ),
                        )

                        # open club history if team known
                        if team_api and team_api in team_api_to_code:
                            tcode = team_api_to_code[team_api]
                            tid = uuid.UUID(store["team"][tcode])
                            hcode = f"{pcode}_{tcode}_{season_year}"
                            hid = mid(store, "history", hcode)
                            cur.execute(
                                """
                                INSERT INTO player_team_history (
                                  id, player_id, team_id, role, start_date, end_date
                                ) VALUES (%s,%s,%s,'permanent',%s,NULL)
                                ON CONFLICT (id) DO UPDATE SET
                                  team_id = EXCLUDED.team_id,
                                  updated_at = now()
                                """,
                                (hid, player_id, tid, date(season_year, 7, 1)),
                            )

                # fixtures (sin eventos aquí — ver api_football_import_events.py)
                # IMPORTANTE: home_score/away_score = acta oficial API (goals.*).
                # NUNCA recalcular desde MATCH_EVENT.
                if args.with_fixtures:
                    fixture_limit = args.limit if args.limit and args.limit > 0 else None
                    written = 0
                    skipped = 0
                    for item in fixtures:
                        if fixture_limit is not None and written >= fixture_limit:
                            break
                        fix = item.get("fixture") or {}
                        teams_f = item.get("teams") or {}
                        goals = item.get("goals") or {}
                        league_f = item.get("league") or {}
                        api_fid = str(fix.get("id") or "")
                        if not api_fid:
                            skipped += 1
                            continue
                        home_api = str(((teams_f.get("home") or {}).get("id") or ""))
                        away_api = str(((teams_f.get("away") or {}).get("id") or ""))
                        if home_api not in team_api_to_code or away_api not in team_api_to_code:
                            skipped += 1
                            continue
                        mcode = f"{season_code}_{team_api_to_code[home_api]}_{team_api_to_code[away_api]}_{api_fid[-4:]}"
                        mid_ = mid(store, "match", mcode)
                        api_map.setdefault("match", {})[api_fid] = mcode
                        status_short = ((fix.get("status") or {}).get("short") or "").upper()
                        status_map = {
                            "TBD": "scheduled",
                            "NS": "scheduled",
                            "1H": "live",
                            "HT": "live",
                            "2H": "live",
                            "ET": "live",
                            "P": "live",
                            "FT": "finished",
                            "AET": "finished",
                            "PEN": "finished",
                            "PST": "postponed",
                            "CANC": "cancelled",
                            "ABD": "cancelled",
                            "AWD": "awarded",
                            "WO": "awarded",
                        }
                        st = status_map.get(status_short, "scheduled")
                        # MVP: no usar live operativo
                        if st == "live":
                            st = "scheduled"
                        hs, aws = goals.get("home"), goals.get("away")
                        # CHECK ck_match_scores_when_finished: finished|awarded exige scores
                        if st in ("finished", "awarded") and (hs is None or aws is None):
                            print(
                                f"  WARN fixture {api_fid}: status={st} sin marcador completo; "
                                "se guarda como scheduled (acta incompleta)"
                            )
                            st = "scheduled"
                        kick = fix.get("date")
                        match_date = date.fromisoformat(kick[:10]) if kick else None
                        if not match_date:
                            skipped += 1
                            continue
                        cur.execute(
                            """
                            INSERT INTO match (
                              id, season_id, home_team_id, away_team_id, match_date,
                              kickoff_at, round_name, status, home_score, away_score
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (id) DO UPDATE SET
                              status = EXCLUDED.status,
                              home_score = EXCLUDED.home_score,
                              away_score = EXCLUDED.away_score,
                              kickoff_at = EXCLUDED.kickoff_at,
                              round_name = EXCLUDED.round_name,
                              updated_at = now()
                            """,
                            (
                                mid_,
                                season_id,
                                uuid.UUID(store["team"][team_api_to_code[home_api]]),
                                uuid.UUID(store["team"][team_api_to_code[away_api]]),
                                match_date,
                                kick,
                                league_f.get("round"),
                                st,
                                hs,
                                aws,
                            ),
                        )
                        written += 1
                    print(f"Partidos escritos: {written} (omitidos/skip: {skipped})")

                # refresh caches (omitir en piloto solo-fixtures para no tocar player masivo)
                if args.with_players or not args.with_fixtures:
                    cur.execute(
                        """
                        UPDATE player p
                        SET current_team_id = s.team_id, updated_at = now()
                        FROM (
                          SELECT DISTINCT ON (h.player_id) h.player_id, h.team_id
                          FROM player_team_history h
                          JOIN team t ON t.id = h.team_id
                          WHERE h.end_date IS NULL AND t.team_kind = 'club'
                          ORDER BY h.player_id, h.start_date DESC
                        ) s
                        WHERE p.id = s.player_id
                        """
                    )
                elif args.with_fixtures:
                    print("  (skip refresh current_team_id: piloto fixtures sin --with-players)")

        save_json(MAP_PATH, api_map)
        save_json(EXCEL_MAP_PATH, store)

    print("\nIMPORT API OK")
    print(f"Requests usados: {counters['used']}")
    if counters.get("remaining_header"):
        print(f"Remaining header: {counters['remaining_header']}")
    print(f"Mapa API: {MAP_PATH}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", choices=sorted(LEAGUES.keys()), default="laliga")
    ap.add_argument("--season", type=int, default=2024, help="Free plan: 2022-2024")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--with-players", action="store_true")
    ap.add_argument(
        "--players-mode",
        choices=("auto", "stats", "squads"),
        default="auto",
        help="auto=stats liga y si vacío squads; stats=/players; squads=/players/squads",
    )
    ap.add_argument("--with-fixtures", action="store_true")
    ap.add_argument(
        "--mark-current",
        action="store_true",
        help="Marcar esta season como is_current (off por defecto; no usar en piloto 2025).",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Con --with-fixtures: máx. partidos a escribir (0 = todos). Piloto: 5.",
    )
    ap.add_argument(
        "--max-requests",
        type=int,
        default=80,
        help="Tope seguridad por ejecución (squads ≈ 1 + N equipos)",
    )
    ap.add_argument("--max-player-pages", type=int, default=20, help="Máx páginas de jugadores")
    args = ap.parse_args()
    if args.dry_run == args.apply:
        print("Usa exactamente una opción: --dry-run  o  --apply")
        sys.exit(2)
    try:
        import_league(args)
    except ApiError as e:
        print("ERROR API:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
