"""
Domain models, grid geometry, quality-flag bitwise helpers, and anomaly engine
for the team's harmonized global monthly table: `harmonized.cell_month`.

Aligned strictly with the verified v0.2 PostgreSQL contract in
`docs/CONTRATO_DATOS_WEB_RESPUESTA_V02.md` (`method_version = 'v0.2'`,
range `2012-01-01..2026-08-01`, `south_to_north` row origin, `EXCLUDE_BASELINE_MASK = 29`).
"""

from __future__ import annotations

import math
import statistics
from datetime import date
from enum import IntFlag
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

# =====================================================================
# GLOBAL GRID CONSTANTS & OPERATIONAL LIMITS (VERIFIED v0.2)
# =====================================================================
GRID_ROWS = 720
GRID_COLS = 1440
TOTAL_GRID_CELLS = GRID_ROWS * GRID_COLS  # 1,036,800 global cells
GRID_STEP_DEG = 0.25
GRID_STEP_1DEG = 1.0
GRID_COLS_1DEG = 360
GRID_ROWS_1DEG = 180
EARTH_RADIUS_KM = 6371.0

DEFAULT_METHOD_VERSION = "v0.2"
MIN_BASELINE_YEARS = 10
MAD_NORMAL_CONSTANT = 1.4826

SERIES_START_MONTH = date(2012, 1, 1)
SERIES_END_MONTH = date(2026, 8, 1)
TOTAL_SERIES_MONTHS = 176

# Verified performance & safety caps (CONTRATO_DATOS_WEB_RESPUESTA_V02.md Sec 5, 6c, 6d)
MAX_CALENDAR_CELLS = 50_000
MAP_1DEG_CELL_THRESHOLD = 20_000
CSV_MAX_ROWS = 1_000_000
MIN_RECOMMENDED_AOI_CELLS = 4

AQUA_2026_08_DRIFT_WARNING_ES = (
    "Ago-2026 usa solo MODIS-Aqua, que por su deriva orbital detecta ~10 % menos "
    "que la serie armonizada; el valor tiende a subestimar."
)
LOW_CONFIDENCE_BAND_WARNING_ES = (
    "El AOI intersecta bandas extremas (-60°, 70° o polares) con calibración de baja confianza "
    "(bit 7): valores absolutos poco confiables; la anomalía por percentil no se ve afectada por un sesgo constante."
)

RowOrigin = Literal["north_to_south", "south_to_north"]
LonConvention = Literal["signed_180", "unsigned_360"]

REF_SAT_LABELS: dict[int, str] = {
    2: "Aqua",
    3: "SNPP",
    4: "N20",
    5: "N21",
}

REF_SAT_SENSORS_V02: dict[int, str] = {
    2: "Aqua (solo MODIS / deriva)",
    3: "SNPP",
    4: "N20",
    5: "N21 (respaldo de N20)",
}

# =====================================================================
# CONFIRMED v0.2 CONTRACT REGISTRY
# =====================================================================
TEAM_CONTRACT_V02: dict[str, Any] = {
    "method_version": DEFAULT_METHOD_VERSION,
    "cell_id_row_origin": "south_to_north",   # fila 0 = Sur (lat_center = -89.875)
    "lon_convention": "signed_180",           # col 0 = lon_center = -179.875
    "quality_flag_bitmask_confirmed": True,
    "exclude_baseline_mask": 29,              # bits 0, 2, 3, 4 (1 + 4 + 8 + 16)
    "ref_sat_codes": REF_SAT_LABELS,
    "inactive_satellite_zero_or_null": 0,     # NOT NULL >= 0 before launch or no detections
    "frp_matches_count_filters": True,
    "source_postgres_version": "18",
    "period": "2012-01..2026-08",
    "max_calendar_cells": MAX_CALENDAR_CELLS,
    "map_1deg_cell_threshold": MAP_1DEG_CELL_THRESHOLD,
    "csv_max_rows": CSV_MAX_ROWS,
    "low_confidence_bands": ["-60", "70", "polar"],
    "auxiliary_tables": {
        "monthly_quality_table": "harmonized.reference_plan",
        "reference_plan_table": "harmonized.reference_plan",
        "map_layer_table": "harmonized.map_month",
        "quality_bits_table": "harmonized.quality_bits",
        "dataset_metadata_table": "harmonized.dataset_metadata",
        "gaps_catalog_table": "harmonized.known_gap",
        "sat_month_quality_table": "harmonized.sat_month_quality",
        "global_month_table": "harmonized.global_month",
        "dim_satellite_table": "harmonized.dim_satellite",
    },
}
# Alias preserved for backwards module compatibility
PENDING_TEAM_CONFIRMATION = TEAM_CONTRACT_V02


