# IFLXI — Cómo importar el Excel a PostgreSQL

Este proceso es para **Juanjo** (desarrollo).  
**No lo necesita tu sobrino.** Él solo rellena el Excel en OneDrive.

No modificamos el Excel compartido al importar: solo lo **leemos**.

---

## 1. Requisitos

- BD `iflxi` creada con el DDL aprobado
- Python 3 + paquetes:

```powershell
py -m pip install openpyxl "psycopg[binary]"
```

---

## 2. Configurar conexión (misma ventana PowerShell)

```powershell
$env:PGHOST = "localhost"
$env:PGPORT = "5432"
$env:PGUSER = "postgres"
$env:PGPASSWORD = "TU_PASSWORD"
$env:PGDATABASE = "iflxi"
```

---

## 3. Descargar una copia del Excel (recomendado)

Si el sobrino trabaja en OneDrive, descarga una copia local (o usa la ruta OneDrive) y **no bloquees su archivo** mientras él edita.

```powershell
cd C:\Users\juanj\OneDrive\Escritorio\IFLXI\carga
```

---

## 4. Probar sin escribir (dry-run)

```powershell
py importar_excel.py --dry-run
```

O con otra ruta:

```powershell
py importar_excel.py --dry-run --excel "C:\ruta\IFLXI_Carga_Datos_MVP.xlsx"
```

---

## 5. Cargar en la BD

```powershell
py importar_excel.py --apply
```

El script:

- respeta el orden de hojas
- traduce códigos (`ES`, `FCB`, `YAMAL`…) a UUID
- guarda el mapa en `.import_map.json` (para reimportar sin duplicar IDs)
- actualiza caches `current_team_id` y `current_market_value`

---

## 6. Validar calidad

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -d iflxi -f "..\sql\IFLXI-validaciones-carga.sql"
```

Las consultas de “debe ser 0 filas” tienen que salir vacías.

---

## Avisos

- Si un jugador tiene nacionalidad `GB`, ese país debe existir en `01_Paises`.
- No uses `assist` ni `substitution_in` en eventos.
- Cesión: `rol=loan` + `prestado_desde`.
- Free: importe vacío.

---

## Archivos

| Archivo | Quién |
|---|---|
| `IFLXI_Carga_Datos_MVP.xlsx` | Sobrino (edita) |
| `importar_excel.py` | Juanjo |
| `.import_map.json` | Generado automático (no compartir al sobrino) |
| `../sql/IFLXI-validaciones-carga.sql` | Juanjo |
