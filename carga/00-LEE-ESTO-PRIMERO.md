# IFLXI — Guía de carga para el analista (versión fácil)

Hola. No tienes que programar ni tocar PostgreSQL.

## Archivo principal (USA ESTE)

Abre este Excel:

**`IFLXI_Carga_Datos_MVP.xlsx`**

Tiene **una hoja por tabla**, columnas ya separadas, ejemplos en amarillo y filas vacías para rellenar.

> Los `.csv` de la carpeta `plantillas/` son solo respaldo técnico.  
> En Excel en español a veces se ven mal (todo en una columna). **Ignóralos** y usa el `.xlsx`.

---

## Cómo trabajar

1. Abre `IFLXI_Carga_Datos_MVP.xlsx` con Excel.
2. Empieza por la hoja `00_INSTRUCCIONES`.
3. Luego `01_Paises`, `02_Ciudades`, … en orden.
4. Las filas **amarillas** son ejemplos. Escribe debajo en las filas blancas.
5. No inventes IDs raros. Usa **códigos cortos** (ES, RMA, YAMAL…).
6. Cuando termines una fase, avisa a Juanjo. Él cargará los datos en la base `iflxi`.

---

## Orden obligatorio (no saltes pasos)

| Paso | Archivo | Qué es |
|---|---|---|
| 1 | `01_paises.csv` | Países |
| 2 | `02_ciudades.csv` | Ciudades |
| 3 | `03_competiciones.csv` | Ligas / copas |
| 4 | `04_temporadas.csv` | Temporada (ej. 2025/26) |
| 5 | `05_equipos.csv` | Clubs y selecciones |
| 6 | `06_equipos_en_temporada.csv` | Qué equipos juegan esa temporada |
| 7 | `07_personas.csv` | Personas (nombre real) |
| 8 | `08_jugadores.csv` | Ficha de jugador |
| 9 | `09_historial_equipos.csv` | En qué equipo está / estuvo |
| 10 | `10_partidos.csv` | Partidos |
| 11 | `11_eventos_partido.csv` | Goles, tarjetas, cambios |
| 12 | `12_fichajes.csv` | Traspasos |
| 13 | `13_valor_mercado.csv` | Valor de mercado |
| 14 | `14_slugs.csv` | URL amigable (seo) |

Empieza solo con los pasos **1 → 9**. Partidos y fichajes cuando ya haya plantilla base.

---

## Reglas de oro (léelas una vez)

1. **No crees un equipo “Free Agent” / Sin equipo.**  
   Jugador libre = sin fila abierta en historial de club.

2. **Un jugador solo puede tener UN club abierto a la vez.**  
   Selección + club a la vez = sí permitido.

3. **Cesión:** en historial pon `rol = loan` y rellena `prestado_desde` (club dueño).

4. **Asistencia:** NO pongas tipo `assist`.  
   En un gol, pon el asistente en la columna `jugador_secundario`.

5. **Cambio:** solo tipo `substitution_out`.  
   Sale = `jugador` · Entra = `jugador_secundario`.

6. **Resultado del partido** se pone en la tabla de partidos.  
   Los goles en eventos son detalle; no tienen que “calcular” el marcador.

7. **Traspaso gratuito:** deja el importe vacío (no pongas 0).

8. Si dudas, deja la celda vacía y pregunta. Mejor vacío que inventado.

---

## Valores que puedes escribir (catálogos cortos)

### Continente
`AF` `AS` `EU` `NA` `SA` `OC` `AN`

### Tipo competición
`league` `cup` `international_club` `international_national` `playoff` `other`

### Ámbito
`domestic` `continental` `world`

### Género equipo/competición
`male` `female` `mixed`

### Tipo equipo
`club` `national`

### Posición jugador
`GK` `CB` `LB` `RB` `LWB` `RWB` `CDM` `CM` `CAM` `LM` `RM` `LW` `RW` `CF` `ST`

### Pie
`left` `right` `both` `unknown`

### Estado jugador
`active` `retired` `deceased` `unknown`

### Rol historial
`permanent` `loan` `loan_return` `trial` `youth` `unknown`

### Estado partido
`scheduled` `finished` `postponed` `cancelled` `awarded`  
(no uses `live` por ahora)

### Tipo evento
`goal` `own_goal` `penalty_goal` `penalty_miss` `yellow_card` `red_card` `second_yellow` `substitution_out`  
(**prohibido:** `assist`, `substitution_in`)

### Tipo fichaje
`permanent` `loan` `loan_end` `free` `end_of_contract` `academy_promotion` `unknown`

### Moneda
`EUR` `USD` `GBP`

---

## Fechas

Formato: `AAAA-MM-DD`  
Ejemplo: `2025-08-15`

---

## Cuando acabes

Guarda los CSV (UTF-8 si Excel pregunta) y pásaselos a Juanjo.

**No hace falta dominio ni web.** Esto es solo para llenar la base IFLXI.