class QualityFlagBits(IntFlag):
    """
    8-bit quality bitmask verified in v0.2 (`harmonized.quality_bits`).
    """

    NONE = 0
    VIIRS_PARCIAL = 1 << 0             # 1: ene-2012 (S-NPP inició el 20-ene)
    ULTIMO_MES_STANDARD = 1 << 1       # 2: jul-2026 (último mes standard VIIRS)
    SOLO_MODIS_DERIVA = 1 << 2         # 4: ago-2026 (n_eq = N_Aqua directo; subestima ~10%)
    REF_INCOMPLETA_HUECOS = 1 << 3     # 8: >=3 días afectados con faltantes o catálogo de huecos
    REF_INCOMPLETA_CAIDAS = 1 << 4     # 16: >=3 días afectados con caídas (<30%) o minutos bajos
    CAIDA_SIMULTANEA = 1 << 5          # 32: definido; sin meses marcados actualmente (in_use=false)
    REFERENCIA_RESPALDO = 1 << 6       # 64: respaldo de cadena usado (jul-2023 NOAA-21)
    CALIBRACION_BAJA_CONF = 1 << 7     # 128: nivel fila en bandas extremas (-60°, 70°, polares)

    # Clear semantic aliases
    PARTIAL_MONTH = VIIRS_PARCIAL
    LAST_MONTH = ULTIMO_MES_STANDARD
    MODIS_ONLY = SOLO_MODIS_DERIVA
    GAPS = REF_INCOMPLETA_HUECOS
    DROPS = REF_INCOMPLETA_CAIDAS
    FALLBACK = REFERENCIA_RESPALDO
    LOW_CONFIDENCE_CALIBRATION = CALIBRACION_BAJA_CONF


# Baseline anomaly exclusion mask: bits 0, 2, 3, 4 (1 + 4 + 8 + 16 = 29)
BASELINE_EXCLUDE_MASK = int(
    QualityFlagBits.VIIRS_PARCIAL
    | QualityFlagBits.SOLO_MODIS_DERIVA
    | QualityFlagBits.REF_INCOMPLETA_HUECOS
    | QualityFlagBits.REF_INCOMPLETA_CAIDAS
)
EXCLUDE_BASELINE_MASK = BASELINE_EXCLUDE_MASK

QUALITY_FLAG_LABELS_ES: dict[QualityFlagBits, str] = {
    QualityFlagBits.VIIRS_PARCIAL: "VIIRS parcial (ene-2012: inicio 20-ene)",
    QualityFlagBits.ULTIMO_MES_STANDARD: "Último mes standard del sensor de referencia",
    QualityFlagBits.SOLO_MODIS_DERIVA: "Solo MODIS-Aqua (deriva orbital, subestima ~10%)",
    QualityFlagBits.REF_INCOMPLETA_HUECOS: "Referencia incompleta por huecos (≥3 días afectados)",
    QualityFlagBits.REF_INCOMPLETA_CAIDAS: "Referencia incompleta por caídas / minutos bajos",
    QualityFlagBits.CAIDA_SIMULTANEA: "Caída simultánea en ≥2 satélites",
    QualityFlagBits.REFERENCIA_RESPALDO: "Referencia de respaldo (cadena VIIRS, ej. N21)",
    QualityFlagBits.CALIBRACION_BAJA_CONF: "Calibración de baja confianza (bandas -60°, 70° o polares)",
}

QUALITY_FLAG_CODES_V02: dict[QualityFlagBits, tuple[str, str, bool]] = {
    QualityFlagBits.VIIRS_PARCIAL: ("viirs_parcial", "mes", True),
    QualityFlagBits.ULTIMO_MES_STANDARD: ("ultimo_mes_standard", "mes", False),
    QualityFlagBits.SOLO_MODIS_DERIVA: ("solo_modis_deriva", "mes", True),
    QualityFlagBits.REF_INCOMPLETA_HUECOS: ("ref_incompleta_huecos", "mes", True),
    QualityFlagBits.REF_INCOMPLETA_CAIDAS: ("ref_incompleta_caidas", "mes", True),
    QualityFlagBits.CAIDA_SIMULTANEA: ("caida_simultanea", "mes", False),
    QualityFlagBits.REFERENCIA_RESPALDO: ("referencia_respaldo", "mes", False),
    QualityFlagBits.CALIBRACION_BAJA_CONF: ("calibracion_baja_conf", "fila", False),
}


