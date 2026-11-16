-- =============================================================================
-- 012_calibracion_y_tabla_armonizada.sql  (method_version v0.1-provisional)
-- Trabaja SOLO sobre agregados mensuales (no lee tablas crudas):
--  * harmonized.calibration_coef : α (conteos) y γ (FRP) por satélite VIIRS, banda 10° y estación
--      α_SNPP = ΣN_Aqua/ΣN_SNPP           en 2012-02..2020-12
--      α_N20  = α_SNPP · ΣN_SNPP/ΣN_N20   en 2018-04..2021-12
--      α_N21  = α_N20  · ΣN_N20/ΣN_N21    en 2023-03..2026-07
--    Solo meses completos de ambos satélites (< 5 días faltantes o caídos). Multiplicativo y sin
--    intercepto (6d.1). Respaldo: misma estación global, luego global anual, si hay < 200 focos.
--  * harmonized.reference_plan   : satélite de referencia por mes (provisional) y bandera de calidad
--  * harmonized.cell_month       : TABLA ARMONIZADA FINAL (mes × celda 0,25°), valores aditivos
-- Unidad: focos y MW "equivalentes Aqua" definidos por 2012–2020. Conteos type = 0 sin confianza baja.
-- =============================================================================
\set ON_ERROR_STOP on
\timing on
SET work_mem = '1GB';
BEGIN;

CREATE TEMP TABLE b ON COMMIT DROP AS
SELECT s.month, s.sat_code, g.lat_band,
       (CASE WHEN extract(month FROM s.month) IN (12,1,2) THEN 1 WHEN extract(month FROM s.month) IN (3,4,5) THEN 2
             WHEN extract(month FROM s.month) IN (6,7,8) THEN 3 ELSE 4 END)::smallint AS season,
       sum(s.n_t0_conf)::float8 AS n, sum(s.frp_t0_conf) AS f
  FROM harmonized.cell_month_sat s JOIN harmonized.grid_cell g USING (cell_id)
 GROUP BY 1,2,3,4;

CREATE TEMP TABLE ok_month ON COMMIT DROP AS
SELECT month, sat_code FROM harmonized.sat_month_quality WHERE days_missing + days_caida < 5;

-- Razones por paso de la cadena, con respaldos (GROUPING SETS)
CREATE TEMP TABLE pr ON COMMIT DROP AS
WITH pairs(step, sat_num, sat_den, d0, d1) AS (VALUES
   (1, 2::smallint, 3::smallint, date '2012-02-01', date '2020-12-01'),
   (2, 3::smallint, 4::smallint, date '2018-04-01', date '2021-12-01'),
   (3, 4::smallint, 5::smallint, date '2023-03-01', date '2026-07-01'))
SELECT p.step,
       CASE WHEN grouping(bn.lat_band) = 1 THEN -999 ELSE bn.lat_band END::smallint AS lat_band,
       CASE WHEN grouping(bn.season) = 1 THEN 0 ELSE bn.season END::smallint AS season,
       sum(bn.n) AS n_num, sum(bd.n) AS n_den, sum(bn.f) AS f_num, sum(bd.f) AS f_den,
       min(p.d0) AS d0, max(p.d1) AS d1
  FROM pairs p
  JOIN b bn ON bn.sat_code = p.sat_num AND bn.month BETWEEN p.d0 AND p.d1
  JOIN b bd ON bd.sat_code = p.sat_den AND bd.month = bn.month AND bd.lat_band = bn.lat_band
  JOIN ok_month o1 ON o1.month = bn.month AND o1.sat_code = p.sat_num
  JOIN ok_month o2 ON o2.month = bn.month AND o2.sat_code = p.sat_den
 GROUP BY GROUPING SETS ((p.step, bn.lat_band, bn.season), (p.step, bn.season), (p.step));

