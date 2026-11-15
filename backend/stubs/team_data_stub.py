"""
DISPOSABLE STUB MODULE — CAN BE REPLACED ONCE TEAMMATES DELIVER REAL DUCKDB / PARQUET DATA.

Simulates raw records returned by Teammates 1 & 2's hypothetical dataset/API
inside a requested bounding box, using the provisional keys from `TEAM_FIELD_MAP`.
Uses a deterministic spatial tile grid so that panning/zooming across the world map
lazy-loads new points seamlessly while keeping existing points anchored at fixed coordinates.
"""

import hashlib
import math
import random
from typing import Any, Optional
from team_contract import TEAM_FIELD_MAP, DATA_SOURCE_MODE, parse_team_record, UnifiedHotspot
from harmonization import (
    apply_harmonization,
    compute_monthly_calendar_matrix,
    HarmonizationMode,
    FOOTPRINT_MODIS_KM2,
    FOOTPRINT_VIIRS_375M_KM2,
    FOOTPRINT_VIIRS_750M_KM2,
)


def get_hotspot_dataset(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    calibration_mode: HarmonizationMode = "area_weighted",
) -> dict[str, Any]:
    """
    Unified ingestion gateway that checks DATA_SOURCE_MODE:
    - If 'stub': Generates deterministic spatial-tile multi-temporal records from the stub engine.
    - If 'database': Invokes the team database / DuckDB connector.
    Then applies the selected scientific harmonization algorithm and builds calendar cells.
    """
    if DATA_SOURCE_MODE == "database":
        raw_rows = _query_database(min_lon, min_lat, max_lon, max_lat, start_date, end_date)
    else:
        raw_rows = generate_stub_team_rows(
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
            start_date=start_date,
            end_date=end_date,
        )

    # 1. Translate raw rows to canonical UnifiedHotspot models (10 concepts)
    all_hotspots = [parse_team_record(r) for r in raw_rows]

    # 2. Compute the 2001-2026 multi-year monthly calendar matrix before date slicing
    # so historical medians and anomalies stay statistically sound across 25 years
    calendar_cells = compute_monthly_calendar_matrix(all_hotspots, start_year=2001, end_year=2026)

    # 3. Filter hotspots by the active date range if provided (defaults to recent 2024 range if not set)
    filtered_hotspots = _filter_by_date_range(all_hotspots, start_date, end_date)

    # 4. Apply scientific harmonization algorithm to the active hotspots
    harmonized_hotspots = apply_harmonization(filtered_hotspots, mode=calibration_mode)

    return {
        "bounds": [min_lon, min_lat, max_lon, max_lat],
        "calibration_mode": calibration_mode,
        "start_date": start_date or "2024-01-01",
        "end_date": end_date or "2024-12-31",
        "total_hotspots": len(harmonized_hotspots),
        "calendar_cells": [c.model_dump() for c in calendar_cells],
        "hotspots": [h.model_dump() for h in harmonized_hotspots],
        "data_source": DATA_SOURCE_MODE,
        "summary": {
            "total_detections": len(harmonized_hotspots),
            "total_frp_mw": round(sum(h.frp for h in harmonized_hotspots), 1),
            "satellites": sorted(list({h.satellite for h in harmonized_hotspots})),
            "calibration_mode": calibration_mode,
        },
    }


def _filter_by_date_range(
    hotspots: list[UnifiedHotspot],
    start_date: Optional[str],
    end_date: Optional[str],
) -> list[UnifiedHotspot]:
    if not start_date and not end_date:
        start_date = "2024-01-01"
        end_date = "2024-12-31"

    start_str = (start_date or "2000-01-01")[:10]
    end_str = (end_date or "2099-12-31")[:10]

    filtered: list[UnifiedHotspot] = []
    for hs in hotspots:
        hs_date = hs.datetime_utc[:10]
        if start_str <= hs_date <= end_str:
            filtered.append(hs)
    return filtered


def _query_database(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    start_date: Optional[str],
    end_date: Optional[str],
) -> list[dict[str, Any]]:
    """
    Placeholder adapter for real database / DuckDB integration.
    Once Teammates 1 & 2 deliver their DuckDB file or Parquet tables,
    this function executes the spatial-temporal SQL query.
    """
    return generate_stub_team_rows(min_lon, min_lat, max_lon, max_lat, start_date, end_date)


