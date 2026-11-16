-- =====================================================================
-- Verified v0.2 Web Schema for `harmonized` (PostgreSQL 18)
-- Reference: docs/CONTRATO_DATOS_WEB_RESPUESTA_V02.md
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS harmonized;

CREATE TABLE IF NOT EXISTS harmonized.cell_month (
    month          DATE     NOT NULL,
    cell_id        INTEGER  NOT NULL,
    lat_center     REAL     NOT NULL,
    lon_center     REAL     NOT NULL,
    cell_area_km2  REAL     NOT NULL,
    n_eq           REAL     NOT NULL CHECK (n_eq >= 0),
    f_eq           REAL     NOT NULL CHECK (f_eq >= 0),
    ref_sat        SMALLINT NOT NULL, -- 2=Aqua, 3=SNPP, 4=N20, 5=N21
    sensors        TEXT     NOT NULL,
    n_terra        INTEGER  NOT NULL DEFAULT 0 CHECK (n_terra >= 0),
    n_aqua         INTEGER  NOT NULL DEFAULT 0 CHECK (n_aqua >= 0),
    n_snpp         INTEGER  NOT NULL DEFAULT 0 CHECK (n_snpp >= 0),
    n_n20          INTEGER  NOT NULL DEFAULT 0 CHECK (n_n20 >= 0),
    n_n21          INTEGER  NOT NULL DEFAULT 0 CHECK (n_n21 >= 0),
    frp_terra      REAL     NOT NULL DEFAULT 0 CHECK (frp_terra >= 0),
    frp_aqua       REAL     NOT NULL DEFAULT 0 CHECK (frp_aqua >= 0),
    frp_snpp       REAL     NOT NULL DEFAULT 0 CHECK (frp_snpp >= 0),
    frp_n20        REAL     NOT NULL DEFAULT 0 CHECK (frp_n20 >= 0),
    frp_n21        REAL     NOT NULL DEFAULT 0 CHECK (frp_n21 >= 0),
    quality_flag   SMALLINT NOT NULL DEFAULT 0,
    method_version TEXT     NOT NULL DEFAULT 'v0.2',
    PRIMARY KEY (cell_id, month)
);

CREATE INDEX IF NOT EXISTS idx_cell_month_month ON harmonized.cell_month (month);
CREATE INDEX IF NOT EXISTS idx_cell_month_center ON harmonized.cell_month (lat_center, lon_center);

-- Fast single-month / map-layer table clustered by (month, cell_id)
CREATE TABLE IF NOT EXISTS harmonized.map_month (
    month         DATE     NOT NULL,
    cell_id       INTEGER  NOT NULL,
    lat_center    REAL     NOT NULL,
    lon_center    REAL     NOT NULL,
    cell_area_km2 REAL     NOT NULL,
    n_eq          REAL     NOT NULL DEFAULT 0,
    f_eq          REAL     NOT NULL DEFAULT 0,
    n_terra       INTEGER  NOT NULL DEFAULT 0,
    frp_terra     REAL     NOT NULL DEFAULT 0,
    quality_flag  SMALLINT NOT NULL DEFAULT 0,
    PRIMARY KEY (month, cell_id)
);

-- Month-level provenance & quality flags across all 176 months (even empty AOI months)
CREATE TABLE IF NOT EXISTS harmonized.reference_plan (
    month                  DATE     PRIMARY KEY,
    ref_sat                SMALLINT NOT NULL,
    sensors                TEXT     NOT NULL,
    quality_flag           SMALLINT NOT NULL DEFAULT 0,
    excluded_from_baseline BOOLEAN  NOT NULL DEFAULT FALSE
);

INSERT INTO harmonized.reference_plan (month, ref_sat, sensors, quality_flag, excluded_from_baseline)
SELECT
    m::date AS month,
    CASE
        WHEN m::date = DATE '2026-08-01' THEN 2
        WHEN m::date = DATE '2023-07-01' THEN 5
        WHEN m::date < DATE '2020-01-01' THEN 3
        ELSE 4
    END AS ref_sat,
    CASE
        WHEN m::date = DATE '2026-08-01' THEN 'Aqua (solo MODIS / deriva)'
        WHEN m::date = DATE '2023-07-01' THEN 'N21 (respaldo de N20)'
        WHEN m::date < DATE '2020-01-01' THEN 'SNPP'
        ELSE 'N20'
    END AS sensors,
    CASE
        WHEN m::date = DATE '2012-01-01' THEN 1
        WHEN m::date = DATE '2012-03-01' THEN 24
        WHEN m::date = DATE '2023-07-01' THEN 64
        WHEN m::date = DATE '2026-07-01' THEN 2
        WHEN m::date = DATE '2026-08-01' THEN 6
        ELSE 0
    END AS quality_flag,
    CASE
        WHEN m::date IN (DATE '2012-01-01', DATE '2012-03-01', DATE '2026-08-01') THEN TRUE
        ELSE FALSE
    END AS excluded_from_baseline
