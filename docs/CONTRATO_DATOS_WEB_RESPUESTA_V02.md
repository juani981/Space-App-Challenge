# Contrato de datos para la web: respuesta de Claude Code (v0.2)

> **Origen:** respuesta del agente de datos (Claude Code) al pedido del equipo web, el 15-nov-2026.
> **Base:** `wildfire-armonizado` (esquema `harmonized`). **Versión del método:** `v0.2`. **Período:** 2012-01 a 2026-08.
> **Fuente completa en el repositorio:** `docs/CONTRATO_DATOS_WEB.md` (incluye la sección 8.3 con los 176 meses completos).
>
> **Qué contiene este documento.** Las secciones 3 (casos de prueba), 4, 5, 6, 7 y 8 de la respuesta, más el código de la anomalía. El texto recibido **no incluía** la sección 1 (DDL completo y compatibilidad con PostgreSQL 18), la sección 2 (explicación del mapa de bits; el mapa completo sí está en la sección 8.2, tabla `quality_bits`) ni el código Python de las funciones de grilla (`bbox_to_ranges`, `polygon_to_ranges`, `area_region_km2`). Todo eso está en el archivo del repositorio.
>
> Las partes marcadas como **[nota de edición]** no provienen de Claude Code y se explican en la sección 9.

---

## 3. Grilla `cell_id ↔ (lat, lon)`

### 3.1 Convención **[nota de edición: deducida y verificada contra los casos de prueba]**

```text
fila     = cell_id // 1440          (fila 0 = Sur, lat −89,875)
columna  = cell_id %  1440          (columna 0 = lon −179,875)
lat_center = −90  + (fila + 0,5) · 0,25
lon_center = −180 + (columna + 0,5) · 0,25
área_km2 = R² · radianes(0,25) · ( sin(lat_norte) − sin(lat_sur) ),  R = 6371 km
           con lat_sur = −90 + fila·0,25  y  lat_norte = −90 + (fila+1)·0,25
```

Total: 720 filas × 1440 columnas = 1.036.800 celdas (`cell_id` de 0 a 1.036.799).

### 3.2 Casos de prueba verificados contra PostgreSQL

Valores de `harmonized.cell_month`; el error relativo de área es < 1e-6.

| Caso | cell_id | lat_center | lon_center | cell_area_km2 (BD) | Python |
|---|---|---|---|---|---|
| Sudamérica | 373439 | −25,125 | −60,125 | 699,6523 | igual |
| Ecuador | 519200 | 0,125 | 20,125 | 772,767 | igual |
| Latitud alta | 1021366 | 87,375 | −78,375 | 35,391937 | igual |
| Borde antimeridiano | 908639 | 67,625 | 179,875 | 294,16754 | igual |
| Sur extremo | 172334 | −60,125 | 63,625 | 384,92346 | igual |

### 3.3 `bbox → rangos de cell_id`

| bbox `[min_lon, min_lat, max_lon, max_lat]` | Rangos | Celdas | Área (km²) | Filas jul-2024 por rangos | Filas jul-2024 por centro (SQL) |
|---|---|---|---|---|---|
| Sudamérica `[-82, -56, -34, 13]` | 276 | 52.992 | 35.840.143,5 | 12.473 | 12.473 |
| Ecuador `[15, -5, 25, 5]` | 40 | 1.600 | 1.234.862,4 | 1.126 | 1.126 |
| Antimeridiano `[170, 60, -170, 72]` | 96 | 3.840 | 1.204.759,7 | 3 | 3 |
| Polo norte recortado `[-180, 80, 180, 95]` | 1 | 57.600 | 3.874.512,7 (= 2πR²(1 − sin 80°)) | 4 | 4 |

**Polígono:** un rectángulo pasado como polígono devuelve exactamente los mismos rangos que el bbox (10.560 celdas). Un triángulo de 10° × 10° devuelve 800 celdas (= área / 0,0625).

---

## 4. Dominios y nulabilidad (`cell_month`)

| Columna | Tipo | Nulos | Dominio real |
|---|---|---|---|
| `month` | `date` | no | Primer día del mes, 2012-01-01 … 2026-08-01 |
| `cell_id` | `integer` | no | 0 … 1.036.799 |
| `n_eq`, `f_eq` | `real` | no (0 si la referencia no detectó) | ≥ 0; 1.834.329 filas con `n_eq = 0` |
| `ref_sat` | `smallint` | no | 3 (S-NPP, 2012-01..2019-12), 4 (NOAA-20, 2020-01..2026-07 salvo 2023-07), 5 (NOAA-21, 2023-07), 2 (Aqua, 2026-08) |
| `sensors` | `text` | no | Exactamente 4 valores: `'SNPP'`, `'N20'`, `'N21 (respaldo de N20)'`, `'Aqua (solo MODIS / deriva)'` |
| `n_terra`, `n_aqua`, `n_snpp`, `n_n20`, `n_n21` | `integer` | no | ≥ 0; 0 si el satélite no operaba (NOAA-20 antes de 2018-04, NOAA-21 antes de 2023-03, VIIRS en 2026-08) o no detectó |
| `frp_terra` … `frp_n21` | `real` (MW) | no | ≥ 0; 0 en los mismos casos |
| `quality_flag` | `smallint` | no | Ver `quality_bits` (sección 8.2) |
| `method_version` | `text` | no | `'v0.2'` |
| `lat_center`, `lon_center`, `cell_area_km2` | `real` | no | Ver sección 3 |

- `n_*` y `frp_*` usan el mismo filtro: `type = 0` (vegetación) y sin confianza baja (MODIS `confidence >= 30`; VIIRS `confidence <> 'l'`).
- `n_eq = α · n_ref` y `f_eq = γ · frp_ref`, donde `ref` es el satélite indicado en `ref_sat`. En 2026-08, `n_eq = n_aqua` y `f_eq = frp_aqua`.
- Las sumas regionales conviene hacerlas en `float8`: `sum(n_eq::float8)`.

---

## 5. Ceros y cobertura

