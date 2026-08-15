/* ==========================================================================
   IFLXI — Plataforma mundial de datos de fútbol
   --------------------------------------------------------------------------
   Arquitectura:
     1. DATA   → datos simulados (se sustituirán por una base de datos real)
     2. API    → única puerta de acceso a los datos (async, lista para fetch)
     3. CORE   → utilidades, motor de puntuación y similitud "IA"
     4. UI     → componentes reutilizables (tarjetas, gráficos, buscador)
     5. PAGES  → controlador por página según <body data-page="...">
   ========================================================================== */

"use strict";

/* ==========================================================================
   1. DATA — capa de datos simulada
   ========================================================================== */

/** Clubes de la temporada actual. Clave = id usado por los jugadores. */
const CLUBS = {
  "real-madrid":  { name: "Real Madrid",       short: "RMA", league: "LaLiga",         country: "España",     c1: "#1d2b53", c2: "#0b1020", afId: 541, logo: "img/clubs/real-madrid.png?v=5" },
  "barcelona":    { name: "FC Barcelona",      short: "BAR", league: "LaLiga",         country: "España",     c1: "#8d1237", c2: "#141f52", afId: 529, logo: "img/clubs/barcelona.png?v=5" },
  "atletico":     { name: "Atlético de Madrid",short: "ATM", league: "LaLiga",         country: "España",     c1: "#a01423", c2: "#141c33", afId: 530, logo: "img/clubs/atletico.png?v=5" },
  "man-city":     { name: "Manchester City",   short: "MCI", league: "Premier League", country: "Inglaterra", c1: "#1a6f9c", c2: "#0d2330", afId: 50, logo: "img/clubs/man-city.png?v=5" },
  "arsenal":      { name: "Arsenal FC",        short: "ARS", league: "Premier League", country: "Inglaterra", c1: "#9b1b25", c2: "#1a1010", afId: 42, logo: "img/clubs/arsenal.png?v=5" },
  "liverpool":    { name: "Liverpool FC",      short: "LIV", league: "Premier League", country: "Inglaterra", c1: "#8e1524", c2: "#1c0d10", afId: 40, logo: "img/clubs/liverpool.png?v=5" },
  "chelsea":      { name: "Chelsea FC",        short: "CHE", league: "Premier League", country: "Inglaterra", c1: "#153a8a", c2: "#0a1430", afId: 49, logo: "img/clubs/chelsea.png?v=5" },
  "man-united":   { name: "Manchester United", short: "MUN", league: "Premier League", country: "Inglaterra", c1: "#8f1f1f", c2: "#1b0f0f", afId: 33, logo: "img/clubs/man-united.png?v=5" },
  "bayern":       { name: "Bayern de Múnich",  short: "BAY", league: "Bundesliga",     country: "Alemania",   c1: "#9c1224", c2: "#111a33", afId: 157, logo: "img/clubs/bayern.png?v=5" },
  "psg":          { name: "Paris Saint-Germain", short: "PSG", league: "Ligue 1",      country: "Francia",    c1: "#0f2a63", c2: "#4a0f1c", afId: 85, logo: "img/clubs/psg.png?v=5" }
};

/** CDN API-Sports (mismas fotos/escudos que API-Football). */
const AF_MEDIA = "https://media.api-sports.io/football";
const afPlayerPhoto = (id) => (id ? `${AF_MEDIA}/players/${id}.png` : null);
const afTeamLogo = (id) => (id ? `${AF_MEDIA}/teams/${id}.png` : null);
const afLeagueLogo = (id) => (id ? `${AF_MEDIA}/leagues/${id}.png` : null);

/** IDs API-Football de jugadores demo → foto */
const PLAYER_AF_IDS = {
  yamal: 386828,
  haaland: 1100,
  bellingham: 129718,
  mbappe: 278,
  vinicius: 762,
  musiala: 181812,
  wirtz: 203224,
  pedri: 133609,
  saka: 1460,
  foden: 631,
  valverde: 756,
  rodri: 44,
  julian: 909,
  vitinha: 128384,
  doue: 343027,
  cubarsi: 396623,
  saliba: 22090,
  estevao: 668918,
  "zaire-emery": 494218,
  gavi: 296667,
  guler: 626049,
  hakimi: 9,
  kane: 184,
  mainoo: 284322,
  mastantuono: 449249,
  endrick: 377122,
  davies: 509,
  salah: 306,
  donnarumma: 1622,
};

/** Escudos locales PNG transparentes (img/clubs) + fallback CDN. */
const CLUB_LOGO_SLUG = {
  "Real Madrid": "real-madrid",
  "FC Barcelona": "barcelona",
  "Atlético de Madrid": "atletico",
  "Manchester City": "man-city",
  "Arsenal": "arsenal",
  "Arsenal FC": "arsenal",
  "Liverpool FC": "liverpool",
  "Chelsea FC": "chelsea",
  "Manchester United": "man-united",
  "Bayern de Múnich": "bayern",
  "Paris Saint-Germain": "psg",
  "Inter": "inter",
  "AC Milan": "milan",
  "Borussia Dortmund": "dortmund",
  "Sevilla FC": "sevilla",
  "Newcastle": "newcastle",
  "Tottenham Hotspur": "tottenham",
  "Bayer 04 Leverkusen": "leverkusen",
  "Atalanta": "atalanta",
  "Girona FC": "girona",
  "AS Monaco": "monaco",
  "SE Palmeiras": "palmeiras",
  "Stade Rennais": "rennes",
  "River Plate": "river-plate",
  "Olympique de Marsella": "marseille",
};

/** IDs API-Football por nombre (fallback si no hay PNG local). */
const CLUB_AF_BY_NAME = {
  "Real Madrid": 541,
  "FC Barcelona": 529,
  "Atlético de Madrid": 530,
  "Manchester City": 50,
  "Arsenal": 42,
  "Arsenal FC": 42,
  "Liverpool FC": 40,
  "Chelsea FC": 49,
  "Manchester United": 33,
  "Bayern de Múnich": 157,
  "Paris Saint-Germain": 85,
  "Inter": 505,
  "AC Milan": 489,
  "Borussia Dortmund": 165,
  "Sevilla FC": 536,
  "Newcastle": 34,
  "Tottenham Hotspur": 47,
  "Bayer 04 Leverkusen": 168,
  "Atalanta": 499,
  "Girona FC": 547,
  "AS Monaco": 91,
  "SE Palmeiras": 121,
  "Stade Rennais": 94,
  "River Plate": 435,
  "Olympique de Marsella": 81,
};

/** IDs API-Football de ligas (escudos CDN). */
const LEAGUE_AF_BY_NAME = {
  "LaLiga": 140,
  "LaLiga EA Sports": 140,
  "La Liga": 140,
  "Premier League": 39,
  "Serie A": 135,
  "Bundesliga": 78,
  "Ligue 1": 61,
  "Eredivisie": 88,
  "Liga Portugal": 94,
  "Brasileirão Serie A": 71,
  "Major League Soccer": 253,
  "Saudi Pro League": 307,
  "Champions League": 2,
  "UEFA Champions League": 2,
  "Europa League": 3,
  "UEFA Europa League": 3,
  "Conference League": 848,
  "World Cup": 1,
  "Euro Championship": 4,
  "Copa del Rey": 143,
  "FA Cup": 45,
  "DFB Pokal": 81,
  "Coppa Italia": 137,
  "Coupe de France": 66,
  "Championship": 40,
  "LaLiga 2": 141,
  "Segunda División": 141,
  "Serie B": 136,
  "2. Bundesliga": 79,
  "Ligue 2": 62,
};

function resolveLeagueAfId(compOrName) {
  if (compOrName == null) return null;
  if (typeof compOrName === "object") {
    if (compOrName.afId) return compOrName.afId;
    if (compOrName.logoAfId) return compOrName.logoAfId;
    const n = compOrName.name || compOrName.league || "";
    if (LEAGUE_AF_BY_NAME[n]) return LEAGUE_AF_BY_NAME[n];
    const hit = LEAGUES.find(
      (l) =>
        normalize(l.name) === normalize(n) ||
        normalize(n).includes(normalize(l.name).slice(0, 8)) ||
        normalize(l.name).includes(normalize(n).slice(0, 8))
    );
    return hit?.afId || null;
  }
  const name = String(compOrName);
  if (LEAGUE_AF_BY_NAME[name]) return LEAGUE_AF_BY_NAME[name];
  const hit = LEAGUES.find((l) => normalize(l.name) === normalize(name) || normalize(name).includes(normalize(l.name)));
  return hit?.afId || null;
}

function leagueBadgeHTML(compOrName, size = "") {
  const name =
    typeof compOrName === "object"
      ? compOrName.name || compOrName.league || "Liga"
      : String(compOrName || "Liga");
  const afId = resolveLeagueAfId(compOrName);
  const logo = afLeagueLogo(afId);
  const short = (name || "LG").replace(/[^A-Za-z0-9]/g, "").slice(0, 2).toUpperCase() || "LG";
  const mod = size ? ` badge-league--${size}` : "";
  if (logo) {
    return `<span class="badge-league badge-league--img${mod}" title="${name}" data-fallback="${short}"><img src="${logo}" alt="" loading="lazy" decoding="async" onerror="this.onerror=null;const p=this.parentElement;p.classList.remove('badge-league--img');p.textContent=p.dataset.fallback||'LG';"></span>`;
  }
  return `<span class="badge-league${mod}" title="${name}">${short}</span>`;
}

/** Ligas indexadas para el buscador global / demo. */
const LEAGUES = [
  { id: "laliga",     name: "LaLiga EA Sports",  country: "España",     teams: 20, players: 512, tier: 1, afId: 140 },
  { id: "premier",    name: "Premier League",    country: "Inglaterra", teams: 20, players: 534, tier: 1, afId: 39 },
  { id: "seriea",     name: "Serie A",           country: "Italia",     teams: 20, players: 548, tier: 1, afId: 135 },
  { id: "bundesliga", name: "Bundesliga",        country: "Alemania",   teams: 18, players: 486, tier: 1, afId: 78 },
  { id: "ligue1",     name: "Ligue 1",           country: "Francia",    teams: 18, players: 471, tier: 1, afId: 61 },
  { id: "eredivisie", name: "Eredivisie",        country: "Países Bajos", teams: 18, players: 442, tier: 2, afId: 88 },
  { id: "liga-pt",    name: "Liga Portugal",     country: "Portugal",   teams: 18, players: 458, tier: 2, afId: 94 },
  { id: "brasileirao",name: "Brasileirão Serie A", country: "Brasil",   teams: 20, players: 601, tier: 2, afId: 71 },
  { id: "mls",        name: "Major League Soccer", country: "EE. UU.",  teams: 30, players: 870, tier: 2, afId: 253 },
  { id: "saudi",      name: "Saudi Pro League",  country: "Arabia Saudí", teams: 18, players: 466, tier: 2, afId: 307 }
];

/**
 * Jugadores. Formato pensado para mapear 1:1 con una tabla SQL:
 *   valueHistory → [año, valor en millones de €]
 *   attrs        → índices 0-100 usados por el motor de puntuación
 */