def bit_or_flags(flags: list[int]) -> int:
    """Aggregates regional `quality_flag` values with bitwise OR (`bit_or` SQL equivalent)."""
    combined = 0
    for f in flags:
        combined |= int(f)
    return combined


def decode_quality_flags(flag: int) -> list[dict[str, Any]]:
    """Decodes an 8-bit `quality_flag` integer into structured v0.2 flag descriptors."""
    decoded: list[dict[str, Any]] = []
    for bit, label_es in QUALITY_FLAG_LABELS_ES.items():
        if flag & bit:
            code, scope, excludes_baseline = QUALITY_FLAG_CODES_V02[bit]
            decoded.append(
                {
                    "bit": int(bit),
                    "code": code,
                    "scope": scope,
                    "excludes_baseline": excludes_baseline,
                    "label_es": label_es,
                }
            )
    return decoded


# =====================================================================
# PYDANTIC CONTRACTS FOR `harmonized.cell_month` & EXTENSIBLE ANALYTICS
# =====================================================================
class HarmonizedCellMonthRow(BaseModel):
    """Direct domain representation of a row in `harmonized.cell_month` (0.25° × 0.25°)."""

    month: date
    cell_id: int = Field(ge=0, lt=TOTAL_GRID_CELLS)
    lat_center: float = Field(ge=-90.0, le=90.0)
    lon_center: float = Field(ge=-180.0, le=360.0)
    cell_area_km2: float = Field(gt=0.0)

    # Harmonized Aqua-equivalent values (primary series)
    n_eq: float = Field(ge=0.0, description="Harmonized active fire count (Aqua-equivalent)")
    f_eq: float = Field(ge=0.0, description="Harmonized instantaneous FRP in MW (Aqua-equivalent)")

    # Provenance (`smallint NOT NULL`: 2=Aqua, 3=SNPP, 4=N20, 5=N21)
    ref_sat: int = Field(ge=2, le=5)
    sensors: str

    # Raw per-satellite counts & FRP (for audit/comparison; NEVER sum VIIRS sensors directly)
    n_terra: int = 0
    n_aqua: int = 0
    n_snpp: int = 0
    n_n20: int = 0
    n_n21: int = 0
    frp_terra: float = 0.0
    frp_aqua: float = 0.0
    frp_snpp: float = 0.0
    frp_n20: float = 0.0
    frp_n21: float = 0.0

    # Quality & method tracking
    quality_flag: int = 0
    method_version: str = DEFAULT_METHOD_VERSION
    analysis_metrics: Optional[dict[str, Any]] = Field(
        default=None,
        description="Extensible metadata slot compliant with TEAM_DATA_CONTRACT Golden Rule.",
    )


AnomalySeverityClass = Literal["lte_50", "50_75", "75_90", "gt_90", "unavailable"]


class MonthlyRegionAggregate(BaseModel):
    """Monthly sum of harmonized and raw values across all active cells inside an AOI."""

    month: date
    year: int
    month_num: int
    n_eq: float
    f_eq: float
    frp_density_mw_km2: float
    area_region_km2: float
    quality_flag: int
    quality_flags_decoded: list[dict[str, Any]] = Field(default_factory=list)
    active_cell_count: int
    # Terra kept as its own non-harmonized morning/drift-affected series
    n_terra: int = 0
    frp_terra: float = 0.0
    raw_by_satellite: dict[str, dict[str, float | int]] = Field(default_factory=dict)
    method_version: str = DEFAULT_METHOD_VERSION


class MonthlyAnomalyResult(BaseModel):
    """Calendar cell result combining regional sums with percentile & robust log1p-MAD anomaly."""

    month: date
    year: int
    month_num: int
    n_eq: float
    f_eq: float
    frp_density_mw_km2: float
    quality_flag: int
    quality_flags_decoded: list[dict[str, Any]] = Field(default_factory=list)
    excluded_from_baseline: bool = False
    baseline_years_count: int = 0
    anomaly_available: bool = False
    unavailable_reason: Optional[str] = None
    percentile: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    severity_class: AnomalySeverityClass = "unavailable"
    is_series_record: bool = False
    z_robust_log1p: Optional[float] = None
    ratio_to_median: Optional[float] = None
    method_version: str = DEFAULT_METHOD_VERSION