- **Ausencia de fila = 0** en todas las columnas de conteo y FRP para esa celda y mes. Hay fila si **cualquier satélite detectó algo** en la celda, de cualquier tipo o confianza. Por eso existen filas con `n_eq = 0`: por ejemplo, detecciones solo de S-NPP en 2024 (ver la muestra en 8.1), o solo de `type ≠ 0` o de confianza baja.
- **"0 fuegos reales" frente a "sin cobertura":** la información de cobertura es **por mes y satélite, no por celda**.
  - Hueco de cobertura del mes: `reference_plan.quality_flag & (8 | 16) <> 0` (referencia incompleta), o `& 4` (solo MODIS). En la v0.2: 2012-03 (bits 3 y 4) y 2026-08 (bit 2).
  - Mes con respaldo (cobertura completa con otro satélite): bit 6 (2023-07).
  - Mes completo (bits 3, 4 y 2 apagados): un 0 es "0 detecciones tras los filtros", es decir, sin fuego detectable a ese umbral.
  - Detalle por satélite: `sat_month_quality` (`days_missing`, `days_caida`, `days_catalog`, `days_minutes_low`, `days_affected`, `complete`). Incluye los huecos de S-NPP en 2022–2026, que no afectan la serie porque S-NPP no es la referencia desde 2020.
  - Detalle espacial opcional: `sat_day_effort` por banda de 10° (un `n_minutes` bajo frente a días vecinos indica pasadas faltantes en esa banda).
  - `known_gap` solo tiene 4 huecos documentados (Aqua 2020-08 y 2022-04; Terra 2016-02 y 2022-10). Los días faltantes de los VIIRS están en `sat_month_quality`.
- **Tope de celdas a 0,25°** (no hay tabla de 1°): 50.000 celdas por consulta de calendario. Sudamérica (52.992 celdas) tarda 0,7–0,83 s en caliente y 1,1 s en frío. Por encima del tope, rechazar o pedir una región menor. Para el mapa al alejar el zoom, agregar a 1° al vuelo (sección 6c).

---

## 6. Consultas medidas (SQL exacto y `EXPLAIN ANALYZE, BUFFERS`; segunda ejecución)

Parámetros: `$1` = arreglo de inicios y `$2` = arreglo de finales de `bbox_to_ranges` / `polygon_to_ranges`. Con psycopg 3 se pasan como `list[int]`.

Forma recomendada: `CROSS JOIN LATERAL (… OFFSET 0)`. Obliga a una búsqueda por índice por rango; sin ella, el planificador eligió un recorrido completo en un caso medido (4,6 s).

### 6a. Serie mensual del calendario

```sql
WITH reg AS (
  SELECT x.month,
         sum(x.n_eq::float8)                  AS n_eq,
         sum(x.f_eq::float8)                  AS f_eq,
         count(*)                             AS celdas_con_filas,
         bit_or(x.quality_flag) & 128         AS bit7
    FROM unnest($1::int[], $2::int[]) AS r(s, e)
    CROSS JOIN LATERAL (
      SELECT m.month, m.n_eq, m.f_eq, m.quality_flag
        FROM harmonized.cell_month m
       WHERE m.cell_id BETWEEN r.s AND r.e
      OFFSET 0) x
   GROUP BY x.month)
SELECT p.month,
       coalesce(reg.n_eq, 0)                  AS n_eq,
       coalesce(reg.f_eq, 0)                  AS f_eq,
       coalesce(reg.celdas_con_filas, 0)      AS celdas_con_filas,
       p.quality_flag | coalesce(reg.bit7, 0) AS quality_flag,
       p.excluded_from_baseline,
       p.ref_sat,
       p.sensors
  FROM harmonized.reference_plan p          -- 176 meses: completa ceros sin perder banderas
  LEFT JOIN reg USING (month)
 ORDER BY p.month;
```

Traer **siempre los 176 meses**: la anomalía necesita la base completa. El rango de fechas del usuario solo filtra lo que se muestra.

| AOI | Celdas | Rangos | Tiempo (`unnest + JOIN`) | Tiempo (`LATERAL … OFFSET 0`) | Buffers |
|---|---|---|---|---|---|
| Chico (Córdoba `[-65.8,-35,-61.8,-29.5]`) | 352 | 22 | 10,6 ms | — | hit 43, read 356 |
| Mediano (Argentina `[-73.5,-55,-53.5,-22]`) | 10.560 | 132 | 173,8 ms | 119,9 ms | hit 886, read 5.751 |
| Sudamérica `[-82,-56,-34,13]` | 52.992 | 276 | 829,9 ms | 712,6 ms | hit 6.968, read 26.038 |

Plan (todas las variantes): `Nested Loop → Index Scan using cell_month_pkey on cell_month m`, con `Index Cond: ((cell_id >= r.s) AND (cell_id <= r.e))`, una búsqueda por rango (22, 132 o 276), y `Hash Join` con `reference_plan` (176 filas, `Seq Scan`, 2 buffers).

Variante con `generate_series` como columna vertebral (equivalente; la medida de la tabla usa esta forma en la columna "unnest + JOIN"):

```sql
WITH meses AS (SELECT (date '2012-01-01' + make_interval(months => i))::date AS month FROM generate_series(0, 175) i),
reg AS (
  SELECT m.month, sum(m.n_eq) AS n_eq, sum(m.f_eq) AS f_eq, count(*) AS celdas_con_filas,
         bit_or(m.quality_flag) & 128 AS bit7
    FROM unnest($1::int[], $2::int[]) AS r(s, e)
    JOIN harmonized.cell_month m ON m.cell_id BETWEEN r.s AND r.e
   GROUP BY m.month)
SELECT x.month, coalesce(reg.n_eq, 0) AS n_eq, coalesce(reg.f_eq, 0) AS f_eq,
       coalesce(reg.celdas_con_filas, 0) AS celdas_con_filas,
       p.quality_flag | coalesce(reg.bit7, 0) AS quality_flag,
       p.excluded_from_baseline, p.ref_sat, p.sensors
  FROM meses x JOIN harmonized.reference_plan p USING (month) LEFT JOIN reg USING (month)
 ORDER BY x.month;
```

### 6b. `area_region_km2`

```sql
SELECT sum((6371.0 ^ 2) * radians(0.25)
           * (sin(radians(-90 + ((r.s / 1440) + 1) * 0.25)) - sin(radians(-90 + (r.s / 1440) * 0.25)))
           * (r.e - r.s + 1)) AS area_region_km2
  FROM unnest($1::int[], $2::int[]) AS r(s, e);   -- requiere rangos de una sola fila (no unir filas completas)
```

