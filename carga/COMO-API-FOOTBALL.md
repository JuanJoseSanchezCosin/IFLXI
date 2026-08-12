# IFLXI — API-Football (guía rápida)

Plan Pro: ~7500 requests/día. Ir por fases igualmente (no quemar cuota al azar).

## Preparar sesión PowerShell

```powershell
cd C:\Users\juanj\OneDrive\Escritorio\IFLXI\carga

$env:API_FOOTBALL_KEY = "TU_KEY"
$env:PGHOST = "localhost"
$env:PGPORT = "5432"
$env:PGUSER = "postgres"
$env:PGPASSWORD = "TU_PASSWORD_POSTGRES"
$env:PGDATABASE = "iflxi"
```

> Plan Free: solo temporadas **2022–2024**. Plan Pro: incluye **2025/2026** (p. ej. LaLiga 2026 = 2026/27).

## Fase 0 — Catálogo de todas las ligas ≈ 1 request

Carga **todas** las competiciones de API-Football (`competition` + `season` actual).  
No trae equipos ni jugadores (eso sigue siendo por liga con el importador de abajo).

```powershell
py api_football_import_leagues.py --dry-run
py api_football_import_leagues.py --apply
```

Comprobar:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -d iflxi -c "SELECT COUNT(*) AS competitions FROM competition; SELECT competition_type, COUNT(*) FROM competition GROUP BY 1 ORDER BY 2 DESC; SELECT COUNT(*) AS seasons_current FROM season WHERE is_current;"
```

## Fase 0b — Rellenar ligas (equipos / plantillas) por lotes

El catálogo solo crea filas en `competition`/`season`. Para meter **equipos** (y luego plantillas) de muchas ligas:

```powershell
# 1) Solo equipos de type=League (reanudable; ~1 req por liga)
py api_football_fill_leagues.py --dry-run --mode teams --max-requests 50
py api_football_fill_leagues.py --apply --mode teams --max-requests 400

# 2) Cuando terminen los equipos: plantillas (squads) — más requests
py api_football_fill_leagues.py --apply --mode squads --max-requests 500
```

- Progreso en `.api_football_map.json` → `fill.teams` / `fill.squads`
- Big 5 (ya cargadas) se saltan
- Si para por tope de requests, **repite el mismo comando**

## Fase 1 — Solo equipos ≈ 1 request

```powershell
py api_football_import.py --league laliga --season 2026 --dry-run
py api_football_import.py --league laliga --season 2026 --apply
```

Carga: competición + temporada + equipos + inscripción en temporada.

## Fase 2 — Jugadores / plantillas

`/players?league=&season=` a menudo devuelve **0** al inicio de temporada (sin stats aún).
El importador en `--players-mode auto` (por defecto) hace fallback a **`/players/squads`** por equipo (~20 requests en LaLiga).

```powershell
# Recomendado (auto: stats → si vacío, squads)
py api_football_import.py --league laliga --season 2026 --apply --with-players --max-requests 80

# Forzar solo plantillas
py api_football_import.py --league laliga --season 2026 --apply --with-players --players-mode squads --max-requests 80
```

Plantillas = roster actual (menos campos: a veces sin fecha nacimiento / altura). Suficiente para MVP de plantillas.

## Fase 3 — Partidos (MATCH, sin eventos) ≈ +1 request

`home_score` / `away_score` = acta oficial API (`goals.*`). **Nunca** recalcular desde eventos.

Piloto (máx. 5 partidos). Preferir temporada con `coverage.fixtures.events=true` (Big-5 **2025** en el cache actual; **2026** suele tener `events=false`):

```powershell
# Dry-run equipos+fixtures (sin escribir)
py api_football_import.py --league laliga --season 2025 --dry-run --with-fixtures --limit 5

