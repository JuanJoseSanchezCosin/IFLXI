#!/usr/bin/env python3
"""
IFLXI — Importador API-Football → TRANSFER (preparado; NO ejecutar durante fill)

Endpoint:
  GET /transfers?team={team_id}
  GET /transfers?player={player_id}

Uso (SOLO cuando fill_leagues haya parado y no escriba mapas):
  py api_football_import_transfers.py --league laliga --limit-teams 3 --dry-run
  py api_football_import_transfers.py --league laliga --limit-teams 3 --apply

Reglas congeladas:
  - No inventar entidades ni tocar SQL estructural
  - free / end_of_contract ⇒ fee_amount NULL (nunca 0)
  - Este importador v1 NO sincroniza PLAYER_TEAM_HISTORY automáticamente
    (regla 4: related_history_id queda NULL hasta fase de sync)
  - No recalcula market values (API-Football no trae Transfermarkt €)
  - --apply solo persiste bucket 'transfer' en .import_map.json
    (NO reescribe .api_football_map.json)

NO ejecutar en paralelo con fill_leagues (misma API key + mismo mapa UUID).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import uuid
from datetime import date, datetime
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


def parse_fee(type_str: str | None) -> tuple[str, float | None, str | None, bool]:
    """
    API type ejemplos: "€45M", "€1.5M", "Free", "Loan", "N/A".
    → (transfer_type, fee_amount, fee_currency, fee_is_estimated)
    """
    raw = (type_str or "").strip()
    low = raw.lower()
    if not raw or low in ("n/a", "na", "-"):
        return "unknown", None, None, False
    if "loan" in low:
        return "loan", None, None, False
    if low in ("free", "bosman") or "free" in low:
        return "free", None, None, False

    # Importe tipo €45M / $12.5M / £3m
    m = re.search(r"([€$£])\s*([\d.,]+)\s*([kKmMbB])?", raw)
    if not m:
        # Solo número raro → unknown
        return "unknown", None, None, False

    sym, num_s, scale = m.group(1), m.group(2), (m.group(3) or "").upper()
    num_s = num_s.replace(",", ".")
    try:
        val = float(num_s)
    except ValueError:
        return "unknown", None, None, False
    if scale == "K":
        val *= 1_000
    elif scale == "M":
        val *= 1_000_000
    elif scale == "B":
        val *= 1_000_000_000

    currency = {"€": "EUR", "$": "USD", "£": "GBP"}.get(sym, "EUR")
    if val <= 0:
        return "permanent", None, None, True
    return "permanent", val, currency, True  # fees API suelen ser estimados


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = str(s).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            return None


def transfer_key(player_api: str, date_s: str, out_api: str, in_api: str, ttype: str) -> str:
    raw = "|".join([player_api, date_s, out_api, in_api, ttype])
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"AFTR_{player_api}_{digest}"


def resolve_uuid(store: dict, entity: str, code: str | None) -> uuid.UUID | None:
    if not code:
        return None
    bucket = store.get(entity) or {}
    if code not in bucket:
        return None
    return uuid.UUID(bucket[code])


def resolve_from_api(
    api_map: dict, store: dict, entity: str, api_id
) -> tuple[str | None, uuid.UUID | None]:
    if api_id is None or api_id == "":
        return None, None
    code = (api_map.get(entity) or {}).get(str(api_id))
    if not code:
        return None, None
    return code, resolve_uuid(store, entity, code)


def teams_for_league(api_map: dict, league_slug: str, limit: int) -> list[tuple[str, str]]:
    """Devuelve [(api_team_id, team_code), ...] ya mapeados."""
    meta = LEAGUES.get(league_slug)
    if not meta:
        raise SystemExit(f"Liga desconocida: {league_slug}")
    # Preferir equipos del mapa team cuya code o presencia sea Big-5;
    # no hay liga en cada team → tomamos los primeros N del mapa team
    # filtrando por codes conocidos del import Big-5 si existen.
    teams = api_map.get("team") or {}
    items = list(teams.items())  # api_id -> code
    # Heurística: priorizar codes "famosos" no hace falta; limit corta
    out = []
    for api_id, code in items:
        out.append((str(api_id), code))
        if len(out) >= limit:
            break
    return out


def process(args) -> None:
    if args.dry_run == args.apply:
        print("Usa exactamente una opción: --dry-run  o  --apply")
        sys.exit(2)

    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise SystemExit("Falta API_FOOTBALL_KEY")

    print(
        "AVISO: no ejecutar en paralelo con fill_leagues "
        "(comparte API key y .import_map.json)."
    )

    counters = {"used": 0, "soft_limit": int(args.max_requests), "remaining_header": None}
    api_map = load_json(MAP_PATH)
    store = load_json(EXCEL_MAP_PATH)

    team_list: list[tuple[str, str]] = []
    if args.team:
        for tid in str(args.team).split(","):
            tid = tid.strip()
            if not tid:
                continue
            code = (api_map.get("team") or {}).get(tid)
            if not code:
                print(f"WARN: team API {tid} sin mapping — omitido")
                continue
            team_list.append((tid, code))
    else:
        # Equipos de la liga vía /teams (1 req) y filtrar los ya mapeados
        league = LEAGUES[args.league]
        tdata = api_get(
            "/teams",
            {"league": league["api_id"], "season": args.season},
            key,
            counters,
        )
        mapped = 0
        for item in tdata.get("response") or []:
            api_tid = str((item.get("team") or {}).get("id") or "")
            if not api_tid:
                continue
            code = (api_map.get("team") or {}).get(api_tid)
            if not code:
                continue
            team_list.append((api_tid, code))
            mapped += 1
            if args.limit_teams and mapped >= args.limit_teams:
                break

    if not team_list:
        print("ERROR: ningún equipo mapeado para pedir /transfers")
        sys.exit(4)

    print(f"Equipos a consultar transfers: {len(team_list)}")

    planned: list[dict] = []
    stats = {"seen": 0, "mapped": 0, "skip": 0, "warn": 0}

    for api_tid, tcode in team_list:
        try:
            data = api_get("/transfers", {"team": int(api_tid)}, key, counters)
        except ApiError as e:
            print(f"  ERROR transfers team={api_tid}: {e}")
            stats["warn"] += 1
            continue

        for block in data.get("response") or []:
            pl = block.get("player") or {}
            player_api = str(pl.get("id") or "")
            for tr in block.get("transfers") or []:
                stats["seen"] += 1
                teams_o = tr.get("teams") or {}
                out_api = str(((teams_o.get("out") or {}).get("id") or "") or "")
                in_api = str(((teams_o.get("in") or {}).get("id") or "") or "")
                date_s = (tr.get("date") or "")[:10]
                type_raw = tr.get("type")
                ttype, fee, currency, estimated = parse_fee(type_raw)
                eff = parse_date(date_s)
                if not eff:
                    print(f"  WARN sin fecha: player={player_api} type={type_raw!r} → skip")
                    stats["skip"] += 1
                    continue

                p_code, player_uuid = resolve_from_api(api_map, store, "player", player_api)
                _o, from_uuid = resolve_from_api(api_map, store, "team", out_api)
                _i, to_uuid = resolve_from_api(api_map, store, "team", in_api)

                if not player_uuid:
                    print(f"  WARN player API {player_api} sin mapping → skip")
                    stats["skip"] += 1
                    stats["warn"] += 1
                    continue
                if not to_uuid and not from_uuid:
                    print(f"  WARN transfer sin equipos mapeados player={player_api} → skip")
                    stats["skip"] += 1
                    continue
                if from_uuid and to_uuid and from_uuid == to_uuid:
                    stats["skip"] += 1
                    continue
                if ttype in ("free", "end_of_contract"):
                    fee, currency = None, None

                tkey = transfer_key(player_api, date_s, out_api, in_api, ttype)
                row = {
                    "key": tkey,
                    "player_id": player_uuid,
                    "from_team_id": from_uuid,
                    "to_team_id": to_uuid,
                    "transfer_type": ttype,
                    "announced_date": eff,
                    "effective_date": eff,
                    "fee_amount": fee,
                    "fee_currency": currency,
                    "fee_is_estimated": estimated,
                    "related_history_id": None,
                    "player_api": player_api,
                    "type_raw": type_raw,
                }
                planned.append(row)
                stats["mapped"] += 1
                print(
                    f"  TRANSFER {date_s} player={player_api} "
                    f"{out_api or '∅'}→{in_api or '∅'} {ttype} "
                    f"fee={fee} {currency or ''} (API {type_raw!r})"
                )

    print("\n======= RESUMEN =======")
    print(
        f"seen={stats['seen']} mapped={stats['mapped']} "
        f"skip={stats['skip']} warn={stats['warn']} req={counters['used']}"
    )
    if counters.get("remaining_header"):
        print(f"Remaining header: {counters['remaining_header']}")

    if args.dry_run:
        print("DRY-RUN OK — no se escribió PostgreSQL ni mapas.")
        print("NOTA: related_history_id=NULL en v1 (sync HISTORY = fase aparte).")
        return

    if not planned:
        print("APPLY: nada que insertar.")
        return

    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                for row in planned:
                    tid = mid(store, "transfer", row["key"])
                    cur.execute(
                        """
                        INSERT INTO transfer (
                          id, player_id, from_team_id, to_team_id, transfer_type,
                          announced_date, effective_date, fee_amount, fee_currency,
                          fee_is_estimated, related_history_id
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (id) DO UPDATE SET
                          player_id = EXCLUDED.player_id,
                          from_team_id = EXCLUDED.from_team_id,
                          to_team_id = EXCLUDED.to_team_id,
                          transfer_type = EXCLUDED.transfer_type,
                          announced_date = EXCLUDED.announced_date,
                          effective_date = EXCLUDED.effective_date,
                          fee_amount = EXCLUDED.fee_amount,
                          fee_currency = EXCLUDED.fee_currency,
                          fee_is_estimated = EXCLUDED.fee_is_estimated,
                          updated_at = now()
                        """,
                        (
                            tid,
                            row["player_id"],
                            row["from_team_id"],
                            row["to_team_id"],
                            row["transfer_type"],
                            row["announced_date"],
                            row["effective_date"],
                            row["fee_amount"],
                            row["fee_currency"],
                            row["fee_is_estimated"],
                            None,
                        ),
                    )

    save_json(EXCEL_MAP_PATH, store)
    print(f"APPLY OK — transfers upserted: {len(planned)}")
    print("NOTA: .api_football_map.json no modificado.")
    print("NOTA: HISTORY no sincronizado (related_history_id NULL).")


def main():
    ap = argparse.ArgumentParser(
        description="IFLXI API-Football -> TRANSFER (no ejecutar durante fill)"
    )
    ap.add_argument("--league", choices=sorted(LEAGUES.keys()), default="laliga")
    ap.add_argument(
        "--season",
        type=int,
        default=2026,
        help="Solo para listar equipos de la liga (no filtra transfers por año)",
    )
    ap.add_argument("--limit-teams", type=int, default=3, help="Piloto: máx equipos")
    ap.add_argument("--team", default="", help="API team id(s) separados por coma")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-requests", type=int, default=40)
    args = ap.parse_args()
    try:
        process(args)
    except ApiError as e:
        print("ERROR API:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
