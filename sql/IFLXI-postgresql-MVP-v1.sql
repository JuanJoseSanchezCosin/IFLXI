-- =============================================================================
-- IFLXI (Info Football Lab XI) — Diseño físico PostgreSQL MVP v1
-- =============================================================================
-- Fuentes congeladas:
--   - docs/IFLXI-diccionario-datos-MVP-v1.md (MVP v1.1 + Anexo A)
--   - docs/IFLXI_ER_MVP_v1.2.drawio (visual; nombres de columna siguen diccionario)
--   - 17 decisiones de negocio congeladas
--
-- Requisitos: PostgreSQL 13+ (gen_random_uuid() nativo)
-- Este script NO inserta datos de prueba.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- Extensiones
-- -----------------------------------------------------------------------------
-- pgcrypto: compatibilidad con entornos donde gen_random_uuid() no esté en core
-- (PostgreSQL < 13). En PG 13+ es redundante pero inocuo.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =============================================================================
-- TIPOS ENUM (catálogos cerrados MVP — append-only conceptual)
-- =============================================================================

CREATE TYPE continent_code AS ENUM (
  'AF', 'AS', 'EU', 'NA', 'SA', 'OC', 'AN'
);

CREATE TYPE competition_type AS ENUM (
  'league',
  'cup',
  'international_club',
  'international_national',
  'playoff',
  'other'
);

CREATE TYPE competition_scope AS ENUM (
  'domestic',
  'continental',
  'world'
);

CREATE TYPE gender_competition AS ENUM (
  'male',
  'female',
  'mixed'
);

CREATE TYPE age_category_competition AS ENUM (
  'senior',
  'u23',
  'u21',
  'u19',
  'u17',
  'other'
);

CREATE TYPE age_category_team AS ENUM (
  'senior',
  'u23',
  'u21',
  'u19',
  'u17',
  'b_team',
  'other'
);

CREATE TYPE sport_code AS ENUM (
  'football'
);

CREATE TYPE team_kind AS ENUM (
  'club',
  'national'
);

CREATE TYPE team_competition_status AS ENUM (
  'registered',
  'withdrawn',
  'disqualified'
);

CREATE TYPE person_gender AS ENUM (
  'male',
  'female',
  'other',
  'unknown'
);

-- Posiciones MVP cerradas (diccionario listaba “…”. Ver decisión D-POS-01 en MD).
CREATE TYPE player_position AS ENUM (
  'GK',
  'CB',
  'LB',
  'RB',
  'LWB',
  'RWB',
  'CDM',
  'CM',
  'CAM',
  'LM',
  'RM',
  'LW',
  'RW',
  'CF',
  'ST'
);

CREATE TYPE player_foot AS ENUM (
  'left',
  'right',
  'both',
  'unknown'
);

CREATE TYPE player_status AS ENUM (
  'active',
  'retired',
  'deceased',
  'unknown'
);

CREATE TYPE history_role AS ENUM (
  'permanent',
  'loan',
  'loan_return',
  'trial',
  'youth',
  'unknown'
);

-- `live` incluido como valor reservado (diccionario). No es estado operativo MVP (regla 8).
CREATE TYPE match_status AS ENUM (
  'scheduled',
  'live',
  'finished',
  'postponed',
  'cancelled',
  'awarded'
);

-- D-SUB-01 / Regla 12:
-- MVP utiliza exclusivamente substitution_out.
-- player_id = jugador que sale.
-- secondary_player_id = jugador que entra.
-- substitution_in no se utiliza.
-- assist no existe como event_type; las asistencias se representan mediante
-- secondary_player_id en goal/penalty_goal.
CREATE TYPE event_type AS ENUM (
  'goal',
  'own_goal',
  'penalty_goal',
  'penalty_miss',
  'yellow_card',
  'red_card',
  'second_yellow',
  'substitution_out'
);

