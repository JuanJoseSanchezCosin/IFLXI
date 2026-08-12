# IFLXI — Diccionario de datos MVP v1

**Producto:** IFL / IFLXI (Info Football Lab XI)  
**Versión:** MVP v1.1 (diccionario + reglas de negocio)  
**Estado:** Aprobado para diseñar SQL tras este documento  
**Equipo:** desarrollo + analista/implementación de datos  
**Fuera de alcance de este documento:** SQL, PostgreSQL físico, código de aplicación

---

## Control de cambios

| Versión | Fecha | Cambio |
|---|---|---|
| MVP v1.0 | 2026-08-07 | Diccionario inicial de entidades MVP |
| MVP v1.1 | 2026-08-07 | Incorporación de 7 cambios obligatorios + **Anexo A — Reglas de negocio** |

### Cambios incorporados en v1.1

1. Modelo único de asistencias en `MATCH_EVENT` (sin doble conteo).  
2. Definición de jugador sin club / libre agente.  
3. Contrato de caches en `PLAYER`.  
4. Sincronía obligatoria `TRANSFER` ↔ `PLAYER_TEAM_HISTORY`.  
5. Como máximo una `SEASON.is_current = true` por competición.  
6. Marcador oficial de `MATCH` vs detalle de eventos.  
7. Alcance explícito de estadísticas publicables en MVP.

El detalle normativo está en el **Anexo A**. Las entidades más abajo ya reflejan esos criterios.

---

## Principios

1. Los **hechos** viven en tablas base.  
2. Los **cálculos** no se almacenan como verdad.  
3. Todo lo que depende del tiempo tiene **historial** o serie temporal.  
4. No duplicar información derivable por relaciones.  
5. MVP simple, preparado para crecer 10 años sin migraciones destructivas.  
6. Caches permitidos solo si están **gobernados** (Anexo A.3).

### Equivalencias con arquitectura larga

| MVP v1 | Arquitectura 10 años |
|---|---|
| `SEASON` | `COMPETITION_EDITION` |
| `TEAM_COMPETITION` | `TEAM_COMPETITION_ENTRY` |
| `PLAYER_TEAM_HISTORY` | `PLAYER_TEAM_SPELL` |
| `MARKET_VALUE_HISTORY` | `MARKET_VALUE_SNAPSHOT` |
| `SLUG` | `ENTITY_SLUG` |

---

# GEO

## ENTIDAD: COUNTRY

**Descripción:**  
Territorio o nación usada para nacionalidades, sedes de equipos y contexto de competiciones.

**Objetivo:**  
Normalizar países para evitar variantes de texto (“Spain / España / ESP”).

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador interno estable.  
**Ejemplo:** `b2c1e0a4-1111-4a2b-9c3d-000000000001`

**Campo:** `iso2`  
**Tipo lógico:** texto (2)  
**Obligatorio:** Sí  
**Descripción:** Código ISO 3166-1 alpha-2. Clave natural de negocio. Único.  
**Ejemplo:** `ES`

**Campo:** `iso3`  
**Tipo lógico:** texto (3)  
**Obligatorio:** No  
**Descripción:** Código ISO alpha-3.  
**Ejemplo:** `ESP`

**Campo:** `fifa_code`  
**Tipo lógico:** texto (3)  
**Obligatorio:** No  
**Descripción:** Código FIFA si aporta claridad deportiva.  
**Ejemplo:** `ESP`

**Campo:** `name_default`  
**Tipo lógico:** texto  
**Obligatorio:** Sí  
**Descripción:** Nombre canónico de trabajo.  
**Ejemplo:** `Spain`

**Campo:** `continent_code`  
**Tipo lógico:** catálogo (`AF`,`AS`,`EU`,`NA`,`SA`,`OC`,`AN`)  
**Obligatorio:** No  
**Descripción:** Continente sin tabla CONTINENT en MVP.  
**Ejemplo:** `EU`

**Campo:** `is_active`  
**Tipo lógico:** boolean  
**Obligatorio:** Sí (default true)  
**Descripción:** Disponibilidad en formularios/carga.  
**Ejemplo:** `true`

**Campo:** `created_at` / `updated_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Auditoría básica.

**Relaciones:**
- 1 COUNTRY → N CITY
- 1 COUNTRY → N TEAM
- 1 COUNTRY → N PERSON / PLAYER (nacimiento / nacionalidad de ficha)

**Campos que NO deben estar aquí:**  
`player_count`, `club_count`, listas de ligas.  
**Explicación:** Agregados calculables.

---

## ENTIDAD: CITY

**Descripción:**  
Localidad geográfica vinculada a un país.

**Objetivo:**  
Sedes y lugares de nacimiento sin texto libre caótico.

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador interno.

**Campo:** `country_id`  
**Tipo lógico:** UUID (FK → COUNTRY)  
**Obligatorio:** Sí  
**Descripción:** País al que pertenece.

**Campo:** `name_default`  
**Tipo lógico:** texto  
**Obligatorio:** Sí  
**Descripción:** Nombre canónico.  
**Ejemplo:** `Barcelona`

**Campo:** `latitude` / `longitude`  
**Tipo lógico:** decimal  
**Obligatorio:** No  
**Descripción:** Coordenadas futuras.

**Campo:** `is_active`  
**Tipo lógico:** boolean  
**Obligatorio:** Sí  
**Descripción:** Disponibilidad en carga.

**Campo:** `created_at` / `updated_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Auditoría.

**Relaciones:**
- N CITY → 1 COUNTRY
- 1 CITY → N TEAM / PERSON / MATCH (sede opcional)

**Campos que NO deben estar aquí:**  
nombre del país en texto.

---

# COMPETICIONES