# =====================================================================
# GRID GEOMETRY & SPHERICAL CELL AREA (SECTION 3)
# =====================================================================
def spherical_cell_area_km2(lat_south_deg: float, lat_north_deg: float, dlon_deg: float = GRID_STEP_DEG) -> float:
    """
    Computes exact spherical surface area of a 0.25° grid cell:
        A = R^2 * dlambda * (sin(phi_north) - sin(phi_south))
    Matches doc benchmarks (~773 km2 at equator, ~387 km2 at 60 deg).
    """
    s = max(-90.0, min(90.0, lat_south_deg))
    n = max(-90.0, min(90.0, lat_north_deg))
    if n <= s:
        return 0.0
    dlambda = math.radians(dlon_deg)
    return (EARTH_RADIUS_KM ** 2) * dlambda * (math.sin(math.radians(n)) - math.sin(math.radians(s)))


def _clamp_lon_signed_180(lon: float) -> float:
    if lon >= 180.0:
        return 179.999999
    if lon < -180.0:
        return -180.0
    return lon


def _lat_range_to_south_indices(min_lat: float, max_lat: float) -> tuple[int, int]:
    """Maps [min_lat, max_lat] to inclusive south-based latitude band indices [0..719]."""
    lo = max(-90.0, min(90.0, min(min_lat, max_lat)))
    hi = max(-90.0, min(90.0, max(min_lat, max_lat)))
    idx_min = max(0, min(GRID_ROWS - 1, int(math.floor((lo + 90.0) / GRID_STEP_DEG))))
    # Subtract tiny epsilon when hi lands exactly on a cell boundary (> lo)
    hi_adj = hi - 1e-9 if hi > lo and ((hi + 90.0) % GRID_STEP_DEG == 0.0) else hi
    idx_max = max(0, min(GRID_ROWS - 1, int(math.floor((hi_adj + 90.0) / GRID_STEP_DEG))))
    if idx_max < idx_min:
        idx_max = idx_min
    return idx_min, idx_max


def _lon_to_col_index(lon: float) -> int:
    clamped = _clamp_lon_signed_180(lon)
    return max(0, min(GRID_COLS - 1, int(math.floor((clamped + 180.0) / GRID_STEP_DEG))))


def _lon_span_to_col_ranges(min_lon: float, max_lon: float) -> list[tuple[int, int]]:
    """
    Converts [min_lon, max_lon] into 1 or 2 inclusive column ranges.
    When min_lon > max_lon, assumes antimeridian (+-180°) crossing and returns 2 ranges.
    """
    if min_lon <= max_lon:
        col_start = _lon_to_col_index(min_lon)
        hi_adj = max_lon - 1e-9 if max_lon > min_lon and ((max_lon + 180.0) % GRID_STEP_DEG == 0.0) else max_lon
        col_end = max(col_start, _lon_to_col_index(hi_adj))
        return [(col_start, col_end)]

    # Antimeridian split: [min_lon .. 180) and [-180 .. max_lon]
    col_left_start = _lon_to_col_index(min_lon)
    hi_adj = max_lon - 1e-9 if ((max_lon + 180.0) % GRID_STEP_DEG == 0.0) else max_lon
    col_right_end = _lon_to_col_index(hi_adj)
    return [(col_left_start, GRID_COLS - 1), (0, col_right_end)]


def row_col_to_cell_id(
    south_idx: int,
    col_idx: int,
    row_origin: RowOrigin = "south_to_north",
) -> int:
    """Converts a south-based latitude index (0..719) and column (0..1439) to `cell_id`."""
    row = (GRID_ROWS - 1 - south_idx) if row_origin == "north_to_south" else south_idx
    return row * GRID_COLS + col_idx