const PLAYERS = [
  {
    id: "yamal", name: "Lamine Yamal", shirt: 10, age: 19, birth: "13/07/2007",
    nationality: "España", flag: "🇪🇸", position: "Extremo derecho", pos: "ED",
    club: "barcelona", contract: 2031, height: 180, foot: "Izquierdo", value: 200,
    stats: { matches: 51, goals: 21, assists: 24, minutes: 4032 },
    attrs: { ritmo: 91, tiro: 84, pase: 88, regate: 95, defensa: 34, fisico: 68 },
    valueHistory: [[2023, 20], [2024, 90], [2025, 150], [2026, 200]],
    career: [
      { club: "FC Barcelona", from: 2023, to: null, apps: 132, goals: 42 },
      { club: "Barcelona Atlètic", from: 2022, to: 2023, apps: 12, goals: 3 }
    ]
  },
  {
    id: "haaland", name: "Erling Haaland", shirt: 9, age: 26, birth: "21/07/2000",
    nationality: "Noruega", flag: "🇳🇴", position: "Delantero centro", pos: "DC",
    club: "man-city", contract: 2034, height: 195, foot: "Izquierdo", value: 180,
    stats: { matches: 47, goals: 45, assists: 7, minutes: 3866 },
    attrs: { ritmo: 89, tiro: 96, pase: 68, regate: 78, defensa: 42, fisico: 94 },
    valueHistory: [[2020, 60], [2021, 110], [2022, 150], [2023, 180], [2024, 180], [2025, 175], [2026, 180]],
    career: [
      { club: "Manchester City", from: 2022, to: null, apps: 198, goals: 182 },
      { club: "Borussia Dortmund", from: 2020, to: 2022, apps: 89, goals: 86 },
      { club: "RB Salzburg", from: 2019, to: 2020, apps: 27, goals: 29 },
      { club: "Molde FK", from: 2017, to: 2019, apps: 50, goals: 20 }
    ]
  },
  {
    id: "bellingham", name: "Jude Bellingham", shirt: 5, age: 23, birth: "29/06/2003",
    nationality: "Inglaterra", flag: "🇬🇧", position: "Mediocentro ofensivo", pos: "MCO",
    club: "real-madrid", contract: 2029, height: 186, foot: "Derecho", value: 180,
    stats: { matches: 49, goals: 18, assists: 13, minutes: 4114 },
    attrs: { ritmo: 82, tiro: 86, pase: 87, regate: 87, defensa: 74, fisico: 88 },
    valueHistory: [[2021, 45], [2022, 80], [2023, 120], [2024, 180], [2025, 180], [2026, 180]],
    career: [
      { club: "Real Madrid", from: 2023, to: null, apps: 141, goals: 52 },
      { club: "Borussia Dortmund", from: 2020, to: 2023, apps: 132, goals: 24 },
      { club: "Birmingham City", from: 2019, to: 2020, apps: 44, goals: 4 }
    ]
  },
  {
    id: "mbappe", name: "Kylian Mbappé", shirt: 10, age: 27, birth: "20/12/1998",
    nationality: "Francia", flag: "🇫🇷", position: "Delantero centro", pos: "DC",
    club: "real-madrid", contract: 2029, height: 178, foot: "Derecho", value: 170,
    stats: { matches: 52, goals: 42, assists: 11, minutes: 4260 },
    attrs: { ritmo: 97, tiro: 93, pase: 82, regate: 93, defensa: 30, fisico: 79 },
    valueHistory: [[2019, 200], [2020, 180], [2021, 160], [2022, 160], [2023, 180], [2024, 180], [2025, 170], [2026, 170]],
    career: [
      { club: "Real Madrid", from: 2024, to: null, apps: 96, goals: 78 },
      { club: "Paris Saint-Germain", from: 2017, to: 2024, apps: 308, goals: 256 },
      { club: "AS Monaco", from: 2015, to: 2017, apps: 60, goals: 27 }
    ]
  },
  {
    id: "vinicius", name: "Vinícius Júnior", shirt: 7, age: 26, birth: "12/07/2000",
    nationality: "Brasil", flag: "🇧🇷", position: "Extremo izquierdo", pos: "EI",
    club: "real-madrid", contract: 2027, height: 176, foot: "Derecho", value: 160,
    stats: { matches: 46, goals: 22, assists: 17, minutes: 3644 },
    attrs: { ritmo: 95, tiro: 84, pase: 80, regate: 94, defensa: 32, fisico: 71 },
    valueHistory: [[2020, 40], [2021, 60], [2022, 100], [2023, 150], [2024, 200], [2025, 180], [2026, 160]],
    career: [
      { club: "Real Madrid", from: 2018, to: null, apps: 328, goals: 108 },
      { club: "CR Flamengo", from: 2017, to: 2018, apps: 54, goals: 13 }
    ]
  },
  {
    id: "musiala", name: "Jamal Musiala", shirt: 42, age: 23, birth: "26/02/2003",
    nationality: "Alemania", flag: "🇩🇪", position: "Mediocentro ofensivo", pos: "MCO",
    club: "bayern", contract: 2030, height: 184, foot: "Derecho", value: 150,
    stats: { matches: 43, goals: 19, assists: 14, minutes: 3288 },
    attrs: { ritmo: 86, tiro: 82, pase: 85, regate: 95, defensa: 52, fisico: 70 },
    valueHistory: [[2021, 45], [2022, 80], [2023, 110], [2024, 130], [2025, 140], [2026, 150]],
    career: [
      { club: "Bayern de Múnich", from: 2020, to: null, apps: 227, goals: 76 },
      { club: "Chelsea Academy", from: 2011, to: 2019, apps: 0, goals: 0 }
    ]
  },
  {
    id: "wirtz", name: "Florian Wirtz", shirt: 7, age: 23, birth: "03/05/2003",
    nationality: "Alemania", flag: "🇩🇪", position: "Mediocentro ofensivo", pos: "MCO",
    club: "liverpool", contract: 2030, height: 177, foot: "Derecho", value: 145,
    stats: { matches: 45, goals: 14, assists: 20, minutes: 3555 },
    attrs: { ritmo: 82, tiro: 80, pase: 92, regate: 91, defensa: 55, fisico: 68 },
    valueHistory: [[2021, 40], [2022, 70], [2023, 85], [2024, 130], [2025, 140], [2026, 145]],
    career: [
      { club: "Liverpool FC", from: 2025, to: null, apps: 45, goals: 14 },
      { club: "Bayer 04 Leverkusen", from: 2020, to: 2025, apps: 197, goals: 57 },
      { club: "1. FC Köln", from: 2010, to: 2020, apps: 0, goals: 0 }
    ]
  },
  {
    id: "pedri", name: "Pedri", shirt: 8, age: 23, birth: "25/11/2002",
    nationality: "España", flag: "🇪🇸", position: "Mediocentro", pos: "MC",
    club: "barcelona", contract: 2030, height: 174, foot: "Derecho", value: 140,
    stats: { matches: 44, goals: 8, assists: 15, minutes: 3520 },
    attrs: { ritmo: 76, tiro: 74, pase: 94, regate: 90, defensa: 70, fisico: 66 },
    valueHistory: [[2021, 50], [2022, 80], [2023, 100], [2024, 100], [2025, 130], [2026, 140]],
    career: [
      { club: "FC Barcelona", from: 2020, to: null, apps: 214, goals: 26 },
      { club: "UD Las Palmas", from: 2019, to: 2020, apps: 36, goals: 4 }
    ]
  },
  {
    id: "saka", name: "Bukayo Saka", shirt: 7, age: 24, birth: "05/09/2001",
    nationality: "Inglaterra", flag: "🇬🇧", position: "Extremo derecho", pos: "ED",
    club: "arsenal", contract: 2027, height: 178, foot: "Izquierdo", value: 140,
    stats: { matches: 48, goals: 17, assists: 19, minutes: 3936 },
    attrs: { ritmo: 88, tiro: 84, pase: 86, regate: 90, defensa: 58, fisico: 74 },
    valueHistory: [[2021, 55], [2022, 80], [2023, 110], [2024, 140], [2025, 140], [2026, 140]],
    career: [{ club: "Arsenal FC", from: 2018, to: null, apps: 302, goals: 84 }]
  },
  {
    id: "foden", name: "Phil Foden", shirt: 47, age: 26, birth: "28/05/2000",
    nationality: "Inglaterra", flag: "🇬🇧", position: "Mediocentro ofensivo", pos: "MCO",
    club: "man-city", contract: 2027, height: 171, foot: "Izquierdo", value: 120,
    stats: { matches: 45, goals: 16, assists: 12, minutes: 3420 },
    attrs: { ritmo: 84, tiro: 87, pase: 88, regate: 92, defensa: 56, fisico: 64 },
    valueHistory: [[2021, 70], [2022, 90], [2023, 110], [2024, 150], [2025, 130], [2026, 120]],
    career: [{ club: "Manchester City", from: 2017, to: null, apps: 356, goals: 102 }]
  },
  {
    id: "valverde", name: "Federico Valverde", shirt: 15, age: 28, birth: "22/07/1998",
    nationality: "Uruguay", flag: "🇺🇾", position: "Mediocentro", pos: "MC",
    club: "real-madrid", contract: 2029, height: 182, foot: "Derecho", value: 115,
    stats: { matches: 54, goals: 9, assists: 11, minutes: 4590 },
    attrs: { ritmo: 87, tiro: 85, pase: 86, regate: 80, defensa: 82, fisico: 90 },
    valueHistory: [[2021, 60], [2022, 70], [2023, 100], [2024, 110], [2025, 130], [2026, 115]],
    career: [
      { club: "Real Madrid", from: 2018, to: null, apps: 348, goals: 44 },
      { club: "RC Deportivo", from: 2017, to: 2018, apps: 21, goals: 2 },
      { club: "Peñarol", from: 2015, to: 2016, apps: 14, goals: 1 }
    ]
  },
  {
    id: "rodri", name: "Rodri", shirt: 16, age: 30, birth: "22/06/1996",
    nationality: "España", flag: "🇪🇸", position: "Mediocentro defensivo", pos: "MCD",
    club: "man-city", contract: 2027, height: 191, foot: "Derecho", value: 110,
    stats: { matches: 41, goals: 6, assists: 9, minutes: 3567 },
    attrs: { ritmo: 66, tiro: 78, pase: 93, regate: 80, defensa: 90, fisico: 87 },
    valueHistory: [[2021, 70], [2022, 80], [2023, 100], [2024, 130], [2025, 110], [2026, 110]],
    career: [
      { club: "Manchester City", from: 2019, to: null, apps: 322, goals: 33 },
      { club: "Atlético de Madrid", from: 2018, to: 2019, apps: 47, goals: 3 },
      { club: "Villarreal CF", from: 2015, to: 2018, apps: 93, goals: 3 }
    ]
  },
  {
    id: "julian", name: "Julián Álvarez", shirt: 19, age: 26, birth: "31/01/2000",
    nationality: "Argentina", flag: "🇦🇷", position: "Delantero centro", pos: "DC",
    club: "atletico", contract: 2030, height: 170, foot: "Derecho", value: 110,
    stats: { matches: 50, goals: 28, assists: 8, minutes: 4050 },
    attrs: { ritmo: 88, tiro: 88, pase: 80, regate: 87, defensa: 48, fisico: 76 },
    valueHistory: [[2022, 25], [2023, 50], [2024, 75], [2025, 100], [2026, 110]],
    career: [
      { club: "Atlético de Madrid", from: 2024, to: null, apps: 98, goals: 51 },
      { club: "Manchester City", from: 2022, to: 2024, apps: 103, goals: 36 },
      { club: "River Plate", from: 2018, to: 2022, apps: 121, goals: 54 }
    ]
  },
  {
    id: "vitinha", name: "Vitinha", shirt: 17, age: 26, birth: "13/02/2000",
    nationality: "Portugal", flag: "🇵🇹", position: "Mediocentro", pos: "MC",
    club: "psg", contract: 2029, height: 172, foot: "Derecho", value: 100,
    stats: { matches: 49, goals: 10, assists: 13, minutes: 4116 },
    attrs: { ritmo: 78, tiro: 79, pase: 92, regate: 89, defensa: 76, fisico: 70 },
    valueHistory: [[2022, 30], [2023, 40], [2024, 60], [2025, 90], [2026, 100]],
    career: [
      { club: "Paris Saint-Germain", from: 2022, to: null, apps: 196, goals: 26 },
      { club: "FC Porto", from: 2020, to: 2022, apps: 70, goals: 6 },
      { club: "Wolverhampton", from: 2019, to: 2020, apps: 22, goals: 1 }
    ]
  },
  {
    id: "doue", name: "Désiré Doué", shirt: 14, age: 21, birth: "03/06/2005",
    nationality: "Francia", flag: "🇫🇷", position: "Extremo derecho", pos: "ED",
    club: "psg", contract: 2029, height: 181, foot: "Izquierdo", value: 95,
    stats: { matches: 44, goals: 13, assists: 15, minutes: 3080 },
    attrs: { ritmo: 89, tiro: 80, pase: 84, regate: 92, defensa: 45, fisico: 72 },
    valueHistory: [[2023, 15], [2024, 30], [2025, 60], [2026, 95]],
    career: [
      { club: "Paris Saint-Germain", from: 2024, to: null, apps: 88, goals: 24 },
      { club: "Stade Rennais", from: 2022, to: 2024, apps: 68, goals: 8 }
    ]
  },
  {
    id: "cubarsi", name: "Pau Cubarsí", shirt: 2, age: 19, birth: "22/01/2007",
    nationality: "España", flag: "🇪🇸", position: "Defensa central", pos: "DFC",
    club: "barcelona", contract: 2029, height: 184, foot: "Derecho", value: 90,
    stats: { matches: 46, goals: 2, assists: 3, minutes: 3910 },
    attrs: { ritmo: 78, tiro: 40, pase: 85, regate: 74, defensa: 88, fisico: 76 },
    valueHistory: [[2024, 15], [2025, 60], [2026, 90]],
    career: [
      { club: "FC Barcelona", from: 2024, to: null, apps: 92, goals: 3 },
      { club: "Barcelona Atlètic", from: 2023, to: 2024, apps: 18, goals: 1 }
    ]
  },
  {
    id: "saliba", name: "William Saliba", shirt: 2, age: 25, birth: "24/03/2001",
    nationality: "Francia", flag: "🇫🇷", position: "Defensa central", pos: "DFC",
    club: "arsenal", contract: 2030, height: 192, foot: "Derecho", value: 85,
    stats: { matches: 47, goals: 3, assists: 2, minutes: 4183 },
    attrs: { ritmo: 86, tiro: 42, pase: 79, regate: 70, defensa: 91, fisico: 89 },
    valueHistory: [[2022, 25], [2023, 55], [2024, 80], [2025, 80], [2026, 85]],
    career: [
      { club: "Arsenal FC", from: 2019, to: null, apps: 178, goals: 8 },
      { club: "Olympique Marsella", from: 2021, to: 2022, apps: 51, goals: 2 },
      { club: "AS Saint-Étienne", from: 2018, to: 2019, apps: 34, goals: 1 }
    ]
  },
  {
    id: "estevao", name: "Estêvão Willian", shirt: 41, age: 19, birth: "24/04/2007",
    nationality: "Brasil", flag: "🇧🇷", position: "Extremo derecho", pos: "ED",
    club: "chelsea", contract: 2033, height: 176, foot: "Izquierdo", value: 80,
    stats: { matches: 42, goals: 15, assists: 9, minutes: 2940 },
    attrs: { ritmo: 91, tiro: 82, pase: 78, regate: 92, defensa: 32, fisico: 63 },
    valueHistory: [[2024, 20], [2025, 45], [2026, 80]],
    career: [
      { club: "Chelsea FC", from: 2025, to: null, apps: 42, goals: 15 },
      { club: "SE Palmeiras", from: 2022, to: 2025, apps: 76, goals: 22 }
    ]
  },
  {
    id: "zaire-emery", name: "Warren Zaïre-Emery", shirt: 33, age: 20, birth: "08/03/2006",
    nationality: "Francia", flag: "🇫🇷", position: "Mediocentro", pos: "MC",
    club: "psg", contract: 2029, height: 178, foot: "Derecho", value: 80,
    stats: { matches: 45, goals: 6, assists: 10, minutes: 3555 },
    attrs: { ritmo: 80, tiro: 72, pase: 87, regate: 82, defensa: 81, fisico: 79 },
    valueHistory: [[2023, 25], [2024, 60], [2025, 70], [2026, 80]],
    career: [{ club: "Paris Saint-Germain", from: 2022, to: null, apps: 152, goals: 15 }]
  },
  {
    id: "gavi", name: "Gavi", shirt: 6, age: 21, birth: "05/08/2004",
    nationality: "España", flag: "🇪🇸", position: "Mediocentro", pos: "MC",
    club: "barcelona", contract: 2030, height: 173, foot: "Derecho", value: 70,
    stats: { matches: 38, goals: 5, assists: 8, minutes: 2584 },
    attrs: { ritmo: 79, tiro: 70, pase: 86, regate: 87, defensa: 78, fisico: 72 },
    valueHistory: [[2022, 50], [2023, 90], [2024, 60], [2025, 60], [2026, 70]],
    career: [{ club: "FC Barcelona", from: 2021, to: null, apps: 164, goals: 12 }]
  },
  {
    id: "guler", name: "Arda Güler", shirt: 15, age: 21, birth: "25/02/2005",
    nationality: "Turquía", flag: "🇹🇷", position: "Mediocentro ofensivo", pos: "MCO",
    club: "real-madrid", contract: 2029, height: 176, foot: "Izquierdo", value: 70,
    stats: { matches: 40, goals: 9, assists: 12, minutes: 2600 },
    attrs: { ritmo: 74, tiro: 84, pase: 90, regate: 88, defensa: 48, fisico: 62 },
    valueHistory: [[2023, 18], [2024, 25], [2025, 45], [2026, 70]],
    career: [
      { club: "Real Madrid", from: 2023, to: null, apps: 84, goals: 18 },
      { club: "Fenerbahçe", from: 2021, to: 2023, apps: 51, goals: 7 }
    ]
  },
  {
    id: "hakimi", name: "Achraf Hakimi", shirt: 2, age: 27, birth: "04/11/1998",
    nationality: "Marruecos", flag: "🇲🇦", position: "Lateral derecho", pos: "LD",
    club: "psg", contract: 2029, height: 181, foot: "Derecho", value: 70,
    stats: { matches: 46, goals: 7, assists: 12, minutes: 3910 },
    attrs: { ritmo: 94, tiro: 74, pase: 82, regate: 84, defensa: 76, fisico: 82 },
    valueHistory: [[2021, 65], [2022, 70], [2023, 65], [2024, 60], [2025, 70], [2026, 70]],
    career: [
      { club: "Paris Saint-Germain", from: 2021, to: null, apps: 232, goals: 27 },
      { club: "Inter de Milán", from: 2020, to: 2021, apps: 45, goals: 7 },
      { club: "Borussia Dortmund", from: 2018, to: 2020, apps: 73, goals: 12 },
      { club: "Real Madrid", from: 2017, to: 2018, apps: 17, goals: 2 }
    ]
  },
  {
    id: "kane", name: "Harry Kane", shirt: 9, age: 33, birth: "28/07/1993",
    nationality: "Inglaterra", flag: "🇬🇧", position: "Delantero centro", pos: "DC",
    club: "bayern", contract: 2027, height: 188, foot: "Derecho", value: 70,
    stats: { matches: 46, goals: 41, assists: 12, minutes: 3956 },
    attrs: { ritmo: 68, tiro: 94, pase: 88, regate: 80, defensa: 47, fisico: 84 },
    valueHistory: [[2021, 120], [2022, 100], [2023, 90], [2024, 100], [2025, 80], [2026, 70]],
    career: [
      { club: "Bayern de Múnich", from: 2023, to: null, apps: 142, goals: 128 },
      { club: "Tottenham Hotspur", from: 2011, to: 2023, apps: 435, goals: 280 }
    ]
  },
  {
    id: "mainoo", name: "Kobbie Mainoo", shirt: 37, age: 21, birth: "19/04/2005",
    nationality: "Inglaterra", flag: "🇬🇧", position: "Mediocentro", pos: "MC",
    club: "man-united", contract: 2027, height: 175, foot: "Derecho", value: 65,
    stats: { matches: 39, goals: 4, assists: 6, minutes: 2925 },
    attrs: { ritmo: 76, tiro: 72, pase: 86, regate: 88, defensa: 77, fisico: 74 },
    valueHistory: [[2024, 35], [2025, 55], [2026, 65]],
    career: [{ club: "Manchester United", from: 2023, to: null, apps: 92, goals: 8 }]
  },
  {
    id: "mastantuono", name: "Franco Mastantuono", shirt: 30, age: 19, birth: "14/08/2007",
    nationality: "Argentina", flag: "🇦🇷", position: "Mediocentro ofensivo", pos: "MCO",
    club: "real-madrid", contract: 2031, height: 177, foot: "Izquierdo", value: 60,
    stats: { matches: 36, goals: 8, assists: 7, minutes: 2340 },
    attrs: { ritmo: 82, tiro: 83, pase: 85, regate: 88, defensa: 44, fisico: 66 },
    valueHistory: [[2024, 8], [2025, 35], [2026, 60]],
    career: [
      { club: "Real Madrid", from: 2025, to: null, apps: 36, goals: 8 },
      { club: "River Plate", from: 2024, to: 2025, apps: 64, goals: 13 }
    ]
  },
  {
    id: "endrick", name: "Endrick", shirt: 16, age: 20, birth: "21/07/2006",
    nationality: "Brasil", flag: "🇧🇷", position: "Delantero centro", pos: "DC",
    club: "real-madrid", contract: 2030, height: 173, foot: "Izquierdo", value: 55,
    stats: { matches: 34, goals: 12, assists: 4, minutes: 1870 },
    attrs: { ritmo: 89, tiro: 85, pase: 68, regate: 84, defensa: 30, fisico: 74 },
    valueHistory: [[2023, 35], [2024, 40], [2025, 45], [2026, 55]],
    career: [
      { club: "Real Madrid", from: 2024, to: null, apps: 62, goals: 20 },
      { club: "SE Palmeiras", from: 2022, to: 2024, apps: 82, goals: 21 }
    ]
  },
  {
    id: "davies", name: "Alphonso Davies", shirt: 19, age: 25, birth: "02/11/2000",
    nationality: "Canadá", flag: "🇨🇦", position: "Lateral izquierdo", pos: "LI",
    club: "bayern", contract: 2030, height: 183, foot: "Izquierdo", value: 55,
    stats: { matches: 40, goals: 3, assists: 9, minutes: 3320 },
    attrs: { ritmo: 96, tiro: 66, pase: 80, regate: 87, defensa: 74, fisico: 80 },
    valueHistory: [[2021, 80], [2022, 70], [2023, 70], [2024, 60], [2025, 50], [2026, 55]],
    career: [
      { club: "Bayern de Múnich", from: 2019, to: null, apps: 258, goals: 17 },
      { club: "Vancouver Whitecaps", from: 2016, to: 2018, apps: 66, goals: 8 }
    ]
  },
  {
    id: "salah", name: "Mohamed Salah", shirt: 11, age: 34, birth: "15/06/1992",
    nationality: "Egipto", flag: "🇪🇬", position: "Extremo derecho", pos: "ED",
    club: "liverpool", contract: 2027, height: 175, foot: "Izquierdo", value: 45,
    stats: { matches: 48, goals: 26, assists: 18, minutes: 4128 },
    attrs: { ritmo: 87, tiro: 89, pase: 82, regate: 88, defensa: 40, fisico: 72 },
    valueHistory: [[2021, 100], [2022, 100], [2023, 85], [2024, 65], [2025, 55], [2026, 45]],
    career: [
      { club: "Liverpool FC", from: 2017, to: null, apps: 448, goals: 262 },
      { club: "AS Roma", from: 2016, to: 2017, apps: 41, goals: 19 },
      { club: "Chelsea FC", from: 2014, to: 2016, apps: 19, goals: 2 },
      { club: "FC Basel", from: 2012, to: 2014, apps: 79, goals: 20 }
    ]
  },
  {
    id: "donnarumma", name: "Gianluigi Donnarumma", shirt: 1, age: 27, birth: "25/02/1999",
    nationality: "Italia", flag: "🇮🇹", position: "Portero", pos: "POR",
    club: "man-city", contract: 2030, height: 196, foot: "Derecho", value: 45,
    stats: { matches: 42, goals: 0, assists: 1, minutes: 3780 },
    attrs: { ritmo: 52, tiro: 30, pase: 72, regate: 44, defensa: 89, fisico: 86 },
    valueHistory: [[2021, 60], [2022, 55], [2023, 50], [2024, 40], [2025, 40], [2026, 45]],
    career: [
      { club: "Manchester City", from: 2025, to: null, apps: 42, goals: 0 },
      { club: "Paris Saint-Germain", from: 2021, to: 2025, apps: 161, goals: 0 },
      { club: "AC Milan", from: 2015, to: 2021, apps: 251, goals: 0 }
    ]
  }
];

