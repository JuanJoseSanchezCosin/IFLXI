#!/usr/bin/env python3
"""
IFLXI — Servidor local: web estática + API sobre PostgreSQL.

Uso (PowerShell):
  $env:PGPASSWORD = "TU_PASSWORD"
  $env:PGDATABASE = "iflxi"
  py -m pip install "fastapi" "uvicorn[standard]" "psycopg[binary]"
  py server.py

Abre: http://127.0.0.1:8787
"""

from __future__ import annotations

import io
import json
import os
import uuid as uuid_lib
from datetime import date
from pathlib import Path

import psycopg
import requests
from PIL import Image
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Query, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent

POS_META = {
    "GK": ("Portero", "PT", {"ritmo": 45, "tiro": 30, "pase": 55, "regate": 40, "defensa": 88, "fisico": 72}),
    "CB": ("Defensa central", "DF", {"ritmo": 62, "tiro": 40, "pase": 68, "regate": 55, "defensa": 86, "fisico": 84}),
    "CM": ("Centrocampista", "MC", {"ritmo": 72, "tiro": 68, "pase": 84, "regate": 78, "defensa": 70, "fisico": 76}),
    "ST": ("Delantero", "DL", {"ritmo": 84, "tiro": 86, "pase": 70, "regate": 82, "defensa": 38, "fisico": 78}),
}

# Clubes "wow" para portada
FEATURED_CLUBS = (
    "Real Madrid",
    "Barcelona",
    "Atletico Madrid",
    "Manchester City",
    "Manchester United",
    "Liverpool",
    "Arsenal",
    "Chelsea",
    "Tottenham",
    "Bayern München",
    "Borussia Dortmund",
    "Inter",
    "Juventus",
    "AC Milan",
    "Napoli",
    "Paris Saint Germain",
    "Olympique Marseille",
    "AS Monaco",
)


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


def age_from_birth(b: date | None) -> int | None:
    if not b:
        return None
    today = date.today()
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))


def colors_from_text(text: str) -> dict:
    h = 0
    for ch in text:
        h = (h * 31 + ord(ch)) % 360
    return {"c1": f"hsl({h} 55% 26%)", "c2": f"hsl({(h + 40) % 360} 60% 12%)"}


def compute_club_lab(squad: list[dict]) -> dict:
    """Radiografía honesta de plantilla — sin inventar mercado ni rating FIFA."""
    n = len(squad)
    ages = [p["age"] for p in squad if isinstance(p.get("age"), (int, float))]
    nations: dict[str, int] = {}
    lines = {"PT": 0, "DF": 0, "MC": 0, "DL": 0, "?": 0}
    line_players: dict[str, list] = {"PT": [], "DF": [], "MC": [], "DL": []}

    for p in squad:
        nat = p.get("nationality") or "—"
        if nat and nat != "—":
            nations[nat] = nations.get(nat, 0) + 1
        line = p.get("pos") or "?"
        if line not in lines:
            line = "?"
        lines[line] = lines.get(line, 0) + 1
        if line in line_players:
            line_players[line].append(
                {"id": p["id"], "name": p["name"], "age": p.get("age"), "pos": p.get("pos")}
            )

    buckets = [
        {"key": "U21", "label": "Sub-21", "min": 0, "max": 20, "count": 0},
        {"key": "21-24", "label": "21–24", "min": 21, "max": 24, "count": 0},
        {"key": "25-28", "label": "25–28", "min": 25, "max": 28, "count": 0},
        {"key": "29-32", "label": "29–32", "min": 29, "max": 32, "count": 0},
        {"key": "33+", "label": "33+", "min": 33, "max": 99, "count": 0},
    ]
    for a in ages:
        ai = int(a)
        for b in buckets:
            if b["min"] <= ai <= b["max"]:
                b["count"] += 1
                break

    avg_age = round(sum(ages) / len(ages), 1) if ages else None
    young = sum(1 for a in ages if a <= 23)
    veterans = sum(1 for a in ages if a >= 30)
    known_nat = sum(nations.values())
    known_pos = n - lines.get("?", 0)

    # Lab Score 0–100: profundidad + equilibrio + juventud + cobertura de datos
    depth = min(1.0, n / 25) * 28
    balanced = 0.0
    if n:
        ideal = {"PT": 0.12, "DF": 0.32, "MC": 0.32, "DL": 0.24}
        balanced = 22 * (
            1
            - sum(abs((lines.get(k, 0) / n) - ideal[k]) for k in ideal) / 2
        )
        balanced = max(0.0, balanced)
    youth = (young / len(ages) * 25) if ages else 10
    coverage = (
        (len(ages) / n) * 12 + (known_nat / n) * 8 + (known_pos / n) * 5
        if n
        else 0
    )
    score = int(round(min(100, max(0, depth + balanced + youth + coverage))))

    nation_list = sorted(
        [{"name": k, "count": v, "pct": round(100 * v / n, 1) if n else 0} for k, v in nations.items()],
        key=lambda x: (-x["count"], x["name"]),
    )[:12]

    insights: list[str] = []
    if n == 0:
        insights.append("Plantilla aún no sincronizada en IFLXI.")
    else:
        insights.append(f"{n} jugadores con vínculo abierto en la base.")
        if avg_age is not None:
            insights.append(f"Edad media real: {avg_age} años ({len(ages)}/{n} con fecha/edad).")
        else:
            insights.append("Edades pendientes de enriquecer (las nuevas sync ya las traen).")
        if young and ages:
            insights.append(f"{young} perfiles ≤23 — foco cantera / proyección.")
        if veterans and ages:
            insights.append(f"{veterans} veteranos (≥30) — experiencia en vestuario.")
        if nation_list:
            top = nation_list[0]
            insights.append(f"Nación dominante: {top['name']} ({top['count']}).")
        else:
            insights.append("Nacionalidades aún no cubiertas en esta ola de plantillas.")
        insights.append("Sin valor de mercado inventado: solo datos verificables.")

    # Once tipo: hasta 1 PT, 4 DF, 3 MC, 3 DL
    xi = []
    for key, take in (("PT", 1), ("DF", 4), ("MC", 3), ("DL", 3)):
        pool = sorted(
            line_players[key],
            key=lambda x: (x["age"] is None, x["age"] or 99, x["name"]),
        )
        xi.extend(pool[:take])

    return {
        "score": score,
        "squadSize": n,
        "avgAge": avg_age,
        "agesKnown": len(ages),
        "youngCount": young,
        "veteranCount": veterans,
        "ageBuckets": [{"key": b["key"], "label": b["label"], "count": b["count"]} for b in buckets],
        "lines": {k: lines.get(k, 0) for k in ("PT", "DF", "MC", "DL")},
        "nations": nation_list,
        "insights": insights,
        "xi": xi,
        "pitch": {
            "PT": line_players["PT"][:5],
            "DF": line_players["DF"][:8],
            "MC": line_players["MC"][:8],
            "DL": line_players["DL"][:8],
        },
        "honesty": {
            "marketValues": False,
            "note": "Radiografía Lab: composición real de plantilla. Valores Transfermarkt = aún no.",
        },
    }


def team_logo_url(api_football_id: int | None) -> str | None:
    """Escudo real vía CDN de API-Football, a partir del ID que guardamos
    en team.api_football_id (sin llamar a la API, es una URL pública fija)."""
    if not api_football_id:
        return None
    return f"https://media.api-sports.io/football/teams/{api_football_id}.png"


def player_photo_url(api_football_id: int | None) -> str | None:
    """Foto real vía CDN de API-Football, a partir de player.api_football_id."""
    if not api_football_id:
        return None
    return f"https://media.api-sports.io/football/players/{api_football_id}.png"


def league_logo_url(api_football_id: int | None) -> str | None:
    """Logo real de la liga vía CDN de API-Football, a partir de
    competition.api_football_id."""
    if not api_football_id:
        return None
    return f"https://media.api-sports.io/football/leagues/{api_football_id}.png"


def club_payload(row: dict | None) -> dict:
    if not row:
        return {
            "id": "unknown",
            "name": "Sin club",
            "short": "—",
            "league": "—",
            "country": "—",
            "logo": None,
            **colors_from_text("x"),
        }
    name = row.get("team_name") or row.get("name_default") or "Club"
    code = (row.get("team_code") or row.get("code") or name[:3]).upper()[:3]
    cols = colors_from_text(name)
    return {
        "id": str(row.get("team_id") or row.get("id")),
        "name": name,
        "short": code,
        "league": row.get("competition_name") or "—",
        "country": row.get("country_name") or "—",
        "logo": team_logo_url(row.get("team_api_football_id") or row.get("api_football_id")),
        **cols,
    }


