# Diseño de la Fase 1: esquema `harmonized` para la armonización MODIS + VIIRS

**Fecha:** 15-nov-2026 · **Estado:** propuesta para la **Puerta 2**. **No se creó ni modificó nada en la base**; todas las mediciones de este documento son consultas de solo lectura (`01_…`, `02_…` de esta carpeta y los scripts de la Fase 0).
Convención: **[M]** medido · **[E]** estimado · **[S]** supuesto. Fuente de verdad: `docs/CONTEXTO_ARMONIZACION.md` (sección 0 y decisiones de la Puerta 1).

---

## 0. Aclaraciones pedidas (A–E)

### A. Deriva de Aqua y validación 2021–2026

Hora solar local mediana de las detecciones diurnas (`type = 0`, enero y julio de cada año) [M]:

| Año | 2012–2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| **Aqua** | 13,55–13,58 h | 13,61 | 13,77 | 14,11 | 14,58 | **15,27** |
| **Terra** | 10,61–10,69 h | 10,48 | 10,33 | 10,06 | 9,66 | **9,27** |
| **S-NPP** | 13,38–13,50 h | 13,40 | 13,42 | 13,40 | 13,43 | 13,50 |

La mediana de `scan` de Aqua sigue en 1,3 km hasta 2025 y baja a 1,2 en 2026; la fracción de detecciones casi-nadir (`scan` ≤ 1,5 km) sube de ~0,65 a 0,69 [M]. La deriva relevante es la **hora de pasada** (casi 2 h en 2026), más que el tamaño del píxel.

**Consecuencia para el diseño (pedido A):** la validación se reporta en **dos cuentas separadas**:
1. **Error de calibración:** validación cruzada por años *dentro* de 2012–2020 (dejar un año afuera, ajustar con los demás, medir sesgo y RMSE en el año excluido). Aqua estuvo a su hora nominal en todo ese período.
2. **Deriva de Aqua:** en 2021–2026, la razón `N_Aqua observado / N_eq predicho desde VIIRS` por mes y banda de latitud, **graficada contra la hora local mediana de Aqua**. No se cuenta como error de calibración: describe cuánto se aleja Aqua de la unidad definida en 2012–2020.

Hallazgo útil: la deriva de Aqua es un "experimento natural" (6b.5). La curva de la cuenta 2 estima el efecto de la hora de pasada sobre la detección.

### B. Agosto de 2026
`N_eq(i, ago-2026) = N_Aqua(i, ago-2026)` y `F_eq = FRP_Aqua`, con bandera **`solo_modis_deriva`**. Aqua pasa a ~15,3 h en 2026, lejos de la unidad 2012–2020: el valor no es estrictamente "equivalente Aqua" y por eso se marca. **Se excluye de la línea base** y la app lo dibuja diferenciado (sección 9).

### C. Indicador de esfuerzo
Se mantiene lo acordado (par de la misma familia + ventanas mensuales o ≥ 8 días) y se agrega en la **misma lectura** de la agregación diaria:
- **Minutos de adquisición distintos** (`count(DISTINCT acq_time)`) por satélite y día, global y por banda de 10° de latitud. Validación [M]: en la caída de Aqua del 23 y 24 de septiembre de 2021 los minutos bajan de ~200 a 65 y 57 (faltan pasadas); en la caída de S-NPP del 3 al 5 de octubre de 2016 (−35 % de detecciones) los minutos siguen en ~445 (no faltan pasadas: la caída es real o por nubes, no de cobertura). El indicador distingue los dos casos.
- **Catálogo de huecos conocidos** (`harmonized.known_gap`), con la siembra de la sección 4.4.

**Limitaciones documentadas y cómo se cubren:**
- **Terra no tiene par en su familia** (es la única órbita de la mañana). Se cubre con: (1) minutos de adquisición, que detectan pasadas faltantes sin necesidad de par; (2) vecindad temporal (±15 días); (3) catálogo de huecos. Lo que no cubre: una caída real de detecciones sin pérdida de pasadas, indistinguible de fuego real.
- **Caídas simultáneas en varios satélites** (p. ej. 2021-01-01/03): la comparación con el par no las ve porque el par también cae. Se cubren con: (1) los minutos de adquisición, que bajan si faltan gránulos; (2) una bandera informativa `caida_simultanea` cuando ≥ 2 satélites caen el mismo día frente a su vecindad. Si los minutos son normales, se asume caída real (no se excluye); si bajan, se marca como hueco de cobertura.