Sudamérica: 0,23 ms (1 fila; 3 buffers). Resultado igual a `area_region_km2()` en Python: 35.840.143,5 km².

### 6c. Capa de mapa limitada al encuadre visible

```sql
-- 1 mes: map_month (BRIN por mes) + filtro por fila/columna derivado de cell_id.
-- Rectángulo [r0..r1] × [c0..c1]
SELECT m.cell_id, m.n_eq, m.f_eq
  FROM harmonized.map_month m
 WHERE m.month = $1
   AND m.cell_id BETWEEN $2 * 1440 AND $3 * 1440 + 1439          -- $2 = r0, $3 = r1
   AND (m.cell_id / 1440) BETWEEN $2 AND $3
   AND (m.cell_id % 1440) BETWEEN $4 AND $5;                     -- $4 = c0, $5 = c1
-- antimeridiano: reemplazar la última línea por
--   AND ((m.cell_id % 1440) BETWEEN $4 AND 1439 OR (m.cell_id % 1440) BETWEEN 0 AND $5)
```

```sql
-- Varios meses o serie completa: cell_month con LATERAL por rango (índice PK)
SELECT x.cell_id, sum(x.n_eq::float8) AS n_eq, sum(x.f_eq::float8) AS f_eq
  FROM unnest($1::int[], $2::int[]) AS r(s, e)
  CROSS JOIN LATERAL (
    SELECT m.cell_id, m.n_eq, m.f_eq
      FROM harmonized.cell_month m
     WHERE m.cell_id BETWEEN r.s AND r.e AND m.month BETWEEN $3 AND $4
    OFFSET 0) x
 GROUP BY x.cell_id;
```

```sql
-- Zoom alejado: agregación a 1° (4 × 4 celdas) al vuelo. block_id = fila_1° * 360 + col_1°
SELECT (m.cell_id / 1440) / 4 * 360 + (m.cell_id % 1440) / 4 AS block_id,
       sum(m.n_eq::float8) AS n_eq, sum(m.f_eq::float8) AS f_eq
  FROM harmonized.map_month m
 WHERE m.month = $1
   AND m.cell_id BETWEEN $2 * 1440 AND $3 * 1440 + 1439
   AND (m.cell_id / 1440) BETWEEN $2 AND $3
   AND (m.cell_id % 1440) BETWEEN $4 AND $5
 GROUP BY 1;
-- centro del bloque: lat = -90 + (block_id / 360) * 1 + 0.5 ; lon = -180 + (block_id % 360) * 1 + 0.5
```

| Encuadre | Consulta | Tiempo | Celdas / bloques | JSON aprox. (`[id, n_eq, f_eq]`) |
|---|---|---|---|---|
| Argentina | 1 mes (`map_month`, filtro fila/columna) | 6,1 ms | 2.758 | 57 kB |
| Argentina | 12 meses (`cell_month`, LATERAL) | 51,4 ms | 4.649 | 97 kB |
| Argentina | Serie completa (`cell_month`, JOIN por rangos) | 167,3 ms | 6.003 | 136 kB |
| Argentina | 1°, 1 mes | 34,9 ms | 343 | 7 kB |
| Argentina | 1°, 12 meses (`map_month`) | 47,4 ms | 415 | 9 kB |
| Sudamérica | 1 mes | 7,9 ms | 14.997 | 311 kB |
| Sudamérica | 12 meses (LATERAL) | 205,0 ms | 20.914 | 453 kB |
| Sudamérica | Serie completa (JOIN por rangos) | 946,2 ms | 24.783 | 574 kB |
| Sudamérica | 1°, 1 mes | 32,1 ms | 1.496 | 32 kB |
| Sudamérica | 1°, 12 meses (`map_month`) | 141,3 ms | 1.712 | 39 kB |
| Antimeridiano `[170,60,-170,72]` | 1 mes / 12 meses (LATERAL) | 32,1 ms / 0,4 ms | 1 / 11 | < 1 kB |

**Formas descartadas (medidas):**
- `map_month` unida a `unnest` de rangos: 671 ms (Argentina) y 1.954 ms (Sudamérica) para 1 mes, porque recorre el mes y compara cada celda contra todos los rangos.
- 12 meses con `unnest + JOIN` simple en Argentina: el planificador eligió `Parallel Seq Scan`, 4.635 ms.

**Propuesta de zoom:** a 0,25° hasta ~20.000 celdas visibles; por encima, 1°.

### 6d. Exportación CSV en streaming

```sql
COPY (
  SELECT m.*
    FROM unnest($1::int[], $2::int[]) AS r(s, e)
    CROSS JOIN LATERAL (
      SELECT * FROM harmonized.cell_month m
       WHERE m.cell_id BETWEEN r.s AND r.e AND m.month BETWEEN $3 AND $4
      OFFSET 0) m
   ORDER BY m.month, m.cell_id
) TO STDOUT WITH (FORMAT csv, HEADER);
```

```python
# FastAPI + psycopg 3: streaming sin cargar el CSV en memoria
from fastapi.responses import StreamingResponse
import psycopg

COPY_SQL = """COPY (SELECT m.* FROM unnest(%s::int[], %s::int[]) AS r(s, e)
  CROSS JOIN LATERAL (SELECT * FROM harmonized.cell_month m
     WHERE m.cell_id BETWEEN r.s AND r.e AND m.month BETWEEN %s AND %s OFFSET 0) m
  ORDER BY m.month, m.cell_id) TO STDOUT WITH (FORMAT csv, HEADER)"""
COUNT_SQL = """SELECT count(*) FROM unnest(%s::int[], %s::int[]) AS r(s, e)
  CROSS JOIN LATERAL (SELECT 1 FROM harmonized.cell_month m
     WHERE m.cell_id BETWEEN r.s AND r.e AND m.month BETWEEN %s AND %s OFFSET 0) m"""
CSV_MAX_ROWS = 1_000_000

def csv_stream(dsn, starts, ends, d0, d1):
    with psycopg.connect(dsn) as conn:
        conn.execute("SET statement_timeout = '60s'")
        n = conn.execute(COUNT_SQL, (starts, ends, d0, d1)).fetchone()[0]
        if n > CSV_MAX_ROWS:
            raise ValueError(f"{n} filas: supera el tope de {CSV_MAX_ROWS}")
        with conn.cursor().copy(COPY_SQL, (starts, ends, d0, d1)) as copy:
            for chunk in copy:
                yield bytes(chunk)

# return StreamingResponse(csv_stream(...), media_type="text/csv",
#                          headers={"Content-Disposition": "attachment; filename=wildfire_harmonized.csv"})
```