def player_payload(row: dict) -> dict:
    """Solo datos reales de BD. Sin inventar edad ni valor de mercado."""
    pos = row.get("primary_position") or "CM"
    label, short, _demo_attrs = POS_META.get(pos, POS_META["CM"])
    birth = row.get("birth_date")
    age = age_from_birth(birth)
    # age_hint solo si viene de un import que lo guardó (no inventar 24)
    if age is None and row.get("age_hint") not in (None, ""):
        try:
            age = int(row["age_hint"])
        except (TypeError, ValueError):
            age = None

    club = club_payload(row)
    name = row.get("display_name") or row.get("full_name") or "Jugador"
    pid = str(row["player_id"])

    # Valor: solo si existe market_value_history (en millones EUR para la UI)
    value = None
    value_history: list = []
    raw_val = row.get("market_value_amount")
    if raw_val is not None:
        try:
            euros = float(raw_val)
            value = round(euros / 1_000_000, 2) if euros >= 1000 else round(euros, 2)
            value_history = [[date.today().year, value]]
        except (TypeError, ValueError):
            value = None

    birth_str = birth.strftime("%d/%m/%Y") if birth else "—"
    height = row.get("height_cm")
    foot_raw = row.get("foot")
    foot = str(foot_raw) if foot_raw not in (None, "") else "—"

    return {
        "id": pid,
        "name": name,
        "photo": player_photo_url(row.get("player_api_football_id")),
        "shirt": row.get("shirt_number") if row.get("shirt_number") is not None else "—",
        "age": age,  # null si desconocida
        "birth": birth_str,
        "nationality": row.get("nationality") or "—",
        "flag": "",
        "position": label,
        "pos": short,
        "club": club["id"],
        "clubInfo": club,
        "contract": "—",  # sin entidad CONTRACT en MVP
        "height": height if height else "—",
        "foot": foot,
        "value": value,  # null = aún no hay fuente de mercado en BD
        "stats": {"matches": 0, "goals": 0, "assists": 0, "minutes": 0},
        # Sin attrs inventados: la UI no debe mostrar "Rating IA" falso
        "attrs": None,
        "valueHistory": value_history,
        "career": [
            {
                "club": club["name"],
                "from": 2025,
                "to": None,
                "apps": 0,
                "goals": 0,
            }
        ],
        "live": True,
        "dataQuality": {
            "hasBirth": birth is not None,
            "hasMarketValue": value is not None,
            "hasNationality": bool(row.get("nationality")),
            "source": "squads/import — sin valores Transfermarkt todavía",
        },
    }


app = FastAPI(title="IFLXI API", version="0.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"ok": True, "db": "iflxi", "mode": "live"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/stats")
def stats():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM player) AS players,
                  (SELECT COUNT(*) FROM team) AS teams,
                  (SELECT COUNT(*) FROM competition) AS leagues,
                  (SELECT COUNT(*) FROM country) AS countries,
                  (SELECT COUNT(*) FROM player_team_history WHERE end_date IS NULL) AS open_histories,
                  (SELECT COUNT(*) FROM match) AS matches,
                  (SELECT COUNT(*) FROM match_event) AS match_events
                """
            )
            row = cur.fetchone()
    return {
        "players": int(row["players"]),
        "teams": int(row["teams"]),
        "leagues": int(row["leagues"]),
        "countries": int(row["countries"]),
        "openHistories": int(row["open_histories"]),
        "matches": int(row["matches"]),
        "matchEvents": int(row["match_events"]),
        "marketValue": 0,
        "live": True,
    }


PLAYER_SELECT = """
SELECT
  p.id AS player_id,
  p.api_football_id AS player_api_football_id,
  per.full_name,
  per.display_name,
  per.birth_date,
  p.primary_position,
  p.foot::text AS foot,
  p.height_cm,
  p.weight_kg,
  p.shirt_name,
  nat.name_default AS nationality,
  t.id AS team_id,
  t.name_default AS team_name,
  t.code AS team_code,
  t.api_football_id AS team_api_football_id,
  ctry.name_default AS country_name,
  (
    SELECT c.name_default
    FROM team_competition tc
    JOIN season s ON s.id = tc.season_id
    JOIN competition c ON c.id = s.competition_id
    WHERE tc.team_id = t.id
    ORDER BY s.is_current DESC, s.year_start DESC
    LIMIT 1
  ) AS competition_name,
  (
    SELECT mv.value_amount
    FROM market_value_history mv
    WHERE mv.player_id = p.id
    ORDER BY mv.recorded_on DESC
    LIMIT 1
  ) AS market_value_amount
FROM player p
JOIN person per ON per.id = p.person_id
LEFT JOIN country nat ON nat.id = p.nationality_country_id
LEFT JOIN team t ON t.id = p.current_team_id
LEFT JOIN country ctry ON ctry.id = t.country_id
"""


@app.get("/api/players")
def list_players(
    limit: int = Query(12, ge=1, le=60),
    max_age: int | None = Query(None, alias="maxAge"),
    sort: str = "featured",
    club: str | None = None,
):
    with connect() as conn:
        with conn.cursor() as cur:
            if sort == "featured" and not club:
                cur.execute(
                    PLAYER_SELECT
                    + """
                    WHERE t.name_default = ANY(%s)
                    ORDER BY t.name_default, per.display_name
                    LIMIT %s
                    """,
                    (list(FEATURED_CLUBS), limit),
                )
            elif club:
                cur.execute(
                    PLAYER_SELECT + " WHERE t.id::text = %s OR t.name_default ILIKE %s ORDER BY per.display_name LIMIT %s",
                    (club, club, limit),
                )
            else:
                cur.execute(
                    PLAYER_SELECT + " WHERE p.current_team_id IS NOT NULL ORDER BY per.display_name LIMIT %s",
                    (limit,),
                )
            rows = cur.fetchall()

    players = [player_payload(r) for r in rows]
    if max_age is not None:
        players = [
            p for p in players
            if isinstance(p.get("age"), (int, float)) and p["age"] <= max_age
        ]
    if sort == "value":
        players.sort(key=lambda p: p["value"] if isinstance(p.get("value"), (int, float)) else -1, reverse=True)
    if sort == "potential":
        players.sort(
            key=lambda p: (
                (100 - p["age"]) if isinstance(p.get("age"), (int, float)) else 0
            )
            + (p["value"] * 0.1 if isinstance(p.get("value"), (int, float)) else 0),
            reverse=True,
        )
    return players[:limit]


@app.get("/api/players/top-valued")
def players_top_valued(limit: int = Query(50, ge=1, le=200)):
    """
    Ranking estilo Transfermarkt «más valiosos».
    Usa cache current_market_value (fuente = MARKET_VALUE_HISTORY).
    Vacío hasta cargar valores (Excel/manual; API-Football no trae € TM).
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  p.id AS player_id,
                  p.api_football_id AS player_api_football_id,
                  per.display_name AS player_name,
                  p.primary_position,
                  p.current_market_value AS value_amount,
                  p.current_market_value_currency::text AS currency,
                  t.id AS team_id,
                  t.name_default AS team_name,
                  t.api_football_id AS team_api_football_id,
                  nat.name_default AS nationality
                FROM player p
                JOIN person per ON per.id = p.person_id
                LEFT JOIN team t ON t.id = p.current_team_id
                LEFT JOIN country nat ON nat.id = p.nationality_country_id
                WHERE p.current_market_value IS NOT NULL
                  AND p.status = 'active'
                ORDER BY p.current_market_value DESC, per.display_name
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return {
        "items": [
            {
                "playerId": str(r["player_id"]),
                "player": r["player_name"],
                "playerPhoto": player_photo_url(r["player_api_football_id"]),
                "position": r["primary_position"],
                "value": float(r["value_amount"]) if r["value_amount"] is not None else None,
                "currency": r["currency"],
                "teamId": str(r["team_id"]) if r["team_id"] else None,
                "team": r["team_name"],
                "teamLogo": team_logo_url(r["team_api_football_id"]),
                "nationality": r["nationality"],
            }
            for r in rows
        ],
        "source": "player.current_market_value ← market_value_history",
    }