## ENTIDAD: COMPETITION

**Descripción:**  
Competición “marca” atemporal (LaLiga, UCL, Mundial…).

**Objetivo:**  
Separar la competición de cada edición/temporada. `/competition/la-liga` apunta aquí.

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador interno.

**Campo:** `name_default`  
**Tipo lógico:** texto  
**Obligatorio:** Sí  
**Descripción:** Nombre canónico.  
**Ejemplo:** `LaLiga EA Sports`

**Campo:** `short_name`  
**Tipo lógico:** texto  
**Obligatorio:** No  
**Descripción:** Abreviatura UI.  
**Ejemplo:** `LaLiga`

**Campo:** `competition_type`  
**Tipo lógico:** catálogo (`league`,`cup`,`international_club`,`international_national`,`playoff`,`other`)  
**Obligatorio:** Sí  
**Descripción:** Tipo estructural.  
**Ejemplo:** `league`

**Campo:** `scope`  
**Tipo lógico:** catálogo (`domestic`,`continental`,`world`)  
**Obligatorio:** Sí  
**Descripción:** Ámbito.  
**Ejemplo:** `domestic`

**Campo:** `country_id`  
**Tipo lógico:** UUID (FK → COUNTRY)  
**Obligatorio:** No  
**Descripción:** País si es doméstica; null en Champions/Mundial.

**Campo:** `governing_body`  
**Tipo lógico:** texto  
**Obligatorio:** No  
**Descripción:** Organismo (UEFA, FIFA, RFEF…).  
**Ejemplo:** `RFEF / LFP`

**Campo:** `gender`  
**Tipo lógico:** catálogo (`male`,`female`,`mixed`)  
**Obligatorio:** Sí  
**Descripción:** Rama competitiva.  
**Ejemplo:** `male`

**Campo:** `age_category`  
**Tipo lógico:** catálogo (`senior`,`u23`,`u21`,`u19`,`u17`,`other`)  
**Obligatorio:** Sí (default `senior`)  
**Descripción:** Categoría de edad.  
**Ejemplo:** `senior`

**Campo:** `sport_code`  
**Tipo lógico:** catálogo  
**Obligatorio:** Sí (default `football`)  
**Descripción:** Puerta a otros deportes.  
**Ejemplo:** `football`

**Campo:** `is_active`  
**Tipo lógico:** boolean  
**Obligatorio:** Sí  
**Descripción:** Si sigue vigente.

**Campo:** `created_at` / `updated_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Auditoría.

**Relaciones:**
- 1 COMPETITION → N SEASON
- 0..1 COUNTRY → N COMPETITION

**Campos que NO deben estar aquí:**  
`season_year`, `champion_team_id`, clasificación.

---

## ENTIDAD: SEASON

**Descripción:**  
Edición concreta de una competición (LaLiga 2025/26).

**Objetivo:**  
Anclar partidos, participantes y futuros agregados a un ciclo temporal.

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador interno.

**Campo:** `competition_id`  
**Tipo lógico:** UUID (FK → COMPETITION)  
**Obligatorio:** Sí  
**Descripción:** Competición padre.

**Campo:** `name_default`  
**Tipo lógico:** texto  
**Obligatorio:** Sí  
**Descripción:** Etiqueta de edición.  
**Ejemplo:** `2025/26`

**Campo:** `year_start`  
**Tipo lógico:** entero  
**Obligatorio:** Sí  
**Descripción:** Año civil de inicio.  
**Ejemplo:** `2025`

**Campo:** `year_end`  
**Tipo lógico:** entero  
**Obligatorio:** Sí  
**Descripción:** Año civil de fin.  
**Ejemplo:** `2026`

**Campo:** `start_date` / `end_date`  
**Tipo lógico:** fecha  
**Obligatorio:** No  
**Descripción:** Ventana real si se conoce.

**Campo:** `is_current`  
**Tipo lógico:** boolean  
**Obligatorio:** Sí (default false)  
**Descripción:** Edición vigente de esa competición.  
**Regla v1.1:** como máximo **una** season con `is_current = true` por cada `competition_id` (Anexo A.5).  
**Ejemplo:** `true`

**Campo:** `created_at` / `updated_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Auditoría.

**Relaciones:**
- N SEASON → 1 COMPETITION
- 1 SEASON → N TEAM_COMPETITION
- 1 SEASON → N MATCH

**Campos que NO deben estar aquí:**  
lista de equipos, clasificación, goleadores.

---

# EQUIPOS

## ENTIDAD: TEAM

**Descripción:**  
Unidad competitiva: club, filial, femenino, cantera o selección.

**Objetivo:**  
Soportar `/club/real-madrid` y, sin rehacer, selecciones y categorías.

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador interno.

**Campo:** `name_default`  
**Tipo lógico:** texto  
**Obligatorio:** Sí  
**Descripción:** Nombre completo.  
**Ejemplo:** `Real Madrid CF`

**Campo:** `short_name`  
**Tipo lógico:** texto  
**Obligatorio:** No  
**Descripción:** Nombre corto.  
**Ejemplo:** `Real Madrid`

**Campo:** `code`  
**Tipo lógico:** texto  
**Obligatorio:** No  
**Descripción:** Código corto.  
**Ejemplo:** `RMA`

**Campo:** `team_kind`  
**Tipo lógico:** catálogo (`club`,`national`)  
**Obligatorio:** Sí  
**Descripción:** Club o selección.  
**Ejemplo:** `club`

**Campo:** `gender`  
**Tipo lógico:** catálogo (`male`,`female`,`mixed`)  
**Obligatorio:** Sí  
**Descripción:** Rama.  
**Ejemplo:** `male`

