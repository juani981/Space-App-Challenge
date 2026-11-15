import csv
import io
import unittest
from datetime import date

from fastapi.testclient import TestClient

from cell_month_service import _build_spatial_where_clause, prepare_cell_month_csv_stream
from main import app

from harmonized_cell_month import (
    BASELINE_EXCLUDE_MASK,
    DEFAULT_METHOD_VERSION,
    EXCLUDE_BASELINE_MASK,
    MAP_1DEG_CELL_THRESHOLD,
    MAX_CALENDAR_CELLS,
    TEAM_CONTRACT_V02,
    HarmonizedCellMonthRow,
    QualityFlagBits,
    aggregate_cells_to_1deg,
    aggregate_rows_by_month,
    aoi_cell_count,
    bbox_to_cell_id_ranges,
    bit_or_flags,
    cell_id_to_center_and_area,
    compute_aoi_grid_area_km2,
    compute_cell_month_calendar_anomalies,
    decode_quality_flags,
    get_v02_reference_plan,
    iter_calendar_months,
    spherical_cell_area_km2,
)


def _make_row(
    year: int,
    month_num: int,
    cell_id: int,
    n_eq: float,
    f_eq: float,
    quality_flag: int = 0,
    n_terra: int = 0,
    method_version: str = DEFAULT_METHOD_VERSION,
) -> HarmonizedCellMonthRow:
    return HarmonizedCellMonthRow(
        month=date(year, month_num, 1),
        cell_id=cell_id,
        lat_center=-25.125,
        lon_center=-60.125,
        cell_area_km2=699.6523,
        n_eq=n_eq,
        f_eq=f_eq,
        ref_sat=4,
        sensors="N20",
        n_terra=n_terra,
        n_aqua=int(n_eq),
        n_n20=int(n_eq * 3),
        frp_terra=round(n_terra * 18.0, 1),
        quality_flag=quality_flag,
        method_version=method_version,
    )