/**
 * Movimientos de mercado (demo).
 * type: "Traspaso" | "Cesión" | "Libre"
 * fee: millones de € (null en cesión; 0 en libre; <1 = miles, p.ej. 0.15 → 150 mil €)
 */
const TRANSFERS = [
  { playerId: "mastantuono", from: "River Plate", to: "Real Madrid", fee: 63.2, type: "Traspaso" },
  { playerId: "wirtz", from: "Bayer 04 Leverkusen", to: "Liverpool FC", fee: 125, type: "Traspaso" },
  { playerId: "estevao", from: "SE Palmeiras", to: "Chelsea FC", fee: 45, type: "Traspaso" },
  { playerId: "doue", from: "Stade Rennais", to: "Paris Saint-Germain", fee: 50, type: "Traspaso" },
  { playerId: "donnarumma", from: "Paris Saint-Germain", to: "Manchester City", fee: 35, type: "Traspaso" },
  { playerId: "julian", from: "Manchester City", to: "Atlético de Madrid", fee: 75, type: "Traspaso" },
  { playerId: "mbappe", from: "Paris Saint-Germain", to: "Real Madrid", fee: 0, type: "Libre" },
  { playerId: "kane", from: "Tottenham Hotspur", to: "Bayern de Múnich", fee: 95, type: "Traspaso" },
  { playerId: "endrick", from: "SE Palmeiras", to: "Real Madrid", fee: 35, type: "Traspaso" },
  { playerId: "cubarsi", from: "FC Barcelona", to: "Girona FC", fee: null, type: "Cesión" },
  { playerId: "zaire-emery", from: "Paris Saint-Germain", to: "AS Monaco", fee: null, type: "Cesión" },
  { playerId: "pedri", from: "FC Barcelona", to: "Manchester City", fee: 0.15, type: "Traspaso" },
];

/** Rumores actuales (demo). pct null = desconocido (?); trend: up | down | flat */
const RUMORS = [
  { playerId: "pedri", club: "FC Barcelona", interested: "Manchester City", pct: 62, trend: "up" },
  { playerId: "vinicius", club: "Real Madrid", interested: "Saudi Pro League", pct: 18, trend: "down" },
  { playerId: "bellingham", club: "Real Madrid", interested: "Bayern de Múnich", pct: null, trend: "flat" },
  { playerId: "musiala", club: "Bayern de Múnich", interested: "FC Barcelona", pct: 41, trend: "up" },
  { playerId: "haaland", club: "Manchester City", interested: "Real Madrid", pct: 33, trend: "down" },
  { playerId: "doue", club: "Paris Saint-Germain", interested: "Chelsea FC", pct: 55, trend: "up" },
];

/** Partidos del día (demo). status: live | scheduled | finished */
const MATCHES = [
  { id: "m1", league: "LaLiga", home: "Real Madrid", away: "FC Barcelona", homeScore: 2, awayScore: 1, minute: 67, status: "live", kickoff: "21:00" },
  { id: "m2", league: "Premier League", home: "Arsenal", away: "Liverpool FC", homeScore: 1, awayScore: 1, minute: 54, status: "live", kickoff: "17:30" },
  { id: "m3", league: "Serie A", home: "Inter", away: "AC Milan", homeScore: 0, awayScore: 0, minute: 12, status: "live", kickoff: "20:45" },
  { id: "m4", league: "Bundesliga", home: "Bayern de Múnich", away: "Borussia Dortmund", homeScore: null, awayScore: null, minute: null, status: "scheduled", kickoff: "18:30" },
  { id: "m5", league: "Ligue 1", home: "Paris Saint-Germain", away: "Olympique de Marsella", homeScore: null, awayScore: null, minute: null, status: "scheduled", kickoff: "21:00" },
  { id: "m6", league: "LaLiga", home: "Atlético de Madrid", away: "Sevilla FC", homeScore: 3, awayScore: 0, minute: 90, status: "finished", kickoff: "14:00" },
  { id: "m7", league: "Premier League", home: "Manchester City", away: "Chelsea FC", homeScore: null, awayScore: null, minute: null, status: "scheduled", kickoff: "16:00" },
  { id: "m8", league: "Champions League", home: "Bayer 04 Leverkusen", away: "Atalanta", homeScore: 1, awayScore: 2, minute: 78, status: "live", kickoff: "21:00" },
];

/**
 * Detalle demo MATCH_EVENT (modelo IFLXI).
 * - Sin event_type=assist (asistencia = secondaryPlayer en goal/penalty_goal)
 * - substitution_out: player = SALE, secondaryPlayer = ENTRA
 * - Marcador oficial solo en MATCH (homeScore/awayScore); no recalcular desde events
 */
const MATCH_DETAILS = {
  m1: {
    events: [
      { id: "e1", type: "goal", label: "Gol", minute: 12, extraMinute: null, clock: "12'", side: "home",
        player: { id: "vinicius", name: "Vinícius Jr" },
        secondaryPlayer: { id: "bellingham", name: "Bellingham" },
        detail: "Asistencia: Bellingham" },
      { id: "e2", type: "yellow_card", label: "Amarilla", minute: 28, extraMinute: null, clock: "28'", side: "away",
        player: { id: "pedri", name: "Pedri" }, secondaryPlayer: null, detail: null },
      { id: "e3", type: "goal", label: "Gol", minute: 41, extraMinute: null, clock: "41'", side: "away",
        player: { id: "lewandowski", name: "Lewandowski" }, secondaryPlayer: null, detail: null },
      { id: "e4", type: "substitution_out", label: "Cambio", minute: 55, extraMinute: null, clock: "55'", side: "home",
        player: { id: "camavinga", name: "Camavinga" },
        secondaryPlayer: { id: "tchouameni", name: "Tchouaméni" },
        detail: "Camavinga → Tchouaméni" },
      { id: "e5", type: "goal", label: "Gol", minute: 67, extraMinute: null, clock: "67'", side: "home",
        player: { id: "mbappe", name: "Mbappé" }, secondaryPlayer: null, detail: null },
    ],
    scoreSource: "match",
  },
  m6: {
    events: [
      { id: "e10", type: "goal", label: "Gol", minute: 8, clock: "8'", side: "home",
        player: { id: "griezmann", name: "Griezmann" },
        secondaryPlayer: { id: "depaul", name: "De Paul" },
        detail: "Asistencia: De Paul" },
      { id: "e11", type: "penalty_goal", label: "Penalti", minute: 33, clock: "33'", side: "home",
        player: { id: "alvarez", name: "Julián Álvarez" }, secondaryPlayer: null, detail: null },
      { id: "e12", type: "second_yellow", label: "Segunda amarilla", minute: 61, clock: "61'", side: "away",
        player: { id: "demo-sev", name: "Jugador Sevilla" }, secondaryPlayer: null, detail: null },
      { id: "e13", type: "goal", label: "Gol", minute: 77, clock: "77'", side: "home",
        player: { id: "griezmann", name: "Griezmann" }, secondaryPlayer: null, detail: null },
    ],
    scoreSource: "match",
  },
};

/** Contadores globales de la plataforma. */
const GLOBAL_STATS = {
  players: 500000,
  teams: 20000,
  leagues: 200,
  countries: 178,
  marketValue: 62.4 // miles de millones de €
};

/* ==========================================================================
   2. API — único punto de acceso a los datos
   --------------------------------------------------------------------------
   Hoy resuelve desde memoria. Para conectar una base de datos real basta
   con reemplazar el cuerpo de cada método por su llamada `fetch`, ya que
   todos devuelven promesas y la UI nunca toca los arrays directamente.
     Ej.:  getPlayer: id => fetch(`/api/players/${id}`).then(r => r.json())
   ========================================================================== */

const LATENCY = 80; // ms simulados de red

const resolve = (value, ms = LATENCY) =>
  new Promise((done) => setTimeout(() => done(value), ms));

/** Detecta si `server.py` está sirviendo /api (Postgres live). */
const LIVE = { enabled: null };

async function detectLive() {
  if (LIVE.enabled !== null) return LIVE.enabled;
  try {
    const r = await fetch("/api/health", { cache: "no-store" });
    const j = await r.json();
    LIVE.enabled = !!(j && j.ok);
  } catch {
    LIVE.enabled = false;
  }
  if (LIVE.enabled) {
    document.documentElement.dataset.live = "1";
    const pill = document.querySelector(".badge-pill");
    if (pill) {
      pill.innerHTML = `<span class="dot"></span> En vivo desde PostgreSQL · <b>IFLXI</b>`;
    }
  }
  return LIVE.enabled;
}

async function jget(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status} ${url}`);
  return r.json();
}

const apiMock = {
  getGlobalStats: () => resolve({ ...GLOBAL_STATS }, 0),

  getPlayers: (options = {}) => {
    let list = PLAYERS.slice();
    if (options.maxAge) list = list.filter((p) => p.age <= options.maxAge);
    if (options.club) list = list.filter((p) => p.club === options.club);
    if (options.sort === "value") list.sort((a, b) => b.value - a.value);
    if (options.sort === "rating") list.sort((a, b) => aiRating(b) - aiRating(a));
    if (options.sort === "potential") list.sort((a, b) => aiPotential(b) - aiPotential(a));
    if (options.limit) list = list.slice(0, options.limit);
    return resolve(list);
  },

  getPlayer: (id) => resolve(PLAYERS.find((p) => p.id === id) || null),

  getClub: (id) => {
    const base = CLUBS[id];
    if (!base) return resolve(null);
    const squad = PLAYERS.filter((p) => p.club === id).map((p) => ({
      ...p,
      clubInfo: { id, ...base },
      value: p.value,
      nationality: p.nationality,
    }));
    return resolve({ id, ...base, founded: 1900, squadSize: squad.length, squad, lab: buildLabFromSquad(squad) });
  },

  getLabShowcase: () =>
    resolve({
      clubs: Object.entries(CLUBS)
        .slice(0, 8)
        .map(([cid, c]) => ({
          id: cid,
          ...c,
          squadSize: PLAYERS.filter((p) => p.club === cid).length || 18,
        })),
    }),

  getTransfers: (limit = 8) => resolve(TRANSFERS.slice(0, limit)),

  getRumors: (limit = 6) => resolve(RUMORS.slice(0, limit)),

  getMatches: (options = {}) => {
    let list = MATCHES.slice();
    if (options.status === "live") list = list.filter((m) => m.status === "live");
    if (options.limit) list = list.slice(0, options.limit);
    return resolve(list);
  },

  getMatch: (id) => {
    const base = MATCHES.find((m) => m.id === id);
    if (!base) return resolve(null);
    const extra = MATCH_DETAILS[id] || { events: [], scoreSource: "match" };
    return resolve({ ...base, ...extra });
  },

  getCompetitions: (options = {}) => {
    let list = LEAGUES.map((l) => ({
      id: l.id,
      name: l.name,
      shortName: l.name,
      type: "league",
      scope: "domestic",
      country: l.country,
      season: "2025/26",
      yearStart: 2025,
      yearEnd: 2026,
      teams: l.teams,
      isActive: true,
      afId: l.afId,
      tier: l.tier,
    }));
    const q = normalize(options.q || "");
    if (q) list = list.filter((c) => normalize(c.name).includes(q) || normalize(c.country).includes(q));
    if (options.type) list = list.filter((c) => c.type === options.type);
    if (options.country) {
      const cq = normalize(options.country);
      list = list.filter((c) => normalize(c.country).includes(cq));
    }
    const limit = options.limit || 60;
    const offset = options.offset || 0;
    return resolve({ total: list.length, limit, offset, items: list.slice(offset, offset + limit) });
  },

  getCompetition: (id) => {
    const base = LEAGUES.find((l) => l.id === id);
    if (!base) return resolve(null);
    const clubList = Object.entries(CLUBS)
      .filter(([, c]) => normalize(c.league).includes(normalize(base.name).slice(0, 6)) || normalize(base.name).includes(normalize(c.league).slice(0, 6)))
      .map(([cid, c]) => ({
        id: cid,
        name: c.name,
        short: c.short,
        league: c.league,
        country: c.country,
        c1: c.c1,
        c2: c.c2,
        afId: c.afId,
        squadSize: PLAYERS.filter((p) => p.club === cid).length || null,
      }));
    return resolve({
      id: base.id,
      name: base.name,
      type: "league",
      country: base.country,
      season: "2025/26",
      yearStart: 2025,
      yearEnd: 2026,
      teams: clubList.length || base.teams,
      afId: base.afId,
      tier: base.tier,
      clubList,
    });
  },

  search: (query) => {
    const q = normalize(query);
    if (q.length < 1) return resolve({ players: [], teams: [], leagues: [] }, 0);

    const players = PLAYERS.filter(
      (p) =>
        normalize(p.name).includes(q) ||
        normalize(p.nationality).includes(q) ||
        normalize(p.position).includes(q) ||
        normalize(clubOf(p).name).includes(q) ||
        normalize(clubOf(p).league).includes(q)
    )
      .sort((a, b) => b.value - a.value)
      .slice(0, 6);

    const teams = Object.entries(CLUBS)
      .filter(([id, c]) => normalize(c.name).includes(q) || normalize(id).includes(q))
      .slice(0, 4)
      .map(([id, c]) => ({ id, ...c }));

    const leagues = LEAGUES.filter(
      (l) => normalize(l.name).includes(q) || normalize(l.country).includes(q)
    ).slice(0, 4);

    return resolve({ players, teams, leagues }, 60);
  }
};

const apiLive = {
  getGlobalStats: () => jget("/api/stats"),

  getPlayers: (options = {}) => {
    const params = new URLSearchParams();
    if (options.limit) params.set("limit", options.limit);
    if (options.maxAge) params.set("maxAge", options.maxAge);
    if (options.club) params.set("club", options.club);
    if (options.sort) params.set("sort", options.sort === "potential" ? "potential" : options.sort === "value" ? "value" : "featured");
    return jget(`/api/players?${params}`);
  },

  getPlayer: (id) => jget(`/api/players/${encodeURIComponent(id)}`).catch(() => null),

  getClub: (id) => jget(`/api/teams/${encodeURIComponent(id)}`).catch(() => null),

  getLabShowcase: () => jget("/api/lab/showcase?limit=8").catch(() => ({ clubs: [] })),

  getTransfers: async (limit = 8) => {
    try {
      const list = await jget(`/api/transfers?limit=${limit}`);
      if (Array.isArray(list) && list.length) return list;
    } catch {
      /* vacío o API caída */
    }
    return TRANSFERS.slice(0, limit);
  },

  getRumors: async (limit = 6) => RUMORS.slice(0, limit),

  getMatches: async (options = {}) => {
    const params = new URLSearchParams();
    if (options.status) params.set("status", options.status);
    if (options.limit) params.set("limit", options.limit);
    const qs = params.toString();
    try {
      const list = await jget(`/api/matches${qs ? `?${qs}` : ""}`);
      if (Array.isArray(list) && list.length) return list;
    } catch {
      /* BD vacía o API caída → demo */
    }
    let list = MATCHES.slice();
    if (options.status === "live") list = list.filter((m) => m.status === "live");
    if (options.limit) list = list.slice(0, options.limit);
    return list;
  },

  getMatch: async (id) => {
    try {
      return await jget(`/api/matches/${encodeURIComponent(id)}`);
    } catch {
      const base = MATCHES.find((m) => m.id === id);
      if (!base) return null;
      const extra = MATCH_DETAILS[id] || { events: [], scoreSource: "match" };
      return { ...base, ...extra };
    }
  },

  getCompetitions: async (options = {}) => {
    const params = new URLSearchParams();
    if (options.q) params.set("q", options.q);
    if (options.type) params.set("type", options.type);
    if (options.country) params.set("country", options.country);
    if (options.limit) params.set("limit", options.limit);
    if (options.offset != null) params.set("offset", options.offset);
    try {
      return await jget(`/api/competitions?${params}`);
    } catch {
      return apiMock.getCompetitions(options);
    }
  },

  getCompetition: async (id) => {
    try {
      return await jget(`/api/competitions/${encodeURIComponent(id)}`);
    } catch {
      return apiMock.getCompetition(id);
    }
  },

  search: (query) => {
    const q = String(query || "").trim();
    if (q.length < 1) return Promise.resolve({ players: [], teams: [], leagues: [] });
    return jget(`/api/search?q=${encodeURIComponent(q)}`);
  }
};

const api = new Proxy(apiMock, {
  get(target, prop) {
    return async (...args) => {
      const live = await detectLive();
      const src = live ? apiLive : apiMock;
      return src[prop](...args);
    };
  }
});

/* ==========================================================================
   3. CORE — utilidades y motor de análisis
   ========================================================================== */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const nf = new Intl.NumberFormat("es-ES");
const nf0 = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 });

const normalize = (str) =>
  String(str).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();

const clamp = (n, min, max) => Math.min(max, Math.max(min, n));

const formatNumber = (n) => nf.format(n);

/** 170 → "170 M €" · null/undefined → "Sin valor" · 0 → "Libre" */
function formatValue(millions, { free = "Libre", empty = "Sin valor" } = {}) {
  if (millions === null || millions === undefined || Number.isNaN(millions)) return empty;
  if (millions === 0) return free;
  if (millions >= 1000) return `${nf1.format(millions / 1000)} MM €`;
  return `${nf1.format(millions)} M €`;
}

/** Coste de fichaje estilo Transfermarkt: Cesión / Libre / 150 mil € / 125,00 mill. € */
function formatTransferCost(transfer) {
  const type = String(transfer.type || "").toLowerCase();
  if (type === "cesión" || type === "cesion") return "Cesión";
  if (type === "libre" || transfer.fee === 0) return "Libre";
  const fee = transfer.fee;
  if (fee == null || Number.isNaN(fee)) return "—";
  if (fee < 1) {
    const mil = Math.round(fee * 1000);
    return `${nf0.format(mil)} mil €`;
  }
  const nf2 = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${nf2.format(fee)} mill. €`;
}

