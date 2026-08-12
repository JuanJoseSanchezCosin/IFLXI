#!/usr/bin/env python3
"""
IFLXI — Importar catálogo completo de competiciones API-Football → PostgreSQL

1 request: GET /leagues
Escribe: country (si falta) + competition + season actual
NO carga equipos / jugadores / partidos.

Uso:
  $env:API_FOOTBALL_KEY = "..."
  $env:PGPASSWORD = "..."
  $env:PGDATABASE = "iflxi"

  py api_football_import_leagues.py --dry-run
  py api_football_import_leagues.py --apply
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date

from api_football_import import (
    ApiError,
    MAP_PATH,
    EXCEL_MAP_PATH,
    api_get,
    connect,
    ensure_country,
    load_json,
    mid,
    save_json,
)

WORLD_ISO = "XX"
WORLD_NAME = "International"


def pick_current_season(seasons: list) -> dict | None:
    if not seasons:
        return None
    for s in seasons:
        if s.get("current"):
            return s
    return max(seasons, key=lambda s: int(s.get("year") or 0))


def classify_competition(league_type: str, name: str, has_country: bool) -> tuple[str, str]:
    """
    Returns (competition_type, scope) for IFLXI enums.
    """
    n = (name or "").lower()
    api_type = (league_type or "").lower()

    world_nat = (
        "world cup",
        "fifa",
        "olympics",
        "olympic",
        "confederations",
    )
    continental_nat = (
        "euro championship",
        "european championship",
        "copa america",
        "africa cup",
        "african nations",
        "asian cup",
        "gold cup",
        "nations league",
        "concacaf",
        "afc asian",
        "ofc",
    )
    club_intl = (
        "champions league",
        "europa league",
        "conference league",
        "uefa super cup",
        "club world",
        "libertadores",
        "sudamericana",
        "recopa",
        "caf champions",
        "afc champions",
        "concacaf champions",
        "leagues cup",
    )

    if not has_country:
        if any(k in n for k in world_nat) or "world cup" in n:
            if "club" in n:
                return "international_club", "world"
            return "international_national", "world"
        if any(k in n for k in continental_nat):
            return "international_national", "continental"
        if any(k in n for k in club_intl) or api_type == "cup":
            # Copas/intercontinentales sin país → club intl por defecto
            scope = "world" if "world" in n or "fifa" in n else "continental"
            return "international_club", scope
        if api_type == "league":
            return "league", "continental"
        return "other", "world"

    # Domésticas
    if api_type == "league":
        return "league", "domestic"
    if api_type == "cup":
        return "cup", "domestic"
    return "other", "domestic"


def guess_gender(name: str) -> str:
    n = (name or "").lower()
    if any(k in n for k in ("women", "woman", "femenin", "feminine", "female", "womens")):
        return "female"
    return "male"


def guess_age(name: str) -> str:
    n = (name or "").lower()
    if "u17" in n or "under 17" in n:
        return "u17"
    if "u19" in n or "under 19" in n:
        return "u19"
    if "u21" in n or "under 21" in n:
        return "u21"
    if "u23" in n or "under 23" in n:
        return "u23"
    return "senior"


def season_code_for(comp_code: str, year: int) -> str:
    y2 = str(year)[2:]
    y2n = str(year + 1)[2:]
    return f"{comp_code}_{y2}{y2n}"


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def competition_code(api_id: str, api_map: dict) -> str:
    existing = (api_map.get("competition") or {}).get(api_id)
    if existing:
        return existing
    return f"AF_{api_id}"


def import_catalog(args) -> None:
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise SystemExit("Falta API_FOOTBALL_KEY")

    counters = {"used": 0, "soft_limit": args.max_requests, "remaining_header": None}
    api_map = load_json(MAP_PATH)
    store = load_json(EXCEL_MAP_PATH)

    print("Catálogo API-Football → competition + season (current)")
    print(f"Modo: {'DRY-RUN' if args.dry_run else 'APPLY'}")

    data = api_get("/leagues", {}, key, counters)
    items = data.get("response") or []
    print(f"Competiciones API: {len(items)}")

    stats = {
        "competitions": 0,
        "seasons": 0,
        "skipped_no_season": 0,
        "countries_touched": set(),
        "by_type": {},
    }

    # Preview dry-run samples
    if args.dry_run:
        for item in items[:8]:
            lg = item.get("league") or {}
            cy = item.get("country") or {}
            cur = pick_current_season(item.get("seasons") or [])
            ctype, scope = classify_competition(
                lg.get("type") or "", lg.get("name") or "", bool(cy.get("code") or cy.get("name"))
            )
            print(
                f"  sample id={lg.get('id')} {lg.get('name')!r} "
                f"type={ctype}/{scope} season={cur.get('year') if cur else None}"
            )
        print("\nDRY-RUN OK (sin escribir en BD)")
        print(f"Requests usados: {counters['used']}")
        if counters.get("remaining_header"):
            print(f"Remaining header: {counters['remaining_header']}")
        print("Siguiente: py api_football_import_leagues.py --apply")
        return

    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                # País International para competiciones sin country
                ensure_country(cur, store, WORLD_ISO, WORLD_NAME)

                for item in items:
                    lg = item.get("league") or {}
                    cy = item.get("country") or {}
                    api_id = str(lg.get("id") or "")
                    if not api_id:
                        continue
                    name = lg.get("name") or f"League {api_id}"
                    api_type = lg.get("type") or ""

                    iso = (cy.get("code") or "").strip().upper()
                    cname = cy.get("name") or ""
                    has_country = bool(iso) and iso not in ("", "XX")
                    # API a veces pone country name World sin code
                    if not iso and cname and cname.lower() in ("world", "international"):
                        has_country = False

                    if has_country:
                        # Algunos codes raros: normalizar longitud 2
                        if len(iso) != 2:
                            iso = re.sub(r"[^A-Z]", "", iso)[:2] or WORLD_ISO
                            if iso == WORLD_ISO:
                                has_country = False
                        if has_country:
                            country_id = ensure_country(cur, store, iso, cname or iso)
                            stats["countries_touched"].add(iso)
                        else:
                            country_id = ensure_country(cur, store, WORLD_ISO, WORLD_NAME)
                    else:
                        country_id = None  # internacional: country_id NULL según diccionario

                    ctype, scope = classify_competition(api_type, name, has_country)
                    gender = guess_gender(name)
                    age = guess_age(name)

                    comp_code = competition_code(api_id, api_map)
                    api_map.setdefault("competition", {})[api_id] = comp_code
                    comp_id = mid(store, "competition", comp_code)

                    # Domésticas: country_id; internacionales: NULL (aunque tengamos XX)
                    db_country_id = country_id if has_country else None

                    cur.execute(
                        """
                        INSERT INTO competition (
                          id, name_default, short_name, competition_type, scope,
                          country_id, gender, age_category, is_active
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
                        ON CONFLICT (id) DO UPDATE SET
                          name_default = EXCLUDED.name_default,
                          short_name = EXCLUDED.short_name,
                          competition_type = EXCLUDED.competition_type,
                          scope = EXCLUDED.scope,
                          country_id = EXCLUDED.country_id,
                          gender = EXCLUDED.gender,
                          age_category = EXCLUDED.age_category,
                          is_active = TRUE,
                          updated_at = now()
                        """,
                        (
                            comp_id,
                            name,
                            name,
                            ctype,
                            scope,
                            db_country_id,
                            gender,
                            age,
                        ),
                    )
                    stats["competitions"] += 1
                    stats["by_type"][ctype] = stats["by_type"].get(ctype, 0) + 1

                    cur_season = pick_current_season(item.get("seasons") or [])
                    if not cur_season:
                        stats["skipped_no_season"] += 1
                        continue

                    year = int(cur_season.get("year") or 0)
                    if year <= 0:
                        stats["skipped_no_season"] += 1
                        continue

                    scode = season_code_for(comp_code, year)
                    # Reutilizar season code ya mapeado para ese api_id:year (Big 5)
                    mapped = (api_map.get("season") or {}).get(f"{api_id}:{year}")
                    if mapped:
                        scode = mapped
                    api_map.setdefault("season", {})[f"{api_id}:{year}"] = scode
                    season_id = mid(store, "season", scode)

                    # Una sola current por competición
                    cur.execute(
                        "UPDATE season SET is_current = FALSE, updated_at = now() WHERE competition_id = %s",
                        (comp_id,),
                    )
                    season_name = f"{year}/{str(year + 1)[2:]}"
                    cur.execute(
                        """
                        INSERT INTO season (
                          id, competition_id, name_default, year_start, year_end,
                          start_date, end_date, is_current
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE)
                        ON CONFLICT (id) DO UPDATE SET
                          name_default = EXCLUDED.name_default,
                          year_start = EXCLUDED.year_start,
                          year_end = EXCLUDED.year_end,
                          start_date = EXCLUDED.start_date,
                          end_date = EXCLUDED.end_date,
                          is_current = TRUE,
                          updated_at = now()
                        """,
                        (
                            season_id,
                            comp_id,
                            season_name,
                            year,
                            year + 1,
                            parse_date(cur_season.get("start")),
                            parse_date(cur_season.get("end")),
                        ),
                    )
                    stats["seasons"] += 1

        save_json(MAP_PATH, api_map)
        save_json(EXCEL_MAP_PATH, store)

    print("\nIMPORT CATÁLOGO OK")
    print(f"Competitions upserted: {stats['competitions']}")
    print(f"Seasons (current) upserted: {stats['seasons']}")
    print(f"Sin season usable: {stats['skipped_no_season']}")
    print(f"Tipos: {stats['by_type']}")
    print(f"Países tocados: {len(stats['countries_touched'])}")
    print(f"Requests usados: {counters['used']}")
    if counters.get("remaining_header"):
        print(f"Remaining header: {counters['remaining_header']}")
    print(f"Mapa API: {MAP_PATH}")


def main():
    ap = argparse.ArgumentParser(description="Importar catálogo /leagues → IFLXI")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-requests", type=int, default=5)
    args = ap.parse_args()
    if args.dry_run == args.apply:
        print("Usa exactamente una opción: --dry-run  o  --apply")
        sys.exit(2)
    try:
        import_catalog(args)
    except ApiError as e:
        print("ERROR API:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