@app.get("/api/players/free-agents")
def players_free_agents(limit: int = Query(50, ge=1, le=200)):
    """Agentes libres (Anexo A.2): sin spell de club abierto ni Free Agent artificial."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  p.id AS player_id,
                  per.display_name AS player_name,
                  p.primary_position,
                  p.current_market_value,
                  p.current_market_value_currency::text AS currency,
                  nat.name_default AS nationality
                FROM player p
                JOIN person per ON per.id = p.person_id
                LEFT JOIN country nat ON nat.id = p.nationality_country_id
                WHERE p.status = 'active'
                  AND p.current_team_id IS NULL
                  AND NOT EXISTS (
                    SELECT 1
                    FROM player_team_history h
                    JOIN team t ON t.id = h.team_id
                    WHERE h.player_id = p.id
                      AND h.end_date IS NULL
                      AND t.team_kind = 'club'
                  )
                ORDER BY p.current_market_value DESC NULLS LAST, per.display_name
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return {
        "items": [
            {
                "playerId": str(r["player_id"]),
                "player": r["player_name"],
                "position": r["primary_position"],
                "value": float(r["current_market_value"])
                if r["current_market_value"] is not None
                else None,
                "currency": r["currency"],
                "nationality": r["nationality"],
            }
            for r in rows
        ],
        "rule": "Anexo A.2",
    }


@app.get("/api/players/{player_id}/market-value-history")
def player_market_value_history(player_id: str):
    """Todo el histórico de valores registrados para un jugador, más antiguo
    primero — para el gráfico/tabla de evolución en su ficha."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT value_amount, currency::text AS currency, recorded_on
                FROM market_value_history
                WHERE player_id = %s
                ORDER BY recorded_on ASC
                """,
                (player_id,),
            )
            rows = cur.fetchall()
    return [
        {
            "value": float(r["value_amount"]),
            "currency": r["currency"],
            "recordedOn": r["recorded_on"].isoformat() if r["recorded_on"] else None,
        }
        for r in rows
    ]


@app.get("/api/players/{player_id}")
def get_player(player_id: str):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(PLAYER_SELECT + " WHERE p.id::text = %s", (player_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Jugador no encontrado")
            # historial de clubes
            cur.execute(
                """
                SELECT t.name_default AS club, h.start_date, h.end_date
                FROM player_team_history h
                JOIN team t ON t.id = h.team_id
                WHERE h.player_id = %s
                ORDER BY h.start_date DESC NULLS LAST
                """,
                (player_id,),
            )
            hist = cur.fetchall()
            # Histórico real de valor (no el punto único fabricado de player_payload)
            cur.execute(
                "SELECT value_amount, recorded_on FROM market_value_history WHERE player_id = %s ORDER BY recorded_on ASC",
                (player_id,),
            )
            value_rows = cur.fetchall()
    payload = player_payload(row)
    if value_rows:
        payload["valueHistory"] = [
            [v["recorded_on"].year, round(float(v["value_amount"]) / 1_000_000, 2)]
            for v in value_rows
        ]
    if hist:
        payload["career"] = [
            {
                "club": h["club"],
                "from": h["start_date"].year if h["start_date"] else 2025,
                "to": h["end_date"].year if h["end_date"] else None,
                "apps": 0,
                "goals": 0,
            }
            for h in hist
        ]
    return payload


@app.get("/api/players/{player_id}/stats")
def player_event_stats(player_id: str):
    """
    Stats derivadas SOLO desde MATCH_EVENT (Transfermarkt-like).
    Vacío = ceros hasta cargar eventos. No inventa ratings.
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM player WHERE id::text = %s", (player_id,))
            if not cur.fetchone():
                raise HTTPException(404, "Jugador no encontrado")
            cur.execute(
                """
                SELECT
                  COALESCE(SUM(CASE WHEN event_type IN ('goal', 'penalty_goal')
                                    AND player_id::text = %s THEN 1 ELSE 0 END), 0) AS goals,
                  COALESCE(SUM(CASE WHEN event_type IN ('goal', 'penalty_goal')
                                    AND secondary_player_id::text = %s THEN 1 ELSE 0 END), 0) AS assists,
                  COALESCE(SUM(CASE WHEN event_type = 'own_goal'
                                    AND player_id::text = %s THEN 1 ELSE 0 END), 0) AS own_goals,
                  COALESCE(SUM(CASE WHEN event_type = 'penalty_miss'
                                    AND player_id::text = %s THEN 1 ELSE 0 END), 0) AS penalty_misses,
                  COALESCE(SUM(CASE WHEN event_type = 'yellow_card'
                                    AND player_id::text = %s THEN 1 ELSE 0 END), 0) AS yellow_cards,
                  COALESCE(SUM(CASE WHEN event_type = 'second_yellow'
                                    AND player_id::text = %s THEN 1 ELSE 0 END), 0) AS second_yellows,
                  COALESCE(SUM(CASE WHEN event_type IN ('red_card', 'second_yellow')
                                    AND player_id::text = %s THEN 1 ELSE 0 END), 0) AS red_cards,
                  COALESCE(SUM(CASE WHEN event_type = 'substitution_out'
                                    AND player_id::text = %s THEN 1 ELSE 0 END), 0) AS subs_out,
                  COALESCE(SUM(CASE WHEN event_type = 'substitution_out'
                                    AND secondary_player_id::text = %s THEN 1 ELSE 0 END), 0) AS subs_in
                FROM match_event
                WHERE player_id::text = %s OR secondary_player_id::text = %s
                """,
                (player_id,) * 11,
            )
            row = cur.fetchone() or {}
    return {
        "playerId": player_id,
        "source": "match_event",
        "goals": int(row.get("goals") or 0),
        "assists": int(row.get("assists") or 0),
        "ownGoals": int(row.get("own_goals") or 0),
        "penaltyMisses": int(row.get("penalty_misses") or 0),
        "yellowCards": int(row.get("yellow_cards") or 0),
        "secondYellows": int(row.get("second_yellows") or 0),
        "redCards": int(row.get("red_cards") or 0),
        "substitutionsOut": int(row.get("subs_out") or 0),
        "substitutionsIn": int(row.get("subs_in") or 0),
        "note": "Asistencias = secondary_player_id en goal/penalty_goal. Sin event_type=assist.",
    }


@app.get("/api/players/{player_id}/transfers")
def player_transfers(player_id: str, limit: int = Query(50, ge=1, le=200)):
    """Historial de fichajes del jugador (estilo TM / Fichajes confirmados)."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM player WHERE id::text = %s", (player_id,))
            if not cur.fetchone():
                raise HTTPException(404, "Jugador no encontrado")
            cur.execute(
                """
                SELECT
                  t.id, t.transfer_type::text AS transfer_type, t.effective_date,
                  t.fee_amount, t.fee_currency::text AS fee_currency,
                  tf.name_default AS from_team, tt.name_default AS to_team
                FROM transfer t
                LEFT JOIN team tf ON tf.id = t.from_team_id
                LEFT JOIN team tt ON tt.id = t.to_team_id
                WHERE t.player_id::text = %s
                ORDER BY t.effective_date DESC NULLS LAST, t.created_at DESC
                LIMIT %s
                """,
                (player_id, limit),
            )
            rows = cur.fetchall()
    return {
        "playerId": player_id,
        "items": [
            {
                "id": str(r["id"]),
                "from": r["from_team"],
                "to": r["to_team"],
                "type": r["transfer_type"],
                "date": r["effective_date"].isoformat() if r["effective_date"] else None,
                "fee": float(r["fee_amount"]) if r["fee_amount"] is not None else None,
                "currency": r["fee_currency"],
            }
            for r in rows
        ],
    }


@app.get("/api/players/{player_id}/market-values")
def player_market_values(player_id: str, limit: int = Query(40, ge=1, le=200)):
    """Serie temporal de valor (MARKET_VALUE_HISTORY) — gráfico TM."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM player WHERE id::text = %s", (player_id,))
            if not cur.fetchone():
                raise HTTPException(404, "Jugador no encontrado")
            cur.execute(
                """
                SELECT value_amount, currency::text AS currency, recorded_on, source
                FROM market_value_history
                WHERE player_id::text = %s
                ORDER BY recorded_on DESC, created_at DESC
                LIMIT %s
                """,
                (player_id, limit),
            )
            rows = cur.fetchall()
    items = [
        {
            "value": float(r["value_amount"]),
            "currency": r["currency"],
            "date": r["recorded_on"].isoformat() if r["recorded_on"] else None,
            "source": r["source"],
        }
        for r in rows
    ]
    items.reverse()  # cronológico ascendente para charts
    return {"playerId": player_id, "items": items}


@app.get("/api/competitions/{competition_id}/top-scorers")
def competition_top_scorers(
    competition_id: str,
    limit: int = Query(20, ge=1, le=50),
):
    """Máximos goleadores de la competición (derivado de MATCH_EVENT)."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.player_id, per.display_name AS player_name, COUNT(*) AS goals
                FROM match_event e
                JOIN match m ON m.id = e.match_id
                JOIN season s ON s.id = m.season_id
                JOIN player p ON p.id = e.player_id
                JOIN person per ON per.id = p.person_id
                WHERE s.competition_id::text = %s
                  AND e.event_type IN ('goal', 'penalty_goal')
                GROUP BY e.player_id, per.display_name
                ORDER BY goals DESC, per.display_name
                LIMIT %s
                """,
                (competition_id, limit),
            )
            rows = cur.fetchall()
    return {
        "competitionId": competition_id,
        "items": [
            {
                "playerId": str(r["player_id"]),
                "player": r["player_name"],
                "goals": int(r["goals"]),
            }
            for r in rows
        ],
    }


@app.get("/api/competitions/{competition_id}/top-assists")
def competition_top_assists(
    competition_id: str,
    limit: int = Query(20, ge=1, le=50),
):
    """Máximos asistentes (secondary_player_id en goal/penalty_goal)."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.secondary_player_id AS player_id,
                       per.display_name AS player_name,
                       COUNT(*) AS assists
                FROM match_event e
                JOIN match m ON m.id = e.match_id
                JOIN season s ON s.id = m.season_id
                JOIN player p ON p.id = e.secondary_player_id
                JOIN person per ON per.id = p.person_id
                WHERE s.competition_id::text = %s
                  AND e.event_type IN ('goal', 'penalty_goal')
                  AND e.secondary_player_id IS NOT NULL
                GROUP BY e.secondary_player_id, per.display_name
                ORDER BY assists DESC, per.display_name
                LIMIT %s
                """,
                (competition_id, limit),
            )
            rows = cur.fetchall()
    return {
        "competitionId": competition_id,
        "items": [
            {
                "playerId": str(r["player_id"]),
                "player": r["player_name"],
                "assists": int(r["assists"]),
            }
            for r in rows
        ],
    }


