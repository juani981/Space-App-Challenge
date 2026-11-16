-- Fase 0 / 06: piloto ene-2026 (4 tablas). Solo lectura.
\timing on
\pset footer off
SET work_mem = '512MB';

\echo '=== Duplicados por (acq_date, acq_time, satellite, latitude, longitude) y duplicados exactos ==='
SELECT 'modis' t,
  (SELECT count(*) FROM modis WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01') AS filas,
  (SELECT coalesce(sum(c-1),0) FROM (SELECT count(*) c FROM modis WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01' GROUP BY acq_date, acq_time, satellite, latitude, longitude HAVING count(*)>1) x) AS dup_clave,
  (SELECT coalesce(sum(c-1),0) FROM (SELECT count(*) c FROM modis WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01' GROUP BY latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, confidence, version, bright_t31, frp, daynight, type HAVING count(*)>1) x) AS dup_exactos
UNION ALL SELECT 'viirs_suomi',
  (SELECT count(*) FROM viirs_suomi WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01'),
  (SELECT coalesce(sum(c-1),0) FROM (SELECT count(*) c FROM viirs_suomi WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01' GROUP BY acq_date, acq_time, satellite, latitude, longitude HAVING count(*)>1) x),
  (SELECT coalesce(sum(c-1),0) FROM (SELECT count(*) c FROM viirs_suomi WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01' GROUP BY latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, confidence, version, bright_t31, frp, daynight, type HAVING count(*)>1) x)
UNION ALL SELECT 'viirs_j1',
  (SELECT count(*) FROM viirs_j1 WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01'),
  (SELECT coalesce(sum(c-1),0) FROM (SELECT count(*) c FROM viirs_j1 WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01' GROUP BY acq_date, acq_time, satellite, latitude, longitude HAVING count(*)>1) x),
  (SELECT coalesce(sum(c-1),0) FROM (SELECT count(*) c FROM viirs_j1 WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01' GROUP BY latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, confidence, version, bright_t31, frp, daynight, type HAVING count(*)>1) x)
UNION ALL SELECT 'viirs_j2',
  (SELECT count(*) FROM viirs_j2 WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01'),
  (SELECT coalesce(sum(c-1),0) FROM (SELECT count(*) c FROM viirs_j2 WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01' GROUP BY acq_date, acq_time, satellite, latitude, longitude HAVING count(*)>1) x),
  (SELECT coalesce(sum(c-1),0) FROM (SELECT count(*) c FROM viirs_j2 WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01' GROUP BY latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, confidence, version, bright_t31, frp, daynight, type HAVING count(*)>1) x);

\echo '=== Perfil del mes por tabla (nulos, rangos, FRP<=0, type, confianza, día/noche, scan/track) ==='
SELECT 'modis' t, satellite, count(*) n,
  count(*) FILTER (WHERE type=0) t0, count(*) FILTER (WHERE type=1) t1, count(*) FILTER (WHERE type=2) t2, count(*) FILTER (WHERE type=3) t3, count(*) FILTER (WHERE type IS NULL) t_null,
  count(*) FILTER (WHERE confidence < 30) conf_baja, count(*) FILTER (WHERE confidence >= 30 AND confidence < 80) conf_nom, count(*) FILTER (WHERE confidence >= 80) conf_alta,
  count(*) FILTER (WHERE daynight='D') dia, count(*) FILTER (WHERE frp <= 0) frp_le0, count(*) FILTER (WHERE frp IS NULL) frp_null,
  count(*) FILTER (WHERE brightness IS NULL OR scan IS NULL OR track IS NULL OR bright_t31 IS NULL OR confidence IS NULL OR daynight IS NULL) otros_null,
  count(*) FILTER (WHERE acq_time !~ '^([01][0-9]|2[0-3])[0-5][0-9]$') hora_mal,
  round(min(scan)::numeric,2) scan_min, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY scan)::numeric,2) scan_med, round(max(scan)::numeric,2) scan_max,
  round(min(latitude)::numeric,2) lat_min, round(max(latitude)::numeric,2) lat_max, round(min(longitude)::numeric,2) lon_min, round(max(longitude)::numeric,2) lon_max,
  count(DISTINCT acq_date) dias
FROM modis WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01' GROUP BY satellite
UNION ALL
SELECT tn, satellite, count(*),
  count(*) FILTER (WHERE type=0), count(*) FILTER (WHERE type=1), count(*) FILTER (WHERE type=2), count(*) FILTER (WHERE type=3), count(*) FILTER (WHERE type IS NULL),
  count(*) FILTER (WHERE confidence='l'), count(*) FILTER (WHERE confidence='n'), count(*) FILTER (WHERE confidence='h'),
  count(*) FILTER (WHERE daynight='D'), count(*) FILTER (WHERE frp <= 0), count(*) FILTER (WHERE frp IS NULL),
  count(*) FILTER (WHERE brightness IS NULL OR scan IS NULL OR track IS NULL OR bright_t31 IS NULL OR confidence IS NULL OR daynight IS NULL),
  count(*) FILTER (WHERE acq_time !~ '^([01][0-9]|2[0-3])[0-5][0-9]$'),
  round(min(scan)::numeric,2), round(percentile_cont(0.5) WITHIN GROUP (ORDER BY scan)::numeric,2), round(max(scan)::numeric,2),
  round(min(latitude)::numeric,2), round(max(latitude)::numeric,2), round(min(longitude)::numeric,2), round(max(longitude)::numeric,2),
  count(DISTINCT acq_date)
FROM (SELECT 'viirs_suomi' tn, * FROM viirs_suomi WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01'
      UNION ALL SELECT 'viirs_j1', * FROM viirs_j1 WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01'
      UNION ALL SELECT 'viirs_j2', * FROM viirs_j2 WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01') v
GROUP BY tn, satellite ORDER BY 1;

\echo '=== Velocidad de la pasada de perfil (S-NPP, ene-2026) ==='
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT acq_date, satellite, (floor(latitude/10)*10)::int AS lat_band, count(*),
  count(*) FILTER (WHERE type=0), sum(frp) FILTER (WHERE type=0), count(*) FILTER (WHERE confidence='l'),
  count(*) FILTER (WHERE daynight='D'), count(*) FILTER (WHERE frp<=0), sum(scan)
FROM viirs_suomi WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01' GROUP BY 1,2,3;

\echo '=== Agregación tipo Fase 2 (S-NPP, ene-2026): día x celda 0,25° x satélite, con celdas ~1 km ocupadas ==='
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
WITH k AS (
  SELECT acq_date, satellite,
         (floor((latitude + 90) / 0.25) * 1440 + floor((longitude + 180) / 0.25))::int AS cell_025,
         (floor((latitude + 90) / 0.01) * 36000 + floor((longitude + 180) / 0.01))::bigint AS cell_001,
         type, confidence, daynight, frp
    FROM viirs_suomi WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01'
), c1 AS (
  SELECT acq_date, satellite, cell_025, cell_001,
         count(*) FILTER (WHERE type = 0) AS n_t0,
         count(*) FILTER (WHERE type = 0 AND confidence <> 'l') AS n_t0_conf,
         count(*) FILTER (WHERE type = 0 AND daynight = 'D') AS n_t0_dia,
         sum(frp) FILTER (WHERE type = 0) AS frp_sum, max(frp) FILTER (WHERE type = 0) AS frp_max,
         count(*) AS n_all
    FROM k GROUP BY 1,2,3,4
)
SELECT acq_date, satellite, cell_025, sum(n_all) n_all, sum(n_t0) n_t0, sum(n_t0_conf) n_t0_conf, sum(n_t0_dia) n_t0_dia,
       sum(frp_sum) frp_sum, max(frp_max) frp_max, count(*) FILTER (WHERE n_t0 > 0) AS celdas_1km_t0
  FROM c1 GROUP BY 1,2,3;

\echo '=== Filas resultantes de la agregación tipo Fase 2 por tabla (ene-2026) ==='
SELECT 'modis' t, count(*) FROM (SELECT DISTINCT acq_date, satellite, (floor((latitude + 90) / 0.25) * 1440 + floor((longitude + 180) / 0.25))::int FROM modis WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01') x
UNION ALL SELECT 'viirs_suomi', count(*) FROM (SELECT DISTINCT acq_date, (floor((latitude + 90) / 0.25) * 1440 + floor((longitude + 180) / 0.25))::int FROM viirs_suomi WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01') x
UNION ALL SELECT 'viirs_j1', count(*) FROM (SELECT DISTINCT acq_date, (floor((latitude + 90) / 0.25) * 1440 + floor((longitude + 180) / 0.25))::int FROM viirs_j1 WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01') x
UNION ALL SELECT 'viirs_j2', count(*) FROM (SELECT DISTINCT acq_date, (floor((latitude + 90) / 0.25) * 1440 + floor((longitude + 180) / 0.25))::int FROM viirs_j2 WHERE acq_date >= '2026-01-01' AND acq_date < '2026-02-01') x;
