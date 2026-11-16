# Contrato de datos web: base liviana `wildfire-armonizado` (`harmonized.cell_month`, v0.2)

**Fecha:** 15-nov-2026 · **Versión de datos:** `method_version = 'v0.2'` · **Origen medido:** `PostgreSQL 18.6 on x86_64-windows, compiled by msvc-19.44.35228, 64-bit`
**Archivo a restaurar:** `wildfire_armonizado.dump` (pg_dump formato custom, 289,5 MB; contiene solo el esquema `harmonized`, sin tablas `*_v01`).
Todo lo de este documento se obtuvo con **consultas de solo lectura** sobre la base local (`default_transaction_read_only = on`). Los tiempos son de la máquina de origen (Ryzen 5 7535HS, 15 GB RAM, SSD USB, configuración por defecto de PostgreSQL).

## 0. Estado y puntos sujetos a cambio

- **v0.2 cerrada y `.dump` reexportado** el 15-nov-2026 16:17 (`D:\Agustin\wildfire_nasa_export\wildfire_armonizado.dump`). Verificado restaurándolo en una base vacía: 11 tablas, `cell_month` con 9.588.557 filas, 1.707 MB restaurado.
- **`DOCUMENTACION_TABLA_ARMONIZADA.md` no existe en este repositorio** (rama `armonizacion-datos`). Este contrato se basa en la base real; si ese documento dice algo distinto, prevalece lo medido acá.
- **Sujeto a cambio:**
  1. **Valores (no esquema).** Habrá una versión nueva de la base armonizada; cambiarán los valores y `method_version`, pero se mantiene el esquema de `cell_month` (columnas, tipos y clave).
  2. **`dataset_metadata.low_confidence_bands`** dice "-60, 70 (y bandas polares sin datos)" y está **incompleto**. La regla exacta es la de la sección 2.3; se corregirá en la próxima versión. Usen la regla de este contrato o el bit 7.
  3. **Tablas que no existen hoy:** `block_month` (1°), `cell_climatology` y la tabla de grilla `grid_cell` **no están en la base web**. La geometría se calcula con las fórmulas de la sección 3 y el 1° se agrega al vuelo (sección 6c).
  4. **Restos cosméticos del dump:** una secuencia huérfana `harmonized.harmonization_log_log_id_seq` y nombres de restricciones `NOT NULL` con sufijo `_v02`. No afectan.
  5. En la base local siguen las tablas `*_v01` hasta que el responsable cierre la v0.1; **no están en el `.dump`**.

## 1. DDL real y restauración

### 1.1 DDL exacto (salida de `pg_dump --schema-only -n harmonized`, sin `*_v01`)

