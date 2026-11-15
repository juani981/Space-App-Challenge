import math
import statistics
from datetime import datetime
from typing import Any, Literal
from team_contract import UnifiedHotspot, MonthlyCalendarCell

HarmonizationMode = Literal["raw", "area_weighted", "deduplicated"]

# Standard reference footprints in km2
FOOTPRINT_MODIS_KM2 = 1.0
FOOTPRINT_VIIRS_375M_KM2 = 0.14
FOOTPRINT_VIIRS_750M_KM2 = 0.56


def get_default_pixel_geom(satellite: str) -> float:
    """Returns baseline pixel footprint (km2) by satellite sensor generation."""
    sat = satellite.upper()
    if sat in ("T", "A", "TERRA", "AQUA"):
        return FOOTPRINT_MODIS_KM2
    elif sat in ("N", "SNPP", "S-NPP"):
        return FOOTPRINT_VIIRS_750M_KM2
    else:  # N20, N21, NOAA-20, NOAA-21
        return FOOTPRINT_VIIRS_375M_KM2


def apply_harmonization(
    hotspots: list[UnifiedHotspot],
    mode: HarmonizationMode = "area_weighted",
) -> list[UnifiedHotspot]:
    """
    Applies the selected scientific harmonization algorithm to raw hotspot detections:
    - 'raw': Passthrough with standard metrics audit.
    - 'area_weighted': Normalized by pixel footprint (1.0 km2 MODIS vs 0.14 km2 VIIRS)
      to avoid sensor bias when comparing multi-decadal fire frequency.
    - 'deduplicated': Space-time clustering (~1.5 km and +/- 6h) that consolidates
      overlapping MODIS and VIIRS passes into singular physical fire events.
    """
    if not hotspots:
        return []

    if mode == "raw":
        return _apply_raw_mode(hotspots)
    elif mode == "area_weighted":
        return _apply_area_weighted_mode(hotspots)
    elif mode == "deduplicated":
        return _apply_deduplicated_mode(hotspots)
    else:
        return _apply_area_weighted_mode(hotspots)


def _apply_raw_mode(hotspots: list[UnifiedHotspot]) -> list[UnifiedHotspot]:
    result: list[UnifiedHotspot] = []
    for hs in hotspots:
        geom = hs.pixel_geom if hs.pixel_geom is not None else get_default_pixel_geom(hs.satellite)
        metrics = {
            "harmonization_mode": "raw",
            "harmonization_factor": 1.0,
            "effective_area_km2": round(geom, 3),
            "calibrated_frp": round(hs.frp, 1),
            "equivalent_count": 1.0,
            "is_cluster": False,
        }
        updated = hs.model_copy(update={"analysis_metrics": metrics, "pixel_geom": geom})
        result.append(updated)
    return result


def _apply_area_weighted_mode(hotspots: list[UnifiedHotspot]) -> list[UnifiedHotspot]:
    result: list[UnifiedHotspot] = []
    for hs in hotspots:
        geom = hs.pixel_geom if hs.pixel_geom is not None else get_default_pixel_geom(hs.satellite)
        # Weight represents the fraction of 1 km2 reference footprint
        # A 0.14 km2 VIIRS pixel counts as 0.14 of a standard 1 km2 MODIS detection
        weight = min(max(geom / FOOTPRINT_MODIS_KM2, 0.05), 1.5)
        calibrated_frp = round(hs.frp * math.sqrt(weight), 1)

        metrics = {
            "harmonization_mode": "area_weighted",
            "harmonization_factor": round(weight, 3),
            "effective_area_km2": round(geom, 3),
            "calibrated_frp": calibrated_frp,
            "equivalent_count": round(weight, 3),
            "reference_sensor": "MODIS_1KM_BASELINE",
            "is_cluster": False,
        }
        updated = hs.model_copy(update={"analysis_metrics": metrics, "pixel_geom": geom})
        result.append(updated)
    return result


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance in kilometers."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * r * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def _parse_iso_ts(dt_str: str) -> float:
    """Parses ISO datetime string into epoch seconds."""
    try:
        clean = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean).timestamp()
    except Exception:
        return 0.0


def _apply_deduplicated_mode(
    hotspots: list[UnifiedHotspot],
    max_distance_km: float = 1.8,
    max_time_diff_hours: float = 6.0,
) -> list[UnifiedHotspot]:
    """
    Consolidates spatial-temporal clusters into single harmonized fire detections.
    Prioritizes highest-resolution sensor (VIIRS 375m) for geolocation coordinates.
    """
    if not hotspots:
        return []

    n = len(hotspots)
    visited = [False] * n
    clusters: list[list[int]] = []

    timestamps = [_parse_iso_ts(hs.datetime_utc) for hs in hotspots]
    max_time_diff_sec = max_time_diff_hours * 3600.0

    for i in range(n):
        if visited[i]:
            continue
        cluster = [i]
        visited[i] = True

        for j in range(i + 1, n):
            if visited[j]:
                continue
            time_diff = abs(timestamps[i] - timestamps[j])
            if time_diff <= max_time_diff_sec:
                dist = _haversine_km(hotspots[i].lat, hotspots[i].lon, hotspots[j].lat, hotspots[j].lon)
                if dist <= max_distance_km:
                    visited[j] = True
                    cluster.append(j)

        clusters.append(cluster)

    result: list[UnifiedHotspot] = []
    cluster_idx = 1

    for c in clusters:
        cluster_members = [hotspots[idx] for idx in c]

        # Choose best representative member: highest resolution (smallest pixel_geom)
        # or highest FRP
        def sort_key(hs: UnifiedHotspot):
            geom = hs.pixel_geom if hs.pixel_geom is not None else get_default_pixel_geom(hs.satellite)
            return (geom, -hs.frp)

        best_hs = sorted(cluster_members, key=sort_key)[0]
        satellites_seen = sorted(list({hs.satellite for hs in cluster_members}))
        total_frp = round(sum(hs.frp for hs in cluster_members), 1)
        peak_frp = max(hs.frp for hs in cluster_members)
        geom = best_hs.pixel_geom if best_hs.pixel_geom is not None else get_default_pixel_geom(best_hs.satellite)

        metrics = {
            "harmonization_mode": "deduplicated",
            "cluster_id": f"CLUS-{cluster_idx:04d}",
            "merged_count": len(cluster_members),
            "satellites_involved": satellites_seen,
            "peak_frp": peak_frp,
            "calibrated_frp": total_frp,
            "harmonization_factor": round(1.0 / len(cluster_members), 3),
            "effective_area_km2": round(geom, 3),
            "is_cluster": len(cluster_members) > 1,
        }

        consolidated = best_hs.model_copy(
            update={
                "frp": peak_frp,
                "pixel_geom": geom,
                "analysis_metrics": metrics,
            }
        )
        result.append(consolidated)
        cluster_idx += 1

    return result


