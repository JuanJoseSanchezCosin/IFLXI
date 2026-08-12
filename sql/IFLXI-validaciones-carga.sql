-- =============================================================================
-- IFLXI — Validaciones de carga MVP v1
-- Ejecutar contra la BD iflxi después de importar.
-- =============================================================================
-- psql -d iflxi -f sql/IFLXI-validaciones-carga.sql
-- =============================================================================

\echo ===== CONTEOS =====
SELECT 'country' AS tabla, COUNT(*) AS n FROM country
UNION ALL SELECT 'city', COUNT(*) FROM city
UNION ALL SELECT 'competition', COUNT(*) FROM competition
UNION ALL SELECT 'season', COUNT(*) FROM season
UNION ALL SELECT 'team', COUNT(*) FROM team
UNION ALL SELECT 'team_competition', COUNT(*) FROM team_competition
UNION ALL SELECT 'person', COUNT(*) FROM person
UNION ALL SELECT 'player', COUNT(*) FROM player
UNION ALL SELECT 'player_team_history', COUNT(*) FROM player_team_history
UNION ALL SELECT 'match', COUNT(*) FROM match
UNION ALL SELECT 'match_event', COUNT(*) FROM match_event
UNION ALL SELECT 'transfer', COUNT(*) FROM transfer
UNION ALL SELECT 'market_value_history', COUNT(*) FROM market_value_history
UNION ALL SELECT 'slug', COUNT(*) FROM slug
ORDER BY 1;

\echo ===== REGLA: más de un club abierto por jugador (debe ser 0 filas) =====
SELECT p.id AS player_id, per.display_name, COUNT(*) AS clubs_abiertos
FROM player_team_history h
JOIN team t ON t.id = h.team_id
JOIN player p ON p.id = h.player_id
JOIN person per ON per.id = p.person_id
WHERE h.end_date IS NULL
  AND t.team_kind = 'club'
GROUP BY p.id, per.display_name
HAVING COUNT(*) > 1;

\echo ===== REGLA: libre agente con cache de club (debe ser 0) =====
SELECT p.id, per.display_name, p.current_team_id
FROM player p
JOIN person per ON per.id = p.person_id
WHERE p.current_team_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM player_team_history h
    JOIN team t ON t.id = h.team_id
    WHERE h.player_id = p.id
      AND h.end_date IS NULL
      AND t.team_kind = 'club'
  );

\echo ===== REGLA: cache club distinto del historial abierto (revisar) =====
SELECT per.display_name,
       p.current_team_id AS cache_team,
       h.team_id AS history_team
FROM player p
JOIN person per ON per.id = p.person_id
JOIN player_team_history h ON h.player_id = p.id AND h.end_date IS NULL
JOIN team t ON t.id = h.team_id AND t.team_kind = 'club'
WHERE p.current_team_id IS DISTINCT FROM h.team_id;

\echo ===== REGLA: seasons current duplicadas por competición (debe 0) =====
SELECT competition_id, COUNT(*) AS currents
FROM season
WHERE is_current = TRUE
GROUP BY competition_id
HAVING COUNT(*) > 1;

\echo ===== REGLA: finished/awarded sin marcador (debe 0) =====
SELECT id, status, home_score, away_score
FROM match
WHERE status IN ('finished', 'awarded')
  AND (home_score IS NULL OR away_score IS NULL);

\echo ===== REGLA: loan sin on_loan_from (debe 0; el CHECK ya lo impide) =====
SELECT id, player_id, team_id, role, on_loan_from_team_id
FROM player_team_history
WHERE role = 'loan' AND on_loan_from_team_id IS NULL;

\echo ===== REGLA: free/end_of_contract con fee (debe 0) =====
SELECT id, transfer_type, fee_amount
FROM transfer
WHERE transfer_type IN ('free', 'end_of_contract')
  AND fee_amount IS NOT NULL;

\echo ===== INFO: jugadores y club cache actual =====
SELECT per.display_name,
       t.name_default AS club_cache,
       p.current_market_value,
       p.current_market_value_currency
FROM player p
JOIN person per ON per.id = p.person_id
LEFT JOIN team t ON t.id = p.current_team_id
ORDER BY per.display_name;
