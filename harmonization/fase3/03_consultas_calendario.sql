-- =============================================================================
-- fase3/03_consultas_calendario.sql  (base wildfire-armonizado)
-- Mide con EXPLAIN (ANALYZE, BUFFERS) las consultas tipo de la app sobre
-- harmonized.cell_month (PK actual: (cell_id, month)) y compara índices
-- alternativos sobre una COPIA TEMPORAL de sesión (no modifica la tabla).
-- Rectángulos: celdas cuyo CENTRO cae dentro (como en el diseño).
-- =============================================================================
\set ON_ERROR_STOP on
\pset footer off
SET work_mem = '256MB';

-- Rectángulos de prueba: (nombre, lat_min, lat_max, lon_min, lon_max)
CREATE TEMP TABLE aoi AS
SELECT nombre,
       ceil((lat_min + 90) / 0.25 - 0.5)::int AS r0, floor((lat_max + 90) / 0.25 - 0.5)::int AS r1,
       ceil((lon_min + 180) / 0.25 - 0.5)::int AS c0, floor((lon_max + 180) / 0.25 - 0.5)::int AS c1
  FROM (VALUES ('chica_cordoba',  -35.0, -29.5, -65.8, -61.8),
               ('media_2000',     -35.0, -24.0, -66.0, -54.0),
               ('grande_argentina',-55.0, -22.0, -73.5, -53.5),
               ('sudamerica',     -56.0,  13.0, -82.0, -34.0)) v(nombre, lat_min, lat_max, lon_min, lon_max);
SELECT nombre, (r1 - r0 + 1) * (c1 - c0 + 1) AS celdas, r1 - r0 + 1 AS rangos FROM aoi;

-- Consulta del calendario (una fila por mes) para un AOI
CREATE OR REPLACE FUNCTION pg_temp.q_cal(p text, tabla text) RETURNS SETOF text LANGUAGE plpgsql AS $$
DECLARE a record; l text;
BEGIN
  SELECT * INTO a FROM aoi WHERE nombre = p;
  FOR l IN EXECUTE format($q$EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
     SELECT m.month, sum(m.n_eq), sum(m.f_eq), bit_or(m.quality_flag), count(*)
       FROM generate_series(%s, %s) r JOIN %s m ON m.cell_id BETWEEN r * 1440 + %s AND r * 1440 + %s
      GROUP BY m.month ORDER BY m.month$q$, a.r0, a.r1, tabla, a.c0, a.c1)
  LOOP
    IF l ~ '(Execution Time|Index|Seq Scan|Buffers: shared|Heap Fetches)' THEN RETURN NEXT l; END IF;
  END LOOP;
END $$;

\echo '##### A. Tabla real, índice actual PK (cell_id, month) — 1ª y 2ª ejecución'
SELECT nombre, x FROM aoi, LATERAL pg_temp.q_cal(nombre, 'harmonized.cell_month') x;
SELECT nombre, x FROM aoi, LATERAL pg_temp.q_cal(nombre, 'harmonized.cell_month') x WHERE x ~ 'Execution';

\echo '##### A. Capa de mapa de un mes (todas las celdas de ago-2024) con el índice actual'
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF) SELECT cell_id, n_eq, f_eq, quality_flag FROM harmonized.cell_month WHERE month = '2024-08-01';
\echo '##### A. Serie global (suma de toda la tabla por mes)'
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF) SELECT month, sum(n_eq) FROM harmonized.cell_month GROUP BY month;

\echo '##### Copia temporal de sesión para probar índices alternativos'
\timing on
CREATE TEMP TABLE cm AS SELECT * FROM harmonized.cell_month ORDER BY cell_id, month;
CREATE INDEX cm_cubriente ON cm (cell_id, month) INCLUDE (n_eq, f_eq, quality_flag);
VACUUM ANALYZE cm;
SELECT pg_size_pretty(pg_relation_size('cm_cubriente')) AS indice_cubriente;
\timing off

\echo '##### B. Índice cubriente (cell_id, month) INCLUDE (n_eq, f_eq, quality_flag) — index-only scan'
SELECT nombre, x FROM aoi, LATERAL pg_temp.q_cal(nombre, 'cm') x;
SELECT nombre, x FROM aoi, LATERAL pg_temp.q_cal(nombre, 'cm') x WHERE x ~ 'Execution';

\echo '##### C. Índice (month, cell_id) para la capa de mapa de un mes'
\timing on
CREATE INDEX cm_mes ON cm (month, cell_id) INCLUDE (n_eq, f_eq, quality_flag);
\timing off
SELECT pg_size_pretty(pg_relation_size('cm_mes')) AS indice_mes;
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF) SELECT cell_id, n_eq, f_eq, quality_flag FROM cm WHERE month = '2024-08-01';
\echo '##### C. ¿Con (month, cell_id) el calendario de un AOI empeora? (forzando ese índice)'
DROP INDEX cm_cubriente;
SELECT nombre, x FROM aoi, LATERAL pg_temp.q_cal(nombre, 'cm') x WHERE x ~ 'Execution|Index';