**Campo:** `age_category`  
**Tipo lógico:** catálogo (`senior`,`u23`,`u21`,`u19`,`u17`,`b_team`,`other`)  
**Obligatorio:** Sí (default `senior`)  
**Descripción:** Nivel / filial.  
**Ejemplo:** `senior`

**Campo:** `country_id`  
**Tipo lógico:** UUID (FK → COUNTRY)  
**Obligatorio:** Sí  
**Descripción:** País del club o de la selección.

**Campo:** `city_id`  
**Tipo lógico:** UUID (FK → CITY)  
**Obligatorio:** No  
**Descripción:** Ciudad sede.

**Campo:** `parent_team_id`  
**Tipo lógico:** UUID (FK → TEAM)  
**Obligatorio:** No  
**Descripción:** Filial → equipo padre.

**Campo:** `founded_year`  
**Tipo lógico:** entero  
**Obligatorio:** No  
**Descripción:** Año de fundación.

**Campo:** `is_active`  
**Tipo lógico:** boolean  
**Obligatorio:** Sí  
**Descripción:** Operativo o histórico.

**Campo:** `created_at` / `updated_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Auditoría.

**Relaciones:**
- N TEAM → 1 COUNTRY
- 1 TEAM → N TEAM_COMPETITION
- 1 TEAM → N PLAYER_TEAM_HISTORY
- 1 TEAM → N MATCH / TRANSFER

**Campos que NO deben estar aquí:**  
`coach_name` como verdad, `competition_id` único, plantilla embebida, puntos de clasificación.  
**Explicación:** Entrenador = fase COACH; competiciones = TEAM_COMPETITION; plantilla = histories abiertas.

---

## ENTIDAD: TEAM_COMPETITION

**Descripción:**  
Inscripción de un TEAM en una SEASON.

**Objetivo:**  
Participación real por edición (Liga + Champions, etc.).

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador interno.

**Campo:** `team_id`  
**Tipo lógico:** UUID (FK → TEAM)  
**Obligatorio:** Sí  
**Descripción:** Equipo participante.

**Campo:** `season_id`  
**Tipo lógico:** UUID (FK → SEASON)  
**Obligatorio:** Sí  
**Descripción:** Edición.

**Campo:** `status`  
**Tipo lógico:** catálogo (`registered`,`withdrawn`,`disqualified`)  
**Obligatorio:** Sí (default `registered`)  
**Descripción:** Estado de participación.

**Campo:** `created_at` / `updated_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Auditoría.

**Relaciones:**
- N → 1 TEAM  
- N → 1 SEASON  
- Unicidad de negocio: (`team_id`,`season_id`) único.

**Campos que NO deben estar aquí:**  
`points`, `played`, `rank` (calculados en fase posterior).

**Regla de carga (recomendada):**  
Los `home_team_id` / `away_team_id` de un `MATCH` de esa season deberían estar inscritos aquí (salvo amistosos futuros).

---

# PERSONAS

## ENTIDAD: PERSON

**Descripción:**  
Identidad humana real, independiente del rol deportivo.

**Objetivo:**  
No duplicar identidad si mañana la persona es entrenador.

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador interno.

**Campo:** `full_name`  
**Tipo lógico:** texto  
**Obligatorio:** Sí  
**Descripción:** Nombre completo.  
**Ejemplo:** `Lamine Yamal Nasraoui Ebana`

**Campo:** `display_name`  
**Tipo lógico:** texto  
**Obligatorio:** Sí  
**Descripción:** Nombre público.  
**Ejemplo:** `Lamine Yamal`

**Campo:** `first_name` / `last_name`  
**Tipo lógico:** texto  
**Obligatorio:** No  
**Descripción:** Estructura opcional del nombre.

**Campo:** `birth_date`  
**Tipo lógico:** fecha  
**Obligatorio:** No  
**Descripción:** Nacimiento. **La edad no se guarda; se calcula.**  
**Ejemplo:** `2007-07-13`

**Campo:** `birth_country_id`  
**Tipo lógico:** UUID (FK → COUNTRY)  
**Obligatorio:** No  
**Descripción:** País de nacimiento.

**Campo:** `birth_city_id`  
**Tipo lógico:** UUID (FK → CITY)  
**Obligatorio:** No  
**Descripción:** Ciudad de nacimiento.

**Campo:** `gender`  
**Tipo lógico:** catálogo (`male`,`female`,`other`,`unknown`)  
**Obligatorio:** No  
**Descripción:** Dato demográfico opcional.