function formatAge(age) {
  if (age === null || age === undefined || age === "" || Number.isNaN(age)) return "—";
  return `${age} años`;
}

function initials(name) {
  const words = name.split(/\s+/).filter((w) => w.length > 2);
  if (words.length === 0) return name.slice(0, 2).toUpperCase();
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return words.slice(0, 2).map((w) => w[0].toUpperCase()).join("");
}

/** Color determinista a partir de un texto (para escudos sin imagen). */
function colorsFromText(text) {
  let hash = 0;
  for (let i = 0; i < text.length; i++) hash = (hash * 31 + text.charCodeAt(i)) % 360;
  return { c1: `hsl(${hash} 55% 26%)`, c2: `hsl(${(hash + 40) % 360} 60% 12%)` };
}

function clubOf(player) {
  if (player && player.clubInfo) return player.clubInfo;
  return CLUBS[player.club] || { name: player.club || "Sin club", short: "—", league: "—", country: "—", c1: "#1d2636", c2: "#0d1119" };
}

/* --- Motor de puntuación "IA" -------------------------------------------- */

const POSITION_GROUP = {
  POR: "POR", DFC: "DEF", LI: "DEF", LD: "DEF",
  MCD: "MID", MC: "MID", MCO: "MID",
  EI: "ATT", ED: "ATT", DC: "ATT", SD: "ATT"
};

const RATING_WEIGHTS = {
  POR: { ritmo: 0.05, tiro: 0.03, pase: 0.20, regate: 0.05, defensa: 0.47, fisico: 0.20 },
  DEF: { ritmo: 0.15, tiro: 0.04, pase: 0.16, regate: 0.09, defensa: 0.41, fisico: 0.15 },
  MID: { ritmo: 0.11, tiro: 0.14, pase: 0.31, regate: 0.20, defensa: 0.14, fisico: 0.10 },
  ATT: { ritmo: 0.20, tiro: 0.30, pase: 0.13, regate: 0.25, defensa: 0.02, fisico: 0.10 }
};

const ATTR_LABELS = {
  ritmo: "Ritmo", tiro: "Tiro", pase: "Pase",
  regate: "Regate", defensa: "Defensa", fisico: "Físico"
};

/** Puntuación IA global (0-100) ponderada según la demarcación. */
function aiRating(player) {
  if (!player?.attrs) return null;
  const group = POSITION_GROUP[player.pos] || "MID";
  const w = RATING_WEIGHTS[group];
  const base = Object.keys(w).reduce((sum, k) => sum + (player.attrs[k] || 0) * w[k], 0);
  const impact = productivity(player) * 3.2;
  return Math.round(clamp(base + impact, 40, 99) * 10) / 10;
}

/** Techo estimado: la juventud suma potencial. */
function aiPotential(player) {
  const rating = aiRating(player);
  if (rating == null) return null;
  const age = player.age;
  if (age == null) return rating;
  const youth = Math.max(0, 24 - age);
  return Math.round(clamp(rating + youth * 1.35, rating, 99) * 10) / 10;
}

/** Goles + asistencias por 90 minutos. */
function productivity(player) {
  const { goals, assists, minutes } = player.stats;
  if (!minutes) return 0;
  return ((goals + assists) * 90) / minutes;
}

/** Afinidad 0-100 entre dos jugadores según su perfil de atributos. */
function affinity(a, b) {
  if (!a?.attrs || !b?.attrs) return 0;
  const keys = Object.keys(ATTR_LABELS);
  const distance = Math.sqrt(
    keys.reduce((sum, k) => sum + Math.pow((a.attrs[k] || 0) - (b.attrs[k] || 0), 2), 0) / keys.length
  );
  const samePos = a.pos === b.pos ? 8 : POSITION_GROUP[a.pos] === POSITION_GROUP[b.pos] ? 4 : -10;
  const ageGap = Math.abs((a.age || 25) - (b.age || 25)) * 0.5;
  return Math.round(clamp(100 - distance * 2.4 + samePos - ageGap, 35, 99));
}

/** Los N jugadores con el perfil más parecido. */
function similarPlayers(player, limit = 4) {
  return PLAYERS.filter((p) => p.id !== player.id)
    .map((p) => ({ player: p, score: affinity(player, p) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

/** Tendencia del valor de mercado en el último año registrado. */
function valueTrend(player) {
  const h = player.valueHistory || [];
  if (h.length < 2) return { diff: 0, pct: 0, unknown: player.value == null };
  const [, last] = h[h.length - 1];
  const [, prev] = h[h.length - 2];
  return { diff: last - prev, pct: prev ? Math.round(((last - prev) / prev) * 100) : 0, unknown: false };
}

/* ==========================================================================
   4. UI — componentes reutilizables
   ========================================================================== */

function playerPhotoURL(player) {
  if (!player) return null;
  if (player.photo) return player.photo;
  const afId = player.afId || PLAYER_AF_IDS[player.id];
  return afPlayerPhoto(afId);
}

function clubLogoURL(nameOrClub) {
  if (!nameOrClub) return null;
  if (typeof nameOrClub === "object") {
    if (nameOrClub.logo) return nameOrClub.logo;
    if (nameOrClub.id && CLUBS[nameOrClub.id]?.logo) return CLUBS[nameOrClub.id].logo;
    if (nameOrClub.afId) {
      const local = Object.values(CLUBS).find((c) => c.afId === nameOrClub.afId);
      if (local?.logo) return local.logo;
    }
    nameOrClub = nameOrClub.name;
  }
  const known = Object.entries(CLUBS).find(([, c]) => c.name === nameOrClub);
  if (known?.[1]?.logo) return known[1].logo;
  if (known?.[0]) return `img/clubs/${known[0]}.png?v=5`;
  const slug = CLUB_LOGO_SLUG[nameOrClub];
  if (slug) return `img/clubs/${slug}.png?v=5`;
  // Sin CDN con fondo blanco: mejor iniciales que cuadrado blanco
  return null;
}

function avatarHTML(player, modifier = "") {
  const club = clubOf(player);
  const photo = playerPhotoURL(player);
  const fallback = initials(player.name);
  const src = photo
    ? `<img src="${photo}" alt="" loading="lazy" decoding="async" onerror="this.onerror=null;const p=this.parentElement;p.classList.remove('avatar--photo');p.textContent=p.dataset.fallback||'';">`
    : fallback;
  return `<div class="avatar ${modifier}${photo ? " avatar--photo" : ""}" style="--c1:${club.c1};--c2:${club.c2}" data-fallback="${fallback}">${src}</div>`;
}

function clubBadgeHTML(name) {
  const known = Object.values(CLUBS).find((c) => c.name === name);
  const { c1, c2 } = known || colorsFromText(name);
  const short = known ? known.short : initials(name) || "FC";
  const logo = clubLogoURL(name);
  if (logo) {
    return `<span class="badge-club badge-club--img" title="${name}" data-fallback="${short}" data-c1="${c1}" data-c2="${c2}"><img src="${logo}" alt="" loading="lazy" decoding="async" onerror="this.onerror=null;const p=this.parentElement;p.classList.remove('badge-club--img');p.style.background='linear-gradient(150deg,'+p.dataset.c1+','+p.dataset.c2+')';p.textContent=p.dataset.fallback||'FC';"></span>`;
  }
  return `<span class="badge-club" style="background:linear-gradient(150deg,${c1},${c2})" title="${name}">${short}</span>`;
}

const ICON_AI = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1M7.7 16.3l-2.1 2.1"/><circle cx="12" cy="12" r="3.2"/></svg>';

function playerCardHTML(player) {
  const club = clubOf(player);
  const rating = aiRating(player);
  const stats = player.stats || { matches: 0, goals: 0, assists: 0 };
  return `
    <a class="player-card" href="jugador.html?id=${player.id}" data-reveal>
      <span class="pos-tag">${player.pos}</span>
      <div class="player-card__top">
        ${avatarHTML(player)}
        <div>
          <div class="player-card__name">${player.name}</div>
          <div class="player-card__club">${clubBadgeHTML(club.name)} ${club.name}</div>
        </div>
      </div>
      <div class="player-card__stats">
        <div class="mini-stat"><b>${stats.matches || "—"}</b><span>PJ</span></div>
        <div class="mini-stat"><b>${stats.goals || "—"}</b><span>Goles</span></div>
        <div class="mini-stat"><b>${stats.assists || "—"}</b><span>Asist.</span></div>
      </div>
      <div class="player-card__footer">
        <span class="value-tag">${formatValue(player.value)}</span>
        ${rating != null ? `<span class="ai-score">${ICON_AI} ${nf1.format(rating)}</span>` : `<span class="tag">BD</span>`}
      </div>
    </a>`;
}

function talentCardHTML(player) {
  const club = clubOf(player);
  const potential = aiPotential(player);
  const fill = potential != null ? potential : 0;
  return `
    <a class="talent-card" href="jugador.html?id=${player.id}" data-reveal>
      <span class="talent-card__age">${player.age != null ? player.age : "—"}</span>
      ${avatarHTML(player)}
      <div class="player-card__name" style="margin-top:14px">${player.name}</div>
      <div class="player-card__club">${clubBadgeHTML(club.name)} ${club.name}</div>
      <div class="label-row"><span>Edad</span><b>${formatAge(player.age)}</b></div>
      <div class="progress"><span data-fill="${fill}"></span></div>
      <div class="label-row"><span>Valor</span><b class="value-tag">${formatValue(player.value)}</b></div>
    </a>`;
}

const ICON_ARROW = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h13m-5-6 6 6-6 6"/></svg>';

/** Fila de "Últimos fichajes" (home) para un fichaje REAL de la API (no demo).
 * La API da: playerId, player (nombre), from, to, type (ENUM: permanent/loan/
 * loan_end/free/end_of_contract/academy_promotion/unknown), fee (euros en
 * crudo o null), currency. No hay foto de jugador en este endpoint, por eso
 * no usa avatarHTML/PLAYERS (que son solo el elenco de ejemplo). */
function realTransferRowHTML(t) {
  if (!t || !t.player) return "";
  const from = t.from || "Agente libre";
  const to = t.to || "—";
  let cost;
  let costClass = "fee";
  if (t.type === "loan" || t.type === "loan_end") {
    cost = "Cesión";
    costClass = "fee fee--loan";
  } else if (t.type === "free" || t.type === "end_of_contract" || t.fee === 0) {
    cost = "Libre";
    costClass = "fee fee--free";
  } else if (t.fee != null) {
    const millions = t.fee / 1_000_000;
    cost =
      millions < 1
        ? `${nf0.format(Math.round(t.fee / 1000))} mil €`
        : `${new Intl.NumberFormat("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(millions)} mill. €`;
  } else {
    cost = "—";
  }
  const routeTitle = `${from} → ${to}`;
  const fallback = initials(t.player);
  return `
    <tr data-href="jugador.html?id=${t.playerId}" title="${routeTitle}">
      <td>
        <div class="cell-player">
          <div class="avatar avatar--sm" style="--c1:#1a1a1a;--c2:#3a3a3a">${fallback}</div>
          <div>
            <b class="tm-link">${t.player}</b>
          </div>
        </div>
      </td>
      <td class="td-route">
        <div class="transfer-route transfer-route--badges" title="${routeTitle}">
          <span class="club-only" title="${from}">${clubBadgeHTML(from)}</span>
          <span class="transfer-route__arrow" aria-hidden="true">${ICON_ARROW}</span>
          <span class="club-only" title="${to}">${clubBadgeHTML(to)}</span>
        </div>
      </td>
      <td class="${costClass}">${cost}</td>
    </tr>`;
}

function transferRowHTML(transfer) {
  const player = PLAYERS.find((p) => p.id === transfer.playerId);
  if (!player) return "";
  const cost = formatTransferCost(transfer);
  const costClass =
    cost === "Cesión" ? "fee fee--loan" : cost === "Libre" ? "fee fee--free" : "fee";
  const routeTitle = `${transfer.from} → ${transfer.to}`;
  return `
    <tr data-href="jugador.html?id=${player.id}" title="${routeTitle}">
      <td>
        <div class="cell-player">
          ${avatarHTML(player, "avatar--sm")}
          <div>
            <b class="tm-link">${player.name}</b>
            <small>${player.position || player.pos}</small>
          </div>
        </div>
      </td>
      <td class="td-route">
        <div class="transfer-route transfer-route--badges" title="${routeTitle}">
          <span class="club-only" title="${transfer.from}">${clubBadgeHTML(transfer.from)}</span>
          <span class="transfer-route__arrow" aria-hidden="true">${ICON_ARROW}</span>
          <span class="club-only" title="${transfer.to}">${clubBadgeHTML(transfer.to)}</span>
        </div>
      </td>
      <td class="${costClass}">${cost}</td>
    </tr>`;
}

/** Convierte el % de un rumor en una etiqueta de fiabilidad Baja/Media/Alta. */
function rumorLevelHTML(pct) {
  if (pct == null) return `<span class="rumor-pct rumor-pct--unk">Sin datos</span>`;
  if (pct >= 60) return `<span class="rumor-pct rumor-pct--up">Alta</span>`;
  if (pct >= 35) return `<span class="rumor-pct rumor-pct--flat">Media</span>`;
  return `<span class="rumor-pct rumor-pct--down">Baja</span>`;
}

function rumorRowHTML(rumor) {
  const player = PLAYERS.find((p) => p.id === rumor.playerId);
  const name = player?.name || rumor.player || "—";
  const club = rumor.club || (player ? clubOf(player).name : "—");
  const pct = rumorLevelHTML(rumor.pct);
  return `
    <tr${player ? ` data-href="jugador.html?id=${player.id}"` : ""}>
      <td>
        <div class="cell-player">
          ${player ? avatarHTML(player, "avatar--sm") : ""}
          <div>
            <b class="tm-link">${name}</b>
            <small class="cell-club-inline">${clubBadgeHTML(club)} ${club}</small>
          </div>
        </div>
      </td>
      <td class="td-club">
        <span class="club-only" title="${rumor.interested}">${clubBadgeHTML(rumor.interested)}</span>
      </td>
      <td>${pct}</td>
    </tr>`;
}

function topValuedRowHTML(player) {
  const club = clubOf(player);
  return `
    <tr data-href="jugador.html?id=${player.id}">
      <td>
        <div class="cell-player">
          ${avatarHTML(player, "avatar--sm")}
          <div>
            <b class="tm-link">${player.name}</b>
            <small>${player.position || player.pos}</small>
          </div>
        </div>
      </td>
      <td class="td-club">
        <span class="club-only" title="${club.name}">${clubBadgeHTML(club.name)}</span> ${club.name}
      </td>
      <td class="fee">${formatValue(player.value)}</td>
    </tr>`;
}

/** Fila de "fichajes top de verano": como transferRowHTML pero solo con el club de destino. */
function topTransferRowHTML(transfer) {
  const player = PLAYERS.find((p) => p.id === transfer.playerId);
  if (!player) return "";
  const cost = formatTransferCost(transfer);
  const costClass =
    cost === "Cesión" ? "fee fee--loan" : cost === "Libre" ? "fee fee--free" : "fee";
  return `
    <tr data-href="jugador.html?id=${player.id}">
      <td>
        <div class="cell-player">
          ${avatarHTML(player, "avatar--sm")}
          <div>
            <b class="tm-link">${player.name}</b>
            <small>${player.position || player.pos}</small>
          </div>
        </div>
      </td>
      <td class="td-club">
        <span class="club-only" title="${transfer.to}">${clubBadgeHTML(transfer.to)}</span> ${transfer.to}
      </td>
      <td class="${costClass}">${cost}</td>
    </tr>`;
}

function matchCardHTML(match) {
  /* Tarjeta compacta (home / grids) */
  const isLive = match.status === "live";
  const isDone = match.status === "finished";
  const score =
    match.homeScore != null
      ? `<span class="match-card__score">${match.homeScore} – ${match.awayScore}</span>`
      : `<span class="match-card__kick">${match.kickoff || "—"}</span>`;
  const badge = isLive
    ? `<span class="match-card__live"><span class="dot"></span> ${match.minute ?? "—"}'</span>`
    : isDone
      ? `<span class="tag">Final</span>`
      : `<span class="tag">${match.kickoff || "—"}</span>`;
  const href = `partido.html?id=${encodeURIComponent(match.id)}`;
  return `
    <a class="match-card ${isLive ? "match-card--live" : ""}" href="${href}">
      <div class="match-card__meta">
        <span class="match-card__league">${leagueBadgeHTML(match.league)} <span>${match.league || "—"}</span></span>
        ${badge}
      </div>
      <div class="match-card__teams">
        <div class="match-card__team">
          ${clubBadgeHTML(match.home)}
          <span>${match.home}</span>
        </div>
        ${score}
        <div class="match-card__team match-card__team--away">
          <span>${match.away}</span>
          ${clubBadgeHTML(match.away)}
        </div>
      </div>
    </a>`;
}

function matchRowHTML(match) {
  /* Fila estilo resultados (partidos.html) */
  const isLive = match.status === "live";
  const isDone = match.status === "finished";
  const statusBit = isLive
    ? `<span class="match-row__live"><span class="dot"></span>${match.minute ?? "—"}'</span>`
    : isDone
      ? `<span class="match-row__final">Final</span>`
      : `<span class="match-row__kick">${match.kickoff || "—"}</span>`;
  const score =
    match.homeScore != null
      ? `<span class="match-row__score"><b>${match.homeScore}</b><span>:</span><b>${match.awayScore}</b></span>`
      : `<span class="match-row__score match-row__score--kick">–</span>`;
  const href = `partido.html?id=${encodeURIComponent(match.id)}`;
  return `
    <a class="match-row ${isLive ? "match-row--live" : ""} ${isDone ? "match-row--done" : ""}" href="${href}">
      <div class="match-row__status">${statusBit}</div>
      <div class="match-row__home">
        <span class="match-row__name">${match.home}</span>
        ${clubBadgeHTML(match.home)}
      </div>
      ${score}
      <div class="match-row__away">
        ${clubBadgeHTML(match.away)}
        <span class="match-row__name">${match.away}</span>
      </div>
    </a>`;
}

function matchLeagueBlockHTML(leagueName, matches) {
  return `
    <section class="match-block">
      <header class="match-block__head">
        ${leagueBadgeHTML(leagueName, "md")}
        <div class="match-block__titles">
          <h2>${leagueName}</h2>
          <span>${matches.length} partido${matches.length === 1 ? "" : "s"}</span>
        </div>
      </header>
      <div class="match-block__list">
        ${matches.map(matchRowHTML).join("")}
      </div>
    </section>`;
}

function matchEventRowHTML(ev) {
  const side = ev.side === "away" ? "match-event--away" : ev.side === "home" ? "match-event--home" : "";
  const icon =
    ev.type === "goal" || ev.type === "penalty_goal"
      ? "⚽"
      : ev.type === "own_goal"
        ? "⚽"
        : ev.type === "yellow_card"
          ? "🟨"
          : ev.type === "second_yellow" || ev.type === "red_card"
            ? "🟥"
            : ev.type === "substitution_out"
              ? "🔄"
              : ev.type === "penalty_miss"
                ? "□"
                : "·";
  const who = ev.player?.name || "—";
  const sub = ev.detail
    ? `<span class="match-event__detail">${ev.detail}</span>`
    : "";
  const playerLink = ev.player?.id
    ? `<a href="jugador.html?id=${encodeURIComponent(ev.player.id)}">${who}</a>`
    : who;
  return `
    <li class="match-event ${side}">
      <span class="match-event__clock">${ev.clock || "—"}</span>
      <span class="match-event__icon" aria-hidden="true">${icon}</span>
      <div class="match-event__body">
        <b>${ev.label || ev.type}</b>
        <span class="match-event__who">${playerLink}</span>
        ${sub}
      </div>
    </li>`;
}

function matchDetailHTML(match) {
  const isLive = match.status === "live";
  const score =
    match.homeScore != null
      ? `${match.homeScore} – ${match.awayScore}`
      : "–";
  const statusLabel = isLive
    ? `${match.minute ?? "—"}'`
    : match.status === "finished"
      ? "Final"
      : match.kickoff || "Programado";
  const events = Array.isArray(match.events) ? match.events : [];
  const timeline = events.length
    ? `<ol class="match-events">${events.map(matchEventRowHTML).join("")}</ol>`
    : `<p class="empty-note">Sin eventos cargados aún. El marcador oficial no depende de la timeline.</p>`;

  return `
    <section class="match-detail reveal">
      <div class="match-detail__league">
        ${leagueBadgeHTML(match.league, "md")}
        <span>${match.league || "—"}</span>
      </div>
      <div class="match-detail__board">
        <div class="match-detail__side">
          <span class="match-detail__crest">${clubBadgeHTML(match.home)}</span>
          <h1>${match.home}</h1>
        </div>
        <div class="match-detail__scoreblock">
          <div class="match-detail__score">${score}</div>
          <div class="match-detail__status">${statusLabel}</div>
        </div>
        <div class="match-detail__side match-detail__side--away">
          <span class="match-detail__crest">${clubBadgeHTML(match.away)}</span>
          <h1>${match.away}</h1>
        </div>
      </div>
      <div class="match-detail__timeline">
        <h2>Timeline</h2>
        ${timeline}
      </div>
    </section>`;
}

/* --- Gráfico de evolución de valor (SVG puro) ---------------------------- */

function renderValueChart(host, history) {
  const W = 720, H = 280;
  const pad = { t: 24, r: 18, b: 38, l: 52 };
  const innerW = W - pad.l - pad.r;
  const innerH = H - pad.t - pad.b;

  const values = history.map(([, v]) => v);
  const max = Math.max(...values) * 1.18 || 10;
  const min = 0;

  const x = (i) => pad.l + (history.length === 1 ? innerW / 2 : (i / (history.length - 1)) * innerW);
  const y = (v) => pad.t + innerH - ((v - min) / (max - min)) * innerH;

  const points = history.map(([year, v], i) => ({ year, v, cx: x(i), cy: y(v) }));
  const line = points.map((p, i) => `${i ? "L" : "M"}${p.cx.toFixed(1)},${p.cy.toFixed(1)}`).join(" ");
  const area = `${line} L${points[points.length - 1].cx.toFixed(1)},${pad.t + innerH} L${points[0].cx.toFixed(1)},${pad.t + innerH} Z`;

  const ticks = 4;
  const gridY = Array.from({ length: ticks + 1 }, (_, i) => {
    const value = min + ((max - min) / ticks) * i;
    const py = y(value);
    return `
      <line x1="${pad.l}" y1="${py.toFixed(1)}" x2="${W - pad.r}" y2="${py.toFixed(1)}" stroke="rgba(255,255,255,.06)" />
      <text x="${pad.l - 12}" y="${(py + 4).toFixed(1)}" text-anchor="end" fill="#5d6678" font-size="11">${Math.round(value)}M</text>`;
  }).join("");

  const labelsX = points
    .map((p) => `<text x="${p.cx.toFixed(1)}" y="${H - 12}" text-anchor="middle" fill="#5d6678" font-size="11">${p.year}</text>`)
    .join("");

  const dots = points
    .map(
      (p, i) => `<circle class="chart-dot" data-i="${i}" cx="${p.cx.toFixed(1)}" cy="${p.cy.toFixed(1)}" r="4.5"
        fill="#06080d" stroke="#00e5a0" stroke-width="2.5" />`
    )
    .join("");

  host.style.position = "relative";
  host.innerHTML = `
    <svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img"
         aria-label="Evolución del valor de mercado">
      <defs>
        <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#00e5a0" stop-opacity=".38" />
          <stop offset="100%" stop-color="#00e5a0" stop-opacity="0" />
        </linearGradient>
        <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#00e5a0" />
          <stop offset="100%" stop-color="#4d7cff" />
        </linearGradient>
      </defs>
      ${gridY}
      <path d="${area}" fill="url(#areaGrad)" />
      <path class="chart-line" d="${line}" fill="none" stroke="url(#lineGrad)" stroke-width="3"
            stroke-linecap="round" stroke-linejoin="round" />
      ${dots}
      ${labelsX}
    </svg>
    <div class="chart-tip"></div>`;

  // Animación de trazado
  const path = $(".chart-line", host);
  const length = path.getTotalLength();
  path.style.strokeDasharray = length;
  path.style.strokeDashoffset = length;
  requestAnimationFrame(() => {
    path.style.transition = "stroke-dashoffset 1.4s cubic-bezier(.22,1,.36,1)";
    path.style.strokeDashoffset = "0";
  });

  // Tooltip
  const tip = $(".chart-tip", host);
  const svg = $("svg", host);
  $$(".chart-dot", host).forEach((dot) => {
    const show = () => {
      const p = points[Number(dot.dataset.i)];
      const rect = svg.getBoundingClientRect();
      tip.innerHTML = `${p.year} · <b>${formatValue(p.v)}</b>`;
      tip.style.left = `${(p.cx / W) * rect.width}px`;
      tip.style.top = `${(p.cy / H) * rect.height}px`;
      tip.classList.add("is-visible");
      dot.setAttribute("r", "6.5");
    };
    const hide = () => {
      tip.classList.remove("is-visible");
      dot.setAttribute("r", "4.5");
    };
    dot.addEventListener("mouseenter", show);
    dot.addEventListener("mouseleave", hide);
    dot.addEventListener("touchstart", show, { passive: true });
  });
}

/* --- Gráfico radar (comparador) ------------------------------------------ */

function renderRadarChart(host, playerA, playerB) {
  const size = 340, cx = size / 2, cy = size / 2, radius = 118;
  const keys = Object.keys(ATTR_LABELS);
  const step = (Math.PI * 2) / keys.length;

  const point = (i, ratio) => {
    const angle = i * step - Math.PI / 2;
    return [cx + Math.cos(angle) * radius * ratio, cy + Math.sin(angle) * radius * ratio];
  };

  const rings = [0.25, 0.5, 0.75, 1]
    .map((r) => {
      const pts = keys.map((_, i) => point(i, r).map((n) => n.toFixed(1)).join(",")).join(" ");
      return `<polygon points="${pts}" fill="none" stroke="rgba(255,255,255,.07)" />`;
    })
    .join("");

  const axes = keys
    .map((_, i) => {
      const [px, py] = point(i, 1);
      return `<line x1="${cx}" y1="${cy}" x2="${px.toFixed(1)}" y2="${py.toFixed(1)}" stroke="rgba(255,255,255,.06)" />`;
    })
    .join("");

  const labels = keys
    .map((k, i) => {
      const [px, py] = point(i, 1.22);
      return `<text x="${px.toFixed(1)}" y="${(py + 4).toFixed(1)}" text-anchor="middle" fill="#8a94a8" font-size="11.5">${ATTR_LABELS[k]}</text>`;
    })
    .join("");

  const shape = (player, color) => {
    const pts = keys
      .map((k, i) => point(i, player.attrs[k] / 100).map((n) => n.toFixed(1)).join(","))
      .join(" ");
    return `<polygon points="${pts}" fill="${color}22" stroke="${color}" stroke-width="2" stroke-linejoin="round" />`;
  };

  host.innerHTML = `
    <svg viewBox="0 0 ${size} ${size}" width="100%" style="max-width:360px" role="img"
         aria-label="Comparativa de atributos">
      ${rings}${axes}
      ${shape(playerA, "#00e5a0")}
      ${shape(playerB, "#b45cff")}
      ${labels}
    </svg>`;
}

/* --- Comportamientos globales -------------------------------------------- */

function applyTheme(theme) {
  const dark = theme === "dark";
  if (dark) document.documentElement.setAttribute("data-theme", "dark");
  else document.documentElement.removeAttribute("data-theme");
  try {
    localStorage.setItem("iflxi-theme", dark ? "dark" : "light");
  } catch (_) {}
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", dark ? "#06080d" : "#f3f5f9");
  $$("[data-theme-toggle]").forEach((btn) => {
    btn.setAttribute("aria-pressed", String(dark));
    btn.title = dark ? "Cambiar a modo claro" : "Cambiar a modo oscuro";
  });
}

function initTheme() {
  let theme = "light";
  try {
    theme = localStorage.getItem("iflxi-theme") === "dark" ? "dark" : "light";
  } catch (_) {}
  applyTheme(theme);
  $$("[data-theme-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
    });
  });
}

function initHeader() {
  const header = $(".header");
  if (!header) return;

  const onScroll = () => header.classList.toggle("is-stuck", window.scrollY > 12);
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  const burger = $(".burger");
  const nav = $(".nav");
  if (burger && nav) {
    burger.addEventListener("click", () => {
      const open = nav.classList.toggle("is-open");
      burger.setAttribute("aria-expanded", String(open));
    });
    nav.addEventListener("click", (e) => {
      if (e.target.closest("a")) nav.classList.remove("is-open");
    });
  }

  const page = document.body.dataset.page;
  $$(".nav a").forEach((a) => a.classList.toggle("is-active", a.dataset.nav === page));
}

const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-visible");
      revealObserver.unobserve(entry.target);
    });
  },
  { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
);