```sql
CREATE SCHEMA harmonized;

CREATE TABLE harmonized.cell_month (
    month date CONSTRAINT cell_month_v02_month_not_null NOT NULL,
    cell_id integer CONSTRAINT cell_month_v02_cell_id_not_null NOT NULL,
    lat_center real,
    lon_center real,
    cell_area_km2 real,
    n_eq real,
    f_eq real,
    ref_sat smallint,
    sensors text,
    n_terra integer,
    n_aqua integer,
    n_snpp integer,
    n_n20 integer,
    n_n21 integer,
    frp_terra real,
    frp_aqua real,
    frp_snpp real,
    frp_n20 real,
    frp_n21 real,
    quality_flag smallint,
    method_version text
);
ALTER TABLE ONLY harmonized.cell_month ADD CONSTRAINT cell_month_pkey PRIMARY KEY (cell_id, month);

CREATE TABLE harmonized.map_month (
    month date,
    cell_id integer,
    n_eq real,
    f_eq real
);
CREATE INDEX map_month_month_brin ON harmonized.map_month USING brin (month);

CREATE TABLE harmonized.global_month (
    month date NOT NULL,
    n_eq double precision,
    f_eq double precision,
    n_terra bigint,
    n_aqua bigint,
    n_snpp bigint,
    n_n20 bigint,
    n_n21 bigint,
    frp_terra double precision,
    frp_aqua double precision,
    n_cells bigint,
    ref_sat smallint,
    sensors text,
    quality_flag smallint,
    excluded_from_baseline boolean
);
ALTER TABLE ONLY harmonized.global_month ADD CONSTRAINT global_month_pkey PRIMARY KEY (month);

CREATE TABLE harmonized.reference_plan (
    month date CONSTRAINT reference_plan_v02_month_not_null NOT NULL,
    preferred_sat smallint CONSTRAINT reference_plan_v02_preferred_sat_not_null NOT NULL,
    ref_sat smallint CONSTRAINT reference_plan_v02_ref_sat_not_null NOT NULL,
    days_affected integer CONSTRAINT reference_plan_v02_days_affected_not_null NOT NULL,
    days_missing integer CONSTRAINT reference_plan_v02_days_missing_not_null NOT NULL,
    days_caida integer CONSTRAINT reference_plan_v02_days_caida_not_null NOT NULL,
    quality_flag smallint CONSTRAINT reference_plan_v02_quality_flag_not_null NOT NULL,
    excluded_from_baseline boolean CONSTRAINT reference_plan_v02_excluded_from_baseline_not_null NOT NULL,
    sensors text CONSTRAINT reference_plan_v02_sensors_not_null NOT NULL
);
ALTER TABLE ONLY harmonized.reference_plan ADD CONSTRAINT reference_plan_pkey PRIMARY KEY (month);

CREATE TABLE harmonized.sat_month_quality (
    month date CONSTRAINT sat_month_quality_v02_month_not_null NOT NULL,
    sat_code smallint CONSTRAINT sat_month_quality_v02_sat_code_not_null NOT NULL,
    days_in_range integer CONSTRAINT sat_month_quality_v02_days_in_range_not_null NOT NULL,
    days_missing integer CONSTRAINT sat_month_quality_v02_days_missing_not_null NOT NULL,
    days_caida integer CONSTRAINT sat_month_quality_v02_days_caida_not_null NOT NULL,
    days_parcial integer CONSTRAINT sat_month_quality_v02_days_parcial_not_null NOT NULL,
    days_catalog integer CONSTRAINT sat_month_quality_v02_days_catalog_not_null NOT NULL,
    days_minutes_low integer CONSTRAINT sat_month_quality_v02_days_minutes_low_not_null NOT NULL,
    days_affected integer CONSTRAINT sat_month_quality_v02_days_affected_not_null NOT NULL,
    complete boolean CONSTRAINT sat_month_quality_v02_complete_not_null NOT NULL
);
ALTER TABLE ONLY harmonized.sat_month_quality ADD CONSTRAINT sat_month_quality_pkey PRIMARY KEY (month, sat_code);

CREATE TABLE harmonized.sat_day_effort (
    obs_date date NOT NULL,
    sat_code smallint NOT NULL,
    lat_band smallint NOT NULL,
    n_minutes integer NOT NULL,
    n_det integer NOT NULL
);
ALTER TABLE ONLY harmonized.sat_day_effort ADD CONSTRAINT sat_day_effort_pkey PRIMARY KEY (obs_date, sat_code, lat_band);

CREATE TABLE harmonized.known_gap (
    gap_id integer NOT NULL,
    sat_code smallint NOT NULL,
    date_from date NOT NULL,
    date_to date NOT NULL,
    gap_kind text NOT NULL,
    source text NOT NULL,
    note text,
    CONSTRAINT known_gap_gap_kind_check CHECK ((gap_kind = ANY (ARRAY['sin_datos'::text, 'caida'::text, 'falla_documentada'::text]))),
    CONSTRAINT known_gap_source_check CHECK ((source = ANY (ARRAY['nasa'::text, 'fase0'::text, 'fase2_empirico'::text])))
);
CREATE SEQUENCE harmonized.known_gap_gap_id_seq AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
ALTER SEQUENCE harmonized.known_gap_gap_id_seq OWNED BY harmonized.known_gap.gap_id;
ALTER TABLE ONLY harmonized.known_gap ALTER COLUMN gap_id SET DEFAULT nextval('harmonized.known_gap_gap_id_seq'::regclass);
ALTER TABLE ONLY harmonized.known_gap ADD CONSTRAINT known_gap_pkey PRIMARY KEY (gap_id);
ALTER TABLE ONLY harmonized.known_gap ADD CONSTRAINT known_gap_sat_code_date_from_date_to_source_key UNIQUE (sat_code, date_from, date_to, source);
ALTER TABLE ONLY harmonized.known_gap ADD CONSTRAINT known_gap_sat_code_fkey FOREIGN KEY (sat_code) REFERENCES harmonized.dim_satellite(sat_code);

CREATE TABLE harmonized.dim_satellite (
    sat_code smallint NOT NULL,
    raw_satellite text NOT NULL,
    firms_code text NOT NULL,
    sensor text NOT NULL,
    orbit_family text NOT NULL,
    nominal_pixel_km real NOT NULL,
    raw_table text NOT NULL,
    first_date date NOT NULL,
    last_date date NOT NULL,
    scan_c1 real NOT NULL,
    scan_c2 real NOT NULL,
    scan_c3 real NOT NULL,
    scan_c4 real NOT NULL,
    CONSTRAINT dim_satellite_orbit_family_check CHECK ((orbit_family = ANY (ARRAY['manana'::text, 'tarde'::text]))),
    CONSTRAINT dim_satellite_sensor_check CHECK ((sensor = ANY (ARRAY['MODIS'::text, 'VIIRS'::text])))
);
ALTER TABLE ONLY harmonized.dim_satellite ADD CONSTRAINT dim_satellite_pkey PRIMARY KEY (sat_code);
ALTER TABLE ONLY harmonized.dim_satellite ADD CONSTRAINT dim_satellite_raw_satellite_key UNIQUE (raw_satellite);

CREATE TABLE harmonized.calibration_coef (
    method_version text CONSTRAINT calibration_coef_v02_method_version_not_null NOT NULL,
    sat_code smallint CONSTRAINT calibration_coef_v02_sat_code_not_null NOT NULL,
    lat_band smallint CONSTRAINT calibration_coef_v02_lat_band_not_null NOT NULL,
    sector smallint CONSTRAINT calibration_coef_v02_sector_not_null NOT NULL,
    season smallint CONSTRAINT calibration_coef_v02_season_not_null NOT NULL,
    alpha double precision CONSTRAINT calibration_coef_v02_alpha_not_null NOT NULL,
    gamma double precision CONSTRAINT calibration_coef_v02_gamma_not_null NOT NULL,
    confidence text CONSTRAINT calibration_coef_v02_confidence_not_null NOT NULL,
    fit_level text CONSTRAINT calibration_coef_v02_fit_level_not_null NOT NULL,
    CONSTRAINT calibration_coef_v02_confidence_check CHECK ((confidence = ANY (ARRAY['alta'::text, 'baja'::text])))
);
ALTER TABLE ONLY harmonized.calibration_coef ADD CONSTRAINT calibration_coef_pkey PRIMARY KEY (method_version, sat_code, lat_band, sector, season);

CREATE TABLE harmonized.quality_bits (
    "bit" smallint NOT NULL,
    value smallint NOT NULL,
    name text NOT NULL,
    scope text NOT NULL,
    excludes_baseline boolean NOT NULL,
    in_use boolean NOT NULL,
    description text NOT NULL
);
ALTER TABLE ONLY harmonized.quality_bits ADD CONSTRAINT quality_bits_pkey PRIMARY KEY ("bit");

CREATE TABLE harmonized.dataset_metadata (
    key text NOT NULL,
    value text NOT NULL,
    description text NOT NULL
);
ALTER TABLE ONLY harmonized.dataset_metadata ADD CONSTRAINT dataset_metadata_pkey PRIMARY KEY (key);

-- Resto cosmético incluido en el dump (sin tabla asociada):
CREATE SEQUENCE harmonized.harmonization_log_log_id_seq START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
```

**Compatibilidad:**
- En `cell_month` solo `month` y `cell_id` son `NOT NULL` a nivel de esquema, pero **ninguna columna tiene `NULL` en los datos** (verificado en las 9.588.557 filas).
- No hay `DEFAULT` salvo `known_gap.gap_id`.
- Índices que existen: las claves primarias listadas y el BRIN `map_month_month_brin`. **No hay índice por `month` en `cell_month`**; es intencional, porque uno `(month, cell_id)` hace que el planificador empeore el calendario entre 1,2× y 2×.
- `map_month` no tiene clave primaria: su unicidad `(month, cell_id)` está garantizada por construcción, porque es copia de `cell_month`.

### 1.2 Restauración en PostgreSQL 18

```sql
-- psql como superusuario
CREATE DATABASE "wildfire-armonizado" TEMPLATE template0 ENCODING 'UTF8';
```

```bash
pg_restore -h <host> -p <puerto> -U postgres -d wildfire-armonizado --no-owner --no-privileges -j 4 wildfire_armonizado.dump
psql -h <host> -p <puerto> -U postgres -d wildfire-armonizado -c "VACUUM ANALYZE"
```

El `VACUUM ANALYZE` posterior es obligatorio: deja estadísticas del planificador y el mapa de visibilidad.

## 2. `quality_flag`

### 2.1 Diccionario bit a bit (tabla `harmonized.quality_bits`)

| Bit | Valor | Constante | Nivel | Excluye de la línea base | En uso | Significado |
|---:|---:|---|---|:---:|:---:|---|
| 0 | 1 | `QF_VIIRS_PARCIAL` | mes | sí | sí | Ene-2012: S-NPP empieza el 20-ene; mes parcial sin corregir |
| 1 | 2 | `QF_ULTIMO_MES_STANDARD` | mes | no | sí | Último mes standard del sensor de referencia (jul-2026 VIIRS, ago-2026 MODIS); posibles reprocesos |
| 2 | 4 | `QF_SOLO_MODIS_DERIVA` | mes | sí | sí | Ago-2026: `n_eq = N_Aqua` directo, sin VIIRS; tiende a subestimar ~10 % por la deriva de Aqua |
| 3 | 8 | `QF_REF_INCOMPLETA_HUECOS` | mes | sí | sí | Referencia incompleta (≥ 3 días afectados) con días faltantes o del catálogo de huecos |
| 4 | 16 | `QF_REF_INCOMPLETA_CAIDAS` | mes | sí | sí | Referencia incompleta (≥ 3 días afectados) con caídas (< 30 %) o minutos de adquisición bajos |
| 5 | 32 | `QF_CAIDA_SIMULTANEA` | mes | no | **no** | Definido; hoy no marca ningún mes |
| 6 | 64 | `QF_REFERENCIA_RESPALDO` | mes | no | sí | Se usó el siguiente satélite de la cadena (jul-2023: NOAA-21 en lugar de NOAA-20) |
| 7 | 128 | `QF_CALIBRACION_BAJA_CONF` | **celda** | no | sí | Coeficiente de confianza baja: valor absoluto poco confiable; la anomalía por percentil no se afecta por un sesgo constante |