| Exportación | Filas | Tamaño CSV | Tiempo `COPY … TO STDOUT` | Velocidad |
|---|---|---|---|---|
| Argentina, 12 meses (2024) | 25.668 | 2,6 MB | 0,14 s | 182.795 filas/s |
| Argentina, serie completa | 359.145 | 36 MB | 1,12 s | 320.751 filas/s |
| Sudamérica, serie completa | 1.873.938 | 187 MB | 9,63 s | 194.624 filas/s |

**Tope recomendado:** 1.000.000 filas (~100 MB, ~5 s), verificado antes con el `COUNT` (que cuesta lo mismo que el calendario). La cabecera del CSV debe aclarar que son celdas de 0,25° seleccionadas por centro de celda.

---

## 7. Seguridad y operación

```sql
-- Como superusuario, en la base wildfire-armonizado
CREATE ROLE wildfire_web LOGIN PASSWORD '<CAMBIAR>' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT CONNECTION LIMIT 20;
REVOKE ALL ON DATABASE "wildfire-armonizado" FROM PUBLIC;
GRANT CONNECT ON DATABASE "wildfire-armonizado" TO wildfire_web;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA harmonized TO wildfire_web;
GRANT SELECT ON ALL TABLES IN SCHEMA harmonized TO wildfire_web;
ALTER DEFAULT PRIVILEGES IN SCHEMA harmonized GRANT SELECT ON TABLES TO wildfire_web;

ALTER ROLE wildfire_web SET default_transaction_read_only = on;
ALTER ROLE wildfire_web SET search_path = harmonized;
ALTER ROLE wildfire_web SET statement_timeout = '5s';                 -- calendario <= 1 s; el CSV sube a 60 s con SET LOCAL
ALTER ROLE wildfire_web SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE wildfire_web SET lock_timeout = '2s';
ALTER ROLE wildfire_web SET work_mem = '64MB';                        -- con 4 MB, el mapa de 12 meses de Sudamérica derramó a disco
ALTER ROLE wildfire_web SET jit = off;                                -- consultas cortas: JIT solo agrega latencia
```

- `pg_hba.conf`: permitir `wildfire_web` solo desde el host del backend, con `scram-sha-256`.
- Pool de conexiones (`psycopg_pool` o `asyncpg`): 5–10 conexiones.
- Validar entradas antes de consultar: fechas dentro de 2012-01..2026-08 y primer día de mes; polígono de ≤ 1.000 vértices; ≤ 50.000 celdas.
- Respuestas: informar `celdas_usadas` y avisar si son menos de 4; informar la resolución (0,25° o 1°); propagar `quality_flag`.
- Caché: `reference_plan`, `quality_bits`, `dataset_metadata`, `global_month` y `dim_satellite` son chicas y estáticas; cargarlas al iniciar el backend.
- Base de solo lectura: después del `VACUUM ANALYZE` de la restauración no hace falta mantenimiento.

### Anomalía (decisiones cerradas) en Python

Código reconstruido a partir de un texto con saltos de línea rotos; verificar contra el archivo del repositorio **[nota de edición]**.

```python
import math, statistics

EXCLUDE_BASELINE_MASK = 29      # bits 0, 2, 3 y 4 (1 + 4 + 8 + 16)
MIN_VALID_YEARS = 10

def anomaly(series: dict[tuple[int, int], tuple[float, int]], target: tuple[int, int]) -> dict | None:
    """series[(año, mes)] = (X regional sumado, quality_flag del mes, con el bit 7 si se quiere).
    Base = mismo mes calendario, otros años, con (flag & EXCLUDE_BASELINE_MASK) == 0 (leave-one-out)."""
    y, m = target
    X = series[target][0]
    base = [v for (yy, mm), (v, f) in series.items()
            if mm == m and yy != y and (f & EXCLUDE_BASELINE_MASK) == 0]
    if len(base) < MIN_VALID_YEARS:
        return None
    pct = (sum(b < X for b in base) + 0.5 * sum(b == X for b in base)) / len(base)
    clase = "<=50" if pct <= 0.50 else "50-75" if pct <= 0.75 else "75-90" if pct <= 0.90 else ">90"
    record = X > max(base)      # estrictamente mayor que el máximo de los meses válidos
    lb = [math.log1p(b) for b in base]
    med = statistics.median(lb)
    mad = statistics.median([abs(v - med) for v in lb])
    if mad > 0:
        z_robusto, razon_mediana = (math.log1p(X) - med) / (1.4826 * mad), None
    else:
        mb = statistics.median(base)
        z_robusto, razon_mediana = None, (X / mb if mb > 0 else None)   # None si la mediana es 0
    return {"n_base": len(base), "percentil": pct, "clase": clase, "record": record,
            "z_robusto": z_robusto, "razon_mediana": razon_mediana}
```

Probado según Claude Code: un caso normal (percentil 0,9167, clase `>90`, z 1,33); un mes excluido evaluado contra 13 años de base; y `MAD = 0` (`z_robusto = None`, `razon_mediana = None` con mediana 0).

---

## 8. Tamaños y muestras reales

| Tabla | Tamaño total | Filas | Mínimo | Máximo |
|---|---|---|---|---|
| `harmonized.cell_month` | 1276 MB | 9.588.557 | 2012-01-01 | 2026-08-01 |
| `harmonized.map_month` | 405 MB | 9.588.557 | 2012-01-01 | 2026-08-01 |
| `harmonized.sat_day_effort` | 18 MB | 273.099 | 2012-01-01 | 2026-08-31 |
| `harmonized.calibration_coef` | 112 kB | 648 | — | — |
| `harmonized.sat_month_quality` | 80 kB | 668 | 2012-01-01 | 2026-08-01 |
| `harmonized.global_month` | 56 kB | 176 | 2012-01-01 | 2026-08-01 |
| `harmonized.reference_plan` | 40 kB | 176 | 2012-01-01 | 2026-08-01 |
| `harmonized.known_gap` | 48 kB | 4 | 2016-02-19 (`date_from`) | 2022-10-23 (`date_to`) |
| `harmonized.dim_satellite` | 48 kB | 5 | 2012-01-01 (`first_date`) | 2026-08-31 (`last_date`) |
| `harmonized.quality_bits` | 32 kB | 8 | — | — |
| `harmonized.dataset_metadata` | 32 kB | 15 | — | — |
| **Esquema publicado** | **1.700 MB** | | | |

