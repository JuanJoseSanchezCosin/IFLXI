# IFLXI — Diseño físico PostgreSQL MVP v1

| Campo | Valor |
|---|---|
| Producto | IFL / IFLXI (Info Football Lab XI) |
| Versión | PostgreSQL físico MVP v1 |
| Estado | APTO PARA EJECUTAR EN POSTGRESQL MVP v1 (post-correcciones auditoría) |
| Script DDL | `sql/IFLXI-postgresql-MVP-v1.sql` |
| Fuentes congeladas | Diccionario MVP v1.1 + Anexo A · ER MVP v1.2 · 17 decisiones de negocio |
| Requisitos | PostgreSQL **13+** |

---

## 1. Alcance y principios

Este documento **materializa** el diccionario aprobado en DDL PostgreSQL.

| Permitido | Prohibido |
|---|---|
| Tipos, PK/FK, UNIQUE, CHECK, índices, comentarios | Nuevas entidades de negocio |
| ENUM / TEXT+CHECK para catálogos del diccionario | Renombrar / eliminar las 14 entidades |
| Documentar ambigüedades | Reinterpretar el Anexo A |
| | Triggers complejos de sync cache/transfer |
| | INSERT de datos de prueba |
| | Stats acumuladas en `player` |

**Nombres físicos:** tablas en `snake_case` minúsculas (`country`, `player_team_history`, …). Columnas según **diccionario** (`id`, `name_default`, …), no según etiquetas abreviadas del ER visual.

---

## 2. Decisiones de diseño global

### 2.1 PK: UUID consistente

| Decisión | Valor |
|---|---|
| Tipo PK | `UUID` en las 14 tablas |
| Generación | `DEFAULT gen_random_uuid()` |
| Extensión | `CREATE EXTENSION IF NOT EXISTS pgcrypto` (compatibilidad; en PG 13+ `gen_random_uuid` es nativo) |
| Alternativa descartada | `BIGINT` serial — el diccionario fija UUID como tipo lógico |

### 2.2 Timestamps y fechas

| Campo | Tipo | Motivo |
|---|---|---|
| `created_at` / `updated_at` | `TIMESTAMPTZ` | Auditoría con zona horaria |
| `kickoff_at` | `TIMESTAMPTZ` | Instante real del saque (regla de producto) |
| `match_date`, `start_date`, `end_date`, `recorded_on`, … | `DATE` | Día civil |
| Convención | Almacenar instantes en **UTC** | Consistencia multi-país |

**Nota:** no hay trigger de auto-`updated_at` en MVP (responsabilidad de aplicación/carga).

### 2.3 Monetario

`NUMERIC(14, 2)` para `fee_amount`, `value_amount`, `current_market_value`.

### 2.4 TEXT vs VARCHAR

Se usa `TEXT` salvo longitudes fijas ISO (`CHAR(2)` / `CHAR(3)`).

### 2.5 ON DELETE

Política por defecto: **`ON DELETE RESTRICT`** en FKs de entidades núcleo.

| Excepción | Política | Motivo |
|---|---|---|
| `player.current_team_id` | `ON DELETE SET NULL` | Es **cache**; si un team se desactivara/eliminara en escenario excepcional, no debe romper el player |
| Entidades con slug público | No DELETE físico en MVP | Soft via `is_active` / estados |
| `slug` | Sin FK físicas | Polimorfismo (regla 16) |

**No se usa `CASCADE`** en eliminaciones de `player`, `team`, `competition`, `season`, `match`.

### 2.6 Caches

| Columna | Fuente de verdad |
|---|---|
| `player.current_team_id` | `player_team_history` (spell club abierto) |
| `player.current_market_value` (+ currency) | `market_value_history` (último `recorded_on`) |

Comentarios SQL `COMMENT ON COLUMN` documentan esto. **Sin triggers de sync en esta fase.**

---

## 3. Catálogos / ENUM

Estrategia MVP: **ENUM PostgreSQL** para conjuntos cerrados del diccionario. Conceptualmente **append-only** (`ALTER TYPE ... ADD VALUE` en el futuro; no cambiar significado).