@app.get("/api/competitions/{competition_id}/standings")
def competition_standings(competition_id: str):
    """Clasificación real, calculada a partir de partidos terminados de la
    temporada actual (o, si no hay ninguna marcada como actual, la más
    reciente) de la competición."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name_default
                FROM season
                WHERE competition_id = %s
                ORDER BY is_current DESC, year_start DESC
                LIMIT 1
                """,
                (competition_id,),
            )
            season_row = cur.fetchone()
            if not season_row:
                return {"season": None, "items": []}

            cur.execute(
                """
                WITH team_matches AS (
                  SELECT m.home_team_id AS team_id, m.home_score AS gf, m.away_score AS ga
                  FROM match m
                  WHERE m.season_id = %(season_id)s AND m.status = 'finished'
                  UNION ALL
                  SELECT m.away_team_id AS team_id, m.away_score AS gf, m.home_score AS ga
                  FROM match m
                  WHERE m.season_id = %(season_id)s AND m.status = 'finished'
                )
                SELECT
                  t.id AS team_id,
                  t.name_default AS team_name,
                  t.api_football_id,
                  COUNT(*) AS played,
                  SUM(CASE WHEN tm.gf > tm.ga THEN 1 ELSE 0 END) AS won,
                  SUM(CASE WHEN tm.gf = tm.ga THEN 1 ELSE 0 END) AS drawn,
                  SUM(CASE WHEN tm.gf < tm.ga THEN 1 ELSE 0 END) AS lost,
                  SUM(tm.gf) AS goals_for,
                  SUM(tm.ga) AS goals_against,
                  SUM(CASE WHEN tm.gf > tm.ga THEN 3 WHEN tm.gf = tm.ga THEN 1 ELSE 0 END) AS points
                FROM team_matches tm
                JOIN team t ON t.id = tm.team_id
                GROUP BY t.id, t.name_default, t.api_football_id
                ORDER BY points DESC, (SUM(tm.gf) - SUM(tm.ga)) DESC, SUM(tm.gf) DESC, t.name_default
                """,
                {"season_id": season_row["id"]},
            )
            rows = cur.fetchall()
    return {
        "season": season_row["name_default"],
        "items": [
            {
                "teamId": str(r["team_id"]),
                "team": r["team_name"],
                "teamLogo": team_logo_url(r["api_football_id"]),
                "played": int(r["played"]),
                "won": int(r["won"]),
                "drawn": int(r["drawn"]),
                "lost": int(r["lost"]),
                "goalsFor": int(r["goals_for"]),
                "goalsAgainst": int(r["goals_against"]),
                "goalDiff": int(r["goals_for"]) - int(r["goals_against"]),
                "points": int(r["points"]),
            }
            for r in rows
        ],
    }


@app.get("/api/competitions/{competition_id}/clean-sheets")
def competition_clean_sheets(competition_id: str, limit: int = Query(20, ge=1, le=50)):
    """Porterías a cero por equipo (partidos terminados de la temporada
    actual en los que el rival no marcó). A nivel de equipo, no de portero
    concreto: no tenemos datos de alineación por partido para saber qué
    portero jugó cada uno."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM season WHERE competition_id = %s ORDER BY is_current DESC, year_start DESC LIMIT 1",
                (competition_id,),
            )
            season_row = cur.fetchone()
            if not season_row:
                return {"items": []}
            cur.execute(
                """
                WITH team_matches AS (
                  SELECT m.home_team_id AS team_id, m.away_score AS conceded
                  FROM match m WHERE m.season_id = %(season_id)s AND m.status = 'finished'
                  UNION ALL
                  SELECT m.away_team_id AS team_id, m.home_score AS conceded
                  FROM match m WHERE m.season_id = %(season_id)s AND m.status = 'finished'
                )
                SELECT
                  t.id AS team_id, t.name_default AS team_name, t.api_football_id,
                  COUNT(*) FILTER (WHERE tm.conceded = 0) AS clean_sheets
                FROM team_matches tm
                JOIN team t ON t.id = tm.team_id
                GROUP BY t.id, t.name_default, t.api_football_id
                HAVING COUNT(*) FILTER (WHERE tm.conceded = 0) > 0
                ORDER BY clean_sheets DESC, t.name_default
                LIMIT %(limit)s
                """,
                {"season_id": season_row["id"], "limit": limit},
            )
            rows = cur.fetchall()
    return {
        "items": [
            {
                "teamId": str(r["team_id"]),
                "team": r["team_name"],
                "teamLogo": team_logo_url(r["api_football_id"]),
                "cleanSheets": int(r["clean_sheets"]),
            }
            for r in rows
        ]
    }


@app.get("/api/teams/{team_id}/transfers")
def team_transfers(team_id: str, limit: int = Query(30, ge=1, le=100)):
    """Fichajes in/out de un club (vacío hasta cargar TRANSFER)."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name_default FROM team WHERE id::text = %s", (team_id,))
            team = cur.fetchone()
            if not team:
                raise HTTPException(404, "Equipo no encontrado")
            cur.execute(
                """
                SELECT
                  t.id, t.transfer_type::text AS transfer_type, t.effective_date,
                  t.fee_amount, t.fee_currency::text AS fee_currency,
                  per.display_name AS player_name, p.id AS player_id,
                  tf.name_default AS from_team, tt.name_default AS to_team,
                  CASE
                    WHEN t.to_team_id = %s THEN 'in'
                    WHEN t.from_team_id = %s THEN 'out'
                  END AS direction
                FROM transfer t
                JOIN player p ON p.id = t.player_id
                JOIN person per ON per.id = p.person_id
                LEFT JOIN team tf ON tf.id = t.from_team_id
                LEFT JOIN team tt ON tt.id = t.to_team_id
                WHERE t.to_team_id = %s OR t.from_team_id = %s
                ORDER BY t.effective_date DESC NULLS LAST
                LIMIT %s
                """,
                (team["id"], team["id"], team["id"], team["id"], limit),
            )
            rows = cur.fetchall()
    return {
        "teamId": str(team["id"]),
        "team": team["name_default"],
        "items": [
            {
                "id": str(r["id"]),
                "direction": r["direction"],
                "playerId": str(r["player_id"]),
                "player": r["player_name"],
                "from": r["from_team"],
                "to": r["to_team"],
                "type": r["transfer_type"],
                "date": r["effective_date"].isoformat() if r["effective_date"] else None,
                "fee": float(r["fee_amount"]) if r["fee_amount"] is not None else None,
                "currency": r["fee_currency"],
            }
            for r in rows
        ],
    }


