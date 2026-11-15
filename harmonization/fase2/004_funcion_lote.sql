-- =============================================================================
-- 004_funcion_lote.sql
-- harmonized.process_batch(tabla_cruda, mes): procesa un lote (tabla, mes) en
-- UNA lectura de la tabla cruda (filtro por acq_date → BRIN) y escribe:
--   * harmonized.cell_day_sat   (día × celda 0,25° × satélite)
--   * harmonized.sat_day_effort (día × satélite × banda 10°, y global = -999)
-- Idempotente: borra primero el mes y los satélites de esa tabla.
-- Conciliación: filas leídas = suma de n_all; si no coincide, lanza excepción y
-- la transacción completa se revierte (no queda nada a medias).
-- Registra el lote en harmonized.harmonization_log.
-- =============================================================================
\set ON_ERROR_STOP on

CREATE OR REPLACE FUNCTION harmonized.process_batch(p_table text, p_month date)
RETURNS TABLE (rows_read bigint, rows_daily bigint, n_all_sum bigint, rows_effort bigint)
LANGUAGE plpgsql AS
$fn$
DECLARE
    v_start  timestamptz := clock_timestamp();
    v_m0     date := date_trunc('month', p_month)::date;
    v_m1     date := (date_trunc('month', p_month) + interval '1 month')::date;
    v_sats   smallint[];
    v_conf   text;
BEGIN
    IF p_table NOT IN ('modis', 'viirs_suomi', 'viirs_j1', 'viirs_j2') THEN
        RAISE EXCEPTION 'Tabla cruda no válida: %', p_table;
    END IF;
    SELECT array_agg(sat_code) INTO v_sats FROM harmonized.dim_satellite WHERE raw_table = p_table;
    v_conf := CASE WHEN p_table = 'modis' THEN 'r.confidence >= 30' ELSE 'r.confidence <> ''l''' END;

    DELETE FROM harmonized.cell_day_sat   WHERE obs_date >= v_m0 AND obs_date < v_m1 AND sat_code = ANY (v_sats);
    DELETE FROM harmonized.sat_day_effort WHERE obs_date >= v_m0 AND obs_date < v_m1 AND sat_code = ANY (v_sats);

    EXECUTE format($q$
      WITH src AS MATERIALIZED (
        SELECT r.acq_date AS obs_date, d.sat_code, r.acq_time, r.latitude, r.type, r.daynight, r.frp, r.scan,
               (%1$s) AS conf_ok,
               least(floor((r.latitude + 90) / 0.25), 719)::int * 1440 + mod(floor((r.longitude + 180) / 0.25)::int, 1440) AS cell_id,
               least(floor((r.latitude + 90) / 0.01), 17999)::int AS r1,
               mod(floor((r.longitude + 180) / 0.01)::int, 36000) AS c1,
               d.scan_c1, d.scan_c2, d.scan_c3, d.scan_c4
          FROM public.%2$I r
          LEFT JOIN harmonized.dim_satellite d ON d.raw_satellite = r.satellite
         WHERE r.acq_date >= $1 AND r.acq_date < $2),
      k1 AS (
        SELECT obs_date, sat_code, cell_id, r1, c1,
               count(*) AS n_all,
               count(*) FILTER (WHERE type = 0) AS n_t0,
               count(*) FILTER (WHERE type = 0 AND conf_ok) AS n_t0_conf,
               count(*) FILTER (WHERE type = 0 AND daynight = 'D') AS n_t0_day,
               count(*) FILTER (WHERE type = 1) AS n_t1,
               count(*) FILTER (WHERE type = 2) AS n_t2,
               count(*) FILTER (WHERE type = 3) AS n_t3,
               count(*) FILTER (WHERE type = 0 AND scan <= scan_c1) AS n_t0_s1,
               count(*) FILTER (WHERE type = 0 AND scan <= scan_c2) AS n_t0_s2,
               count(*) FILTER (WHERE type = 0 AND scan <= scan_c3) AS n_t0_s3,
               count(*) FILTER (WHERE type = 0 AND scan <= scan_c4) AS n_t0_s4,
               coalesce(sum(frp) FILTER (WHERE type = 0), 0) AS frp_t0,
               coalesce(sum(frp) FILTER (WHERE type = 0 AND conf_ok), 0) AS frp_t0_conf,
               coalesce(sum(frp) FILTER (WHERE type = 0 AND scan <= scan_c1), 0) AS frp_t0_s1,
               coalesce(sum(frp) FILTER (WHERE type = 0 AND scan <= scan_c2), 0) AS frp_t0_s2,
               coalesce(sum(frp) FILTER (WHERE type = 0 AND scan <= scan_c3), 0) AS frp_t0_s3,
               coalesce(sum(frp) FILTER (WHERE type = 0 AND scan <= scan_c4), 0) AS frp_t0_s4,
               max(frp) FILTER (WHERE type = 0) AS frp_t0_max
          FROM src GROUP BY 1, 2, 3, 4, 5),
      ins_d AS (
        INSERT INTO harmonized.cell_day_sat
        SELECT obs_date, cell_id, sat_code,
               sum(n_all), sum(n_t0), sum(n_t0_conf), sum(n_t0_day), sum(n_t1), sum(n_t2), sum(n_t3),
               sum(n_t0_s1), sum(n_t0_s2), sum(n_t0_s3), sum(n_t0_s4),
               sum(frp_t0), sum(frp_t0_conf), sum(frp_t0_s1), sum(frp_t0_s2), sum(frp_t0_s3), sum(frp_t0_s4),
               max(frp_t0_max), count(*) FILTER (WHERE n_t0 > 0)
          FROM k1 GROUP BY obs_date, cell_id, sat_code
        RETURNING n_all),
      ins_e AS (
        INSERT INTO harmonized.sat_day_effort
        SELECT obs_date, sat_code,
               CASE WHEN grouping(lat_band) = 1 THEN -999 ELSE lat_band END,
               count(DISTINCT acq_time), count(*)
          FROM (SELECT obs_date, sat_code, acq_time, (floor(latitude / 10) * 10)::smallint AS lat_band FROM src) s
         GROUP BY GROUPING SETS ((obs_date, sat_code, lat_band), (obs_date, sat_code))
        RETURNING 1)
      SELECT (SELECT count(*) FROM src), (SELECT count(*) FROM ins_d),
             (SELECT coalesce(sum(n_all), 0) FROM ins_d), (SELECT count(*) FROM ins_e)
    $q$, v_conf, p_table)
    USING v_m0, v_m1
    INTO rows_read, rows_daily, n_all_sum, rows_effort;

    IF rows_read <> n_all_sum THEN
        RAISE EXCEPTION 'Conciliación fallida en % %: leídas %, n_all %', p_table, v_m0, rows_read, n_all_sum;
    END IF;

    INSERT INTO harmonized.harmonization_log
        (step, raw_table, month, status, rows_read, rows_daily, n_all_sum, rows_effort, started_at)
    VALUES ('cell_day_sat', p_table, v_m0, 'ok', rows_read, rows_daily, n_all_sum, rows_effort, v_start);

    RETURN NEXT;
END;
$fn$;

COMMENT ON FUNCTION harmonized.process_batch(text, date) IS
  'Fase 2: un lote (tabla cruda, mes) en una lectura → cell_day_sat + sat_day_effort; idempotente y conciliado';