| Tipo ENUM | Valores | Origen |
|---|---|---|
| `continent_code` | AF AS EU NA SA OC AN | COUNTRY |
| `competition_type` | league cup international_club international_national playoff other | COMPETITION |
| `competition_scope` | domestic continental world | COMPETITION |
| `gender_competition` | male female mixed | COMPETITION / TEAM |
| `age_category_competition` | senior u23 u21 u19 u17 other | COMPETITION |
| `age_category_team` | senior u23 u21 u19 u17 b_team other | TEAM |
| `sport_code` | football | COMPETITION |
| `team_kind` | club national | TEAM |
| `team_competition_status` | registered withdrawn disqualified | TEAM_COMPETITION |
| `person_gender` | male female other unknown | PERSON |
| `player_position` | GK CB LB RB LWB RWB CDM CM CAM LM RM LW RW CF ST | PLAYER *(ver D-POS-01)* |
| `player_foot` | left right both unknown | PLAYER |
| `player_status` | active retired deceased unknown | PLAYER |
| `history_role` | permanent loan loan_return trial youth unknown | HISTORY |
| `match_status` | scheduled **live** finished postponed cancelled awarded | MATCH (`live` reservado) |
| `event_type` | goal own_goal penalty_goal penalty_miss yellow_card red_card second_yellow **substitution_out** | MATCH_EVENT *(sin assist; sin substitution_in — D-SUB-01)* |
| `event_period` | first_half second_half extra_first extra_second penalty_shootout unknown | MATCH_EVENT |
| `transfer_type` | permanent loan loan_end free end_of_contract academy_promotion unknown | TRANSFER |
| `currency_code` | EUR USD GBP | montos / cache |
| `slug_entity_type` | player team competition match transfer season | SLUG |

**No ENUM (TEXT + DEFAULT/CHECK):**

| Campo | Estrategia | Motivo |
|---|---|---|
| `market_value_history.source` | `TEXT NOT NULL DEFAULT 'manual'` | Extensible sin migración de tipo |
| `slug.locale` | `TEXT` + CHECK patrón | Añadir locales sin `ALTER TYPE` |
| `slug.slug` | `TEXT` + CHECK formato | Normalización URL |

**Total ENUM creados: 20**

---

## 4. Ambigüedades documentadas (sin inventar)

### D-SUB-01 — `substitution_in` (cerrado)

| Fuente | Dice |
|---|---|
| Diccionario MATCH_EVENT | Catálogo incluye `substitution_in` y `substitution_out` |
| Regla 12 congelada (prioridad) | Solo `substitution_out` |

**Decisión física definitiva MVP v1:**

> D-SUB-01 / Regla 12:  
> MVP utiliza exclusivamente `substitution_out`.  
> `player_id` = jugador que sale.  
> `secondary_player_id` = jugador que entra.  
> `substitution_in` no se utiliza.  
> `assist` no existe como `event_type`; las asistencias se representan mediante `secondary_player_id` en `goal`/`penalty_goal`.

El ENUM `event_type` **no incluye** `substitution_in` ni `assist`. El diccionario no se modifica; la decisión congelada tiene prioridad.

### D-POS-01 — posiciones con “…”

El diccionario lista posiciones con ellipsis. Se cierra un set MVP explícito (ver tabla ENUM). Ampliable con `ALTER TYPE ... ADD VALUE`.

### D-CARD-01 — tarjetas (resuelto por regla 11)

Anexo A.7 dejaba abierto si `second_yellow` suma amarilla. **Regla 11 congelada:** amarillas = solo `yellow_card`; rojas = `red_card` + `second_yellow`. Documentado en `COMMENT`; no requiere tabla nueva.

### D-RELHIST-01 — `related_history_id` NULLABLE

Diccionario: campo opcional. Regla 4: sync obligatoria en operativa. **Físico:** columna NULLABLE + comentario; la obligatoriedad operativa queda en checklist de carga (no `NOT NULL` para no bloquear borradores incompletos).

