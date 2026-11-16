-- =============================================================================
-- 003_vista_canonica.sql
-- Capa canónica como VISTA (CONTEXTO 0.14): traduce nombres y códigos de las 4
-- tablas crudas sin copiarlas. Los filtros por obs_date deben llegar a cada
-- tabla cruda como filtro sobre acq_date (BRIN); se verifica con EXPLAIN.
-- =============================================================================
\set ON_ERROR_STOP on
BEGIN;

CREATE OR REPLACE VIEW harmonized.v_detection AS
SELECT m.acq_date AS obs_date,
       m.acq_date + m.acq_time::time AS obs_ts_utc,
       CASE m.satellite WHEN 'Terra' THEN 1 WHEN 'Aqua' THEN 2 END::smallint AS sat_code,
       'MODIS'::text AS sensor,
       CASE m.satellite WHEN 'Terra' THEN 'manana' ELSE 'tarde' END AS orbit_family,
       m.latitude AS lat, m.longitude AS lon,
       least(floor((m.latitude + 90) / 0.25), 719)::int * 1440 + mod(floor((m.longitude + 180) / 0.25)::int, 1440) AS cell_id,
       m.frp,
       CASE WHEN m.confidence < 30 THEN 'baja' WHEN m.confidence < 80 THEN 'nominal' ELSE 'alta' END AS confidence_class,
       m.confidence::text AS confidence_raw,
       m.type, m.daynight, m.scan, m.track, m.scan * m.track AS pixel_area_km2,
       m.brightness, m.bright_t31, m.version
  FROM public.modis m
UNION ALL
SELECT v.acq_date, v.acq_date + v.acq_time::time, 3::smallint, 'VIIRS', 'tarde', v.latitude, v.longitude,
       least(floor((v.latitude + 90) / 0.25), 719)::int * 1440 + mod(floor((v.longitude + 180) / 0.25)::int, 1440),
       v.frp, CASE v.confidence WHEN 'l' THEN 'baja' WHEN 'n' THEN 'nominal' WHEN 'h' THEN 'alta' END, v.confidence::text,
       v.type, v.daynight, v.scan, v.track, v.scan * v.track, v.brightness, v.bright_t31, v.version
  FROM public.viirs_suomi v
UNION ALL
SELECT v.acq_date, v.acq_date + v.acq_time::time, 4::smallint, 'VIIRS', 'tarde', v.latitude, v.longitude,
       least(floor((v.latitude + 90) / 0.25), 719)::int * 1440 + mod(floor((v.longitude + 180) / 0.25)::int, 1440),
       v.frp, CASE v.confidence WHEN 'l' THEN 'baja' WHEN 'n' THEN 'nominal' WHEN 'h' THEN 'alta' END, v.confidence::text,
       v.type, v.daynight, v.scan, v.track, v.scan * v.track, v.brightness, v.bright_t31, v.version
  FROM public.viirs_j1 v
UNION ALL
SELECT v.acq_date, v.acq_date + v.acq_time::time, 5::smallint, 'VIIRS', 'tarde', v.latitude, v.longitude,
       least(floor((v.latitude + 90) / 0.25), 719)::int * 1440 + mod(floor((v.longitude + 180) / 0.25)::int, 1440),
       v.frp, CASE v.confidence WHEN 'l' THEN 'baja' WHEN 'n' THEN 'nominal' WHEN 'h' THEN 'alta' END, v.confidence::text,
       v.type, v.daynight, v.scan, v.track, v.scan * v.track, v.brightness, v.bright_t31, v.version
  FROM public.viirs_j2 v;

COMMENT ON VIEW harmonized.v_detection IS 'Capa canónica (adaptador) sobre las 4 tablas crudas. Filtrar SIEMPRE por obs_date.';

COMMIT;
