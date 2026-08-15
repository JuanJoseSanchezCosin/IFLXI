#!/usr/bin/env python3
"""
IFLXI — Arregla nombres con codificación corrupta (mojibake).

Problema: algunos nombres en person/team/city/competition quedaron mal
guardados por una doble conversión de codificación (texto UTF-8 original
interpretado como CP850/Latin-1 y reencodeado). Se ven en pantalla como
"H├â┬©jlund" en vez de "Højlund".

Este script prueba una cadena de conversión conocida (cp850 -> utf-8,
luego latin1 -> utf-8) sobre las columnas de texto de cada tabla. Si el
resultado es texto válido y distinto del original, lo marca como
candidato a arreglo. Si la cadena falla (caso más raro / mixto), lo deja
fuera y lo lista aparte para revisión manual — no fuerza un arreglo
a ciegas que podría corromper el nombre aún más.

Uso:
  py fix_encoding.py --dry-run     # solo muestra qué cambiaría
  py fix_encoding.py --apply       # aplica los cambios seguros en BD

Variables de entorno (igual que el resto del pipeline):
  PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
"""

from __future__ import annotations

import argparse
import os
import sys

import psycopg
from psycopg.rows import dict_row

# Tabla -> columnas de texto a revisar
TARGETS = {
    "person": ["full_name", "display_name", "first_name", "last_name"],
    "team": ["name_default", "short_name"],
    "city": ["name_default"],
    "competition": ["name_default", "short_name"],
}

# Marcadores típicos de este mojibake concreto (aparecen si el texto
# está corrupto). Si ninguno aparece, la fila no se toca.
MARKERS = ["Ã", "Â"]


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


def looks_corrupted(text: str | None) -> bool:
    if not text:
        return False
    return any(m in text for m in MARKERS)


def try_fix(text: str) -> str | None:
    """Devuelve el texto arreglado si la cadena de conversión funciona
    limpiamente y el resultado ya no contiene marcadores de corrupción.
    Devuelve None si no se puede arreglar con confianza."""
    try:
        fixed = text.encode("latin1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return None
    if looks_corrupted(fixed):
        return None
    if fixed == text:
        return None
    return fixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.dry_run == args.apply:
        print("Usa exactamente una opción: --dry-run  o  --apply")
        sys.exit(2)

    fixable = []   # (tabla, id, columna, antes, después)
    manual = []    # (tabla, id, columna, antes) — no se pudo arreglar con confianza

    with connect() as conn:
        with conn.cursor() as cur:
            for table, columns in TARGETS.items():
                for col in columns:
                    cur.execute(
                        f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL"
                    )
                    for row in cur.fetchall():
                        original = row[col]
                        if not looks_corrupted(original):
                            continue
                        fixed = try_fix(original)
                        if fixed:
                            fixable.append((table, row["id"], col, original, fixed))
                        else:
                            manual.append((table, row["id"], col, original))

    print(f"Arreglables automáticamente: {len(fixable)}")
    print(f"Necesitan revisión manual (patrón distinto): {len(manual)}")
    print()

    print("--- Ejemplos de arreglo (primeros 20) ---")
    for table, rid, col, before, after in fixable[:20]:
        print(f"  [{table}.{col}] {before!r} -> {after!r}")

    if manual:
        print("\n--- Necesitan revisión manual (primeros 20) ---")
        for table, rid, col, before in manual[:20]:
            print(f"  [{table}.{col}] id={rid} {before!r}")

    if args.dry_run:
        print("\nDRY-RUN OK — no se escribió nada en PostgreSQL.")
        return

    if not fixable:
        print("\nAPPLY: nada que arreglar.")
        return

    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                applied = 0
                for table, rid, col, before, after in fixable:
                    try:
                        with conn.transaction():
                            cur.execute(
                                f"UPDATE {table} SET {col} = %s, updated_at = now() WHERE id = %s",
                                (after, rid),
                            )
                        applied += 1
                    except Exception as exc:
                        print(f"  WARN: fila {table}.{rid} rechazada ({exc}) → skip")
    print(f"\nAPPLY OK — filas corregidas: {applied}")
    print(f"Filas para revisión manual (sin tocar): {len(manual)}")


if __name__ == "__main__":
    main()