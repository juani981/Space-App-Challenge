-- Fase 1 / 03: distribución de scan y track de MODIS por satélite y año (enero y julio, type = 0). Solo lectura.
-- Objetivo: definir el criterio casi-nadir relativo al píxel de nadir de cada satélite y año (CONTEXTO 0.19).
\timing on
\pset footer off
SET work_mem = '512MB';

\echo '=== EXPLAIN (debe usar BRIN por mes) ==='
EXPLAIN
WITH meses AS (
  SELECT make_date(y, m, 1) AS d0, (make_date(y, m, 1) + interval '1 month')::date AS d1
    FROM generate_series(2012, 2026) y, unnest(ARRAY[1, 7]) m WHERE make_date(y, m, 1) <= '2026-07-01')
SELECT count(*) FROM meses, LATERAL (SELECT scan FROM modis WHERE acq_date >= meses.d0 AND acq_date < meses.d1 AND type = 0) t;

\echo '=== Percentiles y valores mínimos de scan/track por satélite y año ==='
WITH meses AS (
  SELECT make_date(y, m, 1) AS d0, (make_date(y, m, 1) + interval '1 month')::date AS d1
    FROM generate_series(2012, 2026) y, unnest(ARRAY[1, 7]) m WHERE make_date(y, m, 1) <= '2026-07-01'),
x AS (SELECT t.* FROM meses, LATERAL (
        SELECT satellite, extract(year FROM acq_date)::int AS anio, scan, track
          FROM modis WHERE acq_date >= meses.d0 AND acq_date < meses.d1 AND type = 0) t)
SELECT satellite, anio, count(*) AS n,
       min(scan) AS scan_min, min(track) AS track_min,
       round(avg((scan <= 1.0)::int)::numeric, 3) AS frac_scan_1_0,
       round(avg((track <= 1.0)::int)::numeric, 3) AS frac_track_1_0,
       percentile_disc(0.05) WITHIN GROUP (ORDER BY scan) AS scan_p05,
       percentile_disc(0.25) WITHIN GROUP (ORDER BY scan) AS scan_p25,
       percentile_disc(0.50) WITHIN GROUP (ORDER BY scan) AS scan_p50,
       round(avg((scan <= 1.5)::int)::numeric, 3) AS frac_le_1_5,
       round(avg((scan <= 1.2)::int)::numeric, 3) AS frac_le_1_2,
       round((sum(scan * track) FILTER (WHERE scan <= 1.0) / nullif(count(*) FILTER (WHERE scan <= 1.0), 0))::numeric, 3) AS area_media_en_1_0
  FROM x GROUP BY 1, 2 ORDER BY 1, 2;
