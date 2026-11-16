-- Fase 1 / 01: aclaraciones A–E (solo lectura)
\timing on
\pset footer off
SET work_mem = '1GB';
SET max_parallel_workers_per_gather = 0;

\echo '=== D. WAL, archivado y replicación ==='
SELECT name, setting FROM pg_settings
 WHERE name IN ('archive_mode','archive_command','archive_library','wal_level','max_wal_senders',
                'max_replication_slots','checkpoint_timeout','max_wal_size','min_wal_size','fsync','full_page_writes')
 ORDER BY 1;
SELECT count(*) AS slots_replicacion FROM pg_replication_slots;
SELECT count(*) AS conexiones_replicacion FROM pg_stat_replication;
SELECT archived_count, failed_count, last_archived_wal FROM pg_stat_archiver;
SELECT pg_size_pretty(sum(size)) AS pg_wal_actual, count(*) AS segmentos FROM pg_ls_waldir();

\echo '=== E. Conciliación con carga_log ==='
SELECT sum(filas) AS total_cargado,
       sum(filas) FILTER (WHERE archivo LIKE 'fire_nrt_%') AS nrt_eliminado,
       sum(filas) FILTER (WHERE archivo NOT LIKE 'fire_nrt_%') AS archive_vigente
  FROM carga_log;

\echo '=== A. Hora solar local mediana (detecciones diurnas) y scan mediano: enero y julio de cada año ==='
-- NOTA: la primera versión de esta consulta filtraba con IN (generate_series ...), que el BRIN no aprovecha,
-- y recorrió MODIS y S-NPP completos (5 min). Esta versión usa un rango de fechas por mes (BRIN) vía LATERAL.
WITH meses AS (
  SELECT make_date(y, m, 1) AS d0, (make_date(y, m, 1) + interval '1 month')::date AS d1
    FROM generate_series(2012, 2026) y, unnest(ARRAY[1, 7]) m
   WHERE make_date(y, m, 1) <= '2026-07-01'),
x AS (
  SELECT t.* FROM meses, LATERAL (
    SELECT satellite, extract(year FROM acq_date)::int AS anio,
           ((substr(acq_time,1,2)::int * 60 + substr(acq_time,3,2)::int) / 60.0 + longitude / 15.0 + 24)::numeric % 24 AS hsl, scan
      FROM modis WHERE acq_date >= meses.d0 AND acq_date < meses.d1 AND daynight = 'D' AND type = 0
    UNION ALL
    SELECT 'SNPP', extract(year FROM acq_date)::int,
           ((substr(acq_time,1,2)::int * 60 + substr(acq_time,3,2)::int) / 60.0 + longitude / 15.0 + 24)::numeric % 24, scan
      FROM viirs_suomi WHERE acq_date >= meses.d0 AND acq_date < meses.d1 AND daynight = 'D' AND type = 0) t)
SELECT satellite, anio,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY hsl)::numeric, 2) AS hora_local_mediana,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY scan)::numeric, 3) AS scan_mediano,
       round(avg((scan <= 1.5)::int)::numeric, 3) AS frac_scan_casi_nadir, count(*) AS n
  FROM x GROUP BY 1,2 ORDER BY 1,2;

\echo '=== C. Minutos de adquisición distintos por día: días con huecos conocidos vs vecinos ==='
SELECT 'Aqua 2021-09' AS caso, acq_date, count(DISTINCT acq_time) AS minutos, count(*) AS n
  FROM modis WHERE satellite = 'Aqua' AND acq_date BETWEEN '2021-09-19' AND '2021-09-28' GROUP BY acq_date
UNION ALL
SELECT 'SNPP 2016-10', acq_date, count(DISTINCT acq_time), count(*)
  FROM viirs_suomi WHERE acq_date BETWEEN '2016-09-29' AND '2016-10-08' GROUP BY acq_date
UNION ALL
SELECT 'Aqua 2021-01', acq_date, count(DISTINCT acq_time), count(*)
  FROM modis WHERE satellite = 'Aqua' AND acq_date BETWEEN '2020-12-28' AND '2021-01-06' GROUP BY acq_date
ORDER BY 1, 2;