FROM generate_series(DATE '2012-01-01', DATE '2026-08-01', INTERVAL '1 month') AS gs(m)
ON CONFLICT (month) DO NOTHING;

CREATE TABLE IF NOT EXISTS harmonized.quality_bits (
    bit               SMALLINT PRIMARY KEY,
    value             INTEGER  NOT NULL,
    name              TEXT     NOT NULL,
    scope             TEXT     NOT NULL,
    excludes_baseline BOOLEAN  NOT NULL,
    in_use            BOOLEAN  NOT NULL,
    description       TEXT     NOT NULL
);

INSERT INTO harmonized.quality_bits (bit, value, name, scope, excludes_baseline, in_use, description) VALUES
(0, 1,   'viirs_parcial',         'mes',  TRUE,  TRUE,  'Ene-2012: S-NPP empieza el 20-ene; mes parcial sin corregir'),
(1, 2,   'ultimo_mes_standard',   'mes',  FALSE, TRUE,  'Último mes standard disponible del sensor de referencia (posibles reprocesos)'),
(2, 4,   'solo_modis_deriva',     'mes',  TRUE,  TRUE,  'Ago-2026: n_eq = N_Aqua directo, sin VIIRS; tiende a subestimar ~10 % por la deriva de Aqua'),
(3, 8,   'ref_incompleta_huecos', 'mes',  TRUE,  TRUE,  'Referencia incompleta (>= 3 días afectados) con días faltantes o del catálogo de huecos'),
(4, 16,  'ref_incompleta_caidas', 'mes',  TRUE,  TRUE,  'Referencia incompleta (>= 3 días afectados) con caídas (< 30 %) o minutos de adquisición bajos'),
(5, 32,  'caida_simultanea',      'mes',  FALSE, FALSE, 'Caída en >= 2 satélites el mismo día: definido, hoy no marca ningún mes'),
(6, 64,  'referencia_respaldo',   'mes',  FALSE, TRUE,  'Se usó el siguiente satélite de la cadena porque la referencia estaba incompleta (jul-2023: NOAA-21)'),
(7, 128, 'calibracion_baja_conf', 'fila', FALSE, TRUE,  'Coeficiente de confianza baja (banda extrema -60°, 70° o polar)')
ON CONFLICT (bit) DO NOTHING;

CREATE TABLE IF NOT EXISTS harmonized.dataset_metadata (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS harmonized.known_gap (
    gap_id    INTEGER  PRIMARY KEY,
    sat_code  SMALLINT NOT NULL,
    date_from DATE     NOT NULL,
    date_to   DATE     NOT NULL,
    gap_kind  TEXT     NOT NULL,
    source    TEXT     NOT NULL,
    note      TEXT
);

CREATE TABLE IF NOT EXISTS harmonized.dim_satellite (
    sat_code         SMALLINT PRIMARY KEY,
    raw_satellite    TEXT     NOT NULL,
    firms_code       TEXT     NOT NULL,
    sensor           TEXT     NOT NULL,
    orbit_family     TEXT     NOT NULL,
    nominal_pixel_km REAL     NOT NULL,
    raw_table        TEXT     NOT NULL,
    first_date       DATE     NOT NULL,
    last_date        DATE     NOT NULL
);

CREATE TABLE IF NOT EXISTS harmonized.global_month (
    month        DATE             PRIMARY KEY,
    n_eq_global  DOUBLE PRECISION NOT NULL DEFAULT 0,
    f_eq_global  DOUBLE PRECISION NOT NULL DEFAULT 0,
    quality_flag SMALLINT         NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS harmonized.sat_month_quality (
    month           DATE     NOT NULL,
    sat_code        SMALLINT NOT NULL,
    days_in_range   SMALLINT NOT NULL,
    days_missing    SMALLINT NOT NULL,
    days_caida      SMALLINT NOT NULL,
    days_parcial    SMALLINT NOT NULL,
    days_catalog    SMALLINT NOT NULL,
    days_minutes_low SMALLINT NOT NULL,
    days_affected   SMALLINT NOT NULL,
    complete        BOOLEAN  NOT NULL,
    PRIMARY KEY (month, sat_code)
);