# Apply solo 5 partidos
py api_football_import.py --league laliga --season 2025 --apply --with-fixtures --limit 5
```

## Fase 4 — Eventos (MATCH_EVENT) — piloto

Script: `api_football_import_events.py`  
Endpoint: `GET /fixtures/events?fixture={id}`  
Requisito: los fixtures deben existir ya en `MATCH` + mapas.

**Atajo (cuando fill haya terminado):**

```powershell
.\piloto_match_events.ps1 -BackupMaps
.\piloto_match_events.ps1 -ApplyFixtures
.\piloto_match_events.ps1 -ApplyEvents
.\piloto_match_events.ps1 -Validate
```

```powershell
# 1) Dry-run (no escribe PG ni mapas)
py api_football_import_events.py --league laliga --season 2025 --limit 5 --dry-run

# 2) Piloto apply (solo cuando el dry-run sea correcto)
py api_football_import_events.py --league laliga --season 2025 --limit 5 --apply
```

Opcional: fijar fixtures concretos:

```powershell
py api_football_import_events.py --league laliga --season 2025 --fixture 12345,67890 --dry-run
```

Validación post-piloto:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -d iflxi -f "..\sql\IFLXI-validaciones-match-event.sql"
```

Notas de mapeo (congeladas):
- Asistencia → `secondary_player_id` en `goal`/`penalty_goal` (nunca `event_type=assist`)
- Sustitución API `player`=entra / `assist`=sale → IFLXI `substitution_out` con `player_id`=sale, `secondary`=entra
- `Yellow Red Card` → solo `second_yellow` (sin yellow extra)
- Idempotencia: clave natural en `.import_map.json` bucket `event` (API no da `event.id` estable)
- `period` = NULL si no hay info fiable (no inventar)
- Events `--apply` solo actualiza `.import_map.json` (no reescribe `.api_football_map.json`)
- **No** lanzar fixtures/events mientras `fill_leagues` esté escribiendo mapas

## Fase 5 — Fichajes (TRANSFER) — preparado, no ejecutar durante fill

Script: `api_football_import_transfers.py`  
Endpoint: `GET /transfers?team={id}`  

```powershell
# Solo cuando fill haya parado
py api_football_import_transfers.py --league laliga --limit-teams 3 --dry-run
# py api_football_import_transfers.py --league laliga --limit-teams 3 --apply
```

Notas:
- Mapea Free/Loan/€XM → `free` / `loan` / `permanent`
- v1 **no** sincroniza `PLAYER_TEAM_HISTORY` (`related_history_id` NULL)
- No escribe `.api_football_map.json`
- Validación: `sql/IFLXI-validaciones-transfer.sql`

## Qué tienen Transfermarkt / Fichajes.com que IFLXI aún no (MVP)

Auditoría profunda (páginas reales, 2026-08-11): club TM Real Madrid + home Fichajes.com.

### Transfermarkt — ficha de club (lo que vende el producto)

