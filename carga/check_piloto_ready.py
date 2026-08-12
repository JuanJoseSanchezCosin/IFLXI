#!/usr/bin/env python3
"""
Chequeo de preparación del piloto MATCH + MATCH_EVENT.
Solo lectura: no escribe BD ni mapas ni llama a API-Football.

Uso:
  py check_piloto_ready.py
  py check_piloto_ready.py --league laliga --season 2025
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAP = ROOT / ".api_football_map.json"
CACHE = ROOT / ".api_leagues_cache.json"
STORE = ROOT / ".import_map.json"

LEAGUE_API = {
    "laliga": 140,
    "premier": 39,
    "seriea": 135,
    "bundesliga": 78,
    "ligue1": 61,
}


def load(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def coverage_events(cache: dict, api_id: int, season: int) -> bool | None:
    for item in cache.get("response") or []:
        lg = item.get("league") or {}
        if int(lg.get("id") or -1) != api_id:
            continue
        for s in item.get("seasons") or []:
            if int(s.get("year") or -1) == season:
                return bool(((s.get("coverage") or {}).get("fixtures") or {}).get("events"))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="laliga", choices=sorted(LEAGUE_API.keys()))
    ap.add_argument("--season", type=int, default=2025)
    args = ap.parse_args()
    api_id = LEAGUE_API[args.league]

    ok = True
    print(f"=== Check piloto {args.league} season={args.season} ===\n")

    amap = load(MAP)
    store = load(STORE)
    cache = load(CACHE)

    if not amap:
        print("FAIL: falta .api_football_map.json")
        sys.exit(1)
    if not store:
        print("FAIL: falta .import_map.json")
        sys.exit(1)
    if not cache:
        print("FAIL: falta .api_leagues_cache.json")
        ok = False

    fill = amap.get("fill") or {}
    n_teams = len(fill.get("teams") or {})
    n_squads = len(fill.get("squads") or {})
    n_teams_fill = n_teams
    comps = len(amap.get("competition") or {})
    print(f"fill.teams marcadas:  {n_teams_fill}")
    print(f"fill.squads marcadas: {n_squads}")
    print(f"competition en mapa: {comps} (incluye Cups; no usar como pendientes)")

    # Misma lógica que fill_leagues: pendientes = ligas type=League sin flag fill
    league_ids = []
    for item in (cache or {}).get("response") or []:
        lg = item.get("league") or {}
        lid = lg.get("id")
        if not lid:
            continue
        if (lg.get("type") or "").lower() != "league":
            continue
        league_ids.append(str(lid))
    pending_teams = sum(1 for lid in league_ids if lid not in (fill.get("teams") or {}))
    pending_squads = sum(1 for lid in league_ids if lid not in (fill.get("squads") or {}))
    print(f"Pendientes teams (League):  ~{pending_teams} / {len(league_ids)}")
    print(f"Pendientes squads (League): ~{pending_squads} / {len(league_ids)}")

    if pending_squads > 0 or pending_teams > 0:
        print("WARN: fill aún incompleto (type=League) — no lances fixtures/events.")
        ok = False
    else:
        print("OK: fill League cerrado (teams+squads ~0 pendientes).")

    ev = coverage_events(cache or {}, api_id, args.season) if cache else None
    print(f"\ncoverage.fixtures.events league={api_id} season={args.season}: {ev}")
    if ev is True:
        print("OK: events disponibles para el piloto.")
    elif ev is False:
        print("FAIL: events=false — elige otra temporada (p. ej. 2025).")
        ok = False
    else:
        print("WARN: no se pudo leer coverage en cache.")
        ok = False

    n_team_api = len(amap.get("team") or {})
    n_player_api = len(amap.get("player") or {})
    n_match_api = len(amap.get("match") or {})
    print(f"\nmapa team:   {n_team_api}")
    print(f"mapa player: {n_player_api}")
    print(f"mapa match:  {n_match_api}")
    if n_team_api < 100:
        print("WARN: pocos teams mapeados.")
        ok = False
    if n_player_api < 1000:
        print("WARN: pocos players mapeados (events tendrán muchos skips).")
        ok = False
    if n_match_api == 0:
        print("INFO: aún no hay MATCH mapeados — normal antes del piloto fixtures.")

    print("\n--- Siguiente cuando fill termine ---")
    print("  1) .\\piloto_match_events.ps1 -BackupMaps")
    print(f"  2) py api_football_import.py --league {args.league} --season {args.season} --apply --with-fixtures --limit 5")
    print(f"  3) py api_football_import_events.py --league {args.league} --season {args.season} --limit 5 --dry-run")
    print(f"  4) py api_football_import_events.py --league {args.league} --season {args.season} --limit 5 --apply")

    print("\nRESULTADO:", "LISTO (con matices)" if ok else "NO LISTO — espera fill / revisa WARN")
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    main()