Valores presentes en `cell_month.quality_flag` (combinaciones reales): 0, 1, 2, 6, 24, 64, 128, 129, 130, 152, 192.

> **Cambio de significado del bit 7 (v0.1 → v0.2).** En la v0.1 (`cell_month_v01`) el bit 7 significaba **"calibración provisional"** y estaba prendido en **todas** las filas. En la v0.2 significa **"calibración de confianza baja"** y está prendido solo en **21.796 filas (0,23 %)**, que suman el 0,06 % de `n_eq`. Cualquier código que suponga que el bit 7 está siempre prendido, o que lo use como marca de "dato provisional", debe actualizarse: leer el significado desde `quality_bits`.
> **Bits 3 y 4 en la v0.2:** solo se marcan cuando la referencia del mes está incompleta (≥ 3 días afectados). En la v0.1 se marcaban con ≥ 5 días de hueco o caída.

### 2.2 Banderas de nivel mes y completado de ceros

- **Tabla:** `harmonized.reference_plan`. Tiene **una fila por cada mes de 2012-01 a 2026-08 (176)**. Columnas: `month`, `quality_flag` (solo bits de mes: 0, 1, 2, 3, 4, 6), `excluded_from_baseline`, `ref_sat`, `sensors`, `days_affected`, `days_missing`, `days_caida`, `preferred_sat`.
- `harmonized.global_month` repite `quality_flag` y `excluded_from_baseline` por mes.
- **Completar ceros:** usar `reference_plan` (o `generate_series`) como columna vertebral y `LEFT JOIN` con la suma regional. Las banderas de mes salen de `reference_plan`, así que **no se pierden aunque la región no tenga filas ese mes**. El bit 7 (nivel celda) se agrega con `bit_or` sobre las celdas de la región (sección 6a).

```python
EXCLUDE_BASELINE_MASK = 29          # bits 0, 2, 3, 4 = 1 | 4 | 8 | 16
MIN_VALID_YEARS = 10
```

Cantidad de años válidos (meses con `quality_flag & 29 = 0`) por mes calendario en 2012-01..2026-08 [medido]:

| Mes | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Años válidos | 14 | 15 | 14 | 15 | 15 | 15 | 15 | 14 | 14 | 14 | 14 | 14 |
| Excluidos | 2012-01 | — | 2012-03 | — | — | — | — | 2026-08 | — | — | — | — |
| Base leave-one-out si el mes evaluado es válido | 13 | 14 | 13 | 14 | 14 | 14 | 14 | 13 | 13 | 13 | 13 | 13 |

La máscara coincide con `reference_plan.excluded_from_baseline` en los 176 meses (verificado).

### 2.3 Baja confianza (bit 7): cómo detectarla en el backend

La regla exacta, verificada contra las 9.588.557 filas **sin discrepancias** (21.796 filas con bit 7), es:

```python
def es_baja_confianza(lat_center: float, month: int, ref_sat: int) -> bool:
    """Bit 7 de cell_month. lat_band = límite inferior de la banda de 10°; season: 1 DEF, 2 MAM, 3 JJA, 4 SON."""
    if ref_sat == 2:                      # ago-2026 (Aqua directo): no usa coeficientes
        return False
    lat_band = int(math.floor(lat_center / 10.0)) * 10
    season = 1 if month in (12, 1, 2) else 2 if month in (3, 4, 5) else 3 if month in (6, 7, 8) else 4
    return lat_band <= -60 or lat_band >= 70 or (lat_band == -50 and season == 3) or (lat_band == 60 and season == 1)
```

- **Aviso por AOI:** si la región toca alguna fila de celdas con `lat_center < -50` o `lat_center >= 70`, avisar siempre. Si toca −50° a −40° (avisar en jun–ago) o 60° a 70° (avisar en dic–feb), avisar en esos meses.
- **Con datos:** el calendario de la sección 6a devuelve `bit_or(quality_flag) & 128` por mes.
- **Fuente:** `harmonized.calibration_coef` (`confidence = 'baja'`), que da la misma clasificación por `(lat_band, sector, season)`.

## 3. Grilla `cell_id` ↔ (lat, lon)

- **Celda:** 0,25° × 0,25°. **720 filas × 1440 columnas**. `cell_id = fila * 1440 + columna` (0 a 1.036.799).
- **Fila 0 = SUR:** latitudes de −90,00 a −89,75, centro −89,875. La fila 719 es la última al norte.
- **Columna 0 = −180,00 a −179,75**, centro **−179,875**. La columna 1439 tiene centro 179,875.
- **Bordes (asignación de un punto):** `fila = floor((lat + 90) / 0,25)` y `col = floor((lon + 180) / 0,25)`. El borde inferior y el izquierdo pertenecen a la celda; `lat = 90` va a la fila 719; `lon = 180` va a la columna 0 (mismo meridiano que −180).
- **Selección de región:** una celda pertenece a un rectángulo o polígono si su **CENTRO** cae dentro, con bordes inclusive.
- **Área:** `R² · Δλ · (sin φ2 − sin φ1)`, con R = 6371,0 km y Δλ = 0,25° en radianes. **No hay tabla de grilla en la base web**: `cell_month.cell_area_km2` trae el área solo de las celdas con filas.