CREATE TYPE event_period AS ENUM (
  'first_half',
  'second_half',
  'extra_first',
  'extra_second',
  'penalty_shootout',
  'unknown'
);

CREATE TYPE transfer_type AS ENUM (
  'permanent',
  'loan',
  'loan_end',
  'free',
  'end_of_contract',
  'academy_promotion',
  'unknown'
);

CREATE TYPE currency_code AS ENUM (
  'EUR',
  'USD',
  'GBP'
);

CREATE TYPE slug_entity_type AS ENUM (
  'player',
  'team',
  'competition',
  'match',
  'transfer',
  'season'
);

COMMENT ON TYPE event_type IS
  'D-SUB-01 / Regla 12: MVP utiliza exclusivamente substitution_out. player_id = jugador que sale. secondary_player_id = jugador que entra. substitution_in no se utiliza. assist no existe como event_type; las asistencias se representan mediante secondary_player_id en goal/penalty_goal.';

COMMENT ON TYPE match_status IS
  'Estados de partido. live = reservado/opcional; operativa MVP: scheduled|finished|postponed|cancelled (+ awarded).';

-- =============================================================================
-- 1. COUNTRY
-- =============================================================================
CREATE TABLE country (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  iso2            CHAR(2) NOT NULL,
  iso3            CHAR(3),
  fifa_code       CHAR(3),
  name_default    TEXT NOT NULL,
  continent_code  continent_code,
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_country_iso2 UNIQUE (iso2),
  CONSTRAINT ck_country_iso2_len CHECK (char_length(iso2) = 2),
  CONSTRAINT ck_country_iso3_len CHECK (iso3 IS NULL OR char_length(iso3) = 3),
  CONSTRAINT ck_country_fifa_len CHECK (fifa_code IS NULL OR char_length(fifa_code) = 3)
);

COMMENT ON TABLE country IS 'Territorio/nación. Clave natural: iso2.';

-- =============================================================================
-- 2. CITY
-- =============================================================================
CREATE TABLE city (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  country_id      UUID NOT NULL REFERENCES country (id) ON DELETE RESTRICT,
  name_default    TEXT NOT NULL,
  latitude        NUMERIC(9, 6),
  longitude       NUMERIC(9, 6),
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_city_latitude CHECK (latitude IS NULL OR (latitude >= -90 AND latitude <= 90)),
  CONSTRAINT ck_city_longitude CHECK (longitude IS NULL OR (longitude >= -180 AND longitude <= 180))
);

CREATE INDEX ix_city_country_id ON city (country_id);

COMMENT ON TABLE city IS 'Localidad geográfica vinculada a country.';