**Campo:** `created_at` / `updated_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Auditoría.

**Relaciones:**
- 1 PERSON → 0..1 PLAYER (MVP)

**Campos que NO deben estar aquí:**  
`club_id`, `position`, `market_value`, `goals`.

---

## ENTIDAD: PLAYER

**Descripción:**  
Rol futbolístico de una PERSON.

**Objetivo:**  
Ficha de jugador sin historial ni totales de temporada como verdad.

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador del rol jugador.

**Campo:** `person_id`  
**Tipo lógico:** UUID (FK → PERSON)  
**Obligatorio:** Sí  
**Descripción:** Persona asociada. Único (1:1) en MVP.

**Campo:** `nationality_country_id`  
**Tipo lógico:** UUID (FK → COUNTRY)  
**Obligatorio:** No  
**Descripción:** Nacionalidad principal de ficha. Doble nacionalidad = fase 2.

**Campo:** `primary_position`  
**Tipo lógico:** catálogo (`GK`,`CB`,`LB`,`RB`,`CDM`,`CM`,`CAM`,`LW`,`RW`,`ST`,…)  
**Obligatorio:** No  
**Descripción:** Posición principal de presentación.

**Campo:** `secondary_position`  
**Tipo lógico:** catálogo  
**Obligatorio:** No  
**Descripción:** Segunda posición habitual (MVP).

**Campo:** `foot`  
**Tipo lógico:** catálogo (`left`,`right`,`both`,`unknown`)  
**Obligatorio:** No  
**Descripción:** Pie dominante.

**Campo:** `height_cm` / `weight_kg`  
**Tipo lógico:** entero  
**Obligatorio:** No  
**Descripción:** Antropometría.

**Campo:** `shirt_name`  
**Tipo lógico:** texto  
**Obligatorio:** No  
**Descripción:** Nombre en dorsal.

**Campo:** `status`  
**Tipo lógico:** catálogo (`active`,`retired`,`deceased`,`unknown`)  
**Obligatorio:** Sí (default `active`)  
**Descripción:** Estado de carrera.  
**Regla v1.1:** `retired`/`deceased` exige cerrar histories abiertas de club (Anexo A.2).

**Campo:** `current_team_id`  
**Tipo lógico:** UUID (FK → TEAM)  
**Obligatorio:** No  
**Descripción:** **CACHE gobernado** del club/team actual de ficha.  
**Regla v1.1:** no es campo de edición libre; se deriva de `PLAYER_TEAM_HISTORY` (Anexo A.2 y A.3).  
**Ejemplo:** `Barcelona id` o `null` si está sin club.

**Campo:** `current_market_value`  
**Tipo lógico:** decimal  
**Obligatorio:** No  
**Descripción:** **CACHE gobernado** del último valor conocido.  
**Regla v1.1:** derivado de `MARKET_VALUE_HISTORY` (Anexo A.3).

**Campo:** `current_market_value_currency`  
**Tipo lógico:** catálogo (`EUR`,`USD`,`GBP`…)  
**Obligatorio:** No (sí si hay value)  
**Descripción:** Divisa del cache.

**Campo:** `created_at` / `updated_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Auditoría.

**Relaciones:**
- 1 PLAYER → 1 PERSON
- 1 PLAYER → N PLAYER_TEAM_HISTORY
- 1 PLAYER → N TRANSFER
- 1 PLAYER → N MARKET_VALUE_HISTORY
- 1 PLAYER → N MATCH_EVENT

**Campos que NO deben estar aquí:**  
`goals`, `assists`, `appearances`, `team_id` como única relación, totales de temporada.

**Estadísticas publicables en MVP:** ver Anexo A.7 (solo métricas derivadas de eventos).

---

## ENTIDAD: PLAYER_TEAM_HISTORY

**Descripción:**  
Periodo en el que un jugador perteneció a un TEAM (club o selección).

**Objetivo:**  
Carrera, plantilla actual y base del cache `current_team_id`.

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador del periodo.

**Campo:** `player_id`  
**Tipo lógico:** UUID (FK → PLAYER)  
**Obligatorio:** Sí  
**Descripción:** Jugador.

**Campo:** `team_id`  
**Tipo lógico:** UUID (FK → TEAM)  
**Obligatorio:** Sí  
**Descripción:** Equipo del periodo.

**Campo:** `role`  
**Tipo lógico:** catálogo (`permanent`,`loan`,`loan_return`,`trial`,`youth`,`unknown`)  
**Obligatorio:** Sí (default `permanent`)  
**Descripción:** Naturaleza de la estancia.  
**Ejemplo:** `loan`

**Campo:** `start_date`  
**Tipo lógico:** fecha  
**Obligatorio:** Sí  
**Descripción:** Inicio. Debe alinearse con transfers cuando existan (Anexo A.4).

**Campo:** `end_date`  
**Tipo lógico:** fecha  
**Obligatorio:** No  
**Descripción:** Fin; **null = vigente**.  
**Regla v1.1 (sin club):** jugador libre = **ningún** history de club con `end_date` null (Anexo A.2).

**Campo:** `shirt_number`  
**Tipo lógico:** entero  
**Obligatorio:** No  
**Descripción:** Dorsal representativo del periodo.

**Campo:** `on_loan_from_team_id`  
**Tipo lógico:** UUID (FK → TEAM)  
**Obligatorio:** No  
**Descripción:** Obligatorio en práctica si `role=loan`: club dueño.

**Campo:** `notes`  
**Tipo lógico:** texto  
**Obligatorio:** No  
**Descripción:** Nota de carga/calidad.

**Campo:** `created_at` / `updated_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Auditoría.

**Relaciones:**
- N HISTORY → 1 PLAYER
- N HISTORY → 1 TEAM
- 0..1 TEAM origen de cesión

**Campos que NO deben estar aquí:**  
`goals_for_club`, `apps_for_club` manuales sin partidos.

---

# PARTIDOS

## ENTIDAD: MATCH

**Descripción:**  
Encuentro entre dos teams en una season.

**Objetivo:**  
Calendario, resultado oficial y ancla de eventos.

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador interno.

**Campo:** `season_id`  
**Tipo lógico:** UUID (FK → SEASON)  
**Obligatorio:** Sí  
**Descripción:** Edición. La competición se obtiene por join, no se duplica.

**Campo:** `home_team_id` / `away_team_id`  
**Tipo lógico:** UUID (FK → TEAM)  
**Obligatorio:** Sí  
**Descripción:** Local y visitante.

**Campo:** `match_date`  
**Tipo lógico:** fecha  
**Obligatorio:** Sí  
**Descripción:** Fecha del partido.

**Campo:** `kickoff_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** No  
**Descripción:** Hora del saque. Convención recomendada: UTC.

**Campo:** `round_name`  
**Tipo lógico:** texto  
**Obligatorio:** No  
**Descripción:** Jornada/fase textual en MVP.  
**Ejemplo:** `Matchday 28`

