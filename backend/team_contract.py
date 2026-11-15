from typing import Any, Optional, Literal
from pydantic import BaseModel, Field

# =====================================================================
# PROVISIONAL TEAM DATA CONTRACT (10 CONCEPTS + EXTENSIBLE METRICS)
# Edit ONLY the right-hand strings when Teammates 1 & 2 freeze their
# unified dataset/API column names.
# Left side  = Internal canonical field name (used by our system)
# Right side = Provisional column/key name from Teammates 1 & 2 (WIP)
# =====================================================================
TEAM_FIELD_MAP: dict[str, str] = {
    "datetime_utc": "datetime_utc",    # 1. Fecha y hora UTC (MODIS: YYYYMMDD+HHMM | VIIRS: acq_date+acq_time)
    "satellite":    "satellite",       # 2. Satélite (MODIS: T/A | VIIRS: N, N20, N21)
    "lat":          "lat",             # 3a. Posición — Latitud (MODIS: lat | VIIRS: latitude)
    "lon":          "lon",             # 3b. Posición — Longitud (MODIS: lon | VIIRS: longitude)
    "temp_1":       "temp_1",          # 4. Temperatura 1 (MODIS: T21 | VIIRS: brightness / I-4)
    "temp_2":       "temp_2",          # 5. Temperatura 2 (MODIS: T31 | VIIRS: bright_t31 / I-5)
    "pixel_geom":   "pixel_area_km2",  # 6. Geometría del píxel (MODIS: sample 0-1353 | VIIRS: scan, track km)
    "frp":          "frp",             # 7. Potencia radiativa en MW (MODIS: FRP | VIIRS: frp)
    "confidence":   "confidence",      # 8. Confianza normalizada (MODIS: conf 0-100 | VIIRS: l/n/h)
    "fire_type":    "type",            # 9. Tipo (MODIS: 0-3 | VIIRS: type en archive)
    "day_night":    "daynight",        # 10. Día/noche (MODIS: dn | VIIRS: daynight)
}

# =====================================================================
# DATA SOURCE SWITCH: 1-line switch to toggle between Disposable Stub
# and Real Database/DuckDB adapter when Teammates finish data integration.
# =====================================================================
DATA_SOURCE_MODE: Literal["stub", "database"] = "stub"


class UnifiedHotspot(BaseModel):
    """
    Canonical internal hotspot model consumed by our backend and frontend.
    Strictly preserves the 10 canonical concepts of TEAM_DATA_CONTRACT.md.
    Extensibility is achieved via `analysis_metrics` without altering the core 10 fields.
    """
    datetime_utc: str
    satellite: str
    lat: float
    lon: float
    temp_1: Optional[float] = None
    temp_2: Optional[float] = None
    pixel_geom: Optional[float] = None
    frp: float
    confidence: str
    fire_type: Optional[int] = None
    day_night: Optional[str] = None
    analysis_metrics: Optional[dict[str, Any]] = Field(
        default=None,
        description="Extensible scientific harmonization and analytics metrics (e.g. weights, effective area, cluster ID)"
    )


class MonthlyCalendarCell(BaseModel):
    """Activity calendar monthly cell with statistical anomaly indicators."""
    year: int
    month: int
    count: int
    historical_median: float
    anomaly_pct: float
    severity: Literal["low", "normal", "elevated", "extreme"]
    harmonized_frp: float = 0.0


def parse_team_record(raw: dict[str, Any]) -> UnifiedHotspot:
    """Translates one raw record from the teammates' dataset/API into a UnifiedHotspot."""
    m = TEAM_FIELD_MAP
    return UnifiedHotspot(
        datetime_utc=str(raw[m["datetime_utc"]]),
        satellite=str(raw[m["satellite"]]),
        lat=float(raw[m["lat"]]),
        lon=float(raw[m["lon"]]),
        temp_1=float(raw[m["temp_1"]]) if raw.get(m["temp_1"]) is not None else None,
        temp_2=float(raw[m["temp_2"]]) if raw.get(m["temp_2"]) is not None else None,
        pixel_geom=float(raw[m["pixel_geom"]]) if raw.get(m["pixel_geom"]) is not None else None,
        frp=float(raw[m["frp"]]),
        confidence=str(raw[m["confidence"]]),
        fire_type=int(raw[m["fire_type"]]) if raw.get(m["fire_type"]) is not None else None,
        day_night=str(raw[m["day_night"]]) if raw.get(m["day_night"]) is not None else None,
        analysis_metrics=raw.get("analysis_metrics"),
    )
