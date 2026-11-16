#!/usr/bin/env python3
"""
Generates deterministic pseudo-random PostgreSQL 18 seed data for the `harmonized` v0.2 schema.

Reuses `backend/harmonized_cell_month.py` geometry, `reference_plan` flags, and bitmask rules
so all generated rows (`cell_month`, `map_month`, `global_month`, `sat_month_quality`,
`dim_satellite`, `known_gap`, `dataset_metadata`) satisfy every schema CHECK constraint and
exercise realistic seasonal/extreme anomalies, sparse months, Terra drift, 2026-08 Aqua-only,
and bit-7 low-confidence latitude bands.

Usage:
    backend/.venv/bin/python scripts/generate_harmonized_seed.py --seed 42
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from datetime import date
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from harmonized_cell_month import (  # noqa: E402
    DEFAULT_METHOD_VERSION,
    SERIES_END_MONTH,
    SERIES_START_MONTH,
    QualityFlagBits,
    bbox_to_grid_indices,
    cell_id_to_center_and_area,
    cell_touches_low_confidence_band,
    get_v02_reference_plan,
    row_col_to_cell_id,
)

DEFAULT_OUTPUT_SQL = REPO_ROOT / "docker" / "postgres" / "04_harmonized_cell_month_seed.sql"

# Diverse spatial regions (including default frontend viewport -65..-58, -35..-29 and bit-7 bands)
SEED_REGIONS: list[tuple[str, float, float, float, float, int, int]] = [
    # (name, min_lon, min_lat, max_lon, max_lat, max_cells, peak_month)
    ("Argentina Centro/Litoral (default viewport)", -66.0, -35.5, -57.5, -28.5, 42, 8),
    ("Chaco / Pantanal / Cerrado", -62.0, -24.0, -52.0, -14.0, 28, 9),
    ("California / Western US", -122.5, 34.0, -118.0, 40.5, 16, 8),
    ("Iberia / Mediterráneo", -6.5, 37.5, 1.5, 42.5, 14, 7),
    ("Sudeste Australia", 145.0, -38.0, 150.5, -33.0, 14, 1),
    ("Banda extrema Sur (-60° bit 7)", -69.0, -61.5, -63.0, -59.5, 6, 1),
    ("Banda extrema Norte (70° bit 7)", 138.0, 70.0, 144.0, 72.0, 6, 7),
]


def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _select_region_cell_ids(rng: random.Random) -> list[tuple[int, int]]:
    """Selects distinct valid `cell_id`s across diverse biomes with their typical peak month."""
    seen: set[int] = set()
    selected: list[tuple[int, int]] = []

    for _, min_lon, min_lat, max_lon, max_lat, count, peak_month in SEED_REGIONS:
        s_min, s_max, col_ranges = bbox_to_grid_indices(min_lon, min_lat, max_lon, max_lat)
        candidates: list[int] = []
        for s_idx in range(s_min, s_max + 1):
            for c_start, c_end in col_ranges:
                for c_idx in range(c_start, c_end + 1):
                    cid = row_col_to_cell_id(s_idx, c_idx, row_origin="south_to_north")
                    if cid not in seen:
                        candidates.append(cid)

        rng.shuffle(candidates)
        for cid in candidates[:count]:
            seen.add(cid)
            selected.append((cid, peak_month))

    selected.sort(key=lambda item: item[0])
    return selected


def _generate_cell_month_tuples(rng: random.Random) -> list[str]:
    """Generates SQL value tuples for `harmonized.cell_month` across 2012-01..2026-08."""
    cells = _select_region_cell_ids(rng)
    ref_plan = get_v02_reference_plan(SERIES_START_MONTH, SERIES_END_MONTH)
    value_lines: list[str] = []

    for cid, region_peak in cells:
        lat_c, lon_c, area_km2 = cell_id_to_center_and_area(cid, row_origin="south_to_north")
        cell_peak = ((region_peak - 1 + rng.randint(-1, 1)) % 12) + 1
        cell_intensity = rng.uniform(0.6, 2.2)
        low_conf_bit = int(QualityFlagBits.CALIBRACION_BAJA_CONF) if cell_touches_low_confidence_band(lat_c) else 0

        for plan in ref_plan:
            m_dt: date = plan["month"]
            dist = min(abs(m_dt.month - cell_peak), 12 - abs(m_dt.month - cell_peak))
            seasonal = 0.22 + 1.45 * math.exp(-(dist ** 2) / 3.2)

            # Sparse activity: omit ~40-75% of quiet off-season months cleanly
            active_prob = min(0.90, 0.26 * seasonal)
            if rng.random() > active_prob:
                continue

            extreme_mult = 1.0
            if m_dt.year == 2020 and m_dt.month in (8, 9, 10):
                extreme_mult = rng.uniform(2.1, 3.2)
            elif m_dt.year == 2024 and m_dt.month in (8, 9):
                extreme_mult = rng.uniform(2.4, 3.6)

            base_count = rng.gammavariate(2.2, 4.5) * seasonal * cell_intensity * extreme_mult
            # ~3% sparse edge case where reference sensor missed detections (n_eq = 0) while Terra saw fires
            is_zero_ref_edge = rng.random() < 0.03
            n_eq = 0.0 if is_zero_ref_edge else round(max(0.5, base_count), 3)
            f_eq = 0.0 if n_eq == 0.0 else round(n_eq * rng.uniform(18.0, 62.0), 2)

            ref_sat = int(plan["ref_sat"])
            sensors = str(plan["sensors"])
            q_flag = int(plan["quality_flag"]) | low_conf_bit
            is_modis_only = bool(int(plan["quality_flag"]) & int(QualityFlagBits.SOLO_MODIS_DERIVA))

            # Terra drifts ~30% downward after 2024; Aqua underestimates ~10% in 2026-08
            terra_mult = 0.7 if m_dt.year >= 2025 else 1.0
            n_terra = max(1 if is_zero_ref_edge else 0, int(round(max(1.0, base_count) * rng.uniform(0.4, 0.75) * terra_mult)))
            n_aqua = 0 if is_zero_ref_edge else max(1, int(round(n_eq * rng.uniform(0.88, 1.08))))
            n_snpp = 0 if is_modis_only else max(0, int(round((n_eq if n_eq > 0 else 1.0) * rng.uniform(2.4, 3.8))))
            n_n20 = 0 if (is_modis_only or m_dt < date(2018, 4, 1)) else max(0, int(round((n_eq if n_eq > 0 else 1.0) * rng.uniform(2.7, 4.1))))
            n_n21 = 0 if (is_modis_only or m_dt < date(2023, 3, 1)) else max(0, int(round((n_eq if n_eq > 0 else 1.0) * rng.uniform(2.5, 3.9))))

            frp_terra = round(n_terra * rng.uniform(16.0, 32.0), 2)
            frp_aqua = round(f_eq * rng.uniform(0.92, 1.06), 2) if n_aqua > 0 else 0.0
            frp_snpp = round(n_snpp * rng.uniform(7.5, 11.5), 2)
            frp_n20 = round(n_n20 * rng.uniform(7.2, 11.0), 2)
            frp_n21 = round(n_n21 * rng.uniform(7.0, 10.8), 2)

            value_lines.append(
                f"('{m_dt.isoformat()}',{cid},{lat_c:.4f},{lon_c:.4f},{area_km2:.4f},"
                f"{n_eq:.3f},{f_eq:.2f},{ref_sat},{_sql_str(sensors)},"
                f"{n_terra},{n_aqua},{n_snpp},{n_n20},{n_n21},"
                f"{frp_terra:.2f},{frp_aqua:.2f},{frp_snpp:.2f},{frp_n20:.2f},{frp_n21:.2f},"
                f"{q_flag},{_sql_str(DEFAULT_METHOD_VERSION)})"
            )

    return value_lines


def _chunked(seq: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def build_seed_sql(seed: int) -> tuple[str, int]:
    """Builds the full idempotent SQL seed script and returns `(sql_text, row_count)`."""
    rng = random.Random(seed)
    cell_month_tuples = _generate_cell_month_tuples(rng)

    parts: list[str] = [
        "-- =============================================================================",
        f"-- Synthetic Random Seed Data for `harmonized` v0.2 Schema (seed={seed})",
        f"-- Generated by scripts/generate_harmonized_seed.py ({len(cell_month_tuples)} cell_month rows)",
        "-- Idempotent (`ON CONFLICT DO NOTHING / DO UPDATE`); safe alongside static lookups.",
        "-- =============================================================================",
        "",
        "BEGIN;",
        "",
        "-- 1. Satellite dimension lookup (Sec 8.2)",
        "INSERT INTO harmonized.dim_satellite",
        "    (sat_code, raw_satellite, firms_code, sensor, orbit_family, nominal_pixel_km, raw_table, first_date, last_date)",
        "VALUES",
        "    (1, 'Terra', 'T', 'MODIS', 'manana', 1.0, 'modis', DATE '2012-01-01', DATE '2026-08-31'),",
        "    (2, 'Aqua',  'A', 'MODIS', 'tarde',  1.0, 'modis', DATE '2012-01-01', DATE '2026-08-31'),",
        "    (3, 'SNPP',  'N', 'VIIRS', 'tarde',  0.375, 'viirs_suomi', DATE '2012-01-20', DATE '2026-07-31'),",
        "    (4, 'N20',   'N20', 'VIIRS', 'tarde', 0.375, 'viirs_j1', DATE '2018-04-01', DATE '2026-07-31'),",
        "    (5, 'N21',   'N21', 'VIIRS', 'tarde', 0.375, 'viirs_j2', DATE '2023-03-01', DATE '2026-07-31')",
        "ON CONFLICT (sat_code) DO NOTHING;",
        "",
        "-- 2. Documented orbital/acquisition gaps catalog (Sec 8.2)",
        "INSERT INTO harmonized.known_gap (gap_id, sat_code, date_from, date_to, gap_kind, source, note) VALUES",
        "    (1, 2, DATE '2020-08-16', DATE '2020-09-02', 'falla_documentada', 'nasa', 'Falla de Aqua: cobertura muy limitada (guía MODIS)'),",
        "    (2, 2, DATE '2022-04-01', DATE '2022-04-16', 'sin_datos', 'fase0', '16 días sin datos de Aqua'),",
        "    (3, 1, DATE '2016-02-19', DATE '2016-02-27', 'sin_datos', 'fase0', '9 días sin datos de Terra'),",
        "    (4, 1, DATE '2022-10-10', DATE '2022-10-23', 'sin_datos', 'fase0', 'Terra: caída el 10-oct y sin datos hasta el 23-oct')",
        "ON CONFLICT (gap_id) DO NOTHING;",
        "",
        "-- 3. Dataset metadata (Sec 8.2)",
        "INSERT INTO harmonized.dataset_metadata (key, value, description) VALUES",
        "    ('method_version', 'v0.2', 'Versión del método de armonización de cell_month'),",
        "    ('period', '2012-01..2026-08', 'Cobertura mensual de cell_month'),",
        "    ('baseline_min_years', '13', 'Años mínimos de línea base leave-one-out por mes calendario (excluye bits 0, 2, 3 y 4)'),",
        "    ('low_confidence_bands', '-60, 70 (y bandas polares sin datos)', 'Toman factor vecino (-90..-50 y 60..90) con bit 7'),",
        "    ('ui_warning_2026_08', 'Ago-2026 usa solo MODIS-Aqua, que por su deriva orbital detecta ~10 % menos que la serie armonizada; el valor tiende a subestimar.', 'Texto sugerido para la interfaz'),",
        f"    ('seed_data_rng', 'random-seed-{seed}', 'Datos aleatorios de prueba generados localmente para validar el esquema v0.2')",
        "ON CONFLICT (key) DO NOTHING;",
        "",
        "-- 4. Synthetic `harmonized.cell_month` sparse detections across 2012-01..2026-08",
    ]

    insert_header = (
        "INSERT INTO harmonized.cell_month (\n"
        "    month, cell_id, lat_center, lon_center, cell_area_km2,\n"
        "    n_eq, f_eq, ref_sat, sensors,\n"
        "    n_terra, n_aqua, n_snpp, n_n20, n_n21,\n"
        "    frp_terra, frp_aqua, frp_snpp, frp_n20, frp_n21,\n"
        "    quality_flag, method_version\n"
        ") VALUES"
    )
    for batch in _chunked(cell_month_tuples, 400):
        parts.append(insert_header)
        parts.append("    " + ",\n    ".join(batch))
        parts.append("ON CONFLICT (cell_id, month) DO NOTHING;")
        parts.append("")

    parts.extend(
        [
            "-- 5. Synchronize fast single-month map table `harmonized.map_month`",
            "INSERT INTO harmonized.map_month (",
            "    month, cell_id, lat_center, lon_center, cell_area_km2,",
            "    n_eq, f_eq, n_terra, frp_terra, quality_flag",
            ")",
            "SELECT month, cell_id, lat_center, lon_center, cell_area_km2,",
            "       n_eq, f_eq, n_terra, frp_terra, quality_flag",
            "FROM harmonized.cell_month",
            "ON CONFLICT (month, cell_id) DO NOTHING;",
            "",
            "-- 6. Synchronize `harmonized.global_month` across all 176 months",
            "INSERT INTO harmonized.global_month (month, n_eq_global, f_eq_global, quality_flag)",
            "SELECT",
            "    p.month,",
            "    COALESCE(SUM(c.n_eq::float8), 0),",
            "    COALESCE(SUM(c.f_eq::float8), 0),",
            "    p.quality_flag",
            "FROM harmonized.reference_plan p",
            "LEFT JOIN harmonized.cell_month c ON c.month = p.month",
            "GROUP BY p.month, p.quality_flag",
            "ON CONFLICT (month) DO UPDATE SET",
            "    n_eq_global = EXCLUDED.n_eq_global,",
            "    f_eq_global = EXCLUDED.f_eq_global,",
            "    quality_flag = EXCLUDED.quality_flag;",
            "",
            "-- 7. Populate `harmonized.sat_month_quality` diagnostics across satellites",
            "INSERT INTO harmonized.sat_month_quality (",
            "    month, sat_code, days_in_range, days_missing, days_caida,",
            "    days_parcial, days_catalog, days_minutes_low, days_affected, complete",
            ")",
            "SELECT",
            "    p.month,",
            "    s.sat_code,",
            "    EXTRACT(DAY FROM (p.month + INTERVAL '1 month - 1 day'))::smallint AS days_in_range,",
            "    CASE WHEN p.month = DATE '2012-03-01' AND s.sat_code = 3 THEN 2 ELSE 0 END AS days_missing,",
            "    CASE WHEN p.month = DATE '2012-03-01' AND s.sat_code = 3 THEN 2 ELSE 0 END AS days_caida,",
            "    CASE WHEN p.month = DATE '2012-01-01' AND s.sat_code = 3 THEN 12 ELSE 0 END AS days_parcial,",
            "    CASE WHEN p.month = DATE '2020-08-01' AND s.sat_code = 2 THEN 16 ELSE 0 END AS days_catalog,",
            "    0::smallint AS days_minutes_low,",
            "    CASE WHEN p.month IN (DATE '2012-01-01', DATE '2012-03-01', DATE '2020-08-01') THEN 4 ELSE 0 END AS days_affected,",
            "    CASE WHEN p.month IN (DATE '2012-01-01', DATE '2012-03-01', DATE '2020-08-01') THEN FALSE ELSE TRUE END AS complete",
            "FROM harmonized.reference_plan p",
            "JOIN harmonized.dim_satellite s",
            "  ON p.month BETWEEN date_trunc('month', s.first_date)::date AND date_trunc('month', s.last_date)::date",
            "ON CONFLICT (month, sat_code) DO NOTHING;",
            "",
            "COMMIT;",
            "",
            "ANALYZE harmonized.cell_month;",
            "ANALYZE harmonized.map_month;",
            "ANALYZE harmonized.global_month;",
            "ANALYZE harmonized.sat_month_quality;",
            "",
        ]
    )

    return "\n".join(parts), len(cell_month_tuples)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate random v0.2 Postgres seed SQL for `harmonized`.")
    parser.add_argument("--seed", type=int, default=2026, help="PRNG seed for reproducibility (default: 2026)")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_SQL,
        help=f"Output SQL file (default: {DEFAULT_OUTPUT_SQL})",
    )
    args = parser.parse_args()

    sql_text, row_count = build_seed_sql(args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(sql_text, encoding="utf-8")
    size_kb = len(sql_text.encode("utf-8")) / 1024.0
    print(f"Generated {row_count} harmonized.cell_month rows -> {args.output} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