### D-ER-NAMES — nombres ER vs diccionario

El ER visual usa etiquetas (`country_id` como PK, `name`, …). **Gana el diccionario:** PK = `id`, nombres = `name_default`, etc.

---

## 5. Tablas (14)

### 5.1 `country`

**Propósito:** Territorio/nación normalizado.

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| iso2 | CHAR(2) | NO | | UK natural |
| iso3 | CHAR(3) | SÍ | | |
| fifa_code | CHAR(3) | SÍ | | |
| name_default | TEXT | NO | | |
| continent_code | continent_code | SÍ | | |
| is_active | BOOLEAN | NO | TRUE | |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

- **UNIQUE:** `iso2`
- **CHECK:** longitudes iso2/iso3/fifa
- **FK:** —
- **Índices extra:** —
- **Reglas:** A.8 (no Free Agent team); base geo

---

### 5.2 `city`

**Propósito:** Localidad → país.

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| country_id | UUID | NO | | FK → country RESTRICT |
| name_default | TEXT | NO | | |
| latitude / longitude | NUMERIC(9,6) | SÍ | | |
| is_active | BOOLEAN | NO | TRUE | |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

- **UNIQUE:** —
- **CHECK:** rangos lat/lon
- **Índices:** `ix_city_country_id`

---

### 5.3 `competition`

**Propósito:** Marca de competición atemporal.

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| name_default | TEXT | NO | | |
| short_name | TEXT | SÍ | | |
| competition_type | competition_type | NO | | |
| scope | competition_scope | NO | | |
| country_id | UUID | SÍ | | FK → country (domésticas) |
| governing_body | TEXT | SÍ | | |
| gender | gender_competition | NO | | |
| age_category | age_category_competition | NO | senior | |
| sport_code | sport_code | NO | football | |
| is_active | BOOLEAN | NO | TRUE | Soft-delete operativo |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

- **Índices:** `ix_competition_country_id`
- **ON DELETE:** RESTRICT en country

---

### 5.4 `season`

**Propósito:** Edición temporal de una competición.

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| competition_id | UUID | NO | | FK → competition RESTRICT |
| name_default | TEXT | NO | | ej. 2025/26 |
| year_start / year_end | INTEGER | NO | | |
| start_date / end_date | DATE | SÍ | | |
| is_current | BOOLEAN | NO | FALSE | Regla 7 |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

- **UNIQUE parcial:** `uq_season_one_current_per_competition` ON `(competition_id) WHERE is_current`
- **CHECK:** `year_start <= year_end`; fechas coherentes
- **Índices:** `ix_season_competition_id`
- **Reglas:** A.5 / regla 7

---

### 5.5 `team`

**Propósito:** Club o selección.

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| name_default | TEXT | NO | | |
| short_name / code | TEXT | SÍ | | |
| team_kind | team_kind | NO | | club \| national |
| gender | gender_competition | NO | | |
| age_category | age_category_team | NO | senior | incluye b_team |
| country_id | UUID | NO | | FK → country |
| city_id | UUID | SÍ | | FK → city |
| parent_team_id | UUID | SÍ | | FK → team (filial) |
| founded_year | INTEGER | SÍ | | |
| is_active | BOOLEAN | NO | TRUE | Preferir desactivar a borrar |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

- **CHECK:** founded_year rango; parent ≠ self
- **Índices:** country, city, parent
- **Reglas:** A.2 — **no** crear team Free Agent

---

### 5.6 `team_competition`

**Propósito:** N:M TEAM ↔ SEASON (única vía).

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| team_id | UUID | NO | | FK → team |
| season_id | UUID | NO | | FK → season |
| status | team_competition_status | NO | registered | |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

- **UNIQUE:** `(team_id, season_id)`
- **Índices:** `ix_team_competition_season_id`
- **Reglas:** no relación directa TEAM–SEASON

---

### 5.7 `person`

