import csv
import io
import unittest
from datetime import date

from fastapi.testclient import TestClient

from cell_month_service import _build_spatial_where_clause
from main import app

from harmonized_cell_month import (
    BASELINE_EXCLUDE_MASK,
    PENDING_TEAM_CONFIRMATION,
    QualityFlagBits,
    HarmonizedCellMonthRow,
    aggregate_rows_by_month,
    bbox_to_cell_id_ranges,
    bit_or_flags,
    compute_aoi_grid_area_km2,
    compute_cell_month_calendar_anomalies,
    decode_quality_flags,
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
    method_version: str = "v0.1-provisional",
) -> HarmonizedCellMonthRow:
    return HarmonizedCellMonthRow(
        month=date(year, month_num, 1),
        cell_id=cell_id,
        lat_center=-31.375,
        lon_center=-64.125,
        cell_area_km2=658.4,
        n_eq=n_eq,
        f_eq=f_eq,
        ref_sat="N20",
        sensors="N20",
        n_terra=n_terra,
        n_aqua=int(n_eq),
        n_n20=int(n_eq * 3),
        frp_terra=round(n_terra * 18.0, 1),
        quality_flag=quality_flag,
        method_version=method_version,
    )


class TestHarmonizedCellMonthEngine(unittest.TestCase):
    def test_spherical_cell_area_matches_doc_benchmarks(self):
        """Section 3 benchmark: ~773 km2 at equator and ~387 km2 near 60 degrees."""
        eq_area = spherical_cell_area_km2(0.0, 0.25)
        lat60_area = spherical_cell_area_km2(59.75, 60.0)
        self.assertAlmostEqual(eq_area, 773.0, delta=1.5)
        self.assertAlmostEqual(lat60_area, 387.0, delta=3.0)

    def test_bbox_to_cell_id_ranges_and_antimeridian_split(self):
        """Contiguous BETWEEN range per latitude row, splitting into 2 per row across +-180."""
        # 2 latitude rows (-0.5 to 0.0 -> 2 bands), 2 longitude columns (-0.5 to 0.0 -> 2 cols)
        ranges_std = bbox_to_cell_id_ranges(-0.5, -0.5, 0.0, 0.0)
        self.assertEqual(len(ranges_std), 2)
        for a, b in ranges_std:
            self.assertEqual(b - a, 1)  # 2 columns -> [a, a+1]

        # Crossing antimeridian (min_lon = 179.5 > max_lon = -179.5) across 1 latitude row
        ranges_anti = bbox_to_cell_id_ranges(179.5, 0.0, -179.5, 0.25)
        self.assertEqual(len(ranges_anti), 2)
        # First chunk covers left side [0..col] and second chunk covers right edge [col..1439]
        self.assertEqual(ranges_anti[0][1] - ranges_anti[0][0], 1)
        self.assertEqual(ranges_anti[1][1] - ranges_anti[1][0], 1)

    def test_sparse_aoi_density_uses_full_grid_area(self):
        """Density divides SUM(f_eq) by FULL AOI grid area, not only returned active rows."""
        full_area = compute_aoi_grid_area_km2(-65.0, -32.0, -64.0, -31.0)
        self.assertGreater(full_area, 9000.0)  # 4x4 grid of 0.25° cells near -31.5°

        # Suppose only ONE cell out of 16 had fire activity
        rows = [_make_row(2024, 9, cell_id=50000, n_eq=10.0, f_eq=full_area * 0.5)]
        agg = aggregate_rows_by_month(rows, area_region_km2=full_area)
        self.assertEqual(len(agg), 1)
        self.assertAlmostEqual(agg[0].frp_density_mw_km2, 0.5, places=4)
        self.assertEqual(agg[0].active_cell_count, 1)

    def test_quality_flag_bit_or_and_decode(self):
        combined = bit_or_flags([
            QualityFlagBits.GAPS,
            QualityFlagBits.FALLBACK | QualityFlagBits.PROVISIONAL_CALIBRATION,
        ])
        codes = {item["code"] for item in decode_quality_flags(combined)}
        self.assertEqual(codes, {"gaps", "fallback", "provisional_calibration"})

    def test_anomaly_percentile_record_zrobust_and_ten_year_guard(self):
        """
        Verifies Section 4 rules:
        - Exclude GAPS/MODIS_ONLY/LAST_MONTH/PARTIAL_MONTH from baseline
        - Refuse anomaly calculation when baseline < 10 valid years
        - Compute exact mid-rank percentile, record flag, and log1p-MAD z-score
        """
        area = 10000.0
        rows: list[HarmonizedCellMonthRow] = []

        # 11 clean baseline years (2013..2023) for September with known n_eq values
        clean_values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 110.0]
        for idx, val in enumerate(clean_values):
            rows.append(_make_row(2013 + idx, 9, cell_id=100, n_eq=val, f_eq=val * 10.0))

        # 2024 September: extreme series record (250.0)
        rows.append(_make_row(2024, 9, cell_id=100, n_eq=250.0, f_eq=2500.0))
        # 2025 September: GAPS flag (must stay in output, but excluded from others' baseline)
        rows.append(
            _make_row(2025, 9, cell_id=100, n_eq=999.0, f_eq=9990.0, quality_flag=int(QualityFlagBits.GAPS))
        )

        # Also add January with only 5 years (< 10) -> must mark unavailable
        for y in range(2020, 2025):
            rows.append(_make_row(y, 1, cell_id=100, n_eq=15.0, f_eq=150.0))

        monthly = aggregate_rows_by_month(rows, area_region_km2=area)
        anomalies = compute_cell_month_calendar_anomalies(monthly, metric="n_eq")
        by_ym = {(a.year, a.month_num): a for a in anomalies}

        # January: < 10 baseline years -> unavailable
        jan_2024 = by_ym[(2024, 1)]
        self.assertFalse(jan_2024.anomaly_available)
        self.assertEqual(jan_2024.severity_class, "unavailable")

        # September 2024: baseline has 11 valid years (2013..2023; 2025 excluded due to GAPS)
        sep_2024 = by_ym[(2024, 9)]
        self.assertTrue(sep_2024.anomaly_available)
        self.assertEqual(sep_2024.baseline_years_count, 11)
        self.assertEqual(sep_2024.percentile, 1.0)
        self.assertEqual(sep_2024.severity_class, "gt_90")
        self.assertTrue(sep_2024.is_series_record)
        self.assertIsNotNone(sep_2024.z_robust_log1p)
        self.assertGreater(sep_2024.z_robust_log1p, 1.5)

        # September 2025 (GAPS): still rendered in calendar output, flagged as excluded from baseline
        sep_2025 = by_ym[(2025, 9)]
        self.assertTrue(sep_2025.excluded_from_baseline)
        self.assertTrue(sep_2025.anomaly_available)
        self.assertEqual(sep_2025.baseline_years_count, 12)  # 2013..2024 are all unflagged!

    def test_mad_zero_fallback_and_version_mixing_guard(self):
        """When MAD == 0, returns ratio to median instead of crashing; rejects mixed method_version."""
        area = 5000.0
        rows = [_make_row(2012 + i, 5, cell_id=200, n_eq=10.0, f_eq=100.0) for i in range(11)]
        rows.append(_make_row(2023, 5, cell_id=200, n_eq=30.0, f_eq=300.0))

        monthly = aggregate_rows_by_month(rows, area_region_km2=area)
        anomalies = compute_cell_month_calendar_anomalies(monthly, metric="n_eq")
        y2023 = [a for a in anomalies if a.year == 2023][0]
        self.assertIsNone(y2023.z_robust_log1p)
        self.assertAlmostEqual(y2023.ratio_to_median, 3.0)

        # Mixing method_version must raise ValueError
        mixed = [
            _make_row(2023, 6, cell_id=200, n_eq=10.0, f_eq=100.0, method_version="v0.1-provisional"),
            _make_row(2023, 7, cell_id=200, n_eq=10.0, f_eq=100.0, method_version="v1.0-final"),
        ]
        with self.assertRaises(ValueError):
            aggregate_rows_by_month(mixed, area_region_km2=area)

        # Pending confirmation map exists cleanly
        self.assertFalse(PENDING_TEAM_CONFIRMATION["quality_flag_bitmask_confirmed"])

    def test_cell_month_api_endpoints_and_csv_export(self):
        """Verifies GET /api/cell-month/aoi and GET /api/cell-month/export.csv via stub fallback."""
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
        self.assertEqual(payload["method_version"], "v0.1-provisional")
        self.assertIn(payload["data_source"], ("stub", "postgres"))
        self.assertGreater(payload["area_region_km2"], 0.0)
        # Complete 2012-01..2026-08 calendar (176 months) even when sparse AOI has zero-fire months
        self.assertEqual(len(payload["calendar_anomalies"]), 176)
        self.assertIn("pending_confirmations", payload)
        self.assertIn("n_terra_separate_series", payload["summary"])

        # Verify 2026-08 unconditionally carries MODIS_ONLY + LAST_MONTH from month-level quality map
        aug_2026 = [c for c in payload["calendar_anomalies"] if c["year"] == 2026 and c["month_num"] == 8]
        self.assertEqual(len(aug_2026), 1)
        codes = {f["code"] for f in aug_2026[0]["quality_flags_decoded"]}
        self.assertIn("modis_only", codes)
        self.assertIn("last_month", codes)

        # Verify CSV export
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
        headers = reader[0]
        for required_col in ("month", "cell_id", "n_eq", "f_eq", "ref_sat", "sensors", "quality_flag", "method_version"):
            self.assertIn(required_col, headers)

    def test_sql_spatial_predicate_modes(self):
        """Verifies both lat/lon fallback and cell_id BETWEEN SQL predicates (regular + antimeridian)."""
        sql_ll, params_ll = _build_spatial_where_clause(-65.0, -32.0, -64.0, -31.0, use_cell_id_ranges=False)
        self.assertIn("lat_center BETWEEN", sql_ll)
        self.assertEqual(params_ll, [-32.0, -31.0, -65.0, -64.0])

        sql_anti, params_anti = _build_spatial_where_clause(179.0, -1.0, -179.0, 1.0, use_cell_id_ranges=False)
        self.assertIn("OR lon_center <=", sql_anti)
        self.assertEqual(params_anti, [-1.0, 1.0, 179.0, -179.0])

        sql_cid, params_cid = _build_spatial_where_clause(-0.5, -0.5, 0.0, 0.0, use_cell_id_ranges=True)
        self.assertIn("cell_id BETWEEN %s AND %s", sql_cid)
        self.assertEqual(len(params_cid), 4)  # 2 latitude rows * 2 bounds each

    def test_sparse_zero_months_and_month_level_quality_table(self):
        """Zero-fire months are filled as 0.0 via calendar sequence and preserve month-level flags."""
        area = 8000.0
        # Only 1 active fire row in March 2024; 2012..2026 other Marches had 0 fires
        rows = [_make_row(2024, 3, cell_id=300, n_eq=25.0, f_eq=250.0)]
        all_months = iter_calendar_months(date(2012, 1, 1), date(2026, 8, 1))
        monthly_quality = {date(2026, 8, 1): int(QualityFlagBits.MODIS_ONLY | QualityFlagBits.LAST_MONTH)}

        agg = aggregate_rows_by_month(
            rows,
            area_region_km2=area,
            all_months=all_months,
            monthly_quality_map=monthly_quality,
        )
        self.assertEqual(len(agg), 176)

        aug26 = [m for m in agg if m.month == date(2026, 8, 1)][0]
        self.assertEqual(aug26.n_eq, 0.0)
        self.assertTrue(bool(aug26.quality_flag & QualityFlagBits.MODIS_ONLY))

        anomalies = compute_cell_month_calendar_anomalies(agg, metric="n_eq")
        mar24 = [a for a in anomalies if a.year == 2024 and a.month_num == 3][0]
        # 2012..2023 + 2025..2026 Marches (14 zero-fire years) count as valid baseline!
        self.assertTrue(mar24.anomaly_available)
        self.assertEqual(mar24.baseline_years_count, 14)
        self.assertTrue(mar24.is_series_record)


if __name__ == "__main__":
    unittest.main()