class TestHarmonizedCellMonthEngine(unittest.TestCase):
    def test_postgres_verified_cell_id_test_vectors(self):
        """Asserts all 5 exact cell_id -> (lat_center, lon_center, cell_area_km2) vectors from Sec 3.2."""
        vectors = [
            (373439, -25.125, -60.125, 699.6523),
            (519200, 0.125, 20.125, 772.767),
            (1021366, 87.375, -78.375, 35.391937),
            (908639, 67.625, 179.875, 294.16754),
            (172334, -60.125, 63.625, 384.92346),
        ]
        for cid, exp_lat, exp_lon, exp_area in vectors:
            lat, lon, area = cell_id_to_center_and_area(cid)
            self.assertAlmostEqual(lat, exp_lat, places=6, msg=f"cell_id={cid} lat mismatch")
            self.assertAlmostEqual(lon, exp_lon, places=6, msg=f"cell_id={cid} lon mismatch")
            self.assertAlmostEqual(area, exp_area, delta=0.005, msg=f"cell_id={cid} area mismatch")

    def test_postgres_verified_bbox_benchmarks(self):
        """Asserts all 4 bbox range, cell count, and spherical area benchmarks from Sec 3.3."""
        benchmarks = [
            (-82.0, -56.0, -34.0, 13.0, 276, 52_992, 35_840_143.5),     # Sudamerica
            (15.0, -5.0, 25.0, 5.0, 40, 1_600, 1_234_862.4),             # Ecuador
            (170.0, 60.0, -170.0, 72.0, 96, 3_840, 1_204_759.7),         # Antimeridiano
            (-180.0, 80.0, 180.0, 95.0, 40, 57_600, 3_874_512.7),        # Polo norte recortado
        ]
        for min_lon, min_lat, max_lon, max_lat, exp_ranges, exp_cells, exp_area in benchmarks:
            ranges = bbox_to_cell_id_ranges(min_lon, min_lat, max_lon, max_lat)
            cells = aoi_cell_count(min_lon, min_lat, max_lon, max_lat)
            area = compute_aoi_grid_area_km2(min_lon, min_lat, max_lon, max_lat)
            self.assertEqual(len(ranges), exp_ranges)
            self.assertEqual(cells, exp_cells)
            self.assertAlmostEqual(area, exp_area, delta=25.0)

    def test_spherical_cell_area_matches_doc_benchmarks(self):
        """Spherical area at equator (~772.8 km2) and 60 deg (~387 km2)."""
        eq_area = spherical_cell_area_km2(0.0, 0.25)
        lat60_area = spherical_cell_area_km2(59.75, 60.0)
        self.assertAlmostEqual(eq_area, 772.8, delta=1.5)
        self.assertAlmostEqual(lat60_area, 387.0, delta=3.0)

    def test_v02_quality_flags_mask_and_reference_plan(self):
        """Verifies EXCLUDE_BASELINE_MASK == 29 and exact 176-month reference_plan rules (Sec 8.2-8.3)."""
        self.assertEqual(BASELINE_EXCLUDE_MASK, 29)
        self.assertEqual(EXCLUDE_BASELINE_MASK, 29)
        self.assertTrue(TEAM_CONTRACT_V02["quality_flag_bitmask_confirmed"])

        combined = bit_or_flags([
            QualityFlagBits.REF_INCOMPLETA_HUECOS,
            QualityFlagBits.REFERENCIA_RESPALDO | QualityFlagBits.CALIBRACION_BAJA_CONF,
        ])
        codes = {item["code"] for item in decode_quality_flags(combined)}
        self.assertEqual(codes, {"ref_incompleta_huecos", "referencia_respaldo", "calibracion_baja_conf"})

        plan = get_v02_reference_plan()
        self.assertEqual(len(plan), 176)
        by_month = {row["month"]: row for row in plan}
        self.assertEqual(by_month[date(2012, 1, 1)]["quality_flag"], 1)
        self.assertEqual(by_month[date(2012, 3, 1)]["quality_flag"], 24)
        self.assertEqual(by_month[date(2023, 7, 1)]["quality_flag"], 64)
        self.assertEqual(by_month[date(2023, 7, 1)]["ref_sat"], 5)
        self.assertEqual(by_month[date(2026, 7, 1)]["quality_flag"], 2)
        self.assertEqual(by_month[date(2026, 8, 1)]["quality_flag"], 6)
        self.assertEqual(by_month[date(2026, 8, 1)]["ref_sat"], 2)

    def test_sparse_aoi_density_uses_full_grid_area(self):
        """Density divides SUM(f_eq) by FULL AOI grid area, not only returned active rows."""
        full_area = compute_aoi_grid_area_km2(-65.0, -32.0, -64.0, -31.0)
        self.assertGreater(full_area, 9000.0)

        rows = [_make_row(2024, 9, cell_id=373439, n_eq=10.0, f_eq=full_area * 0.5)]
        agg = aggregate_rows_by_month(rows, area_region_km2=full_area)
        self.assertEqual(len(agg), 1)
        self.assertAlmostEqual(agg[0].frp_density_mw_km2, 0.5, places=4)
        self.assertEqual(agg[0].active_cell_count, 1)

    def test_anomaly_percentile_record_zrobust_and_ten_year_guard(self):
        """Verifies baseline exclusions, strict > max record, 10-year guard, and log1p-MAD."""
        area = 10000.0
        rows: list[HarmonizedCellMonthRow] = []

        clean_values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 110.0]
        for idx, val in enumerate(clean_values):
            rows.append(_make_row(2013 + idx, 9, cell_id=100, n_eq=val, f_eq=val * 10.0))

        # 2024 September: extreme series record (250.0)
        rows.append(_make_row(2024, 9, cell_id=100, n_eq=250.0, f_eq=2500.0))
        # 2025 September: excluded bit 3 (REF_INCOMPLETA_HUECOS = 8)
        rows.append(
            _make_row(
                2025,
                9,
                cell_id=100,
                n_eq=999.0,
                f_eq=9990.0,
                quality_flag=int(QualityFlagBits.REF_INCOMPLETA_HUECOS),
            )
        )

        # January with only 5 years (< 10) -> must mark unavailable
        for y in range(2020, 2025):
            rows.append(_make_row(y, 1, cell_id=100, n_eq=15.0, f_eq=150.0))

        monthly = aggregate_rows_by_month(rows, area_region_km2=area)
        anomalies = compute_cell_month_calendar_anomalies(monthly, metric="n_eq")
        by_ym = {(a.year, a.month_num): a for a in anomalies}

        jan_2024 = by_ym[(2024, 1)]
        self.assertFalse(jan_2024.anomaly_available)
        self.assertEqual(jan_2024.severity_class, "unavailable")

        sep_2024 = by_ym[(2024, 9)]
        self.assertTrue(sep_2024.anomaly_available)
        self.assertEqual(sep_2024.baseline_years_count, 11)
        self.assertEqual(sep_2024.percentile, 1.0)
        self.assertEqual(sep_2024.severity_class, "gt_90")
        self.assertTrue(sep_2024.is_series_record)
        self.assertGreater(sep_2024.z_robust_log1p, 1.5)

        sep_2025 = by_ym[(2025, 9)]
        self.assertTrue(sep_2025.excluded_from_baseline)
        self.assertTrue(sep_2025.anomaly_available)
        self.assertEqual(sep_2025.baseline_years_count, 12)

    def test_mad_zero_and_strict_record_and_version_guard(self):
        """MAD==0 falls back cleanly; equal-to-max is NOT a record; mixed method_version raises."""
        area = 5000.0
        rows = [_make_row(2012 + i, 5, cell_id=200, n_eq=10.0, f_eq=100.0) for i in range(11)]
        # Exact tie with max (10.0): must NOT count as series record (strict X > max)
        rows.append(_make_row(2023, 5, cell_id=200, n_eq=10.0, f_eq=100.0))

        monthly = aggregate_rows_by_month(rows, area_region_km2=area)
        anomalies = compute_cell_month_calendar_anomalies(monthly, metric="n_eq")
        y2023 = [a for a in anomalies if a.year == 2023][0]
        self.assertIsNone(y2023.z_robust_log1p)
        self.assertAlmostEqual(y2023.ratio_to_median, 1.0)
        self.assertFalse(y2023.is_series_record)

        mixed = [
            _make_row(2023, 6, cell_id=200, n_eq=10.0, f_eq=100.0, method_version="v0.1"),
            _make_row(2023, 7, cell_id=200, n_eq=10.0, f_eq=100.0, method_version="v0.2"),
        ]
        with self.assertRaises(ValueError):
            aggregate_rows_by_month(mixed, area_region_km2=area)

    def test_1deg_aggregation_and_api_warnings_and_limits(self):
        """Verifies 1° block_id rollup, >20k / >50k limits, <4 cells / bit 7 / 2026-08 warnings."""
        # Two cells inside the same 1° block (fila 360..363, col 720..723 -> block_id = 90*360 + 180)
        cid_a = 360 * 1440 + 720
        cid_b = 361 * 1440 + 721
        blocks = aggregate_cells_to_1deg([
            {"cell_id": cid_a, "n_eq": 10.0, "f_eq": 200.0, "quality_flag": 0, "active_months": 2},
            {"cell_id": cid_b, "n_eq": 5.0, "f_eq": 100.0, "quality_flag": 128, "active_months": 4},
        ])
        self.assertEqual(len(blocks), 1)
        self.assertAlmostEqual(blocks[0]["lat_center"], 0.5)
        self.assertAlmostEqual(blocks[0]["lon_center"], 0.5)
        self.assertEqual(blocks[0]["n_eq"], 15.0)
        self.assertEqual(blocks[0]["quality_flag"], 128)
        self.assertEqual(blocks[0]["resolution_deg"], 1.0)

        client = TestClient(app)

        # Case 1: Tiny AOI (<4 cells) at -61° touching bit 7 and 2026-08 drift
        tiny = client.get(
            "/api/cell-month/aoi",
            params={
                "min_lon": -68.0,
                "min_lat": -61.0,
                "max_lon": -67.75,
                "max_lat": -60.75,
                "start_date": "2026-06-01",
                "end_date": "2026-08-01",
            },
        ).json()
        self.assertLess(tiny["aoi_cells_count"], 4)
        self.assertEqual(tiny["resolution_deg"], 0.25)
        self.assertTrue(tiny["calendar_available"])
        warn_codes = {w["code"] for w in tiny["ui_warnings"]}
        self.assertTrue({"few_cells", "low_confidence_band", "aqua_2026_08_drift"}.issubset(warn_codes))

        # Case 2: Large AOI (> 20k and > 50k cells, e.g. Sudamerica 52,992 cells)
        large = client.get(
            "/api/cell-month/aoi",
            params={
                "min_lon": -82.0,
                "min_lat": -56.0,
                "max_lon": -34.0,
                "max_lat": 13.0,
                "start_date": "2024-01-01",
                "end_date": "2024-12-01",
            },
        ).json()
        self.assertGreater(large["aoi_cells_count"], MAP_1DEG_CELL_THRESHOLD)
        self.assertGreater(large["aoi_cells_count"], MAX_CALENDAR_CELLS)
        self.assertEqual(large["resolution_deg"], 1.0)
        self.assertFalse(large["calendar_available"])
        self.assertEqual(large["calendar_anomalies"], [])

    def test_cell_month_api_endpoints_and_streaming_csv_export(self):
        """Verifies v0.2 GET /api/cell-month/aoi and streaming GET /api/cell-month/export.csv."""
        client = TestClient(app)

        resp = client.get(
            "/api/cell-month/aoi",
            params={
                "min_lon": -65.0,
                "min_lat": -32.0,
                "max_lon": -63.0,
                "max_lat": -30.0,
                "start_date": "2024-01-01",
                "end_date": "2026-08-01",
                "metric": "f_eq",
            },
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["method_version"], DEFAULT_METHOD_VERSION)
        self.assertEqual(payload["resolution_deg"], 0.25)
        self.assertTrue(payload["calendar_available"])
        self.assertEqual(len(payload["calendar_anomalies"]), 176)

        aug_2026 = [c for c in payload["calendar_anomalies"] if c["year"] == 2026 and c["month_num"] == 8]
        codes = {f["code"] for f in aug_2026[0]["quality_flags_decoded"]}
        self.assertEqual(codes, {"solo_modis_deriva", "ultimo_mes_standard"})

        # Verify streaming CSV endpoint + chunk iterator directly
        _, _, count_est, stream = prepare_cell_month_csv_stream(-65.0, -32.0, -63.0, -30.0, "2024-01-01", "2024-12-31")
        csv_text = b"".join(stream).decode("utf-8")
        rows = list(csv.reader(io.StringIO(csv_text)))
        self.assertEqual(len(rows) - 1, count_est)

        csv_resp = client.get(
            "/api/cell-month/export.csv",
            params={
                "min_lon": -65.0,
                "min_lat": -32.0,
                "max_lon": -63.0,
                "max_lat": -30.0,
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
        )
        self.assertEqual(csv_resp.status_code, 200)
        self.assertIn("text/csv", csv_resp.headers["content-type"])
        reader = list(csv.reader(io.StringIO(csv_resp.text)))
        self.assertGreater(len(reader), 1)
        for required_col in ("month", "cell_id", "n_eq", "f_eq", "ref_sat", "sensors", "quality_flag", "method_version"):
            self.assertIn(required_col, reader[0])

    def test_sql_spatial_predicate_modes(self):
        """Verifies both lat/lon fallback and confirmed south_to_north cell_id BETWEEN SQL predicates."""
        sql_ll, params_ll = _build_spatial_where_clause(-65.0, -32.0, -64.0, -31.0, use_cell_id_ranges=False)
        self.assertIn("lat_center BETWEEN", sql_ll)
        self.assertEqual(params_ll, [-32.0, -31.0, -65.0, -64.0])

        sql_cid, params_cid = _build_spatial_where_clause(-0.5, -0.5, 0.0, 0.0, use_cell_id_ranges=True)
        self.assertIn("cell_id BETWEEN %s AND %s", sql_cid)
        self.assertEqual(len(params_cid), 4)

    def test_sparse_zero_months_and_month_level_quality_table(self):
        """Zero-fire months are filled as 0.0 via calendar sequence and preserve month-level flags."""
        area = 8000.0
        rows = [_make_row(2024, 3, cell_id=373439, n_eq=25.0, f_eq=250.0)]
        all_months = iter_calendar_months(date(2012, 1, 1), date(2026, 8, 1))
        monthly_quality = {date(2026, 8, 1): int(QualityFlagBits.SOLO_MODIS_DERIVA | QualityFlagBits.ULTIMO_MES_STANDARD)}

        agg = aggregate_rows_by_month(
            rows,
            area_region_km2=area,
            all_months=all_months,
            monthly_quality_map=monthly_quality,
        )
        self.assertEqual(len(agg), 176)

        aug26 = [m for m in agg if m.month == date(2026, 8, 1)][0]
        self.assertEqual(aug26.n_eq, 0.0)
        self.assertTrue(bool(aug26.quality_flag & QualityFlagBits.SOLO_MODIS_DERIVA))

        anomalies = compute_cell_month_calendar_anomalies(agg, metric="n_eq")
        mar24 = [a for a in anomalies if a.year == 2024 and a.month_num == 3][0]
        self.assertTrue(mar24.anomaly_available)
        self.assertEqual(mar24.baseline_years_count, 14)
        self.assertTrue(mar24.is_series_record)


if __name__ == "__main__":
    unittest.main()