### D. `UNLOGGED`: verificación y conversión [M]
- `archive_mode = off`, `archive_command` deshabilitado, **0 slots de replicación**, 0 conexiones de replicación, 0 archivos archivados, `wal_level = replica`, `pg_wal` actual 1 GB (64 segmentos) en C:. Con esto, `UNLOGGED` no genera WAL durante la construcción y no hay réplicas que lo necesiten.
- Conversión a `LOGGED`: **partición por partición** (una por año, ~0,6–1 GB cada una), cada una en su propia transacción, con `CHECKPOINT` y control de espacio en C: entre particiones. `ALTER TABLE … SET LOGGED` reescribe la partición y la escribe entera en el WAL: ~1 GB de WAL por partición, que se recicla con `max_wal_size` de 1 GB.
- Alternativa (dejar `UNLOGGED` para siempre): ante cualquier apagado no limpio, PostgreSQL **vacía** las tablas `UNLOGGED`. Reconstruirlas cuesta **~30–50 min** (sección 7). Dado el incidente de desconexión del disco USB de la carga inicial, **recomiendo convertir a `LOGGED`** al validar cada etapa (decisión 4).
- A verificar en el piloto: PostgreSQL 18 no acepta `UNLOGGED` en la tabla particionada padre (que no tiene almacenamiento); las **particiones** se crean `UNLOGGED` individualmente. Si alguna versión lo impidiera, se usa el plan B: tablas por año con una vista `UNION ALL` (sección 5.1).

### E. De dónde sale 588.784.736 y cierre de la conciliación [M]
- 610.870.539 = todo lo cargado desde los CSV (suma de `carga_log`, incluido NRT).
- 22.085.803 = filas NRT **eliminadas** el 15-nov-2026 por decisión del usuario (registradas en `carga_log.observacion`).
- **588.784.736 = 610.870.539 − 22.085.803** = filas vigentes en las 4 tablas, verificado fila por fila en la pasada de perfil de la Fase 0.
- Para la sección 9 ("filas crudas = procesadas + excluidas"): la base de la conciliación son las **588.784.736** filas vigentes; las 22.085.803 NRT quedan como exclusión previa documentada, con motivo "NRT eliminado por decisión del usuario". En la Fase 2, `harmonization_log` registra por tabla y mes: filas leídas = `n_all` agregadas (debe coincidir exacto), y por categoría las excluidas de cada vista (`type ≠ 0`, confianza baja).

---

## 1. Principios del diseño

1. **Una lectura por tabla cruda** (1b.1): la Fase 2 lee cada tabla una vez, por lotes mensuales, y produce en esa misma lectura los agregados diarios **y** el esfuerzo. Todo lo demás se calcula sobre agregados.
2. **Capa canónica como vista**, no como copia: `harmonized.v_detection` traduce nombres y códigos (adaptador) sin duplicar 589 M filas (~60 GB). Se materializa solo lo agregado.
3. **Aditividad** (6d.4): todo valor por celda y mes es una suma (conteos, FRP, celdas de ~1 km ocupadas, días con detección). Las anomalías y medianas **nunca** se guardan por AOI.
4. **Grilla row-major** para que un rectángulo sea un conjunto de **rangos contiguos** de `cell_id`, y para que el orden físico de las tablas (por `cell_id`) haga contiguas en disco las celdas vecinas de una misma fila de latitud.
5. **Calibración separada de los datos**: los coeficientes viven en tablas propias con `method_version`; recalibrar no relee las crudas.

## 2. Grilla y `cell_id`

