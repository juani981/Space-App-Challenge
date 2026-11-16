-- =============================================================================
-- 002_agregados_diarios.sql
-- Tabla de agregados diarios por (día, celda 0,25°, satélite), particionada por
-- año (2012–2026), y tabla de esfuerzo por (día, satélite, banda de 10°).
-- Particiones y esfuerzo se crean UNLOGGED (CONTEXTO 0.10); se pasan a LOGGED
-- partición por partición tras validar (CONTEXTO 0.16).
-- Índices: se crean al final de la carga de cada partición (005).
-- Idempotente.
-- =============================================================================
\set ON_ERROR_STOP on
BEGIN;

CREATE TABLE IF NOT EXISTS harmonized.cell_day_sat (
    obs_date      date     NOT NULL,
    cell_id       integer  NOT NULL,
    sat_code      smallint NOT NULL,
    n_all         integer  NOT NULL,  -- todas las filas crudas (conciliación)
    n_t0          integer  NOT NULL,  -- type = 0 (vegetación)
    n_t0_conf     integer  NOT NULL,  -- type = 0 sin confianza baja (MODIS conf >= 30; VIIRS <> 'l')
    n_t0_day      integer  NOT NULL,  -- type = 0 diurnas
    n_t1          integer  NOT NULL,
    n_t2          integer  NOT NULL,
    n_t3          integer  NOT NULL,
    n_t0_s1       integer  NOT NULL,  -- type = 0 con scan <= dim_satellite.scan_c1 (acumulado)
    n_t0_s2       integer  NOT NULL,
    n_t0_s3       integer  NOT NULL,
    n_t0_s4       integer  NOT NULL,
    frp_t0        real     NOT NULL,  -- MW, suma
    frp_t0_conf   real     NOT NULL,
    frp_t0_s1     real     NOT NULL,
    frp_t0_s2     real     NOT NULL,
    frp_t0_s3     real     NOT NULL,
    frp_t0_s4     real     NOT NULL,
    frp_t0_max    real,               -- máximo (no aditivo; NULL si no hay type = 0)
    cells1km_t0   smallint NOT NULL   -- subceldas de 0,01° con >= 1 detección type = 0 (<= 625)
) PARTITION BY RANGE (obs_date);

DO $$
DECLARE y int;
BEGIN
  FOR y IN 2012..2026 LOOP
    IF to_regclass(format('harmonized.cell_day_sat_%s', y)) IS NULL THEN
      EXECUTE format('CREATE UNLOGGED TABLE harmonized.cell_day_sat_%s PARTITION OF harmonized.cell_day_sat
                        FOR VALUES FROM (%L) TO (%L)', y, make_date(y, 1, 1), make_date(y + 1, 1, 1));
    END IF;
  END LOOP;
END $$;

CREATE UNLOGGED TABLE IF NOT EXISTS harmonized.sat_day_effort (
    obs_date   date     NOT NULL,
    sat_code   smallint NOT NULL,
    lat_band   smallint NOT NULL,  -- límite inferior de la banda de 10°; -999 = global
    n_minutes  integer  NOT NULL,  -- minutos de adquisición (acq_time) distintos
    n_det      integer  NOT NULL
);

COMMIT;