```python
import math

R_KM, D, NROW, NCOL, EPS = 6371.0, 0.25, 720, 1440, 1e-9

def cell_id_from_latlon(lat: float, lon: float) -> int:
    row = min(max(int(math.floor((lat + 90.0) / D)), 0), NROW - 1)
    col = int(math.floor((lon + 180.0) / D)) % NCOL
    return row * NCOL + col

def cell_center(cell_id: int) -> tuple[float, float, float]:
    """(b) cell_id -> (lat_center, lon_center, cell_area_km2)."""
    row, col = divmod(int(cell_id), NCOL)
    lat_c = -90.0 + (row + 0.5) * D
    lon_c = -180.0 + (col + 0.5) * D
    area = R_KM ** 2 * math.radians(D) * (math.sin(math.radians(-90.0 + (row + 1) * D)) - math.sin(math.radians(-90.0 + row * D)))
    return lat_c, lon_c, area

def _rows(min_lat, max_lat):
    r0 = max(0, math.ceil((min_lat + 90.0) / D - 0.5 - EPS))
    r1 = min(NROW - 1, math.floor((max_lat + 90.0) / D - 0.5 + EPS))
    return r0, r1

def _cols(lo, hi):
    c0 = max(0, math.ceil((lo + 180.0) / D - 0.5 - EPS))
    c1 = min(NCOL - 1, math.floor((hi + 180.0) / D - 0.5 + EPS))
    return c0, c1

def bbox_to_ranges(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> list[tuple[int, int]]:
    """(a) bbox -> [(cell_id_inicio, cell_id_fin)], celdas cuyo centro cae en el bbox (bordes inclusive).
    Cruce del antimeridiano: min_lon > max_lon. Recorta latitudes fuera de [-90, 90].
    Une rangos contiguos (un bbox de ancho completo queda en un solo rango)."""
    r0, r1 = _rows(min_lat, max_lat)
    if r0 > r1:
        return []
    spans = [_cols(min_lon, max_lon)] if min_lon <= max_lon else [_cols(min_lon, 180.0), _cols(-180.0, max_lon)]
    out: list[tuple[int, int]] = []
    for r in range(r0, r1 + 1):
        for c0, c1 in spans:
            if c0 > c1:
                continue
            a, b = r * NCOL + c0, r * NCOL + c1
            if out and out[-1][1] + 1 == a:
                out[-1] = (out[-1][0], b)
            else:
                out.append((a, b))
    return out

def _inside(lon, lat, ring):
    ins, n = False, len(ring)
    for i in range(n):
        x1, y1 = ring[i]; x2, y2 = ring[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            if lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
                ins = not ins
    return ins

def polygon_to_ranges(ring: list[tuple[float, float]]) -> list[tuple[int, int]]:
    """Polígono simple [(lon, lat), ...] sin cruce del antimeridiano -> rangos por centro de celda."""
    lons = [p[0] for p in ring]; lats = [p[1] for p in ring]
    r0, r1 = _rows(min(lats), max(lats)); c0, c1 = _cols(min(lons), max(lons))
    out: list[tuple[int, int]] = []
    for r in range(r0, r1 + 1):
        lat, start = -90.0 + (r + 0.5) * D, None
        for c in range(c0, c1 + 2):
            ok = c <= c1 and _inside(-180.0 + (c + 0.5) * D, lat, ring)
            if ok and start is None:
                start = c
            if not ok and start is not None:
                a, b = r * NCOL + start, r * NCOL + c - 1
                if out and out[-1][1] + 1 == a:
                    out[-1] = (out[-1][0], b)
                else:
                    out.append((a, b))
                start = None
    return out

def ranges_cell_count(ranges) -> int:
    return sum(b - a + 1 for a, b in ranges)

def area_region_km2(ranges) -> float:
    """Suma el área fila por fila (funciona también con rangos que unen filas completas)."""
    total = 0.0
    for a, b in ranges:
        ra, ca = divmod(a, NCOL); rb, cb = divmod(b, NCOL)
        for r in range(ra, rb + 1):
            c_ini = ca if r == ra else 0
            c_fin = cb if r == rb else NCOL - 1
            total += cell_center(r * NCOL)[2] * (c_fin - c_ini + 1)
    return total
```

**Pruebas verificadas contra PostgreSQL** (valores de `harmonized.cell_month`; el error relativo de área es < 1e-6):

| Caso | `cell_id` | `lat_center` | `lon_center` | `cell_area_km2` (BD) | Python |
|---|---:|---:|---:|---:|---|
| Sudamérica | 373439 | −25,125 | −60,125 | 699,6523 | igual |
| Ecuador | 519200 | 0,125 | 20,125 | 772,767 | igual |
| Latitud alta | 1021366 | 87,375 | −78,375 | 35,391937 | igual |
| Borde antimeridiano | 908639 | 67,625 | 179,875 | 294,16754 | igual |
| Sur extremo | 172334 | −60,125 | 63,625 | 384,92346 | igual |

| bbox `[min_lon, min_lat, max_lon, max_lat]` | Rangos | Celdas | Área (km²) | Filas jul-2024 por rangos | Filas jul-2024 por centro (SQL) |
|---|---:|---:|---:|---:|---:|
| Sudamérica `[-82, -56, -34, 13]` | 276 | 52.992 | 35.840.143,5 | 12.473 | 12.473 |
| Ecuador `[15, -5, 25, 5]` | 40 | 1.600 | 1.234.862,4 | 1.126 | 1.126 |
| Antimeridiano `[170, 60, -170, 72]` | 96 | 3.840 | 1.204.759,7 | 3 | 3 |
| Polo norte recortado `[-180, 80, 180, 95]` | 1 | 57.600 | 3.874.512,7 (= 2πR²(1 − sin 80°)) | 4 | 4 |

Polígono: un rectángulo pasado como polígono devuelve exactamente los mismos rangos que el bbox (10.560 celdas); un triángulo de 10° × 10° devuelve 800 celdas (= área / 0,0625).

**Rangos que abarcan varias filas.** Si el bbox cubre los 360° de longitud, `bbox_to_ranges` une las filas consecutivas en un solo rango; por ejemplo, el polo norte recortado da 1 rango de 40 filas. Es correcto para todo filtro `cell_id BETWEEN r.s AND r.e` (calendario, mapa, CSV), porque los `cell_id` de filas consecutivas son contiguos: en el caso del polo, la consulta por rangos y la consulta por centro de celda devolvieron las mismas 4 filas. Para el área se usa `area_region_km2()` en Python o la consulta corregida de la sección 6b, que recorren fila por fila.

## 4. Dominios y nulabilidad (`cell_month`)

| Columna | Tipo | Nulos | Dominio real |
|---|---|---|---|
| `month` | date | no | Primer día del mes, 2012-01-01 … 2026-08-01 |
| `cell_id` | integer | no | 0 … 1.036.799 |
| `n_eq`, `f_eq` | real | **no** (0 si la referencia no detectó) | ≥ 0; 1.834.329 filas con `n_eq = 0` |
| `ref_sat` | smallint | no | **3** (S-NPP, 2012-01..2019-12), **4** (NOAA-20, 2020-01..2026-07 salvo 2023-07), **5** (NOAA-21, 2023-07), **2** (Aqua, 2026-08) |
| `sensors` | text | no | Exactamente 4 valores: `'SNPP'`, `'N20'`, `'N21 (respaldo de N20)'`, `'Aqua (solo MODIS / deriva)'` |
| `n_terra`, `n_aqua`, `n_snpp`, `n_n20`, `n_n21` | integer | **no** | ≥ 0; **0** si el satélite no operaba (NOAA-20 antes de 2018-04, NOAA-21 antes de 2023-03, VIIRS en 2026-08) o no detectó |
| `frp_terra` … `frp_n21` | real (MW) | **no** | ≥ 0; 0 en los mismos casos |
| `quality_flag` | smallint | no | Sección 2 |
| `method_version` | text | no | `'v0.2'` |
| `lat_center`, `lon_center`, `cell_area_km2` | real | no | Ver sección 3 |

- `n_*` y `frp_*` usan **el mismo filtro**: `type = 0` (vegetación) y sin confianza baja (MODIS `confidence >= 30`; VIIRS `confidence <> 'l'`).
- `n_eq = α · n_ref` y `f_eq = γ · frp_ref`, donde `ref` es el satélite indicado en `ref_sat`. En 2026-08, `n_eq = n_aqua` y `f_eq = frp_aqua`.
- Las sumas regionales conviene hacerlas en `float8`: `sum(n_eq::float8)`.

## 5. Ceros y cobertura

