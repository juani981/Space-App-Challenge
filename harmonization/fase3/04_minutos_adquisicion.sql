-- =============================================================================
-- fase3/04_minutos_adquisicion.sql
-- Tabla chica de esfuerzo: minutos de adquisición (acq_time) distintos por
-- (día, satélite, banda de 10°) y global (lat_band = -999). LOGGED.
-- La carga la hace 04_minutos_adquisicion.py, un lote (tabla cruda, mes) por
-- transacción, con filtro por acq_date (BRIN). Idempotente.
-- =============================================================================
\set ON_ERROR_STOP on
CREATE TABLE IF NOT EXISTS harmonized.sat_day_effort (
    obs_date   date     NOT NULL,
    sat_code   smallint NOT NULL,
    lat_band   smallint NOT NULL,   -- límite inferior de la banda de 10°; -999 = global
    n_minutes  integer  NOT NULL,   -- minutos de adquisición distintos
    n_det      integer  NOT NULL,   -- detecciones (todas)
    PRIMARY KEY (obs_date, sat_code, lat_band)
);

CREATE OR REPLACE FUNCTION harmonized.load_effort(p_table text, p_month date)
RETURNS bigint LANGUAGE plpgsql AS $fn$
DECLARE v_m0 date := date_trunc('month', p_month)::date;
        v_m1 date := (date_trunc('month', p_month) + interval '1 month')::date;
        v_n bigint;
BEGIN
  IF p_table NOT IN ('modis','viirs_suomi','viirs_j1','viirs_j2') THEN RAISE EXCEPTION 'tabla no válida'; END IF;
  DELETE FROM harmonized.sat_day_effort e USING harmonized.dim_satellite d
   WHERE e.sat_code = d.sat_code AND d.raw_table = p_table AND e.obs_date >= v_m0 AND e.obs_date < v_m1;
  EXECUTE format($q$
    INSERT INTO harmonized.sat_day_effort
    SELECT acq_date, sat_code, CASE WHEN grouping(lat_band) = 1 THEN -999 ELSE lat_band END,
           count(DISTINCT acq_time), count(*)
      FROM (SELECT r.acq_date, d.sat_code, r.acq_time, (floor(r.latitude / 10) * 10)::smallint AS lat_band
              FROM public.%I r JOIN harmonized.dim_satellite d ON d.raw_satellite = r.satellite
             WHERE r.acq_date >= $1 AND r.acq_date < $2 OFFSET 0) s
     GROUP BY GROUPING SETS ((acq_date, sat_code, lat_band), (acq_date, sat_code))$q$, p_table)
  USING v_m0, v_m1;
  SELECT coalesce(sum(n_det), 0) INTO v_n FROM harmonized.sat_day_effort e JOIN harmonized.dim_satellite d USING (sat_code)
   WHERE d.raw_table = p_table AND e.lat_band = -999 AND e.obs_date >= v_m0 AND e.obs_date < v_m1;
  RETURN v_n;   -- filas crudas del mes (para conciliar contra la Fase 0)
END $fn$;