-- =============================================================================
-- 3. COMPETITION
-- =============================================================================
CREATE TABLE competition (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name_default        TEXT NOT NULL,
  short_name          TEXT,
  competition_type    competition_type NOT NULL,
  scope               competition_scope NOT NULL,
  country_id          UUID REFERENCES country (id) ON DELETE RESTRICT,
  governing_body      TEXT,
  gender              gender_competition NOT NULL,
  age_category        age_category_competition NOT NULL DEFAULT 'senior',
  sport_code          sport_code NOT NULL DEFAULT 'football',
  is_active           BOOLEAN NOT NULL DEFAULT TRUE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_competition_country_id ON competition (country_id);

COMMENT ON TABLE competition IS 'Competición marca atemporal. No almacena season_year ni clasificación.';

-- =============================================================================
-- 4. SEASON
-- =============================================================================
CREATE TABLE season (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  competition_id    UUID NOT NULL REFERENCES competition (id) ON DELETE RESTRICT,
  name_default      TEXT NOT NULL,
  year_start        INTEGER NOT NULL,
  year_end          INTEGER NOT NULL,
  start_date        DATE,
  end_date          DATE,
  is_current        BOOLEAN NOT NULL DEFAULT FALSE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_season_years CHECK (year_start <= year_end),
  CONSTRAINT ck_season_dates CHECK (start_date IS NULL OR end_date IS NULL OR start_date <= end_date)
);

-- Regla 7 / Anexo A.5: máx. una season current por competición
CREATE UNIQUE INDEX uq_season_one_current_per_competition
  ON season (competition_id)
  WHERE is_current = TRUE;

CREATE INDEX ix_season_competition_id ON season (competition_id);

COMMENT ON TABLE season IS 'Edición concreta de una competición.';
COMMENT ON COLUMN season.is_current IS
  'Máximo una TRUE por competition_id (índice único parcial uq_season_one_current_per_competition).';

-- =============================================================================
-- 5. TEAM
-- =============================================================================
CREATE TABLE team (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name_default      TEXT NOT NULL,
  short_name        TEXT,
  code              TEXT,
  team_kind         team_kind NOT NULL,
  gender            gender_competition NOT NULL,
  age_category      age_category_team NOT NULL DEFAULT 'senior',
  country_id        UUID NOT NULL REFERENCES country (id) ON DELETE RESTRICT,
  city_id           UUID REFERENCES city (id) ON DELETE RESTRICT,
  parent_team_id    UUID REFERENCES team (id) ON DELETE RESTRICT,
  founded_year      INTEGER,
  is_active         BOOLEAN NOT NULL DEFAULT TRUE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_team_founded_year CHECK (
    founded_year IS NULL OR (founded_year >= 1800 AND founded_year <= 2100)
  ),
  CONSTRAINT ck_team_parent_not_self CHECK (
    parent_team_id IS NULL OR parent_team_id <> id
  )
);

CREATE INDEX ix_team_country_id ON team (country_id);
CREATE INDEX ix_team_city_id ON team (city_id);
CREATE INDEX ix_team_parent_team_id ON team (parent_team_id);

COMMENT ON TABLE team IS
  'Unidad competitiva (club o selección). NO crear TEAM Free Agent (Anexo A.2 / regla 2).';

-- =============================================================================
-- 6. TEAM_COMPETITION
-- =============================================================================
CREATE TABLE team_competition (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  team_id     UUID NOT NULL REFERENCES team (id) ON DELETE RESTRICT,
  season_id   UUID NOT NULL REFERENCES season (id) ON DELETE RESTRICT,
  status      team_competition_status NOT NULL DEFAULT 'registered',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_team_competition_team_season UNIQUE (team_id, season_id)
);

CREATE INDEX ix_team_competition_season_id ON team_competition (season_id);

COMMENT ON TABLE team_competition IS
  'Participación TEAM en SEASON. No existe relación directa TEAM–SEASON.';

-- =============================================================================
-- 7. PERSON
-- =============================================================================
CREATE TABLE person (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name           TEXT NOT NULL,
  display_name        TEXT NOT NULL,
  first_name          TEXT,
  last_name           TEXT,
  birth_date          DATE,
  birth_country_id    UUID REFERENCES country (id) ON DELETE RESTRICT,
  birth_city_id       UUID REFERENCES city (id) ON DELETE RESTRICT,
  gender              person_gender,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_person_birth_country_id ON person (birth_country_id);
CREATE INDEX ix_person_birth_city_id ON person (birth_city_id);

COMMENT ON TABLE person IS 'Identidad humana. Edad = cálculo desde birth_date; no se almacena.';

-- =============================================================================
-- 8. PLAYER
-- =============================================================================
CREATE TABLE player (
  id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id                       UUID NOT NULL REFERENCES person (id) ON DELETE RESTRICT,
  nationality_country_id          UUID REFERENCES country (id) ON DELETE RESTRICT,
  primary_position                player_position,
  secondary_position              player_position,
  foot                            player_foot,
  height_cm                       INTEGER,
  weight_kg                       INTEGER,
  shirt_name                      TEXT,
  status                          player_status NOT NULL DEFAULT 'active',
  -- CACHES (Anexo A.3 / regla 3) — NO fuente de verdad
  current_team_id                 UUID REFERENCES team (id) ON DELETE SET NULL,
  current_market_value            NUMERIC(14, 2),
  current_market_value_currency   currency_code,
  created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_player_person_id UNIQUE (person_id),
  CONSTRAINT ck_player_height CHECK (height_cm IS NULL OR (height_cm BETWEEN 120 AND 250)),
  CONSTRAINT ck_player_weight CHECK (weight_kg IS NULL OR (weight_kg BETWEEN 40 AND 150)),
  CONSTRAINT ck_player_market_cache_currency CHECK (
    (current_market_value IS NULL AND current_market_value_currency IS NULL)
    OR (current_market_value IS NOT NULL AND current_market_value_currency IS NOT NULL)
  ),
  CONSTRAINT ck_player_market_value_nonneg CHECK (
    current_market_value IS NULL OR current_market_value >= 0
  )
);

CREATE INDEX ix_player_current_team_id ON player (current_team_id);
CREATE INDEX ix_player_nationality_country_id ON player (nationality_country_id);

COMMENT ON TABLE player IS
  'Rol futbolístico de PERSON. Sin stats acumuladas (regla 17). PERSON 1 — 0..1 PLAYER.';

COMMENT ON COLUMN player.current_team_id IS
  'Campo derivado/cache. Fuente de verdad: PLAYER_TEAM_HISTORY (spell club abierto). Sin club = NULL. No editar a mano en flujo normal.';

COMMENT ON COLUMN player.current_market_value IS
  'Campo derivado/cache. Fuente de verdad: MARKET_VALUE_HISTORY (último recorded_on).';

COMMENT ON COLUMN player.current_market_value_currency IS
  'Campo derivado/cache. Divisa del valor cacheado. Fuente de verdad: MARKET_VALUE_HISTORY.';

COMMENT ON COLUMN player.status IS
  'retired/deceased: cerrar histories de club abiertas (Anexo A.2). Validación de aplicación.';

-- =============================================================================
-- 9. PLAYER_TEAM_HISTORY
-- =============================================================================
CREATE TABLE player_team_history (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id               UUID NOT NULL REFERENCES player (id) ON DELETE RESTRICT,
  team_id                 UUID NOT NULL REFERENCES team (id) ON DELETE RESTRICT,
  role                    history_role NOT NULL DEFAULT 'permanent',
  start_date              DATE NOT NULL,
  end_date                DATE,
  shirt_number            INTEGER,
  on_loan_from_team_id    UUID REFERENCES team (id) ON DELETE RESTRICT,
  notes                   TEXT,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_history_dates CHECK (end_date IS NULL OR start_date <= end_date),
  CONSTRAINT ck_history_shirt CHECK (shirt_number IS NULL OR shirt_number BETWEEN 0 AND 99),
  -- Cesión: on_loan_from obligatorio y distinto de team_id.
  -- Si role <> loan: on_loan_from_team_id debe ser NULL.
  CONSTRAINT ck_history_loan_from CHECK (
    (
      role = 'loan'
      AND on_loan_from_team_id IS NOT NULL
      AND on_loan_from_team_id <> team_id
    )
    OR
    (
      role <> 'loan'
      AND on_loan_from_team_id IS NULL
    )
  )
);

CREATE INDEX ix_player_team_history_player_id ON player_team_history (player_id);
CREATE INDEX ix_player_team_history_team_id ON player_team_history (team_id);
CREATE INDEX ix_player_team_history_on_loan_from_team_id ON player_team_history (on_loan_from_team_id);
-- Apoyo a consultas de plantilla / libre agente (spells abiertos)
CREATE INDEX ix_player_team_history_open_spells
  ON player_team_history (player_id, team_id)
  WHERE end_date IS NULL;

COMMENT ON TABLE player_team_history IS
  'Spell de pertenencia. end_date NULL = vigente. Máx. un club abierto a la vez (regla 13: app). Cesión: role=loan + on_loan_from_team_id.';

COMMENT ON COLUMN player_team_history.end_date IS
  'NULL = spell vigente. Jugador libre = ningún spell de club abierto (regla 2).';

COMMENT ON COLUMN player_team_history.on_loan_from_team_id IS
  'En role=loan: equipo propietario/origen. team_id = cesionario.';

-- =============================================================================
-- 10. MATCH
-- =============================================================================
CREATE TABLE match (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  season_id       UUID NOT NULL REFERENCES season (id) ON DELETE RESTRICT,
  home_team_id    UUID NOT NULL REFERENCES team (id) ON DELETE RESTRICT,
  away_team_id    UUID NOT NULL REFERENCES team (id) ON DELETE RESTRICT,
  match_date      DATE NOT NULL,
  kickoff_at      TIMESTAMPTZ,
  round_name      TEXT,
  status          match_status NOT NULL DEFAULT 'scheduled',
  home_score      INTEGER,
  away_score      INTEGER,
  venue_city_id   UUID REFERENCES city (id) ON DELETE RESTRICT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_match_distinct_teams CHECK (home_team_id <> away_team_id),
  CONSTRAINT ck_match_scores_nonneg CHECK (
    (home_score IS NULL OR home_score >= 0)
    AND (away_score IS NULL OR away_score >= 0)
  ),
  -- Regla 8 / Anexo A.6: finished|awarded → scores obligatorios
  CONSTRAINT ck_match_scores_when_finished CHECK (
    status NOT IN ('finished', 'awarded')
    OR (home_score IS NOT NULL AND away_score IS NOT NULL)
  )
);

CREATE INDEX ix_match_season_id ON match (season_id);
CREATE INDEX ix_match_home_team_id ON match (home_team_id);
CREATE INDEX ix_match_away_team_id ON match (away_team_id);
CREATE INDEX ix_match_match_date ON match (match_date);

COMMENT ON TABLE match IS
  'Encuentro. home_score/away_score = resultado oficial de acta; NO se recalcula desde MATCH_EVENT (regla 8).';

COMMENT ON COLUMN match.kickoff_at IS
  'TIMESTAMPTZ: instante del saque con zona horaria. Convención de proyecto: almacenar en UTC.';

COMMENT ON COLUMN match.home_score IS
  'Resultado oficial. Fuente de verdad del marcador. Null si no jugado.';

COMMENT ON COLUMN match.away_score IS
  'Resultado oficial. Fuente de verdad del marcador. Null si no jugado.';

COMMENT ON COLUMN match.status IS
  'live reservado. Operativa MVP: scheduled|finished|postponed|cancelled|awarded.';

-- =============================================================================
-- 11. MATCH_EVENT
-- =============================================================================
CREATE TABLE match_event (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  match_id              UUID NOT NULL REFERENCES match (id) ON DELETE RESTRICT,
  event_type            event_type NOT NULL,
  player_id             UUID REFERENCES player (id) ON DELETE RESTRICT,
  secondary_player_id   UUID REFERENCES player (id) ON DELETE RESTRICT,
  team_id               UUID NOT NULL REFERENCES team (id) ON DELETE RESTRICT,
  minute                INTEGER,
  extra_minute          INTEGER,
  period                event_period,
  sort_order            INTEGER,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_event_minute CHECK (minute IS NULL OR (minute BETWEEN 0 AND 120)),
  CONSTRAINT ck_event_extra_minute CHECK (extra_minute IS NULL OR (extra_minute BETWEEN 0 AND 30)),
  CONSTRAINT ck_event_players_distinct CHECK (
    player_id IS NULL
    OR secondary_player_id IS NULL
    OR player_id <> secondary_player_id
  ),
  -- Regla 9: goles/disciplina requieren player_id
  CONSTRAINT ck_event_player_required CHECK (
    event_type NOT IN (
      'goal', 'own_goal', 'penalty_goal', 'penalty_miss',
      'yellow_card', 'red_card', 'second_yellow'
    )
    OR player_id IS NOT NULL
  ),
  -- Regla 12: substitution_out = sale (player_id) + entra (secondary_player_id)
  CONSTRAINT ck_event_substitution_out CHECK (
    event_type <> 'substitution_out'
    OR (player_id IS NOT NULL AND secondary_player_id IS NOT NULL)
  ),
  -- Asistencia solo en goal/penalty_goal; secondary también en substitution_out
  CONSTRAINT ck_event_secondary_usage CHECK (
    secondary_player_id IS NULL
    OR event_type IN ('goal', 'penalty_goal', 'substitution_out')
  ),
  -- Regla 10 / A.1: own_goal no usa secondary
  CONSTRAINT ck_event_own_goal_no_secondary CHECK (
    event_type <> 'own_goal'
    OR secondary_player_id IS NULL
  )
);

CREATE INDEX ix_match_event_match_id ON match_event (match_id);
CREATE INDEX ix_match_event_player_id ON match_event (player_id);
CREATE INDEX ix_match_event_secondary_player_id ON match_event (secondary_player_id);
CREATE INDEX ix_match_event_team_id ON match_event (team_id);
CREATE INDEX ix_match_event_type ON match_event (event_type);

COMMENT ON TABLE match_event IS
  'Hecho atómico. Fuente de stats MVP. D-SUB-01 / Regla 12: MVP utiliza exclusivamente substitution_out. player_id = jugador que sale. secondary_player_id = jugador que entra. substitution_in no se utiliza. assist no existe como event_type; las asistencias se representan mediante secondary_player_id en goal/penalty_goal.';

COMMENT ON COLUMN match_event.secondary_player_id IS
  'Asistente en goal/penalty_goal. En substitution_out = jugador que entra (D-SUB-01 / Regla 12). Única forma de asistencia (regla 1).';

COMMENT ON COLUMN match_event.team_id IS
  'Equipo al que se atribuye el evento. own_goal: team_id = equipo que SUFRE el gol (regla 10).';

COMMENT ON COLUMN match_event.event_type IS
  'second_yellow: cuenta como roja, NO suma amarilla adicional (regla 11). amarillas=yellow_card; rojas=red_card+second_yellow.';

-- =============================================================================
-- 12. TRANSFER
-- =============================================================================
CREATE TABLE transfer (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id             UUID NOT NULL REFERENCES player (id) ON DELETE RESTRICT,
  from_team_id          UUID REFERENCES team (id) ON DELETE RESTRICT,
  to_team_id            UUID REFERENCES team (id) ON DELETE RESTRICT,
  transfer_type         transfer_type NOT NULL,
  announced_date        DATE,
  effective_date        DATE NOT NULL,
  fee_amount            NUMERIC(14, 2),
  fee_currency          currency_code,
  fee_is_estimated      BOOLEAN NOT NULL DEFAULT FALSE,
  related_history_id    UUID REFERENCES player_team_history (id) ON DELETE RESTRICT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Impide from = to cuando ambos tienen valor; permite NULL (p. ej. libre).
  CONSTRAINT ck_transfer_distinct_teams CHECK (
    from_team_id IS DISTINCT FROM to_team_id
  ),
  -- Regla 14: libres → fee NULL; no usar 0
  CONSTRAINT ck_transfer_free_fee_null CHECK (
    transfer_type NOT IN ('free', 'end_of_contract')
    OR fee_amount IS NULL
  ),
  CONSTRAINT ck_transfer_fee_positive CHECK (
    fee_amount IS NULL OR fee_amount > 0
  ),
  CONSTRAINT ck_transfer_fee_currency CHECK (
    (fee_amount IS NULL AND fee_currency IS NULL)
    OR (fee_amount IS NOT NULL AND fee_currency IS NOT NULL)
  )
);

CREATE INDEX ix_transfer_player_id ON transfer (player_id);
CREATE INDEX ix_transfer_from_team_id ON transfer (from_team_id);
CREATE INDEX ix_transfer_to_team_id ON transfer (to_team_id);
CREATE INDEX ix_transfer_related_history_id ON transfer (related_history_id);
CREATE INDEX ix_transfer_effective_date ON transfer (effective_date);

COMMENT ON TABLE transfer IS
  'Movimiento de mercado. Debe sincronizar PLAYER_TEAM_HISTORY (regla 4). No sustituye HISTORY.';

COMMENT ON COLUMN transfer.related_history_id IS
  'Apunta SIEMPRE al spell de DESTINO creado/afectado por la transferencia (regla 4). Sync operativa en aplicación.';

COMMENT ON COLUMN transfer.fee_amount IS
  'NULL en free/end_of_contract. No usar 0 para gratuidad (regla 14).';

-- =============================================================================
-- 13. MARKET_VALUE_HISTORY
-- =============================================================================
CREATE TABLE market_value_history (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id       UUID NOT NULL REFERENCES player (id) ON DELETE RESTRICT,
  value_amount    NUMERIC(14, 2) NOT NULL,
  currency        currency_code NOT NULL,
  recorded_on     DATE NOT NULL,
  source          TEXT NOT NULL DEFAULT 'manual',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_market_value_player_date_source UNIQUE (player_id, recorded_on, source),
  CONSTRAINT ck_market_value_nonneg CHECK (value_amount >= 0),
  CONSTRAINT ck_market_value_source_nonempty CHECK (char_length(btrim(source)) > 0)
);

CREATE INDEX ix_market_value_history_player_id ON market_value_history (player_id);
CREATE INDEX ix_market_value_history_recorded_on ON market_value_history (recorded_on);

COMMENT ON TABLE market_value_history IS
  'Serie temporal de valor. Fuente de verdad del cache player.current_market_value.';

COMMENT ON COLUMN market_value_history.source IS
  'DEFAULT manual (regla 15). Texto extensible append-only (manual, ifl_model, import_x…).';

-- =============================================================================
-- 14. SLUG
-- =============================================================================
CREATE TABLE slug (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type     slug_entity_type NOT NULL,
  entity_id       UUID NOT NULL,
  locale          TEXT NOT NULL,
  slug            TEXT NOT NULL,
  is_primary      BOOLEAN NOT NULL DEFAULT TRUE,
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_slug_locale_slug UNIQUE (locale, slug),
  CONSTRAINT ck_slug_locale CHECK (locale ~ '^[a-z]{2}(-[A-Z]{2})?$'),
  CONSTRAINT ck_slug_format CHECK (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$')
);

-- Regla 16: máx. un primary por (entity_type, entity_id, locale)
CREATE UNIQUE INDEX uq_slug_one_primary_per_entity_locale
  ON slug (entity_type, entity_id, locale)
  WHERE is_primary = TRUE;

CREATE INDEX ix_slug_entity ON slug (entity_type, entity_id);

COMMENT ON TABLE slug IS
  'SEO polimórfico. Sin FK físicas a entidades (regla 16). No DELETE físico de entidades con slug público.';

COMMENT ON COLUMN slug.entity_id IS
  'UUID polimórfico controlado por entity_type. Integridad referencial en aplicación.';

COMMIT;

-- =============================================================================
-- FIN DDL MVP v1
-- =============================================================================
-- Conteos de referencia (post-correcciones auditoría final):
--   Tablas: 14
--   ENUM types: 20
--   FK: 29
--   UNIQUE de negocio: 7
--   CHECK: 34
--   Índices no-únicos: 32
-- =============================================================================