- **Ausencia de fila = 0** en todas las columnas de conteo y FRP para esa celda y mes. Hay fila si **cualquier** satélite detectó **algo** en la celda, de cualquier tipo o confianza. Por eso existen filas con `n_eq = 0`: por ejemplo, detecciones solo de S-NPP en 2024 (ver la muestra de la sección 8), o solo de `type ≠ 0` o de confianza baja.
- **"0 fuegos reales" vs "sin cobertura":** la información de cobertura es **por mes y satélite, no por celda**.
  - **Hueco de cobertura** del mes: `reference_plan.quality_flag & (8 | 16) <> 0` (referencia incompleta), o `& 4` (solo MODIS). En la v0.2: 2012-03 (bits 3 y 4) y 2026-08 (bit 2).
  - **Mes con respaldo** (cobertura completa con otro satélite): bit 6 (2023-07).
  - **Mes completo** (bits 3, 4 y 2 apagados): un 0 es "0 detecciones tras los filtros", es decir, sin fuego detectable a ese umbral.
  - **Detalle por satélite:** `sat_month_quality` (`days_missing`, `days_caida`, `days_catalog`, `days_minutes_low`, `days_affected`, `complete`). Esto incluye los huecos de S-NPP en 2022–2026, que no afectan la serie porque S-NPP no es la referencia desde 2020.
  - **Detalle espacial opcional:** `sat_day_effort` por banda de 10° (`n_minutes` bajo frente a días vecinos indica pasadas faltantes en esa banda).
  - `known_gap` solo tiene 4 huecos documentados (Aqua 2020-08 y 2022-04; Terra 2016-02 y 2022-10). Los días faltantes de los VIIRS están en `sat_month_quality`.
- **Tope de celdas a 0,25° (no hay tabla de 1°):** **50.000 celdas por consulta de calendario**. Sudamérica (52.992 celdas) tarda 0,7–0,83 s en caliente y 1,1 s en frío. Por encima del tope, rechazar o pedir una región menor. Para el mapa al alejar el zoom, agregar a 1° al vuelo (sección 6c).

## 6. Consultas medidas (SQL exacto + EXPLAIN ANALYZE, BUFFERS; segunda ejecución)

Parámetros: `$1` = arreglo de inicios y `$2` = arreglo de finales de `bbox_to_ranges` / `polygon_to_ranges`. Con psycopg 3 se pasan como `list[int]`. **Forma recomendada:** `CROSS JOIN LATERAL (… OFFSET 0)`. Obliga a una búsqueda por índice por rango; sin ella, el planificador eligió un recorrido completo en un caso medido (4,6 s).

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

Traer siempre los 176 meses: la anomalía necesita la base completa. El rango de fechas del usuario solo filtra lo que se muestra.

| AOI | Celdas | Rangos | Tiempo (`unnest` + JOIN) | Tiempo (`LATERAL … OFFSET 0`) | Buffers |
|---|---:|---:|---:|---:|---|
| Chico (Córdoba `[-65.8,-35,-61.8,-29.5]`) | 352 | 22 | 10,6 ms | — | hit 43, read 356 |
| Mediano (Argentina `[-73.5,-55,-53.5,-22]`) | 10.560 | 132 | 173,8 ms | **119,9 ms** | hit 886, read 5.751 |
| Sudamérica `[-82,-56,-34,13]` | 52.992 | 276 | 829,9 ms | **712,6 ms** | hit 6.968, read 26.038 |

Plan (todas las variantes): `Nested Loop` → `Index Scan using cell_month_pkey on cell_month m`, con `Index Cond: ((cell_id >= r.s) AND (cell_id <= r.e))`, una búsqueda por rango (22, 132 o 276), y `Hash Join` con `reference_plan` (176 filas, `Seq Scan`, 2 buffers).

```sql
-- Variante con generate_series como columna vertebral (equivalente; la medida de la tabla usa esta forma en la columna "unnest + JOIN")
WITH meses AS (SELECT (date '2012-01-01' + make_interval(months => i))::date AS month FROM generate_series(0, 175) i),
reg AS (
  SELECT m.month, sum(m.n_eq) AS n_eq, sum(m.f_eq) AS f_eq, count(*) AS celdas_con_filas, bit_or(m.quality_flag) & 128 AS bit7
    FROM unnest($1::int[], $2::int[]) AS r(s, e)
    JOIN harmonized.cell_month m ON m.cell_id BETWEEN r.s AND r.e
   GROUP BY m.month)
SELECT x.month, coalesce(reg.n_eq, 0) AS n_eq, coalesce(reg.f_eq, 0) AS f_eq, coalesce(reg.celdas_con_filas, 0) AS celdas_con_filas,
       p.quality_flag | coalesce(reg.bit7, 0) AS quality_flag, p.excluded_from_baseline, p.ref_sat, p.sensors
  FROM meses x JOIN harmonized.reference_plan p USING (month) LEFT JOIN reg USING (month)
 ORDER BY x.month;
```

### 6b. `area_region_km2`

```sql
-- Acepta cualquier rango, incluidos los que abarcan varias filas (bbox de 360° de ancho unidos por bbox_to_ranges):
-- recorre fila por fila con generate_series y cuenta solo las columnas del rango dentro de cada fila.
SELECT sum((6371.0 ^ 2) * radians(0.25)
           * (sin(radians(-90 + (f + 1) * 0.25)) - sin(radians(-90 + f * 0.25)))
           * (least(r.e, f * 1440 + 1439) - greatest(r.s, f * 1440) + 1)) AS area_region_km2
  FROM unnest($1::int[], $2::int[]) AS r(s, e)
  CROSS JOIN LATERAL generate_series(r.s / 1440, r.e / 1440) AS f;
```

**Corrección (15-nov-2026).**
- **Qué estaba mal:** la versión anterior de esta consulta multiplicaba el área de la **primera** fila del rango por todas sus celdas. Con un rango que abarca varias filas daba un resultado erróneo: 7.633.686,6 km² en lugar de 3.874.512,7 km² para el polo norte recortado, y 1.747.960,6 km² en lugar de 510.064.471,9 km² para el mundo entero.
- **Dónde se resuelve:** en la consulta. `bbox_to_ranges` puede seguir uniendo filas completas en un solo rango (eso es válido y más eficiente para el calendario, el mapa y el CSV, que filtran con `cell_id BETWEEN r.s AND r.e`). El backend **no** necesita dividir los rangos por fila.

| Caso | Rangos | Python `area_region_km2()` | SQL corregido | SQL anterior |
|---|---:|---:|---:|---:|
| Sudamérica `[-82,-56,-34,13]` | 276 | 35.840.143,5 | 35.840.143,5 | 35.840.143,5 |
| Ecuador `[15,-5,25,5]` | 40 | 1.234.862,4 | 1.234.862,4 | 1.234.862,4 |
| Antimeridiano `[170,60,-170,72]` | 96 | 1.204.759,7 | 1.204.759,7 | 1.204.759,7 |
| Polo norte recortado `[-180,80,180,95]` | 1 (40 filas) | 3.874.512,7 | **3.874.512,7** | 7.633.686,6 ✗ |
| Mundo `[-180,-90,180,90]` | 1 (720 filas) | 510.064.471,9 | **510.064.471,9** (= 4πR²) | 1.747.960,6 ✗ |

Sudamérica con la consulta anterior: 0,23 ms; la corregida recorre como máximo 720 filas por rango, así que su costo es despreciable.