function observeReveals(root = document) {
  $$("[data-reveal]", root).forEach((el, i) => {
    el.style.transitionDelay = `${Math.min(i * 45, 320)}ms`;
    revealObserver.observe(el);
  });
}

/** Rellena barras (.progress span[data-fill] y .bar i[data-fill]) al entrar en pantalla. */
function animateBars(root = document) {
  const bars = $$("[data-fill]", root);
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.style.width = `${entry.target.dataset.fill}%`;
        io.unobserve(entry.target);
      });
    },
    { threshold: 0.4 }
  );
  bars.forEach((b) => io.observe(b));
}

/** Contadores animados con easing. */
function animateCounters(root = document) {
  const easeOut = (t) => 1 - Math.pow(1 - t, 3);
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        io.unobserve(el);

        const target = Number(el.dataset.count);
        const decimals = Number(el.dataset.decimals || 0);
        const suffix = el.dataset.suffix || "";
        const duration = 1600;
        const start = performance.now();

        const tick = (now) => {
          const t = clamp((now - start) / duration, 0, 1);
          const value = target * easeOut(t);
          el.textContent =
            (decimals
              ? new Intl.NumberFormat("es-ES", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(value)
              : nf.format(Math.round(value))) + suffix;
          if (t < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
    },
    { threshold: 0.4 }
  );
  $$("[data-count]", root).forEach((el) => io.observe(el));
}

/** Buscador global (header y/o hero) con navegación por teclado. */
function initSearch() {
  const boxes = $$(".searchbox");
  if (!boxes.length) return;

  const bindBox = (box, { isPrimary = false } = {}) => {
    const input = $("input", box);
    const results = $(".results", box);
    if (!input || !results) return;

    let items = [];
    let cursor = -1;
    let timer;

    const close = () => {
      results.classList.remove("is-open");
      cursor = -1;
    };

    const highlight = () => {
      items.forEach((el, i) => el.classList.toggle("is-highlighted", i === cursor));
      if (items[cursor]) items[cursor].scrollIntoView({ block: "nearest" });
    };

    const render = ({ players, teams, leagues }) => {
      const total = players.length + teams.length + leagues.length;
      if (!total) {
        results.innerHTML = `<div class="results__empty">Sin resultados. Prueba con <b>Yamal</b>, <b>Real Madrid</b> o <b>Premier League</b>.</div>`;
        results.classList.add("is-open");
        items = [];
        return;
      }

      let html = "";

      if (players.length) {
        html += `<div class="results__group">Jugadores</div>`;
        html += players
          .map(
            (p) => `
          <a class="result" href="jugador.html?id=${p.id}">
            ${avatarHTML(p, "avatar--sm")}
            <div class="result__main">
              <div class="result__name">${p.flag} ${p.name}</div>
              <div class="result__meta">${p.pos} · ${clubOf(p).name} · ${p.age} años</div>
            </div>
            <span class="result__value">${formatValue(p.value)}</span>
          </a>`
          )
          .join("");
      }

      if (teams.length) {
        html += `<div class="results__group">Equipos</div>`;
        html += teams
          .map((t) => {
            const short = t.short || "FC";
            const logo = clubLogoURL(t) || clubLogoURL(t.name);
            const mark = logo
              ? `<div class="avatar avatar--sm avatar--photo" data-fallback="${short}"><img src="${logo}" alt="" loading="lazy" onerror="this.onerror=null;const p=this.parentElement;p.classList.remove('avatar--photo');p.textContent=p.dataset.fallback||'FC';"></div>`
              : `<div class="avatar avatar--sm" style="--c1:${t.c1 || "#233047"};--c2:${t.c2 || "#0e131d"}">${short}</div>`;
            return `
          <a class="result" href="club.html?id=${t.id}">
            ${mark}
            <div class="result__main">
              <div class="result__name">${t.name}</div>
              <div class="result__meta">${t.league || "—"} · ${t.country || "—"}${t.squadSize != null ? ` · ${t.squadSize} jugadores` : ""}</div>
            </div>
          </a>`;
          })
          .join("");
      }

      if (leagues.length) {
        html += `<div class="results__group">Ligas</div>`;
        html += leagues
          .map((l) => {
            const logo = afLeagueLogo(l.afId);
            const short = (l.name || "LG").slice(0, 2).toUpperCase();
            const mark = logo
              ? `<div class="avatar avatar--sm avatar--photo" data-fallback="${short}"><img src="${logo}" alt="" loading="lazy" onerror="this.onerror=null;const p=this.parentElement;p.classList.remove('avatar--photo');p.textContent=p.dataset.fallback||'LG';"></div>`
              : `<div class="avatar avatar--sm" style="--c1:#233047;--c2:#0e131d">${short}</div>`;
            return `
          <a class="result" href="competicion.html?id=${encodeURIComponent(l.id)}">
            ${mark}
            <div class="result__main">
              <div class="result__name">${l.name}</div>
              <div class="result__meta">${l.country} · ${l.teams} equipos · ${formatNumber(l.players)} jugadores</div>
            </div>
          </a>`;
          })
          .join("");
      }

      results.innerHTML = html;
      results.classList.add("is-open");
      items = $$(".result", results);
      cursor = -1;
    };

    const run = (value) => {
      clearTimeout(timer);
      if (!value.trim()) return close();
      timer = setTimeout(() => api.search(value).then(render), 130);
    };

    input.addEventListener("input", (e) => run(e.target.value));
    input.addEventListener("focus", () => {
      if (input.value.trim()) run(input.value);
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "Escape") return close();
      if (!items.length) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        cursor = (cursor + 1) % items.length;
        highlight();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        cursor = (cursor - 1 + items.length) % items.length;
        highlight();
      } else if (e.key === "Enter" && items[cursor]) {
        e.preventDefault();
        items[cursor].click();
      }
    });

    document.addEventListener("click", (e) => {
      if (!box.contains(e.target)) close();
    });

    if (isPrimary) {
      document.addEventListener("keydown", (e) => {
        if (e.key === "/" && document.activeElement !== input && !/input|textarea/i.test(document.activeElement?.tagName || "")) {
          e.preventDefault();
          input.focus();
        }
      });
    }
  };

  boxes.forEach((box, i) => bindBox(box, { isPrimary: i === 0 }));
}

