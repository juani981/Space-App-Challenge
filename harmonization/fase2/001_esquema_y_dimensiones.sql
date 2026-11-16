-- =============================================================================
-- 001_esquema_y_dimensiones.sql
-- Crea el esquema harmonized y las tablas chicas (LOGGED): dimensión de
-- satélites, grilla de 0,25°, catálogo de huecos conocidos y registro de lotes.
-- Idempotente: se puede volver a ejecutar sin duplicar datos.
-- No toca las tablas crudas. Aprobado en la Puerta 2 (15-nov-2026).
-- =============================================================================
\set ON_ERROR_STOP on
BEGIN;

CREATE SCHEMA IF NOT EXISTS harmonized;
COMMENT ON SCHEMA harmonized IS 'Armonización MODIS + VIIRS (ver docs/CONTEXTO_ARMONIZACION.md y harmonization/fase1/DISENO_FASE1.md)';

-- --- Satélites -----------------------------------------------------------------
-- scan_c1..c4: límites (km) de las 4 clases acumuladas de scan para evaluar el
-- criterio casi-nadir en la Fase 3 (CONTEXTO 0.19). FIRMS redondea el scan de
-- MODIS a 0,1 km, por eso las clases de MODIS van de 1,0 a 2,0.
CREATE TABLE IF NOT EXISTS harmonized.dim_satellite (
    sat_code         smallint PRIMARY KEY,
    raw_satellite    text     NOT NULL UNIQUE,   -- valor de la columna satellite en la tabla cruda
    firms_code       text     NOT NULL,
    sensor           text     NOT NULL CHECK (sensor IN ('MODIS','VIIRS')),
    orbit_family     text     NOT NULL CHECK (orbit_family IN ('manana','tarde')),
    nominal_pixel_km real     NOT NULL,
    raw_table        text     NOT NULL,
    first_date       date     NOT NULL,
    last_date        date     NOT NULL,
    scan_c1          real     NOT NULL,
    scan_c2          real     NOT NULL,
    scan_c3          real     NOT NULL,
    scan_c4          real     NOT NULL
);
INSERT INTO harmonized.dim_satellite VALUES
 (1, 'Terra', 'T',   'MODIS', 'manana', 1.0,   'modis',       '2012-01-01', '2026-08-31', 1.0, 1.2, 1.5, 2.0),
 (2, 'Aqua',  'A',   'MODIS', 'tarde',  1.0,   'modis',       '2012-01-01', '2026-08-31', 1.0, 1.2, 1.5, 2.0),
 (3, 'SNPP',  'N',   'VIIRS', 'tarde',  0.375, 'viirs_suomi', '2012-01-20', '2026-07-31', 0.40, 0.45, 0.50, 0.60),
 (4, 'N20',   'N20', 'VIIRS', 'tarde',  0.375, 'viirs_j1',    '2018-04-01', '2026-07-31', 0.40, 0.45, 0.50, 0.60),
 (5, 'N21',   'N21', 'VIIRS', 'tarde',  0.375, 'viirs_j2',    '2023-03-01', '2026-07-31', 0.40, 0.45, 0.50, 0.60)
ON CONFLICT (sat_code) DO NOTHING;

-- --- Grilla de 0,25° (row-major) ---------------------------------------------
-- cell_id = cell_row * 1440 + cell_col; un rectángulo = un rango contiguo por fila.
CREATE TABLE IF NOT EXISTS harmonized.grid_cell (
    cell_id       integer  PRIMARY KEY,
    cell_row      smallint NOT NULL,   -- 0..719  = floor((lat + 90) / 0.25)
    cell_col      smallint NOT NULL,   -- 0..1439 = floor((lon + 180) / 0.25)
    block_id      integer  NOT NULL,   -- bloque de 1° (4 x 4 celdas): (row/4)*360 + col/4
    lat_center    real     NOT NULL,
    lon_center    real     NOT NULL,
    cell_area_km2 real     NOT NULL,
    lat_band      smallint NOT NULL    -- banda de 10° (límite inferior)
);
INSERT INTO harmonized.grid_cell
SELECT r * 1440 + c, r, c, (r / 4) * 360 + (c / 4),
       -90 + (r + 0.5) * 0.25, -180 + (c + 0.5) * 0.25,
       6371.0 ^ 2 * radians(0.25) * (sin(radians(-90 + (r + 1) * 0.25)) - sin(radians(-90 + r * 0.25))),
       (floor((-90 + (r + 0.5) * 0.25) / 10) * 10)::smallint
  FROM generate_series(0, 719) r, generate_series(0, 1439) c
ON CONFLICT (cell_id) DO NOTHING;
CREATE INDEX IF NOT EXISTS grid_cell_block_idx ON harmonized.grid_cell (block_id);

-- --- Catálogo de huecos conocidos --------------------------------------------
CREATE TABLE IF NOT EXISTS harmonized.known_gap (
    gap_id    serial   PRIMARY KEY,
    sat_code  smallint NOT NULL REFERENCES harmonized.dim_satellite,
    date_from date     NOT NULL,
    date_to   date     NOT NULL,
    gap_kind  text     NOT NULL CHECK (gap_kind IN ('sin_datos','caida','falla_documentada')),
    source    text     NOT NULL CHECK (source IN ('nasa','fase0','fase2_empirico')),
    note      text,
    UNIQUE (sat_code, date_from, date_to, source)
);
-- Siembra manual (Fase 0 y documentación). Los días sin datos de S-NPP, NOAA-20 y
-- NOAA-21 se cargan automáticamente desde cell_day_sat al terminar la Fase 2.
INSERT INTO harmonized.known_gap (sat_code, date_from, date_to, gap_kind, source, note) VALUES
 (2, '2020-08-16', '2020-09-02', 'falla_documentada', 'nasa',  'Falla de Aqua: cobertura muy limitada (guía MODIS)'),
 (2, '2022-04-01', '2022-04-16', 'sin_datos',         'fase0', '16 días sin datos de Aqua'),
 (1, '2016-02-19', '2016-02-27', 'sin_datos',         'fase0', '9 días sin datos de Terra'),
 (1, '2022-10-10', '2022-10-23', 'sin_datos',         'fase0', 'Terra: caída el 10-oct y sin datos hasta el 23-oct')
ON CONFLICT DO NOTHING;

-- --- Registro de lotes ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS harmonized.harmonization_log (
    log_id       bigserial   PRIMARY KEY,
    step         text        NOT NULL,          -- 'cell_day_sat', 'indices', ...
    raw_table    text,
    month        date,
    status       text        NOT NULL CHECK (status IN ('ok','error')),
    rows_read    bigint,
    rows_daily   bigint,
    n_all_sum    bigint,
    rows_effort  bigint,
    started_at   timestamptz NOT NULL,
    finished_at  timestamptz NOT NULL DEFAULT clock_timestamp(),
    seconds      numeric GENERATED ALWAYS AS (round(extract(epoch FROM finished_at - started_at)::numeric, 2)) STORED,
    error        text
);
CREATE INDEX IF NOT EXISTS harmonization_log_lote_idx ON harmonized.harmonization_log (step, raw_table, month, status);

COMMIT;