def generate_stub_team_rows(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Produces deterministic, spatially anchored multi-year raw rows inside [min_lon, min_lat, max_lon, max_lat]
    by dividing the viewport into fixed geographic grid cells.
    When the user pans across the world map, existing points stay at their exact (lat, lon) coordinates
    while newly exposed grid cells lazy-load seamlessly.
    """
    if min_lon > max_lon:
        min_lon, max_lon = max_lon, min_lon
    if min_lat > max_lat:
        min_lat, max_lat = max_lat, min_lat

    lon_span = max(0.05, max_lon - min_lon)
    lat_span = max(0.05, max_lat - min_lat)

    # Choose a fixed spatial grid resolution (2.0 deg for regional/continental, 0.5 deg for local zoom)
    if max(lon_span, lat_span) <= 2.5:
        grid_step = 0.5
    elif max(lon_span, lat_span) <= 14.0:
        grid_step = 2.0
    else:
        grid_step = 6.0

    start_gx = int(math.floor(min_lon / grid_step))
    end_gx = int(math.floor(max_lon / grid_step))
    start_gy = int(math.floor(min_lat / grid_step))
    end_gy = int(math.floor(max_lat / grid_step))

    tiles: list[tuple[int, int]] = []
    for gx in range(start_gx, end_gx + 1):
        for gy in range(start_gy, end_gy + 1):
            tiles.append((gx, gy))

    # Cap maximum evaluated tiles to keep response under 40ms even at global zoom
    if len(tiles) > 16:
        stride = max(1, len(tiles) // 16)
        tiles = tiles[::stride][:16]

    m = TEAM_FIELD_MAP
    confidences = ["low", "nominal", "high"]
    day_nights = ["D", "N"]

    monthly_weights = {
        1: 2, 2: 2, 3: 3, 4: 4, 5: 6, 6: 8,
        7: 14, 8: 28, 9: 36, 10: 20, 11: 6, 12: 3,
    }

    year_multipliers = {
        2020: 2.2,
        2024: 1.8,
        2013: 0.5,
        2017: 1.3,
    }

    raw_rows: list[dict[str, Any]] = []
    tile_density_scale = max(1, len(tiles))

    for gx, gy in tiles:
        tile_min_lon = gx * grid_step
        tile_max_lon = (gx + 1) * grid_step
        tile_min_lat = gy * grid_step
        tile_max_lat = (gy + 1) * grid_step

        seed_str = f"tile:{grid_step:.2f}:{gx}:{gy}"
        seed = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(seed)

        for year in range(2001, 2027):
            y_mult = year_multipliers.get(year, 1.0)

            available_sats = ["T", "A"]
            if year >= 2012:
                available_sats.append("N")
            if year >= 2017:
                available_sats.append("N20")
            if year >= 2023:
                available_sats.append("N21")

            for month in range(1, 13):
                base_count = monthly_weights[month]
                count = int(round((base_count * y_mult * rng.uniform(0.7, 1.3) * 0.45) / math.sqrt(tile_density_scale)))
                if month in (8, 9) and count < 1:
                    count = 1

                for _ in range(count):
                    sat = rng.choice(available_sats)
                    if sat in ("T", "A"):
                        pixel_geom = FOOTPRINT_MODIS_KM2
                    elif sat == "N":
                        pixel_geom = FOOTPRINT_VIIRS_750M_KM2
                    else:
                        pixel_geom = FOOTPRINT_VIIRS_375M_KM2

                    lat = round(rng.uniform(tile_min_lat, tile_max_lat), 4)
                    lon = round(rng.uniform(tile_min_lon, tile_max_lon), 4)
                    day = rng.randint(1, 28)
                    hour = rng.randint(0, 23)
                    minute = rng.randint(0, 59)
                    frp = round(rng.uniform(10.0, 160.0) * (0.8 if sat in ("N20", "N21") else 1.2), 1)

                    if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                        raw_rows.append(
                            {
                                m["datetime_utc"]: f"{year}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00Z",
                                m["satellite"]: sat,
                                m["lat"]: lat,
                                m["lon"]: lon,
                                m["temp_1"]: round(rng.uniform(310.0, 375.0), 1),
                                m["temp_2"]: round(rng.uniform(285.0, 315.0), 1),
                                m["pixel_geom"]: pixel_geom,
                                m["frp"]: frp,
                                m["confidence"]: rng.choice(confidences),
                                m["fire_type"]: 0,
                                m["day_night"]: rng.choice(day_nights),
                            }
                        )

                        # Coincident overpass cluster in Aug/Sep 2024
                        if year == 2024 and month in (8, 9) and rng.random() < 0.35 and len(available_sats) > 2:
                            paired_sat = "N20" if sat != "N20" else "T"
                            paired_geom = FOOTPRINT_VIIRS_375M_KM2 if paired_sat == "N20" else FOOTPRINT_MODIS_KM2
                            offset_lat = round(lat + rng.uniform(-0.008, 0.008), 4)
                            offset_lon = round(lon + rng.uniform(-0.008, 0.008), 4)
                            offset_hour = (hour + rng.randint(1, 3)) % 24

                            if min_lat <= offset_lat <= max_lat and min_lon <= offset_lon <= max_lon:
                                raw_rows.append(
                                    {
                                        m["datetime_utc"]: f"{year}-{month:02d}-{day:02d}T{offset_hour:02d}:{minute:02d}:00Z",
                                        m["satellite"]: paired_sat,
                                        m["lat"]: offset_lat,
                                        m["lon"]: offset_lon,
                                        m["temp_1"]: round(rng.uniform(320.0, 380.0), 1),
                                        m["temp_2"]: round(rng.uniform(290.0, 320.0), 1),
                                        m["pixel_geom"]: paired_geom,
                                        m["frp"]: round(frp * rng.uniform(0.85, 1.15), 1),
                                        m["confidence"]: "high",
                                        m["fire_type"]: 0,
                                        m["day_night"]: "D" if 10 <= offset_hour <= 18 else "N",
                                    }
                                )

    return raw_rows