def compute_monthly_calendar_matrix(
    all_historical_hotspots: list[UnifiedHotspot],
    start_year: int = 2001,
    end_year: int = 2026,
) -> list[MonthlyCalendarCell]:
    """
    Computes a Year x Month matrix of Burning Activity cells:
    - Aggregates harmonized count and FRP per month/year.
    - Computes multi-year historical median for each month (1..12).
    - Computes anomaly percentage: ((count - median) / median) * 100.
    - Classifies severity: 'low' | 'normal' | 'elevated' | 'extreme'.
    """
    # 1. Bucket by (year, month)
    counts: dict[tuple[int, int], int] = {}
    frp_totals: dict[tuple[int, int], float] = {}

    for hs in all_historical_hotspots:
        try:
            dt = datetime.fromisoformat(hs.datetime_utc.replace("Z", "+00:00"))
            y, m = dt.year, dt.month
            if start_year <= y <= end_year:
                counts[(y, m)] = counts.get((y, m), 0) + 1
                frp_totals[(y, m)] = frp_totals.get((y, m), 0.0) + hs.frp
        except Exception:
            continue

    # 2. Compute historical median for each month (1..12) across all evaluated years
    month_historical_series: dict[int, list[int]] = {m: [] for m in range(1, 13)}
    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            val = counts.get((y, m), 0)
            month_historical_series[m].append(val)

    monthly_medians: dict[int, float] = {}
    for m in range(1, 13):
        vals = month_historical_series[m]
        monthly_medians[m] = float(statistics.median(vals)) if vals else 0.0

    # 3. Build MonthlyCalendarCell for each year and month
    cells: list[MonthlyCalendarCell] = []
    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            cnt = counts.get((y, m), 0)
            frp_sum = round(frp_totals.get((y, m), 0.0), 1)
            med = monthly_medians[m]

            if med > 0:
                anomaly_pct = round(((cnt - med) / med) * 100.0, 1)
            elif cnt > 0:
                anomaly_pct = 100.0
            else:
                anomaly_pct = 0.0

            if anomaly_pct < -25.0:
                severity = "low"
            elif anomaly_pct <= 25.0:
                severity = "normal"
            elif anomaly_pct <= 100.0:
                severity = "elevated"
            else:
                severity = "extreme"

            cells.append(
                MonthlyCalendarCell(
                    year=y,
                    month=m,
                    count=cnt,
                    historical_median=round(med, 1),
                    anomaly_pct=anomaly_pct,
                    severity=severity,
                    harmonized_frp=frp_sum,
                )
            )

    return cells


def export_hotspots_csv(hotspots: list[UnifiedHotspot], calibration_mode: str = "area_weighted") -> str:
    """
    Exports a list of harmonized hotspots to RFC-4180 compliant CSV format,
    including the 10 canonical concepts plus scientific harmonization columns.
    """
    headers = [
        "datetime_utc",
        "satellite",
        "lat",
        "lon",
        "temp_1_k",
        "temp_2_k",
        "pixel_geom_km2",
        "frp_mw",
        "confidence",
        "fire_type",
        "day_night",
        "harmonization_mode",
        "harmonization_factor",
        "effective_area_km2",
        "calibrated_frp_mw",
        "is_cluster",
        "cluster_id",
    ]
    lines = [",".join(headers)]

    for hs in hotspots:
        metrics = hs.analysis_metrics or {}
        row = [
            hs.datetime_utc,
            hs.satellite,
            f"{hs.lat:.5f}",
            f"{hs.lon:.5f}",
            f"{hs.temp_1:.1f}" if hs.temp_1 is not None else "",
            f"{hs.temp_2:.1f}" if hs.temp_2 is not None else "",
            f"{hs.pixel_geom:.2f}" if hs.pixel_geom is not None else "",
            f"{hs.frp:.1f}",
            hs.confidence,
            str(hs.fire_type) if hs.fire_type is not None else "",
            hs.day_night or "",
            str(metrics.get("harmonization_mode", calibration_mode)),
            str(metrics.get("harmonization_factor", "1.0")),
            str(metrics.get("effective_area_km2", hs.pixel_geom or "")),
            str(metrics.get("calibrated_frp", hs.frp)),
            str(metrics.get("is_cluster", False)),
            str(metrics.get("cluster_id", "")),
        ]
        lines.append(",".join(row))

    return "\n".join(lines)
