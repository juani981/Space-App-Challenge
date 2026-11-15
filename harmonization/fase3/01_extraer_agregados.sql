-- =============================================================================
-- fase3/01_extraer_agregados.sql  (SOLO LECTURA, sobre harmonized.cell_month_sat)
-- Sector continental por longitud del centro de la celda:
--   1 = Américas (lon < -30), 2 = Europa/África (-30 <= lon < 60), 3 = Asia/Oceanía (lon >= 60)
-- Salidas (CSV en la carpeta indicada por :salida):
--   region_month.csv : (mes, satélite, banda 10°, sector) → focos y FRP (type 0, sin confianza baja)
--   cell_aqua_snpp.csv: por celda y mes, Aqua y S-NPP en 2012-01..2020-12 (para validación cruzada)
-- =============================================================================
\set ON_ERROR_STOP on
SHOW default_transaction_read_only;
SET work_mem = '1GB';
\timing on

SELECT format($q$\copy (SELECT s.month, s.sat_code, g.lat_band,
       CASE WHEN g.lon_center < -30 THEN 1 WHEN g.lon_center < 60 THEN 2 ELSE 3 END AS sector,
       sum(s.n_t0_conf) AS n, sum(s.frp_t0_conf) AS f, count(*) AS celdas
  FROM harmonized.cell_month_sat s JOIN harmonized.grid_cell g USING (cell_id)
 GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4) TO '%s/region_month.csv' WITH (FORMAT csv, HEADER)$q$, :'salida') \gset q_
:q_format

SELECT format($q$\copy (SELECT s.month, s.cell_id, g.lat_band,
       CASE WHEN g.lon_center < -30 THEN 1 WHEN g.lon_center < 60 THEN 2 ELSE 3 END AS sector,
       sum(s.n_t0_conf) FILTER (WHERE s.sat_code = 2) AS n_aqua, sum(s.n_t0_conf) FILTER (WHERE s.sat_code = 3) AS n_snpp,
       sum(s.frp_t0_conf) FILTER (WHERE s.sat_code = 2) AS f_aqua, sum(s.frp_t0_conf) FILTER (WHERE s.sat_code = 3) AS f_snpp
  FROM harmonized.cell_month_sat s JOIN harmonized.grid_cell g USING (cell_id)
 WHERE s.sat_code IN (2, 3) AND s.month < '2021-01-01'
 GROUP BY 1, 2, 3, 4) TO '%s/cell_aqua_snpp.csv' WITH (FORMAT csv, HEADER)$q$, :'salida') \gset q_
:q_format
