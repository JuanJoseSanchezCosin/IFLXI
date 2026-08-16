#!/usr/bin/env python3
"""
IFLXI — Rellena team.api_football_id y player.api_football_id a partir de
los mapas locales ya existentes (.api_football_map.json + .import_map.json),
sin llamar a la API — es instantáneo y no gasta cuota.

Cadena de resolución: api_id (numérico de API-Football)
                       -> código interno (en .api_football_map.json)
                       -> UUID de IFLXI (en .import_map.json)

Uso:
  py fill_api_football_ids.py --dry-run
  py fill_api_football_ids.py --apply

Variables de entorno (igual que el resto del pipeline):
  PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent
API_MAP_PATH = ROOT / ".api_football_map.json"
UUID_MAP_PATH = ROOT / ".import_map.json"


def connect():
    password = os.environ.get("PGPASSWORD")
    if not password:
        raise RuntimeError("Falta PGPASSWORD")
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        user=os.environ.get("PGUSER", "postgres"),
        password=password,
        dbname=os.environ.get("PGDATABASE", "iflxi"),
        row_factory=dict_row,
    )


def build_uuid_to_apiid(entity: str, api_map: dict, uuid_map: dict) -> dict[str, int]:
    """api_id -> código (api_map) + código -> uuid (uuid_map) => uuid -> api_id."""
    code_to_apiid: dict[str, int] = {}
    for api_id, code in api_map.get(entity, {}).items():
        try:
            code_to_apiid[code] = int(api_id)
        except (TypeError, ValueError):
            continue
    result: dict[str, int] = {}
    for code, uuid_str in uuid_map.get(entity, {}).items():
        if code in code_to_apiid:
            result[uuid_str] = code_to_apiid[code]
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.dry_run == args.apply:
        print("Usa exactamente una opción: --dry-run  o  --apply")
        sys.exit(2)

    if not API_MAP_PATH.exists() or not UUID_MAP_PATH.exists():
        print(f"ERROR: faltan {API_MAP_PATH.name} o {UUID_MAP_PATH.name} en esta carpeta.")
        sys.exit(1)

    api_map = json.loads(API_MAP_PATH.read_text(encoding="utf-8"))
    uuid_map = json.loads(UUID_MAP_PATH.read_text(encoding="utf-8"))

    team_pairs = build_uuid_to_apiid("team", api_map, uuid_map)
    player_pairs = build_uuid_to_apiid("player", api_map, uuid_map)
    competition_pairs = build_uuid_to_apiid("competition", api_map, uuid_map)

    print(f"Equipos con api_football_id resuelto: {len(team_pairs)}")
    print(f"Jugadores con api_football_id resuelto: {len(player_pairs)}")
    print(f"Competiciones con api_football_id resuelto: {len(competition_pairs)}")

    if args.dry_run:
        sample_t = list(team_pairs.items())[:5]
        sample_p = list(player_pairs.items())[:5]
        sample_c = list(competition_pairs.items())[:5]
        print("Ejemplo equipos:", sample_t)
        print("Ejemplo jugadores:", sample_p)
        print("Ejemplo competiciones:", sample_c)
        print("\nDRY-RUN OK — no se escribió nada en PostgreSQL.")
        return

    with connect() as conn:
        with conn.cursor() as cur:
            # Tabla temporal + COPY (carga masiva) en vez de un UPDATE por fila:
            # sobre una conexión remota (Supabase), un UPDATE por fila son miles
            # de idas y vueltas por red; con COPY es una sola subida en bloque.
            cur.execute(
                "CREATE TEMP TABLE tmp_team_ids (id UUID, api_football_id INTEGER)"
            )
            with cur.copy("COPY tmp_team_ids (id, api_football_id) FROM STDIN") as copy:
                for uuid_str, api_id in team_pairs.items():
                    copy.write_row((uuid_str, api_id))
            cur.execute(
                """
                UPDATE team SET api_football_id = tmp.api_football_id
                FROM tmp_team_ids tmp
                WHERE team.id = tmp.id
                """
            )
            applied_t = cur.rowcount

            cur.execute(
                "CREATE TEMP TABLE tmp_player_ids (id UUID, api_football_id INTEGER)"
            )
            with cur.copy("COPY tmp_player_ids (id, api_football_id) FROM STDIN") as copy:
                for uuid_str, api_id in player_pairs.items():
                    copy.write_row((uuid_str, api_id))
            cur.execute(
                """
                UPDATE player SET api_football_id = tmp.api_football_id
                FROM tmp_player_ids tmp
                WHERE player.id = tmp.id
                """
            )
            applied_p = cur.rowcount
            conn.commit()

            cur.execute(
                "CREATE TEMP TABLE tmp_comp_ids (id UUID, api_football_id INTEGER)"
            )
            with cur.copy("COPY tmp_comp_ids (id, api_football_id) FROM STDIN") as copy:
                for uuid_str, api_id in competition_pairs.items():
                    copy.write_row((uuid_str, api_id))
            cur.execute(
                """
                UPDATE competition SET api_football_id = tmp.api_football_id
                FROM tmp_comp_ids tmp
                WHERE competition.id = tmp.id
                """
            )
            applied_c = cur.rowcount
            conn.commit()

    print(f"\nAPPLY OK — equipos actualizados: {applied_t}, jugadores actualizados: {applied_p}, competiciones actualizadas: {applied_c}")


if __name__ == "__main__":
    main()
