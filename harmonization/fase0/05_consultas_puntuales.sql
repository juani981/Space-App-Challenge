-- Fase 0 / 05: consultas puntuales acotadas por BRIN. Solo lectura.
\timing on
\pset footer off
SET work_mem = '256MB';

\echo '=== (b) Filas anteriores a 2012 ==='
SELECT 'modis' t, count(*) FROM modis WHERE acq_date < '2012-01-01'
UNION ALL SELECT 'viirs_suomi', count(*) FROM viirs_suomi WHERE acq_date < '2012-01-01'
UNION ALL SELECT 'viirs_j1', count(*) FROM viirs_j1 WHERE acq_date < '2012-01-01'
UNION ALL SELECT 'viirs_j2', count(*) FROM viirs_j2 WHERE acq_date < '2012-01-01';

\echo '=== Filas antes de las ventanas de inicio (deben ser 0 para que los mínimos sean válidos) ==='
SELECT 'viirs_j1 < 2018-01-01' t, count(*) FROM viirs_j1 WHERE acq_date < '2018-01-01'
UNION ALL SELECT 'viirs_j2 < 2023-01-01', count(*) FROM viirs_j2 WHERE acq_date < '2023-01-01'
UNION ALL SELECT 'filas > 2026-08-31 (todas)', (SELECT count(*) FROM modis WHERE acq_date > '2026-08-31')
   + (SELECT count(*) FROM viirs_suomi WHERE acq_date > '2026-07-31')
   + (SELECT count(*) FROM viirs_j1 WHERE acq_date > '2026-07-31')
   + (SELECT count(*) FROM viirs_j2 WHERE acq_date > '2026-07-31');

\echo '=== (a) Mínimo por tabla y satélite ==='
SELECT 'modis' t, satellite, min(acq_date), min(acq_date + acq_time::time) AS primera_obs FROM modis WHERE acq_date < '2012-02-01' GROUP BY 2
UNION ALL SELECT 'viirs_suomi', satellite, min(acq_date), min(acq_date + acq_time::time) FROM viirs_suomi WHERE acq_date < '2012-03-01' GROUP BY 2
UNION ALL SELECT 'viirs_j1', satellite, min(acq_date), min(acq_date + acq_time::time) FROM viirs_j1 WHERE acq_date < '2018-06-01' GROUP BY 2
UNION ALL SELECT 'viirs_j2', satellite, min(acq_date), min(acq_date + acq_time::time) FROM viirs_j2 WHERE acq_date < '2023-06-01' GROUP BY 2
ORDER BY 1,2;

\echo '=== (a) Máximo por tabla y satélite ==='
SELECT 'modis' t, satellite, max(acq_date), max(acq_date + acq_time::time) AS ultima_obs FROM modis WHERE acq_date >= '2026-06-01' GROUP BY 2
UNION ALL SELECT 'viirs_suomi', satellite, max(acq_date), max(acq_date + acq_time::time) FROM viirs_suomi WHERE acq_date >= '2026-06-01' GROUP BY 2
UNION ALL SELECT 'viirs_j1', satellite, max(acq_date), max(acq_date + acq_time::time) FROM viirs_j1 WHERE acq_date >= '2026-06-01' GROUP BY 2
UNION ALL SELECT 'viirs_j2', satellite, max(acq_date), max(acq_date + acq_time::time) FROM viirs_j2 WHERE acq_date >= '2026-06-01' GROUP BY 2
ORDER BY 1,2;
