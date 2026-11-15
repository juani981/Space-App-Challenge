"""
PostgreSQL Database Connector for Harmonized Hotspots.
Supports real spatial-temporal querying against PostgreSQL 18 table `hotspots`.
Provides automatic fallback to the deterministic stub generator if the database
is unreachable, uninitialized, or driver is absent.
"""

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger("backend.db")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/hotspots_db")


def query_postgres_hotspots(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[list[dict[str, Any]]]:
    """
    Executes spatial bounding-box and temporal query against PostgreSQL 18.
    Returns:
        - list[dict]: Clean records matching TEAM_FIELD_MAP keys when query succeeds.
        - None: If database is unreachable or psycopg is not installed, triggering safe fallback.
    """
    try:
        import psycopg
    except ImportError:
        logger.debug("psycopg is not installed in current environment; using stub engine")
        return None

    if min_lon > max_lon:
        min_lon, max_lon = max_lon, min_lon
    if min_lat > max_lat:
        min_lat, max_lat = max_lat, min_lat

    start_str = (start_date or "2000-01-01")[:10]
    end_str = (end_date or "2099-12-31")[:10]

    sql = """
    SELECT
        datetime_utc,
        satellite,
        lat,
        lon,
        temp_1,
        temp_2,
        pixel_area_km2,
        frp,
        confidence,
        type,
        daynight,
        analysis_metrics
    FROM hotspots
    WHERE lon >= %s AND lon <= %s
      AND lat >= %s AND lat <= %s
      AND datetime_utc >= %s AND datetime_utc <= %s
    ORDER BY datetime_utc ASC;
    """

    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        min_lon,
                        max_lon,
                        min_lat,
                        max_lat,
                        f"{start_str}T00:00:00Z",
                        f"{end_str}T23:59:59Z",
                    ),
                )
                rows = cur.fetchall()
                results: list[dict[str, Any]] = []
                for r in rows:
                    dt = r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0])
                    metrics = r[11] if isinstance(r[11], dict) else json.loads(r[11]) if r[11] else {}
                    results.append(
                        {
                            "datetime_utc": dt,
                            "satellite": str(r[1]),
                            "lat": float(r[2]),
                            "lon": float(r[3]),
                            "temp_1": float(r[4]) if r[4] is not None else None,
                            "temp_2": float(r[5]) if r[5] is not None else None,
                            "pixel_area_km2": float(r[6]) if r[6] is not None else None,
                            "frp": float(r[7]),
                            "confidence": str(r[8]),
                            "type": int(r[9]) if r[9] is not None else None,
                            "daynight": str(r[10]) if r[10] is not None else None,
                            "analysis_metrics": metrics,
                        }
                    )
                logger.info(f"Retrieved {len(results)} records from PostgreSQL 18")
                return results
    except Exception as e:
        logger.warning(f"PostgreSQL query failed ({e}); falling back gracefully to stub generator")
        return None
