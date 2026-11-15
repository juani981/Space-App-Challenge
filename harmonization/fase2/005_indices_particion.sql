-- =============================================================================
-- 005_indices_particion.sql
-- Crea los índices de UNA partición anual de cell_day_sat (al terminar de
-- cargarla), los de sat_day_effort, y ejecuta ANALYZE.
-- Uso: psql -v anio=2026 -f 005_indices_particion.sql
-- Los índices de partición se adjuntan luego a los índices del padre (006).
-- =============================================================================
\set ON_ERROR_STOP on

SELECT format('harmonized.cell_day_sat_%s', :'anio') AS part \gset
SET maintenance_work_mem = '1GB';

SELECT format('CREATE UNIQUE INDEX IF NOT EXISTS cell_day_sat_%s_pk ON %s (obs_date, cell_id, sat_code)', :'anio', :'part') \gexec
SELECT format('CREATE INDEX IF NOT EXISTS cell_day_sat_%s_cell_idx ON %s (cell_id, obs_date)', :'anio', :'part') \gexec
SELECT format('ANALYZE %s', :'part') \gexec

CREATE UNIQUE INDEX IF NOT EXISTS sat_day_effort_pk ON harmonized.sat_day_effort (obs_date, sat_code, lat_band);
ANALYZE harmonized.sat_day_effort;
