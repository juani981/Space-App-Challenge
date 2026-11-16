-- =============================================================================
-- fase3/06_indice_mapa.sql  (base wildfire-armonizado; COPIA TEMPORAL de sesión)
-- ¿El índice (month, cell_id) INCLUDE (...) para la capa de mapa empeora el
-- calendario cuando convive con el índice (cell_id, month) de la clave primaria?
-- La medición anterior (03) lo probó SIN el índice (cell_id, month) presente.
-- =============================================================================
\set ON_ERROR_STOP on
\pset footer off
SET work_mem = '256MB';
CREATE TEMP TABLE aoi AS
SELECT nombre, ceil((lat_min + 90) / 0.25 - 0.5)::int AS r0, floor((lat_max + 90) / 0.25 - 0.5)::int AS r1,
       ceil((lon_min + 180) / 0.25 - 0.5)::int AS c0, floor((lon_max + 180) / 0.25 - 0.5)::int AS c1
  FROM (VALUES ('chica_cordoba', -35.0, -29.5, -65.8, -61.8), ('media_2000', -35.0, -24.0, -66.0, -54.0),
               ('grande_argentina', -55.0, -22.0, -73.5, -53.5), ('sudamerica', -56.0, 13.0, -82.0, -34.0)) v(nombre, lat_min, lat_max, lon_min, lon_max);
CREATE OR REPLACE FUNCTION pg_temp.q_cal(p text) RETURNS SETOF text LANGUAGE plpgsql AS $$
DECLARE a record; l text;
BEGIN
  SELECT * INTO a FROM aoi WHERE nombre = p;
  FOR l IN EXECUTE format($q$EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
     SELECT m.month, sum(m.n_eq), sum(m.f_eq), bit_or(m.quality_flag), count(*)
       FROM generate_series(%s, %s) r JOIN cm m ON m.cell_id BETWEEN r * 1440 + %s AND r * 1440 + %s
      GROUP BY m.month ORDER BY m.month$q$, a.r0, a.r1, a.c0, a.c1)
  LOOP IF l ~ '(Execution Time|Index (Only )?Scan using)' THEN RETURN NEXT l; END IF; END LOOP;
END $$;

CREATE TEMP TABLE cm AS SELECT * FROM harmonized.cell_month ORDER BY cell_id, month;
ALTER TABLE cm ADD PRIMARY KEY (cell_id, month);
VACUUM ANALYZE cm;

\echo '##### 1. Solo PK (cell_id, month): calendario (2 ejecuciones, se reporta la 2ª)'
SELECT nombre, x FROM aoi, LATERAL pg_temp.q_cal(nombre) x WHERE false;
SELECT nombre, x FROM aoi, LATERAL pg_temp.q_cal(nombre) x;

\echo '##### 2. PK + índice de mapa (month, cell_id) INCLUDE (n_eq, f_eq, quality_flag)'
CREATE INDEX cm_mapa ON cm (month, cell_id) INCLUDE (n_eq, f_eq, quality_flag);
ANALYZE cm;
SELECT nombre, x FROM aoi, LATERAL pg_temp.q_cal(nombre) x WHERE false;
SELECT nombre, x FROM aoi, LATERAL pg_temp.q_cal(nombre) x;

\echo '##### 3. Capa de mapa de un mes con ambos índices'
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF) SELECT cell_id, n_eq, f_eq, quality_flag FROM cm WHERE month = '2024-08-01';
