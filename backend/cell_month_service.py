"""
PostgreSQL 18 Adapter & Deterministic 2012-2026 v0.2 Service for `harmonized.cell_month`.

Aligned with `docs/CONTRATO_DATOS_WEB_RESPUESTA_V02.md`:
- Uses confirmed `south_to_north` `cell_id` ranges with `CROSS JOIN LATERAL (... OFFSET 0)`.
- Joins month-level quality flags from `harmonized.reference_plan` (`generate_series` 176 months).
- Routes single-month map requests to `harmonized.map_month` and zoomed-out viewports
  (> 20,000 cells) to dynamic 1° x 1° spatial rollups (`resolution_deg = 1.0`).
- Guards calendar queries above 50,000 cells (`calendar_available = False`) and CSV exports
  above 1,000,000 rows (`ValueError` / HTTP 413), streaming DB exports via `COPY ... TO STDOUT`.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import math
import os
from datetime import date
from typing import Any, Iterator, Literal, Optional

from db import DATABASE_URL
from harmonized_cell_month import (
    AQUA_2026_08_DRIFT_WARNING_ES,
    CSV_MAX_ROWS,
    DEFAULT_METHOD_VERSION,
    GRID_COLS,
    GRID_COLS_1DEG,
    GRID_STEP_1DEG,
    GRID_STEP_DEG,
    LOW_CONFIDENCE_BAND_WARNING_ES,
    MAP_1DEG_CELL_THRESHOLD,
    MAX_CALENDAR_CELLS,
    MIN_RECOMMENDED_AOI_CELLS,
    PENDING_TEAM_CONFIRMATION,
    SERIES_END_MONTH,
    SERIES_START_MONTH,
    TEAM_CONTRACT_V02,
    HarmonizedCellMonthRow,
    MonthlyRegionAggregate,
    QualityFlagBits,
    aggregate_cells_to_1deg,
    aggregate_rows_by_month,
    aoi_cell_count,
    bbox_to_cell_id_ranges,
    bbox_to_grid_indices,
    bbox_touches_low_confidence_band,
    bit_or_flags,
    cell_touches_low_confidence_band,
    compute_aoi_grid_area_km2,
    compute_cell_month_calendar_anomalies,
    decode_quality_flags,
    get_v02_reference_plan,
    get_v02_reference_quality_map,
    iter_calendar_months,
    row_col_to_cell_id,
    spherical_cell_area_km2,
)
from team_contract import DATA_SOURCE_MODE

logger = logging.getLogger("backend.cell_month")


class DatabaseUnavailableError(RuntimeError):
    """La base armonizada no responde, no tiene el esquema o está vacía.
    En modo `database` se propaga como HTTP 503: nunca se reemplaza por datos sintéticos."""

SERIES_START_DATE = SERIES_START_MONTH
SERIES_END_DATE = SERIES_END_MONTH
USE_CELL_ID_RANGES = os.getenv("CELL_MONTH_USE_CELL_ID_RANGES", "true").lower() == "true"

CSV_HEADERS = [
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


def _parse_iso_month(date_str: Optional[str], fallback: date) -> date:
    if not date_str:
        return fallback
    try:
        parts = date_str[:10].split("-")
        parsed = date(int(parts[0]), int(parts[1]), 1)
    except Exception:
        return fallback
    if parsed < SERIES_START_DATE:
        return SERIES_START_DATE
    if parsed > SERIES_END_DATE:
        return SERIES_END_DATE
    return parsed


def _build_spatial_where_clause(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    use_cell_id_ranges: bool,
) -> tuple[str, list[Any]]:
    """Parameterized SQL predicate supporting confirmed `cell_id` ranges and antimeridian splits."""
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

    return (
        "lat_center BETWEEN %s AND %s AND (lon_center >= %s OR lon_center <= %s)",
        [lo_lat, hi_lat, min_lon, max_lon],
    )


def _range_arrays(
    min_lon: float,
    lo_lat: float,
    max_lon: float,
    hi_lat: float,
) -> tuple[list[int], list[int]]:
    ranges = bbox_to_cell_id_ranges(min_lon, lo_lat, max_lon, hi_lat)
    return [r[0] for r in ranges], [r[1] for r in ranges]


def query_postgres_cell_month(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    start_month: date = SERIES_START_DATE,
    end_month: date = SERIES_END_DATE,
    use_cell_id_ranges: Optional[bool] = None,
) -> Optional[list[HarmonizedCellMonthRow]]:
    """
    Fetches raw `harmonized.cell_month` rows from PostgreSQL 18.
    Returns `None` if `psycopg` is unavailable, schema doesn't exist, or table is empty.
    """
    try:
        import psycopg
    except ImportError:
        logger.debug("psycopg not installed; using cell_month stub fallback")
        return None

    use_ranges = USE_CELL_ID_RANGES if use_cell_id_ranges is None else use_cell_id_ranges
    lo_lat, hi_lat = min(min_lat, max_lat), max(min_lat, max_lat)

    if use_ranges:
        starts, ends = _range_arrays(min_lon, lo_lat, max_lon, hi_lat)
        sql = """
        WITH ranges AS (
            SELECT * FROM unnest(%s::int[], %s::int[]) AS t(s, e)
        )
        SELECT
            x.month, x.cell_id, x.lat_center, x.lon_center, x.cell_area_km2,
            x.n_eq, x.f_eq, x.ref_sat, x.sensors,
            x.n_terra, x.n_aqua, x.n_snpp, x.n_n20, x.n_n21,
            x.frp_terra, x.frp_aqua, x.frp_snpp, x.frp_n20, x.frp_n21,
            x.quality_flag, x.method_version
        FROM ranges r
        CROSS JOIN LATERAL (
            SELECT
                m.month, m.cell_id, m.lat_center, m.lon_center, m.cell_area_km2,
                m.n_eq, m.f_eq, m.ref_sat, m.sensors,
                m.n_terra, m.n_aqua, m.n_snpp, m.n_n20, m.n_n21,
                m.frp_terra, m.frp_aqua, m.frp_snpp, m.frp_n20, m.frp_n21,
                m.quality_flag, m.method_version
            FROM harmonized.cell_month m
            WHERE m.cell_id BETWEEN r.s AND r.e
              AND m.month BETWEEN %s AND %s
            OFFSET 0
        ) x
        ORDER BY x.month ASC, x.cell_id ASC;
        """
        params: list[Any] = [starts, ends, start_month, end_month]
    else:
        spatial_sql, spatial_params = _build_spatial_where_clause(
            min_lon=min_lon,
            min_lat=lo_lat,
            max_lon=max_lon,
            max_lat=hi_lat,
            use_cell_id_ranges=False,
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
        params = [start_month, end_month, *spatial_params]

    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
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
                        ref_sat=int(r[7]),
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


def _query_postgres_v02_fast(
    min_lon: float,
    lo_lat: float,
    max_lon: float,
    hi_lat: float,
    win_start: date,
    win_end: date,
    area_km2: float,
    include_calendar: bool,
    resolution_deg: float,
) -> Optional[dict[str, Any]]:
    """
    Fast aggregated PostgreSQL 18 execution following Sec 6a & 6c of
    `CONTRATO_DATOS_WEB_RESPUESTA_V02.md`: avoids fetching raw cell rows into Python.
    Raises `DatabaseUnavailableError` if PostgreSQL or tables are unavailable/empty.
    """
    try:
        import psycopg
    except ImportError as exc:
        raise DatabaseUnavailableError("psycopg no está instalado en el backend.") from exc

    starts, ends = _range_arrays(min_lon, lo_lat, max_lon, hi_lat)

    calendar_sql = """
    WITH ranges AS (
        SELECT * FROM unnest(%s::int[], %s::int[]) AS t(s, e)
    ),
    agg AS (
        SELECT x.month,
               sum(x.n_eq::float8) AS n_eq,
               sum(x.f_eq::float8) AS f_eq,
               sum(x.n_terra) AS n_terra,
               sum(x.frp_terra::float8) AS frp_terra,
               sum(x.n_aqua) AS n_aqua,
               sum(x.frp_aqua::float8) AS frp_aqua,
               sum(x.n_snpp) AS n_snpp,
               sum(x.frp_snpp::float8) AS frp_snpp,
               sum(x.n_n20) AS n_n20,
               sum(x.frp_n20::float8) AS frp_n20,
               sum(x.n_n21) AS n_n21,
               sum(x.frp_n21::float8) AS frp_n21,
               bit_or(x.quality_flag)::int AS row_flag,
               count(*) AS active_cells
        FROM ranges r
        CROSS JOIN LATERAL (
            SELECT m.month, m.n_eq, m.f_eq, m.n_terra, m.frp_terra,
                   m.n_aqua, m.frp_aqua, m.n_snpp, m.frp_snpp,
                   m.n_n20, m.frp_n20, m.n_n21, m.frp_n21, m.quality_flag
            FROM harmonized.cell_month m
            WHERE m.cell_id BETWEEN r.s AND r.e
            OFFSET 0
        ) x
        GROUP BY x.month
    )
    SELECT p.month,
           COALESCE(a.n_eq, 0.0), COALESCE(a.f_eq, 0.0),
           COALESCE(a.n_terra, 0), COALESCE(a.frp_terra, 0.0),
           COALESCE(a.n_aqua, 0), COALESCE(a.frp_aqua, 0.0),
           COALESCE(a.n_snpp, 0), COALESCE(a.frp_snpp, 0.0),
           COALESCE(a.n_n20, 0), COALESCE(a.frp_n20, 0.0),
           COALESCE(a.n_n21, 0), COALESCE(a.frp_n21, 0.0),
           (p.quality_flag::int | COALESCE(a.row_flag, 0)) AS combined_flag,
           COALESCE(a.active_cells, 0)
    FROM harmonized.reference_plan p
    LEFT JOIN agg a USING (month)
    ORDER BY p.month ASC;
    """

    # Capa de mapa (contrato v0.2, secc. 6c). Todas las variantes leen SOLO `harmonized.cell_month`:
    # en la base real `map_month` tiene únicamente (month, cell_id, n_eq, f_eq), así que no sirve para
    # devolver n_terra, quality_flag (bit 7 por celda) ni sensors. `cell_month` tiene las mismas columnas
    # en el esquema provisional de Docker y en el .dump real. `LATERAL ... OFFSET 0` fuerza un Index Scan
    # por rango sobre la PK (cell_id, month); sin él el planificador eligió un Seq Scan (4,6 s medidos).
    if resolution_deg >= GRID_STEP_1DEG:
        # 1° × 1° zoom-out dynamic aggregation (Sec 6c)
        map_sql = """
        WITH ranges AS (SELECT * FROM unnest(%s::int[], %s::int[]) AS t(s, e))
        SELECT ((x.cell_id / 1440) / 4) * 360 + ((x.cell_id %% 1440) / 4) AS block_id,
               sum(x.n_eq::float8) AS n_eq,
               sum(x.f_eq::float8) AS f_eq,
               sum(x.n_terra) AS n_terra,
               sum(x.frp_terra::float8) AS frp_terra,
               bit_or(x.quality_flag)::int AS quality_flag,
               count(DISTINCT x.month) AS months_active,
               count(DISTINCT x.cell_id) AS subcell_count,
               array_agg(DISTINCT x.sensors ORDER BY x.sensors) AS sensors
        FROM ranges r
        CROSS JOIN LATERAL (
            SELECT m.month, m.cell_id, m.n_eq, m.f_eq, m.n_terra, m.frp_terra, m.quality_flag, m.sensors
            FROM harmonized.cell_month m
            WHERE m.cell_id BETWEEN r.s AND r.e
              AND m.month BETWEEN %s AND %s
            OFFSET 0
        ) x
        GROUP BY 1
        ORDER BY n_eq DESC;
        """
    else:
        # 0.25° × 0.25° native resolution
        map_sql = """
        WITH ranges AS (SELECT * FROM unnest(%s::int[], %s::int[]) AS t(s, e))
        SELECT x.cell_id, min(x.lat_center) AS lat_center, min(x.lon_center) AS lon_center,
               min(x.cell_area_km2) AS cell_area_km2,
               sum(x.n_eq::float8) AS n_eq,
               sum(x.f_eq::float8) AS f_eq,
               sum(x.n_terra) AS n_terra,
               sum(x.frp_terra::float8) AS frp_terra,
               bit_or(x.quality_flag)::int AS quality_flag,
               count(*) AS months_active,
               array_agg(DISTINCT x.sensors ORDER BY x.sensors) AS sensors
        FROM ranges r
        CROSS JOIN LATERAL (
            SELECT m.cell_id, m.lat_center, m.lon_center, m.cell_area_km2,
                   m.n_eq, m.f_eq, m.n_terra, m.frp_terra, m.quality_flag, m.sensors
            FROM harmonized.cell_month m
            WHERE m.cell_id BETWEEN r.s AND r.e
              AND m.month BETWEEN %s AND %s
            OFFSET 0
        ) x
        GROUP BY x.cell_id
        ORDER BY n_eq DESC;
        """
    map_params: list[Any] = [starts, ends, win_start, win_end]

    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                # Quick check that harmonized.cell_month actually has loaded rows
                cur.execute("SELECT 1 FROM harmonized.cell_month LIMIT 1;")
                if cur.fetchone() is None:
                    raise DatabaseUnavailableError(
                        "La tabla harmonized.cell_month está vacía: falta cargar el .dump armonizado."
                    )

                monthly_series: list[MonthlyRegionAggregate] = []
                if include_calendar:
                    cur.execute(calendar_sql, [starts, ends])
                    cal_rows = cur.fetchall()
                    for cr in cal_rows:
                        m_dt: date = cr[0]
                        n_eq = float(cr[1])
                        f_eq = float(cr[2])
                        q_flag = int(cr[13])
                        monthly_series.append(
                            MonthlyRegionAggregate(
                                month=m_dt,
                                year=m_dt.year,
                                month_num=m_dt.month,
                                n_eq=round(n_eq, 4),
                                f_eq=round(f_eq, 4),
                                frp_density_mw_km2=round(f_eq / area_km2, 6),
                                area_region_km2=round(area_km2, 3),
                                quality_flag=q_flag,
                                quality_flags_decoded=decode_quality_flags(q_flag),
                                active_cell_count=int(cr[14]),
                                n_terra=int(cr[3]),
                                frp_terra=round(float(cr[4]), 2),
                                raw_by_satellite={
                                    "terra": {"count": int(cr[3]), "frp_mw": round(float(cr[4]), 2)},
                                    "aqua": {"count": int(cr[5]), "frp_mw": round(float(cr[6]), 2)},
                                    "snpp": {"count": int(cr[7]), "frp_mw": round(float(cr[8]), 2)},
                                    "n20": {"count": int(cr[9]), "frp_mw": round(float(cr[10]), 2)},
                                    "n21": {"count": int(cr[11]), "frp_mw": round(float(cr[12]), 2)},
                                },
                                method_version=DEFAULT_METHOD_VERSION,
                            )
                        )

                cur.execute(map_sql, map_params)
                raw_cells = cur.fetchall()
                cells_out: list[dict[str, Any]] = []
                if resolution_deg >= GRID_STEP_1DEG:
                    for row in raw_cells:
                        block_id = int(row[0])
                        b_row = block_id // GRID_COLS_1DEG
                        b_col = block_id % GRID_COLS_1DEG
                        lat_c = -90.0 + b_row + 0.5
                        lon_c = -180.0 + b_col + 0.5
                        area_b = round(spherical_cell_area_km2(lat_c - 0.5, lat_c + 0.5, GRID_STEP_1DEG), 3)
                        q_flag = int(row[5])
                        cells_out.append(
                            {
                                "cell_id": block_id,
                                "block_id": block_id,
                                "lat_center": round(lat_c, 3),
                                "lon_center": round(lon_c, 3),
                                "cell_area_km2": area_b,
                                "n_eq": round(float(row[1]), 2),
                                "f_eq": round(float(row[2]), 1),
                                "n_terra": int(row[3]),
                                "frp_terra": round(float(row[4]), 2),
                                "months_active": int(row[6]),
                                "subcell_count": int(row[7]),
                                "sensors": list(row[8] or []),
                                "quality_flag": q_flag,
                                "quality_flags_decoded": decode_quality_flags(q_flag),
                                "resolution_deg": GRID_STEP_1DEG,
                            }
                        )
                else:
                    for row in raw_cells:
                        q_flag = int(row[8])
                        months_act = int(row[9])
                        cells_out.append(
                            {
                                "cell_id": int(row[0]),
                                "lat_center": float(row[1]),
                                "lon_center": float(row[2]),
                                "cell_area_km2": float(row[3]),
                                "n_eq": round(float(row[4]), 2),
                                "f_eq": round(float(row[5]), 1),
                                "n_terra": int(row[6]),
                                "frp_terra": round(float(row[7]), 2),
                                "months_active": months_act,
                                "sensors": list(row[10] or []),
                                "quality_flag": q_flag,
                                "quality_flags_decoded": decode_quality_flags(q_flag),
                                "resolution_deg": GRID_STEP_DEG,
                            }
                        )

                return {"monthly_series": monthly_series, "cells": cells_out}
    except DatabaseUnavailableError:
        raise
    except Exception as exc:
        # En modo `database` NO se cae a datos sintéticos: se informa el error (HTTP 503 en la API).
        logger.error("PostgreSQL v0.2 query failed: %s", exc)
        raise DatabaseUnavailableError("No se pudo consultar la base armonizada. Revisá el log del backend.") from exc


def database_health() -> dict[str, Any]:
    """
    Estado de la fuente de datos para `/api/health`.
    En modo `stub` no toca la base. En modo `database` verifica conexión, que `cell_month` tenga
    filas y lee la versión desde `dataset_metadata` (si existe; el esquema provisional de Docker
    no la tiene). Usa solo consultas baratas (catálogo y tablas chicas).
    """
    if DATA_SOURCE_MODE != "database":
        return {"status": "ok", "data_source_mode": DATA_SOURCE_MODE, "database": "no se usa (modo stub)"}
    try:
        import psycopg

        with psycopg.connect(DATABASE_URL, connect_timeout=3) as conn:
            has_rows = conn.execute("SELECT EXISTS (SELECT 1 FROM harmonized.cell_month)").fetchone()[0]
            if not has_rows:
                raise DatabaseUnavailableError(
                    "La tabla harmonized.cell_month está vacía: falta cargar el .dump armonizado."
                )
            est_rows = conn.execute(
                "SELECT reltuples::bigint FROM pg_class WHERE oid = 'harmonized.cell_month'::regclass"
            ).fetchone()[0]
            months = conn.execute(
                "SELECT min(month), max(month), count(*) FROM harmonized.reference_plan"
            ).fetchone()
            version = None
            if conn.execute("SELECT to_regclass('harmonized.dataset_metadata') IS NOT NULL").fetchone()[0]:
                row = conn.execute(
                    "SELECT value FROM harmonized.dataset_metadata WHERE key = 'method_version'"
                ).fetchone()
                version = row[0] if row else None
            server = conn.execute("SHOW server_version").fetchone()[0]
            user = conn.execute("SELECT current_user").fetchone()[0]
    except DatabaseUnavailableError:
        raise
    except Exception as exc:
        logger.error("Health check: no se pudo conectar a la base armonizada: %s", exc)
        raise DatabaseUnavailableError("No se pudo conectar a la base armonizada. Revisá el log del backend.") from exc

    return {
        "status": "ok",
        "data_source_mode": DATA_SOURCE_MODE,
        "database": "conectada",
        "db_user": user,
        "postgres_version": server,
        "method_version": version or "desconocida (sin dataset_metadata: ¿esquema provisional sin el .dump?)",
        "cell_month_rows_estimate": int(est_rows),
        "series": {"first_month": months[0].isoformat(), "last_month": months[1].isoformat(), "months": int(months[2])},
    }


_V02_PLAN_LOOKUP: dict[date, tuple[int, str, int]] = {
    row["month"]: (int(row["ref_sat"]), str(row["sensors"]), int(row["quality_flag"]))
    for row in get_v02_reference_plan(SERIES_START_DATE, SERIES_END_DATE)
}


def _month_provenance_and_flags(month_dt: date) -> tuple[int, str, int]:
    """Returns exact v0.2 month-level `(ref_sat, sensors, quality_flag)` from `reference_plan`."""
    if month_dt in _V02_PLAN_LOOKUP:
        return _V02_PLAN_LOOKUP[month_dt]
    if month_dt < date(2020, 1, 1):
        return 3, "SNPP", 0
    return 4, "N20", 0


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
        area = round(spherical_cell_area_km2(lat_s, lat_s + GRID_STEP_DEG), 4)
        for c_idx in all_cols[::step]:
            lon_c = round(-180.0 + (c_idx + 0.5) * GRID_STEP_DEG, 3)
            cell_id = row_col_to_cell_id(s_idx, c_idx, row_origin="south_to_north")
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
    Generates deterministic sparse `harmonized.cell_month` v0.2 records across `2012-01..2026-08`
    for development/testing when the real Postgres `.dump` is not loaded yet.
    Includes row-level bit 7 (`CALIBRACION_BAJA_CONF`) for extreme bands (`-60°`, `70°`, polar).
    """
    cells = _sample_aoi_cells(min_lon, min_lat, max_lon, max_lat)
    months = iter_calendar_months(start_month, end_month)
    rows: list[HarmonizedCellMonthRow] = []

    for cell_id, lat_c, lon_c, area in cells:
        cell_seed = int(hashlib.md5(f"{cell_id}".encode()).hexdigest()[:8], 16)
        peak_month = 7 + (cell_seed % 3)  # Southern hemisphere dry-season peak (Jul/Aug/Sep)
        low_conf_bit = int(QualityFlagBits.CALIBRACION_BAJA_CONF) if cell_touches_low_confidence_band(lat_c) else 0

        for m_dt in months:
            h_val = int(hashlib.md5(f"{cell_id}-{m_dt.isoformat()}".encode()).hexdigest()[:8], 16)
            seasonal_weight = 0.25 + 1.35 * math.exp(-((m_dt.month - peak_month) ** 2) / 3.5)

            # Sparse behavior: omit quiet off-season months deterministically
            if (h_val % 100) / 100.0 > min(0.88, 0.30 * seasonal_weight):
                continue

            extreme_mult = 2.6 if m_dt.year in (2020, 2024) else 1.0
            n_eq = round((1.5 + (h_val % 24) * 0.85) * seasonal_weight * extreme_mult, 2)
            f_eq = round(n_eq * (28.0 + (h_val % 45)), 1)

            ref_sat, sensors, month_flag = _month_provenance_and_flags(m_dt)
            q_flag = month_flag | low_conf_bit
            is_modis_only = bool(month_flag & QualityFlagBits.SOLO_MODIS_DERIVA)

            # Terra drifts down ~30% in 2025-2026; Aqua solo in 2026-08 underestimates ~10%
            terra_drift = 0.7 if m_dt.year >= 2025 else 1.0
            n_terra = max(0, int(round(n_eq * 0.55 * terra_drift)))
            n_aqua = max(0, int(round(n_eq)))
            n_snpp = 0 if is_modis_only else max(0, int(round(n_eq * 3.1)))
            n_n20 = 0 if (is_modis_only or m_dt < date(2018, 4, 1)) else max(0, int(round(n_eq * 3.4)))
            n_n21 = 0 if (is_modis_only or m_dt < date(2023, 3, 1)) else max(0, int(round(n_eq * 3.2)))

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