**Propósito:** Identidad humana.

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| full_name | TEXT | NO | | |
| display_name | TEXT | NO | | |
| first_name / last_name | TEXT | SÍ | | |
| birth_date | DATE | SÍ | | edad calculada |
| birth_country_id | UUID | SÍ | | FK → country |
| birth_city_id | UUID | SÍ | | FK → city |
| gender | person_gender | SÍ | | |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

- Nacionalidad de ficha vive en **`player.nationality_country_id`** (diccionario), no aquí.

---

### 5.8 `player`

**Propósito:** Rol futbolístico. Entidad central.

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| person_id | UUID | NO | | FK → person; **UNIQUE** (1:0..1) |
| nationality_country_id | UUID | SÍ | | FK → country |
| primary_position / secondary_position | player_position | SÍ | | |
| foot | player_foot | SÍ | | |
| height_cm / weight_kg | INTEGER | SÍ | | |
| shirt_name | TEXT | SÍ | | |
| status | player_status | NO | active | |
| current_team_id | UUID | SÍ | | **CACHE** FK → team SET NULL |
| current_market_value | NUMERIC(14,2) | SÍ | | **CACHE** |
| current_market_value_currency | currency_code | SÍ | | **CACHE** |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

- **CHECK:** altura/peso; coherencia value+currency; value ≥ 0
- **Índices:** current_team, nationality (+ UNIQUE person_id)
- **Reglas:** 2, 3, 17 — sin columnas de stats

---

### 5.9 `player_team_history`

**Propósito:** Spell de pertenencia (fuente de verdad de club actual).

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| player_id | UUID | NO | | FK → player |
| team_id | UUID | NO | | FK → team |
| role | history_role | NO | permanent | loan → cesión |
| start_date | DATE | NO | | |
| end_date | DATE | SÍ | | NULL = vigente |
| shirt_number | INTEGER | SÍ | | |
| on_loan_from_team_id | UUID | SÍ | | FK → team; obligatorio si loan |
| notes | TEXT | SÍ | | |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

- **CHECK:** `start_date <= end_date` (regla 6); `ck_history_loan_from`: si `role=loan` → `on_loan_from` NOT NULL y ≠ `team_id`; si `role<>loan` → `on_loan_from` IS NULL
- **Índices:** player, team, on_loan_from; parcial abiertos `(player_id, team_id) WHERE end_date IS NULL`
- **Regla 13 (app):** máx. un club abierto; club+selección OK — **no enforceable con CHECK simple** sin join a `team.team_kind`

---

### 5.10 `match`

**Propósito:** Encuentro + marcador oficial.

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| season_id | UUID | NO | | FK → season |
| home_team_id / away_team_id | UUID | NO | | FK → team |
| match_date | DATE | NO | | |
| kickoff_at | TIMESTAMPTZ | SÍ | | Decisión: TIMESTAMPTZ |
| round_name | TEXT | SÍ | | |
| status | match_status | NO | scheduled | |
| home_score / away_score | INTEGER | SÍ | | acta oficial |
| venue_city_id | UUID | SÍ | | FK → city |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

- **CHECK:** teams distintos; scores ≥ 0; **finished|awarded ⇒ scores NOT NULL** (regla 8)
- **Índices:** season, home, away, match_date
- **Reglas:** scores ≠ suma automática de eventos

---

### 5.11 `match_event`

**Propósito:** Hechos atómicos; fuente de stats MVP.

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| match_id | UUID | NO | | FK → match |
| event_type | event_type | NO | | sin assist / sin substitution_in |
| player_id | UUID | SÍ* | | *obligatorio en tipos regla 9 |
| secondary_player_id | UUID | SÍ | | asistente / entra |
| team_id | UUID | NO | | atribución; own_goal = sufre |
| minute / extra_minute | INTEGER | SÍ | | |
| period | event_period | SÍ | | |
| sort_order | INTEGER | SÍ | | |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

- **CHECK:** player requerido (regla 9); substitution_out exige ambos jugadores (regla 12); secondary solo en goal/penalty_goal/substitution_out; own_goal sin secondary (regla 10)
- **Índices:** match, player, secondary, team, event_type
- **Reglas:** 1, 9, 10, 11, 12, 17

