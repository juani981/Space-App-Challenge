"""
PostgreSQL 18 Adapter & Deterministic 2012-2026 Stub Service for `harmonized.cell_month`.

Provides:
- `query_postgres_cell_month`: Queries `harmonized.cell_month` safely with either
  `(lat_center, lon_center)` ranges (while `cell_id` row origin awaits confirmation) or
  contiguous `cell_id BETWEEN` ranges, falling back cleanly if the DB is absent/empty.
- `generate_stub_cell_month_rows`: Deterministic sparse `0.25° x 0.25°` monthly stub
  covering `2012-01` through `2026-08` with realistic seasonal patterns and quality flags.
- `query_cell_month_aoi`: Orchestrates full-series baseline anomaly calculation,
  active map cell aggregation for `[start_date, end_date]`, and metadata audit.
- `export_cell_month_csv`: RFC-4180 CSV export (Option 1 of DOCUMENTACION_TABLA_ARMONIZADA.md).
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import math
from datetime import date
from typing import Any, Literal, Optional

from db import DATABASE_URL
from harmonized_cell_month import (
    DEFAULT_METHOD_VERSION,
    GRID_STEP_DEG,
    PENDING_TEAM_CONFIRMATION,
    HarmonizedCellMonthRow,
    QualityFlagBits,
    aggregate_rows_by_month,
    bit_or_flags,
    bbox_to_cell_id_ranges,
    bbox_to_grid_indices,
    compute_aoi_grid_area_km2,
    compute_cell_month_calendar_anomalies,
    decode_quality_flags,
    row_col_to_cell_id,
    spherical_cell_area_km2,
)
from team_contract import DATA_SOURCE_MODE

logger = logging.getLogger("backend.cell_month")

SERIES_START_DATE = date(2012, 1, 1)
SERIES_END_DATE = date(2026, 8, 1)


def _iter_series_months(start: date = SERIES_START_DATE, end: date = SERIES_END_DATE) -> list[date]:
    months: list[date] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(date(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _parse_iso_month(date_str: Optional[str], fallback: date) -> date:
    if not date_str:
        return fallback
    try:
        parts = date_str[:10].split("-")
        return date(int(parts[0]), int(parts[1]), 1)
    except Exception:
        return fallback


def _build_spatial_where_clause(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    use_cell_id_ranges: bool,
) -> tuple[str, list[Any]]:
    """
    Builds parameterized SQL spatial predicate.
    While `cell_id` row origin is unconfirmed, `lat_center`/`lon_center` avoids orientation ambiguity
    (as recommended in Section 3 of `DOCUMENTACION_TABLA_ARMONIZADA.md`).
    """
    lo_lat, hi_lat = min(min_lat, max_lat), max(min_lat, max_lat)

    if use_cell_id_ranges:
        ranges = bbox_to_cell_id_ranges(min_lon, lo_lat, max_lon, hi_lat)
        clauses = ["(cell_id BETWEEN %s AND %s)" for _ in ranges]
        params: list[Any] = []
        for a, b in ranges:
            params.extend([a, b])
        return "(" + " OR ".join(clauses) + ")", params

    if min_lon <= max_lon:
        return (
            "lat_center BETWEEN %s AND %s AND lon_center BETWEEN %s AND %s",
            [lo_lat, hi_lat, min_lon, max_lon],
        )

    # Antimeridian split on lon_center
    return (
        "lat_center BETWEEN %s AND %s AND (lon_center >= %s OR lon_center <= %s)",
        [lo_lat, hi_lat, min_lon, max_lon],
    )


def query_postgres_cell_month(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    start_month: date = SERIES_START_DATE,
    end_month: date = SERIES_END_DATE,
    use_cell_id_ranges: bool = False,
) -> Optional[list[HarmonizedCellMonthRow]]:
    """
    Queries PostgreSQL 18 `harmonized.cell_month` across the full baseline window.
    Returns `None` if `psycopg` is unavailable, schema doesn't exist, or table is empty
    so the API degrades gracefully to deterministic stub data during development.
    """
    try:
        import psycopg
    except ImportError:
        logger.debug("psycopg not installed; using cell_month stub fallback")
        return None

    spatial_sql, spatial_params = _build_spatial_where_clause(
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
        use_cell_id_ranges=use_cell_id_ranges,
    )

    sql = f"""
    SELECT
        month, cell_id, lat_center, lon_center, cell_area_km2,
        n_eq, f_eq, ref_sat, sensors,
        n_terra, n_aqua, n_snpp, n_n20, n_n21,
        frp_terra, frp_aqua, frp_snpp, frp_n20, frp_n21,
        quality_flag, method_version
    FROM harmonized.cell_month
    WHERE month BETWEEN %s AND %s
      AND {spatial_sql}
    ORDER BY month ASC, cell_id ASC;
    """

    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, [start_month, end_month, *spatial_params])
                raw_rows = cur.fetchall()
                if not raw_rows:
                    return None
                return [
                    HarmonizedCellMonthRow(
                        month=r[0],
                        cell_id=int(r[1]),
                        lat_center=float(r[2]),
                        lon_center=float(r[3]),
                        cell_area_km2=float(r[4]),
                        n_eq=float(r[5]),
                        f_eq=float(r[6]),
                        ref_sat=str(r[7]) if r[7] is not None else None,
                        sensors=str(r[8]),
                        n_terra=int(r[9]),
                        n_aqua=int(r[10]),
                        n_snpp=int(r[11]),
                        n_n20=int(r[12]),
                        n_n21=int(r[13]),
                        frp_terra=float(r[14]),
                        frp_aqua=float(r[15]),
                        frp_snpp=float(r[16]),
                        frp_n20=float(r[17]),
                        frp_n21=float(r[18]),
                        quality_flag=int(r[19]),
                        method_version=str(r[20]),
                    )
                    for r in raw_rows
                ]
    except Exception as exc:
        logger.warning("PostgreSQL cell_month query failed (%s); falling back to stub", exc)
        return None


def _month_provenance_and_flags(month_dt: date) -> tuple[Optional[str], str, int]:
    """Simulates documented quality flags and VIIRS reference chain across 2012-2026."""
    base_flag = int(QualityFlagBits.PROVISIONAL_CALIBRATION)
    ym = (month_dt.year, month_dt.month)

    if ym == (2012, 1):
        return "SNPP", "SNPP", base_flag | int(QualityFlagBits.PARTIAL_MONTH)
    if ym == (2026, 8):
        return (
            PENDING_TEAM_CONFIRMATION["ref_sat_modis_only_value"],
            "AQUA_ONLY",
            base_flag | int(QualityFlagBits.LAST_MONTH) | int(QualityFlagBits.MODIS_ONLY),
        )
    if ym == (2022, 4):
        return "N20", "N20_FALLBACK", base_flag | int(QualityFlagBits.GAPS) | int(QualityFlagBits.FALLBACK)
    if ym == (2026, 7):
        return "N20", "N20_FALLBACK", base_flag | int(QualityFlagBits.GAPS) | int(QualityFlagBits.FALLBACK)

    if month_dt.year < 2018:
        return "SNPP", "SNPP", base_flag
    if month_dt.year < 2023:
        return "N20", "N20", base_flag
    return "N20", "N20+N21", base_flag


def _sample_aoi_cells(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    max_cells: int = 80,
) -> list[tuple[int, float, float, float]]:
    """
    Selects deterministic 0.25° grid cells inside the AOI up to `max_cells`
    so the stub stays fast (<30ms) even on continental viewports.
    """
    s_min, s_max, col_ranges = bbox_to_grid_indices(min_lon, min_lat, max_lon, max_lat)
    all_cols = [c for c_start, c_end in col_ranges for c in range(c_start, c_end + 1)]
    south_indices = list(range(s_min, s_max + 1))

    total_cells = len(south_indices) * len(all_cols)
    step = max(1, int(math.ceil(math.sqrt(total_cells / max_cells)))) if total_cells > max_cells else 1

    cells: list[tuple[int, float, float, float]] = []
    for s_idx in south_indices[::step]:
        lat_s = -90.0 + s_idx * GRID_STEP_DEG
        lat_c = round(lat_s + GRID_STEP_DEG / 2.0, 3)
        area = round(spherical_cell_area_km2(lat_s, lat_s + GRID_STEP_DEG), 2)
        for c_idx in all_cols[::step]:
            lon_c = round(-180.0 + (c_idx + 0.5) * GRID_STEP_DEG, 3)
            cell_id = row_col_to_cell_id(s_idx, c_idx)
            cells.append((cell_id, lat_c, lon_c, area))
            if len(cells) >= max_cells:
                return cells
    return cells


def generate_stub_cell_month_rows(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    start_month: date = SERIES_START_DATE,
    end_month: date = SERIES_END_DATE,
) -> list[HarmonizedCellMonthRow]:
    """
    Generates deterministic sparse `harmonized.cell_month` records across 2012-01..2026-08
    for development/testing when the real Postgres `.dump` is not loaded yet.
    """
    cells = _sample_aoi_cells(min_lon, min_lat, max_lon, max_lat)
    months = _iter_series_months(start_month, end_month)
    rows: list[HarmonizedCellMonthRow] = []

    for cell_id, lat_c, lon_c, area in cells:
        cell_seed = int(hashlib.md5(f"{cell_id}".encode()).hexdigest()[:8], 16)
        peak_month = 7 + (cell_seed % 3)  # Southern hemisphere dry-season peak (Jul/Aug/Sep)

        for m_dt in months:
            h_val = int(hashlib.md5(f"{cell_id}-{m_dt.isoformat()}".encode()).hexdigest()[:8], 16)
            seasonal_weight = 0.25 + 1.35 * math.exp(-((m_dt.month - peak_month) ** 2) / 3.5)

            # Sparse behavior: omit quiet off-season months deterministically
            if (h_val % 100) / 100.0 > min(0.88, 0.30 * seasonal_weight):
                continue

            extreme_mult = 2.6 if m_dt.year in (2020, 2024) else 1.0
            n_eq = round((1.5 + (h_val % 24) * 0.85) * seasonal_weight * extreme_mult, 2)
            f_eq = round(n_eq * (28.0 + (h_val % 45)), 1)

            ref_sat, sensors, q_flag = _month_provenance_and_flags(m_dt)
            is_modis_only = bool(q_flag & QualityFlagBits.MODIS_ONLY)

            # Terra drifts down ~30% in 2025-2026 as documented in Section 3
            terra_drift = 0.7 if m_dt.year >= 2025 else 1.0
            n_terra = max(0, int(round(n_eq * 0.55 * terra_drift)))
            n_aqua = max(0, int(round(n_eq)))
            n_snpp = 0 if is_modis_only else max(0, int(round(n_eq * 3.1)))
            n_n20 = 0 if (is_modis_only or m_dt.year < 2018) else max(0, int(round(n_eq * 3.4)))
            n_n21 = 0 if (is_modis_only or m_dt.year < 2023) else max(0, int(round(n_eq * 3.2)))

            rows.append(
                HarmonizedCellMonthRow(
                    month=m_dt,
                    cell_id=cell_id,
                    lat_center=lat_c,
                    lon_center=lon_c,
                    cell_area_km2=area,
                    n_eq=n_eq,
                    f_eq=f_eq,
                    ref_sat=ref_sat,
                    sensors=sensors,
                    n_terra=n_terra,
                    n_aqua=n_aqua,
                    n_snpp=n_snpp,
                    n_n20=n_n20,
                    n_n21=n_n21,
                    frp_terra=round(n_terra * 22.0, 1),
                    frp_aqua=round(f_eq, 1),
                    frp_snpp=round(n_snpp * 8.5, 1),
                    frp_n20=round(n_n20 * 8.2, 1),
                    frp_n21=round(n_n21 * 8.0, 1),
                    quality_flag=q_flag,
                    method_version=DEFAULT_METHOD_VERSION,
                )
            )

    return rows


def _aggregate_active_map_cells(window_rows: list[HarmonizedCellMonthRow]) -> list[dict[str, Any]]:
    """Collapses filtered `[start_date, end_date]` rows per spatial cell for map rendering."""
    by_cell: dict[int, list[HarmonizedCellMonthRow]] = {}
    for row in window_rows:
        by_cell.setdefault(row.cell_id, []).append(row)

    cells_out: list[dict[str, Any]] = []
    for cid, group in by_cell.items():
        first = group[0]
        q_flag = bit_or_flags([g.quality_flag for g in group])
        cells_out.append(
            {
                "cell_id": cid,
                "lat_center": first.lat_center,
                "lon_center": first.lon_center,
                "cell_area_km2": first.cell_area_km2,
                "n_eq": round(sum(g.n_eq for g in group), 2),
                "f_eq": round(sum(g.f_eq for g in group), 1),
                "n_terra": sum(g.n_terra for g in group),
                "months_active": len(group),
                "sensors": sorted({g.sensors for g in group}),
                "quality_flag": q_flag,
                "quality_flags_decoded": decode_quality_flags(q_flag),
            }
        )
    cells_out.sort(key=lambda c: c["n_eq"], reverse=True)
    return cells_out


def _fetch_all_rows_for_aoi(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> tuple[list[HarmonizedCellMonthRow], Literal["postgres", "stub"]]:
    if DATA_SOURCE_MODE == "database":
        pg_rows = query_postgres_cell_month(
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
        )
        if pg_rows is not None:
            return pg_rows, "postgres"

    return (
        generate_stub_cell_month_rows(
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
        ),
        "stub",
    )


def query_cell_month_aoi(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    metric: Literal["n_eq", "f_eq"] = "n_eq",
) -> dict[str, Any]:
    """
    Executes a complete AOI analytics query against `harmonized.cell_month`:
    - Baseline calendar anomalies always span the full 2012-2026 series.
    - Map cells and summary KPIs slice strictly to `[start_date, end_date]`.
    """
    lo_lat, hi_lat = min(min_lat, max_lat), max(min_lat, max_lat)
    area_km2 = compute_aoi_grid_area_km2(min_lon, lo_lat, max_lon, hi_lat)

    all_rows, source_used = _fetch_all_rows_for_aoi(min_lon, lo_lat, max_lon, hi_lat)
    monthly_series = aggregate_rows_by_month(all_rows, area_region_km2=area_km2)
    calendar_anomalies = compute_cell_month_calendar_anomalies(monthly_series, metric=metric)

    win_start = _parse_iso_month(start_date, date(2024, 1, 1))
    win_end = _parse_iso_month(end_date, date(2024, 12, 1))
    if win_start > win_end:
        win_start, win_end = win_end, win_start

    window_rows = [r for r in all_rows if win_start <= r.month <= win_end]
    active_cells = _aggregate_active_map_cells(window_rows)

    total_n_eq = round(sum(r.n_eq for r in window_rows), 2)
    total_f_eq = round(sum(r.f_eq for r in window_rows), 1)

    return {
        "bounds": [min_lon, lo_lat, max_lon, hi_lat],
        "start_date": win_start.isoformat(),
        "end_date": win_end.isoformat(),
        "metric": metric,
        "method_version": DEFAULT_METHOD_VERSION,
        "data_source": source_used,
        "area_region_km2": area_km2,
        "pending_confirmations": PENDING_TEAM_CONFIRMATION,
        "summary": {
            "total_n_eq": total_n_eq,
            "total_f_eq_mw": total_f_eq,
            "frp_density_mw_km2": round(total_f_eq / area_km2, 6) if area_km2 > 0 else 0.0,
            "active_cells_count": len(active_cells),
            "window_rows_count": len(window_rows),
            "n_terra_separate_series": sum(r.n_terra for r in window_rows),
        },
        "calendar_anomalies": [a.model_dump(mode="json") for a in calendar_anomalies],
        "monthly_series": [m.model_dump(mode="json") for m in monthly_series],
        "cells": active_cells,
        "window_rows": [r.model_dump(mode="json") for r in window_rows],
    }


def export_cell_month_csv(rows: list[dict[str, Any]]) -> str:
    """
    Exports harmonized cell-month rows in RFC-4180 CSV format (Option 1 of Section 5),
    preserving provenance, quality flags, and `method_version`.
    """
    headers = [
        "month",
        "cell_id",
        "lat_center",
        "lon_center",
        "cell_area_km2",
        "n_eq",
        "f_eq",
        "ref_sat",
        "sensors",
        "n_terra",
        "n_aqua",
        "n_snpp",
        "n_n20",
        "n_n21",
        "frp_terra",
        "frp_aqua",
        "frp_snpp",
        "frp_n20",
        "frp_n21",
        "quality_flag",
        "method_version",
    ]
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in rows:
        writer.writerow([r.get(h, "") if r.get(h) is not None else "" for h in headers])
    return buf.getvalue()
