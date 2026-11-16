-- =============================================================================
-- 013_v02_construccion.sql  (method_version 'v0.2') — base wildfire-nasa
-- Construye la v0.2 en tablas NUEVAS (sufijo _v02) sin tocar la v0.1:
--   sat_month_quality_v02, reference_plan_v02, calibration_coef_v02 (desde CSV de 08_preparar_v02.py
--   y 07_v02_analisis.py) y cell_month_v02 (mismas columnas y clave primaria que cell_month).
-- Modelo: α/γ por banda 10° × sector continental × estación, respaldo jerárquico (banda → grupo
--   de bandas extremas → estación → global), mínimo 2.000 focos; cadena S-NPP → NOAA-20 → NOAA-21;
--   referencia S-NPP hasta dic-2019 y NOAA-20 desde ene-2020; respaldo si la referencia está incompleta.
-- Regla de mes completo: < 3 días afectados (faltante | caída | catálogo | minutos bajos).
-- Uso: psql -v dir=<carpeta con los CSV> -f 013_v02_construccion.sql
-- =============================================================================
\set ON_ERROR_STOP on
\timing on
SET work_mem = '1GB';
BEGIN;

DROP TABLE IF EXISTS harmonized.sat_month_quality_v02;
CREATE TABLE harmonized.sat_month_quality_v02 (
    month date NOT NULL, sat_code smallint NOT NULL,
    days_in_range int NOT NULL, days_missing int NOT NULL, days_caida int NOT NULL, days_parcial int NOT NULL,
    days_catalog int NOT NULL, days_minutes_low int NOT NULL, days_affected int NOT NULL, complete boolean NOT NULL,
    PRIMARY KEY (month, sat_code));
SELECT format('\copy harmonized.sat_month_quality_v02 FROM %L WITH (FORMAT csv, HEADER)', :'dir' || '/sat_month_quality_v02.csv') \gset c_
:c_format

DROP TABLE IF EXISTS harmonized.reference_plan_v02;
CREATE TABLE harmonized.reference_plan_v02 (
    month date PRIMARY KEY, preferred_sat smallint NOT NULL, ref_sat smallint NOT NULL,
    days_affected int NOT NULL, days_missing int NOT NULL, days_caida int NOT NULL,
    quality_flag smallint NOT NULL,            -- bits de mes (0,1,2,3,4,6); el bit 7 es por fila (cell_month)
    excluded_from_baseline boolean NOT NULL, sensors text NOT NULL);
SELECT format('\copy harmonized.reference_plan_v02 FROM %L WITH (FORMAT csv, HEADER)', :'dir' || '/reference_plan_v02.csv') \gset c_
:c_format

DROP TABLE IF EXISTS harmonized.calibration_coef_v02;
CREATE TABLE harmonized.calibration_coef_v02 (
    method_version text NOT NULL, sat_code smallint NOT NULL, lat_band smallint NOT NULL,
    sector smallint NOT NULL,                  -- 1 Américas (lon < -30), 2 Europa/África, 3 Asia/Oceanía (lon >= 60)
    season smallint NOT NULL,                  -- 1 DEF, 2 MAM, 3 JJA, 4 SON
    alpha double precision NOT NULL, gamma double precision NOT NULL,
    confidence text NOT NULL CHECK (confidence IN ('alta', 'baja')),
    fit_level text NOT NULL,                   -- nivel de la jerarquía usado para el ajuste
    PRIMARY KEY (method_version, sat_code, lat_band, sector, season));
SELECT format('\copy harmonized.calibration_coef_v02 FROM %L WITH (FORMAT csv, HEADER)', :'dir' || '/coeficientes_v02_propuestos.csv') \gset c_
:c_format
SELECT count(*) AS coef_sin_valor FROM harmonized.calibration_coef_v02 WHERE alpha = 'NaN' OR gamma = 'NaN';

