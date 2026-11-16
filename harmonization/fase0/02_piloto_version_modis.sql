-- Fase 0 / 02: piloto de un mes (ene-2023) para versiones de MODIS
\timing on
SET work_mem = '256MB';
EXPLAIN
SELECT satellite, version, count(*), min(acq_date), max(acq_date)
  FROM modis
 WHERE acq_date >= '2023-01-01' AND acq_date < '2023-02-01'
 GROUP BY 1,2;

EXPLAIN (ANALYZE, BUFFERS)
SELECT satellite, version, count(*), min(acq_date), max(acq_date)
  FROM modis
 WHERE acq_date >= '2023-01-01' AND acq_date < '2023-02-01'
 GROUP BY 1,2;
