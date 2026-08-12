# IFLXI

Info Football Lab XI — plataforma mundial de datos de fútbol. HTML, CSS y JavaScript puro (+ `server.py` opcional para datos reales).

## Archivos

| Archivo | Contenido |
| --- | --- |
| `index.html` | Portada: buscador global, estadísticas mundiales, jugadores destacados, jóvenes talentos y últimos fichajes |
| `jugador.html` | Ficha de jugador (se carga con `?id=mbappe`) |
| `comparador.html` | Comparador de dos jugadores (`?a=yamal&b=bellingham`) |
| `partidos.html` | Listado de partidos del día |
| `partido.html` | Ficha de partido + timeline de eventos (`?id=`) |
| `style.css` | Sistema de diseño completo (tokens, componentes, responsive) |
| `script.js` | Datos, API, motor de puntuación y controladores de página |
| `server.py` | FastAPI + PostgreSQL (`/api/players`, `/api/teams`, `/api/matches`, …) |

## Cómo abrirlo (demo local sin BD)

Basta con abrir `index.html` en el navegador, o:

```bash
python -m http.server 8899
```

## Cómo abrirlo CON datos reales (PostgreSQL)

Con la base `iflxi` cargada:

```powershell
cd C:\Users\juanj\OneDrive\Escritorio\IFLXI
$env:PGPASSWORD = "TU_PASSWORD"
$env:PGDATABASE = "iflxi"
py -m pip install "fastapi" "uvicorn[standard]" "psycopg[binary]"
py server.py
```

Abre **http://127.0.0.1:8787** — contadores, buscador, fichas y plantillas de club salen de la BD.
Si abres el HTML a pelo (sin `server.py`), sigue el modo demo.

## Estructura de `script.js`

1. **DATA** — `CLUBS`, `LEAGUES`, `PLAYERS`, `TRANSFERS`, `GLOBAL_STATS` (datos de ejemplo).
2. **API** — único punto de acceso a los datos. Todos los métodos son asíncronos.
3. **CORE** — utilidades de formato y motor de análisis (`aiRating`, `aiPotential`, `affinity`, `similarPlayers`).
4. **UI** — componentes reutilizables: tarjetas, gráfico de valor en SVG, radar, buscador.
5. **PAGES** — controlador por página, elegido según `<body data-page="...">`.

## Conectar una base de datos real

La interfaz nunca lee los arrays directamente: siempre pasa por `api`. Para enchufar un backend
solo hay que cambiar el cuerpo de cada método, manteniendo la forma de los objetos.

```js
const api = {
  getPlayers: (options = {}) =>
    fetch(`/api/players?${new URLSearchParams(options)}`).then((r) => r.json()),

  getPlayer: (id) => fetch(`/api/players/${id}`).then((r) => r.json()),

  getTransfers: (limit = 8) => fetch(`/api/transfers?limit=${limit}`).then((r) => r.json()),

  search: (query) => fetch(`/api/search?q=${encodeURIComponent(query)}`).then((r) => r.json())
};
```

### Esquema de un jugador

```js
{
  id, name, shirt, age, birth, nationality, flag, position, pos,
  club,            // clave de CLUBS
  contract, height, foot, value,             // valor en millones de €
  photo,           // opcional; si falta se genera un avatar con iniciales
  stats: { matches, goals, assists, minutes },
  attrs: { ritmo, tiro, pase, regate, defensa, fisico },  // 0-100
  valueHistory: [[año, valor]],
  career: [{ club, from, to, apps, goals }]
}
```

Los datos incluidos son simulados y sirven como prototipo de demostración.