### 8.1 `cell_month`: Sudamérica (lat −35..−20, lon −66..−55)

Un mes normal (2024-08), ene-2012 parcial (bit 0), jul-2023 con respaldo NOAA-21 (bit 6), ago-2026 solo MODIS y último mes (bits 1 y 2), y una fila con `n_eq = 0`. Transcrito de un texto con saltos de línea: **verificar contra el archivo del repositorio**.

```json
[
  {"month":"2024-08-01","cell_id":402253,"lat_center":-20.125,"lon_center":-56.625,"cell_area_km2":725.58685,"n_eq":351.95383,"f_eq":49090.848,"ref_sat":4,"sensors":"N20","n_terra":190,"n_aqua":227,"n_snpp":1475,"n_n20":1601,"n_n21":1384,"frp_terra":15610.309,"frp_aqua":43269.906,"frp_snpp":32173.04,"frp_n20":53659.496,"frp_n21":40733.55,"quality_flag":0,"method_version":"v0.2"},
  {"month":"2024-08-01","cell_id":402254,"lat_center":-20.125,"lon_center":-56.375,"cell_area_km2":725.58685,"n_eq":330.4101,"f_eq":23812.443,"ref_sat":4,"sensors":"N20","n_terra":121,"n_aqua":157,"n_snpp":1589,"n_n20":1503,"n_n21":1602,"frp_terra":9206.2,"frp_aqua":18057.11,"frp_snpp":25443.594,"frp_n20":26028.553,"frp_n21":24543.293,"quality_flag":0,"method_version":"v0.2"},
  {"month":"2024-08-01","cell_id":399370,"lat_center":-20.625,"lon_center":-57.375,"cell_area_km2":723.23895,"n_eq":263.141,"f_eq":9964.496,"ref_sat":4,"sensors":"N20","n_terra":90,"n_aqua":172,"n_snpp":1318,"n_n20":1197,"n_n21":1148,"frp_terra":2917.1003,"frp_aqua":9701.199,"frp_snpp":13736.167,"frp_n20":10891.844,"frp_n21":12295.302,"quality_flag":0,"method_version":"v0.2"},
  {"month":"2024-08-01","cell_id":399371,"lat_center":-20.625,"lon_center":-57.125,"cell_area_km2":723.23895,"n_eq":245.99396,"f_eq":10879.312,"ref_sat":4,"sensors":"N20","n_terra":69,"n_aqua":145,"n_snpp":1301,"n_n20":1119,"n_n21":1135,"frp_terra":1340.5001,"frp_aqua":9429.396,"frp_snpp":12103.57,"frp_n20":11891.797,"frp_n21":11201.374,"quality_flag":0,"method_version":"v0.2"},
  {"month":"2012-01-01","cell_id":373447,"lat_center":-25.125,"lon_center":-58.125,"cell_area_km2":699.6523,"n_eq":29.413475,"f_eq":1377.7814,"ref_sat":3,"sensors":"SNPP","n_terra":40,"n_aqua":33,"n_snpp":205,"n_n20":0,"n_n21":0,"frp_terra":1867.9999,"frp_aqua":1549.0001,"frp_snpp":1972.3604,"frp_n20":0,"frp_n21":0,"quality_flag":1,"method_version":"v0.2"},
  {"month":"2012-01-01","cell_id":370567,"lat_center":-25.625,"lon_center":-58.125,"cell_area_km2":696.7623,"n_eq":24.104702,"f_eq":1336.4551,"ref_sat":3,"sensors":"SNPP","n_terra":21,"n_aqua":22,"n_snpp":168,"n_n20":0,"n_n21":0,"frp_terra":704.3999,"frp_aqua":894.10004,"frp_snpp":1913.1997,"frp_n20":0,"frp_n21":0,"quality_flag":1,"method_version":"v0.2"},
  {"month":"2012-01-01","cell_id":366249,"lat_center":-26.375,"lon_center":-57.625,"cell_area_km2":692.328,"n_eq":22.956858,"f_eq":1315.9246,"ref_sat":3,"sensors":"SNPP","n_terra":30,"n_aqua":33,"n_snpp":160,"n_n20":0,"n_n21":0,"frp_terra":788.69995,"frp_aqua":1808.5001,"frp_snpp":1883.8093,"frp_n20":0,"frp_n21":0,"quality_flag":1,"method_version":"v0.2"},
  {"month":"2023-07-01","cell_id":373453,"lat_center":-25.125,"lon_center":-56.625,"cell_area_km2":699.6523,"n_eq":51.804165,"f_eq":2119.8723,"ref_sat":5,"sensors":"N21 (respaldo de N20)","n_terra":30,"n_aqua":40,"n_snpp":223,"n_n20":251,"n_n21":227,"frp_terra":923.6,"frp_aqua":2170.0999,"frp_snpp":2679.4084,"frp_n20":3318.2876,"frp_n21":2591.41,"quality_flag":64,"method_version":"v0.2"},
  {"month":"2023-07-01","cell_id":383513,"lat_center":-23.375,"lon_center":-61.625,"cell_area_km2":709.34607,"n_eq":49.750256,"f_eq":5043.29,"ref_sat":5,"sensors":"N21 (respaldo de N20)","n_terra":21,"n_aqua":65,"n_snpp":276,"n_n20":89,"n_n21":218,"frp_terra":6233.8,"frp_aqua":4929.7,"frp_snpp":4211.2314,"frp_n20":469.00995,"frp_n21":6165.1035,"quality_flag":64,"method_version":"v0.2"},
  {"month":"2023-07-01","cell_id":357609,"lat_center":-27.875,"lon_center":-57.625,"cell_area_km2":683.1043,"n_eq":29.211159,"f_eq":763.72864,"ref_sat":5,"sensors":"N21 (respaldo de N20)","n_terra":5,"n_aqua":24,"n_snpp":153,"n_n20":27,"n_n21":128,"frp_terra":125.2,"frp_aqua":711.49994,"frp_snpp":1351.4602,"frp_n20":167.48997,"frp_n21":933.61,"quality_flag":64,"method_version":"v0.2"},
  {"month":"2023-07-01","cell_id":399358,"lat_center":-20.625,"lon_center":-60.375,"cell_area_km2":723.23895,"n_eq":28.754734,"f_eq":1598.7577,"ref_sat":5,"sensors":"N21 (respaldo de N20)","n_terra":48,"n_aqua":33,"n_snpp":127,"n_n20":91,"n_n21":126,"frp_terra":4262.901,"frp_aqua":2774.9001,"frp_snpp":1574.7896,"frp_n20":1186.1105,"frp_n21":1954.3802,"quality_flag":64,"method_version":"v0.2"},
  {"month":"2026-08-01","cell_id":369103,"lat_center":-25.875,"lon_center":-64.125,"cell_area_km2":695.2975,"n_eq":51,"f_eq":4361.1997,"ref_sat":2,"sensors":"Aqua (solo MODIS / deriva)","n_terra":9,"n_aqua":51,"n_snpp":0,"n_n20":0,"n_n21":0,"frp_terra":146.2,"frp_aqua":4361.1997,"frp_snpp":0,"frp_n20":0,"frp_n21":0,"quality_flag":6,"method_version":"v0.2"},
  {"month":"2026-08-01","cell_id":399355,"lat_center":-20.625,"lon_center":-61.125,"cell_area_km2":723.23895,"n_eq":38,"f_eq":5226.8,"ref_sat":2,"sensors":"Aqua (solo MODIS / deriva)","n_terra":38,"n_aqua":38,"n_snpp":0,"n_n20":0,"n_n21":0,"frp_terra":3655.5999,"frp_aqua":5226.8,"frp_snpp":0,"frp_n20":0,"frp_n21":0,"quality_flag":6,"method_version":"v0.2"},
  {"month":"2026-08-01","cell_id":400806,"lat_center":-20.375,"lon_center":-58.375,"cell_area_km2":724.4198,"n_eq":30,"f_eq":1417.1,"ref_sat":2,"sensors":"Aqua (solo MODIS / deriva)","n_terra":15,"n_aqua":30,"n_snpp":0,"n_n20":0,"n_n21":0,"frp_terra":195.1,"frp_aqua":1417.1,"frp_snpp":0,"frp_n20":0,"frp_n21":0,"quality_flag":6,"method_version":"v0.2"},
  {"month":"2024-08-01","cell_id":317258,"lat_center":-34.875,"lon_center":-65.375,"cell_area_km2":633.9807,"n_eq":0,"f_eq":0,"ref_sat":4,"sensors":"N20","n_terra":0,"n_aqua":0,"n_snpp":3,"n_n20":0,"n_n21":0,"frp_terra":0,"frp_aqua":0,"frp_snpp":22.73,"frp_n20":0,"frp_n21":0,"quality_flag":0,"method_version":"v0.2"}
]
```

