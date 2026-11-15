"""
DISPOSABLE STUB MODULE — DELETE THIS FOLDER (`backend/stubs/`) ONCE TEAMMATES DELIVER REAL DATA.

Simulates raw records returned by Teammates 1 & 2's hypothetical dataset/API
inside a requested bounding box, using the provisional keys from `TEAM_FIELD_MAP`.
"""

import hashlib
import random
from typing import Any
from team_contract import TEAM_FIELD_MAP


def generate_stub_team_rows(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    count: int = 12,
) -> list[dict[str, Any]]:
    """
    Produces `count` deterministic fake rows inside [min_lon, min_lat, max_lon, max_lat]
    structured with the exact keys defined in TEAM_FIELD_MAP.
    """
    seed_str = f"{min_lon:.3f},{min_lat:.3f},{max_lon:.3f},{max_lat:.3f}"
    seed = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)

    m = TEAM_FIELD_MAP
    satellites = ["T", "A", "N", "N20", "N21"]
    confidences = ["low", "nominal", "high"]
    day_nights = ["D", "N"]

    raw_rows: list[dict[str, Any]] = []
    for i in range(count):
        lat = round(rng.uniform(min_lat, max_lat), 4)
        lon = round(rng.uniform(min_lon, max_lon), 4)
        sat = rng.choice(satellites)
        day = rng.randint(1, 28)
        hour = rng.randint(0, 23)
        minute = rng.randint(0, 59)

        raw_rows.append(
            {
                m["datetime_utc"]: f"2024-08-{day:02d}T{hour:02d}:{minute:02d}:00Z",
                m["satellite"]: sat,
                m["lat"]: lat,
                m["lon"]: lon,
                m["temp_1"]: round(rng.uniform(310.0, 365.0), 1),
                m["temp_2"]: round(rng.uniform(285.0, 310.0), 1),
                m["pixel_geom"]: round(rng.uniform(0.14, 1.2), 2),
                m["frp"]: round(rng.uniform(8.5, 140.0), 1),
                m["confidence"]: rng.choice(confidences),
                m["fire_type"]: 0,
                m["day_night"]: rng.choice(day_nights),
            }
        )

    return raw_rows