---

### 5.12 `transfer`

**Propósito:** Movimiento de mercado; complementa HISTORY.

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| player_id | UUID | NO | | FK → player |
| from_team_id / to_team_id | UUID | SÍ | | FK → team |
| transfer_type | transfer_type | NO | | |
| announced_date | DATE | SÍ | | |
| effective_date | DATE | NO | | |
| fee_amount | NUMERIC(14,2) | SÍ | | |
| fee_currency | currency_code | SÍ | | |
| fee_is_estimated | BOOLEAN | NO | FALSE | |
| related_history_id | UUID | SÍ | | FK → history; **destino** |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

- **CHECK:** `from_team_id IS DISTINCT FROM to_team_id` (permite NULL); free/end_of_contract ⇒ fee NULL; fee > 0 si presente; currency coherente (regla 14)
- **Índices:** player, from, to, related_history, effective_date
- **Reglas:** 4 — sync HISTORY en aplicación; `related_history_id` = spell destino

---

### 5.13 `market_value_history`

**Propósito:** Serie de valor; fuente del cache.

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| player_id | UUID | NO | | FK → player |
| value_amount | NUMERIC(14,2) | NO | | |
| currency | currency_code | NO | | |
| recorded_on | DATE | NO | | |
| source | TEXT | NO | **'manual'** | Regla 15 |
| created_at | TIMESTAMPTZ | NO | now() | sin updated_at (diccionario) |

- **UNIQUE:** `(player_id, recorded_on, source)`
- **Índices:** player_id, recorded_on

---

### 5.14 `slug`

**Propósito:** SEO polimórfico transversal.

| Columna | Tipo | Nulo | Default | Notas |
|---|---|---|---|---|
| id | UUID | NO | gen_random_uuid() | PK |
| entity_type | slug_entity_type | NO | | |
| entity_id | UUID | NO | | sin FK física |
| locale | TEXT | NO | | CHECK patrón |
| slug | TEXT | NO | | CHECK formato |
| is_primary | BOOLEAN | NO | TRUE | |
| is_active | BOOLEAN | NO | TRUE | |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

- **UNIQUE:** `(locale, slug)`
- **UNIQUE parcial:** un primary por `(entity_type, entity_id, locale)` WHERE `is_primary`
- **Índices:** `(entity_type, entity_id)`
- **Reglas:** 16 — no DELETE físico de entidades publicadas

---

## 6. Resumen de relaciones FK

| # | Desde | Columna | Hacia | ON DELETE |
|---|---|---|---|---|
| 1 | city | country_id | country | RESTRICT |
| 2 | competition | country_id | country | RESTRICT |
| 3 | season | competition_id | competition | RESTRICT |
| 4 | team | country_id | country | RESTRICT |
| 5 | team | city_id | city | RESTRICT |
| 6 | team | parent_team_id | team | RESTRICT |
| 7 | team_competition | team_id | team | RESTRICT |
| 8 | team_competition | season_id | season | RESTRICT |
| 9 | person | birth_country_id | country | RESTRICT |
| 10 | person | birth_city_id | city | RESTRICT |
| 11 | player | person_id | person | RESTRICT |
| 12 | player | nationality_country_id | country | RESTRICT |
| 13 | player | current_team_id | team | **SET NULL** |
| 14 | player_team_history | player_id | player | RESTRICT |
| 15 | player_team_history | team_id | team | RESTRICT |
| 16 | player_team_history | on_loan_from_team_id | team | RESTRICT |
| 17 | match | season_id | season | RESTRICT |
| 18 | match | home_team_id | team | RESTRICT |
| 19 | match | away_team_id | team | RESTRICT |
| 20 | match | venue_city_id | city | RESTRICT |
| 21 | match_event | match_id | match | RESTRICT |
| 22 | match_event | player_id | player | RESTRICT |
| 23 | match_event | secondary_player_id | player | RESTRICT |
| 24 | match_event | team_id | team | RESTRICT |
| 25 | transfer | player_id | player | RESTRICT |
| 26 | transfer | from_team_id | team | RESTRICT |
| 27 | transfer | to_team_id | team | RESTRICT |
| 28 | transfer | related_history_id | player_team_history | RESTRICT |
| 29 | market_value_history | player_id | player | RESTRICT |

