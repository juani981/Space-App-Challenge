"""
Pruebas de la conexión del backend a la base armonizada (`harmonized.cell_month`, v0.2).

1. `TestDatabaseErrorHandling` (siempre): en modo `database`, si la base no responde la API
   devuelve HTTP 503 genérico y NUNCA datos sintéticos ni detalles de la conexión.
2. `TestRealDatabaseIntegration` (solo si `INTEGRATION_DATABASE_URL` está definida): verifica
   contra la base real los valores medidos en docs/CONTRATO_DATOS_WEB.md.

Ejemplo (base del contenedor Docker, puerto publicado en .env):
    INTEGRATION_DATABASE_URL=postgresql://wildfire_web:<clave>@127.0.0.1:5434/hotspots_db \
    python -m unittest test_db_connection -v
"""

import os
import unittest
import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402

import cell_month_service  # noqa: E402
from main import app  # noqa: E402

INTEGRATION_URL = os.getenv("INTEGRATION_DATABASE_URL")

CORDOBA = dict(min_lon=-65.8, min_lat=-35.0, max_lon=-61.8, max_lat=-29.5)
ARGENTINA = dict(min_lon=-73.5, min_lat=-55.0, max_lon=-53.5, max_lat=-22.0)
SUDAMERICA = dict(min_lon=-82.0, min_lat=-56.0, max_lon=-34.0, max_lat=13.0)
OCEANO = dict(min_lon=-30.0, min_lat=-30.0, max_lon=-25.0, max_lat=-25.0)


class _DatabaseModeMixin:
    """Fuerza modo `database` y una URL dada, restaurando el estado original al terminar."""

    url: str = ""

    def setUp(self):
        self._prev_mode = cell_month_service.DATA_SOURCE_MODE
        self._prev_url = cell_month_service.DATABASE_URL
        cell_month_service.DATA_SOURCE_MODE = "database"
        cell_month_service.DATABASE_URL = self.url
        self.client = TestClient(app)

    def tearDown(self):
        cell_month_service.DATA_SOURCE_MODE = self._prev_mode
        cell_month_service.DATABASE_URL = self._prev_url


class TestDatabaseErrorHandling(_DatabaseModeMixin, unittest.TestCase):
    # Puerto 1: nadie escucha ahí, la conexión falla de inmediato.
    url = "postgresql://nadie:secreto@127.0.0.1:1/base_inexistente"

    def _assert_503_sin_detalles(self, response):
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["error"], "database_unavailable")
        for filtrado in ("secreto", "base_inexistente", "127.0.0.1", "nadie"):
            self.assertNotIn(filtrado, body["detail"], "el 503 no debe exponer datos de conexión")

    def test_aoi_returns_503_instead_of_stub(self):
        response = self.client.get("/api/cell-month/aoi", params={**CORDOBA, "start_date": "2024-08", "end_date": "2024-08"})
        self._assert_503_sin_detalles(response)

    def test_csv_returns_503_instead_of_stub(self):
        response = self.client.get("/api/cell-month/export.csv", params={**CORDOBA, "start_date": "2024-01", "end_date": "2024-12"})
        self._assert_503_sin_detalles(response)

    def test_health_returns_503(self):
        self._assert_503_sin_detalles(self.client.get("/api/health"))


@unittest.skipUnless(INTEGRATION_URL, "definir INTEGRATION_DATABASE_URL para probar contra la base real")
class TestRealDatabaseIntegration(_DatabaseModeMixin, unittest.TestCase):
    url = INTEGRATION_URL or ""

    def _aoi(self, bbox, start, end):
        response = self.client.get("/api/cell-month/aoi", params={**bbox, "start_date": start, "end_date": end})
        self.assertEqual(response.status_code, 200, response.text[:300])
        data = response.json()
        self.assertEqual(data["data_source"], "postgres")
        return data

    def test_health_reports_v02(self):
        data = self.client.get("/api/health").json()
        self.assertEqual(data["database"], "conectada")
        self.assertEqual(data["method_version"], "v0.2")
        self.assertEqual(data["series"], {"first_month": "2012-01-01", "last_month": "2026-08-01", "months": 176})
        self.assertGreater(data["cell_month_rows_estimate"], 9_000_000)

    def test_single_month_map_uses_real_rows(self):
        # Contrato 6c: Argentina, ago-2024, 0,25° -> 2.758 celdas
        data = self._aoi(ARGENTINA, "2024-08", "2024-08")
        self.assertEqual(data["resolution_deg"], 0.25)
        self.assertEqual(len(data["cells"]), 2758)
        self.assertTrue(all(c["sensors"] for c in data["cells"]))

    def test_twelve_month_map(self):
        # Contrato 6c: Argentina, 2024, 0,25° -> 4.649 celdas
        self.assertEqual(len(self._aoi(ARGENTINA, "2024-01", "2024-12")["cells"]), 4649)

    def test_1deg_rollup_without_calendar_above_50k_cells(self):
        # Contrato 6c: Sudamérica (52.992 celdas) a 1°, ago-2024 -> 1.496 bloques; calendario no disponible
        data = self._aoi(SUDAMERICA, "2024-08", "2024-08")
        self.assertEqual(data["resolution_deg"], 1.0)
        self.assertEqual(len(data["cells"]), 1496)
        self.assertFalse(data["calendar_available"])

    def test_calendar_has_176_months_and_month_flags(self):
        data = self._aoi(CORDOBA, "2024-01", "2024-12")
        series = {m["month"]: m for m in data["monthly_series"]}
        self.assertEqual(len(series), 176)
        self.assertEqual(series["2012-01-01"]["quality_flag"] & 1, 1)        # bit 0: VIIRS parcial
        self.assertEqual(series["2012-03-01"]["quality_flag"] & 24, 24)      # bits 3 y 4: referencia incompleta
        self.assertEqual(series["2023-07-01"]["quality_flag"] & 64, 64)      # bit 6: respaldo NOAA-21
        self.assertEqual(series["2026-08-01"]["quality_flag"] & 4, 4)        # bit 2: solo MODIS

    def test_empty_ocean_region_is_zero_not_stub(self):
        data = self._aoi(OCEANO, "2024-08", "2024-08")
        self.assertEqual(data["cells"], [])
        self.assertEqual(len(data["monthly_series"]), 176)
        self.assertTrue(all(m["n_eq"] == 0 for m in data["monthly_series"]))

    def test_csv_stream_row_count(self):
        response = self.client.get("/api/cell-month/export.csv", params={**CORDOBA, "start_date": "2024-01", "end_date": "2024-12"})
        self.assertEqual(response.status_code, 200)
        lines = response.text.strip().splitlines()
        self.assertEqual(response.headers["X-Export-Row-Count"], str(len(lines) - 1))
        self.assertEqual(len(lines) - 1, 1364)
        self.assertTrue(lines[0].startswith("month,cell_id,lat_center,lon_center"))


if __name__ == "__main__":
    unittest.main()