@app.get("/api/teams/{team_id}")
def get_team(team_id: str):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.id, t.name_default, t.code, t.founded_year, t.api_football_id,
                       c.name_default AS country_name,
                       (
                         SELECT comp.name_default
                         FROM team_competition tc
                         JOIN season s ON s.id = tc.season_id
                         JOIN competition comp ON comp.id = s.competition_id
                         WHERE tc.team_id = t.id
                         ORDER BY s.is_current DESC, s.year_start DESC
                         LIMIT 1
                       ) AS competition_name,
                       (SELECT COUNT(*) FROM player_team_history h
                        WHERE h.team_id = t.id AND h.end_date IS NULL) AS squad_size
                FROM team t
                LEFT JOIN country c ON c.id = t.country_id
                WHERE t.id::text = %s
                """,
                (team_id,),
            )
            team = cur.fetchone()
            if not team:
                raise HTTPException(404, "Equipo no encontrado")

            cur.execute(
                """
                SELECT
                  p.id AS player_id,
                  p.api_football_id AS player_api_football_id,
                  per.full_name,
                  per.display_name,
                  per.birth_date,
                  p.primary_position,
                  p.foot::text AS foot,
                  p.height_cm,
                  p.shirt_name,
                  nat.name_default AS nationality,
                  t.id AS team_id,
                  t.name_default AS team_name,
                  t.code AS team_code,
                  t.api_football_id AS team_api_football_id,
                  ctry.name_default AS country_name,
                  %s AS competition_name,
                  (
                    SELECT mv.value_amount
                    FROM market_value_history mv
                    WHERE mv.player_id = p.id
                    ORDER BY mv.recorded_on DESC
                    LIMIT 1
                  ) AS market_value_amount
                FROM player_team_history h
                JOIN player p ON p.id = h.player_id
                JOIN person per ON per.id = p.person_id
                JOIN team t ON t.id = h.team_id
                LEFT JOIN country nat ON nat.id = p.nationality_country_id
                LEFT JOIN country ctry ON ctry.id = t.country_id
                WHERE h.team_id::text = %s AND h.end_date IS NULL
                ORDER BY p.primary_position NULLS LAST, per.display_name
                """,
                (team.get("competition_name"), team_id),
            )
            squad = cur.fetchall()
            cur.execute(
                """
                SELECT
                  COUNT(*) FILTER (WHERE tr.to_team_id = %s) AS arrivals,
                  COUNT(*) FILTER (WHERE tr.from_team_id = %s) AS departures,
                  COALESCE(SUM(tr.fee_amount) FILTER (WHERE tr.to_team_id = %s), 0) AS spend_amount,
                  COALESCE(SUM(tr.fee_amount) FILTER (WHERE tr.from_team_id = %s), 0) AS income_amount
                FROM transfer tr
                WHERE tr.to_team_id = %s OR tr.from_team_id = %s
                """,
                (team["id"],) * 6,
            )
            tw = cur.fetchone() or {}

    club = club_payload(
        {
            "team_id": team["id"],
            "team_name": team["name_default"],
            "team_code": team["code"],
            "api_football_id": team["api_football_id"],
            "country_name": team["country_name"],
            "competition_name": team["competition_name"],
        }
    )
    squad_payload = [player_payload(r) for r in squad]
    lab = compute_club_lab(squad_payload)
    # KPIs estilo Transfermarkt (derivados; sin estadio / sin clasificación)
    foreigners = 0
    team_country = (team["country_name"] or "").strip().lower()
    if team_country:
        for p in squad_payload:
            nat = (p.get("nationality") or "").strip().lower()
            if nat and nat not in ("—", "-") and nat != team_country:
                foreigners += 1
    values = [p["value"] for p in squad_payload if isinstance(p.get("value"), (int, float))]
    squad_value_m = round(sum(values), 2) if values else None
    spend = float(tw.get("spend_amount") or 0)
    income = float(tw.get("income_amount") or 0)
    return {
        **club,
        "founded": team["founded_year"],
        "squadSize": int(team["squad_size"] or 0),
        "avgAge": lab.get("avgAge"),
        "foreigners": foreigners,
        "foreignersPct": round(100 * foreigners / len(squad_payload), 1) if squad_payload else 0,
        "squadMarketValueM": squad_value_m,
        "transferWindow": {
            "arrivals": int(tw.get("arrivals") or 0),
            "departures": int(tw.get("departures") or 0),
            "spend": spend,
            "income": income,
            "balance": income - spend,
        },
        "squad": squad_payload,
        "lab": lab,
        "outOfMvp": {
            "stadium": False,
            "standings": False,
            "trophies": False,
            "coach": False,
            "note": "Estadio / clasificación / trofeos / entrenador = fuera del MVP congelado",
        },
    }


@app.get("/api/lab/showcase")
def lab_showcase(limit: int = Query(8, ge=1, le=16)):
    """Clubes con plantilla cargada para la vitrina Radiografía Lab."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.id, t.name_default, t.code, c.name_default AS country_name,
                  (
                    SELECT comp.name_default FROM team_competition tc
                    JOIN season s ON s.id = tc.season_id
                    JOIN competition comp ON comp.id = s.competition_id
                    WHERE tc.team_id = t.id
                    ORDER BY s.is_current DESC LIMIT 1
                  ) AS competition_name,
                  COUNT(h.id) AS squad_size
                FROM team t
                LEFT JOIN country c ON c.id = t.country_id
                JOIN player_team_history h ON h.team_id = t.id AND h.end_date IS NULL
                WHERE t.team_kind = 'club'
                GROUP BY t.id, c.name_default
                HAVING COUNT(h.id) >= 15
                ORDER BY COUNT(h.id) DESC, t.name_default
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    out = []
    for r in rows:
        c = club_payload(
            {
                "team_id": r["id"],
                "team_name": r["name_default"],
                "team_code": r["code"],
                "country_name": r["country_name"],
                "competition_name": r["competition_name"],
            }
        )
        c["squadSize"] = int(r["squad_size"] or 0)
        out.append(c)
    return {"clubs": out, "live": True}