def cell_id_to_center_and_area(
    cell_id: int,
    row_origin: RowOrigin = "south_to_north",
) -> tuple[float, float, float]:
    """
    Converts `cell_id` (0..1036799) to `(lat_center, lon_center, cell_area_km2)`.
    Matches verified PostgreSQL formula (CONTRATO_DATOS_WEB_RESPUESTA_V02.md Sec 3.1-3.2):
      fila = cell_id // 1440 (0 = -89.875° Sur), columna = cell_id % 1440 (0 = -179.875° Oeste)
    """
    if not (0 <= cell_id < TOTAL_GRID_CELLS):
        raise ValueError(f"cell_id out of range [0, {TOTAL_GRID_CELLS - 1}]: {cell_id}")
    raw_row = cell_id // GRID_COLS
    col_idx = cell_id % GRID_COLS
    south_idx = (GRID_ROWS - 1 - raw_row) if row_origin == "north_to_south" else raw_row
    lat_center = -90.0 + (south_idx + 0.5) * GRID_STEP_DEG
    lon_center = -180.0 + (col_idx + 0.5) * GRID_STEP_DEG
    area_km2 = spherical_cell_area_km2(lat_center - 0.125, lat_center + 0.125, GRID_STEP_DEG)
    return lat_center, lon_center, area_km2