### 8.2 Tablas auxiliares

**`map_month`** (3 filas de muestra):

```json
[
  {"month":"2024-08-01","cell_id":373408,"n_eq":0.21983373,"f_eq":0.9240071},
  {"month":"2024-08-01","cell_id":373410,"n_eq":0,"f_eq":0},
  {"month":"2024-08-01","cell_id":373411,"n_eq":0.21983373,"f_eq":0.8050755}
]
```

**`global_month`** (4 filas de muestra):

```json
[
  {"month":"2012-01-01","n_eq":84957.09375,"f_eq":3129637.5,"n_terra":127302,"n_aqua":234750,"n_snpp":507930,"n_n20":0,"n_n21":0,"frp_terra":4420968,"frp_aqua":8631598,"n_cells":32247,"ref_sat":3,"sensors":"SNPP","quality_flag":1,"excluded_from_baseline":true},
  {"month":"2023-07-01","n_eq":353789.96875,"f_eq":18924308,"n_terra":155771,"n_aqua":373996,"n_snpp":2000417,"n_n20":1855323,"n_n21":2028923,"frp_terra":8567092,"frp_aqua":18923280,"n_cells":60067,"ref_sat":5,"sensors":"N21 (respaldo de N20)","quality_flag":64,"excluded_from_baseline":false},
  {"month":"2024-08-01","n_eq":533706.5625,"f_eq":27645796,"n_terra":204560,"n_aqua":498793,"n_snpp":3103304,"n_n20":3037131,"n_n21":2907401,"frp_terra":9980086,"frp_aqua":28197462,"n_cells":63194,"ref_sat":4,"sensors":"N20","quality_flag":0,"excluded_from_baseline":false},
  {"month":"2026-08-01","n_eq":354788,"f_eq":16153211,"n_terra":138895,"n_aqua":354788,"n_snpp":0,"n_n20":0,"n_n21":0,"frp_terra":7062951.5,"frp_aqua":16153211,"n_cells":31150,"ref_sat":2,"sensors":"Aqua (solo MODIS / deriva)","quality_flag":6,"excluded_from_baseline":true}
]
```

**`sat_month_quality`** (4 filas de muestra):

```json
[
  {"month":"2012-03-01","sat_code":3,"days_in_range":31,"days_missing":1,"days_caida":2,"days_parcial":2,"days_catalog":0,"days_minutes_low":4,"days_affected":4,"complete":false},
  {"month":"2023-07-01","sat_code":4,"days_in_range":31,"days_missing":4,"days_caida":0,"days_parcial":0,"days_catalog":0,"days_minutes_low":4,"days_affected":4,"complete":false},
  {"month":"2024-07-01","sat_code":3,"days_in_range":31,"days_missing":10,"days_caida":3,"days_parcial":0,"days_catalog":0,"days_minutes_low":13,"days_affected":13,"complete":false},
  {"month":"2024-08-01","sat_code":4,"days_in_range":31,"days_missing":0,"days_caida":0,"days_parcial":0,"days_catalog":0,"days_minutes_low":0,"days_affected":0,"complete":true}
]
```

**`sat_day_effort`** (4 filas de muestra; `lat_band = -999` es el total global):