def _aggregate_active_map_cells(
    window_rows: list[HarmonizedCellMonthRow],
    resolution_deg: float = GRID_STEP_DEG,
) -> list[dict[str, Any]]:
    """Collapses filtered `[start_date, end_date]` rows per spatial cell (0.25° or 1.0°)."""
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
                "frp_terra": round(sum(g.frp_terra for g in group), 2),
                "months_active": len(group),
                "active_months": len(group),
                "sensors": sorted({g.sensors for g in group}),
                "quality_flag": q_flag,
                "quality_flags_decoded": decode_quality_flags(q_flag),
                "resolution_deg": GRID_STEP_DEG,
            }
        )

    if resolution_deg >= GRID_STEP_1DEG:
        cells_out = aggregate_cells_to_1deg(cells_out)

    cells_out.sort(key=lambda c: c["n_eq"], reverse=True)
    return cells_out


def _build_ui_warnings(
    *,
    aoi_cells_count: int,
    lo_lat: float,
    hi_lat: float,
    win_start: date,
    win_end: date,
    resolution_deg: float,
    calendar_available: bool,
    active_cells: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Emits structured v0.2 UI alerts per Sec 7 & 8.2 (`few_cells`, bit 7, 2026-08, caps)."""
    warnings: list[dict[str, Any]] = []

    if aoi_cells_count < MIN_RECOMMENDED_AOI_CELLS:
        warnings.append(
            {
                "code": "few_cells",
                "severity": "warning",
                "message_es": (
                    f"El AOI cubre solo {aoi_cells_count} celda(s) de 0,25° (< {MIN_RECOMMENDED_AOI_CELLS}): "
                    "las estadísticas regionales pueden resultar ruidosas."
                ),
            }
        )

    if not calendar_available:
        warnings.append(
            {
                "code": "calendar_limit_exceeded",
                "severity": "info",
                "message_es": (
                    f"El AOI cubre {aoi_cells_count:,} celdas (> {MAX_CALENDAR_CELLS:,}): "
                    "acerca el zoom o reduce el área para calcular el calendario completo 2012–2026."
                ),
            }
        )

    if resolution_deg >= GRID_STEP_1DEG:
        warnings.append(
            {
                "code": "map_downsampled_1deg",
                "severity": "info",
                "message_es": (
                    f"Vista amplia ({aoi_cells_count:,} celdas > {MAP_1DEG_CELL_THRESHOLD:,}): "
                    "el mapa agrupa dinámicamente bloques de 1° × 1° para mantener fluidez."
                ),
            }
        )

    touches_bit7 = bbox_touches_low_confidence_band(lo_lat, hi_lat) or any(
        bool(c.get("quality_flag", 0) & QualityFlagBits.CALIBRACION_BAJA_CONF) for c in active_cells
    )
    if touches_bit7:
        warnings.append(
            {
                "code": "low_confidence_band",
                "severity": "warning",
                "message_es": LOW_CONFIDENCE_BAND_WARNING_ES,
            }
        )

    if win_end >= date(2026, 8, 1) >= win_start or any(
        bool(c.get("quality_flag", 0) & QualityFlagBits.SOLO_MODIS_DERIVA) for c in active_cells
    ):
        warnings.append(
            {
                "code": "aqua_2026_08_drift",
                "severity": "warning",
                "message_es": AQUA_2026_08_DRIFT_WARNING_ES,
            }
        )

    return warnings


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
    Executes a complete v0.2 AOI analytics query against `harmonized.cell_month`:
    - Baseline calendar anomalies always span `2012-01..2026-08` (`MAX_CALENDAR_CELLS = 50,000`).
    - Map cells switch dynamically between `0.25°` and `1.0°` above `20,000` visible cells.
    - Emits UI warnings (`few_cells`, `low_confidence_band` bit 7, `aqua_2026_08_drift`).
    """
    lo_lat, hi_lat = min(min_lat, max_lat), max(min_lat, max_lat)
    area_km2 = compute_aoi_grid_area_km2(min_lon, lo_lat, max_lon, hi_lat)
    aoi_cells_count = aoi_cell_count(min_lon, lo_lat, max_lon, hi_lat)
    calendar_available = aoi_cells_count <= MAX_CALENDAR_CELLS
    resolution_deg = GRID_STEP_1DEG if aoi_cells_count > MAP_1DEG_CELL_THRESHOLD else GRID_STEP_DEG

    win_start = _parse_iso_month(start_date, date(2024, 1, 1))
    win_end = _parse_iso_month(end_date, date(2024, 12, 1))
    if win_start > win_end:
        win_start, win_end = win_end, win_start

    source_used: Literal["postgres", "stub"] = "stub"
    monthly_series: list[MonthlyRegionAggregate] = []
    active_cells: list[dict[str, Any]] = []

    if DATA_SOURCE_MODE == "database":
        # Sin caída a datos sintéticos: si la base falla, DatabaseUnavailableError -> HTTP 503.
        pg_result = _query_postgres_v02_fast(
            min_lon=min_lon,
            lo_lat=lo_lat,
            max_lon=max_lon,
            hi_lat=hi_lat,
            win_start=win_start,
            win_end=win_end,
            area_km2=area_km2,
            include_calendar=calendar_available,
            resolution_deg=resolution_deg,
        )
        source_used = "postgres"
        monthly_series = pg_result["monthly_series"]
        active_cells = pg_result["cells"]
    else:
        all_rows = generate_stub_cell_month_rows(min_lon, lo_lat, max_lon, hi_lat)
        if calendar_available:
            all_months = iter_calendar_months(SERIES_START_DATE, SERIES_END_DATE)
            monthly_series = aggregate_rows_by_month(
                all_rows,
                area_region_km2=area_km2,
                all_months=all_months,
                monthly_quality_map=get_v02_reference_quality_map(SERIES_START_DATE, SERIES_END_DATE),
            )
        window_rows = [r for r in all_rows if win_start <= r.month <= win_end]
        active_cells = _aggregate_active_map_cells(window_rows, resolution_deg=resolution_deg)

    calendar_anomalies = (
        compute_cell_month_calendar_anomalies(monthly_series, metric=metric)
        if calendar_available and monthly_series
        else []
    )

    total_n_eq = round(sum(float(c["n_eq"]) for c in active_cells), 2)
    total_f_eq = round(sum(float(c["f_eq"]) for c in active_cells), 1)
    n_terra_sum = sum(int(c.get("n_terra", 0)) for c in active_cells)
    ui_warnings = _build_ui_warnings(
        aoi_cells_count=aoi_cells_count,
        lo_lat=lo_lat,
        hi_lat=hi_lat,
        win_start=win_start,
        win_end=win_end,
        resolution_deg=resolution_deg,
        calendar_available=calendar_available,
        active_cells=active_cells,
    )

    return {
        "bounds": [min_lon, lo_lat, max_lon, hi_lat],
        "start_date": win_start.isoformat(),
        "end_date": win_end.isoformat(),
        "metric": metric,
        "method_version": DEFAULT_METHOD_VERSION,
        "data_source": source_used,
        "area_region_km2": area_km2,
        "aoi_cells_count": aoi_cells_count,
        "celdas_usadas": aoi_cells_count,
        "resolution_deg": resolution_deg,
        "calendar_available": calendar_available,
        "ui_warnings": ui_warnings,
        "pending_confirmations": PENDING_TEAM_CONFIRMATION,
        "contract": TEAM_CONTRACT_V02,
        "summary": {
            "total_n_eq": total_n_eq,
            "total_f_eq_mw": total_f_eq,
            "frp_density_mw_km2": round(total_f_eq / area_km2, 6) if area_km2 > 0 else 0.0,
            "active_cells_count": len(active_cells),
            "aoi_cells_count": aoi_cells_count,
            "resolution_deg": resolution_deg,
            "n_terra_separate_series": n_terra_sum,
        },
        "calendar_anomalies": [a.model_dump(mode="json") for a in calendar_anomalies],
        "monthly_series": [m.model_dump(mode="json") for m in monthly_series],
        "cells": active_cells,
    }


def export_cell_month_csv(rows: list[dict[str, Any]]) -> str:
    """
    Exports harmonized cell-month rows in RFC-4180 CSV format (Option 1),
    preserving provenance (`ref_sat`, `sensors`), `quality_flag`, and `method_version`.
    """
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADERS)
    for r in rows:
        writer.writerow([r.get(h, "") if r.get(h) is not None else "" for h in CSV_HEADERS])
    return buf.getvalue()