def bbox_to_grid_indices(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> tuple[int, int, list[tuple[int, int]]]:
    """Returns `(south_idx_min, south_idx_max, col_ranges)` for an AOI bounding box."""
    return _lat_range_to_south_indices(min_lat, max_lat) + (_lon_span_to_col_ranges(min_lon, max_lon),)


def aoi_cell_count(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> int:
    """Returns total number of 0.25° grid cells inside the bounding box."""
    s_min, s_max, col_ranges = bbox_to_grid_indices(min_lon, min_lat, max_lon, max_lat)
    total_cols = sum((c_end - c_start + 1) for c_start, c_end in col_ranges)
    return (s_max - s_min + 1) * total_cols


def cell_touches_low_confidence_band(lat_center: float) -> bool:
    """True when a cell lies inside extreme v0.2 low-confidence calibration bands (-60°, 70°, polar)."""
    return lat_center < -50.0 or lat_center >= 70.0


def bbox_touches_low_confidence_band(min_lat: float, max_lat: float) -> bool:
    """True when an AOI overlaps extreme v0.2 calibration bands (-60°, 70°, polar) triggering bit 7."""
    lo = max(-90.0, min(min_lat, max_lat))
    hi = min(90.0, max(min_lat, max_lat))
    return lo < -50.0 or hi >= 70.0


def bbox_to_cell_id_ranges(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    row_origin: RowOrigin = "south_to_north",
) -> list[tuple[int, int]]:
    """
    Translates an AOI bounding box into contiguous `(start_cell_id, end_cell_id)` tuples
    for fast `cell_id BETWEEN :a AND :b` SQL queries (supports +-180° antimeridian split).
    """
    s_min, s_max, col_ranges = bbox_to_grid_indices(min_lon, min_lat, max_lon, max_lat)

    ranges: list[tuple[int, int]] = []
    for south_idx in range(s_min, s_max + 1):
        for col_start, col_end in col_ranges:
            c_start = row_col_to_cell_id(south_idx, col_start, row_origin=row_origin)
            c_end = row_col_to_cell_id(south_idx, col_end, row_origin=row_origin)
            ranges.append((min(c_start, c_end), max(c_start, c_end)))

    ranges.sort(key=lambda r: r[0])
    return ranges


def aggregate_cells_to_1deg(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Dynamically rolls up 0.25° map cells into 1° × 1° blocks for zoomed-out map rendering
    (> 20,000 visible cells), matching Sec 6c of `CONTRATO_DATOS_WEB_RESPUESTA_V02.md`:
      block_id = ((cell_id // 1440) // 4) * 360 + ((cell_id % 1440) // 4)
    """
    blocks: dict[int, dict[str, Any]] = {}
    for cell in cells:
        cid = int(cell["cell_id"])
        block_row = (cid // GRID_COLS) // 4
        block_col = (cid % GRID_COLS) // 4
        block_id = block_row * GRID_COLS_1DEG + block_col

        lat_center = -90.0 + block_row + 0.5
        lon_center = -180.0 + block_col + 0.5

        bucket = blocks.get(block_id)
        if bucket is None:
            area_1deg_km2 = round(spherical_cell_area_km2(lat_center - 0.5, lat_center + 0.5, GRID_STEP_1DEG), 3)
            blocks[block_id] = {
                "cell_id": block_id,
                "block_id": block_id,
                "lat_center": round(lat_center, 3),
                "lon_center": round(lon_center, 3),
                "cell_area_km2": area_1deg_km2,
                "n_eq": float(cell.get("n_eq", 0.0)),
                "f_eq": float(cell.get("f_eq", 0.0)),
                "n_terra": int(cell.get("n_terra", 0)),
                "frp_terra": float(cell.get("frp_terra", 0.0)),
                "quality_flag": int(cell.get("quality_flag", 0)),
                "active_months": int(cell.get("active_months", 1)),
                "subcell_count": 1,
                "resolution_deg": GRID_STEP_1DEG,
            }
        else:
            bucket["n_eq"] += float(cell.get("n_eq", 0.0))
            bucket["f_eq"] += float(cell.get("f_eq", 0.0))
            bucket["n_terra"] += int(cell.get("n_terra", 0))
            bucket["frp_terra"] += float(cell.get("frp_terra", 0.0))
            bucket["quality_flag"] |= int(cell.get("quality_flag", 0))
            bucket["active_months"] = max(bucket["active_months"], int(cell.get("active_months", 1)))
            bucket["subcell_count"] += 1

    rolled_up: list[dict[str, Any]] = []
    for block_id in sorted(blocks):
        b = blocks[block_id]
        b["n_eq"] = round(b["n_eq"], 2)
        b["f_eq"] = round(b["f_eq"], 2)
        b["frp_terra"] = round(b["frp_terra"], 2)
        b["quality_flags_decoded"] = decode_quality_flags(b["quality_flag"])
        rolled_up.append(b)
    return rolled_up


def compute_aoi_grid_area_km2(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> float:
    """
    Computes the FULL area (km2) of all 0.25° grid cells covered by the AOI,
    including cells with zero fire rows (essential because `harmonized.cell_month` is sparse).
    """
    s_min, s_max, col_ranges = bbox_to_grid_indices(min_lon, min_lat, max_lon, max_lat)
    total_cols = sum((c_end - c_start + 1) for c_start, c_end in col_ranges)

    total_area = 0.0
    for south_idx in range(s_min, s_max + 1):
        lat_s = -90.0 + south_idx * GRID_STEP_DEG
        lat_n = lat_s + GRID_STEP_DEG
        total_area += spherical_cell_area_km2(lat_s, lat_n) * total_cols
    return round(total_area, 3)


def iter_calendar_months(start_month: date, end_month: date) -> list[date]:
    """Generates an unbroken monthly calendar sequence (`generate_series` equivalent)."""
    months: list[date] = []
    y, m = start_month.year, start_month.month
    while (y, m) <= (end_month.year, end_month.month):
        months.append(date(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


_V02_REFERENCE_EXCEPTIONS: dict[date, tuple[int, str, int, bool]] = {
    date(2012, 1, 1): (3, "SNPP", int(QualityFlagBits.VIIRS_PARCIAL), True),
    date(2012, 3, 1): (
        3,
        "SNPP",
        int(QualityFlagBits.REF_INCOMPLETA_HUECOS | QualityFlagBits.REF_INCOMPLETA_CAIDAS),
        True,
    ),
    date(2023, 7, 1): (5, "N21 (respaldo de N20)", int(QualityFlagBits.REFERENCIA_RESPALDO), False),
    date(2026, 7, 1): (4, "N20", int(QualityFlagBits.ULTIMO_MES_STANDARD), False),
    date(2026, 8, 1): (
        2,
        "Aqua (solo MODIS / deriva)",
        int(QualityFlagBits.ULTIMO_MES_STANDARD | QualityFlagBits.SOLO_MODIS_DERIVA),
        True,
    ),
}


def get_v02_reference_plan(
    start_month: date = SERIES_START_MONTH,
    end_month: date = SERIES_END_MONTH,
) -> list[dict[str, Any]]:
    """
    Returns the static `harmonized.reference_plan` table rows (176 months for 2012-01..2026-08)
    matching `docs/CONTRATO_DATOS_WEB_RESPUESTA_V02.md` Sec 8.3.
    """
    plan: list[dict[str, Any]] = []
    for m_dt in iter_calendar_months(start_month, end_month):
        if m_dt in _V02_REFERENCE_EXCEPTIONS:
            ref_sat, sensors, q_flag, excluded = _V02_REFERENCE_EXCEPTIONS[m_dt]
        elif m_dt < date(2020, 1, 1):
            ref_sat, sensors, q_flag, excluded = 3, "SNPP", 0, False
        else:
            ref_sat, sensors, q_flag, excluded = 4, "N20", 0, False

        plan.append(
            {
                "month": m_dt,
                "ref_sat": ref_sat,
                "sensors": sensors,
                "quality_flag": q_flag,
                "excluded_from_baseline": excluded,
            }
        )
    return plan


def get_v02_reference_quality_map(
    start_month: date = SERIES_START_MONTH,
    end_month: date = SERIES_END_MONTH,
) -> dict[date, int]:
    """Returns `{month: quality_flag}` from `reference_plan` so zero-fire months keep month flags."""
    return {
        row["month"]: row["quality_flag"]
        for row in get_v02_reference_plan(start_month, end_month)
    }


# =====================================================================
# REGIONAL AGGREGATION & ANOMALY ENGINE (SECTIONS 3 & 4)
# =====================================================================
def aggregate_rows_by_month(
    rows: list[HarmonizedCellMonthRow],
    area_region_km2: float,
    all_months: Optional[list[date]] = None,
    monthly_quality_map: Optional[dict[date, int]] = None,
    default_method_version: str = DEFAULT_METHOD_VERSION,
) -> list[MonthlyRegionAggregate]:
    """
    Aggregates sparse `harmonized.cell_month` rows into one regional time-series entry per month.
    When `all_months` is provided (`generate_series LEFT JOIN` pattern), missing sparse months are
    filled as `0.0` instead of gaps, and `monthly_quality_map` injects month-level observation flags
    so zero-activity months never lose quality/exclusion metadata.
    """
    if area_region_km2 <= 0:
        raise ValueError("area_region_km2 must be positive")
    if not rows and not all_months:
        return []

    versions = {r.method_version for r in rows}
    if len(versions) > 1:
        raise ValueError(f"Cannot mix method_version values in a single series: {sorted(versions)}")
    method_version = next(iter(versions)) if versions else default_method_version

    buckets: dict[date, list[HarmonizedCellMonthRow]] = {}
    for row in rows:
        buckets.setdefault(row.month, []).append(row)

    target_months = sorted(set(all_months) | set(buckets.keys())) if all_months else sorted(buckets.keys())
    quality_lookup = monthly_quality_map or {}

    aggregates: list[MonthlyRegionAggregate] = []
    for month_dt in target_months:
        group = buckets.get(month_dt, [])
        n_eq_sum = sum(r.n_eq for r in group)
        f_eq_sum = sum(r.f_eq for r in group)
        combined_flag = bit_or_flags([r.quality_flag for r in group] + [quality_lookup.get(month_dt, 0)])

        n_terra = sum(r.n_terra for r in group)
        frp_terra = sum(r.frp_terra for r in group)
        raw_by_sat = {
            "terra": {"count": n_terra, "frp_mw": round(frp_terra, 2)},
            "aqua": {"count": sum(r.n_aqua for r in group), "frp_mw": round(sum(r.frp_aqua for r in group), 2)},
            "snpp": {"count": sum(r.n_snpp for r in group), "frp_mw": round(sum(r.frp_snpp for r in group), 2)},
            "n20": {"count": sum(r.n_n20 for r in group), "frp_mw": round(sum(r.frp_n20 for r in group), 2)},
            "n21": {"count": sum(r.n_n21 for r in group), "frp_mw": round(sum(r.frp_n21 for r in group), 2)},
        }

        aggregates.append(
            MonthlyRegionAggregate(
                month=month_dt,
                year=month_dt.year,
                month_num=month_dt.month,
                n_eq=round(n_eq_sum, 4),
                f_eq=round(f_eq_sum, 4),
                frp_density_mw_km2=round(f_eq_sum / area_region_km2, 6),
                area_region_km2=round(area_region_km2, 3),
                quality_flag=combined_flag,
                quality_flags_decoded=decode_quality_flags(combined_flag),
                active_cell_count=len(group),
                n_terra=n_terra,
                frp_terra=round(frp_terra, 2),
                raw_by_satellite=raw_by_sat,
                method_version=method_version,
            )
        )
    return aggregates


def _classify_percentile(p: float) -> AnomalySeverityClass:
    if p <= 0.50:
        return "lte_50"
    if p <= 0.75:
        return "50_75"
    if p <= 0.90:
        return "75_90"
    return "gt_90"


def compute_cell_month_calendar_anomalies(
    monthly_series: list[MonthlyRegionAggregate],
    metric: Literal["n_eq", "f_eq"] = "n_eq",
    exclude_mask: int = BASELINE_EXCLUDE_MASK,
    min_baseline_years: int = MIN_BASELINE_YEARS,
) -> list[MonthlyAnomalyResult]:
    """
    Computes Burning Activity Calendar anomalies over the full regional monthly series
    following Section 4 of `DOCUMENTACION_TABLA_ARMONIZADA.md`:
      1. Baseline for (y, m) uses all other years (y' != y) of calendar month m
         without excluded quality flags.
      2. Minimum 10 valid baseline years required; otherwise anomaly is marked unavailable.
      3. Primary metric: mid-rank percentile `(#{base < X} + 0.5 * #{base == X}) / |base|`.
      4. Secondary metric: robust log1p z-score using `1.4826 * MAD`; if `MAD == 0`,
         falls back to ratio against raw baseline median.
    """
    if not monthly_series:
        return []

    versions = {m.method_version for m in monthly_series}
    if len(versions) > 1:
        raise ValueError(f"Cannot compute anomalies across mixed method_version values: {sorted(versions)}")

    by_calendar_month: dict[int, list[MonthlyRegionAggregate]] = {}
    for entry in monthly_series:
        by_calendar_month.setdefault(entry.month_num, []).append(entry)

    results: list[MonthlyAnomalyResult] = []
    for entry in sorted(monthly_series, key=lambda e: e.month):
        x = entry.n_eq if metric == "n_eq" else entry.f_eq
        is_excluded = bool(entry.quality_flag & exclude_mask)

        peers = by_calendar_month.get(entry.month_num, [])
        base_entries = [
            p for p in peers
            if p.year != entry.year and not (p.quality_flag & exclude_mask)
        ]
        base_vals = [p.n_eq if metric == "n_eq" else p.f_eq for p in base_entries]

        if len(base_vals) < min_baseline_years:
            results.append(
                MonthlyAnomalyResult(
                    month=entry.month,
                    year=entry.year,
                    month_num=entry.month_num,
                    n_eq=entry.n_eq,
                    f_eq=entry.f_eq,
                    frp_density_mw_km2=entry.frp_density_mw_km2,
                    quality_flag=entry.quality_flag,
                    quality_flags_decoded=entry.quality_flags_decoded,
                    excluded_from_baseline=is_excluded,
                    baseline_years_count=len(base_vals),
                    anomaly_available=False,
                    unavailable_reason=f"insufficient_baseline_years (<{min_baseline_years})",
                    severity_class="unavailable",
                    method_version=entry.method_version,
                )
            )
            continue

        less_count = sum(1 for v in base_vals if v < x)
        eq_count = sum(1 for v in base_vals if v == x)
        percentile = round((less_count + 0.5 * eq_count) / len(base_vals), 4)
        severity = _classify_percentile(percentile)
        is_record = x > max(base_vals)

        log_base = [math.log1p(max(0.0, v)) for v in base_vals]
        med_log = statistics.median(log_base)
        mad_log = statistics.median([abs(v - med_log) for v in log_base])

        z_robust: Optional[float] = None
        ratio_to_median: Optional[float] = None
        if mad_log > 0.0:
            z_robust = round((math.log1p(max(0.0, x)) - med_log) / (MAD_NORMAL_CONSTANT * mad_log), 4)
        else:
            raw_med = statistics.median(base_vals)
            ratio_to_median = round(x / raw_med, 4) if raw_med > 0.0 else None

        results.append(
            MonthlyAnomalyResult(
                month=entry.month,
                year=entry.year,
                month_num=entry.month_num,
                n_eq=entry.n_eq,
                f_eq=entry.f_eq,
                frp_density_mw_km2=entry.frp_density_mw_km2,
                quality_flag=entry.quality_flag,
                quality_flags_decoded=entry.quality_flags_decoded,
                excluded_from_baseline=is_excluded,
                baseline_years_count=len(base_vals),
                anomaly_available=True,
                percentile=percentile,
                severity_class=severity,
                is_series_record=is_record,
                z_robust_log1p=z_robust,
                ratio_to_median=ratio_to_median,
                method_version=entry.method_version,
            )
        )

    return results