| Elemento | Definición |
|---|---|
| Celda base | 0,25° × 0,25° (CONTEXTO 0.9) |
| `cell_row` | `floor((lat + 90) / 0,25)`, de 0 a 719 (`lat = 90` → 719) |
| `cell_col` | `floor((lon + 180) / 0,25)`, de 0 a 1439 (`lon = 180` → 0, mismo meridiano que −180) |
| `cell_id` | `cell_row * 1440 + cell_col` (integer, 0 a 1.036.799). Orden row-major: dentro de una fila de latitud, celdas contiguas tienen `cell_id` contiguos |
| Subcelda ~1 km | 0,01° (25 × 25 por celda de 0,25°, anidada exacta) para contar celdas de ~1 km ocupadas |
| Bloque 1° | `block_id = floor(cell_row / 4) * 360 + floor(cell_col / 4)` (4 × 4 celdas), para la pirámide de AOIs grandes |
| Área | `cell_area_km2 = R² · Δλ · (sin φ2 − sin φ1)`, con R = 6371,0 km y Δλ en radianes: ~773 km² en el ecuador y ~387 km² a 60° |

**Rectángulo → rangos contiguos.** `[lon_min, lat_min, lon_max, lat_max]` se convierte en filas `r0..r1` y columnas `c0..c1` (celdas **cuyo centro** cae dentro, igual que en el polígono). Cada fila aporta **un** rango `[r·1440 + c0, r·1440 + c1]`: como máximo 720 rangos, nunca un `IN` de miles de celdas. Si el rectángulo cruza el antimeridiano (`lon_min > lon_max`), cada fila aporta dos rangos. En SQL:

```sql
-- $r0,$r1,$c0,$c1 calculados en el backend
SELECT m.month, sum(m.n_eq) ...
  FROM generate_series($r0, $r1) AS r
  JOIN harmonized.cell_month m
    ON m.cell_id BETWEEN r * 1440 + $c0 AND r * 1440 + $c1
 GROUP BY m.month;
```

**Polígono.** El backend (Python, sin PostGIS; prueba punto-en-polígono por *ray casting* sobre los centros dentro del rectángulo envolvente) arma la lista de celdas y la comprime en **corridas** por fila: `(inicio, fin)` contiguos. Se envían como dos arreglos: `JOIN unnest($inicios, $finales) r(s, e) ON m.cell_id BETWEEN r.s AND r.e`. Un polígono "normal" produce del orden de una corrida por fila (o pocas, si es cóncavo).
- Si quedan **menos de 4 celdas**, la respuesta incluye `celdas_usadas` y un aviso (pedido 3).
- **Tope propuesto (decisión 3):** ≤ 1.000 vértices y ≤ **50.000 celdas** (~38 M km² en el ecuador; Sudamérica son ~17,8 M km²). Por encima, la app ofrece regiones predefinidas o la serie global precomputada.

**AOIs grandes (pirámide 1°).** Para regiones de más de ~2.000 celdas, el backend usa los **bloques de 1° cuyas 16 celdas** están dentro (tabla `block_month`) y las celdas sueltas del borde desde `cell_month`. Es aditivo, así que el resultado es idéntico al de sumar las celdas finas.

**Calendario vs CSV en los bordes (documentado para el usuario):** el calendario usa **celdas enteras de 0,25° cuyo centro cae en la región**; el CSV usa **los puntos exactos dentro del rectángulo o polígono**. En el borde, un foco puede estar en el CSV pero no en el calendario (su celda tiene el centro afuera) y viceversa. La diferencia es como máximo la franja de ~1 celda (~28 km en el ecuador) alrededor del borde; la app lo explica en la ayuda del calendario y en la cabecera del CSV.

## 3. Esquema `harmonized`: tablas

**Dimensiones y control** (chicas, `LOGGED` desde el inicio):

