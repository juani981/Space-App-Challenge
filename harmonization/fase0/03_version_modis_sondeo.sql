-- Fase 0 / 03: versiones de MODIS y salto en conteos/FRP
\timing on
\pset footer off
SET work_mem = '256MB';

\echo '=== A. Sondeo por año: versión en la 1a y última semana de cada año ==='
SELECT extract(year FROM acq_date)::int AS anio,
       CASE WHEN extract(month FROM acq_date) = 1 THEN 'ene' ELSE 'dic' END AS extremo,
       satellite, version, count(*) AS filas
  FROM modis
 WHERE (extract(month FROM acq_date) = 1  AND extract(day FROM acq_date) <= 7
        OR extract(month FROM acq_date) = 12 AND extract(day FROM acq_date) >= 25)
   AND acq_date IN (SELECT d::date FROM generate_series('2012-01-01'::date, '2026-12-31', '1 day') d
                     WHERE (extract(month FROM d) = 1 AND extract(day FROM d) <= 7)
                        OR (extract(month FROM d) = 12 AND extract(day FROM d) >= 25))
 GROUP BY 1,2,3,4 ORDER BY 1, 2 DESC, 3, 4;

\echo '=== B. Fecha exacta del cambio de versión (nov-2022 a feb-2023, por día) ==='
SELECT satellite, version, min(acq_date) AS desde, max(acq_date) AS hasta, count(*) AS filas
  FROM modis
 WHERE acq_date >= '2022-11-01' AND acq_date < '2023-03-01'
 GROUP BY 1,2 ORDER BY 1, 3;

