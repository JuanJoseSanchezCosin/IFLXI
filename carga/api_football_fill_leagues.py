#!/usr/bin/env python3
"""
IFLXI — Rellenar ligas del catálogo con equipos (+ plantillas opcionales)

Lee competiciones ya mapeadas / catálogo API, y por lotes:
  1) GET /teams?league=&season=
  2) opcional: GET /players/squads?team= por equipo

Reanuda con api_map["fill"]["teams"|"squads"]. Respeta --max-requests.

Uso:
  py api_football_fill_leagues.py --dry-run --mode teams --max-requests 50
  py api_football_fill_leagues.py --apply --mode teams --max-requests 400
  py api_football_fill_leagues.py --apply --mode squads --max-requests 500

Por defecto solo type=League (no copas). Big 5 ya cargadas se saltan.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import date
from pathlib import Path

from api_football_import import (
    ApiError,
    COUNTRY_ISO,
    EXCEL_MAP_PATH,
    MAP_PATH,
    POSITION_MAP,
    api_get,
    connect,
    ensure_city,
    ensure_country,
    fetch_players_from_squads,
    load_json,
    mid,
    normalize_founded_year,
    normalize_iso2,
    parse_height_cm,
    parse_weight_kg,
    save_json,
    slug_code,
)

ROOT = Path(__file__).resolve().parent
LEAGUES_CACHE = ROOT / ".api_leagues_cache.json"

# Ya rellenadas en piloto (equipos + plantillas)
ALREADY_FILLED_SQUADS = {"140", "39", "135", "78", "61"}


def iso_for_country_name(name: str | None, fallback: str = "XX") -> str:
    fb = normalize_iso2(fallback, "XX")
    if not name:
        return fb
    if name in COUNTRY_ISO:
        return normalize_iso2(COUNTRY_ISO[name], fb)
    alt = name.replace(" ", "-")
    if alt in COUNTRY_ISO:
        return normalize_iso2(COUNTRY_ISO[alt], fb)
    # Si "name" ya es un ISO2 válido
    if len(str(name).strip()) == 2 and str(name).strip().isalpha():
        return str(name).strip().upper()
    return fb


def load_leagues_catalog(key: str, counters: dict, refresh: bool) -> list:
    if LEAGUES_CACHE.exists() and not refresh:
        data = json.loads(LEAGUES_CACHE.read_text(encoding="utf-8"))
        items = data.get("response") or data
        print(f"Catálogo ligas (cache): {len(items)}  [{LEAGUES_CACHE.name}]")
        return items
    data = api_get("/leagues", {}, key, counters)
    LEAGUES_CACHE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    items = data.get("response") or []
    print(f"Catálogo ligas (API): {len(items)} → cache {LEAGUES_CACHE.name}")
    return items


def current_year(item: dict) -> int | None:
    seasons = item.get("seasons") or []
    for s in seasons:
        if s.get("current"):
            y = int(s.get("year") or 0)
            return y or None
    if not seasons:
        return None
    return int(max(seasons, key=lambda s: int(s.get("year") or 0)).get("year") or 0) or None


def season_code_for(comp_code: str, year: int) -> str:
    return f"{comp_code}_{str(year)[2:]}{str(year + 1)[2:]}"


def ensure_fill_seed(api_map: dict) -> None:
    fill = api_map.setdefault("fill", {})
    teams = fill.setdefault("teams", {})
    squads = fill.setdefault("squads", {})
    for aid in ALREADY_FILLED_SQUADS:
        teams.setdefault(aid, True)
        squads.setdefault(aid, True)


def upsert_teams_players(
    cur,
    store: dict,
    api_map: dict,
    *,
    comp_code: str,
    season_code: str,
    season_year: int,
    teams: list,
    players: list | None,
    default_country: str,
    default_iso: str,
) -> tuple[int, int]:
    season_id = mid(store, "season", season_code)
    # season debe existir (catálogo); si no, crear mínima ligada a competition
    comp_id = mid(store, "competition", comp_code)
    cur.execute("SELECT id FROM season WHERE id = %s", (season_id,))
    if not cur.fetchone():
        cur.execute(
            """
            INSERT INTO season (
              id, competition_id, name_default, year_start, year_end, is_current
            ) VALUES (%s,%s,%s,%s,%s,FALSE)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                season_id,
                comp_id,
                f"{season_year}/{str(season_year + 1)[2:]}",
                season_year,
                season_year + 1,
            ),
        )

    team_api_to_code: dict[str, str] = {}
    n_teams = 0
    for item in teams:
        t = item.get("team") or {}
        v = item.get("venue") or {}
        api_tid = str(t.get("id") or "")
        if not api_tid:
            continue
        # reutilizar código API map si existe
        code = (api_map.get("team") or {}).get(api_tid)
        if not code:
            code = (t.get("code") or slug_code(t.get("name"), f"T{api_tid}")).upper()
            if code in store.get("team", {}) and api_map.get("team", {}).get(api_tid) != code:
                code = f"{code}{api_tid[-2:]}"
        team_api_to_code[api_tid] = code
        api_map.setdefault("team", {})[api_tid] = code

        cname = t.get("country") or default_country
        iso = iso_for_country_name(cname, default_iso)
        cid = ensure_country(cur, store, iso, cname or iso)
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
        n_teams += 1

    n_players = 0
    if not players:
        return n_teams, n_players

    for item in players:
        p = item.get("player") or {}
        stats = item.get("statistics") or []
        api_pid = str(p.get("id") or "")
        if not api_pid:
            continue
        pcode = (api_map.get("player") or {}).get(api_pid)
        if not pcode:
            pcode = slug_code(
                (p.get("lastname") or p.get("name") or api_pid).replace(" ", ""),
                f"P{api_pid}",
            )
            if pcode in store.get("player", {}) and api_map.get("player", {}).get(api_pid) != pcode:
                pcode = f"{pcode}{api_pid[-3:]}"
        api_map.setdefault("player", {})[api_pid] = pcode
        person_code = f"{pcode}_P"
        person_id = mid(store, "person", person_code)
        nat = p.get("nationality")
        nat_iso = COUNTRY_ISO.get(nat) if nat else None
        nat_id = ensure_country(cur, store, nat_iso, nat) if nat_iso else None
        birth = p.get("birth") or {}
        bcountry = birth.get("country")
        b_iso = COUNTRY_ISO.get(bcountry) if bcountry else None
        b_cid = ensure_country(cur, store, b_iso, bcountry) if b_iso else None
        birth_date = None
        if birth.get("date"):
            try:
                birth_date = date.fromisoformat(birth["date"][:10])
            except ValueError:
                birth_date = None
        # Squads suele traer age sin birth: estimar 1 jul (no inventamos valor de mercado)
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
              birth_date = COALESCE(EXCLUDED.birth_date, person.birth_date),
              birth_country_id = COALESCE(EXCLUDED.birth_country_id, person.birth_country_id),
              updated_at = now()
            """,
            (
                person_id,
                p.get("name") or f"{p.get('firstname') or ''} {p.get('lastname') or ''}".strip(),
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
              nationality_country_id = COALESCE(EXCLUDED.nationality_country_id, player.nationality_country_id),
              primary_position = COALESCE(EXCLUDED.primary_position, player.primary_position),
              height_cm = COALESCE(EXCLUDED.height_cm, player.height_cm),
              weight_kg = COALESCE(EXCLUDED.weight_kg, player.weight_kg),
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
        n_players += 1

    return n_teams, n_players


def refresh_player_cache(cur) -> None:
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


def run(args) -> None:
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise SystemExit("Falta API_FOOTBALL_KEY")

    counters = {"used": 0, "soft_limit": args.max_requests, "remaining_header": None}
    api_map = load_json(MAP_PATH)
    store = load_json(EXCEL_MAP_PATH)
    ensure_fill_seed(api_map)

    fill = api_map.setdefault("fill", {})
    filled_teams = fill.setdefault("teams", {})
    filled_squads = fill.setdefault("squads", {})

    print(f"Modo fill: {args.mode} | {'DRY-RUN' if args.dry_run else 'APPLY'}")
    print(f"Tope requests: {args.max_requests} | tipo API: {args.api_type or 'ALL'}")

    items = load_leagues_catalog(key, counters, refresh=args.refresh_catalog)
    # Filtrar
    work = []
    for item in items:
        lg = item.get("league") or {}
        api_id = str(lg.get("id") or "")
        if not api_id:
            continue
        if args.api_type and (lg.get("type") or "").lower() != args.api_type.lower():
            continue
        if args.only_id and api_id != str(args.only_id):
            continue
        year = current_year(item)
        if not year:
            continue
        # ¿pendiente?
        if args.mode == "teams":
            if filled_teams.get(api_id) and not args.force:
                continue
        else:  # squads
            if filled_squads.get(api_id) and not args.force:
                continue
        # necesita mapping competition (del catálogo)
        if api_id not in (api_map.get("competition") or {}):
            # generar código al vuelo
            api_map.setdefault("competition", {})[api_id] = f"AF_{api_id}"
        work.append((api_id, lg, item.get("country") or {}, year))

    work.sort(key=lambda x: int(x[0]))
    if args.limit:
        work = work[: args.limit]

    print(f"Ligas pendientes este run: {len(work)}")
    if args.dry_run:
        for api_id, lg, cy, year in work[:15]:
            print(f"  would fill id={api_id} {lg.get('name')!r} season={year} country={cy.get('name')}")
        if len(work) > 15:
            print(f"  ... +{len(work) - 15} más")
        print(f"\nDRY-RUN OK | requests usados: {counters['used']}")
        print("Siguiente: --apply --mode teams --max-requests 400")
        return

    done = 0
    total_teams = 0
    total_players = 0
    stopped_budget = False

    for api_id, lg, cy, year in work:
        # margen: teams=1; squads ≈ 1 + n_teams (desconocido). Parar si no queda 1.
        if counters["used"] >= counters["soft_limit"]:
            stopped_budget = True
            break
        # para squads dejar margen mínimo de 2
        if args.mode == "squads" and counters["used"] + 2 > counters["soft_limit"]:
            stopped_budget = True
            break

        name = lg.get("name") or api_id
        comp_code = api_map["competition"][api_id]
        season_key = f"{api_id}:{year}"
        season_code = (api_map.get("season") or {}).get(season_key) or season_code_for(comp_code, year)
        api_map.setdefault("season", {})[season_key] = season_code

        default_country = cy.get("name") or "International"
        default_iso = normalize_iso2(
            cy.get("code") or iso_for_country_name(default_country),
            "XX",
        )

        print(f"\n→ [{api_id}] {name} season={year} ({comp_code})")

        try:
            tdata = api_get("/teams", {"league": int(api_id), "season": year}, key, counters)
        except ApiError as e:
            print(f"  ERROR teams: {e}")
            # marcar teams para no buclar errores fatales? no — dejar reintento
            if "Tope de seguridad" in str(e):
                stopped_budget = True
                break
            continue

        teams = tdata.get("response") or []
        print(f"  equipos: {len(teams)}")

        players = None
        if args.mode == "squads" and teams:
            # ¿cabe el lote de squads?
            need = len(teams)
            if counters["used"] + need > counters["soft_limit"]:
                print(
                    f"  presupuesto insuficiente para {need} squads "
                    f"(used={counters['used']}/{counters['soft_limit']}); "
                    "guardo equipos y dejo squads pendiente"
                )
                # escribir solo teams, no marcar squads
                with connect() as conn:
                    with conn.transaction():
                        with conn.cursor() as cur:
                            nt, _ = upsert_teams_players(
                                cur,
                                store,
                                api_map,
                                comp_code=comp_code,
                                season_code=season_code,
                                season_year=year,
                                teams=teams,
                                players=None,
                                default_country=default_country,
                                default_iso=default_iso or "XX",
                            )
                            total_teams += nt
                filled_teams[api_id] = True
                save_json(MAP_PATH, api_map)
                save_json(EXCEL_MAP_PATH, store)
                done += 1
                stopped_budget = True
                break

            try:
                players = fetch_players_from_squads(key, counters, teams)
            except ApiError as e:
                print(f"  ERROR squads: {e}")
                if "Tope de seguridad" in str(e):
                    # guardar progreso de equipos si se puede
                    stopped_budget = True
                players = None
                # No marcar filled_squads: esta liga se reintenta en el siguiente run.

        try:
            with connect() as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        nt, np = upsert_teams_players(
                            cur,
                            store,
                            api_map,
                            comp_code=comp_code,
                            season_code=season_code,
                            season_year=year,
                            teams=teams,
                            players=players,
                            default_country=default_country,
                            default_iso=default_iso or "XX",
                        )
                        if players:
                            refresh_player_cache(cur)
                        total_teams += nt
                        total_players += np
        except Exception as e:
            print(f"  ERROR BD (liga {api_id}): {e}")
            # no marcar fill → se reintenta en el siguiente run
            save_json(MAP_PATH, api_map)
            save_json(EXCEL_MAP_PATH, store)
            continue

        filled_teams[api_id] = True
        if args.mode == "squads" and players is not None:
            filled_squads[api_id] = True
        try:
            save_json(MAP_PATH, api_map)
            save_json(EXCEL_MAP_PATH, store)
        except PermissionError as e:
            print(f"  ERROR guardando mapas: {e}")
            print("  La liga YA está en BD; cierra .import_map.json / pausa OneDrive y reanuda.")
            # guardar lo que se pueda; salir para no seguir sin mapa
            try:
                save_json(MAP_PATH, api_map)
            except Exception:
                pass
            break
        done += 1
        print(f"  OK teams+={nt} players+={np if players else 0} | req={counters['used']}")

    print("\n======= FILL RESUMEN =======")
    print(f"Ligas procesadas: {done}")
    print(f"Equipos upserted (suma run): {total_teams}")
    print(f"Jugadores upserted (suma run): {total_players}")
    print(f"Requests usados: {counters['used']}")
    if counters.get("remaining_header"):
        print(f"Remaining header: {counters['remaining_header']}")
    def _type_ok(item: dict) -> bool:
        if not args.api_type:
            return True
        return ((item.get("league") or {}).get("type") or "").lower() == args.api_type.lower()

    pending_teams = sum(
        1
        for item in items
        if (item.get("league") or {}).get("id")
        and _type_ok(item)
        and not filled_teams.get(str((item.get("league") or {}).get("id")))
    )
    pending_squads = sum(
        1
        for item in items
        if (item.get("league") or {}).get("id")
        and _type_ok(item)
        and not filled_squads.get(str((item.get("league") or {}).get("id")))
    )
    print(f"Pendientes teams (filtro tipo): ~{pending_teams}")
    print(f"Pendientes squads (filtro tipo): ~{pending_squads}")
    if stopped_budget:
        print("Parado por tope de requests — vuelve a ejecutar el mismo comando para continuar.")
    print(f"Mapa: {MAP_PATH}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--mode", choices=("teams", "squads"), default="teams")
    ap.add_argument(
        "--api-type",
        default="League",
        help="Filtro API type: League | Cup | '' para todas",
    )
    ap.add_argument("--max-requests", type=int, default=400)
    ap.add_argument("--limit", type=int, default=0, help="Máx ligas este run (0=sin límite salvo requests)")
    ap.add_argument("--force", action="store_true", help="Reprocesar aunque fill diga hecho")
    ap.add_argument("--only-id", type=int, default=0, help="Solo una liga api_id")
    ap.add_argument("--refresh-catalog", action="store_true", help="Forzar GET /leagues")
    args = ap.parse_args()
    if args.api_type == "":
        args.api_type = None
    if args.dry_run == args.apply:
        print("Usa exactamente una opción: --dry-run  o  --apply")
        sys.exit(2)
    try:
        run(args)
    except ApiError as e:
        print("ERROR API:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