| Tabla | Contenido | Filas |
|---|---|---|
| `harmonized.dim_satellite` | `sat_code` smallint PK (1 Terra, 2 Aqua, 3 SNPP, 4 N20, 5 N21), `raw_satellite` (`Terra`, `Aqua`, `SNPP`, `N20`, `N21`), `firms_code` (`T`, `A`, `N`, `N20`, `N21`), `sensor` (MODIS/VIIRS), `orbit_family` (mañana/tarde), `nominal_pixel_km`, `raw_table`, `first_date`, `last_date` | 5 |
| `harmonized.grid_cell` | `cell_id` PK, `cell_row`, `cell_col`, `block_id`, `lat_center`, `lon_center`, `cell_area_km2`, `lat_band` (10°) | 1.036.800 (~70 MB) |
| `harmonized.known_gap` | `sat_code`, `date_from`, `date_to`, `gap_kind` (`sin_datos` / `caida` / `falla_documentada`), `source` (`nasa` / `fase0` / `fase2_empirico`), `note` | decenas |
| `harmonized.harmonization_log` | `batch_id`, `step`, `raw_table`, `month`, `status`, `rows_read`, `rows_daily`, `rows_effort`, `started_at`, `finished_at`, `seconds`, `rows_per_s`, `error` | ~550 por corrida |

**Agregados de la Fase 2** (lectura de las crudas):

| Tabla | Clave | Columnas (todas aditivas salvo los máximos) |
|---|---|---|
| `harmonized.cell_day_sat` (particionada por año) | `(obs_date, cell_id, sat_code)` | `n_all` int (todas las filas: conciliación), `n_t0`, `n_t0_conf` (sin confianza baja), `n_t0_day`, `n_t0_nadir` (`scan` ≤ umbral, decisión 7), `n_t1`, `n_t2`, `n_t3` int · `frp_t0`, `frp_t0_conf`, `frp_t0_nadir` real (MW) · `frp_t0_max` real · `cells1km_t0` smallint (subceldas de 0,01° con ≥ 1 detección `type = 0`, ≤ 625) |
| `harmonized.sat_day_effort` | `(obs_date, sat_code, lat_band)`; `lat_band = -999` = global | `n_minutes` (minutos de adquisición distintos), `n_det` |

**Derivados** (desde los agregados diarios, sin tocar las crudas):

| Tabla | Clave | Contenido |
|---|---|---|
| `harmonized.sat_day_quality` | `(obs_date, sat_code)` | `n_det`, `n_minutes`, mediana ±15 días de ambos, razón contra el par de familia, `status` (`ok` / `parcial` / `caida` / `sin_datos`), `caida_simultanea` bool, `in_known_gap` bool |
| `harmonized.cell_month_sat` | `(month, cell_id, sat_code)` | Sumas mensuales de `cell_day_sat` + `days_detected` (días con `n_t0 > 0`). Base de la calibración (Fase 3) y de la serie propia de Terra |
| `harmonized.sat_month_quality` | `(month, sat_code)` | Días `ok`/`parcial`/`caida`/`sin_datos`, días en huecos del catálogo, minutos medios, bits de `quality_flag` del mes |

**Calibración y serie armonizada** (Fases 3 y 4; se crean en esas fases, se diseñan ahora para fijar el contrato):

| Tabla | Clave | Contenido |
|---|---|---|
| `harmonized.calibration_coef` | `(method_version, sat_code, region_id, season, metric)` | `coef` (α o γ), `se`, `n_cell_months`, `fit_period`, `estimator`; `metric` ∈ {`count`, `count_conf`, `cells1km`, `frp`} |
| `harmonized.reference_plan` | `(method_version, month)` | Satélite VIIRS de referencia del mes y respaldo si tiene huecos (tramos que confirma el test de escalones de la Fase 3) |
| `harmonized.cell_month` | `(month, cell_id)` | **Serie armonizada:** `n_eq`, `f_eq` (MW) en unidad Aqua 2012–2020; crudos por sensor (`n_aqua`, `n_terra`, `n_snpp`, `n_n20`, `n_n21`, `frp_*`); `ref_sat`; `quality_flag` smallint; `method_version` |
| `harmonized.block_month` | `(month, block_id)` | Las mismas sumas por bloque de 1° (pirámide) |
| `harmonized.global_month` | `(month)` | Serie global precomputada |
| `harmonized.cell_climatology` | `(cell_id, month_of_year, method_version)` | Mediana y MAD de `log1p(n_eq)` sobre la línea base, para la capa de mapa (6d.4) |

