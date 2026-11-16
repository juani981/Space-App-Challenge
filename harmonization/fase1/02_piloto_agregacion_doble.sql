-- Fase 1 / 02: piloto de la agregación doble (diaria por celda + esfuerzo por minutos) en UNA lectura,
-- sobre el mes pico de S-NPP (ago-2024) y sobre MODIS ago-2024. Solo lectura (SELECT, sin INSERT).
\timing on
\pset footer off
SET work_mem = '1GB';

\echo '=== EXPLAIN (sin ANALYZE): debe usar el BRIN ==='
EXPLAIN
WITH src AS MATERIALIZED (
  SELECT acq_date, acq_time, latitude, longitude, type, confidence, daynight, frp, scan FROM viirs_suomi
   WHERE acq_date >= '2024-08-01' AND acq_date < '2024-09-01')
SELECT count(*) FROM src;

\echo '=== S-NPP ago-2024: agregación diaria por celda 0,25° + esfuerzo, en una lectura ==='
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY ON)
WITH src AS MATERIALIZED (
  SELECT acq_date, acq_time, latitude, longitude, type, confidence, daynight, frp, scan,
         (floor((latitude + 90) / 0.25))::int * 1440 + (floor((longitude + 180) / 0.25))::int AS cell_id,
         (floor((latitude + 90) / 0.01))::int AS r1, (floor((longitude + 180) / 0.01))::int AS c1
    FROM viirs_suomi WHERE acq_date >= '2024-08-01' AND acq_date < '2024-09-01'),
k1 AS (
  SELECT acq_date, cell_id, r1, c1,
         count(*) AS n_all, count(*) FILTER (WHERE type = 0) AS n_t0,
         count(*) FILTER (WHERE type = 0 AND confidence <> 'l') AS n_t0_conf,
         count(*) FILTER (WHERE type = 0 AND daynight = 'D') AS n_t0_dia,
         count(*) FILTER (WHERE type = 0 AND scan <= 0.5) AS n_t0_nadir,
         sum(frp) FILTER (WHERE type = 0) AS frp_t0, max(frp) FILTER (WHERE type = 0) AS frp_max
    FROM src GROUP BY 1,2,3,4),
diario AS (
  SELECT acq_date, cell_id, sum(n_all) n_all, sum(n_t0) n_t0, sum(n_t0_conf) n_t0_conf, sum(n_t0_dia) n_t0_dia,
         sum(n_t0_nadir) n_t0_nadir, sum(frp_t0) frp_t0, max(frp_max) frp_max,
         count(*) FILTER (WHERE n_t0 > 0) AS celdas_1km_t0
    FROM k1 GROUP BY 1,2),
esfuerzo AS (
  SELECT acq_date, (floor(latitude / 10) * 10)::int AS lat_band, count(DISTINCT acq_time) AS minutos, count(*) AS n
    FROM src GROUP BY GROUPING SETS ((acq_date, 2), (acq_date)))
SELECT (SELECT count(*) FROM diario) AS filas_diario, (SELECT sum(n_all) FROM diario) AS n_conciliado,
       (SELECT count(*) FROM esfuerzo) AS filas_esfuerzo;

\echo '=== Celdas activas por mes (para dimensionar tablas mensuales y consultas de la app) ==='
SELECT 'ago-2024' AS mes,
  (SELECT count(DISTINCT (floor((latitude+90)/0.25))::int*1440 + (floor((longitude+180)/0.25))::int) FROM modis WHERE satellite='Aqua' AND acq_date >= '2024-08-01' AND acq_date < '2024-09-01') AS celdas_aqua,
  (SELECT count(DISTINCT (floor((latitude+90)/0.25))::int*1440 + (floor((longitude+180)/0.25))::int) FROM modis WHERE satellite='Terra' AND acq_date >= '2024-08-01' AND acq_date < '2024-09-01') AS celdas_terra,
  (SELECT count(DISTINCT (floor((latitude+90)/0.25))::int*1440 + (floor((longitude+180)/0.25))::int) FROM viirs_suomi WHERE acq_date >= '2024-08-01' AND acq_date < '2024-09-01') AS celdas_snpp,
  (SELECT count(DISTINCT (floor((latitude+90)/0.25))::int*1440 + (floor((longitude+180)/0.25))::int) FROM viirs_j1 WHERE acq_date >= '2024-08-01' AND acq_date < '2024-09-01') AS celdas_n20,
  (SELECT count(DISTINCT (floor((latitude+90)/0.25))::int*1440 + (floor((longitude+180)/0.25))::int) FROM viirs_j2 WHERE acq_date >= '2024-08-01' AND acq_date < '2024-09-01') AS celdas_n21
UNION ALL
SELECT 'ene-2026',
  (SELECT count(DISTINCT (floor((latitude+90)/0.25))::int*1440 + (floor((longitude+180)/0.25))::int) FROM modis WHERE satellite='Aqua' AND acq_date >= '2026-01-01' AND acq_date < '2026-02-01'),
  (SELECT count(DISTINCT (floor((latitude+90)/0.25))::int*1440 + (floor((longitude+180)/0.25))::int) FROM modis WHERE satellite='Terra' AND acq_date >= '2026-01-01' AND acq_date < '2026-02-01'),
  (SELECT count(DISTINCT (floor((latitude+90)/0.25))::int*1440 + (floor((longitude+180)/0.25))::int) FROM viirs_suomi WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01'),
  (SELECT count(DISTINCT (floor((latitude+90)/0.25))::int*1440 + (floor((longitude+180)/0.25))::int) FROM viirs_j1 WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01'),
  (SELECT count(DISTINCT (floor((latitude+90)/0.25))::int*1440 + (floor((longitude+180)/0.25))::int) FROM viirs_j2 WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01');

\echo '=== Celdas distintas activas en todo 2024 (S-NPP y Aqua): techo de celdas por AOI ==='
EXPLAIN SELECT count(DISTINCT (floor((latitude+90)/0.25))::int*1440 + (floor((longitude+180)/0.25))::int) FROM modis WHERE satellite='Aqua' AND acq_date >= '2024-01-01' AND acq_date < '2025-01-01';
SELECT count(DISTINCT (floor((latitude+90)/0.25))::int*1440 + (floor((longitude+180)/0.25))::int) AS celdas_aqua_2024 FROM modis WHERE satellite='Aqua' AND acq_date >= '2024-01-01' AND acq_date < '2025-01-01';