DROP TABLE IF EXISTS harmonized.cell_month_v02;
CREATE TABLE harmonized.cell_month_v02 AS
WITH p AS (
  SELECT month, cell_id,
         sum(n_t0_conf) FILTER (WHERE sat_code = 1) AS n_terra, sum(n_t0_conf) FILTER (WHERE sat_code = 2) AS n_aqua,
         sum(n_t0_conf) FILTER (WHERE sat_code = 3) AS n_snpp,  sum(n_t0_conf) FILTER (WHERE sat_code = 4) AS n_n20,
         sum(n_t0_conf) FILTER (WHERE sat_code = 5) AS n_n21,
         sum(frp_t0_conf) FILTER (WHERE sat_code = 1) AS frp_terra, sum(frp_t0_conf) FILTER (WHERE sat_code = 2) AS frp_aqua,
         sum(frp_t0_conf) FILTER (WHERE sat_code = 3) AS frp_snpp,  sum(frp_t0_conf) FILTER (WHERE sat_code = 4) AS frp_n20,
         sum(frp_t0_conf) FILTER (WHERE sat_code = 5) AS frp_n21
    FROM harmonized.cell_month_sat GROUP BY 1, 2),
x AS (
  SELECT p.*, g.lat_center, g.lon_center, g.cell_area_km2, g.lat_band,
         (CASE WHEN g.lon_center < -30 THEN 1 WHEN g.lon_center < 60 THEN 2 ELSE 3 END)::smallint AS sector,
         (CASE WHEN extract(month FROM p.month) IN (12,1,2) THEN 1 WHEN extract(month FROM p.month) IN (3,4,5) THEN 2
               WHEN extract(month FROM p.month) IN (6,7,8) THEN 3 ELSE 4 END)::smallint AS season,
         rp.ref_sat, rp.quality_flag AS flag_mes, rp.sensors,
         CASE rp.ref_sat WHEN 2 THEN p.n_aqua WHEN 3 THEN p.n_snpp WHEN 4 THEN p.n_n20 WHEN 5 THEN p.n_n21 END AS n_ref,
         CASE rp.ref_sat WHEN 2 THEN p.frp_aqua WHEN 3 THEN p.frp_snpp WHEN 4 THEN p.frp_n20 WHEN 5 THEN p.frp_n21 END AS f_ref
    FROM p JOIN harmonized.grid_cell g USING (cell_id) JOIN harmonized.reference_plan_v02 rp USING (month))
SELECT x.month, x.cell_id, x.lat_center, x.lon_center, x.cell_area_km2,
       (CASE WHEN x.ref_sat = 2 THEN coalesce(x.n_ref, 0) ELSE coalesce(x.n_ref, 0) * c.alpha END)::real AS n_eq,
       (CASE WHEN x.ref_sat = 2 THEN coalesce(x.f_ref, 0) ELSE coalesce(x.f_ref, 0) * c.gamma END)::real AS f_eq,
       x.ref_sat, x.sensors,
       coalesce(x.n_terra, 0)::int AS n_terra, coalesce(x.n_aqua, 0)::int AS n_aqua, coalesce(x.n_snpp, 0)::int AS n_snpp,
       coalesce(x.n_n20, 0)::int AS n_n20, coalesce(x.n_n21, 0)::int AS n_n21,
       coalesce(x.frp_terra, 0)::real AS frp_terra, coalesce(x.frp_aqua, 0)::real AS frp_aqua,
       coalesce(x.frp_snpp, 0)::real AS frp_snpp, coalesce(x.frp_n20, 0)::real AS frp_n20, coalesce(x.frp_n21, 0)::real AS frp_n21,
       (x.flag_mes | CASE WHEN x.ref_sat <> 2 AND c.confidence = 'baja' THEN 128 ELSE 0 END)::smallint AS quality_flag,
       'v0.2'::text AS method_version
  FROM x
  LEFT JOIN harmonized.calibration_coef_v02 c
         ON c.method_version = 'v0.2' AND c.sat_code = x.ref_sat AND c.lat_band = x.lat_band
        AND c.sector = x.sector AND c.season = x.season
 ORDER BY x.cell_id, x.month;
ALTER TABLE harmonized.cell_month_v02 ADD PRIMARY KEY (cell_id, month);

-- Controles: sin n_eq nulo, mismas filas y celdas que la v0.1
SELECT count(*) AS filas_v02, count(*) FILTER (WHERE n_eq IS NULL OR f_eq IS NULL) AS nulos,
       (SELECT count(*) FROM harmonized.cell_month) AS filas_v01 FROM harmonized.cell_month_v02;
COMMIT;
ANALYZE harmonized.cell_month_v02;
