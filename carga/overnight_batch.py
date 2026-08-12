# IFLXI overnight batch: fixtures + events (season 2025), no dry-run double.
# Usage (from carga/, with API_FOOTBALL_KEY and PGPASSWORD set):
#   py overnight_batch.py
#   py overnight_batch.py --skip-fixtures
# Log: overnight_log.txt

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "overnight_log.txt"

LEAGUES = [
    ("championship", 600),
    ("segunda", 500),
    ("serieb", 400),
    ("bundesliga2", 320),
    ("ligue2", 320),
    ("eredivisie", 320),
    ("ligaportugal", 320),
    ("proleague", 320),
    ("superlig", 320),
    ("premership", 250),
    ("seriea_br", 400),
    ("liga_ar", 500),
    ("mls", 550),
    ("liga_mx", 400),
    ("j1", 400),
    ("saudi_pro", 320),
]


def log(msg: str) -> None:
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def remaining_left() -> int | None:
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        return None
    try:
        req = urllib.request.Request(
            "https://v3.football.api-sports.io/status",
            headers={"x-apisports-key": key},
        )
        raw = urllib.request.urlopen(req, timeout=30).read().decode()
        data = json.loads(raw)
        r = (data.get("response") or {}).get("requests") or {}
        cur = int(r["current"])
        lim = int(r["limit_day"])
        return lim - cur
    except Exception as e:
        log(f"WARN status check failed: {e}")
        return None


def run_py(args: list[str]) -> int:
    cmd = [sys.executable, *args]
    log(f"RUN {' '.join(args)}")
    p = subprocess.run(cmd, cwd=str(ROOT))
    return int(p.returncode)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--min-remaining", type=int, default=400)
    ap.add_argument("--max-requests-per-league", type=int, default=700)
    ap.add_argument(
        "--skip-fixtures",
        action="store_true",
        help="Only events (fixtures already loaded)",
    )
    ap.add_argument(
        "--only",
        default="",
        help="Comma-separated slugs to run (default: all)",
    )
    args = ap.parse_args()

    if not os.environ.get("API_FOOTBALL_KEY"):
        print("Falta API_FOOTBALL_KEY", file=sys.stderr)
        return 2
    if not os.environ.get("PGPASSWORD"):
        print("Falta PGPASSWORD", file=sys.stderr)
        return 2
    os.environ.setdefault("PGDATABASE", "iflxi")

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    leagues = [x for x in LEAGUES if not only or x[0] in only]

    log(
        f"===== OVERNIGHT START season={args.season} "
        f"minRemaining={args.min_remaining} skip_fixtures={args.skip_fixtures} ====="
    )
    left = remaining_left()
    log(f"API remaining left: {left if left is not None else 'unknown'}")

    for slug, limit in leagues:
        left = remaining_left()
        log(f"---- BEFORE {slug} | left={left} ----")
        if left is not None and left < args.min_remaining:
            log(f"STOP: remaining={left} < MinRemaining={args.min_remaining}")
            break

        if not args.skip_fixtures:
            log(f"FIXTURES {slug} season={args.season}")
            fx = run_py(
                [
                    "api_football_import.py",
                    "--league",
                    slug,
                    "--season",
                    str(args.season),
                    "--apply",
                    "--with-fixtures",
                    "--limit",
                    "0",
                    "--max-requests",
                    "40",
                ]
            )
            if fx != 0:
                log(f"WARN fixtures {slug} exit={fx} - still trying events")

            left = remaining_left()
            if left is not None and left < args.min_remaining:
                log(f"STOP before events {slug}: remaining={left}")
                break

        log(f"EVENTS {slug} limit={limit} (apply only)")
        ev = run_py(
            [
                "api_football_import_events.py",
                "--league",
                slug,
                "--season",
                str(args.season),
                "--limit",
                str(limit),
                "--apply",
                "--max-requests",
                str(args.max_requests_per_league),
            ]
        )
        if ev != 0:
            log(f"WARN events {slug} exit={ev} - continue")

        left = remaining_left()
        log(f"---- AFTER {slug} | left={left} ----")

    log("===== OVERNIGHT END =====")
    left = remaining_left()
    log(f"Final remaining left: {left if left is not None else 'unknown'}")
    log("Revisa: SELECT COUNT(*) FROM match; SELECT COUNT(*) FROM match_event;")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