```json
[
  {"obs_date":"2024-08-15","sat_code":4,"lat_band":-999,"n_minutes":509,"n_det":106951},
  {"obs_date":"2024-08-15","sat_code":4,"lat_band":-30,"n_minutes":51,"n_det":8229},
  {"obs_date":"2024-08-15","sat_code":4,"lat_band":-20,"n_minutes":57,"n_det":59273},
  {"obs_date":"2024-08-15","sat_code":4,"lat_band":-10,"n_minutes":55,"n_det":20891}
]
```

**`calibration_coef`** (4 filas de muestra):

```json
[
  {"method_version":"v0.2","sat_code":3,"lat_band":-30,"sector":1,"season":3,"alpha":0.21923941666928415,"gamma":0.9162603544758986,"confidence":"alta","fit_level":"lat_band+sector+season"},
  {"method_version":"v0.2","sat_code":4,"lat_band":-30,"sector":1,"season":3,"alpha":0.2198337385436799,"gamma":0.9148585292532562,"confidence":"alta","fit_level":"lat_band+sector+season"},
  {"method_version":"v0.2","sat_code":4,"lat_band":70,"sector":2,"season":1,"alpha":0.18381734722178686,"gamma":0.9847482733277452,"confidence":"baja","fit_level":"season"},
  {"method_version":"v0.2","sat_code":5,"lat_band":-30,"sector":1,"season":3,"alpha":0.2282121775811091,"gamma":0.8180381862169753,"confidence":"alta","fit_level":"lat_band+sector+season"}
]
```

**`known_gap`** (completa):

```json
[
  {"gap_id":1,"sat_code":2,"date_from":"2020-08-16","date_to":"2020-09-02","gap_kind":"falla_documentada","source":"nasa","note":"Falla de Aqua: cobertura muy limitada (guía MODIS)"},
  {"gap_id":2,"sat_code":2,"date_from":"2022-04-01","date_to":"2022-04-16","gap_kind":"sin_datos","source":"fase0","note":"16 días sin datos de Aqua"},
  {"gap_id":3,"sat_code":1,"date_from":"2016-02-19","date_to":"2016-02-27","gap_kind":"sin_datos","source":"fase0","note":"9 días sin datos de Terra"},
  {"gap_id":4,"sat_code":1,"date_from":"2022-10-10","date_to":"2022-10-23","gap_kind":"sin_datos","source":"fase0","note":"Terra: caída el 10-oct y sin datos hasta el 23-oct"}
]
```

**`dim_satellite`** (completa):

```json
[
  {"sat_code":1,"raw_satellite":"Terra","firms_code":"T","sensor":"MODIS","orbit_family":"manana","nominal_pixel_km":1,"raw_table":"modis","first_date":"2012-01-01","last_date":"2026-08-31","scan_c1":1,"scan_c2":1.2,"scan_c3":1.5,"scan_c4":2},
  {"sat_code":2,"raw_satellite":"Aqua","firms_code":"A","sensor":"MODIS","orbit_family":"tarde","nominal_pixel_km":1,"raw_table":"modis","first_date":"2012-01-01","last_date":"2026-08-31","scan_c1":1,"scan_c2":1.2,"scan_c3":1.5,"scan_c4":2},
  {"sat_code":3,"raw_satellite":"SNPP","firms_code":"N","sensor":"VIIRS","orbit_family":"tarde","nominal_pixel_km":0.375,"raw_table":"viirs_suomi","first_date":"2012-01-20","last_date":"2026-07-31","scan_c1":0.4,"scan_c2":0.45,"scan_c3":0.5,"scan_c4":0.6},
  {"sat_code":4,"raw_satellite":"N20","firms_code":"N20","sensor":"VIIRS","orbit_family":"tarde","nominal_pixel_km":0.375,"raw_table":"viirs_j1","first_date":"2018-04-01","last_date":"2026-07-31","scan_c1":0.4,"scan_c2":0.45,"scan_c3":0.5,"scan_c4":0.6},
  {"sat_code":5,"raw_satellite":"N21","firms_code":"N21","sensor":"VIIRS","orbit_family":"tarde","nominal_pixel_km":0.375,"raw_table":"viirs_j2","first_date":"2023-03-01","last_date":"2026-07-31","scan_c1":0.4,"scan_c2":0.45,"scan_c3":0.5,"scan_c4":0.6}
]
```

**`quality_bits`** (completa). Es el mapa de bits de `quality_flag`:

```json
[
  {"bit":0,"value":1,"name":"viirs_parcial","scope":"mes","excludes_baseline":true,"in_use":true,"description":"Ene-2012: S-NPP empieza el 20-ene; mes parcial sin corregir"},
  {"bit":1,"value":2,"name":"ultimo_mes_standard","scope":"mes","excludes_baseline":false,"in_use":true,"description":"Último mes standard disponible del sensor de referencia (posibles reprocesos)"},
  {"bit":2,"value":4,"name":"solo_modis_deriva","scope":"mes","excludes_baseline":true,"in_use":true,"description":"Ago-2026: n_eq = N_Aqua directo, sin VIIRS; tiende a subestimar ~10 % por la deriva de Aqua"},
  {"bit":3,"value":8,"name":"ref_incompleta_huecos","scope":"mes","excludes_baseline":true,"in_use":true,"description":"Referencia incompleta (>= 3 días afectados) con días faltantes o del catálogo de huecos"},
  {"bit":4,"value":16,"name":"ref_incompleta_caidas","scope":"mes","excludes_baseline":true,"in_use":true,"description":"Referencia incompleta (>= 3 días afectados) con caídas (< 30 %) o minutos de adquisición bajos"},
  {"bit":5,"value":32,"name":"caida_simultanea","scope":"mes","excludes_baseline":false,"in_use":false,"description":"Caída en >= 2 satélites el mismo día: definido, hoy no marca ningún mes (máximo 4 días parciales simultáneos en un mes)"},
  {"bit":6,"value":64,"name":"referencia_respaldo","scope":"mes","excludes_baseline":false,"in_use":true,"description":"Se usó el siguiente satélite de la cadena porque la referencia estaba incompleta (jul-2023: NOAA-21)"},
  {"bit":7,"value":128,"name":"calibracion_baja_conf","scope":"fila","excludes_baseline":false,"in_use":true,"description":"Coeficiente de confianza baja (banda extrema agrupada con su vecina, o respaldo por estación/global): valor absoluto poco confiable; la anomalía por percentil no se afecta por un sesgo constante"}
]
```