def prepare_cell_month_csv_stream(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> tuple[date, date, int, Iterator[bytes]]:
    """
    Checks export row count against `CSV_MAX_ROWS` (1,000,000) and returns a lazy byte-chunk
    stream (Sec 6d `COPY ... TO STDOUT` in Postgres mode, or chunked CSV writer in stub mode).
    """
    lo_lat, hi_lat = min(min_lat, max_lat), max(min_lat, max_lat)
    win_start = _parse_iso_month(start_date, date(2024, 1, 1))
    win_end = _parse_iso_month(end_date, date(2024, 12, 1))
    if win_start > win_end:
        win_start, win_end = win_end, win_start

    if DATA_SOURCE_MODE == "database":
        try:
            import psycopg

            starts, ends = _range_arrays(min_lon, lo_lat, max_lon, hi_lat)
            count_sql = """
            WITH ranges AS (SELECT * FROM unnest(%s::int[], %s::int[]) AS t(s, e))
            SELECT COALESCE(sum(x.cnt), 0)::bigint
            FROM ranges r
            CROSS JOIN LATERAL (
                SELECT count(*) AS cnt
                FROM harmonized.cell_month m
                WHERE m.cell_id BETWEEN r.s AND r.e
                  AND m.month BETWEEN %s AND %s
                OFFSET 0
            ) x;
            """
            copy_inner_sql = """
            WITH ranges AS (SELECT * FROM unnest(%s::int[], %s::int[]) AS t(s, e))
            SELECT m.month, m.cell_id, m.lat_center, m.lon_center, m.cell_area_km2,
                   m.n_eq, m.f_eq, m.ref_sat, m.sensors,
                   m.n_terra, m.n_aqua, m.n_snpp, m.n_n20, m.n_n21,
                   m.frp_terra, m.frp_aqua, m.frp_snpp, m.frp_n20, m.frp_n21,
                   m.quality_flag, m.method_version
            FROM ranges r
            CROSS JOIN LATERAL (
                SELECT * FROM harmonized.cell_month cm
                WHERE cm.cell_id BETWEEN r.s AND r.e
                  AND cm.month BETWEEN %s AND %s
                OFFSET 0
            ) m
            ORDER BY m.month, m.cell_id
            """
            with psycopg.connect(DATABASE_URL, connect_timeout=3) as probe_conn:
                probe_conn.execute("SELECT 1 FROM harmonized.cell_month LIMIT 1;")
                row_count = int(probe_conn.execute(count_sql, [starts, ends, win_start, win_end]).fetchone()[0])
            if row_count > CSV_MAX_ROWS:
                raise ValueError(
                    f"La exportación supera el tope de {CSV_MAX_ROWS:,} filas ({row_count:,} filas). Reduce el AOI o el rango de fechas."
                )

            def _pg_stream() -> Iterator[bytes]:
                with psycopg.connect(DATABASE_URL, connect_timeout=5) as conn:
                    conn.execute("SET statement_timeout = '60s'")
                    with conn.cursor().copy(
                        f"COPY ({copy_inner_sql}) TO STDOUT WITH (FORMAT csv, HEADER true)",
                        [starts, ends, win_start, win_end],
                    ) as copy:
                        for chunk in copy:
                            yield bytes(chunk)

            return win_start, win_end, row_count, _pg_stream()
        except ValueError:
            raise
        except Exception as exc:
            # Sin caída a datos sintéticos en modo `database` (HTTP 503 en la API).
            logger.error("Postgres streaming CSV probe failed: %s", exc)
            raise DatabaseUnavailableError("No se pudo consultar la base armonizada. Revisá el log del backend.") from exc

    stub_rows = generate_stub_cell_month_rows(min_lon, lo_lat, max_lon, hi_lat, win_start, win_end)
    if len(stub_rows) > CSV_MAX_ROWS:
        raise ValueError(
            f"La exportación supera el tope de {CSV_MAX_ROWS:,} filas ({len(stub_rows):,} filas)."
        )

    def _stub_stream() -> Iterator[bytes]:
        buf = io.StringIO(newline="")
        writer = csv.writer(buf)
        writer.writerow(CSV_HEADERS)
        yield buf.getvalue().encode("utf-8")
        buf.seek(0)
        buf.truncate(0)

        for idx, row in enumerate(stub_rows, start=1):
            dumped = row.model_dump(mode="json")
            writer.writerow([dumped.get(h, "") if dumped.get(h) is not None else "" for h in CSV_HEADERS])
            if idx % 200 == 0:
                yield buf.getvalue().encode("utf-8")
                buf.seek(0)
                buf.truncate(0)
        leftover = buf.getvalue()
        if leftover:
            yield leftover.encode("utf-8")

    return win_start, win_end, len(stub_rows), _stub_stream()