-- Razón efectiva por (paso, banda, estación) con respaldo
CREATE TEMP TABLE r_eff ON COMMIT DROP AS
SELECT s.step, bs.lat_band, bs.season,
       coalesce(f1.n_num / f1.n_den, f2.n_num / f2.n_den, f3.n_num / f3.n_den) AS rn,
       coalesce(f1.f_num / f1.f_den, f2.f_num / f2.f_den, f3.f_num / f3.f_den) AS rf,
       coalesce(f1.n_num, f2.n_num, f3.n_num) AS n_num, coalesce(f1.n_den, f2.n_den, f3.n_den) AS n_den,
       coalesce(f1.d0, f2.d0, f3.d0) AS d0, coalesce(f1.d1, f2.d1, f3.d1) AS d1
  FROM (SELECT DISTINCT lat_band, season FROM b
        UNION SELECT -999::smallint, s FROM generate_series(0, 4) s) bs
 CROSS JOIN (VALUES (1), (2), (3)) s(step)
  LEFT JOIN pr f1 ON f1.step = s.step AND f1.lat_band = bs.lat_band AND f1.season = bs.season
                 AND f1.n_num >= 200 AND f1.n_den >= 200 AND f1.f_den > 0
  LEFT JOIN pr f2 ON f2.step = s.step AND f2.lat_band = -999 AND f2.season = bs.season AND bs.season > 0
                 AND f2.n_num >= 200 AND f2.n_den >= 200
  LEFT JOIN pr f3 ON f3.step = s.step AND f3.lat_band = -999 AND f3.season = 0;

DROP TABLE IF EXISTS harmonized.calibration_coef;
CREATE TABLE harmonized.calibration_coef (
    method_version text     NOT NULL,
    sat_code       smallint NOT NULL,
    lat_band       smallint NOT NULL,   -- -999 = global
    season         smallint NOT NULL,   -- 1 DEF, 2 MAM, 3 JJA, 4 SON; 0 = todo el año
    alpha          double precision NOT NULL,  -- focos equivalentes Aqua por foco del satélite
    gamma          double precision NOT NULL,  -- MW equivalentes Aqua por MW del satélite
    n_num          double precision,
    n_den          double precision,
    fit_from       date,
    fit_to         date,
    PRIMARY KEY (method_version, sat_code, lat_band, season)
);
INSERT INTO harmonized.calibration_coef
SELECT 'v0.1-provisional', 3, r1.lat_band, r1.season, r1.rn, r1.rf, r1.n_num, r1.n_den, r1.d0, r1.d1
  FROM r_eff r1 WHERE r1.step = 1
UNION ALL
SELECT 'v0.1-provisional', 4, r1.lat_band, r1.season, r1.rn * r2.rn, r1.rf * r2.rf, r2.n_num, r2.n_den, r2.d0, r2.d1
  FROM r_eff r1 JOIN r_eff r2 ON r2.step = 2 AND r2.lat_band = r1.lat_band AND r2.season = r1.season WHERE r1.step = 1
UNION ALL
SELECT 'v0.1-provisional', 5, r1.lat_band, r1.season, r1.rn * r2.rn * r3.rn, r1.rf * r2.rf * r3.rf, r3.n_num, r3.n_den, r3.d0, r3.d1
  FROM r_eff r1 JOIN r_eff r2 ON r2.step = 2 AND r2.lat_band = r1.lat_band AND r2.season = r1.season
                JOIN r_eff r3 ON r3.step = 3 AND r3.lat_band = r1.lat_band AND r3.season = r1.season WHERE r1.step = 1;

-- ---------- Plan de referencia por mes (provisional; se confirma con el test de escalones, Fase 3) ----------
DROP TABLE IF EXISTS harmonized.reference_plan;
CREATE TABLE harmonized.reference_plan AS
WITH m AS (
  SELECT d AS month,
         CASE WHEN d = date '2026-08-01' THEN ARRAY[2]::smallint[]
              WHEN d < date '2020-01-01' THEN ARRAY[3, 4]::smallint[]
              ELSE ARRAY[4, 5, 3]::smallint[] END AS pref
    FROM (SELECT (date '2012-01-01' + make_interval(months => i))::date AS d FROM generate_series(0, 175) i) g),
c AS (
  SELECT m.month, m.pref,
         (SELECT u.s FROM unnest(m.pref) WITH ORDINALITY u(s, o)
           WHERE EXISTS (SELECT 1 FROM ok_month k WHERE k.month = m.month AND k.sat_code = u.s) ORDER BY o LIMIT 1) AS ok_sat,
         (SELECT u.s FROM unnest(m.pref) WITH ORDINALITY u(s, o)
           WHERE EXISTS (SELECT 1 FROM harmonized.sat_month_quality q WHERE q.month = m.month AND q.sat_code = u.s) ORDER BY o LIMIT 1) AS any_sat
    FROM m)