**`dataset_metadata`** (completa):

```json
[
  {"key":"aqua_over_harmonized_2026","value":"0.90","description":"Razón Aqua / serie armonizada en ene–jul 2026 (0,9006): ago-2026 (Aqua directo) tiende a subestimar ~10 %"},
  {"key":"baseline_min_years","value":"13","description":"Años mínimos de línea base leave-one-out por mes calendario (excluye bits 0, 2, 3 y 4)"},
  {"key":"built_at","value":"2026-11-15 16:15 -03","description":"Fecha de construcción"},
  {"key":"complete_month_rule","value":"dias_afectados < 3","description":"Día afectado = faltante, caída (< 30 % de la mediana ±15 días), dentro del catálogo de huecos o con minutos bajos. Los parciales (30–60 %) con minutos normales no cuentan. Umbral conservador: los datos separan 1 de 4 días, no hay meses con 2 o 3"},
  {"key":"low_confidence_bands","value":"-60, 70 (y bandas polares sin datos)","description":"Toman el factor de su grupo vecino (-90..-50 y 60..90) y llevan el bit 7: valores absolutos poco confiables; la anomalía por percentil no se afecta por un sesgo constante"},
  {"key":"method_version","value":"v0.2","description":"Versión del método de armonización de cell_month"},
  {"key":"min_focos_calibracion","value":"2000","description":"Mínimo de focos (de cada satélite) para usar un nivel de la jerarquía"},
  {"key":"minutes_low_threshold","value":"0.6","description":"Minutos de adquisición distintos < 60 % de la mediana de ±15 días del mismo satélite"},
  {"key":"period","value":"2012-01..2026-08","description":"Cobertura mensual de cell_month"},
  {"key":"previous_version_table","value":"harmonized.cell_month_v01","description":"v0.1 conservada hasta que el usuario la dé por cerrada"},
  {"key":"raw_rows","value":"588784736","description":"Filas crudas (archive) procesadas; 610.870.539 cargadas menos 22.085.803 NRT eliminadas"},
  {"key":"reference_switch","value":"2020-01","description":"Cambio de referencia S-NPP → NOAA-20: fecha que minimiza el salto entre 63 candidatas (oct-2018..dic-2023); evidencia independiente: Aqua/armonizada entre 0,98 y 1,03 hasta 2025"},
  {"key":"regionalization","value":"banda 10° × sector continental × estación","description":"Sectores por longitud del centro de celda: 1 Américas (< -30°), 2 Europa/África (-30° a 60°), 3 Asia/Oceanía (>= 60°); respaldo jerárquico banda → grupo de bandas extremas → estación → global"},
  {"key":"ui_warning_2026_08","value":"Ago-2026 usa solo MODIS-Aqua, que por su deriva orbital detecta ~10 % menos que la serie armonizada; el valor tiende a subestimar.","description":"Texto sugerido para la interfaz"},
  {"key":"unit","value":"equivalente Aqua 2012–2020","description":"n_eq en focos y f_eq en MW equivalentes a Aqua, definidos por la calibración 2012-02..2020-12 (Aqua cerca de su hora nominal)"}
]
```

### 8.3 Tabla de calidad mensual completa (`reference_plan`, 176 meses)

El listado completo está en `docs/CONTRATO_DATOS_WEB.md`, sección 8.3 (se omitió en el mensaje por longitud).

- Son 176 objetos `{"month","quality_flag","excluded_from_baseline","ref_sat","sensors","days_affected"}`.
- Todos los meses tienen `quality_flag = 0` salvo:
  - 2012-01 (1, excluido);
  - 2012-03 (24, excluido, `days_affected` 4);
  - 2023-07 (64, `ref_sat` 5, `"N21 (respaldo de N20)"`);
  - 2026-07 (2);
  - 2026-08 (6, excluido, `ref_sat` 2, `"Aqua (solo MODIS / deriva)"`).
- `ref_sat` es 3 hasta 2019-12 y 4 desde 2020-01, salvo esos casos.
- Tienen `days_affected` distinto de 0, sin exclusión: 2012-06 (1), 2023-09 (1), 2023-10 (1) y 2024-02 (2).
- **Nota:** en 2023-07, `days_affected = 0` corresponde al satélite usado (NOAA-21). Los 4 días afectados de NOAA-20 están en `sat_month_quality` (`month = '2023-07-01'`, `sat_code = 4`).

---

## 9. Notas de edición (no provienen de Claude Code)

1. **Partes ausentes del texto recibido:** la sección 1 (DDL completo y compatibilidad con PostgreSQL 18), la sección 2 (explicación del mapa de bits; el mapa completo está en 8.2) y el código Python de `bbox_to_ranges`, `polygon_to_ranges` y `area_region_km2`. La fuente es `docs/CONTRATO_DATOS_WEB.md`.
2. **Convención de grilla (3.1):** el texto recibido no la enunciaba. La deduje de los casos de prueba y de la consulta 6b, y la verifiqué en Python contra los 5 casos de prueba (centro y área coinciden), contra el bbox de Sudamérica (276 rangos, 52.992 celdas, 35.840.143,5 km²) y contra el de Ecuador (40 rangos, 1.600 celdas, 1.234.862,4 km²).
3. **Código de la anomalía:** el texto recibido tenía líneas fusionadas y partidas; reconstruí la sintaxis sin cambiar la lógica y comprobé que ejecuta. Los valores de la prueba que cita Claude Code (percentil 0,9167, z 1,33) no los pude reproducir porque no se incluyeron sus datos de entrada.
4. **Posible inconsistencia a confirmar con Claude Code (rangos y área):** la consulta 6b exige "rangos de una sola fila", pero el caso "Polo norte recortado" devuelve **1 rango que abarca 40 filas** (57.600 celdas). Aplicar la fórmula SQL de 6b a ese rango daría ≈ 7,63 M km² en vez de los 3,87 M km² correctos, porque usaría el área de la celda de la primera fila para todas. El backend debe dividir los rangos por fila antes de calcular el área, o usar la función Python, que sí da el valor correcto.
5. **Coeficientes de muestra:** en las filas mostradas de `calibration_coef`, α ≈ 0,18–0,23 y γ ≈ 0,82–0,98. Son valores de unos pocos estratos, no un resultado general.