**Bits de `quality_flag`** (decisión 5):

| Bit | Valor | Significado | ¿Excluye de la línea base? |
|---|---|---|---|
| 0 | 1 | Mes parcial de VIIRS (ene-2012) | Sí |
| 1 | 2 | Último mes standard del sensor de referencia (posibles reprocesos) | No (solo aviso) |
| 2 | 4 | `solo_modis_deriva` (ago-2026) | Sí |
| 3 | 8 | Hueco del catálogo en el satélite de referencia durante el mes | Sí si ≥ 5 días |
| 4 | 16 | Caída empírica (minutos faltantes) del satélite de referencia | Sí si ≥ 5 días |
| 5 | 32 | Caída simultánea en ≥ 2 satélites (informativa) | No |
| 6 | 64 | Se usó el satélite de respaldo (la referencia tenía huecos) | No |
| 7 | 128 | Calibración provisional (antes de validar la Fase 3) | No |

La bandera es por mes y satélite (igual para todas las celdas), así que se guarda en `sat_month_quality` y se copia a `cell_month` (2 bytes por fila) para no hacer joins en la app.

**Vista canónica** `harmonized.v_detection`: `UNION ALL` de las 4 crudas con `obs_ts_utc = acq_date + acq_time::time`, `sat_code`, `sensor_family`, `lat`, `lon`, `cell_id` (calculado), `frp`, `confidence_class` (`baja` / `nominal` / `alta`: MODIS < 30 / 30–79 / ≥ 80; VIIRS `l` / `n` / `h`), `type`, `daynight`, `pixel_area_km2 = scan · track`. Sin datos propios; sirve como adaptador para el CSV y para la documentación.

## 4. Fase 2: plan por lotes

### 4.1 Unidad de trabajo
Un lote = **(tabla cruda, mes)**: 176 + 175 + 100 + 41 = **492 lotes**. Cada lote, en **una transacción y una sola lectura** (`WITH src AS MATERIALIZED`, medido en `02_piloto_agregacion_doble.sql`):

```sql
BEGIN;
SET LOCAL work_mem = '1GB';
DELETE FROM harmonized.cell_day_sat  WHERE obs_date >= $m0 AND obs_date < $m1 AND sat_code = ANY($sats);  -- idempotencia
DELETE FROM harmonized.sat_day_effort WHERE obs_date >= $m0 AND obs_date < $m1 AND sat_code = ANY($sats);
WITH src AS MATERIALIZED (SELECT … FROM <cruda> WHERE acq_date >= $m0 AND acq_date < $m1),   -- BRIN
     k1  AS (… GROUP BY obs_date, cell_id, sat_code, subcelda_1km),
     ins_d AS (INSERT INTO harmonized.cell_day_sat  SELECT … FROM k1 GROUP BY obs_date, cell_id, sat_code RETURNING n_all),
     ins_e AS (INSERT INTO harmonized.sat_day_effort SELECT … FROM src
                 GROUP BY GROUPING SETS ((obs_date, sat_code, lat_band), (obs_date, sat_code)) RETURNING 1)
SELECT (SELECT count(*) FROM src), (SELECT sum(n_all) FROM ins_d), (SELECT count(*) FROM ins_e);
-- control: count(src) = sum(n_all); si no, ROLLBACK y error en harmonization_log
INSERT INTO harmonized.harmonization_log …;
COMMIT;
```

- **Reanudable:** el orquestador (Python) saltea los lotes `ok` en `harmonization_log`.
- **Conciliación por lote:** filas leídas = Σ `n_all`; si no coincide, el lote no se confirma.
- **Paralelismo:** 2 procesos sobre tablas distintas (≤ núcleos − 1; la lectura USB es el límite).

