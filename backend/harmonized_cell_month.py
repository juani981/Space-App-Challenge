"""
Domain models, grid geometry, quality-flag bitwise helpers, and anomaly engine
for the team's harmonized global monthly table: `harmonized.cell_month`.

Based strictly on `docs/DOCUMENTACION_TABLA_ARMONIZADA.md` (method_version: v0.1-provisional).
Pending items awaiting DDL / Phase-1 confirmation from Teammates 1 & 2 are
explicitly isolated inside `PENDING_TEAM_CONFIRMATION` so they can be swapped
in a single localized edit without touching downstream consumers.
"""

from __future__ import annotations

import math
import statistics
from datetime import date
from enum import IntFlag
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

# =====================================================================
# GLOBAL GRID CONSTANTS (CONFIRMED IN DOCUMENTACION_TABLA_ARMONIZADA.md)
# =====================================================================
GRID_ROWS = 720
GRID_COLS = 1440
TOTAL_GRID_CELLS = GRID_ROWS * GRID_COLS  # 1,036,800 global cells
GRID_STEP_DEG = 0.25
EARTH_RADIUS_KM = 6371.0

DEFAULT_METHOD_VERSION = "v0.1-provisional"
MIN_BASELINE_YEARS = 10
MAD_NORMAL_CONSTANT = 1.4826

RowOrigin = Literal["north_to_south", "south_to_north"]
LonConvention = Literal["signed_180", "unsigned_360"]

# =====================================================================
# PENDING CONFIRMATIONS (Sección 6 de DOCUMENTACION_TABLA_ARMONIZADA.md)
# Update these values once the other team returns the exact DDL & Phase-1 spec.
# =====================================================================
PENDING_TEAM_CONFIRMATION: dict[str, Any] = {
    "cell_id_row_origin": "north_to_south",   # Provisional: confirm row=0 (+89.875 vs -89.875)
    "lon_convention": "signed_180",           # Provisional: [-180, 180] vs [0, 360]
    "quality_flag_bitmask_confirmed": False,  # Confirm exact bit exponents in Phase 1 doc
    "ref_sat_modis_only_value": None,         # Confirm NULL vs special token in 2026-08
    "frp_matches_count_filters": True,        # Confirm type=0 & no-low-conf on frp_*
    "auxiliary_tables": {
        "grid_areas_table": None,
        "one_degree_table": None,
        "climatology_table": None,
        "gaps_catalog_table": None,
    },
}


class QualityFlagBits(IntFlag):
    """
    8-bit quality bitmask for `harmonized.cell_month.quality_flag` (`smallint`).
    PROVISIONAL bit positions pending Phase 1 design confirmation.
    """

    NONE = 0
    PARTIAL_MONTH = 1 << 0             # e.g., 2012-01 (S-NPP started Jan 20)
    LAST_MONTH = 1 << 1                # e.g., 2026-08 (last month of series)
    MODIS_ONLY = 1 << 2                # No VIIRS available (Aqua direct, subject to drift)
    GAPS = 1 << 3                      # Reference satellite had >= 5 missing days in month
    FALLBACK = 1 << 4                  # Next VIIRS satellite in chain used due to gap
    PROVISIONAL_CALIBRATION = 1 << 5   # Calculated with v0.1 calibration


# Baseline anomaly exclusion mask (Section 3: exclude gaps >= 5d, MODIS-only, last month, partial month)
BASELINE_EXCLUDE_MASK = (
    QualityFlagBits.GAPS
    | QualityFlagBits.MODIS_ONLY
    | QualityFlagBits.LAST_MONTH
    | QualityFlagBits.PARTIAL_MONTH
)

QUALITY_FLAG_LABELS_ES: dict[QualityFlagBits, str] = {
    QualityFlagBits.PARTIAL_MONTH: "Mes parcial",
    QualityFlagBits.LAST_MONTH: "Último mes de la serie",
    QualityFlagBits.MODIS_ONLY: "Solo MODIS (Aqua directo)",
    QualityFlagBits.GAPS: "Huecos (≥ 5 días sin datos)",
    QualityFlagBits.FALLBACK: "Satélite de respaldo",
    QualityFlagBits.PROVISIONAL_CALIBRATION: "Calibración provisional (v0.1)",
}


def bit_or_flags(flags: list[int]) -> int:
    """Aggregates regional `quality_flag` values with bitwise OR (`bit_or` SQL equivalent)."""
    combined = 0
    for f in flags:
        combined |= int(f)
    return combined


def decode_quality_flags(flag: int) -> list[dict[str, Any]]:
    """Decodes an 8-bit `quality_flag` integer into structured flag descriptors."""
    decoded: list[dict[str, Any]] = []
    for bit, label_es in QUALITY_FLAG_LABELS_ES.items():
        if flag & bit:
            decoded.append({"bit": int(bit), "code": bit.name.lower(), "label_es": label_es})
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

    # Provenance
    ref_sat: Optional[str] = None
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
    row_origin: RowOrigin = PENDING_TEAM_CONFIRMATION["cell_id_row_origin"],
) -> int:
    """Converts a south-based latitude index (0..719) and column (0..1439) to `cell_id`."""
    row = (GRID_ROWS - 1 - south_idx) if row_origin == "north_to_south" else south_idx
    return row * GRID_COLS + col_idx


def bbox_to_grid_indices(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> tuple[int, int, list[tuple[int, int]]]:
    """Returns `(south_idx_min, south_idx_max, col_ranges)` for an AOI bounding box."""
    return _lat_range_to_south_indices(min_lat, max_lat) + (_lon_span_to_col_ranges(min_lon, max_lon),)


def bbox_to_cell_id_ranges(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    row_origin: RowOrigin = PENDING_TEAM_CONFIRMATION["cell_id_row_origin"],
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


# =====================================================================
# REGIONAL AGGREGATION & ANOMALY ENGINE (SECTIONS 3 & 4)
# =====================================================================
def aggregate_rows_by_month(
    rows: list[HarmonizedCellMonthRow],
    area_region_km2: float,
) -> list[MonthlyRegionAggregate]:
    """
    Aggregates sparse `harmonized.cell_month` rows into one regional time-series entry per month.
    Enforces the scientific rule that `method_version` cannot be mixed within a single series.
    """
    if area_region_km2 <= 0:
        raise ValueError("area_region_km2 must be positive")
    if not rows:
        return []

    versions = {r.method_version for r in rows}
    if len(versions) > 1:
        raise ValueError(f"Cannot mix method_version values in a single series: {sorted(versions)}")
    method_version = next(iter(versions))

    buckets: dict[date, list[HarmonizedCellMonthRow]] = {}
    for row in rows:
        buckets.setdefault(row.month, []).append(row)

    aggregates: list[MonthlyRegionAggregate] = []
    for month_dt in sorted(buckets.keys()):
        group = buckets[month_dt]
        n_eq_sum = sum(r.n_eq for r in group)
        f_eq_sum = sum(r.f_eq for r in group)
        combined_flag = bit_or_flags([r.quality_flag for r in group])

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