**Campo:** `status`  
**Tipo lógico:** catálogo (`scheduled`,`live`,`finished`,`postponed`,`cancelled`,`awarded`)  
**Obligatorio:** Sí  
**Descripción:** Estado del encuentro.

**Campo:** `home_score` / `away_score`  
**Tipo lógico:** entero  
**Obligatorio:** No  
**Descripción:** **Resultado oficial de acta** (hecho). Null si no jugado.  
**Regla v1.1:** no se recalcula automáticamente desde eventos en MVP (Anexo A.6).  
**Ejemplo:** `2` - `1`

**Campo:** `venue_city_id`  
**Tipo lógico:** UUID (FK → CITY)  
**Obligatorio:** No  
**Descripción:** Ciudad del partido (estadio detallado = fase 2).

**Campo:** `created_at` / `updated_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Auditoría.

**Relaciones:**
- N MATCH → 1 SEASON → 1 COMPETITION
- N MATCH → 1 TEAM (home) + 1 TEAM (away)
- 1 MATCH → N MATCH_EVENT

**Campos que NO deben estar aquí:**  
`competition_name`, nombres de equipos en texto, goleadores embebidos.

---

## ENTIDAD: MATCH_EVENT

**Descripción:**  
Hecho atómico de partido (gol, tarjeta, cambio…).

**Objetivo:**  
Fuente original de estadísticas MVP (Anexo A.7).

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador del evento.

**Campo:** `match_id`  
**Tipo lógico:** UUID (FK → MATCH)  
**Obligatorio:** Sí  
**Descripción:** Partido.

**Campo:** `event_type`  
**Tipo lógico:** catálogo  
**Obligatorio:** Sí  
**Descripción:** Catálogo MVP v1.1 (cerrado, append-only después):  
`goal`, `own_goal`, `penalty_goal`, `penalty_miss`, `yellow_card`, `red_card`, `second_yellow`, `substitution_in`, `substitution_out`.  
**Cambio v1.1:** **`assist` NO forma parte del catálogo MVP** (Anexo A.1).

**Campo:** `player_id`  
**Tipo lógico:** UUID (FK → PLAYER)  
**Obligatorio:** No  
**Descripción:** Protagonista.

**Campo:** `secondary_player_id`  
**Tipo lógico:** UUID (FK → PLAYER)  
**Obligatorio:** No  
**Descripción:** En goles (`goal` / `penalty_goal`) = **asistente**. En cambios = el otro jugador según convención de carga.  
**Regla v1.1:** única forma de registrar asistencia en MVP (Anexo A.1).

**Campo:** `team_id`  
**Tipo lógico:** UUID (FK → TEAM)  
**Obligatorio:** Sí  
**Descripción:** Equipo al que se atribuye el evento.  
**Autogol:** ver Anexo A.1 (convención).

**Campo:** `minute`  
**Tipo lógico:** entero  
**Obligatorio:** No  
**Descripción:** Minuto de juego.

**Campo:** `extra_minute`  
**Tipo lógico:** entero  
**Obligatorio:** No  
**Descripción:** Añadido (90+3 → minute=90, extra_minute=3).

**Campo:** `period`  
**Tipo lógico:** catálogo (`first_half`,`second_half`,`extra_first`,`extra_second`,`penalty_shootout`,`unknown`)  
**Obligatorio:** No  
**Descripción:** Periodo.

**Campo:** `sort_order`  
**Tipo lógico:** entero  
**Obligatorio:** No  
**Descripción:** Orden estable en el mismo minuto.

**Campo:** `created_at` / `updated_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Auditoría.

**Relaciones:**
- N EVENT → 1 MATCH
- N EVENT → 0..1 PLAYER (main / secondary)
- N EVENT → 1 TEAM

**Campos que NO deben estar aquí:**  
`season_id`, `competition_id`, totales de jugador.

---

# MERCADO

## ENTIDAD: TRANSFER

**Descripción:**  
Movimiento de un jugador entre equipos.

**Objetivo:**  
Fichajes públicos. Complementa, no sustituye, `PLAYER_TEAM_HISTORY`.

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador.

**Campo:** `player_id`  
**Tipo lógico:** UUID (FK → PLAYER)  
**Obligatorio:** Sí  
**Descripción:** Jugador transferido.

**Campo:** `from_team_id`  
**Tipo lógico:** UUID (FK → TEAM)  
**Obligatorio:** No  
**Descripción:** Origen; null si libre/sin team modelado.

**Campo:** `to_team_id`  
**Tipo lógico:** UUID (FK → TEAM)  
**Obligatorio:** No  
**Descripción:** Destino; null en casos finales futuros.

**Campo:** `transfer_type`  
**Tipo lógico:** catálogo (`permanent`,`loan`,`loan_end`,`free`,`end_of_contract`,`academy_promotion`,`unknown`)  
**Obligatorio:** Sí  
**Descripción:** Tipo de movimiento.

**Campo:** `announced_date`  
**Tipo lógico:** fecha  
**Obligatorio:** No  
**Descripción:** Anuncio público.

**Campo:** `effective_date`  
**Tipo lógico:** fecha  
**Obligatorio:** Sí  
**Descripción:** Fecha efectiva. Debe alinearse con `start_date`/`end_date` del history (Anexo A.4).

**Campo:** `fee_amount`  
**Tipo lógico:** decimal  
**Obligatorio:** No  
**Descripción:** Importe.  
**Convención v1.1:** en `free` / `end_of_contract` usar `fee_amount = null` (no aplica / no hay fee), no `0`, salvo que documentéis lo contrario en una carga concreta.

**Campo:** `fee_currency`  
**Tipo lógico:** catálogo  
**Obligatorio:** No  
**Descripción:** Divisa; obligatoria si `fee_amount` no es null.

