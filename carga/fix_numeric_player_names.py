#!/usr/bin/env python3
"""
IFLXI — Arregla jugadores cuyo full_name se guardó como el ID numérico de
API-Football (fallo puntual de la carga original, cuando la API no traía
nombre y el script usó el ID como último recurso).

Vuelve a pedir esos jugadores concretos a la API (uno por uno, son pocos)
y actualiza person.full_name / display_name con el nombre real.

Uso:
  py fix_numeric_player_names.py --dry-run
  py fix_numeric_player_names.py --apply

Variables de entorno (igual que el resto del pipeline):
  API_FOOTBALL_KEY, PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
"""

from __future__ import annotations

import argparse
import os
import sys

from api_football_import import ApiError, api_get, connect


def find_numeric_named_players(cur) -> list[dict]:
    cur.execute(
        """
        SELECT p.id AS player_id, per.id AS person_id, per.full_name, p.api_football_id
        FROM player p
        JOIN person per ON per.id = p.person_id
        WHERE per.full_name ~ '^[0-9]+$'
        ORDER BY per.full_name
        """
    )
    return cur.fetchall()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.dry_run == args.apply:
        print("Usa exactamente una opción: --dry-run  o  --apply")
        sys.exit(2)

    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise SystemExit("Falta API_FOOTBALL_KEY")

    with connect() as conn:
        with conn.cursor() as cur:
            rows = find_numeric_named_players(cur)

    print(f"Jugadores con nombre numérico encontrados: {len(rows)}")
    if not rows:
        return

    counters = {"used": 0, "soft_limit": 200, "remaining_header": None}
    fixes: list[tuple[str, str, str]] = []  # (person_id, nombre_viejo, nombre_nuevo)
    sin_resolver: list[str] = []

    for row in rows:
        api_id = row["api_football_id"]
        old_name = row["full_name"]
        if not api_id:
            sin_resolver.append(old_name)
            print(f"  {old_name}: sin api_football_id, no se puede consultar → se deja igual")
            continue
        try:
            data = api_get("/players", {"id": api_id, "season": 2026}, key, counters)
            items = data.get("response") or []
            if not items:
                # Puede que en la temporada nueva aún no tenga stats; probamos la anterior.
                data = api_get("/players", {"id": api_id, "season": 2025}, key, counters)
                items = data.get("response") or []
        except ApiError as e:
            sin_resolver.append(old_name)
            print(f"  {old_name} (id {api_id}): error de API ({e}) → se deja igual")
            continue
        if not items:
            sin_resolver.append(old_name)
            print(f"  {old_name} (id {api_id}): la API no devolvió datos → se deja igual")
            continue
        info = items[0].get("player") or {}
        new_name = (info.get("name") or "").strip()
        if not new_name or new_name.isdigit():
            first = (info.get("firstname") or "").strip()
            last = (info.get("lastname") or "").strip()
            new_name = f"{first} {last}".strip()
        if not new_name or new_name.isdigit():
            sin_resolver.append(old_name)
            print(f"  {old_name} (id {api_id}): la API tampoco trae nombre real → se deja igual")
            continue
        fixes.append((row["person_id"], old_name, new_name))
        print(f"  {old_name} (id {api_id}) → {new_name}")

    print(f"\nArreglables: {len(fixes)}  |  Sin resolver: {len(sin_resolver)}")
    print(f"Requests usados: {counters['used']}")

    if args.dry_run:
        print("\nDRY-RUN OK — no se escribió nada en PostgreSQL.")
        return

    if not fixes:
        print("\nAPPLY: nada que arreglar.")
        return

    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                applied = 0
                for person_id, old_name, new_name in fixes:
                    try:
                        with conn.transaction():
                            cur.execute(
                                "UPDATE person SET full_name = %s, display_name = %s WHERE id = %s",
                                (new_name, new_name, person_id),
                            )
                        applied += 1
                    except Exception as exc:
                        print(f"  WARN: {old_name} rechazado ({exc}) → skip")
    print(f"\nAPPLY OK — jugadores corregidos: {applied}")


if __name__ == "__main__":
    main()