-- =============================================================================
-- IFLXI — Validaciones post-piloto MATCH_EVENT (API-Football)
-- No modifica esquema. Esperado: 0 filas en reglas de integridad.
-- =============================================================================
-- psql -d iflxi -f sql/IFLXI-validaciones-match-event.sql
-- =============================================================================

\echo ===== CONTEO match / match_event =====
SELECT
  (SELECT COUNT(*) FROM match) AS matches,
  (SELECT COUNT(*) FROM match_event) AS events;

\echo ===== 1. No existe event_type=assist (ENUM no lo permite; defensa) =====
-- Si el ENUM está correcto, esta consulta ni siquiera admite el literal.
-- Comprobación alternativa: tipos presentes
SELECT event_type, COUNT(*) AS n
FROM match_event
GROUP BY event_type
ORDER BY 1;

\echo ===== 2. No existe substitution_in (ENUM no lo permite) =====
-- Ver listado anterior: solo debe aparecer substitution_out entre sustituciones.

\echo ===== 3. goal puede tener secondary_player_id (INFO) =====
SELECT COUNT(*) AS goals,
       COUNT(secondary_player_id) AS goals_with_assist
FROM match_event
WHERE event_type = 'goal';

\echo ===== 4. penalty_goal puede tener secondary_player_id (INFO) =====
SELECT COUNT(*) AS penalty_goals,
       COUNT(secondary_player_id) AS with_assist
FROM match_event
WHERE event_type = 'penalty_goal';

\echo ===== 5. own_goal NO tiene secondary_player_id (debe 0) =====
SELECT id, match_id, player_id, secondary_player_id, minute
FROM match_event
WHERE event_type = 'own_goal'
  AND secondary_player_id IS NOT NULL;

\echo ===== 6. substitution_out tiene player_id y secondary_player_id (debe 0) =====
SELECT id, match_id, player_id, secondary_player_id, minute
FROM match_event
WHERE event_type = 'substitution_out'
  AND (player_id IS NULL OR secondary_player_id IS NULL);

\echo ===== 7. player_id existe cuando está informado (debe 0) =====
SELECT e.id, e.event_type, e.player_id
FROM match_event e
WHERE e.player_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM player p WHERE p.id = e.player_id);

\echo ===== 8. secondary_player_id existe cuando está informado (debe 0) =====
SELECT e.id, e.event_type, e.secondary_player_id
FROM match_event e
WHERE e.secondary_player_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM player p WHERE p.id = e.secondary_player_id);

\echo ===== 9. team_id existe (debe 0) =====
SELECT e.id, e.event_type, e.team_id
FROM match_event e
WHERE NOT EXISTS (SELECT 1 FROM team t WHERE t.id = e.team_id);

\echo ===== 10. minute >= 0 (y dentro CHECK 0-120) (debe 0) =====
SELECT id, event_type, minute
FROM match_event
WHERE minute IS NOT NULL AND minute < 0;

\echo ===== 11. extra_minute >= 0 (debe 0) =====
SELECT id, event_type, extra_minute
FROM match_event
WHERE extra_minute IS NOT NULL AND extra_minute < 0;

\echo ===== 12. second_yellow + yellow_card mismo jugador/partido/minuto (revisar; debe 0) =====
-- El mapper no emite yellow_card extra al mapear Yellow Red Card.
SELECT a.match_id, a.player_id, a.minute, a.extra_minute
FROM match_event a
JOIN match_event b
  ON b.match_id = a.match_id
 AND b.player_id = a.player_id
 AND b.minute IS NOT DISTINCT FROM a.minute
 AND b.extra_minute IS NOT DISTINCT FROM a.extra_minute
WHERE a.event_type = 'second_yellow'
  AND b.event_type = 'yellow_card';

\echo ===== 13. MATCH scores vs goles de eventos (INFO; NO deben igualarse a la fuerza) =====
-- home_score/away_score = acta oficial. Los eventos NO deben usarse para recalcular.
-- Esta consulta solo informa diferencias; no es error automático.
SELECT m.id,
       m.home_score,
       m.away_score,
       (
         SELECT COUNT(*) FROM match_event e
         WHERE e.match_id = m.id
           AND e.event_type IN ('goal', 'penalty_goal')
           AND e.team_id = m.home_team_id
       )
       +
       (
         SELECT COUNT(*) FROM match_event e
         WHERE e.match_id = m.id
           AND e.event_type = 'own_goal'
           AND e.team_id = m.away_team_id
       ) AS events_home_approx,
       (
         SELECT COUNT(*) FROM match_event e
         WHERE e.match_id = m.id
           AND e.event_type IN ('goal', 'penalty_goal')
           AND e.team_id = m.away_team_id
       )
       +
       (
         SELECT COUNT(*) FROM match_event e
         WHERE e.match_id = m.id
           AND e.event_type = 'own_goal'
           AND e.team_id = m.home_team_id
       ) AS events_away_approx
FROM match m
WHERE EXISTS (SELECT 1 FROM match_event e WHERE e.match_id = m.id)
ORDER BY m.match_date DESC
LIMIT 50;

\echo ===== 14. Duplicados naturales (mismo partido/tipo/minuto/jugadores/orden) (debe 0) =====
SELECT match_id, event_type, minute, extra_minute, player_id, secondary_player_id,
       team_id, sort_order, COUNT(*) AS n
FROM match_event
GROUP BY match_id, event_type, minute, extra_minute, player_id, secondary_player_id,
         team_id, sort_order
HAVING COUNT(*) > 1;

\echo ===== EXTRA: secondary solo en tipos permitidos (debe 0) =====
SELECT id, event_type, secondary_player_id
FROM match_event
WHERE secondary_player_id IS NOT NULL
  AND event_type NOT IN ('goal', 'penalty_goal', 'substitution_out');

\echo ===== FIN validaciones MATCH_EVENT =====