**Total FK: 29**  
**SLUG:** 0 FK (polimórfico intencional).

---

## 7. Índices (no PK)

### 7.1 Únicos de negocio (además de PK)

| Nombre | Definición | Motivo |
|---|---|---|
| uq_country_iso2 | UNIQUE(iso2) | Clave natural |
| uq_season_one_current_per_competition | UNIQUE(competition_id) WHERE is_current | Regla 7 |
| uq_team_competition_team_season | UNIQUE(team_id, season_id) | A.9 |
| uq_player_person_id | UNIQUE(person_id) | 1:0..1 |
| uq_market_value_player_date_source | UNIQUE(player_id, recorded_on, source) | Regla 15 |
| uq_slug_locale_slug | UNIQUE(locale, slug) | Regla 16 |
| uq_slug_one_primary_per_entity_locale | UNIQUE(entity_type, entity_id, locale) WHERE is_primary | Regla 16 |

**Total UNIQUE de negocio: 7**

### 7.2 Índices no únicos

| Índice | Motivo |
|---|---|
| ix_city_country_id | Join geo |
| ix_competition_country_id | Filtro domésticas |
| ix_season_competition_id | Listado ediciones |
| ix_team_country_id / city_id / parent_team_id | Navegación club |
| ix_team_competition_season_id | Plantilla de season |
| ix_person_birth_country_id / birth_city_id | Filtros demográficos |
| ix_player_current_team_id | Plantilla vía cache |
| ix_player_nationality_country_id | Filtro ficha |
| ix_player_team_history_player_id / team_id / on_loan_from | Pedidos mínimos + cesiones |
| ix_player_team_history_open_spells | Plantilla / libre agente (parcial) |
| ix_match_season_id / home / away / match_date | Calendario |
| ix_match_event_match_id / player_id / secondary / team_id / type | Stats MVP |
| ix_transfer_player / from / to / related_history / effective_date | Mercado |
| ix_market_value_history_player_id / recorded_on | Serie + cache |
| ix_slug_entity | Lookup por entidad |

**Nota:** `UNIQUE(person_id)` y FKs indexadas por PostgreSQL en PK; no se duplica índice en `player(person_id)` más allá del UNIQUE.

---

## 8. Constraints CHECK (resumen)

| Tabla | Constraint | Regla |
|---|---|---|
| country | longitudes ISO | diccionario |
| city | lat/lon | integridad |
| season | años/fechas | diccionario |
| team | founded_year; parent≠self | integridad |
| player | height/weight; cache currency; value≥0 | A.3 |
| player_team_history | fechas; loan+on_loan_from (completo: null si no loan) | 5, 6 |
| match | teams distintos; scores; finished/awarded | 8 |
| match_event | player required; sub_out; secondary usage; own_goal | 1,9,10,12 |
| transfer | from IS DISTINCT FROM to; free fee null; fee>0; currency | 14 |
| market_value_history | value≥0; source nonempty | 15 |
| slug | locale/slug format | 16 |

---

## 9. Reglas que quedan en aplicación (no CHECK simple)

| Regla | Motivo |
|---|---|
| Regla 2 — libre agente = sin history club abierto + cache null | Requiere join `team.team_kind` |
| Regla 4 — sync TRANSFER↔HISTORY en cada tipo | Secuencia multi-fila |
| Regla 13 — máx. un club abierto; club+selección OK | Join a `team_kind` |
| Regla 3 — no editar caches a mano | Procedimiento de carga |
| Regla 16 — no DELETE entidades con slug | Política operativa |
| retired/deceased ⇒ cerrar clubs abiertos | Anexo A.2 |
| Coherencia soft goles-evento vs marcador | A.6 warning futuro |

---

