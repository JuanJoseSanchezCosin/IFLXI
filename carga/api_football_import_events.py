#!/usr/bin/env python3
"""
IFLXI — Importador API-Football MATCH_EVENT (piloto controlado)

Lee eventos de:
  GET /fixtures/events?fixture={fixture_id}

Requisitos previos:
  - MATCH ya cargados (p. ej. api_football_import.py --with-fixtures --limit N)
  - Mapas .api_football_map.json + .import_map.json con team/player/match
  - coverage.fixtures.events = true para la liga/temporada (ver .api_leagues_cache.json)

Uso:
  py api_football_import_events.py --league laliga --season 2025 --limit 5 --dry-run
  py api_football_import_events.py --league laliga --season 2025 --limit 5 --apply

Reglas congeladas (no modificar modelo):
  - Nunca event_type=assist ni substitution_in
  - Asistencia = secondary_player_id en goal/penalty_goal
  - own_goal sin secondary
  - substitution_out: player_id=SALE, secondary=ENTRA
    (API: player=ENTRA, assist=SALE → se invierte)
  - MATCH.home_score/away_score NO se tocan aquí
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import uuid
from pathlib import Path

from api_football_import import (
    ApiError,
    EXCEL_MAP_PATH,
    LEAGUES,
    MAP_PATH,
    api_get,
    connect,
    load_json,
    mid,
    save_json,
)

ROOT = Path(__file__).resolve().parent
LEAGUES_CACHE = ROOT / ".api_leagues_cache.json"

# Normalización de detail (API puede variar mayúsculas/guiones)
DETAIL_GOAL = {
    "normal goal": "goal",
    "penalty": "penalty_goal",
    "missed penalty": "penalty_miss",
    "own goal": "own_goal",
}
DETAIL_CARD = {
    "yellow card": "yellow_card",
    "red card": "red_card",
    "yellow red card": "second_yellow",
    "yellow-red card": "second_yellow",
    "yellowred card": "second_yellow",
}


def norm_detail(text: str | None) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def resolve_league_api_id(league_arg: str) -> tuple[int, str]:
    """Acepta slug Big-5 (laliga) o id numérico API."""
    key = (league_arg or "").strip().lower()
    if key in LEAGUES:
        meta = LEAGUES[key]
        return int(meta["api_id"]), meta["code"]
    if key.isdigit():
        api_id = int(key)
        api_map = load_json(MAP_PATH)
        code = (api_map.get("competition") or {}).get(str(api_id)) or f"AF_{api_id}"
        return api_id, code
    raise SystemExit(f"Liga desconocida: {league_arg} (usa slug Big-5 o id API numérico)")


def coverage_events_ok(api_league_id: int, season_year: int) -> tuple[bool, str]:
    if not LEAGUES_CACHE.exists():
        return False, f"No existe {LEAGUES_CACHE.name}; ejecuta antes api_football_import_leagues.py"
    data = load_json(LEAGUES_CACHE)
    items = data.get("response") or data
    if not isinstance(items, list):
        return False, "Cache de ligas con formato inesperado"
    for item in items:
        lg = item.get("league") or {}
        if int(lg.get("id") or -1) != api_league_id:
            continue
        for s in item.get("seasons") or []:
            if int(s.get("year") or -1) != season_year:
                continue
            cov = ((s.get("coverage") or {}).get("fixtures") or {})
            ok = bool(cov.get("events"))
            return ok, (
                f"coverage.fixtures.events={cov.get('events')} "
                f"lineups={cov.get('lineups')} para league={api_league_id} season={season_year}"
            )
        return False, f"Temporada {season_year} no hallada en cache para league={api_league_id}"
    return False, f"League {api_league_id} no hallada en {LEAGUES_CACHE.name}"


def map_event_type(api_type: str | None, detail: str | None) -> str | None:
    t = (api_type or "").strip().lower()
    d = norm_detail(detail)
    if t == "goal":
        return DETAIL_GOAL.get(d)
    if t == "card":
        return DETAIL_CARD.get(d)
    if t in ("subst", "substitution"):
        return "substitution_out"
    # VAR y demás: sin representación en ENUM IFLXI
    return None


def event_natural_key(
    fixture_id: str,
    *,
    event_type: str,
    minute: int | None,
    extra: int | None,
    player_api: str,
    secondary_api: str,
    team_api: str,
    sort_order: int,
) -> str:
    """
    Idempotencia sin tocar el esquema SQL.

    Decisión: API-Football /fixtures/events no expone un event.id estable
    en el contrato que usamos. Clave natural determinista → código en
    .import_map.json bucket 'event' → UUID IFLXI. UPSERT ON CONFLICT (id).

    Clave = fixture + tipo + minuto + extra + player + secondary + team + orden API.
    """
    raw = "|".join(
        [
            str(fixture_id),
            event_type,
            "" if minute is None else str(minute),
            "" if extra is None else str(extra),
            player_api or "",
            secondary_api or "",
            team_api or "",
            str(sort_order),
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
    return f"AFEVT_{fixture_id}_{digest}"


def resolve_uuid(store: dict, entity: str, code: str | None) -> uuid.UUID | None:
    if not code:
        return None
    bucket = store.get(entity) or {}
    if code not in bucket:
        return None
    return uuid.UUID(bucket[code])


def resolve_from_api_map(
    api_map: dict, store: dict, entity: str, api_id: str | int | None
) -> tuple[str | None, uuid.UUID | None]:
    if api_id is None or api_id == "":
        return None, None
    code = (api_map.get(entity) or {}).get(str(api_id))
    if not code:
        return None, None
    return code, resolve_uuid(store, entity, code)


def list_fixtures_from_api(
    key: str, counters: dict, league_api_id: int, season_year: int
) -> list[dict]:
    data = api_get(
        "/fixtures",
        {"league": league_api_id, "season": season_year},
        key,
        counters,
    )
    return data.get("response") or []


def process_events(args) -> None:
    api_league_id, _league_code = resolve_league_api_id(args.league)
    season_year = int(args.season)
    limit = max(1, int(args.limit or 5))

    ok, cov_msg = coverage_events_ok(api_league_id, season_year)
    print(f"Coverage: {cov_msg}")
    if not ok:
        print(
            "WARN: events=false o no disponible para esta liga/temporada. "
            "No se harán llamadas a /fixtures/events. "
            "Prueba --season 2025 en Big-5 según cache actual."
        )
        sys.exit(3)

    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise SystemExit("Falta API_FOOTBALL_KEY")

    counters = {"used": 0, "soft_limit": int(args.max_requests), "remaining_header": None}
    api_map = load_json(MAP_PATH)
    store = load_json(EXCEL_MAP_PATH)

    if args.fixture:
        fixture_ids = [str(x).strip() for x in args.fixture.split(",") if str(x).strip()]
        fixture_meta: dict[str, dict] = {fid: {} for fid in fixture_ids}
    else:
        fixtures = list_fixtures_from_api(key, counters, api_league_id, season_year)

        def sort_key(item):
            fix = item.get("fixture") or {}
            st = ((fix.get("status") or {}).get("short") or "").upper()
            goals = item.get("goals") or {}
            done = 0 if st in ("FT", "AET", "PEN") and goals.get("home") is not None else 1
            return (done, fix.get("date") or "")

        fixtures = sorted(fixtures, key=sort_key)
        fixture_ids = []
        fixture_meta = {}
        for item in fixtures:
            fid = str((item.get("fixture") or {}).get("id") or "")
            if not fid:
                continue
            fixture_ids.append(fid)
            fixture_meta[fid] = item

    print(f"Fixtures API candidatos: {len(fixture_ids)} (limit piloto={limit})")

    selected: list[tuple[str, uuid.UUID, dict]] = []
    missing_match = 0
    for fid in fixture_ids:
        if len(selected) >= limit:
            break
        mcode = (api_map.get("match") or {}).get(fid)
        match_uuid = resolve_uuid(store, "match", mcode) if mcode else None
        if not match_uuid:
            missing_match += 1
            print(f"  fixture no encontrado en MATCH: {fid}")
            continue
        selected.append((fid, match_uuid, fixture_meta.get(fid) or {}))

    if not selected:
        league_slug = args.league if args.league in LEAGUES else "laliga"
        print(
            "ERROR: ningún fixture del lote está en MATCH.\n"
            "Primero carga partidos, p. ej.:\n"
            f"  py api_football_import.py --league {league_slug} "
            f"--season {season_year} --apply --with-fixtures --limit {limit}"
        )
        if missing_match:
            print(f"  (fixtures vistos sin MATCH mapeado: {missing_match})")
        sys.exit(4)

    print(f"Fixtures con MATCH en BD: {len(selected)} (omitidos sin MATCH: {missing_match})")

    stats = {
        "events_seen": 0,
        "events_mapped": 0,
        "events_upserted": 0,
        "ignored": 0,
        "warnings": 0,
        "errors": 0,
    }
    planned_rows: list[dict] = []

    for fid, match_uuid, meta in selected:
        print("\n" + "=" * 60)
        print(f"MATCH: fixture {fid} → match UUID {match_uuid}")
        if meta:
            teams = meta.get("teams") or {}
            goals = meta.get("goals") or {}
            print(
                f"  {((teams.get('home') or {}).get('name'))} "
                f"{goals.get('home')} - {goals.get('away')} "
                f"{((teams.get('away') or {}).get('name'))} "
                f"| status={((meta.get('fixture') or {}).get('status') or {}).get('short')}"
            )
            print("  (marcador oficial en MATCH; este importador NO lo modifica)")

        try:
            edata = api_get("/fixtures/events", {"fixture": fid}, key, counters)
        except ApiError as e:
            print(f"  ERROR API events fixture {fid}: {e}")
            stats["errors"] += 1
            continue

        events = edata.get("response") or []
        print(f"  Eventos API: {len(events)}")

        for ord_i, ev in enumerate(events):
            stats["events_seen"] += 1
            api_type = ev.get("type")
            detail = ev.get("detail")
            etype = map_event_type(api_type, detail)
            if not etype:
                stats["ignored"] += 1
                stats["warnings"] += 1
                print(
                    f"  WARN ignored #{ord_i}: type={api_type!r} detail={detail!r} "
                    "(sin representación en ENUM IFLXI)"
                )
                continue

            time_o = ev.get("time") or {}
            minute = time_o.get("elapsed")
            extra = time_o.get("extra")
            try:
                minute_i = int(minute) if minute is not None else None
            except (TypeError, ValueError):
                minute_i = None
            try:
                extra_i = int(extra) if extra is not None else None
            except (TypeError, ValueError):
                extra_i = None

            # CHECK PostgreSQL: minute 0–120, extra 0–30
            if minute_i is not None and not (0 <= minute_i <= 120):
                print(f"  WARN #{ord_i}: minute={minute_i} fuera de rango → NULL")
                stats["warnings"] += 1
                minute_i = None
            if extra_i is not None and not (0 <= extra_i <= 30):
                print(f"  WARN #{ord_i}: extra_minute={extra_i} fuera de rango → NULL")
                stats["warnings"] += 1
                extra_i = None

            team_api = str(((ev.get("team") or {}).get("id") or "") or "")
            player_api = str(((ev.get("player") or {}).get("id") or "") or "")
            assist_api = str(((ev.get("assist") or {}).get("id") or "") or "")

            # --- papeles según tipo (reglas congeladas) ---
            primary_api = player_api
            secondary_api = ""
            if etype in ("goal", "penalty_goal"):
                # assist → secondary_player_id; NUNCA event_type=assist
                primary_api = player_api
                secondary_api = assist_api
            elif etype == "own_goal":
                primary_api = player_api
                secondary_api = ""  # regla 10
            elif etype == "substitution_out":
                # API: player = ENTRA, assist = SALE
                # IFLXI: player_id = SALE, secondary_player_id = ENTRA
                primary_api = assist_api
                secondary_api = player_api
            else:
                # cards, penalty_miss
                primary_api = player_api
                secondary_api = ""

            _team_code, team_uuid = resolve_from_api_map(api_map, store, "team", team_api)
            _p_code, player_uuid = resolve_from_api_map(api_map, store, "player", primary_api)
            _s_code, secondary_uuid = resolve_from_api_map(
                api_map, store, "player", secondary_api
            )

            skip = False
            if not team_uuid:
                print(
                    f"  WARN #{ord_i} {etype} {minute_i}': "
                    f"team API {team_api or '∅'} sin mapping → skip"
                )
                stats["warnings"] += 1
                skip = True
            if etype == "substitution_out":
                if not primary_api or not secondary_api:
                    print(
                        f"  WARN #{ord_i} substitution_out {minute_i}': "
                        f"falta sale/entra (assist={assist_api or '∅'}, "
                        f"player={player_api or '∅'}) → skip"
                    )
                    stats["warnings"] += 1
                    skip = True
                elif not player_uuid or not secondary_uuid:
                    print(
                        f"  WARN #{ord_i} substitution_out {minute_i}': "
                        f"jugador no mapeado sale={primary_api} entra={secondary_api} → skip"
                    )
                    stats["warnings"] += 1
                    skip = True
            elif etype in (
                "goal",
                "own_goal",
                "penalty_goal",
                "penalty_miss",
                "yellow_card",
                "red_card",
                "second_yellow",
            ):
                if not primary_api or not player_uuid:
                    print(
                        f"  WARN #{ord_i} {etype} {minute_i}': "
                        f"player API {primary_api or '∅'} sin mapping → skip"
                    )
                    stats["warnings"] += 1
                    skip = True
                if etype in ("goal", "penalty_goal") and secondary_api and not secondary_uuid:
                    print(
                        f"  WARN #{ord_i} {etype} {minute_i}': "
                        f"assist API {secondary_api} sin mapping → secondary=NULL"
                    )
                    stats["warnings"] += 1
                    secondary_uuid = None
                    secondary_api = ""
                if (
                    secondary_uuid
                    and player_uuid
                    and secondary_uuid == player_uuid
                ):
                    print(
                        f"  WARN #{ord_i} {etype} {minute_i}': "
                        f"asistente = goleador (dato API inconsistente) → secondary=NULL"
                    )
                    stats["warnings"] += 1
                    secondary_uuid = None
                    secondary_api = ""

            if skip:
                continue

            # period (event_period): sin info fiable de periodo en el payload
            # de events → NULL (columna nullable). No inventar first_half/etc.
            period = None

            ekey = event_natural_key(
                fid,
                event_type=etype,
                minute=minute_i,
                extra=extra_i,
                player_api=primary_api,
                secondary_api=secondary_api,
                team_api=team_api,
                sort_order=ord_i,
            )
            # Dry-run: no reservar UUID vía mid() (evita UUID distintos al apply).
            # Apply: mid() escribe en store['event'] y se persiste solo .import_map.json.
            event_id = None if args.dry_run else mid(store, "event", ekey)
            stats["events_mapped"] += 1

            row = {
                "id": event_id,
                "match_id": match_uuid,
                "event_type": etype,
                "player_id": player_uuid,
                "secondary_player_id": secondary_uuid,
                "team_id": team_uuid,
                "minute": minute_i,
                "extra_minute": extra_i,
                "period": period,
                "sort_order": ord_i,
                "key": ekey,
            }
            planned_rows.append(row)

            label = f"{minute_i}'" if minute_i is not None else "?"
            if extra_i:
                label += f"+{extra_i}"
            print(f"  EVENT: {label} {etype}  (API {api_type}/{detail})")
            if etype == "substitution_out":
                print(
                    f"    sale API {primary_api} → player_id={player_uuid}\n"
                    f"    entra API {secondary_api} → secondary_player_id={secondary_uuid}"
                )
            else:
                print(f"    player API {primary_api} → {player_uuid}")
                if etype in ("goal", "penalty_goal"):
                    print(
                        f"    assist API {secondary_api or '∅'} → "
                        f"secondary_player_id={secondary_uuid}"
                    )
            print(f"    team API {team_api} → {team_uuid}")
            if args.dry_run:
                print(f"    idempotency key={ekey} (UUID se asigna en --apply)")
            else:
                print(f"    idempotency key={ekey} → event UUID {event_id}")

    print("\n======= RESUMEN =======")
    print(
        f"events_seen={stats['events_seen']} mapped={stats['events_mapped']} "
        f"ignored={stats['ignored']} warnings={stats['warnings']} errors={stats['errors']}"
    )
    print(f"Requests usados: {counters['used']}")
    if counters.get("remaining_header"):
        print(f"Remaining header: {counters['remaining_header']}")

    if args.dry_run:
        print("DRY-RUN OK — no se escribió PostgreSQL ni mapas.")
        return

    if not planned_rows:
        print("APPLY: nada que insertar.")
        return

    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                skipped_db = 0
                for row in planned_rows:
                    # Defensa: este script NUNCA hace UPDATE/INSERT sobre match
                    # (home_score/away_score = acta oficial; no recalcular).
                    # Cada fila va en su propio savepoint: si una fila falla por
                    # un dato inesperado, se descarta solo ella y sigue el resto
                    # (antes: un solo fallo tiraba toda la carga sin insertar nada).
                    try:
                        with conn.transaction():
                            cur.execute(
                                """
                                INSERT INTO match_event (
                                  id, match_id, event_type, player_id, secondary_player_id,
                                  team_id, minute, extra_minute, period, sort_order
                                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                ON CONFLICT (id) DO UPDATE SET
                                  event_type = EXCLUDED.event_type,
                                  player_id = EXCLUDED.player_id,
                                  secondary_player_id = EXCLUDED.secondary_player_id,
                                  team_id = EXCLUDED.team_id,
                                  minute = EXCLUDED.minute,
                                  extra_minute = EXCLUDED.extra_minute,
                                  period = EXCLUDED.period,
                                  sort_order = EXCLUDED.sort_order,
                                  updated_at = now()
                                """,
                                (
                                    row["id"],
                                    row["match_id"],
                                    row["event_type"],
                                    row["player_id"],
                                    row["secondary_player_id"],
                                    row["team_id"],
                                    row["minute"],
                                    row["extra_minute"],
                                    row["period"],
                                    row["sort_order"],
                                ),
                            )
                    except Exception as exc:
                        skipped_db += 1
                        print(f"  WARN DB: fila {row['id']} rechazada ({exc}) → skip")
                        continue
                    stats["events_upserted"] += 1
                if skipped_db:
                    print(f"Filas rechazadas por la base de datos: {skipped_db}")

    # Solo persistir .import_map.json (bucket event + UUIDs).
    # NO reescribir .api_football_map.json: este importador no lo muta y
    # un save concurrente con fill_leagues podría pisar progreso de squads.
    save_json(EXCEL_MAP_PATH, store)
    print(f"APPLY OK — eventos upserted: {stats['events_upserted']}")
    print(f"Mapa UUID: {EXCEL_MAP_PATH}")
    print("NOTA: .api_football_map.json no se ha modificado.")
    print("NOTA: MATCH.home_score/away_score no fueron modificados.")


def main():
    ap = argparse.ArgumentParser(
        description="IFLXI API-Football -> MATCH_EVENT (piloto; no toca scores de MATCH)"
    )
    ap.add_argument(
        "--league",
        required=True,
        help="Slug Big-5 (laliga, premier, ...) o id numérico API",
    )
    ap.add_argument("--season", type=int, required=True, help="Año API (piloto: 2025)")
    ap.add_argument("--limit", type=int, default=5, help="Máx. partidos a procesar (piloto=5)")
    ap.add_argument(
        "--fixture",
        default="",
        help="Opcional: fixture id(s) API separados por coma (salta listado)",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-requests", type=int, default=40)
    args = ap.parse_args()
    if args.dry_run == args.apply:
        print("Usa exactamente una opción: --dry-run  o  --apply")
        sys.exit(2)
    try:
        process_events(args)
    except ApiError as e:
        print("ERROR API:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()