**Campo:** `fee_is_estimated`  
**Tipo lógico:** boolean  
**Obligatorio:** Sí (default false)  
**Descripción:** Fee estimado vs oficial.

**Campo:** `related_history_id`  
**Tipo lógico:** UUID (FK → PLAYER_TEAM_HISTORY)  
**Obligatorio:** No  
**Descripción:** Spell creado/cerrado por este movimiento.  
**Regla v1.1:** toda transfer efectiva debe sincronizar HISTORY (Anexo A.4).

**Campo:** `created_at` / `updated_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Auditoría.

**Relaciones:**
- N TRANSFER → 1 PLAYER
- N TRANSFER → 0..1 TEAM (from/to)
- 0..1 PLAYER_TEAM_HISTORY relacionada

**Campos que NO deben estar aquí:**  
nombres en texto, valor de mercado embebido sin snapshot.

---

## ENTIDAD: MARKET_VALUE_HISTORY

**Descripción:**  
Instantánea del valor de mercado de un jugador en una fecha.

**Objetivo:**  
Serie temporal; base del cache `current_market_value`.

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador del snapshot.

**Campo:** `player_id`  
**Tipo lógico:** UUID (FK → PLAYER)  
**Obligatorio:** Sí  
**Descripción:** Jugador.

**Campo:** `value_amount`  
**Tipo lógico:** decimal  
**Obligatorio:** Sí  
**Descripción:** Importe.

**Campo:** `currency`  
**Tipo lógico:** catálogo  
**Obligatorio:** Sí  
**Descripción:** Divisa.  
**Ejemplo:** `EUR`

**Campo:** `recorded_on`  
**Tipo lógico:** fecha  
**Obligatorio:** Sí  
**Descripción:** Fecha de la valoración (día civil; convención UTC de proyecto).

**Campo:** `source`  
**Tipo lógico:** catálogo/texto  
**Obligatorio:** No  
**Descripción:** Origen (`manual`, `ifl_model`, `import_x`).

**Campo:** `created_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Inserción del registro.

**Relaciones:**
- N → 1 PLAYER

**Campos que NO deben estar aquí:**  
`is_current` como única verdad sin serie.

**Valor actual:** snapshot con `recorded_on` más reciente (y desempate por `created_at` / `source` según Anexo A.3).

---

# PRODUCTO

## ENTIDAD: SLUG

**Descripción:**  
Identificador legible de URL por entidad e idioma.

**Objetivo:**  
SEO: `/player/lamine-yamal`, `/club/real-madrid`, `/competition/la-liga`.

**Campos:**

**Campo:** `id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Identificador del slug.

**Campo:** `entity_type`  
**Tipo lógico:** catálogo (`player`,`team`,`competition`,`match`,`transfer`,`season`)  
**Obligatorio:** Sí  
**Descripción:** Tipo de entidad publicable.

**Campo:** `entity_id`  
**Tipo lógico:** UUID  
**Obligatorio:** Sí  
**Descripción:** Id de la entidad (polimórfico controlado).

**Campo:** `locale`  
**Tipo lógico:** catálogo (`es`,`en`,`fr`,…)  
**Obligatorio:** Sí  
**Descripción:** Idioma de la ruta.

**Campo:** `slug`  
**Tipo lógico:** texto  
**Obligatorio:** Sí  
**Descripción:** Segmento URL normalizado.  
**Ejemplo:** `lamine-yamal`

**Campo:** `is_primary`  
**Tipo lógico:** boolean  
**Obligatorio:** Sí  
**Descripción:** Canónico para esa entidad+locale.  
**Regla:** un solo primary por (`entity_type`,`entity_id`,`locale`).

**Campo:** `is_active`  
**Tipo lógico:** boolean  
**Obligatorio:** Sí  
**Descripción:** Si resuelve. Los antiguos pueden quedar inactive/no primary (redirects = fase 2).

**Campo:** `created_at` / `updated_at`  
**Tipo lógico:** timestamp  
**Obligatorio:** Sí  
**Descripción:** Auditoría.

**Relaciones:**
- cada entidad publicable 1 → N SLUG

**Unicidad:** (`locale`,`slug`) único a nivel producto.

**Campos que NO deben estar aquí:**  
meta SEO editorial larga (fase `SEO_META`).

---

# Páginas MVP — origen de datos

### `/player/{slug}`
| Bloque | Origen |
|---|---|
| Nombre | PERSON.display_name |
| Edad | calculada de PERSON.birth_date |
| Nacionalidad | PLAYER.nationality_country_id → COUNTRY |
| Posición | PLAYER.primary_position |
| Club actual | HISTORY abierta de club o cache gobernado; `null` = sin club |
| Historial | PLAYER_TEAM_HISTORY |
| Estadísticas | solo métricas Anexo A.7 desde MATCH_EVENT |
| Valor | último MARKET_VALUE_HISTORY (+ cache gobernado) |
| Noticias | fuera de MVP tablas |

### `/club/{slug}`
| Bloque | Origen |
|---|---|
| Nombre/país | TEAM + COUNTRY |
| Plantilla | HISTORY abiertas del team |
| Entrenador | fuera de MVP core |
| Competiciones | TEAM_COMPETITION → SEASON → COMPETITION |
| Partidos | MATCH |
| Fichajes | TRANSFER |

### `/competition/{slug}`
| Bloque | Origen |
|---|---|
| Nombre | COMPETITION |
| Temporada | SEASON `is_current` (única) |
| Equipos | TEAM_COMPETITION |
| Partidos | MATCH |
| Clasificación | fuera de MVP |

---

# Orden de creación física (cuando toque SQL)

1. COUNTRY  
2. CITY  
3. COMPETITION  
4. SEASON  
5. TEAM  
6. TEAM_COMPETITION  
7. PERSON  
8. PLAYER  
9. PLAYER_TEAM_HISTORY  
10. MATCH  
11. MATCH_EVENT  
12. TRANSFER  
13. MARKET_VALUE_HISTORY  
14. SLUG  

---

# Dependencias

```text
COUNTRY
  ├── CITY
  ├── TEAM
  ├── COMPETITION (opcional country_id)
  └── PLAYER / PERSON

