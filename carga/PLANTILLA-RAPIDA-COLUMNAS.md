# Qué significa cada columna (versión corta)

Abre siempre primero: `00-LEE-ESTO-PRIMERO.md`

## 01 Países
| Columna | Ejemplo | Obligatorio |
|---|---|---|
| codigo_pais | ES | sí |
| nombre | Spain | sí |
| codigo_iso3 | ESP | no |
| codigo_fifa | ESP | no |
| continente | EU | no |
| activo | si / no | sí |

## 02 Ciudades
| Columna | Ejemplo | Obligatorio |
|---|---|---|
| codigo_ciudad | BCN | sí |
| nombre | Barcelona | sí |
| codigo_pais | ES | sí (debe existir en 01) |
| activo | si | sí |

## 05 Equipos
| Columna | Ejemplo | Notas |
|---|---|---|
| codigo_equipo | FCB | tu código interno |
| tipo_equipo | club / national | |
| codigo_pais | ES | obligatorio |
| codigo_ciudad | BCN | opcional |
| codigo_equipo_padre | | solo filiales |

## 08 Jugadores
| Columna | Notas |
|---|---|
| codigo_jugador | ej. YAMAL |
| codigo_persona | debe existir en 07 |
| estado | active / retired / … |
| **No pongas goles ni asistencias aquí** | van en eventos |

## 09 Historial
| Columna | Notas |
|---|---|
| fecha_fin | vacío = sigue en el equipo |
| rol | permanent o loan |
| prestado_desde | solo si rol = loan (club dueño) |

**Jugador libre:** no dejes ninguna fila de club con `fecha_fin` vacía.

## 11 Eventos
| tipo_evento | jugador | jugador_secundario |
|---|---|---|
| goal / penalty_goal | goleador | asistente (o vacío) |
| own_goal | quien marca en propia | vacío |
| yellow_card / red_card / second_yellow | quien recibe | vacío |
| substitution_out | quien SALE | quien ENTRA |

## 12 Fichajes
| Columna | Notas |
|---|---|
| importe | vacío si free (NO pongas 0) |
| codigo_historial_destino | el historial del equipo al que llega |

## Sí / No
Escribe siempre: `si` o `no` (minúsculas, sin tilde).
