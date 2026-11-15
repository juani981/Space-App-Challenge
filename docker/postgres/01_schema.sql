-- =====================================================================
-- NASA Space Apps Challenge 2026 — Harmonization of MODIS & VIIRS
-- PostgreSQL 18 Database Schema (TEAM_DATA_CONTRACT.md Compliant)
-- =====================================================================

CREATE TABLE IF NOT EXISTS hotspots (
    id BIGSERIAL PRIMARY KEY,
    datetime_utc TIMESTAMPTZ NOT NULL,
    satellite VARCHAR(16) NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    temp_1 DOUBLE PRECISION,
    temp_2 DOUBLE PRECISION,
    pixel_area_km2 DOUBLE PRECISION,
    frp DOUBLE PRECISION NOT NULL,
    confidence VARCHAR(20) NOT NULL,
    type INT DEFAULT 0,
    daynight VARCHAR(5) DEFAULT 'D',
    analysis_metrics JSONB DEFAULT '{}'::jsonb
);

-- Ultra-fast spatial-temporal and analytic indexes
CREATE INDEX IF NOT EXISTS idx_hotspots_spatial ON hotspots (lon, lat);
CREATE INDEX IF NOT EXISTS idx_hotspots_lat ON hotspots (lat);
CREATE INDEX IF NOT EXISTS idx_hotspots_lon ON hotspots (lon);
CREATE INDEX IF NOT EXISTS idx_hotspots_datetime ON hotspots (datetime_utc);
CREATE INDEX IF NOT EXISTS idx_hotspots_satellite ON hotspots (satellite);
CREATE INDEX IF NOT EXISTS idx_hotspots_metrics ON hotspots USING gin (analysis_metrics);
