-- =============================================================================
-- 010_cell_month_sat.sql  (ruta rápida, pedido del usuario 15-nov-2026 15:00)
-- Agregado MENSUAL por (mes, celda 0,25°, satélite) en UNA lectura por tabla
-- cruda, sin pasar por la tabla diaria. Uso: psql -v tabla=modis -f 010_...
-- =============================================================================
\set ON_ERROR_STOP on
CREATE UNLOGGED TABLE IF NOT EXISTS harmonized.cell_month_sat (
    month       date     NOT NULL,
    cell_id     integer  NOT NULL,
    sat_code    smallint NOT NULL,
    n_all       integer  NOT NULL,
    n_t0        integer  NOT NULL,
    n_t0_conf   integer  NOT NULL,
    frp_t0      double precision NOT NULL,
    frp_t0_conf double precision NOT NULL
);
SET work_mem = '2GB';
SET max_parallel_workers_per_gather = 2;
\timing on
BEGIN;
SELECT format('DELETE FROM harmonized.cell_month_sat WHERE sat_code IN (SELECT sat_code FROM harmonized.dim_satellite WHERE raw_table = %L)', :'tabla') \gexec
SELECT format($q$
INSERT INTO harmonized.cell_month_sat
SELECT date_trunc('month', r.acq_date)::date,
       least(floor((r.latitude + 90) / 0.25), 719)::int * 1440 + mod(floor((r.longitude + 180) / 0.25)::int, 1440),
       d.sat_code,
       count(*),
       count(*) FILTER (WHERE r.type = 0),
       count(*) FILTER (WHERE r.type = 0 AND %s),
       coalesce(sum(r.frp) FILTER (WHERE r.type = 0), 0),
       coalesce(sum(r.frp) FILTER (WHERE r.type = 0 AND %s), 0)
  FROM public.%I r JOIN harmonized.dim_satellite d ON d.raw_satellite = r.satellite
 GROUP BY 1, 2, 3$q$,
  CASE WHEN :'tabla' = 'modis' THEN 'r.confidence >= 30' ELSE 'r.confidence <> ''l''' END,
  CASE WHEN :'tabla' = 'modis' THEN 'r.confidence >= 30' ELSE 'r.confidence <> ''l''' END,
  :'tabla') \gexec
SELECT format('INSERT INTO harmonized.harmonization_log (step, raw_table, status, rows_read, n_all_sum, started_at) SELECT %L, %L, %L, sum(n_all), sum(n_all), now() FROM harmonized.cell_month_sat WHERE sat_code IN (SELECT sat_code FROM harmonized.dim_satellite WHERE raw_table = %L)', 'cell_month_sat', :'tabla', 'ok', :'tabla') \gexec
COMMIT;
SELECT :'tabla' AS tabla, sum(n_all) AS n_all FROM harmonized.cell_month_sat WHERE sat_code IN (SELECT sat_code FROM harmonized.dim_satellite WHERE raw_table = :'tabla');