### 6c. Capa de mapa limitada al encuadre visible

```sql
-- 1 mes: map_month (BRIN por mes) + filtro por fila/columna derivado de cell_id. Rectángulo [r0..r1] × [c0..c1]
SELECT m.cell_id, m.n_eq, m.f_eq
  FROM harmonized.map_month m
 WHERE m.month = $1
   AND m.cell_id BETWEEN $2 * 1440 AND $3 * 1440 + 1439          -- $2 = r0, $3 = r1
   AND (m.cell_id / 1440) BETWEEN $2 AND $3
   AND (m.cell_id % 1440) BETWEEN $4 AND $5;                     -- $4 = c0, $5 = c1
-- antimeridiano: reemplazar la última línea por
--   AND ((m.cell_id % 1440) BETWEEN $4 AND 1439 OR (m.cell_id % 1440) BETWEEN 0 AND $5)

-- Varios meses o serie completa: cell_month con LATERAL por rango (índice PK)
SELECT x.cell_id, sum(x.n_eq::float8) AS n_eq, sum(x.f_eq::float8) AS f_eq
  FROM unnest($1::int[], $2::int[]) AS r(s, e)
  CROSS JOIN LATERAL (
    SELECT m.cell_id, m.n_eq, m.f_eq
      FROM harmonized.cell_month m
     WHERE m.cell_id BETWEEN r.s AND r.e AND m.month BETWEEN $3 AND $4
    OFFSET 0) x
 GROUP BY x.cell_id;

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

| Encuadre | Consulta | Tiempo | Celdas/bloques | JSON aprox. (`[id, n_eq, f_eq]`) |
|---|---|---:|---:|---:|
| Argentina | 1 mes (`map_month`, filtro fila/columna) | **6,1 ms** | 2.758 | 57 kB |
| Argentina | 12 meses (`cell_month`, LATERAL) | **51,4 ms** | 4.649 | 97 kB |
| Argentina | Serie completa (`cell_month`, JOIN por rangos) | 167,3 ms | 6.003 | 136 kB |
| Argentina | 1°, 1 mes | 34,9 ms | 343 | 7 kB |
| Argentina | 1°, 12 meses (`map_month`) | 47,4 ms | 415 | 9 kB |
| Sudamérica | 1 mes | **7,9 ms** | 14.997 | 311 kB |
| Sudamérica | 12 meses (LATERAL) | **205,0 ms** | 20.914 | 453 kB |
| Sudamérica | Serie completa (JOIN por rangos) | 946,2 ms | 24.783 | 574 kB |
| Sudamérica | 1°, 1 mes | 32,1 ms | 1.496 | 32 kB |
| Sudamérica | 1°, 12 meses (`map_month`) | 141,3 ms | 1.712 | 39 kB |
| Antimeridiano `[170,60,-170,72]` | 1 mes / 12 meses (LATERAL) | 32,1 ms / 0,4 ms | 1 / 11 | < 1 kB |

**Formas descartadas (medidas):**
- `map_month` unida a `unnest` de rangos: 671 ms (Argentina) y 1.954 ms (Sudamérica) para 1 mes, porque recorre el mes y compara cada celda contra todos los rangos.
- 12 meses con `unnest` + JOIN simple en Argentina: el planificador eligió `Parallel Seq Scan`, **4.635 ms**.

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
|---|---:|---:|---:|---:|
| Argentina, 12 meses (2024) | 25.668 | 2,6 MB | 0,14 s | 182.795 filas/s |
| Argentina, serie completa | 359.145 | 36 MB | 1,12 s | 320.751 filas/s |
| Sudamérica, serie completa | 1.873.938 | 187 MB | 9,63 s | 194.624 filas/s |

**Tope recomendado:** **1.000.000 filas** (~100 MB, ~5 s), verificado antes con el `COUNT` (que cuesta lo mismo que el calendario). Cabecera del CSV: aclarar que son celdas de 0,25° seleccionadas por centro de celda.

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
ALTER ROLE wildfire_web SET jit = off;                                 -- consultas cortas: JIT solo agrega latencia
```

- **pg_hba.conf:** permitir `wildfire_web` solo desde el host del backend, con `scram-sha-256`.
- **Pool de conexiones** (psycopg_pool o asyncpg): 5–10 conexiones.
- **Validar entradas antes de consultar:** fechas dentro de 2012-01..2026-08 y primer día de mes; polígono de ≤ 1.000 vértices; ≤ 50.000 celdas.
- **Respuestas:** informar `celdas_usadas` y avisar si son menos de 4; informar la resolución (0,25° o 1°); propagar `quality_flag`.
- **Caché:** `reference_plan`, `quality_bits`, `dataset_metadata`, `global_month` y `dim_satellite` son chicas y estáticas; cargarlas al iniciar el backend.
- **Base de solo lectura:** después del `VACUUM ANALYZE` de la restauración no hace falta mantenimiento.

### Anomalía (decisiones cerradas) en Python