### 4.2 Escala (regla 5.4)
1. **Piloto de un mes:** ene-2026, las 4 tablas (4 lotes). Se mide tiempo, filas y tamaño; se verifica conciliación, idempotencia (correr dos veces) y el `ANALYZE`.
2. **Un año:** 2024 (año pico, con los 5 satélites; 48 lotes). Se recalibran las estimaciones de la sección 7.
3. **Todo:** los ~440 lotes restantes, por año, con control de espacio en D: y C: entre años.
4. **Derivados:** `sat_day_quality`, `cell_month_sat`, `sat_month_quality` y la siembra de `known_gap` desde `cell_day_sat` (minutos, sin releer las crudas).
5. **Índices y `ANALYZE`** al final de cada partición; conversión a `LOGGED` por partición tras validar (decisión 4).

### 4.3 Particionado
- `cell_day_sat`: `PARTITION BY RANGE (obs_date)`, **una partición por año** (2012–2026: 15). Permite reprocesar o convertir a `LOGGED` un año, y que las consultas por fecha descarten particiones.
- `sat_day_effort`, `cell_month_sat`, `cell_month`: sin particionar (≤ ~25 M filas). `cell_month` se ordena físicamente por `(cell_id, month)` (`CLUSTER` tras construirla).

### 4.4 Siembra del catálogo `known_gap`
- `falla_documentada` (fuente `nasa`): Aqua 2020-08-16 → 2020-09-02.
- `sin_datos` / `caida` (fuente `fase0`): Aqua 2022-04-01 → 04-16; Terra 2016-02-19 → 02-27 y 2022-10-10 → 10-23; S-NPP: los **49 días sin datos** se cargan **automáticamente** desde `cell_day_sat` (días sin filas dentro del rango del satélite), incluidos 2022-07-27 → 08-10 y 2026-07-10 → 07-16; NOAA-20 (6 días) y NOAA-21 (2 días) igual.
- `fase2_empirico`: las caídas por minutos de adquisición que detecte `sat_day_quality`.

### 4.5 Índices (después de la carga de cada partición)

| Tabla | Índices |
|---|---|
| `cell_day_sat` | PK `(obs_date, cell_id, sat_code)` (B-tree, por partición) · B-tree `(cell_id, obs_date)` para consultas diarias por AOI |
| `sat_day_effort` | PK `(obs_date, sat_code, lat_band)` |
| `cell_month_sat` | PK `(month, cell_id, sat_code)` · B-tree `(cell_id, month)` |
| `cell_month` | PK `(cell_id, month)` con `INCLUDE (n_eq, f_eq, quality_flag)` → solo índice en la consulta del calendario |
| `block_month` | PK `(block_id, month)` con `INCLUDE (n_eq, f_eq, quality_flag)` |
| `cell_climatology` | PK `(cell_id, month_of_year, method_version)` |

Las tablas crudas **no** reciben índices nuevos (regla 5.6).

## 5. Detalles técnicos

### 5.1 `UNLOGGED` y conversión
Particiones de `cell_day_sat` creadas `UNLOGGED`; `sat_day_effort` y `cell_month_sat` también durante la construcción. Tras validar el año: `ALTER TABLE harmonized.cell_day_sat_2024 SET LOGGED;` (una partición por transacción, con `CHECKPOINT` y control de espacio). Plan B si una partición no admite el cambio: tablas por año sin padre, más la vista `harmonized.v_cell_day_sat` con `UNION ALL`.

### 5.2 Calibración (Fase 3, resumen del contrato)
- Unidad: **equivalente Aqua definida por la calibración 2012–2020** (decisión del usuario). Terra queda fuera de la serie armonizada, como serie propia visible desde `cell_month_sat`.
- Ajuste multiplicativo sin intercepto (6d.1) por región (banda de latitud; decisión 9) y estación, con los estimadores de 6d.1 comparados en validación cruzada por año dentro de 2012–2020.
- Cadena: Aqua ↔ S-NPP (2012–2020) define α_SNPP; S-NPP ↔ NOAA-20 en el solapamiento (2018 →) define α_N20; NOAA-20 ↔ NOAA-21 (2023-03 →) define α_N21. `reference_plan` fija la referencia de cada mes; el **test de escalones** (antes y después de cada transición: abr-2018, mar-2023, ene-2023 por la versión de MODIS, y la fecha en que cambie la referencia) confirma los tramos (Puerta 1, decisión 3).
- Respaldo: si el satélite de referencia tiene ≥ 5 días de hueco en un mes, ese mes usa el siguiente de la cadena con su propio α y bit 6.

