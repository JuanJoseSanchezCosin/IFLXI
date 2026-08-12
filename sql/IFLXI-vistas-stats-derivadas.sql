-- =============================================================================
-- IFLXI — Vistas de lectura (NO modifican el modelo E/R ni tablas base)
-- Stats derivadas SOLO desde MATCH_EVENT + MATCH (regla: PLAYER no acumula).
-- Seguras de crear mientras corre el fill (solo DDL de VIEW).
-- =============================================================================
-- psql -d iflxi -f sql/IFLXI-vistas-stats-derivadas.sql
-- =============================================================================

-- Goles / asistencias / tarjetas / penaltis por jugador (global, todos los partidos cargados)
-- Asistencias SOLO desde goal/penalty_goal.secondary_player_id (Anexo A.1 / A.7).
CREATE OR REPLACE VIEW v_player_event_stats AS
SELECT
  p.id AS player_id,
  COALESCE(g.goals, 0) AS goals,
  COALESCE(og.own_goals, 0) AS own_goals,
  COALESCE(a.assists, 0) AS assists,
  COALESCE(pm.penalty_misses, 0) AS penalty_misses,
  COALESCE(yc.yellow_cards, 0) AS yellow_cards,
  COALESCE(sy.second_yellows, 0) AS second_yellows,
  COALESCE(rc.red_cards, 0) AS red_cards,
  COALESCE(so.subs_out, 0) AS subs_out,
  COALESCE(si.subs_in, 0) AS subs_in
FROM player p
LEFT JOIN (
  SELECT player_id, COUNT(*) AS goals
  FROM match_event
  WHERE event_type IN ('goal', 'penalty_goal')
  GROUP BY player_id
) g ON g.player_id = p.id
LEFT JOIN (
  SELECT player_id, COUNT(*) AS own_goals
  FROM match_event WHERE event_type = 'own_goal'
  GROUP BY player_id
) og ON og.player_id = p.id
LEFT JOIN (
  SELECT secondary_player_id AS player_id, COUNT(*) AS assists
  FROM match_event
  WHERE event_type IN ('goal', 'penalty_goal') AND secondary_player_id IS NOT NULL
  GROUP BY secondary_player_id
) a ON a.player_id = p.id
LEFT JOIN (
  SELECT player_id, COUNT(*) AS penalty_misses
  FROM match_event WHERE event_type = 'penalty_miss'
  GROUP BY player_id
) pm ON pm.player_id = p.id
LEFT JOIN (
  SELECT player_id, COUNT(*) AS yellow_cards
  FROM match_event WHERE event_type = 'yellow_card'
  GROUP BY player_id
) yc ON yc.player_id = p.id
LEFT JOIN (
  SELECT player_id, COUNT(*) AS second_yellows
  FROM match_event WHERE event_type = 'second_yellow'
  GROUP BY player_id
) sy ON sy.player_id = p.id
LEFT JOIN (
  SELECT player_id, COUNT(*) AS red_cards
  FROM match_event WHERE event_type IN ('red_card', 'second_yellow')
  GROUP BY player_id
) rc ON rc.player_id = p.id
LEFT JOIN (
  SELECT player_id, COUNT(*) AS subs_out
  FROM match_event WHERE event_type = 'substitution_out'
  GROUP BY player_id
) so ON so.player_id = p.id
LEFT JOIN (
  SELECT secondary_player_id AS player_id, COUNT(*) AS subs_in
  FROM match_event
  WHERE event_type = 'substitution_out' AND secondary_player_id IS NOT NULL
  GROUP BY secondary_player_id
) si ON si.player_id = p.id;

COMMENT ON VIEW v_player_event_stats IS
  'Stats derivadas de MATCH_EVENT (Anexo A.7). Asistencias = secondary_player_id en goal/penalty_goal. second_yellow cuenta como roja.';

-- Asistencias correctas (solo secondary en goal/penalty_goal) — vista limpia
CREATE OR REPLACE VIEW v_player_goals_assists AS
SELECT
  p.id AS player_id,
  COALESCE(g.goals, 0) AS goals,
  COALESCE(a.assists, 0) AS assists
FROM player p
LEFT JOIN (
  SELECT player_id, COUNT(*) AS goals
  FROM match_event
  WHERE event_type IN ('goal', 'penalty_goal')
  GROUP BY player_id
) g ON g.player_id = p.id
LEFT JOIN (
  SELECT secondary_player_id AS player_id, COUNT(*) AS assists
  FROM match_event
  WHERE event_type IN ('goal', 'penalty_goal')
    AND secondary_player_id IS NOT NULL
  GROUP BY secondary_player_id
) a ON a.player_id = p.id;

-- Máximos goleadores por competición (vía match → season → competition)
CREATE OR REPLACE VIEW v_competition_top_scorers AS
SELECT
  c.id AS competition_id,
  c.name_default AS competition_name,
  s.id AS season_id,
  s.name_default AS season_name,
  e.player_id,
  per.display_name AS player_name,
  COUNT(*) AS goals