/** Filas de tabla clicables. */
function initRowLinks(root = document) {
  $$("tr[data-href]", root).forEach((tr) =>
    tr.addEventListener("click", () => {
      window.location.href = tr.dataset.href;
    })
  );
}

/* ==========================================================================
   5. PAGES — controladores
   ========================================================================== */

function labClubCardHTML(club) {
  return `
    <a class="lab-club-card" href="club.html?id=${club.id}" style="--c1:${club.c1};--c2:${club.c2}">
      <div class="lab-club-card__badge">${club.short}</div>
      <div class="lab-club-card__body">
        <strong>${club.name}</strong>
        <span>${club.league || "—"} · ${club.country || "—"}</span>
        <em>${club.squadSize || 0} en plantilla · Abrir radiografía</em>
      </div>
      <span class="lab-club-card__arrow">→</span>
    </a>`;
}

const ARENA_PRESETS = [
  ["yamal", "estevao"],
  ["haaland", "mbappe"],
  ["bellingham", "pedri"],
  ["vinicius", "saka"],
  ["musiala", "wirtz"],
  ["cubarsi", "saliba"],
];

const FLASH_NEWS = [
  {
    tag: "Mercado",
    time: "12'",
    title: "Mbappé lidera las búsquedas IFLXI en las últimas 24 horas",
    excerpt: "El delantero del Real Madrid concentra el tráfico Lab y Arena por encima del resto de perfiles.",
    c: "#1d2b53",
  },
  {
    tag: "Lab",
    time: "28'",
    title: "Plantillas Big 5 sincronizadas: radiografías listas",
    excerpt: "LaLiga, Premier, Serie A, Bundesliga y Ligue 1 ya permiten once táctico y pirámide de edades.",
    c: "#147a4a",
  },
  {
    tag: "Arena",
    time: "41'",
    title: "Yamal vs Estêvão, el duelo más repetido del día",
    excerpt: "El choque Sub-21 encabeza las comparativas de perfil en la Arena IFLXI.",
    c: "#9b1b25",
  },
  {
    tag: "Scouting",
    time: "1h",
    title: "Cubarsí–Saliba: el eje defensivo más comparado",
    excerpt: "El Lab detecta afinidad de perfil alta entre ambos centrales en edad y proyección.",
    c: "#153a8a",
  },
  {
    tag: "Datos",
    time: "2h",
    title: "IFLXI supera el medio millón de perfiles indexados",
    excerpt: "El catálogo sigue creciendo con la ola de plantillas API-Football.",
    c: "#4a0f1c",
  },
  {
    tag: "Clubes",
    time: "3h",
    title: "Madrid y Barça, radiografías más abiertas hoy",
    excerpt: "Los usuarios priorizan plantillas con más vínculos abiertos en la base.",
    c: "#8d1237",
  },
];

function initNewsRail() {
  const grid = $("#news-grid");
  const ticker = $("#news-ticker-track");
  if (!grid) return;

  if (ticker) {
    const ticks = FLASH_NEWS.map(
      (n) => `<span class="tm-news__tick"><b>${n.tag}</b> ${n.title}</span>`
    ).join("");
    ticker.innerHTML = ticks + ticks;
  }

  grid.innerHTML = FLASH_NEWS.map(
    (n, i) => `
    <a class="tm-news__item${i === 0 ? " tm-news__item--lead" : ""}" href="#fichajes" style="--c:${n.c}">
      <div class="tm-news__thumb">${n.tag}</div>
      <div class="tm-news__body">
        <div class="tm-news__meta">
          <span class="tm-news__cat">${n.tag}</span>
          <span>${n.time}</span>
        </div>
        <h3 class="tm-news__title">${n.title}</h3>
        ${i === 0 ? `<p class="tm-news__excerpt">${n.excerpt}</p>` : ""}
      </div>
    </a>`
  ).join("");
}

function initArena() {
  const stage = $("#arena-stage");
  const presetsHost = $("#arena-presets");
  const inputA = $("#arena-q-a");
  const inputB = $("#arena-q-b");
  const resultsA = $("#arena-results-a");
  const resultsB = $("#arena-results-b");
  const pickedA = $("#arena-picked-a");
  const pickedB = $("#arena-picked-b");
  if (!stage || !inputA || !inputB) return;

  const byId = (id) => PLAYERS.find((p) => p.id === id);
  const pool = PLAYERS.filter((p) => p.attrs);
  const validPresets = ARENA_PRESETS.filter(([a, b]) => byId(a) && byId(b));
  let idA = validPresets[0]?.[0] || null;
  let idB = validPresets[0]?.[1] || null;

  const paintPicked = () => {
    const a = byId(idA);
    const b = byId(idB);
    if (pickedA) pickedA.textContent = a ? `Seleccionado: ${a.name}` : "";
    if (pickedB) pickedB.textContent = b ? `Seleccionado: ${b.name}` : "";
    if (a && inputA && document.activeElement !== inputA) inputA.value = a.name;
    if (b && inputB && document.activeElement !== inputB) inputB.value = b.name;
  };

  const renderDuel = () => {
    const a = byId(idA);
    const b = byId(idB);
    paintPicked();
    if (!a || !b) {
      stage.innerHTML = `<div class="arena__loading">Busca y elige dos jugadores para empezar el duelo</div>`;
      return;
    }
    if (a.id === b.id) {
      stage.innerHTML = `<div class="arena__loading">Elige dos jugadores distintos.</div>`;
      return;
    }

    const ra = aiRating(a);
    const rb = aiRating(b);
    const keys = Object.keys(ATTR_LABELS);
    const winner =
      ra == null || rb == null ? null : ra === rb ? "empate" : ra > rb ? a.name : b.name;

    stage.innerHTML = `
      <div class="arena__duel">
        <article class="arena__fighter arena__fighter--a">
          <div class="arena__fighter-top">
            ${avatarHTML(a, "avatar--xl")}
            <div>
              <p class="arena__fighter-name">${a.name}</p>
              <p class="arena__fighter-meta">${a.pos} · ${clubOf(a).name} · ${formatAge(a.age)}</p>
            </div>
          </div>
          <div class="arena__rating"><b>${ra != null ? nf1.format(ra) : "—"}</b><span>IFLXI</span></div>
          <div style="margin-top:14px"><a class="btn btn--sm arena__btn-light" href="jugador.html?id=${a.id}">Ver ficha</a></div>
        </article>
        <div class="arena__center">
          <div class="arena__vs">VS</div>
          <div class="arena__radar" id="arena-radar"></div>
        </div>
        <article class="arena__fighter arena__fighter--b">
          <div class="arena__fighter-top">
            ${avatarHTML(b, "avatar--xl")}
            <div>
              <p class="arena__fighter-name">${b.name}</p>
              <p class="arena__fighter-meta">${b.pos} · ${clubOf(b).name} · ${formatAge(b.age)}</p>
            </div>
          </div>
          <div class="arena__rating"><b>${rb != null ? nf1.format(rb) : "—"}</b><span>IFLXI</span></div>
          <div style="margin-top:14px"><a class="btn btn--sm arena__btn-light" href="jugador.html?id=${b.id}">Ver ficha</a></div>
        </article>
      </div>
      <div class="arena__meters">
        ${keys.map((k) => {
          const va = a.attrs?.[k] || 0;
          const vb = b.attrs?.[k] || 0;
          const sum = va + vb || 1;
          return `
            <div class="arena__meter">
              <span class="arena__meter-label">${ATTR_LABELS[k]}</span>
              <span class="arena__meter-val arena__meter-val--a">${va}</span>
              <div class="arena__meter-track">
                <div class="arena__meter-fill arena__meter-fill--a" data-w="${(va / sum) * 100}"></div>
                <div class="arena__meter-fill arena__meter-fill--b" data-w="${(vb / sum) * 100}"></div>
              </div>
              <span class="arena__meter-val arena__meter-val--b">${vb}</span>
            </div>`;
        }).join("")}
      </div>
      <p class="arena__verdict">${
        winner === "empate"
          ? "Empate técnico en el índice IFLXI"
          : winner
            ? `Ventaja de perfil: <strong>${winner}</strong>`
            : "Duelo listo"
      } · afinidad <em>${affinity(a, b)}%</em></p>`;

    const radar = $("#arena-radar", stage);
    if (radar && a.attrs && b.attrs) renderRadarChart(radar, a, b);
    requestAnimationFrame(() => {
      $$(".arena__meter-fill", stage).forEach((el) => {
        el.style.width = `${el.dataset.w || 0}%`;
      });
    });
    $$(".arena__preset", presetsHost).forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.a === idA && btn.dataset.b === idB);
    });
  };

  const bindSearch = (input, resultsEl, side) => {
    const close = () => {
      resultsEl.hidden = true;
      resultsEl.innerHTML = "";
    };
    const open = (q) => {
      const query = normalize(q);
      if (query.length < 1) {
        close();
        return;
      }
      const hits = pool
        .filter(
          (p) =>
            normalize(p.name).includes(query) ||
            normalize(clubOf(p).name).includes(query) ||
            normalize(p.pos).includes(query)
        )
        .slice(0, 8);
      if (!hits.length) {
        resultsEl.hidden = false;
        resultsEl.innerHTML = `<div class="arena-search__option"><span>Sin resultados</span></div>`;
        return;
      }
      resultsEl.hidden = false;
      resultsEl.innerHTML = hits
        .map(
          (p) => `
          <button type="button" class="arena-search__option" data-id="${p.id}">
            ${avatarHTML(p)}
            <div><b>${p.name}</b><span>${p.pos} · ${clubOf(p).name}</span></div>
          </button>`
        )
        .join("");
    };

    input.addEventListener("input", () => open(input.value));
    input.addEventListener("focus", () => {
      if (input.value.trim()) open(input.value);
    });
    resultsEl.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-id]");
      if (!btn) return;
      if (side === "a") idA = btn.dataset.id;
      else idB = btn.dataset.id;
      close();
      renderDuel();
    });
    document.addEventListener("click", (e) => {
      if (!e.target.closest(side === "a" ? '.arena-search[data-side="a"]' : '.arena-search[data-side="b"]')) {
        close();
      }
    });
  };

  bindSearch(inputA, resultsA, "a");
  bindSearch(inputB, resultsB, "b");

  if (presetsHost) {
    presetsHost.innerHTML = validPresets
      .map(
        ([a, b]) =>
          `<button type="button" class="arena__preset" data-a="${a}" data-b="${b}">${byId(a).name.split(" ").slice(-1)[0]} vs ${byId(b).name.split(" ").slice(-1)[0]}</button>`
      )
      .join("");
    presetsHost.addEventListener("click", (e) => {
      const btn = e.target.closest(".arena__preset");
      if (!btn) return;
      idA = btn.dataset.a;
      idB = btn.dataset.b;
      renderDuel();
    });
  }

  $("#arena-random")?.addEventListener("click", () => {
    const a = pool[Math.floor(Math.random() * pool.length)];
    let b = pool[Math.floor(Math.random() * pool.length)];
    while (b.id === a.id) b = pool[Math.floor(Math.random() * pool.length)];
    idA = a.id;
    idB = b.id;
    renderDuel();
  });

  renderDuel();
}

function initAuth() {
  const form = $("#register-form");
  if (!form) return;
  const feedback = $("#cuenta-feedback");
  const sessionEl = $("#cuenta-session");
  const toggle = $("#login-toggle");
  let mode = "register";

  const readSession = () => {
    try {
      return JSON.parse(localStorage.getItem("iflxi-user") || "null");
    } catch (_) {
      return null;
    }
  };

  const paintSession = () => {
    const user = readSession();
    if (!sessionEl) return;
    sessionEl.textContent = user
      ? `Sesión activa: ${user.name} (${user.email})`
      : "";
  };

  const setFeedback = (msg, isError = false) => {
    if (!feedback) return;
    feedback.textContent = msg;
    feedback.classList.toggle("is-error", isError);
  };

  toggle?.addEventListener("click", () => {
    mode = mode === "register" ? "login" : "register";
    const title = form.querySelector("h3");
    const submit = form.querySelector('button[type="submit"]');
    const nameLabel = form.querySelector('input[name="name"]')?.closest("label");
    const terms = form.querySelector('input[name="terms"]')?.closest("label");
    if (title) title.textContent = mode === "register" ? "Registro" : "Entrar";
    if (submit) submit.textContent = mode === "register" ? "Crear cuenta" : "Entrar";
    if (nameLabel) nameLabel.hidden = mode === "login";
    if (terms) terms.hidden = mode === "login";
    if (toggle) toggle.textContent = mode === "register" ? "Entrar" : "Crear cuenta";
    form.querySelector(".cuenta__switch").childNodes[0].textContent =
      mode === "register" ? "¿Ya tienes cuenta? " : "¿No tienes cuenta? ";
    setFeedback("");
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const data = new FormData(form);
    const name = String(data.get("name") || "").trim();
    const email = String(data.get("email") || "").trim().toLowerCase();
    const password = String(data.get("password") || "");
    const terms = data.get("terms");

    if (!email || !password || password.length < 6) {
      setFeedback("Email y contraseña (mín. 6) son obligatorios.", true);
      return;
    }

    const users = (() => {
      try {
        return JSON.parse(localStorage.getItem("iflxi-users") || "[]");
      } catch (_) {
        return [];
      }
    })();

    if (mode === "register") {
      if (!name) {
        setFeedback("Pon tu nombre.", true);
        return;
      }
      if (!terms) {
        setFeedback("Debes aceptar las condiciones.", true);
        return;
      }
      if (users.some((u) => u.email === email)) {
        setFeedback("Ese email ya está registrado. Prueba a entrar.", true);
        return;
      }
      users.push({ name, email, password });
      localStorage.setItem("iflxi-users", JSON.stringify(users));
      localStorage.setItem("iflxi-user", JSON.stringify({ name, email }));
      setFeedback("Cuenta creada. ¡Bienvenido a IFLXI!");
      paintSession();
      form.reset();
      return;
    }

    const found = users.find((u) => u.email === email && u.password === password);
    if (!found) {
      setFeedback("Email o contraseña incorrectos.", true);
      return;
    }
    localStorage.setItem("iflxi-user", JSON.stringify({ name: found.name, email: found.email }));
    setFeedback(`Hola, ${found.name}. Sesión iniciada.`);
    paintSession();
  });

  paintSession();
}

async function initHome() {
  const [topLive, transfers, rumors, liveMatches] = await Promise.all([
    api.getPlayers({ sort: "value", limit: 10 }).catch(() => []),
    api.getTransfers(8).catch(() => TRANSFERS.slice(0, 8)),
    api.getRumors(6).catch(() => RUMORS.slice(0, 6)),
    api.getMatches({ status: "live", limit: 6 }).catch(() => MATCHES.filter((m) => m.status === "live")),
  ]);

  const top10 = (topLive?.length ? topLive : PLAYERS.slice())
    .slice()
    .sort((a, b) => (b.value || 0) - (a.value || 0))
    .slice(0, 10);

  // Panel home: fichajes reales de la API (con reserva a demo si la API
  // aún no responde, gestionada dentro de api.getTransfers).
  const usingRealTransfers = Array.isArray(transfers) && transfers.length && transfers[0]?.player;
  const transfersBody = $("#transfers-body");
  if (transfersBody) {
    const rows = usingRealTransfers
      ? transfers.slice(0, 5).map(realTransferRowHTML).filter(Boolean).join("")
      : TRANSFERS.slice(0, 5).map(transferRowHTML).filter(Boolean).join("");
    transfersBody.innerHTML = rows || `<tr><td colspan="3">Sin fichajes para mostrar.</td></tr>`;
  }

  // Rumores: sin tabla real en el modelo de datos todavía → placeholder
  // "próximamente" en vez de datos inventados.
  const rumorsBody = $("#rumors-body");
  if (rumorsBody) {
    rumorsBody.innerHTML = `<tr><td colspan="3" class="empty-note">Próximamente: rumores de fichajes basados en datos reales.</td></tr>`;
  }

  const liveHost = $("#live-matches");
  if (liveHost) {
    const list = liveMatches?.length ? liveMatches : MATCHES.filter((m) => m.status === "live");
    if (!list.length) {
      liveHost.innerHTML = `<p class="empty-note">No hay partidos en directo ahora. <a href="partidos.html">Ver todos los del día</a>.</p>`;
    } else {
      const byLeague = new Map();
      for (const m of list) {
        const key = m.league || "Otros";
        if (!byLeague.has(key)) byLeague.set(key, []);
        byLeague.get(key).push(m);
      }
      liveHost.innerHTML = [...byLeague.entries()]
        .map(([league, matches]) => matchLeagueBlockHTML(league, matches))
        .join("");
    }
  }

  const topValueBody = $("#top-value-body");
  if (topValueBody) topValueBody.innerHTML = top10.slice(0, 5).map(topValuedRowHTML).join("");

  const topTransfersBody = $("#top-transfers-body");
  if (topTransfersBody) {
    const topSummer = TRANSFERS.slice()
      .sort((a, b) => (b.fee || 0) - (a.fee || 0))
      .slice(0, 5);
    topTransfersBody.innerHTML = topSummer.map(topTransferRowHTML).filter(Boolean).join("");
  }

  initNewsRail();

  observeReveals();
  animateBars();
  animateCounters();
  initRowLinks();
}

