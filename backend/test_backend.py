import unittest
from fastapi.testclient import TestClient

from team_contract import (
    UnifiedHotspot,
    parse_team_record,
    TEAM_FIELD_MAP,
    DATA_SOURCE_MODE,
)
from harmonization import (
    apply_harmonization,
    compute_monthly_calendar_matrix,
    export_hotspots_csv,
    FOOTPRINT_MODIS_KM2,
    FOOTPRINT_VIIRS_375M_KM2,
)
from main import app


class TestBackendScientificHarmonization(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_team_contract_canonical_10_concepts(self):
        """Ensures all 10 concepts are mapped and analysis_metrics is supported without breaking core fields."""
        raw = {
            "datetime_utc": "2024-08-15T14:30:00Z",
            "satellite": "N20",
            "lat": -31.42,
            "lon": -64.18,
            "temp_1": 345.5,
            "temp_2": 298.0,
            "pixel_area_km2": 0.14,
            "frp": 25.4,
            "confidence": "high",
            "type": 0,
            "daynight": "D",
        }
        hs = parse_team_record(raw)
        self.assertEqual(hs.datetime_utc, "2024-08-15T14:30:00Z")
        self.assertEqual(hs.satellite, "N20")
        self.assertAlmostEqual(hs.lat, -31.42)
        self.assertAlmostEqual(hs.lon, -64.18)
        self.assertEqual(hs.temp_1, 345.5)
        self.assertEqual(hs.temp_2, 298.0)
        self.assertEqual(hs.pixel_geom, 0.14)
        self.assertEqual(hs.frp, 25.4)
        self.assertEqual(hs.confidence, "high")
        self.assertEqual(hs.fire_type, 0)
        self.assertEqual(hs.day_night, "D")
        self.assertIsNone(hs.analysis_metrics)

    def test_data_source_mode_switch(self):
        """Verifies the clean 1-line switch for stub vs real database exists."""
        self.assertIn(DATA_SOURCE_MODE, ["stub", "database"])

    def test_harmonization_modes(self):
        """Verifies raw, area_weighted, and deduplicated calibration logic."""
        hs_modis = UnifiedHotspot(
            datetime_utc="2024-08-15T14:00:00Z",
            satellite="T",
            lat=-31.4200,
            lon=-64.1800,
            pixel_geom=FOOTPRINT_MODIS_KM2,
            frp=50.0,
            confidence="nominal",
        )
        hs_viirs = UnifiedHotspot(
            datetime_utc="2024-08-15T14:30:00Z",
            satellite="N20",
            lat=-31.4205,
            lon=-64.1805,
            pixel_geom=FOOTPRINT_VIIRS_375M_KM2,
            frp=20.0,
            confidence="high",
        )

        # 1. Raw mode
        raw_res = apply_harmonization([hs_modis, hs_viirs], mode="raw")
        self.assertEqual(len(raw_res), 2)
        self.assertEqual(raw_res[0].analysis_metrics["harmonization_mode"], "raw")
        self.assertEqual(raw_res[0].analysis_metrics["harmonization_factor"], 1.0)

        # 2. Area-weighted mode
        weighted_res = apply_harmonization([hs_modis, hs_viirs], mode="area_weighted")
        self.assertEqual(len(weighted_res), 2)
        # MODIS weight ~ 1.0
        self.assertAlmostEqual(weighted_res[0].analysis_metrics["harmonization_factor"], 1.0, places=2)
        # VIIRS weight ~ 0.14 (reflecting 0.14 km2 footprint)
        self.assertAlmostEqual(weighted_res[1].analysis_metrics["harmonization_factor"], 0.14, places=2)

        # 3. Deduplicated mode (space-time clustering within ~1.5km and 6h)
        dedup_res = apply_harmonization([hs_modis, hs_viirs], mode="deduplicated")
        self.assertEqual(len(dedup_res), 1)  # Merged into 1 cluster
        cluster_hs = dedup_res[0]
        self.assertTrue(cluster_hs.analysis_metrics["is_cluster"])
        self.assertEqual(cluster_hs.analysis_metrics["merged_count"], 2)
        self.assertIn("T", cluster_hs.analysis_metrics["satellites_involved"])
        self.assertIn("N20", cluster_hs.analysis_metrics["satellites_involved"])
        self.assertEqual(cluster_hs.analysis_metrics["peak_frp"], 50.0)

    def test_calendar_matrix_computation(self):
        """Verifies multi-year monthly calendar matrix with historical medians and anomalies."""
        test_hotspots = [
            UnifiedHotspot(
                datetime_utc=f"{y}-08-15T12:00:00Z",
                satellite="T",
                lat=-31.0,
                lon=-64.0,
                frp=30.0,
                confidence="nominal",
            )
            for y in range(2001, 2027)
        ]
        # Extra hotspots in 2024 August to simulate an elevated anomaly
        for _ in range(5):
            test_hotspots.append(
                UnifiedHotspot(
                    datetime_utc="2024-08-20T14:00:00Z",
                    satellite="N20",
                    lat=-31.1,
                    lon=-64.1,
                    frp=40.0,
                    confidence="high",
                )
            )

        cells = compute_monthly_calendar_matrix(test_hotspots, start_year=2001, end_year=2026)
        self.assertEqual(len(cells), 26 * 12)

        # Check August 2024 cell
        aug_2024 = next(c for c in cells if c.year == 2024 and c.month == 8)
        self.assertEqual(aug_2024.count, 6)
        self.assertGreater(aug_2024.anomaly_pct, 0.0)
        self.assertIn(aug_2024.severity, ["elevated", "extreme"])

    def test_export_csv(self):
        """Verifies CSV generation has correct RFC-4180 headers and values."""
        hs = UnifiedHotspot(
            datetime_utc="2024-08-15T12:00:00Z",
            satellite="N21",
            lat=-31.5,
            lon=-64.5,
            pixel_geom=0.14,
            frp=45.2,
            confidence="high",
            analysis_metrics={"harmonization_mode": "area_weighted", "harmonization_factor": 0.14},
        )
        csv_str = export_hotspots_csv([hs])
        self.assertIn("datetime_utc,satellite,lat,lon", csv_str)
        self.assertIn("harmonization_mode,harmonization_factor", csv_str)
        self.assertIn("2024-08-15T12:00:00Z,N21,-31.50000,-64.50000", csv_str)

    def test_api_endpoints(self):
        """Verifies HTTP API endpoints."""
        # Health check
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)

        # GET /api/aoi default
        res_aoi = self.client.get("/api/aoi")
        self.assertEqual(res_aoi.status_code, 200)
        data = res_aoi.json()
        self.assertIn("bounds", data)
        self.assertIn("calendar_cells", data)
        self.assertIn("hotspots", data)
        self.assertIn("summary", data)

        # GET /api/aoi with deduplicated mode and custom dates
        res_dedup = self.client.get(
            "/api/aoi",
            params={
                "min_lon": -64.0,
                "min_lat": -33.0,
                "max_lon": -60.0,
                "max_lat": -30.0,
                "start_date": "2024-08-01",
                "end_date": "2024-08-31",
                "calibration_mode": "deduplicated",
            },
        )
        self.assertEqual(res_dedup.status_code, 200)
        dedup_data = res_dedup.json()
        self.assertEqual(dedup_data["calibration_mode"], "deduplicated")

        # GET /api/aoi/export.csv
        res_csv = self.client.get(
            "/api/aoi/export.csv",
            params={
                "calibration_mode": "area_weighted",
            },
        )
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("attachment; filename=", res_csv.headers["content-disposition"])
        self.assertIn("datetime_utc,satellite", res_csv.text)


if __name__ == "__main__":
    unittest.main()