SELECT c.month, c.pref[1] AS preferred_sat, coalesce(c.ok_sat, c.any_sat) AS ref_sat,
       q.days_missing, q.days_caida,
       (  (CASE WHEN c.month = '2012-01-01' THEN 1 ELSE 0 END)
        + (CASE WHEN c.month IN ('2026-07-01', '2026-08-01') THEN 2 ELSE 0 END)
        + (CASE WHEN c.month = '2026-08-01' THEN 4 ELSE 0 END)
        + (CASE WHEN q.days_missing >= 5 THEN 8 ELSE 0 END)
        + (CASE WHEN q.days_caida >= 5 THEN 16 ELSE 0 END)
        + (CASE WHEN coalesce(c.ok_sat, c.any_sat) <> c.pref[1] THEN 64 ELSE 0 END)
        + 128)::smallint AS quality_flag,
       CASE WHEN c.month = '2026-08-01' THEN 'Aqua (solo MODIS / deriva)'
            ELSE ds.raw_satellite || CASE WHEN coalesce(c.ok_sat, c.any_sat) <> c.pref[1]
                                          THEN ' (respaldo de ' || dp.raw_satellite || ')' ELSE '' END END AS sensors
  FROM c
  JOIN harmonized.dim_satellite ds ON ds.sat_code = coalesce(c.ok_sat, c.any_sat)
  JOIN harmonized.dim_satellite dp ON dp.sat_code = c.pref[1]
  LEFT JOIN harmonized.sat_month_quality q ON q.month = c.month AND q.sat_code = coalesce(c.ok_sat, c.any_sat);
ALTER TABLE harmonized.reference_plan ADD PRIMARY KEY (month);

-- ---------- Tabla armonizada final ----------
DROP TABLE IF EXISTS harmonized.cell_month;
CREATE TABLE harmonized.cell_month AS
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
  SELECT p.*, g.lat_center, g.lon_center, g.cell_area_km2, g.lat_band, rp.ref_sat, rp.quality_flag, rp.sensors,
         (CASE WHEN extract(month FROM p.month) IN (12,1,2) THEN 1 WHEN extract(month FROM p.month) IN (3,4,5) THEN 2
               WHEN extract(month FROM p.month) IN (6,7,8) THEN 3 ELSE 4 END)::smallint AS season,
         CASE rp.ref_sat WHEN 2 THEN p.n_aqua WHEN 3 THEN p.n_snpp WHEN 4 THEN p.n_n20 WHEN 5 THEN p.n_n21 END AS n_ref,
         CASE rp.ref_sat WHEN 2 THEN p.frp_aqua WHEN 3 THEN p.frp_snpp WHEN 4 THEN p.frp_n20 WHEN 5 THEN p.frp_n21 END AS f_ref
    FROM p JOIN harmonized.grid_cell g USING (cell_id) JOIN harmonized.reference_plan rp USING (month))
SELECT x.month, x.cell_id, x.lat_center, x.lon_center, x.cell_area_km2,
       (CASE WHEN x.ref_sat = 2 THEN coalesce(x.n_ref, 0)
             ELSE coalesce(x.n_ref, 0) * coalesce(c.alpha, cg.alpha) END)::real AS n_eq,
       (CASE WHEN x.ref_sat = 2 THEN coalesce(x.f_ref, 0)
             ELSE coalesce(x.f_ref, 0) * coalesce(c.gamma, cg.gamma) END)::real AS f_eq,
       x.ref_sat, x.sensors,
       coalesce(x.n_terra, 0)::int AS n_terra, coalesce(x.n_aqua, 0)::int AS n_aqua, coalesce(x.n_snpp, 0)::int AS n_snpp,
       coalesce(x.n_n20, 0)::int AS n_n20, coalesce(x.n_n21, 0)::int AS n_n21,
       coalesce(x.frp_terra, 0)::real AS frp_terra, coalesce(x.frp_aqua, 0)::real AS frp_aqua,
       coalesce(x.frp_snpp, 0)::real AS frp_snpp, coalesce(x.frp_n20, 0)::real AS frp_n20, coalesce(x.frp_n21, 0)::real AS frp_n21,
       x.quality_flag, 'v0.1-provisional'::text AS method_version
  FROM x
  LEFT JOIN harmonized.calibration_coef c  ON c.method_version = 'v0.1-provisional' AND c.sat_code = x.ref_sat
                                          AND c.lat_band = x.lat_band AND c.season = x.season
  LEFT JOIN harmonized.calibration_coef cg ON cg.method_version = 'v0.1-provisional' AND cg.sat_code = x.ref_sat
                                          AND cg.lat_band = -999 AND cg.season = x.season
 ORDER BY x.cell_id, x.month;
ALTER TABLE harmonized.cell_month ADD PRIMARY KEY (cell_id, month);
COMMIT;
ANALYZE harmonized.cell_month;