FROM match_event e
JOIN match m ON m.id = e.match_id
JOIN season s ON s.id = m.season_id
JOIN competition c ON c.id = s.competition_id
JOIN player p ON p.id = e.player_id
JOIN person per ON per.id = p.person_id
WHERE e.event_type IN ('goal', 'penalty_goal')
GROUP BY c.id, c.name_default, s.id, s.name_default, e.player_id, per.display_name;

-- Asistencias por competición
CREATE OR REPLACE VIEW v_competition_top_assists AS
SELECT
  c.id AS competition_id,
  c.name_default AS competition_name,
  s.id AS season_id,
  s.name_default AS season_name,
  e.secondary_player_id AS player_id,
  per.display_name AS player_name,
  COUNT(*) AS assists
FROM match_event e
JOIN match m ON m.id = e.match_id
JOIN season s ON s.id = m.season_id
JOIN competition c ON c.id = s.competition_id
JOIN player p ON p.id = e.secondary_player_id
JOIN person per ON per.id = p.person_id
WHERE e.event_type IN ('goal', 'penalty_goal')
  AND e.secondary_player_id IS NOT NULL
GROUP BY c.id, c.name_default, s.id, s.name_default, e.secondary_player_id, per.display_name;

-- Resumen de mercado por club (cuando haya TRANSFER)
CREATE OR REPLACE VIEW v_team_transfer_window AS
SELECT
  t.id AS team_id,
  t.name_default AS team_name,
  COUNT(*) FILTER (WHERE tr.to_team_id = t.id) AS arrivals,
  COUNT(*) FILTER (WHERE tr.from_team_id = t.id) AS departures,
  COALESCE(SUM(tr.fee_amount) FILTER (WHERE tr.to_team_id = t.id), 0) AS spend_amount,
  COALESCE(SUM(tr.fee_amount) FILTER (WHERE tr.from_team_id = t.id), 0) AS income_amount
FROM team t
LEFT JOIN transfer tr
  ON tr.to_team_id = t.id OR tr.from_team_id = t.id
GROUP BY t.id, t.name_default;

COMMENT ON VIEW v_team_transfer_window IS
  'Balance fichajes por club. Fees solo cuando fee_amount informado; free no suma 0.';

-- KPIs de plantilla estilo Transfermarkt (sin estadio / sin clasificación)
CREATE OR REPLACE VIEW v_team_squad_kpis AS
SELECT
  t.id AS team_id,
  t.name_default AS team_name,
  COUNT(p.id) AS squad_size,
  ROUND(AVG(
    EXTRACT(YEAR FROM age(CURRENT_DATE, per.birth_date))
  )::numeric, 1) AS avg_age,
  COUNT(*) FILTER (
    WHERE p.nationality_country_id IS NOT NULL
      AND t.country_id IS NOT NULL
      AND p.nationality_country_id <> t.country_id
  ) AS foreigners,
  ROUND(
    100.0 * COUNT(*) FILTER (
      WHERE p.nationality_country_id IS NOT NULL
        AND t.country_id IS NOT NULL
        AND p.nationality_country_id <> t.country_id
    ) / NULLIF(COUNT(p.id), 0),
    1
  ) AS foreigners_pct,
  COALESCE(SUM(p.current_market_value), 0) AS squad_market_value,
  MAX(p.current_market_value_currency::text) AS currency
FROM team t
LEFT JOIN player_team_history h
  ON h.team_id = t.id AND h.end_date IS NULL
LEFT JOIN player p ON p.id = h.player_id
LEFT JOIN person per ON per.id = p.person_id
WHERE t.team_kind = 'club'
GROUP BY t.id, t.name_default;

COMMENT ON VIEW v_team_squad_kpis IS
  'Edad media / extranjeros / valor plantilla desde HISTORY abierta + caches. Sin STADIUM ni standings.';

-- Agentes libres (Anexo A.2): sin spell de club abierto
CREATE OR REPLACE VIEW v_free_agents AS
SELECT
  p.id AS player_id,
  per.display_name AS player_name,
  p.primary_position,
  p.current_market_value,
  p.current_market_value_currency,
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
  );

COMMENT ON VIEW v_free_agents IS
  'Jugadores libres según Anexo A.2 (sin club artificial Free Agent).';

-- Ranking valor de mercado (cache gobernado; fuente = MARKET_VALUE_HISTORY)
CREATE OR REPLACE VIEW v_top_market_values AS
SELECT
  p.id AS player_id,
  per.display_name AS player_name,
  p.primary_position,
  p.current_market_value AS value_amount,
  p.current_market_value_currency AS currency,
  t.id AS team_id,
  t.name_default AS team_name,
  nat.name_default AS nationality
FROM player p
JOIN person per ON per.id = p.person_id
LEFT JOIN team t ON t.id = p.current_team_id
LEFT JOIN country nat ON nat.id = p.nationality_country_id
WHERE p.current_market_value IS NOT NULL
  AND p.status = 'active';

COMMENT ON VIEW v_top_market_values IS
  'Ordenar en consulta (ORDER BY value_amount DESC). Cache; reconstruible desde MARKET_VALUE_HISTORY.';