### 5.3 Anomalía (Fase 5, calculada en el backend por AOI)
Percentil leave-one-out (6d.3) con **cuatro clases**: ≤ 50, 50–75, 75–90, > 90, más la marca **récord de la serie**; z robusto como secundario (tooltip y CSV). Línea base: toda la serie 2012+ excluyendo los meses con bits 0, 2, y 3 o 4 con ≥ 5 días (sección 3). Mínimo 10 años de base; si no, `NULL` con aviso.

## 6. Consultas tipo de la app y tiempos esperados [E]

| Consulta | Cómo | Filas leídas (peor caso) | Tiempo esperado |
|---|---|---|---|
| Calendario, AOI ≤ 2.000 celdas | rangos por fila sobre `cell_month` (índice con `INCLUDE`, ordenada por `cell_id`) | ≤ 2.000 × 176 = 352 k | **0,2–0,6 s** |
| Calendario, AOI grande (≤ 50.000 celdas) | bloques de 1° desde `block_month` + borde desde `cell_month` | ~3.000 bloques × 176 + borde ≈ 0,6–1 M | **0,5–1,5 s** |
| Serie global | `global_month` | 176 | < 50 ms |
| Capa de mapa de un mes (anomalía por celda) | `cell_month` del mes + `cell_climatology` | ≤ ~60 k celdas activas | 0,3–0,8 s |
| Estimación previa del CSV | Σ `n_all` desde `cell_day_sat` por AOI y fechas | según AOI | < 0,5 s |
| CSV de puntos crudos | `v_detection` filtrada por fechas (BRIN) + rectángulo + polígono exacto en el backend; streaming con `COPY … TO STDOUT` y tope | lectura de cada mes pedido en las 4 tablas | ~1–3 s por mes pedido (sin índice espacial en las crudas) |

Supuestos: celdas activas medidas por mes [M]: Aqua 19–28 k, Terra 11–23 k, S-NPP / N20 / N21 39–50 k (ene-2026 y ago-2024); 84 k celdas distintas con actividad de Aqua en todo 2024. La meta de ≤ 2 s se valida con las consultas reales tras la Fase 4.

**CSV (decisión 2):** sin índice espacial en las crudas, cada mes pedido cuesta ~1–3 s de lectura por las 4 tablas. Propuesta: tope de **12 meses o 1 M filas** por descarga (la estimación previa exacta sale de `cell_day_sat`), con streaming. Alternativas con costo: un índice B-tree `(acq_date, latitude)` en las crudas (requiere tu aprobación; ~15–20 GB), o una copia de detalle ordenada por celda (~60 GB).

## 7. Estimaciones de tiempo y espacio [E, calibradas con mediciones M]

**Mediciones de base [M]:**
- Agregación doble en una lectura, S-NPP ago-2024 (mes pico, 3,58 M filas): **8,8 s**; 371.374 filas diarias y 467 filas de esfuerzo; memoria: 340 MB del CTE + 606 MB + 336 MB de hash (cabe en `work_mem` de 1 GB).
- Agregación simple, S-NPP ene-2026 (1,53 M filas): 3,3 s → 253.553 filas diarias.
- Lectura sostenida del SSD USB: ~80 MB/s (pasada de 13 min de la Fase 0).

| Paso | Tiempo | Espacio |
|---|---|---|
| `cell_day_sat` + `sat_day_effort` (492 lotes) | **35–55 min** con 1 proceso (~0,4 M filas/s de agregación + escritura `UNLOGGED`); **25–35 min** con 2 | Filas diarias: razón agregado/crudo 0,10–0,17 en VIIRS y ~0,37 en MODIS → **~75–110 M filas** × ~76 B ≈ **6–8 GB** de heap; PK + índice `(cell_id, obs_date)` ≈ **5–6 GB**. Esfuerzo: ~0,4 M filas, < 50 MB |
| Derivados (`sat_day_quality`, `cell_month_sat`, `sat_month_quality`) | 5–10 min | `cell_month_sat`: ~21 M filas (celdas activas por mes × meses por satélite) ≈ **2–2,5 GB** con índices |
| Conversión a `LOGGED` (15 particiones + derivados) | 10–20 min | WAL transitorio de ~1 GB por partición en C: (80 GB libres) |
| Fase 4: `cell_month` + `block_month` + `global_month` | minutos | `cell_month`: ~9–10 M filas (unión de celdas activas por mes) ≈ **1,5 GB**; `block_month` < 0,3 GB |
| **Total nuevo en D:** | | **~16–20 GB** (504 GB libres) |

