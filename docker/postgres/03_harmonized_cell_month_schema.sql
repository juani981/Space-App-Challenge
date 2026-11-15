-- =====================================================================
-- Provisional Web Schema for `harmonized.cell_month` (PostgreSQL 18)
-- Reference: docs/DOCUMENTACION_TABLA_ARMONIZADA.md
-- NOTE: Types marked as referential in Section 2 must be verified once
--       Teammates deliver the real `\d+ harmonized.cell_month` DDL.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS harmonized;

CREATE TABLE IF NOT EXISTS harmonized.cell_month (
    month          DATE             NOT NULL,
    cell_id        INTEGER          NOT NULL,
    lat_center     REAL             NOT NULL,
    lon_center     REAL             NOT NULL,
    cell_area_km2  REAL             NOT NULL,
    n_eq           DOUBLE PRECISION NOT NULL,
    f_eq           DOUBLE PRECISION NOT NULL,
    -- TODO(PENDING_TEAM_CONFIRMATION): Confirm exact type (TEXT vs SMALLINT) and MODIS-only value
    ref_sat        TEXT,
    sensors        TEXT             NOT NULL,
    n_terra        INTEGER          NOT NULL DEFAULT 0,
    n_aqua         INTEGER          NOT NULL DEFAULT 0,
    n_snpp         INTEGER          NOT NULL DEFAULT 0,
    n_n20          INTEGER          NOT NULL DEFAULT 0,
    n_n21          INTEGER          NOT NULL DEFAULT 0,
    frp_terra      REAL             NOT NULL DEFAULT 0,
    frp_aqua       REAL             NOT NULL DEFAULT 0,
    frp_snpp       REAL             NOT NULL DEFAULT 0,
    frp_n20        REAL             NOT NULL DEFAULT 0,
    frp_n21        REAL             NOT NULL DEFAULT 0,
    quality_flag   SMALLINT         NOT NULL DEFAULT 0,
    method_version TEXT             NOT NULL DEFAULT 'v0.1-provisional',
    PRIMARY KEY (cell_id, month)
);

-- Supports month-first slices and lat/lon center fallback while cell_id origin is confirmed
CREATE INDEX IF NOT EXISTS idx_cell_month_month ON harmonized.cell_month (month);
CREATE INDEX IF NOT EXISTS idx_cell_month_center ON harmonized.cell_month (lat_center, lon_center);