COMPETITION → SEASON → TEAM_COMPETITION ← TEAM
SEASON → MATCH → MATCH_EVENT ← PLAYER
PERSON → PLAYER → PLAYER_TEAM_HISTORY ← TEAM
PLAYER → TRANSFER ← TEAM
PLAYER → MARKET_VALUE_HISTORY
SLUG → (player|team|competition|match|transfer|season)
```

---

# Críticas vs pueden esperar

### Críticas para lanzar MVP
COUNTRY, CITY, COMPETITION, SEASON, TEAM, TEAM_COMPETITION, PERSON, PLAYER, PLAYER_TEAM_HISTORY, MATCH, MATCH_EVENT, TRANSFER, MARKET_VALUE_HISTORY, SLUG

### Pueden esperar
COACH, STADIUM, MATCH_APPEARANCE, stats materializadas, CONTRACT, INJURY, NEWS, MEDIA, USER/FAVOURITES/ALERTS, IFL_SCORE/AI/RANKINGS, redirects de slug, doble nacionalidad N:N

---

# ANEXO A — Reglas de negocio MVP v1.1

Este anexo es **normativo**. La carga manual (analista) y el desarrollo deben cumplirlo antes y después del SQL.

---

## A.1 Asistencias sin doble conteo (`MATCH_EVENT`)

**Decisión:** en MVP hay **un solo** modelo de asistencia.

| Caso | Cómo se registra |
|---|---|
| Gol con asistencia | `event_type = goal` o `penalty_goal`; `player_id` = goleador; `secondary_player_id` = asistente |
| Gol sin asistencia | `secondary_player_id = null` |
| Evento `assist` | **Prohibido en MVP** — no usar |

**Cálculo de asistencias de un jugador:**  
contar eventos donde  
`event_type IN (goal, penalty_goal)` AND `secondary_player_id = :playerId`.

**Autogoles (`own_goal`):**
- `player_id` = jugador que marca en propia puerta  
- `team_id` = equipo que **sufre** el gol en contra (el equipo del autor del autogol)  
- el gol a favor del rival se refleja en el **marcador oficial** de `MATCH`, no inventando un segundo evento de gol rival en MVP salvo que el analista cargue el detalle completo de forma consistente  
- `secondary_player_id` no aplica

**Penalti fallado:** `penalty_miss` — no suma gol ni asistencia.

---

## A.2 Jugador sin club / libre agente

**No** crear un TEAM artificial tipo “Free Agent”.

Un jugador está **sin club** cuando se cumplen **ambas**:

1. No existe ningún `PLAYER_TEAM_HISTORY` de equipo `team_kind = club` con `end_date IS NULL`.  
2. `PLAYER.current_team_id IS NULL`.

**Notas:**
- Puede seguir existiendo history abierta con selección (`team_kind = national`) sin que eso cuente como “club actual” de ficha.  
- **Club actual de ficha (cache):** el history abierto de club más reciente / el único abierto de club (Anexo A.3).  
- Si `PLAYER.status ∈ {retired, deceased}`: no debe quedar history de club abierta; cerrar con `end_date`.

**Cantera:** usar `role = youth` y/o `TEAM.age_category` adecuada; no mezclar con “sin club”.

---

## A.3 Contrato de caches en `PLAYER`

Campos cache:

- `current_team_id`
- `current_market_value`
- `current_market_value_currency`

**Naturaleza:** derivados. **No son fuente de verdad.**

| Cache | Fuente de verdad | Regla de derivación MVP |
|---|---|---|
| `current_team_id` | `PLAYER_TEAM_HISTORY` | Team del spell de club abierto (`end_date` null, `TEAM.team_kind=club`). Si no hay → `null` |
| `current_market_value` + currency | `MARKET_VALUE_HISTORY` | Snapshot con mayor `recorded_on`; empate → mayor `created_at` |

**Operativa de carga:**
- El analista **no edita caches a mano** en el flujo normal.  
- Tras crear/cerrar history o insertar snapshot, se actualiza el cache (checklist manual en MVP; job/trigger en el futuro).  
- Si hay divergencia, **ganan HISTORY / último snapshot**; se corrige el cache.

**Exposición producto:** las fichas pueden leer cache por rendimiento, pero cualquier reconstrucción debe poder hacerse solo con hechos.

---

## A.4 Sincronía `TRANSFER` ↔ `PLAYER_TEAM_HISTORY`

Toda `TRANSFER` con efecto real en plantilla **debe** dejar HISTORY consistente.  
`related_history_id` debería apuntar al spell principal creado o cerrado por esa operación cuando aplique.

### Secuencias mínimas

**A) `permanent` o `free` (llegada a club destino)**  
1. Cerrar spell de club abierto en origen (si existe): `end_date = effective_date` (o día anterior, convención única del equipo: **usar `effective_date` como fin del origen y inicio del destino** salvo que documentéis day-before).  
2. Abrir spell en destino: `start_date = effective_date`, `role=permanent` (o el que corresponda), `end_date=null`.  
3. Actualizar cache `current_team_id = to_team_id`.

**B) `loan`**  
1. Cerrar o mantener origen según dato real; en MVP simplificado recomendado:  
   - cerrar spell permanente en club dueño con `end_date = effective_date` **o** dejar constancia solo con el spell de cesión activo + `on_loan_from_team_id`  
2. Convención MVP elegida (obligatoria para el equipo):  

   **Convención IFLXI MVP:** durante la cesión hay **un solo spell de club abierto**, el del equipo destino, con:  
   - `role = loan`  
   - `on_loan_from_team_id = club dueño`  
   - `start_date = effective_date`  
   El spell del dueño queda cerrado o segmentado; no dos clubs abiertos a la vez.

3. Cache `current_team_id = to_team_id` (equipo donde juega).

**C) `loan_end`**  
1. Cerrar spell `loan` del equipo de cesión (`end_date = effective_date`).  
2. Abrir (o reabrir) spell en club dueño: `role=permanent` (o `loan_return` si queréis trazar), `start_date = effective_date`.  
3. Cache → club dueño.

**D) `end_of_contract` / salida a libre**  
1. Cerrar spell de club abierto.  
2. `to_team_id` puede ser null.  
3. Cache `current_team_id = null`.

**E) `academy_promotion`**  
1. Cerrar spell youth/cantera si existía.  
2. Abrir spell permanent (o youth→permanent) en primer equipo.  
3. Actualizar cache.

**Prohibido:** alta de TRANSFER “de escaparate” que cambie el relato público sin tocar HISTORY.

**Fechas:** `TRANSFER.effective_date` alineada con `start_date` / `end_date` de los spells afectados.

---

## A.5 Una sola season actual por competición

Para cada `competition_id` existe como máximo **una** fila `SEASON` con `is_current = true`.

Al marcar una season como current:
- poner `is_current = false` en las demás seasons de esa competición.

Uso producto:
- `/competition/{slug}` muestra por defecto la season current.  
- Partidos “de la temporada” del hub de competición = esa season.

---

## A.6 Marcador oficial vs eventos

| Dato | Rol |
|---|---|
| `MATCH.home_score` / `away_score` | **Hecho de acta / resultado oficial** |
| `MATCH_EVENT` (goles) | **Detalle** opcionalmente incompleto en carga manual temprana |

**MVP:**
- El marcador **no** se recalcula automáticamente como suma de eventos.  
- Si hay eventos de gol, el analista debería procurar coherencia; si no cuadra, **prevalece el marcador oficial** y se anota en `notes` de carga / se corrigen eventos.  
- Validación soft futura: warning si suma de goles-evento ≠ marcador.

**Cuándo son obligatorios los scores:**  
si `status ∈ {finished, awarded}` → `home_score` y `away_score` obligatorios (no null).

---

## A.7 Alcance de estadísticas publicables en MVP

Sin entidad de alineaciones/minutos, el MVP **solo** puede publicar de forma honesta métricas derivadas de `MATCH_EVENT`:

| Métrica | Cómo se calcula |
|---|---|
| Goles | COUNT eventos `goal` + `penalty_goal` del jugador (no `own_goal`) |
| Asistencias | COUNT goles donde `secondary_player_id` = jugador |
| Tarjetas amarillas | COUNT `yellow_card` (+ definir si `second_yellow` cuenta aparte) |
| Tarjetas rojas | COUNT `red_card` + `second_yellow` (convención: second_yellow implica roja) |
| Autogoles | COUNT `own_goal` (separado; no sumar a goles a favor) |

**Fuera de MVP (no inventar ni digitar en PLAYER):**
- partidos jugados / titularidades  
- minutos  
- goles/partido  
- clasificación de liga  
- ratings  

**Comunicación de producto:** si la UI muestra “Estadísticas”, etiquetar temporada/competición cuando se filtre por joins a `MATCH → SEASON`, o mostrar totales globales de eventos cargados con transparencia (“basado en partidos cargados”).

---

## A.8 Reglas transversales de carga (operativa)

**Orden de alta recomendado:**  
Country → City → Competition → Season → Team → Team_Competition → Person → Player → History → Match → Events → Transfer → Market value → Spug/Slug.

**Prohibiciones:**
- Totales de goles/asistencias/apps escritos en `PLAYER` o `TEAM`.  
- Editar caches sin actualizar hechos.  
- Transfers sin sync de HISTORY.  
- Usar `event_type = assist`.  
- Varias seasons `is_current` en la misma competición.  
- TEAM “Free Agent”.

**Selección + club a la vez:**  
permitido: un spell de club abierto + uno o más spells de selección abiertos/cerrados por ventana.

**Dos clubs abiertos a la vez:**  
prohibido en MVP.

---

## A.9 Unicidades lógicas a respetar en SQL futuro

| Entidad | Unicidad |
|---|---|
| COUNTRY | `iso2` |
| SEASON | máx. 1 `is_current=true` por `competition_id` |
| TEAM_COMPETITION | (`team_id`,`season_id`) |
| PLAYER | `person_id` |
| SLUG | (`locale`,`slug`); 1 primary por (`entity_type`,`entity_id`,`locale`) |
| MARKET_VALUE_HISTORY | política por (`player_id`,`recorded_on`,`source`) |

---

# Estado del documento

| Pregunta | Respuesta |
|---|---|
| ¿Diccionario listo para diseñar SQL? | **Sí**, con este v1.1 y Anexo A |
| ¿Se puede escribir `CREATE TABLE` ya en este paso? | **No todavía** — este documento solo cierra el diccionario/reglas |
| Siguiente fase | Diseño SQL PostgreSQL MVP v1 (tipos, PK/FK, constraints alineados al Anexo A) |

---

**Frase de control:**  
Si un número se puede contar desde eventos o histories, no se digita como verdad en `PLAYER` / `TEAM`.