Reconstrucción completa ante un apagado no limpio, si quedaran `UNLOGGED`: igual a la primera fila más los derivados, **~30–50 min** (pedido D).

## 8. Validación y criterios (resumen; detalle en la Fase 6)
- Conciliación por lote (sección 4.1) y por tabla: Σ `n_all` = 588.784.736.
- Idempotencia: reprocesar un lote deja los totales iguales.
- Aditividad: Σ por celdas de un AOI = valor por bloques de la pirámide = valor directo.
- Calibración: validación cruzada por año en 2012–2020 (error) y curva de **deriva de Aqua** 2021–2026 (separada, pedido A).
- Escalones: test antes y después de abr-2018, ene-2023 (versión MODIS), mar-2023 y cada cambio de referencia.

## 9. Cómo se ve en la app (contrato con el frontend)
- Calendario: celdas con `quality_flag` bit 2 (ago-2026) con trama o borde distinto y leyenda "solo MODIS / deriva"; bits 3 y 4 con ≥ 5 días como "hueco de datos"; bit 1 con ícono "último mes standard".
- Terra se ofrece como serie propia ("órbita de la mañana") fuera del calendario armonizado.
- AOIs con < 4 celdas: aviso con la cantidad de celdas usadas.
- Diferencia calendario vs CSV en los bordes: texto fijo en la ayuda y en la cabecera del CSV.

---

## 10. Decisiones que necesito para la Puerta 2

1. **Capa canónica como vista** (`v_detection`, sin copia de 60 GB) en lugar de una tabla materializada por detección. ¿De acuerdo?
2. **CSV de puntos crudos:** ¿tope de 12 meses o 1 M filas, sin índices nuevos en las crudas (recomendado), o aprobás un índice B-tree `(acq_date, latitude)` en las crudas (~15–20 GB) para descargas más largas?
3. **Topes de región:** polígono ≤ 1.000 vértices y ≤ 50.000 celdas; pirámide de 1° para AOIs de más de ~2.000 celdas. ¿Aprobás estos valores?
4. **Persistencia:** convertir a `LOGGED` partición por partición tras validar (recomendado), o dejar las tablas derivadas `UNLOGGED` de forma permanente (reconstrucción de ~30–50 min ante un apagado no limpio).
5. **`quality_flag`:** ¿aprobás los 8 bits y las reglas de exclusión de la línea base (umbral de 5 días para huecos y caídas)?
6. **Respaldo de la referencia:** si el satélite VIIRS de referencia tiene ≥ 5 días de hueco en un mes, ese mes usa el siguiente de la cadena con bit 6. ¿De acuerdo con el umbral?
7. **Umbral casi-nadir** para la columna de evaluación `n_t0_nadir`: MODIS `scan` ≤ 1,5 km (~65 % de las detecciones de Aqua) y VIIRS `scan` ≤ 0,5 km. ¿Aprobás estos umbrales o preferís otros?
8. **Particionado anual** de `cell_day_sat` (15 particiones) y **2 procesos en paralelo** en la Fase 2.
9. **Regiones para α y γ:** bandas de latitud de 10° como punto de partida (se ajustan en la Fase 3 si la estabilidad lo pide), ¿o preferís otra regionalización (p. ej. biomas)?
10. **Orden de ejecución de la Fase 2:** piloto ene-2026 → año 2024 → resto, con informe y tu revisión después del piloto y después del año. ¿Querés aprobar cada escala o solo el piloto?