| Bloque TM | ¿Qué es? | IFLXI | Acción |
|---|---|---|---|
| Plantilla + nº / edad / dorsal / posición | Core datos | En carga (fill squads) | Seguir fill; ya expuesto en `/api/teams/{id}` |
| Valor € por jugador + total plantilla | Marca TM | Tabla `market_value_history` vacía; API-Football **no** trae € TM | Carga Excel/manual → cache `current_market_value`; API `/api/players/top-valued` + serie `/market-values` **listas** |
| Edad media / extranjeros % | KPI derivado | **Implementado** en respuesta club (`avgAge`, `foreigners`, `foreignersPct`) + vista `v_team_squad_kpis` | Aplicar SQL vistas en BD local |
| Balance fichajes (altas/bajas/€) | Ventana de mercado | Script transfers listo; API `transferWindow` en club + `/api/teams/{id}/transfers` | Tras fill: import transfers |
| Altas / bajas listadas | TRANSFER | Endpoints listos, BD vacía | Tras fill |
| Historial de temporadas de plantilla | HISTORY por fechas | Modelo listo | UI cuando sobrino |
| Clasificación liga | Tabla posiciones | **Sin entidad** (congelado) | No inventar |
| Estadio + aforo | Infraestructura | **Sin STADIUM** | Fuera MVP |
| Trofeos / palmarés | Logros | Sin entidad | Fuera MVP |
| Entrenador | Staff | Sin COACH | Fuera MVP |
| En vivo / marcadores | Live | MATCH status; datos aún no | Tras piloto fixtures |
| Rumores / foro / noticias | Editorial + comunidad | Demo front + `content/rumors.example.json` | Sobrino / redacción (no tabla rumor) |
| Agentes libres / fin de contrato | Listados mercado | `/api/players/free-agents` (Anexo A.2) listo; contratos **sin** entidad CONTRACT | Free agents sí; “terminan contrato” no |
| Jugadores más valiosos | Ranking € | `/api/players/top-valued` | Cuando haya MVH |
| Goles / asistencias / tarjetas | Performance | Vistas + `/stats`, top-scorers/assists | Tras piloto MATCH_EVENT |
| Apps / minutos / rating | Opta-like | **Prohibido** sin MATCH_APPEARANCE (Anexo A.7) | No inventar |
| URL amigable `/jugador/nombre` | SEO | Tabla SLUG + `generate_slugs.py` | Dry-run/apply cuando quieras (no toca mapas fill) |

### Fichajes.com — home (producto editorial + mercado)

| Bloque Fichajes | ¿Qué es? | IFLXI | Acción |
|---|---|---|---|
| Feed noticias / titulares | CMS | Demo home | Editorial JSON / sobrino |
| Badge **Oficial** vs rumor | Estado noticia | No hay NEWS | Contenido manual |
| Rumores con % / tendencia | Probabilidad editorial | Demo + `content/rumors.example.json` | No entidad rumor en MVP |
| Ticker partidos en vivo | Live scores | MATCH cuando exista | Tras fixtures |
| TV / horarios broadcast | Guía TV | Fuera MVP | No |
| Clasificación | Standings | Fuera MVP | No |
| Jugadores / fichajes confirmados | Catálogo + TRANSFER | Players en fill; transfers script listo | Tras fill |
| “Mi Fichajes” / alertas usuario | Cuenta | Fuera MVP core | Más adelante |

### Ya implementado en código mientras corre el fill (sin escribir mapas)

- APIs: `/api/players/top-valued`, `/api/players/free-agents`, `/api/players/{id}/stats|transfers|market-values`
- APIs: `/api/competitions/{id}/top-scorers|top-assists|matches`, `/api/teams/{id}/transfers`
- Club: KPIs TM (`avgAge`, `foreigners`, balance ventana)
- SQL: `sql/IFLXI-vistas-stats-derivadas.sql` (KPIs, free agents, top values, stats)
- Scripts: `carga/generate_slugs.py`, `carga/sync_transfer_history.py` (Anexo A.4; **no** durante fill)
- Editorial: `content/rumors.example.json`

```powershell
# Solo DDL de vistas (seguro con fill)
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -d iflxi -f sql/IFLXI-vistas-stats-derivadas.sql

# Slugs (escribe tabla slug, no mapas)
cd carga
py generate_slugs.py --entity team --limit 30 --dry-run
```

### Orden cuando fill llegue a ~0 pendientes

1. Backup `.api_football_map.json` + `.import_map.json`
2. Piloto fixtures+events LaLiga 2025
3. Transfers dry-run → apply (pocos equipos)
4. `sync_transfer_history.py --dry-run` → apply
5. Excel market values / slugs
6. UI con sobrino (no antes)

## Comprobar en BD

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -d iflxi -c "SELECT COUNT(*) AS teams FROM team; SELECT COUNT(*) AS players FROM player; SELECT COUNT(*) AS history FROM player_team_history;"
```