```python
import math, statistics

EXCLUDE_BASELINE_MASK = 29
MIN_VALID_YEARS = 10

def anomaly(series: dict[tuple[int, int], tuple[float, int]], target: tuple[int, int]) -> dict | None:
    """series[(year, month)] = (X regional sumado, quality_flag del mes, con el bit 7 si se quiere).
    Base = mismo mes calendario, otros años, con (flag & EXCLUDE_BASELINE_MASK) == 0 (leave-one-out)."""
    y, m = target
    X = series[target][0]
    base = [v for (yy, mm), (v, f) in series.items() if mm == m and yy != y and (f & EXCLUDE_BASELINE_MASK) == 0]
    if len(base) < MIN_VALID_YEARS:
        return None
    pct = (sum(b < X for b in base) + 0.5 * sum(b == X for b in base)) / len(base)
    clase = "<=50" if pct <= 0.50 else "50-75" if pct <= 0.75 else "75-90" if pct <= 0.90 else ">90"
    record = X > max(base)                              # estrictamente mayor que el máximo de los meses válidos
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

**Pruebas reproducibles.** Entradas y salidas exactas, obtenidas ejecutando la función de arriba, copiada del contrato. Formato de entrada: `series[(year, month)] = (x, quality_flag)`.

**Prueba 1 (caso normal), objetivo `(2024, 8)`:**

```json
[
  {"year": 2012, "month": 8, "x": 102.0, "quality_flag": 0},
  {"year": 2013, "month": 8, "x": 90.0,  "quality_flag": 24},
  {"year": 2014, "month": 8, "x": 104.0, "quality_flag": 0},
  {"year": 2015, "month": 8, "x": 100.0, "quality_flag": 0},
  {"year": 2016, "month": 8, "x": 101.0, "quality_flag": 0},
  {"year": 2017, "month": 8, "x": 102.0, "quality_flag": 0},
  {"year": 2018, "month": 8, "x": 103.0, "quality_flag": 0},
  {"year": 2019, "month": 8, "x": 104.0, "quality_flag": 0},
  {"year": 2020, "month": 8, "x": 100.0, "quality_flag": 0},
  {"year": 2021, "month": 8, "x": 101.0, "quality_flag": 0},
  {"year": 2022, "month": 8, "x": 102.0, "quality_flag": 0},
  {"year": 2023, "month": 8, "x": 103.0, "quality_flag": 0},
  {"year": 2024, "month": 8, "x": 104.0, "quality_flag": 0},
  {"year": 2025, "month": 8, "x": 100.0, "quality_flag": 0},
  {"year": 2026, "month": 8, "x": 200.0, "quality_flag": 6}
]
```

Salida:

```json
{"n_base": 12, "percentil": 0.9166666666666666, "clase": ">90", "record": false, "z_robusto": 1.3295554851312064, "razon_mediana": null}
```

Cómo se llega:
- **X = 104.**
- **La base excluye** 2024 (es el mes evaluado), 2013 (`24 & 29 = 24`, excluido) y 2026 (`6 & 29 = 4`, excluido). Quedan **12 valores**: 102, 104, 100, 101, 102, 103, 104, 100, 101, 102, 103, 100.
- **Percentil:** hay 10 valores menores que 104 y 2 iguales, así que (10 + 0,5 · 2) / 12 = **0,9167** → clase `>90`.
- **Récord:** no, porque 104 no supera el máximo de la base (104).

**Prueba 2 (mes excluido evaluado igual), misma serie, objetivo `(2026, 8)`:**

```json
{"n_base": 13, "percentil": 1.0, "clase": ">90", "record": true, "z_robusto": 46.221832066239436, "razon_mediana": null}
```

La base son los 13 años válidos (2012 y 2014–2025). X = 200 supera a todos: récord. El mes en sí está excluido de las bases de los demás años, pero se puede evaluar; la interfaz lo muestra con su bandera.

**Prueba 3 (MAD = 0), objetivo `(2020, 1)`:**

```json
[
  {"year": 2012, "month": 1, "x": 0.0, "quality_flag": 0},
  {"year": 2013, "month": 1, "x": 0.0, "quality_flag": 0},
  {"year": 2014, "month": 1, "x": 0.0, "quality_flag": 0},
  {"year": 2015, "month": 1, "x": 0.0, "quality_flag": 0},
  {"year": 2016, "month": 1, "x": 0.0, "quality_flag": 0},
  {"year": 2017, "month": 1, "x": 0.0, "quality_flag": 0},
  {"year": 2018, "month": 1, "x": 0.0, "quality_flag": 0},
  {"year": 2019, "month": 1, "x": 0.0, "quality_flag": 0},
  {"year": 2020, "month": 1, "x": 3.0, "quality_flag": 0},
  {"year": 2021, "month": 1, "x": 0.0, "quality_flag": 0},
  {"year": 2022, "month": 1, "x": 0.0, "quality_flag": 0},
  {"year": 2023, "month": 1, "x": 0.0, "quality_flag": 0},
  {"year": 2024, "month": 1, "x": 0.0, "quality_flag": 0},
  {"year": 2025, "month": 1, "x": 0.0, "quality_flag": 0},
  {"year": 2026, "month": 1, "x": 0.0, "quality_flag": 0}
]
```

Salida:

```json
{"n_base": 14, "percentil": 1.0, "clase": ">90", "record": true, "z_robusto": null, "razon_mediana": null}
```

La base son 14 ceros, así que MAD = 0 y no hay z robusto. La mediana también es 0, por lo que la razón contra la mediana no está definida (`null`). La interfaz debe mostrar "sin actividad en la base" en lugar de un número.

## 8. Tamaños y muestras reales

| Tabla | Tamaño total | Filas | Mínimo | Máximo |
|---|---:|---:|---|---|
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

- **Base web restaurada desde el `.dump`: 1,7 GB (1.707 MB, medido).** `cell_month` ocupa el 75 % y `map_month` el 24 %; el resto de las tablas suma ~18 MB.
- `.dump` comprimido: 289,5 MB.
- La base local `wildfire-armonizado` ocupa hoy 3,07 GB porque además conserva las tablas `*_v01` (1,36 GB), que no están en el `.dump` y se borrarán cuando el equipo web confirme la v0.2.

### 8.1 `cell_month`: Sudamérica (lat −35..−20, lon −66..−55)

Un mes normal (2024-08), ene-2012 parcial (bit 0), jul-2023 con respaldo NOAA-21 (bit 6), ago-2026 solo MODIS y último mes (bits 1 y 2), y una fila con `n_eq = 0`:

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

`map_month`:
```json
[
  {"month":"2024-08-01","cell_id":373408,"n_eq":0.21983373,"f_eq":0.9240071},
  {"month":"2024-08-01","cell_id":373410,"n_eq":0,"f_eq":0},
  {"month":"2024-08-01","cell_id":373411,"n_eq":0.21983373,"f_eq":0.8050755}
]
```

`global_month`:
```json
[
  {"month":"2012-01-01","n_eq":84957.09375,"f_eq":3129637.5,"n_terra":127302,"n_aqua":234750,"n_snpp":507930,"n_n20":0,"n_n21":0,"frp_terra":4420968,"frp_aqua":8631598,"n_cells":32247,"ref_sat":3,"sensors":"SNPP","quality_flag":1,"excluded_from_baseline":true},
  {"month":"2023-07-01","n_eq":353789.96875,"f_eq":18924308,"n_terra":155771,"n_aqua":373996,"n_snpp":2000417,"n_n20":1855323,"n_n21":2028923,"frp_terra":8567092,"frp_aqua":18923280,"n_cells":60067,"ref_sat":5,"sensors":"N21 (respaldo de N20)","quality_flag":64,"excluded_from_baseline":false},
  {"month":"2024-08-01","n_eq":533706.5625,"f_eq":27645796,"n_terra":204560,"n_aqua":498793,"n_snpp":3103304,"n_n20":3037131,"n_n21":2907401,"frp_terra":9980086,"frp_aqua":28197462,"n_cells":63194,"ref_sat":4,"sensors":"N20","quality_flag":0,"excluded_from_baseline":false},
  {"month":"2026-08-01","n_eq":354788,"f_eq":16153211,"n_terra":138895,"n_aqua":354788,"n_snpp":0,"n_n20":0,"n_n21":0,"frp_terra":7062951.5,"frp_aqua":16153211,"n_cells":31150,"ref_sat":2,"sensors":"Aqua (solo MODIS / deriva)","quality_flag":6,"excluded_from_baseline":true}
]
```

`sat_month_quality`:
```json
[
  {"month":"2012-03-01","sat_code":3,"days_in_range":31,"days_missing":1,"days_caida":2,"days_parcial":2,"days_catalog":0,"days_minutes_low":4,"days_affected":4,"complete":false},
  {"month":"2023-07-01","sat_code":4,"days_in_range":31,"days_missing":4,"days_caida":0,"days_parcial":0,"days_catalog":0,"days_minutes_low":4,"days_affected":4,"complete":false},
  {"month":"2024-07-01","sat_code":3,"days_in_range":31,"days_missing":10,"days_caida":3,"days_parcial":0,"days_catalog":0,"days_minutes_low":13,"days_affected":13,"complete":false},
  {"month":"2024-08-01","sat_code":4,"days_in_range":31,"days_missing":0,"days_caida":0,"days_parcial":0,"days_catalog":0,"days_minutes_low":0,"days_affected":0,"complete":true}
]
```

`sat_day_effort`:
```json
[
  {"obs_date":"2024-08-15","sat_code":4,"lat_band":-999,"n_minutes":509,"n_det":106951},
  {"obs_date":"2024-08-15","sat_code":4,"lat_band":-30,"n_minutes":51,"n_det":8229},
  {"obs_date":"2024-08-15","sat_code":4,"lat_band":-20,"n_minutes":57,"n_det":59273},
  {"obs_date":"2024-08-15","sat_code":4,"lat_band":-10,"n_minutes":55,"n_det":20891}
]
```

`calibration_coef`:
```json
[
  {"method_version":"v0.2","sat_code":3,"lat_band":-30,"sector":1,"season":3,"alpha":0.21923941666928415,"gamma":0.9162603544758986,"confidence":"alta","fit_level":"lat_band+sector+season"},
  {"method_version":"v0.2","sat_code":4,"lat_band":-30,"sector":1,"season":3,"alpha":0.2198337385436799,"gamma":0.9148585292532562,"confidence":"alta","fit_level":"lat_band+sector+season"},
  {"method_version":"v0.2","sat_code":4,"lat_band":70,"sector":2,"season":1,"alpha":0.18381734722178686,"gamma":0.9847482733277452,"confidence":"baja","fit_level":"season"},
  {"method_version":"v0.2","sat_code":5,"lat_band":-30,"sector":1,"season":3,"alpha":0.2282121775811091,"gamma":0.8180381862169753,"confidence":"alta","fit_level":"lat_band+sector+season"}
]
```

`known_gap` (completa):
```json
[
  {"gap_id":1,"sat_code":2,"date_from":"2020-08-16","date_to":"2020-09-02","gap_kind":"falla_documentada","source":"nasa","note":"Falla de Aqua: cobertura muy limitada (guía MODIS)"},
  {"gap_id":2,"sat_code":2,"date_from":"2022-04-01","date_to":"2022-04-16","gap_kind":"sin_datos","source":"fase0","note":"16 días sin datos de Aqua"},
  {"gap_id":3,"sat_code":1,"date_from":"2016-02-19","date_to":"2016-02-27","gap_kind":"sin_datos","source":"fase0","note":"9 días sin datos de Terra"},
  {"gap_id":4,"sat_code":1,"date_from":"2022-10-10","date_to":"2022-10-23","gap_kind":"sin_datos","source":"fase0","note":"Terra: caída el 10-oct y sin datos hasta el 23-oct"}
]
```

`dim_satellite` (completa):
```json
[
  {"sat_code":1,"raw_satellite":"Terra","firms_code":"T","sensor":"MODIS","orbit_family":"manana","nominal_pixel_km":1,"raw_table":"modis","first_date":"2012-01-01","last_date":"2026-08-31","scan_c1":1,"scan_c2":1.2,"scan_c3":1.5,"scan_c4":2},
  {"sat_code":2,"raw_satellite":"Aqua","firms_code":"A","sensor":"MODIS","orbit_family":"tarde","nominal_pixel_km":1,"raw_table":"modis","first_date":"2012-01-01","last_date":"2026-08-31","scan_c1":1,"scan_c2":1.2,"scan_c3":1.5,"scan_c4":2},
  {"sat_code":3,"raw_satellite":"SNPP","firms_code":"N","sensor":"VIIRS","orbit_family":"tarde","nominal_pixel_km":0.375,"raw_table":"viirs_suomi","first_date":"2012-01-20","last_date":"2026-07-31","scan_c1":0.4,"scan_c2":0.45,"scan_c3":0.5,"scan_c4":0.6},
  {"sat_code":4,"raw_satellite":"N20","firms_code":"N20","sensor":"VIIRS","orbit_family":"tarde","nominal_pixel_km":0.375,"raw_table":"viirs_j1","first_date":"2018-04-01","last_date":"2026-07-31","scan_c1":0.4,"scan_c2":0.45,"scan_c3":0.5,"scan_c4":0.6},
  {"sat_code":5,"raw_satellite":"N21","firms_code":"N21","sensor":"VIIRS","orbit_family":"tarde","nominal_pixel_km":0.375,"raw_table":"viirs_j2","first_date":"2023-03-01","last_date":"2026-07-31","scan_c1":0.4,"scan_c2":0.45,"scan_c3":0.5,"scan_c4":0.6}
]
```

`quality_bits` (completa):
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

`dataset_metadata` (completa):
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

```json
[
  {"month":"2012-01-01","quality_flag":1,"excluded_from_baseline":true,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2012-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2012-03-01","quality_flag":24,"excluded_from_baseline":true,"ref_sat":3,"sensors":"SNPP","days_affected":4},
  {"month":"2012-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2012-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2012-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":1},
  {"month":"2012-07-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2012-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2012-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2012-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2012-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2012-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2013-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2013-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2013-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2013-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2013-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2013-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2013-07-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2013-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2013-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2013-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2013-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2013-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2014-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2014-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2014-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2014-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2014-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2014-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2014-07-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2014-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2014-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2014-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2014-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2014-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2015-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2015-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2015-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2015-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2015-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2015-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2015-07-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2015-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2015-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2015-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2015-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2015-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2016-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2016-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2016-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2016-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2016-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2016-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2016-07-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2016-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2016-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2016-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2016-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2016-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2017-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2017-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2017-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2017-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2017-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2017-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2017-07-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2017-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2017-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2017-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2017-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2017-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2018-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2018-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2018-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2018-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2018-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2018-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2018-07-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2018-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2018-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2018-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2018-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2018-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2019-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2019-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2019-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2019-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2019-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2019-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2019-07-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2019-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2019-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2019-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2019-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2019-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":3,"sensors":"SNPP","days_affected":0},
  {"month":"2020-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2020-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2020-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2020-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2020-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2020-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2020-07-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2020-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2020-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2020-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2020-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2020-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2021-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2021-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2021-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2021-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2021-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2021-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2021-07-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2021-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2021-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2021-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2021-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2021-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2022-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2022-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2022-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2022-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2022-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2022-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2022-07-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2022-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2022-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2022-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2022-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2022-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2023-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2023-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2023-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2023-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2023-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2023-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2023-07-01","quality_flag":64,"excluded_from_baseline":false,"ref_sat":5,"sensors":"N21 (respaldo de N20)","days_affected":0},
  {"month":"2023-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2023-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":1},
  {"month":"2023-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":1},
  {"month":"2023-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2023-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2024-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2024-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":2},
  {"month":"2024-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2024-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2024-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2024-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2024-07-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2024-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2024-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2024-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2024-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2024-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2025-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2025-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2025-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2025-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2025-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2025-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2025-07-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2025-08-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2025-09-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2025-10-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2025-11-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2025-12-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2026-01-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2026-02-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2026-03-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2026-04-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2026-05-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2026-06-01","quality_flag":0,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2026-07-01","quality_flag":2,"excluded_from_baseline":false,"ref_sat":4,"sensors":"N20","days_affected":0},
  {"month":"2026-08-01","quality_flag":6,"excluded_from_baseline":true,"ref_sat":2,"sensors":"Aqua (solo MODIS / deriva)","days_affected":0}
]
```

Nota: en 2023-07, `days_affected = 0` corresponde al satélite usado (NOAA-21). Los 4 días afectados de NOAA-20 están en `sat_month_quality` (`month = '2023-07-01'`, `sat_code = 4`).