async function initMatchesPage() {
  const host = $("#day-matches");
  const dateEl = $("#matches-date");
  if (dateEl) {
    dateEl.textContent = new Intl.DateTimeFormat("es-ES", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(new Date());
  }

  const matches = await api.getMatches().catch(() => MATCHES);
  const order = { live: 0, scheduled: 1, finished: 2 };
  const sorted = (matches?.length ? matches : MATCHES)
    .slice()
    .sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9));

  if (host) {
    const byLeague = new Map();
    for (const m of sorted) {
      const key = m.league || "Otros";
      if (!byLeague.has(key)) byLeague.set(key, []);
      byLeague.get(key).push(m);
    }
    host.classList.add("match-day");
    host.classList.remove("live-grid", "live-grid--day");
    host.innerHTML = [...byLeague.entries()]
      .map(([league, list]) => matchLeagueBlockHTML(league, list))
      .join("");
  }

  const liveCount = $("#live-count");
  if (liveCount) {
    liveCount.textContent = String(sorted.filter((m) => m.status === "live").length);
  }

  observeReveals();
}

async function initMatchDetailPage() {
  const root = $("#match-root");
  if (!root) return;
  const id = new URLSearchParams(location.search).get("id");
  if (!id) {
    root.innerHTML = `<p class="empty-note">Falta <code>?id=</code> del partido. <a href="partidos.html">Ver partidos</a></p>`;
    return;
  }
  const match = await api.getMatch(id);
  if (!match) {
    root.innerHTML = `<p class="empty-note">Partido no encontrado. <a href="partidos.html">Volver</a></p>`;
    return;
  }
  document.title = `${match.home} – ${match.away} | IFLXI`;
  root.innerHTML = matchDetailHTML(match);
  observeReveals();
}

function competitionFeaturedHTML(c) {
  const season = c.season || (c.yearStart ? `${c.yearStart}/${String(c.yearEnd || "").slice(-2)}` : "");
  const href = `competicion.html?id=${encodeURIComponent(c.id)}`;
  return `
    <a class="comp-featured" href="${href}">
      <div class="comp-featured__logo">${leagueBadgeHTML(c, "lg")}</div>
      <div class="comp-featured__body">
        <b>${c.name}</b>
        <span>${c.country || "—"}${season ? ` · ${season}` : ""}</span>
        <span class="comp-featured__teams">${c.teams != null ? `${nf0.format(c.teams)} equipos` : ""}</span>
      </div>
    </a>`;
}

function competitionRowHTML(c) {
  const typeLabel = c.type === "cup" ? "Copa" : c.type === "league" ? "Liga" : c.type || "—";
  const season = c.season || (c.yearStart ? `${c.yearStart}/${String(c.yearEnd || "").slice(-2)}` : "—");
  const teams = c.teams != null ? nf0.format(c.teams) : "—";
  const href = `competicion.html?id=${encodeURIComponent(c.id)}`;
  return `
    <tr class="comp-row" data-href="${href}">
      <td>
        <a class="comp-cell" href="${href}">
          ${leagueBadgeHTML(c, "md")}
          <div class="comp-name">
            <b>${c.name}</b>
            <small>${c.country || "—"}</small>
          </div>
        </a>
      </td>
      <td><span class="comp-type comp-type--${c.type || "other"}">${typeLabel}</span></td>
      <td class="comp-season">${season}</td>
      <td class="td-num">${teams}</td>
    </tr>`;
}

function competitionClubRowHTML(club) {
  const href = `club.html?id=${encodeURIComponent(club.id)}`;
  const squad = club.squadSize != null ? nf0.format(club.squadSize) : "—";
  return `
    <a class="comp-club" href="${href}">
      ${clubBadgeHTML(club.name)}
      <div class="comp-club__meta">
        <b>${club.name}</b>
        <span>${club.country || "—"}</span>
      </div>
      <span class="comp-club__squad">${squad} <small>jug.</small></span>
    </a>`;
}

function competitionDetailHTML(comp) {
  const typeLabel = comp.type === "cup" ? "Copa" : comp.type === "league" ? "Liga" : comp.type || "—";
  const season = comp.season || (comp.yearStart ? `${comp.yearStart}/${String(comp.yearEnd || "").slice(-2)}` : "—");
  const clubs = Array.isArray(comp.clubList) ? comp.clubList : [];
  const list = clubs.length
    ? `<div class="comp-club-grid">${clubs.map(competitionClubRowHTML).join("")}</div>`
    : `<p class="empty-note">Aún no hay equipos inscritos en esta temporada (el fill puede estar en curso).</p>`;

  return `
    <section class="comp-detail reveal">
      <header class="comp-detail__hero">
        ${leagueBadgeHTML(comp, "lg")}
        <div class="comp-detail__titles">
          <span class="comp-type comp-type--${comp.type || "other"}">${typeLabel}</span>
          <h1>${comp.name}</h1>
          <p>${comp.country || "—"} · Temporada ${season}</p>
        </div>
        <div class="comp-detail__stats">
          <div><b>${nf0.format(comp.teams ?? clubs.length)}</b><span>Equipos</span></div>
          <div><b>${season}</b><span>Temporada</span></div>
        </div>
      </header>
      <div class="comp-detail__section">
        <h2>Equipos</h2>
        ${list}
      </div>
    </section>`;
}

async function initCompetitionsPage() {
  const root = $("#competitions-root");
  const meta = $("#competitions-meta");
  const form = $("#comp-filters");
  const pager = $("#comp-pager");
  if (!root) return;

  const state = { q: "", type: "", country: "", offset: 0, limit: 60, total: 0 };

  const render = async () => {
    root.innerHTML = `<div class="skeleton" style="min-height:200px"></div>`;
    const data = await api.getCompetitions({
      q: state.q,
      type: state.type,
      country: state.country,
      limit: state.limit,
      offset: state.offset,
    });
    const items = data?.items || [];
    state.total = data?.total ?? items.length;
    if (meta) {
      meta.textContent = `${nf0.format(state.total)} competiciones` + (state.q || state.type || state.country ? " (filtro activo)" : "");
    }
    if (!items.length) {
      root.innerHTML = `<p class="empty-note">No hay competiciones con esos filtros.</p>`;
    } else {
      const featured = items.filter((c) => c.tier === 1 || resolveLeagueAfId(c)).slice(0, 6);
      const featuredBlock =
        state.offset === 0 && !state.q && !state.type && !state.country && featured.length
          ? `<div class="comp-featured-grid">${featured.map(competitionFeaturedHTML).join("")}</div>`
          : "";
      root.innerHTML = `
        ${featuredBlock}
        <div class="table-wrap comp-table-wrap">
          <table class="comp-table">
            <thead>
              <tr>
                <th>Competición</th>
                <th>Tipo</th>
                <th>Temporada</th>
                <th>Equipos</th>
              </tr>
            </thead>
            <tbody>
              ${items.map(competitionRowHTML).join("")}
            </tbody>
          </table>
        </div>`;
    }
    if (pager) {
      const show = state.total > state.limit;
      pager.hidden = !show;
      const page = Math.floor(state.offset / state.limit) + 1;
      const pages = Math.max(1, Math.ceil(state.total / state.limit));
      const label = $("#comp-page-label");
      if (label) label.textContent = `Página ${page} / ${pages}`;
      const prev = $("#comp-prev");
      const next = $("#comp-next");
      if (prev) prev.disabled = state.offset <= 0;
      if (next) next.disabled = state.offset + state.limit >= state.total;
    }
    observeReveals();
  };

  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    state.q = ($("#comp-q")?.value || "").trim();
    state.type = $("#comp-type")?.value || "";
    state.country = ($("#comp-country")?.value || "").trim();
    state.offset = 0;
    render();
  });
  $("#comp-prev")?.addEventListener("click", () => {
    state.offset = Math.max(0, state.offset - state.limit);
    render();
  });
  $("#comp-next")?.addEventListener("click", () => {
    state.offset += state.limit;
    render();
  });

  await render();
}

async function initCompetitionDetailPage() {
  const root = $("#competition-root");
  if (!root) return;
  const id = new URLSearchParams(location.search).get("id");
  if (!id) {
    root.innerHTML = `<p class="empty-note">Falta <code>?id=</code>. <a href="competiciones.html">Ver catálogo</a></p>`;
    return;
  }
  const comp = await api.getCompetition(id);
  if (!comp) {
    root.innerHTML = `<p class="empty-note">Competición no encontrada. <a href="competiciones.html">Volver</a></p>`;
    return;
  }
  document.title = `${comp.name} | IFLXI`;
  root.innerHTML = competitionDetailHTML(comp);
  observeReveals();
}

function posToLine(pos) {
  const p = String(pos || "").toUpperCase();
  if (["PT", "POR", "GK"].includes(p)) return "PT";
  // Delanteros antes que el comodín D* (DC = delantero centro, no defensa)
  if (["DL", "DC", "ST", "ED", "EI", "SD", "EXT"].includes(p)) return "DL";
  if (["DF", "DFC", "CB", "LD", "LI", "CAR", "LT"].includes(p)) return "DF";
  if (["MC", "MCO", "MCD", "CM", "MI", "MD"].includes(p) || p.startsWith("M")) return "MC";
  if (p.startsWith("A") || p.includes("ATAC") || p.includes("FORWARD")) return "DL";
  if (p.startsWith("D") || p.includes("DEF")) return "DF";
  return "MC";
}