@app.get("/api/search")
def search(q: str = Query("", min_length=1)):
    q = q.strip()
    like = f"%{q}%"
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                PLAYER_SELECT
                + """
                WHERE per.display_name ILIKE %s OR per.full_name ILIKE %s OR t.name_default ILIKE %s
                ORDER BY per.display_name
                LIMIT 8
                """,
                (like, like, like),
            )
            players = [player_payload(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT t.id, t.name_default, t.code, c.name_default AS country_name,
                  (
                    SELECT comp.name_default FROM team_competition tc
                    JOIN season s ON s.id = tc.season_id
                    JOIN competition comp ON comp.id = s.competition_id
                    WHERE tc.team_id = t.id
                    ORDER BY s.is_current DESC LIMIT 1
                  ) AS competition_name,
                  (SELECT COUNT(*) FROM player_team_history h WHERE h.team_id = t.id AND h.end_date IS NULL) AS squad_size
                FROM team t
                LEFT JOIN country c ON c.id = t.country_id
                WHERE t.name_default ILIKE %s
                ORDER BY squad_size DESC NULLS LAST
                LIMIT 6
                """,
                (like,),
            )
            teams = []
            for r in cur.fetchall():
                c = club_payload(
                    {
                        "team_id": r["id"],
                        "team_name": r["name_default"],
                        "team_code": r["code"],
                        "country_name": r["country_name"],
                        "competition_name": r["competition_name"],
                    }
                )
                c["squadSize"] = int(r["squad_size"] or 0)
                teams.append(c)

            cur.execute(
                """
                SELECT id::text AS id, name_default AS name, competition_type::text AS type, scope::text AS scope
                FROM competition
                WHERE name_default ILIKE %s
                ORDER BY name_default
                LIMIT 6
                """,
                (like,),
            )
            leagues = [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "country": r["scope"],
                    "teams": 0,
                    "players": 0,
                    "tier": 1 if r["type"] == "league" else 2,
                }
                for r in cur.fetchall()
            ]

    return {"players": players, "teams": teams, "leagues": leagues}


LEAGUE_SLUGS = {
    "premier": "Premier League",
    "laliga": "LaLiga",
    "seriea": "Serie A",
    "bundesliga": "Bundesliga",
    "ligue1": "Ligue 1",
}


@app.get("/api/transfers")
def transfers(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    type: str | None = Query(None, description="permanent | loan | loan_end | free | end_of_contract | academy_promotion | unknown"),
    league: str | None = Query(None, description="premier | laliga | seriea | bundesliga | ligue1"),
    sort: str | None = Query(None, description="fee (importe más alto primero) | nada = más recientes primero"),
):
    """Fichajes desde TRANSFER, con paginación y filtro opcional por tipo y liga
    (liga = liga de destino del jugador, en la temporada más reciente)."""
    clauses: list[str] = []
    params: list = []
    if type:
        clauses.append("t.transfer_type::text = %s")
        params.append(type)
    if league and league in LEAGUE_SLUGS:
        clauses.append(
            """
            EXISTS (
              SELECT 1 FROM team_competition tc
              JOIN competition comp ON comp.id = tc.competition_id
              WHERE tc.team_id = t.to_team_id
                AND comp.name_default = %s
            )
            """
        )
        params.append(LEAGUE_SLUGS[league])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM transfer t {where}", params)
            total = int(cur.fetchone()["n"])
            cur.execute(
                f"""
                SELECT
                  t.id,
                  t.transfer_type::text AS transfer_type,
                  t.effective_date,
                  t.announced_date,
                  t.fee_amount,
                  t.fee_currency::text AS fee_currency,
                  t.fee_is_estimated,
                  p.id AS player_id,
                  p.api_football_id AS player_api_football_id,
                  per.display_name AS player_name,
                  tf.name_default AS from_team,
                  tf.api_football_id AS from_team_api_football_id,
                  tt.name_default AS to_team,
                  tt.api_football_id AS to_team_api_football_id
                FROM transfer t
                JOIN player p ON p.id = t.player_id
                JOIN person per ON per.id = p.person_id
                LEFT JOIN team tf ON tf.id = t.from_team_id
                LEFT JOIN team tt ON tt.id = t.to_team_id
                {where}
                ORDER BY {"t.fee_amount DESC NULLS LAST" if sort == "fee" else "t.effective_date DESC NULLS LAST, t.created_at DESC"}
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            rows = cur.fetchall()
    items = [
        {
            "id": str(r["id"]),
            "playerId": str(r["player_id"]),
            "player": r["player_name"],
            "playerPhoto": player_photo_url(r["player_api_football_id"]),
            "from": r["from_team"],
            "fromLogo": team_logo_url(r["from_team_api_football_id"]),
            "to": r["to_team"],
            "toLogo": team_logo_url(r["to_team_api_football_id"]),
            "type": r["transfer_type"],
            "date": r["effective_date"].isoformat() if r["effective_date"] else None,
            "announced": r["announced_date"].isoformat() if r["announced_date"] else None,
            "fee": float(r["fee_amount"]) if r["fee_amount"] is not None else None,
            "currency": r["fee_currency"],
            "feeEstimated": bool(r["fee_is_estimated"]),
        }
        for r in rows
    ]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@app.get("/api/competitions")
def list_competitions(
    q: str | None = None,
    type: str | None = Query(None, description="league | cup | ..."),
    scope: str | None = None,
    country: str | None = None,
    active: bool | None = True,
    limit: int = Query(60, ge=1, le=300),
    offset: int = Query(0, ge=0),
):
    """
    Catálogo de competiciones (tabla competition).
    Incluye season current y nº de equipos inscritos si existen.
    """
    clauses: list[str] = []
    params: list = []
    if active is True:
        clauses.append("c.is_active = TRUE")
    elif active is False:
        clauses.append("c.is_active = FALSE")
    if type:
        clauses.append("c.competition_type::text = %s")
        params.append(type)
    if scope:
        clauses.append("c.scope::text = %s")
        params.append(scope)
    if country:
        clauses.append("co.name_default ILIKE %s")
        params.append(f"%{country}%")
    if q:
        clauses.append("(c.name_default ILIKE %s OR c.short_name ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    count_sql = f"""
        SELECT COUNT(*) AS n
        FROM competition c
        LEFT JOIN country co ON co.id = c.country_id
        {where}
    """
    list_sql = f"""
        SELECT
          c.id,
          c.name_default,
          c.short_name,
          c.competition_type::text AS competition_type,
          c.scope::text AS scope,
          c.gender::text AS gender,
          c.is_active,
          c.api_football_id,
          co.name_default AS country_name,
          s.id AS season_id,
          s.name_default AS season_name,
          s.year_start,
          s.year_end,
          (
            SELECT COUNT(*)::int
            FROM team_competition tc
            WHERE tc.season_id = s.id
          ) AS team_count
        FROM competition c
        LEFT JOIN country co ON co.id = c.country_id
        LEFT JOIN LATERAL (
          SELECT s2.*
          FROM season s2
          WHERE s2.competition_id = c.id
          ORDER BY s2.is_current DESC, s2.year_start DESC
          LIMIT 1
        ) s ON TRUE
        {where}
        ORDER BY
          CASE c.name_default
            WHEN 'Champions League' THEN 0
            WHEN 'Premier League' THEN 1
            WHEN 'LaLiga' THEN 2
            WHEN 'Serie A' THEN 3
            WHEN 'Bundesliga' THEN 4
            WHEN 'Ligue 1' THEN 5
            WHEN 'Europa League' THEN 6
            ELSE 100
          END,
          CASE c.competition_type::text WHEN 'league' THEN 0 WHEN 'cup' THEN 1 ELSE 2 END,
          co.name_default NULLS LAST,
          c.name_default
        LIMIT %s OFFSET %s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(count_sql, params)
            total = int(cur.fetchone()["n"])
            cur.execute(list_sql, params + [limit, offset])
            rows = cur.fetchall()

    items = [
        {
            "id": str(r["id"]),
            "name": r["name_default"],
            "shortName": r["short_name"],
            "type": r["competition_type"],
            "scope": r["scope"],
            "gender": r["gender"],
            "isActive": bool(r["is_active"]),
            "logo": league_logo_url(r["api_football_id"]),
            "country": r["country_name"] or ("Internacional" if r["scope"] == "international" else "—"),
            "seasonId": str(r["season_id"]) if r["season_id"] else None,
            "season": r["season_name"],
            "yearStart": r["year_start"],
            "yearEnd": r["year_end"],
            "teams": int(r["team_count"] or 0),
        }
        for r in rows
    ]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@app.get("/api/competitions/{competition_id}")
def get_competition(competition_id: str):
    """
    Ficha de competición + equipos inscritos en la season más relevante
    (current, o la más reciente).
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  c.id,
                  c.name_default,
                  c.short_name,
                  c.competition_type::text AS competition_type,
                  c.scope::text AS scope,
                  c.gender::text AS gender,
                  c.is_active,
                  c.api_football_id,
                  co.name_default AS country_name,
                  s.id AS season_id,
                  s.name_default AS season_name,
                  s.year_start,
                  s.year_end,
                  s.is_current
                FROM competition c
                LEFT JOIN country co ON co.id = c.country_id
                LEFT JOIN LATERAL (
                  SELECT s2.*
                  FROM season s2
                  WHERE s2.competition_id = c.id
                  ORDER BY s2.is_current DESC, s2.year_start DESC
                  LIMIT 1
                ) s ON TRUE
                WHERE c.id::text = %s
                """,
                (competition_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Competición no encontrada")

            teams = []
            if row["season_id"]:
                cur.execute(
                    """
                    SELECT
                      t.id AS team_id,
                      t.name_default AS team_name,
                      t.code AS team_code,
                      t.api_football_id,
                      ctr.name_default AS country_name,
                      %s AS competition_name,
                      (
                        SELECT COUNT(*)::int
                        FROM player_team_history h
                        WHERE h.team_id = t.id AND h.end_date IS NULL
                      ) AS squad_size
                    FROM team_competition tc
                    JOIN team t ON t.id = tc.team_id
                    LEFT JOIN country ctr ON ctr.id = t.country_id
                    WHERE tc.season_id = %s
                    ORDER BY t.name_default
                    """,
                    (row["name_default"], row["season_id"]),
                )
                for t in cur.fetchall():
                    club = club_payload(t)
                    club["squadSize"] = int(t["squad_size"] or 0)
                    teams.append(club)

    return {
        "id": str(row["id"]),
        "name": row["name_default"],
        "shortName": row["short_name"],
        "type": row["competition_type"],
        "scope": row["scope"],
        "gender": row["gender"],
        "isActive": bool(row["is_active"]),
        "logo": league_logo_url(row["api_football_id"]),
        "country": row["country_name"]
        or ("Internacional" if row["scope"] == "international" else "—"),
        "seasonId": str(row["season_id"]) if row["season_id"] else None,
        "season": row["season_name"],
        "yearStart": row["year_start"],
        "yearEnd": row["year_end"],
        "isCurrentSeason": bool(row["is_current"]) if row["is_current"] is not None else False,
        "teams": len(teams),
        "clubList": teams,
        "outOfMvp": {
            "standings": False,
            "note": "Clasificación fuera del MVP congelado (Anexo A.7 / páginas MVP)",
        },
    }


# --- MATCH / MATCH_EVENT (contrato IFLXI; scores = acta MATCH, no suma de eventos) ---

EVENT_LABELS = {
    "goal": "Gol",
    "own_goal": "Autogol",
    "penalty_goal": "Penalti",
    "penalty_miss": "Penalti fallado",
    "yellow_card": "Amarilla",
    "second_yellow": "Segunda amarilla",
    "red_card": "Roja",
    "substitution_out": "Cambio",
}


def _kickoff_label(kickoff_at, match_date) -> str | None:
    if kickoff_at is not None:
        try:
            return kickoff_at.strftime("%H:%M")
        except Exception:
            pass
    if match_date is not None:
        return str(match_date)
    return None


def match_list_payload(row: dict) -> dict:
    """Formato compatible con match-card de script.js."""
    return {
        "id": str(row["id"]),
        "league": row.get("competition_name") or "—",
        "leagueLogo": league_logo_url(row.get("competition_api_football_id")),
        "home": row.get("home_name") or "—",
        "homeLogo": team_logo_url(row.get("home_api_football_id")),
        "away": row.get("away_name") or "—",
        "awayLogo": team_logo_url(row.get("away_api_football_id")),
        "homeId": str(row["home_team_id"]) if row.get("home_team_id") else None,
        "awayId": str(row["away_team_id"]) if row.get("away_team_id") else None,
        "homeScore": row.get("home_score"),
        "awayScore": row.get("away_score"),
        "minute": None,  # MVP sin live operativo
        "status": row.get("status") or "scheduled",
        "kickoff": _kickoff_label(row.get("kickoff_at"), row.get("match_date")),
        "roundName": row.get("round_name"),
        "matchDate": row["match_date"].isoformat() if row.get("match_date") else None,
    }


def event_payload(row: dict, *, home_team_id) -> dict:
    et = row["event_type"]
    label = EVENT_LABELS.get(et, et)
    player_name = row.get("player_name")
    secondary_name = row.get("secondary_name")
    detail = None
    if et in ("goal", "penalty_goal") and secondary_name:
        detail = f"Asistencia: {secondary_name}"
    elif et == "substitution_out" and player_name and secondary_name:
        # player_id = SALE, secondary = ENTRA (D-SUB-01)
        detail = f"{player_name} → {secondary_name}"
        label = "Cambio"
    side = None
    if home_team_id and row.get("team_id"):
        side = "home" if str(row["team_id"]) == str(home_team_id) else "away"
    minute = row.get("minute")
    extra = row.get("extra_minute")
    clock = None
    if minute is not None:
        clock = f"{minute}'"
        if extra:
            clock = f"{minute}+{extra}'"
    return {
        "id": str(row["id"]),
        "type": et,
        "label": label,
        "detail": detail,
        "minute": minute,
        "extraMinute": extra,
        "clock": clock,
        "period": row.get("period"),
        "sortOrder": row.get("sort_order"),
        "player": (
            {"id": str(row["player_id"]), "name": player_name}
            if row.get("player_id")
            else None
        ),
        "secondaryPlayer": (
            {"id": str(row["secondary_player_id"]), "name": secondary_name}
            if row.get("secondary_player_id")
            else None
        ),
        "teamId": str(row["team_id"]) if row.get("team_id") else None,
        "teamName": row.get("team_name"),
        "side": side,
    }


MATCH_LIST_SQL = """
SELECT
  m.id,
  m.home_team_id,
  m.away_team_id,
  m.match_date,
  m.kickoff_at,
  m.round_name,
  m.status,
  m.home_score,
  m.away_score,
  th.name_default AS home_name,
  th.api_football_id AS home_api_football_id,
  ta.name_default AS away_name,
  ta.api_football_id AS away_api_football_id,
  c.name_default AS competition_name,
  c.api_football_id AS competition_api_football_id
FROM match m
JOIN team th ON th.id = m.home_team_id
JOIN team ta ON ta.id = m.away_team_id
JOIN season s ON s.id = m.season_id
JOIN competition c ON c.id = s.competition_id
"""


@app.get("/api/competitions/{competition_id}/matches")
def competition_matches(
    competition_id: str,
    season_id: str | None = None,
    status: str | None = None,
    limit: int = Query(40, ge=1, le=200),
):
    """Partidos de la competición (season current por defecto). Hub estilo TM/Fichajes."""
    with connect() as conn:
        with conn.cursor() as cur:
            if season_id:
                sid = season_id
            else:
                cur.execute(
                    """
                    SELECT id::text AS id FROM season
                    WHERE competition_id::text = %s
                    ORDER BY is_current DESC, year_start DESC
                    LIMIT 1
                    """,
                    (competition_id,),
                )
                srow = cur.fetchone()
                if not srow:
                    return {"competitionId": competition_id, "seasonId": None, "items": []}
                sid = srow["id"]
            clauses = ["s.competition_id::text = %s", "m.season_id::text = %s"]
            params: list = [competition_id, sid]
            if status:
                clauses.append("m.status = %s")
                params.append(status)
            where = " WHERE " + " AND ".join(clauses)
            cur.execute(
                MATCH_LIST_SQL
                + where
                + " ORDER BY m.match_date DESC NULLS LAST, m.kickoff_at DESC NULLS LAST LIMIT %s",
                params + [limit],
            )
            rows = cur.fetchall()
    return {
        "competitionId": competition_id,
        "seasonId": sid,
        "items": [match_list_payload(r) for r in rows],
    }


@app.get("/api/matches")
def list_matches(
    status: str | None = None,
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    limit: int = Query(40, ge=1, le=200),
):
    """Lista partidos. homeScore/awayScore = acta MATCH (nunca recalculados)."""
    clauses: list[str] = []
    params: list = []
    if status:
        clauses.append("m.status = %s")
        params.append(status)
    if date_from:
        clauses.append("m.match_date >= %s")
        params.append(date_from)
    if date_to:
        clauses.append("m.match_date <= %s")
        params.append(date_to)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        MATCH_LIST_SQL
        + where
        + " ORDER BY m.match_date DESC NULLS LAST, m.kickoff_at DESC NULLS LAST LIMIT %s"
    )
    params.append(limit)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [match_list_payload(r) for r in rows]


@app.get("/api/matches/{match_id}")
def get_match(match_id: str):
    """
    Detalle + timeline MATCH_EVENT.
    Reglas: sin event_type assist; subst = sale→entra; scores solo de MATCH.
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(MATCH_LIST_SQL + " WHERE m.id::text = %s", (match_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Partido no encontrado")
            cur.execute(
                """
                SELECT
                  e.id, e.event_type, e.minute, e.extra_minute, e.period, e.sort_order,
                  e.player_id, e.secondary_player_id, e.team_id,
                  pp.display_name AS player_name,
                  sp.display_name AS secondary_name,
                  t.name_default AS team_name
                FROM match_event e
                LEFT JOIN player pl ON pl.id = e.player_id
                LEFT JOIN person pp ON pp.id = pl.person_id
                LEFT JOIN player sl ON sl.id = e.secondary_player_id
                LEFT JOIN person sp ON sp.id = sl.person_id
                LEFT JOIN team t ON t.id = e.team_id
                WHERE e.match_id = %s
                ORDER BY e.sort_order NULLS LAST, e.minute NULLS LAST, e.extra_minute NULLS LAST
                """,
                (row["id"],),
            )
            events = cur.fetchall()
    payload = match_list_payload(row)
    payload["events"] = [
        event_payload(e, home_team_id=row["home_team_id"]) for e in events
    ]
    # Defensa documental: el marcador NO se deriva de events
    payload["scoreSource"] = "match"
    return payload


# --- estáticos (después de /api) ---
@app.get("/")
def home():
    return FileResponse(ROOT / "index.html")


@app.get("/club.html")
def club_page():
    return FileResponse(ROOT / "club.html")


@app.get("/partido.html")
def match_page():
    return FileResponse(ROOT / "partido.html")


@app.get("/competiciones.html")
def competitions_page():
    return FileResponse(ROOT / "competiciones.html")


@app.get("/competicion.html")
def competition_detail_page():
    return FileResponse(ROOT / "competicion.html")


# ===================== IMÁGENES DE NOTICIAS =====================

IMAGE_SIZES = {
    "main": (800, 600),   # noticia principal, 4:3
    "mini": (400, 300),   # noticias mini, 4:3
}


def process_image_to_webp(raw: bytes, kind: str) -> bytes:
    """Recorta al centro a la proporción del hueco (main 3:2, gallery 1:1),
    redimensiona al tamaño real usado en la web y convierte a WebP."""
    target_w, target_h = IMAGE_SIZES.get(kind, IMAGE_SIZES["mini"])
    img = Image.open(io.BytesIO(raw))
    img = img.convert("RGB")

    target_ratio = target_w / target_h
    w, h = img.size
    current_ratio = w / h
    if current_ratio > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    img = img.resize((target_w, target_h), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=82)
    return out.getvalue()


def upload_to_supabase_storage(data: bytes, filename: str) -> str:
    """Sube bytes al bucket público 'news-images' de Supabase Storage
    y devuelve la URL pública final."""
    base_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not base_url or not service_key:
        raise HTTPException(500, "Falta SUPABASE_URL o SUPABASE_SERVICE_KEY en el servidor")

    upload_url = f"{base_url}/storage/v1/object/news-images/{filename}"
    resp = requests.post(
        upload_url,
        headers={
            "Authorization": f"Bearer {service_key}",
            "apikey": service_key,
            "Content-Type": "image/webp",
            "x-upsert": "true",
        },
        data=data,
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(502, f"Fallo al subir imagen a Supabase: {resp.status_code} {resp.text[:200]}")
    return f"{base_url}/storage/v1/object/public/news-images/{filename}"


@app.post("/api/admin/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    kind: str = Form("mini"),
    x_admin_password: str | None = Header(None),
):
    require_admin(x_admin_password)
    if kind not in IMAGE_SIZES:
        kind = "mini"
    raw = await file.read()
    try:
        webp_bytes = process_image_to_webp(raw, kind)
    except Exception as exc:
        raise HTTPException(400, f"No se pudo procesar la imagen: {exc}")
    filename = f"{kind}-{uuid_lib.uuid4().hex}.webp"
    url = upload_to_supabase_storage(webp_bytes, filename)
    return {"url": url}


# ===================== NOTICIAS Y RUMORES (panel de admin) =====================


def require_admin(x_admin_password: str | None = Header(None)) -> None:
    """Protección simple por contraseña compartida (sin sistema de usuarios).
    La contraseña real vive en la variable de entorno ADMIN_PASSWORD."""
    expected = os.environ.get("ADMIN_PASSWORD")
    if not expected:
        raise HTTPException(500, "ADMIN_PASSWORD no configurada en el servidor")
    if not x_admin_password or x_admin_password != expected:
        raise HTTPException(401, "Contraseña de administrador incorrecta")


@app.get("/api/news")
def list_news(limit: int = Query(10, ge=1, le=50)):
    """Ranking para portada: destacada primero, luego por importancia y fecha."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, excerpt, tag, image_url, importance, is_featured, created_at
                FROM news_item
                WHERE is_published = TRUE
                ORDER BY is_featured DESC, importance DESC, created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [_news_item_json(r) for r in rows]


@app.get("/api/news/archive")
def news_archive(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    """Archivo completo, más recientes primero — para la página noticias.html."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM news_item WHERE is_published = TRUE")
            total = int(cur.fetchone()["n"])
            cur.execute(
                """
                SELECT id, title, excerpt, tag, image_url, importance, is_featured, created_at
                FROM news_item
                WHERE is_published = TRUE
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
    return {"total": total, "limit": limit, "offset": offset, "items": [_news_item_json(r) for r in rows]}


@app.get("/api/news/{news_id}")
def get_news_item(news_id: str):
    """Una noticia por su ID permanente — para noticia.html."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, excerpt, tag, image_url, importance, is_featured, created_at
                FROM news_item
                WHERE id = %s AND is_published = TRUE
                """,
                (news_id,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Noticia no encontrada")
    return _news_item_json(row)


def _news_item_json(r: dict) -> dict:
    return {
        "id": str(r["id"]),
        "title": r["title"],
        "excerpt": r["excerpt"],
        "tag": r["tag"],
        "image": r["image_url"],
        "importance": r["importance"],
        "isFeatured": bool(r["is_featured"]),
        "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
    }


@app.get("/api/admin/news/list")
def admin_list_news(limit: int = Query(30, ge=1, le=100), x_admin_password: str | None = Header(None)):
    """Listado de gestión para el panel de admin (para editar/borrar)."""
    require_admin(x_admin_password)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, excerpt, tag, image_url, importance, is_featured, created_at
                FROM news_item
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [_news_item_json(r) for r in rows]


@app.post("/api/admin/news")
def create_or_update_news(payload: dict, x_admin_password: str | None = Header(None)):
    """Publica una noticia nueva (o actualiza una existente si mandas 'id',
    por ejemplo para corregir una errata sin perder su URL). Nunca sustituye
    a otra noticia distinta — cada una vive para siempre en su propia fila."""
    require_admin(x_admin_password)
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "Falta el título")
    excerpt = (payload.get("excerpt") or "").strip() or None
    tag = (payload.get("tag") or "Mercado").strip()
    image_url = (payload.get("image") or "").strip() or None
    try:
        importance = int(payload.get("importance") or 3)
    except (TypeError, ValueError):
        importance = 3
    importance = min(5, max(1, importance))
    is_featured = bool(payload.get("isFeatured"))
    existing_id = (payload.get("id") or "").strip() or None

    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                if is_featured:
                    cur.execute("UPDATE news_item SET is_featured = FALSE WHERE is_featured = TRUE")
                if existing_id:
                    cur.execute(
                        """
                        UPDATE news_item SET
                          title = %s, excerpt = %s, tag = %s,
                          image_url = COALESCE(%s, image_url),
                          importance = %s, is_featured = %s, updated_at = now()
                        WHERE id = %s
                        RETURNING id
                        """,
                        (title, excerpt, tag, image_url, importance, is_featured, existing_id),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise HTTPException(404, "Noticia no encontrada para actualizar")
                    new_id = row["id"]
                else:
                    cur.execute(
                        """
                        INSERT INTO news_item (title, excerpt, tag, image_url, importance, is_featured)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (title, excerpt, tag, image_url, importance, is_featured),
                    )
                    new_id = cur.fetchone()["id"]
    return {"id": str(new_id)}


@app.delete("/api/admin/news/{news_id}")
def delete_news_item(news_id: str, x_admin_password: str | None = Header(None)):
    require_admin(x_admin_password)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM news_item WHERE id = %s", (news_id,))
        conn.commit()
    return {"ok": True}


# ===================== VALORES DE MERCADO (panel de admin) =====================


@app.get("/api/admin/market-values")
def list_market_values(limit: int = Query(30, ge=1, le=100), x_admin_password: str | None = Header(None)):
    require_admin(x_admin_password)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  mv.id, mv.value_amount, mv.currency::text AS currency, mv.recorded_on,
                  p.id AS player_id, per.display_name AS player_name
                FROM market_value_history mv
                JOIN player p ON p.id = mv.player_id
                JOIN person per ON per.id = p.person_id
                WHERE mv.source = 'manual'
                ORDER BY mv.recorded_on DESC, mv.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [
        {
            "id": str(r["id"]),
            "playerId": str(r["player_id"]),
            "player": r["player_name"],
            "value": float(r["value_amount"]),
            "currency": r["currency"],
            "recordedOn": r["recorded_on"].isoformat() if r["recorded_on"] else None,
        }
        for r in rows
    ]


@app.post("/api/admin/market-value")
def upsert_market_value(payload: dict, x_admin_password: str | None = Header(None)):
    require_admin(x_admin_password)
    player_id = (payload.get("playerId") or "").strip()
    if not player_id:
        raise HTTPException(400, "Falta el jugador")
    try:
        value_amount = float(payload.get("value"))
    except (TypeError, ValueError):
        raise HTTPException(400, "Valor inválido")
    if value_amount <= 0:
        raise HTTPException(400, "El valor debe ser mayor que 0")
    currency = (payload.get("currency") or "EUR").strip().upper()
    if currency not in ("EUR", "USD", "GBP"):
        currency = "EUR"
    recorded_on = (payload.get("recordedOn") or "").strip() or date.today().isoformat()

    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                # Fuente de verdad: MARKET_VALUE_HISTORY (regla 15: UNIQUE por jugador+fecha+origen)
                cur.execute(
                    """
                    INSERT INTO market_value_history (player_id, value_amount, currency, recorded_on, source)
                    VALUES (%s, %s, %s, %s, 'manual')
                    ON CONFLICT (player_id, recorded_on, source) DO UPDATE SET
                      value_amount = EXCLUDED.value_amount,
                      currency = EXCLUDED.currency
                    RETURNING id
                    """,
                    (player_id, value_amount, currency, recorded_on),
                )
                new_id = cur.fetchone()["id"]
                # Caché (regla 3): player.current_market_value se deriva del registro
                # más reciente en MARKET_VALUE_HISTORY para ese jugador.
                cur.execute(
                    """
                    UPDATE player SET
                      current_market_value = %s,
                      current_market_value_currency = %s
                    WHERE id = %s
                    """,
                    (value_amount, currency, player_id),
                )
    return {"id": str(new_id)}


@app.delete("/api/admin/market-value/{value_id}")
def delete_market_value(value_id: str, x_admin_password: str | None = Header(None)):
    require_admin(x_admin_password)
    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT player_id FROM market_value_history WHERE id = %s",
                    (value_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(404, "No encontrado")
                player_id = row["player_id"]
                cur.execute("DELETE FROM market_value_history WHERE id = %s", (value_id,))
                # Recalcular la caché: coger el registro más reciente que quede, o vaciarla si no queda ninguno.
                cur.execute(
                    """
                    SELECT value_amount, currency::text AS currency
                    FROM market_value_history
                    WHERE player_id = %s
                    ORDER BY recorded_on DESC, created_at DESC
                    LIMIT 1
                    """,
                    (player_id,),
                )
                latest = cur.fetchone()
                if latest:
                    cur.execute(
                        "UPDATE player SET current_market_value = %s, current_market_value_currency = %s WHERE id = %s",
                        (latest["value_amount"], latest["currency"], player_id),
                    )
                else:
                    cur.execute(
                        "UPDATE player SET current_market_value = NULL, current_market_value_currency = NULL WHERE id = %s",
                        (player_id,),
                    )
    return {"ok": True}


RUMOR_SELECT = """
    SELECT
      r.id, r.player_name, r.current_club, r.interested_club, r.level,
      r.created_at, p.id AS player_uuid, p.api_football_id AS player_api_football_id,
      tc.name_default AS current_club_real, tc.api_football_id AS current_club_api_football_id,
      ti.name_default AS interested_club_real, ti.api_football_id AS interested_club_api_football_id
    FROM rumor_item r
    LEFT JOIN player p ON p.id = r.player_id
    LEFT JOIN team tc ON tc.id = r.current_club_id
    LEFT JOIN team ti ON ti.id = r.interested_club_id
"""


def _rumor_json(r: dict) -> dict:
    return {
        "id": str(r["id"]),
        "player": r["player_name"],
        "playerId": str(r["player_uuid"]) if r["player_uuid"] else None,
        "playerPhoto": player_photo_url(r["player_api_football_id"]),
        "club": r["current_club_real"] or r["current_club"],
        "clubLogo": team_logo_url(r["current_club_api_football_id"]),
        "interested": r["interested_club_real"] or r["interested_club"],
        "interestedLogo": team_logo_url(r["interested_club_api_football_id"]),
        "level": r["level"],
        "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
    }


@app.get("/api/rumors")
def list_rumors(limit: int = Query(10, ge=1, le=50)):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(RUMOR_SELECT + " WHERE r.is_published = TRUE ORDER BY r.created_at DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
    return [_rumor_json(r) for r in rows]


@app.get("/api/rumors/archive")
def rumors_archive(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM rumor_item WHERE is_published = TRUE")
            total = int(cur.fetchone()["n"])
            cur.execute(
                RUMOR_SELECT + " WHERE r.is_published = TRUE ORDER BY r.created_at DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = cur.fetchall()
    return {"total": total, "limit": limit, "offset": offset, "items": [_rumor_json(r) for r in rows]}


@app.get("/api/rumors/{rumor_id}")
def get_rumor(rumor_id: str):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(RUMOR_SELECT + " WHERE r.id = %s AND r.is_published = TRUE", (rumor_id,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Rumor no encontrado")
    return _rumor_json(row)


@app.post("/api/admin/rumors")
def create_rumor(payload: dict, x_admin_password: str | None = Header(None)):
    require_admin(x_admin_password)
    player_name = (payload.get("player") or "").strip()
    interested = (payload.get("interested") or "").strip()
    if not player_name or not interested:
        raise HTTPException(400, "Faltan jugador o club interesado")
    club = (payload.get("club") or "").strip() or None
    level = (payload.get("level") or "media").strip()
    if level not in ("baja", "media", "alta"):
        level = "media"
    player_id = (payload.get("playerId") or "").strip() or None
    club_id = (payload.get("clubId") or "").strip() or None
    interested_id = (payload.get("interestedId") or "").strip() or None
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rumor_item
                  (player_name, player_id, current_club, current_club_id, interested_club, interested_club_id, level)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (player_name, player_id, club, club_id, interested, interested_id, level),
            )
            new_id = cur.fetchone()["id"]
        conn.commit()
    return {"id": str(new_id)}


@app.delete("/api/admin/rumors/{rumor_id}")
def delete_rumor(rumor_id: str, x_admin_password: str | None = Header(None)):
    require_admin(x_admin_password)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rumor_item WHERE id = %s", (rumor_id,))
        conn.commit()
    return {"ok": True}


app.mount("/", StaticFiles(directory=str(ROOT), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("IFLXI_PORT", "8787"))
    print(f"IFLXI live → http://127.0.0.1:{port}")
    print("Asegúrate de tener PGPASSWORD y PGDATABASE=iflxi")
    uvicorn.run("server:app", host="127.0.0.1", port=port, reload=False)
