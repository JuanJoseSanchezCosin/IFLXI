#!/usr/bin/env python3
"""
IFLXI — Sincroniza TRANSFER → PLAYER_TEAM_HISTORY (Anexo A.4).

NO ejecutar durante fill (escribe HISTORY + cache current_team_id).
NO toca mapas API. Solo BD.

Uso (cuando haya transfers cargados y fill parado):
  py sync_transfer_history.py --limit 20 --dry-run
  py sync_transfer_history.py --limit 20 --apply

Convención MVP:
  - permanent / free: cierra spell club origen, abre destino
  - loan: un solo spell club abierto en destino con role=loan + on_loan_from
  - end_of_contract / to_team NULL: cierra spell abierto, cache NULL
  - related_history_id apunta al spell destino creado (si aplica)
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import date

from api_football_import import connect


CLUB_OPEN = """
SELECT h.id, h.team_id, h.role::text AS role
FROM player_team_history h
JOIN team t ON t.id = h.team_id
WHERE h.player_id = %s AND h.end_date IS NULL AND t.team_kind = 'club'
ORDER BY h.start_date DESC
"""


def close_open_club(cur, player_id, end_date: date, *, except_team_id=None) -> list[str]:
    closed = []
    cur.execute(CLUB_OPEN, (player_id,))
    for row in cur.fetchall():
        if except_team_id and str(row["team_id"]) == str(except_team_id):
            continue
        cur.execute(
            """
            UPDATE player_team_history
            SET end_date = %s, updated_at = now()
            WHERE id = %s AND end_date IS NULL
            """,
            (end_date, row["id"]),
        )
        closed.append(str(row["id"]))
    return closed


def open_spell(cur, *, player_id, team_id, role: str, start: date, on_loan_from=None) -> str:
    hid = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO player_team_history (
          id, player_id, team_id, role, start_date, end_date, on_loan_from_team_id
        ) VALUES (
          %s, %s, %s, %s::history_role, %s, NULL, %s
        )
        """,
        (hid, player_id, team_id, role, start, on_loan_from),
    )
    return hid


def set_cache(cur, player_id, team_id):
    cur.execute(
        """
        UPDATE player
        SET current_team_id = %s, updated_at = now()
        WHERE id = %s
        """,
        (team_id, player_id),
    )


def apply_one(cur, tr: dict, *, dry: bool) -> str:
    pid = tr["player_id"]
    eff = tr["effective_date"]
    if not eff:
        return "skip:sin_fecha"
    ttype = tr["transfer_type"]
    to_id = tr["to_team_id"]
    from_id = tr["from_team_id"]

    if dry:
        return f"dry:{ttype}:from={from_id}:to={to_id}"

    if ttype in ("permanent", "free", "unknown") and to_id:
        close_open_club(cur, pid, eff)
        hid = open_spell(cur, player_id=pid, team_id=to_id, role="permanent", start=eff)
        set_cache(cur, pid, to_id)
        cur.execute(
            "UPDATE transfer SET related_history_id = %s WHERE id = %s",
            (hid, tr["id"]),
        )
        return f"ok:arrive:{hid}"

    if ttype == "loan" and to_id and from_id:
        close_open_club(cur, pid, eff)
        hid = open_spell(
            cur,
            player_id=pid,
            team_id=to_id,
            role="loan",
            start=eff,
            on_loan_from=from_id,
        )
        set_cache(cur, pid, to_id)
        cur.execute(
            "UPDATE transfer SET related_history_id = %s WHERE id = %s",
            (hid, tr["id"]),
        )
        return f"ok:loan:{hid}"

    if ttype in ("end_of_contract", "free") and not to_id:
        close_open_club(cur, pid, eff)
        set_cache(cur, pid, None)
        return "ok:free_agent"

    if ttype == "loan_end" and to_id:
        # cierra cesión abierta y reabre dueño
        close_open_club(cur, pid, eff)
        hid = open_spell(cur, player_id=pid, team_id=to_id, role="permanent", start=eff)
        set_cache(cur, pid, to_id)
        cur.execute(
            "UPDATE transfer SET related_history_id = %s WHERE id = %s",
            (hid, tr["id"]),
        )
        return f"ok:loan_end:{hid}"

    return f"skip:tipo={ttype}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.dry_run == args.apply:
        print("Usa exactamente uno: --dry-run o --apply")
        return 2
    if not os.environ.get("PGPASSWORD"):
        print("Falta PGPASSWORD")
        return 2

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, player_id, from_team_id, to_team_id,
                       transfer_type::text AS transfer_type, effective_date
                FROM transfer
                WHERE related_history_id IS NULL
                ORDER BY effective_date NULLS LAST, created_at
                LIMIT %s
                """,
                (args.limit,),
            )
            rows = cur.fetchall()
            print(f"Transfers sin related_history_id: {len(rows)}")
            for tr in rows:
                msg = apply_one(cur, tr, dry=args.dry_run)
                print(f"  {tr['id']}: {msg}")
            if args.apply:
                conn.commit()
                print("Commit OK")
            else:
                conn.rollback()
                print("Dry-run: rollback")
    return 0


if __name__ == "__main__":
    sys.exit(main())