function buildLabFromSquad(squad) {
  const n = squad.length;
  const ages = squad.map((p) => p.age).filter((a) => typeof a === "number");
  const lines = { PT: 0, DF: 0, MC: 0, DL: 0 };
  const pitch = { PT: [], DF: [], MC: [], DL: [] };
  const nations = {};
  for (const p of squad) {
    const line = posToLine(p.pos);
    lines[line] = (lines[line] || 0) + 1;
    pitch[line].push({ id: p.id, name: p.name, age: p.age, pos: p.pos || line });
    const nat = p.nationality || "—";
    if (nat !== "—") nations[nat] = (nations[nat] || 0) + 1;
  }
  const buckets = [
    { key: "U21", label: "Sub-21", count: ages.filter((a) => a <= 20).length },
    { key: "21-24", label: "21–24", count: ages.filter((a) => a >= 21 && a <= 24).length },
    { key: "25-28", label: "25–28", count: ages.filter((a) => a >= 25 && a <= 28).length },
    { key: "29-32", label: "29–32", count: ages.filter((a) => a >= 29 && a <= 32).length },
    { key: "33+", label: "33+", count: ages.filter((a) => a >= 33).length },
  ];
  const young = ages.filter((a) => a <= 23).length;
  const veterans = ages.filter((a) => a >= 30).length;
  const avgAge = ages.length ? Math.round((ages.reduce((s, a) => s + a, 0) / ages.length) * 10) / 10 : null;
  const score = Math.min(
    100,
    Math.round(
      Math.min(1, n / 25) * 30 +
        (ages.length ? (young / ages.length) * 28 : 12) +
        (n ? 22 : 0) +
        (Object.keys(nations).length ? 15 : 5)
    )
  );
  const nationList = Object.entries(nations)
    .map(([name, count]) => ({ name, count, pct: n ? Math.round((100 * count) / n) : 0 }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 12);
  return {
    score,
    squadSize: n,
    avgAge,
    agesKnown: ages.length,
    youngCount: young,
    veteranCount: veterans,
    ageBuckets: buckets,
    lines,
    nations: nationList,
    insights: [
      `${n} jugadores en plantilla Lab.`,
      avgAge != null ? `Edad media ${avgAge} años.` : "Edades pendientes.",
      `${young} perfiles ≤23 en proyección.`,
      nationList[0] ? `Nación dominante: ${nationList[0].name}.` : "Sin mapa de naciones.",
      "Demo local — en vivo usa PostgreSQL + API-Football.",
    ],
    pitch,
    honesty: { marketValues: true, note: "Modo demo con datos de ejemplo." },
  };
}

function labScoreRing(score) {
  const s = Math.max(0, Math.min(100, Number(score) || 0));
  const r = 54;
  const c = 2 * Math.PI * r;
  const offset = c - (s / 100) * c;
  return `
    <div class="lab-score" style="--score:${s}">
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <circle class="lab-score__track" cx="60" cy="60" r="${r}"/>
        <circle class="lab-score__value" cx="60" cy="60" r="${r}"
          stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${offset.toFixed(1)}"/>
      </svg>
      <div class="lab-score__num"><b data-count="${s}">0</b><span>Lab</span></div>
    </div>`;
}

function labPitchHTML(pitch, c1, c2) {
  const line = (key, label) => {
    const list = pitch?.[key] || [];
    return `
      <div class="lab-pitch__line" data-line="${key}">
        <span class="lab-pitch__line-label">${label}</span>
        <div class="lab-pitch__chips">
          ${list.length
            ? list.map((p) => `
                <a class="lab-chip" href="jugador.html?id=${p.id}" title="${p.name}">
                  <span class="lab-chip__pos">${p.pos || key}</span>
                  <span class="lab-chip__name">${(p.name || "").split(" ").slice(-1)[0]}</span>
                  <span class="lab-chip__age">${p.age ?? "—"}</span>
                </a>`).join("")
            : `<span class="lab-pitch__empty">Sin datos</span>`}
        </div>
      </div>`;
  };
  return `
    <div class="lab-pitch" style="--c1:${c1};--c2:${c2}">
      <div class="lab-pitch__field">
        <div class="lab-pitch__mark lab-pitch__mark--mid"></div>
        <div class="lab-pitch__mark lab-pitch__mark--box"></div>
        ${line("DL", "Ataque")}
        ${line("MC", "Medio")}
        ${line("DF", "Defensa")}
        ${line("PT", "Portería")}
      </div>
    </div>`;
}

function labAgeBarsHTML(buckets, maxHint) {
  const max = Math.max(1, maxHint || 0, ...(buckets || []).map((b) => b.count));
  return `
    <div class="lab-bars">
      ${(buckets || []).map((b, i) => `
        <div class="lab-bars__row" style="--i:${i}">
          <span class="lab-bars__label">${b.label}</span>
          <div class="lab-bars__track">
            <div class="lab-bars__fill" data-bar style="--w:${(b.count / max) * 100}%"></div>
          </div>
          <span class="lab-bars__n">${b.count}</span>
        </div>`).join("")}
    </div>`;
}

function labNationsHTML(nations) {
  if (!nations?.length) {
    return `<p class="lab-empty">Nacionalidades aún no enriquecidas en esta ola. Las posiciones y el once Lab ya están vivos.</p>`;
  }
  const max = Math.max(1, ...nations.map((n) => n.count));
  return `
    <div class="lab-nations">
      ${nations.slice(0, 8).map((n, i) => `
        <div class="lab-nations__row" style="--i:${i}">
          <span class="lab-nations__name">${n.name}</span>
          <div class="lab-nations__track">
            <div class="lab-nations__fill" data-bar style="--w:${(n.count / max) * 100}%"></div>
          </div>
          <span class="lab-nations__n">${n.count}</span>
        </div>`).join("")}
    </div>`;
}

async function initClubPage() {
  const id = new URLSearchParams(location.search).get("id");
  const host = $("#club-root");
  if (!host) return;
  if (!id) {
    host.innerHTML = `<div class="empty-state"><h2>Elige un club</h2><p>Busca un equipo en el inicio (ej. Real Madrid) y abre su <b>Radiografía Lab</b>.</p><a class="btn btn--primary" href="index.html#lab">Ir al Lab</a></div>`;
    return;
  }
  const club = await api.getClub(id);
  if (!club) {
    host.innerHTML = `<div class="empty-state"><h2>Club no encontrado</h2><a class="btn btn--primary" href="index.html">Volver</a></div>`;
    return;
  }
  document.title = `${club.name} · Radiografía Lab | IFLXI`;
  const squad = club.squad || [];
  const lab = club.lab || buildLabFromSquad(squad);
  const ageMax = Math.max(0, ...(lab.ageBuckets || []).map((b) => b.count));

  host.innerHTML = `
    <section class="lab-hero" style="--c1:${club.c1};--c2:${club.c2}">
      <div class="lab-hero__glow"></div>
      <nav class="breadcrumb lab-hero__crumb">
        <a href="index.html">Inicio</a> <span>›</span>
        <a href="index.html#lab">Lab</a> <span>›</span>
        <span>${club.name}</span>
      </nav>
      <div class="lab-hero__grid">
        <div class="lab-hero__id">
          <div class="avatar avatar--xl lab-hero__badge" style="--c1:${club.c1};--c2:${club.c2}">${club.short}</div>
          <div>
            <span class="eyebrow">Radiografía Lab · IFLXI</span>
            <h1 class="lab-hero__name">${club.name}</h1>
            <p class="lab-hero__meta">${club.country} · ${club.league}${club.founded ? ` · Fundado ${club.founded}` : ""}</p>
            <div class="lab-hero__tags">
              <span class="tag">${lab.squadSize || squad.length} jugadores</span>
              <span class="tag">${lab.avgAge != null ? `Edad media ${lab.avgAge}` : "Edad en sync"}</span>
              <span class="tag tag--accent">${lab.youngCount || 0} ≤23</span>
              <span class="ai-score">${ICON_AI} Sin valor inventado</span>
            </div>
          </div>
        </div>
        <div class="lab-hero__score">
          ${labScoreRing(lab.score)}
          <p class="lab-hero__score-note">Índice de composición de plantilla<br><small>${lab.honesty?.note || ""}</small></p>
        </div>
      </div>
      <div class="lab-kpis">
        <div class="lab-kpi"><b>${lab.lines?.PT ?? 0}</b><span>Porteros</span></div>
        <div class="lab-kpi"><b>${lab.lines?.DF ?? 0}</b><span>Defensas</span></div>
        <div class="lab-kpi"><b>${lab.lines?.MC ?? 0}</b><span>Medios</span></div>
        <div class="lab-kpi"><b>${lab.lines?.DL ?? 0}</b><span>Delanteros</span></div>
        <div class="lab-kpi"><b>${lab.veteranCount ?? 0}</b><span>Veteranos ≥30</span></div>
        <div class="lab-kpi"><b>${lab.agesKnown ?? 0}/${lab.squadSize || squad.length}</b><span>Edades conocidas</span></div>
      </div>
    </section>

    <section class="lab-grid">
      <div class="lab-panel lab-panel--pitch" data-reveal>
        <div class="lab-panel__head">
          <h3>Once Lab</h3>
          <span class="tag">Por línea · datos reales</span>
        </div>
        ${labPitchHTML(lab.pitch, club.c1, club.c2)}
      </div>

      <div class="lab-panel" data-reveal>
        <div class="lab-panel__head">
          <h3>Pirámide de edades</h3>
          <span class="tag">${lab.agesKnown || 0} muestras</span>
        </div>
        ${ageMax ? labAgeBarsHTML(lab.ageBuckets, ageMax) : `<p class="lab-empty">Aún no hay edades en BD para este club. En la próxima sync de squads se estiman desde la API.</p>`}
      </div>

      <div class="lab-panel" data-reveal>
        <div class="lab-panel__head">
          <h3>Mapa de nacionalidades</h3>
          <span class="tag">${(lab.nations || []).length || 0}</span>
        </div>
        ${labNationsHTML(lab.nations)}
      </div>

      <div class="lab-panel lab-panel--insights" data-reveal>
        <div class="lab-panel__head">
          <h3>Señales Lab</h3>
          <span class="tag">Honestidad de datos</span>
        </div>
        <ul class="lab-insights">
          ${(lab.insights || []).map((t) => `<li>${t}</li>`).join("")}
        </ul>
      </div>
    </section>

    <section class="section section--tight">
      <div class="panel" data-reveal>
        <div class="panel__head"><h3>Plantilla completa</h3><span class="tag">${squad.length}</span></div>
        <div class="panel__body" style="overflow:auto">
          <table class="table">
            <thead><tr><th>Jugador</th><th>Pos</th><th>Edad</th><th>Nacionalidad</th><th>Valor</th><th></th></tr></thead>
            <tbody>
              ${squad.map((p) => `
                <tr data-href="jugador.html?id=${p.id}">
                  <td><div class="cell-player">${avatarHTML(p, "avatar--sm")}<div><b>${p.name}</b></div></div></td>
                  <td><span class="tag">${p.pos}</span></td>
                  <td>${p.age ?? "—"}</td>
                  <td>${p.nationality && p.nationality !== "—" ? p.nationality : "—"}</td>
                  <td><span class="tag">${p.value != null ? `${p.value} M€` : "Sin valor"}</span></td>
                  <td><a class="btn btn--sm" href="jugador.html?id=${p.id}">Ficha</a></td>
                </tr>`).join("") || `<tr><td colspan="6" style="padding:20px;color:var(--muted)">Sin plantilla cargada aún para este club.</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>
    </section>`;

  observeReveals();
  animateCounters();
  // animar barras
  requestAnimationFrame(() => {
    $$("[data-bar]", host).forEach((el) => {
      el.style.width = "0";
      requestAnimationFrame(() => {
        el.style.width = getComputedStyle(el).getPropertyValue("--w") || "0%";
      });
    });
  });
  initRowLinks(host);
}

async function initPlayerPage() {
  const params = new URLSearchParams(location.search);
  let id = params.get("id");
  const live = await detectLive();
  if (!id) {
    if (live) {
      const list = await api.getPlayers({ sort: "featured", limit: 1 });
      id = list[0]?.id;
    } else {
      id = "yamal";
    }
  }
  const player = id ? await api.getPlayer(id) : null;
  const host = $("#player-root");
  if (!host) return;

  if (!player) {
    host.innerHTML = `<div class="empty-state">
        <h2>Jugador no encontrado</h2>
        <p style="margin:10px 0 20px">No tenemos ficha para «${id || "—"}». Busca un nombre en el inicio.</p>
        <a class="btn btn--primary" href="index.html">Volver al inicio</a>
      </div>`;
    return;
  }

  document.title = `${player.name} — Ficha | IFLXI`;

  const club = clubOf(player);
  const rating = aiRating(player);
  const potential = aiPotential(player);
  const trend = valueTrend(player);
  const similar = similarPlayers(player, 4);
  const p90 = productivity(player);

  host.innerHTML = `
    <nav class="breadcrumb">
      <a href="index.html">Inicio</a> <span>›</span>
      <a href="index.html#destacados">${club.league}</a> <span>›</span>
      <a href="club.html?id=${club.id}">${club.name}</a> <span>›</span>
      <span style="color:var(--muted)">${player.name}</span>
    </nav>

    <header class="profile" data-reveal>
      <div class="profile__top">
        ${avatarHTML(player, "avatar--xl")}
        <div class="profile__id">
          <span class="eyebrow">${player.flag ? player.flag + " " : ""}${player.nationality} · ${player.live ? "Datos en vivo" : "Demo"}</span>
          <h1 class="profile__name">${player.name}</h1>
          <div class="profile__tags">
            <span class="tag">${player.position}</span>
            <span class="tag">${clubBadgeHTML(club.name)} ${club.name}</span>
            <span class="tag">${club.league}</span>
            ${rating != null ? `<span class="ai-score">${ICON_AI} Rating IA ${nf1.format(rating)}</span>` : `<span class="tag">Sin rating IA aún</span>`}
          </div>
        </div>
        <div class="profile__aside">
          <div class="profile__value-label">Valor de mercado</div>
          <div class="profile__value">${formatValue(player.value)}</div>
          <span class="delta ${player.value == null ? "" : `delta--${trend.diff >= 0 ? "up" : "down"}`}">
            ${
              player.value == null
                ? "Aún no hay valores en BD (API no trae Transfermarkt)"
                : trend.diff === 0
                  ? "— Sin serie histórica"
                  : `${trend.diff > 0 ? "▲ +" : "▼ "}${nf1.format(trend.diff)} M € (${trend.pct}%)`
            }
          </span>
          <div style="margin-top:16px;display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap">
            <a class="btn btn--primary btn--sm" href="comparador.html?a=${player.id}">Comparar jugador</a>
          </div>
        </div>
      </div>

      <dl class="datagrid">
        <div><dt>Edad</dt><dd>${formatAge(player.age)}</dd></div>
        <div><dt>Nacimiento</dt><dd>${player.birth || "—"}</dd></div>
        <div><dt>Nacionalidad</dt><dd>${player.nationality || "—"}</dd></div>
        <div><dt>Posición</dt><dd>${player.pos}</dd></div>
        <div><dt>Altura</dt><dd>${player.height && player.height !== "—" ? `${player.height} cm` : "—"}</dd></div>
        <div><dt>Pie dominante</dt><dd>${player.foot || "—"}</dd></div>
        <div><dt>Club actual</dt><dd>${clubBadgeHTML(club.name)} ${club.short}</dd></div>
        <div><dt>Contrato hasta</dt><dd>${player.contract || "—"}</dd></div>
      </dl>
    </header>

    <section class="section section--tight">
      <div class="layout-2">
        <div style="display:grid;gap:20px">
          <div class="panel" data-reveal>
            <div class="panel__head">
              <h3>Estadísticas de la temporada 2025/26</h3>
              <span class="tag">${club.league}</span>
            </div>
            <div class="panel__body">
              <div class="stat-blocks">
                <div class="stat-block"><b>${player.stats.matches}</b><span>Partidos</span></div>
                <div class="stat-block"><b>${player.stats.goals}</b><span>Goles</span></div>
                <div class="stat-block"><b>${player.stats.assists}</b><span>Asistencias</span></div>
                <div class="stat-block"><b>${formatNumber(player.stats.minutes)}</b><span>Minutos</span></div>
                <div class="stat-block"><b>${nf1.format(p90)}</b><span>G+A / 90'</span></div>
              </div>
            </div>
          </div>

          <div class="panel" data-reveal>
            <div class="panel__head">
              <h3>Evolución del valor de mercado</h3>
              <div class="chart-legend"><span><i></i>Valor estimado (M €)</span></div>
            </div>
            <div class="panel__body">
              <div id="value-chart"></div>
            </div>
          </div>

          <div class="panel" data-reveal>
            <div class="panel__head"><h3>Historial de clubes</h3></div>
            <div class="panel__body">
              <ul class="timeline">
                ${player.career
                  .map(
                    (c) => `
                  <li class="${c.to ? "is-past" : ""}">
                    <div class="tl-head">
                      <span class="tl-club">${clubBadgeHTML(c.club)} ${c.club}</span>
                      <span class="tl-dates">${c.from} — ${c.to || "Actualidad"}</span>
                    </div>
                    <div class="tl-meta">${c.apps} partidos · ${c.goals} goles</div>
                  </li>`
                  )
                  .join("")}
              </ul>
            </div>
          </div>
        </div>

        <div style="display:grid;gap:20px">
          <div class="panel" data-reveal>
            <div class="panel__head">
              <h3>Perfil técnico</h3>
              <span class="ai-score">${ICON_AI} ${nf1.format(potential)} potencial</span>
            </div>
            <div class="panel__body">
              ${Object.entries(ATTR_LABELS)
                .map(
                  ([key, label]) => `
                <div class="attr-row">
                  <span>${label}</span>
                  <div class="bar"><i data-fill="${player.attrs[key]}"></i></div>
                  <b>${player.attrs[key]}</b>
                </div>`
                )
                .join("")}
            </div>
          </div>

          <div class="panel" data-reveal>
            <div class="panel__head"><h3>Jugadores similares</h3><span class="tag">IA</span></div>
            <div class="panel__body">
              <div class="ai-note">
                ${ICON_AI}
                <span>Nuestro modelo compara ${formatNumber(GLOBAL_STATS.players)} perfiles cruzando
                atributos, edad y demarcación para encontrar los estilos más parecidos a ${player.name}.</span>
              </div>
              ${similar
                .map(
                  ({ player: p, score }) => `
                <a class="similar-row" href="jugador.html?id=${p.id}">
                  ${avatarHTML(p, "avatar--sm")}
                  <div class="result__main">
                    <div class="result__name">${p.name}</div>
                    <div class="result__meta">${p.pos} · ${p.age} años · ${formatValue(p.value)}</div>
                  </div>
                  <span class="affinity">${score}%</span>
                </a>`
                )
                .join("")}
              <a class="btn btn--block btn--sm" style="margin-top:14px"
                 href="comparador.html?a=${player.id}&b=${similar[0].player.id}">Comparar con ${similar[0].player.name}</a>
            </div>
          </div>
        </div>
      </div>
    </section>`;

  renderValueChart($("#value-chart"), player.valueHistory);
  observeReveals(host);
  animateBars(host);
}

async function initComparator() {
  const players = await api.getPlayers({ sort: "value" });
  const params = new URLSearchParams(location.search);

  const state = {
    a: params.get("a") || "yamal",
    b: params.get("b") || "bellingham"
  };

  const selectA = $("#select-a");
  const selectB = $("#select-b");

  const optionsHTML = (selected) =>
    players
      .map(
        (p) =>
          `<option value="${p.id}" ${p.id === selected ? "selected" : ""}>${p.name} · ${clubOf(p).short}</option>`
      )
      .join("");

  const byId = (id) => players.find((p) => p.id === id) || players[0];

  function renderPick(side, player) {
    const club = clubOf(player);
    const host = $(`#pick-${side}`);
    host.innerHTML = `
      ${avatarHTML(player, "avatar--xl")}
      <div class="pick__name">${player.flag} ${player.name}</div>
      <div class="pick__meta">${player.position} · ${club.name}</div>
      <div class="value-tag" style="font-size:1.5rem;margin-top:8px">${formatValue(player.value)}</div>`;
  }

  function duelHTML(label, valueA, valueB, format = (v) => nf1.format(v), higherIsBetter = true) {
    const max = Math.max(valueA, valueB) || 1;
    const winA = higherIsBetter ? valueA > valueB : valueA < valueB;
    const winB = higherIsBetter ? valueB > valueA : valueB < valueA;
    return `
      <div class="duel ${winA ? "is-win-a" : ""} ${winB ? "is-win-b" : ""}">
        <div class="duel__side duel__side--a">
          <span class="duel__num">${format(valueA)}</span>
          <div class="duel__bar"><i data-fill="${(valueA / max) * 100}"></i></div>
        </div>
        <div class="duel__label">${label}</div>
        <div class="duel__side duel__side--b">
          <span class="duel__num">${format(valueB)}</span>
          <div class="duel__bar"><i data-fill="${(valueB / max) * 100}"></i></div>
        </div>
      </div>`;
  }

  function render() {
    const a = byId(state.a);
    const b = byId(state.b);

    renderPick("a", a);
    renderPick("b", b);

    const ratingA = aiRating(a);
    const ratingB = aiRating(b);
    const int = (v) => nf.format(Math.round(v));

    $("#duels").innerHTML = [
      duelHTML("Puntuación IA", ratingA, ratingB),
      duelHTML("Potencial IA", aiPotential(a), aiPotential(b)),
      duelHTML("Valor de mercado", a.value, b.value, (v) => formatValue(v)),
      duelHTML("Edad", a.age, b.age, (v) => `${v} años`, false),
      duelHTML("Partidos", a.stats.matches, b.stats.matches, int),
      duelHTML("Goles", a.stats.goals, b.stats.goals, int),
      duelHTML("Asistencias", a.stats.assists, b.stats.assists, int),
      duelHTML("Minutos", a.stats.minutes, b.stats.minutes, int),
      duelHTML("G+A por 90'", productivity(a), productivity(b))
    ].join("");

    renderRadarChart($("#radar"), a, b);

    const winner = ratingA === ratingB ? null : ratingA > ratingB ? a : b;
    const gap = Math.abs(ratingA - ratingB);
    const younger = a.age <= b.age ? a : b;

    // Eficiencia: puntos de rating por cada 10 M € de valor de mercado
    const efficiency = (p) => (aiRating(p) / Math.max(p.value, 1)) * 10;
    const bestValue = efficiency(a) >= efficiency(b) ? a : b;

    $("#verdict").innerHTML = `
      <div class="verdict__card">
        <h4>Veredicto del modelo</h4>
        <p>${
          winner
            ? `<strong>${winner.name}</strong> lidera la comparativa con <strong>${nf1.format(Math.max(ratingA, ratingB))}</strong> de puntuación IA, ${gap < 2 ? "aunque la diferencia es mínima" : `${nf1.format(gap)} puntos por encima`}.`
            : "Empate técnico: ambos perfiles rinden al mismo nivel según el modelo."
        }</p>
      </div>
      <div class="verdict__card">
        <h4>Proyección</h4>
        <p><strong>${younger.name}</strong> es ${Math.abs(a.age - b.age) === 0 ? "de la misma quinta" : `${Math.abs(a.age - b.age)} años más joven`} y alcanza un techo estimado de <strong>${nf1.format(aiPotential(younger))}</strong>.</p>
      </div>
      <div class="verdict__card">
        <h4>Relación calidad-precio</h4>
        <p><strong>${bestValue.name}</strong> ofrece ${nf1.format(efficiency(bestValue))} puntos de rating por cada 10 M € de valor, frente a los ${nf1.format(efficiency(bestValue === a ? b : a))} del otro perfil.</p>
      </div>
      <div class="verdict__card">
        <h4>Afinidad de perfil</h4>
        <p>Sus estilos coinciden en un <strong>${affinity(a, b)}%</strong>. ${
          affinity(a, b) > 75
            ? "Son alternativas intercambiables en un mismo sistema."
            : "Aportan cualidades distintas y podrían complementarse."
        }</p>
      </div>`;

    animateBars($("#duels"));

    const url = `${location.pathname}?a=${state.a}&b=${state.b}`;
    history.replaceState(null, "", url);
  }

  selectA.innerHTML = optionsHTML(state.a);
  selectB.innerHTML = optionsHTML(state.b);

  selectA.addEventListener("change", (e) => {
    state.a = e.target.value;
    render();
  });
  selectB.addEventListener("change", (e) => {
    state.b = e.target.value;
    render();
  });

  $("#swap").addEventListener("click", () => {
    [state.a, state.b] = [state.b, state.a];
    selectA.value = state.a;
    selectB.value = state.b;
    render();
  });

  $("#random").addEventListener("click", () => {
    const pick = () => players[Math.floor(Math.random() * players.length)].id;
    state.a = pick();
    do { state.b = pick(); } while (state.b === state.a);
    selectA.value = state.a;
    selectB.value = state.b;
    render();
  });

  render();
  observeReveals();
}

/* ==========================================================================
   Arranque
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initHeader();
  initSearch();

  const year = $("#year");
  if (year) year.textContent = new Date().getFullYear();

  switch (document.body.dataset.page) {
    case "home":
      initHome();
      break;
    case "player":
      initPlayerPage();
      break;
    case "club":
      initClubPage();
      break;
    case "compare":
      initComparator();
      break;
    case "cuenta":
      initAuth();
      break;
    case "matches":
      initMatchesPage();
      break;
    case "match":
      initMatchDetailPage();
      break;
    case "competitions":
      initCompetitionsPage();
      break;
    case "competition":
      initCompetitionDetailPage();
      break;
    default:
      observeReveals();
  }
});