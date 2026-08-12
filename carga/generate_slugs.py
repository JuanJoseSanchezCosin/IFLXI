#!/usr/bin/env python3
"""
IFLXI — Genera SLUG SEO (entidad 14) desde nombres en BD.

Seguro durante fill: solo LECTURA de player/team/competition + ESCRITURA en tabla `slug`
(no toca .api_football_map.json ni .import_map.json).

Uso:
  py generate_slugs.py --entity player --limit 20 --dry-run
  py generate_slugs.py --entity team --limit 50 --apply
  py generate_slugs.py --entity competition --apply
  py generate_slugs.py --entity all --limit 100 --dry-run

Reglas MVP:
  - locale por defecto: es
  - slug =~ ^[a-z0-9]+(?:-[a-z0-9]+)*$
  - un primary por (entity_type, entity_id, locale)
  - no inventa entidades nuevas
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
import uuid

from api_football_import import connect


def to_slug(text: str, *, fallback: str = "item") -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = raw.lower()
    raw = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    raw = re.sub(r"-{2,}", "-", raw)
    return raw[:80] or fallback


def unique_slug(cur, locale: str, base: str) -> str:
    candidate = base
    n = 2
    while True:
        cur.execute(
            "SELECT 1 FROM slug WHERE locale = %s AND slug = %s LIMIT 1",
            (locale, candidate),
        )
        if not cur.fetchone():
            return candidate
        candidate = f"{base}-{n}"
        n += 1
        if n > 5000:
            return f"{base}-{uuid.uuid4().hex[:8]}"


def entities(kind: str, limit: int) -> list[tuple[str, str, str]]:
    """→ [(entity_type, entity_id, name)]"""
    out: list[tuple[str, str, str]] = []
    with connect() as conn:
        with conn.cursor() as cur:
            if kind in ("player", "all"):
                cur.execute(
                    """
                    SELECT p.id::text, per.display_name
                    FROM player p
                    JOIN person per ON per.id = p.person_id
                    WHERE NOT EXISTS (
                      SELECT 1 FROM slug s
                      WHERE s.entity_type = 'player'
                        AND s.entity_id = p.id
                        AND s.locale = 'es'
                        AND s.is_primary
                    )
                    ORDER BY per.display_name
                    LIMIT %s
                    """,
                    (limit,),
                )
                out.extend(("player", r["id"], r["display_name"]) for r in cur.fetchall())
            if kind in ("team", "all"):
                cur.execute(
                    """
                    SELECT t.id::text, t.name_default
                    FROM team t
                    WHERE t.team_kind = 'club'
                      AND NOT EXISTS (
                        SELECT 1 FROM slug s
                        WHERE s.entity_type = 'team'
                          AND s.entity_id = t.id
                          AND s.locale = 'es'
                          AND s.is_primary
                      )
                    ORDER BY t.name_default
                    LIMIT %s
                    """,
                    (limit,),
                )
                out.extend(("team", r["id"], r["name_default"]) for r in cur.fetchall())
            if kind in ("competition", "all"):
                cur.execute(
                    """
                    SELECT c.id::text, c.name_default
                    FROM competition c
                    WHERE NOT EXISTS (
                      SELECT 1 FROM slug s
                      WHERE s.entity_type = 'competition'
                        AND s.entity_id = c.id
                        AND s.locale = 'es'
                        AND s.is_primary
                    )
                    ORDER BY c.name_default
                    LIMIT %s
                    """,
                    (limit,),
                )
                out.extend(("competition", r["id"], r["name_default"]) for r in cur.fetchall())
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera SLUG SEO IFLXI")
    ap.add_argument("--entity", choices=("player", "team", "competition", "all"), default="player")
    ap.add_argument("--locale", default="es")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.dry_run == args.apply:
        print("Usa exactamente uno: --dry-run o --apply")
        return 2
    if not os.environ.get("PGPASSWORD"):
        print("Falta PGPASSWORD")
        return 2

    rows = entities(args.entity, args.limit)
    print(f"Pendientes ({args.entity}): {len(rows)}")
    planned = []
    with connect() as conn:
        with conn.cursor() as cur:
            for etype, eid, name in rows:
                base = to_slug(name, fallback=etype)
                slug = unique_slug(cur, args.locale, base) if args.apply else base
                # en dry-run no reservamos; puede colisionar en preview
                planned.append((etype, eid, name, slug))
                print(f"  [{etype}] {name} → /{etype}/{slug}")

            if args.apply and planned:
                for etype, eid, name, slug in planned:
                    # re-unique under lock of this transaction
                    slug = unique_slug(cur, args.locale, to_slug(name, fallback=etype))
                    cur.execute(
                        """
                        INSERT INTO slug (
                          id, entity_type, entity_id, locale, slug, is_primary, is_active
                        ) VALUES (
                          %s, %s::slug_entity_type, %s::uuid, %s, %s, TRUE, TRUE
                        )
                        ON CONFLICT DO NOTHING
                        """,
                        (str(uuid.uuid4()), etype, eid, args.locale, slug),
                    )
                conn.commit()
                print(f"Aplicados: {len(planned)}")
            else:
                print("Dry-run: 0 escrituras.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