## 10. Orden de creación

1. Extensión + ENUMs  
2. country → city → competition → season → team → team_competition  
3. person → player → player_team_history  
4. match → match_event  
5. transfer → market_value_history → slug  

Coincide con el diccionario; `player.current_team_id` puede referenciar `team` porque `team` ya existe.

---

## 11. Checklist de integridad MVP v1 (17 decisiones)

| # | Decisión | Materialización |
|---|---|---|
| 1 | Sin `assist`; asistencia = `secondary_player_id` en goal/penalty_goal | ENUM sin assist + CHECK secondary_usage |
| 2 | Libre sin team Free Agent; cache null + sin club abierto | COMMENT team; cache nullable; regla app |
| 3 | Caches player derivados | COMMENT ON COLUMN; sin triggers |
| 4 | TRANSFER sync HISTORY; related_history = destino | COMMENT; FK related_history_id; app |
| 5 | Cesión role=loan + on_loan_from; un club abierto | CHECK loan completo (on_loan null si no loan); regla 13 en app |
| 6 | start_date ≤ end_date; NULL=vigente | CHECK fechas |
| 7 | Una season current / competition | UNIQUE parcial |
| 8 | Scores oficiales; finished/awarded obligatorios; live reservado | CHECK scores; ENUM+COMMENT |
| 9 | player_id obligatorio en goles/disciplina | CHECK |
| 10 | own_goal: player marca; team sufre | COMMENT + no secondary |
| 11 | Amarillas=yellow; rojas=red+second_yellow | COMMENT |
| 12 | Solo substitution_out | ENUM + CHECK ambos jugadores; D-SUB-01 cerrado |
| 13 | Club+selección OK; 2 clubs NO | Documentado app |
| 14 | Free ⇒ fee NULL; no usar 0; from ≠ to | CHECK fee + ck_transfer_distinct_teams |
| 15 | UNIQUE(player, recorded_on, source); source default manual | CONSTRAINT + DEFAULT |
| 16 | UNIQUE(locale,slug); un primary; sin FK slug; no delete público | UNIQUE + parcial + COMMENT |
| 17 | Stats solo desde eventos; no acumular en PLAYER | Sin columnas stats |

---

## 12. Autorevisión del SQL

| Chequeo | Resultado |
|---|---|
| 14 tablas | OK |
| FK del ER presentes | OK (29); slug sin FK intencional |
| PERSON→PLAYER 1:0..1 | UNIQUE(person_id) |
| MATCH home/away | 2 FK a team |
| related_history_id | FK a player_team_history |
| NULL incorrectos | Scores nullable salvo finished/awarded; fee nullable |
| CHECK contradictorios | No detectados |
| UNIQUE | Alineados A.9 + reglas 7/15/16 |
| Índices duplicados | Evitados (person_id solo via UNIQUE) |
| Nombres | Diccionario (`name_default`, `value_amount`, …) |
| Anexo A no reflejado en DDL | Solo reglas multi-fila / join (sección 9) |

---

## 13. Conteos de entrega

| Métrica | Cantidad |
|---|---|
| Tablas | **14** |
| Tipos ENUM | **20** |
| Foreign keys | **29** |
| UNIQUE de negocio (constraints + índices únicos parciales) | **7** |
| Constraints CHECK con nombre | **34** |
| Índices no únicos | **32** |
| Extensiones | **1** (`pgcrypto`) |

---

## 14. Cómo revisar / ejecutar

```bash
# Revisar (dry) en local
psql -v ON_ERROR_STOP=1 -f sql/IFLXI-postgresql-MVP-v1.sql
```

1. Revisar este MD + SQL con el equipo.  
2. Resolver D-SUB-01 si se desea alinear ENUM al catálogo literal del diccionario.  
3. Ejecutar DDL en entorno vacío.  
4. Siguiente fase sugerida: guía de carga manual + dataset seed mínimo (fuera de este entregable).

---

**Frase de control:**  
Si un número se puede contar desde eventos o histories, no se digita como verdad en `player` / `team`.
