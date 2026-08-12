-- =============================================================================
-- IFLXI — Validaciones TRANSFER (post-carga fichajes)
-- No modifica esquema. Esperado: 0 filas en reglas de integridad.
-- =============================================================================
-- psql -d iflxi -f sql/IFLXI-validaciones-transfer.sql
-- =============================================================================

\echo ===== CONTEO transfer =====
SELECT COUNT(*) AS transfers FROM transfer;

\echo ===== free/end_of_contract con fee (debe 0) =====
SELECT id, transfer_type, fee_amount
FROM transfer
WHERE transfer_type IN ('free', 'end_of_contract')
  AND fee_amount IS NOT NULL;

\echo ===== fee sin moneda o moneda sin fee (debe 0) =====
SELECT id, fee_amount, fee_currency
FROM transfer
WHERE (fee_amount IS NULL) <> (fee_currency IS NULL);

\echo ===== fee <= 0 (debe 0) =====
SELECT id, fee_amount
FROM transfer
WHERE fee_amount IS NOT NULL AND fee_amount <= 0;

\echo ===== from_team = to_team (debe 0) =====
SELECT id, from_team_id, to_team_id
FROM transfer
WHERE from_team_id IS NOT NULL
  AND to_team_id IS NOT NULL
  AND from_team_id = to_team_id;

\echo ===== player_id inexistente (debe 0) =====
SELECT t.id
FROM transfer t
WHERE NOT EXISTS (SELECT 1 FROM player p WHERE p.id = t.player_id);

\echo ===== INFO: transfers sin related_history_id (revisar sync regla 4) =====
SELECT COUNT(*) AS without_history_link
FROM transfer
WHERE related_history_id IS NULL;

\echo ===== FIN validaciones TRANSFER =====
