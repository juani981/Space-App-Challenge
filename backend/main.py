from typing import Literal, Optional
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from stubs.team_data_stub import get_hotspot_dataset
from harmonization import export_hotspots_csv, apply_harmonization
from team_contract import parse_team_record
from cell_month_service import (
    DatabaseUnavailableError,
    database_health,
    prepare_cell_month_csv_stream,
    query_cell_month_aoi,
)

app = FastAPI(
    title="Harmonized Hotspots API — NASA Space Apps Challenge 2026",
    description="Scientific harmonization between MODIS and VIIRS satellite active fire detections",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DatabaseUnavailableError)
def database_unavailable_handler(_request, exc: DatabaseUnavailableError):
    """La base armonizada no responde: 503 explícito (nunca datos sintéticos en modo `database`)."""
    return JSONResponse(status_code=503, content={"error": "database_unavailable", "detail": str(exc)})


@app.get("/")
def health_check():
    return {"status": "ok", "service": "Harmonized Hotspots API (Ruta 1)"}


@app.get("/api/health")
def api_health():
    """Estado de la conexión: modo de datos, versión de la tabla armonizada y filas estimadas.
    Devuelve 503 si el modo es `database` y la base no responde o está vacía."""
    return database_health()


@app.get("/api/aoi")
def inspect_aoi(
    min_lon: float = Query(-65.0, description="Minimum longitude"),
    min_lat: float = Query(-35.0, description="Minimum latitude"),
    max_lon: float = Query(-58.0, description="Maximum longitude"),
    max_lat: float = Query(-29.0, description="Maximum latitude"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    calibration_mode: str = Query("area_weighted", description="Calibration mode: raw, area_weighted, deduplicated"),
):
    """
    Returns harmonized hotspot records and multi-year calendar matrix within the specified AOI.
    Supports calibration modes: 'raw', 'area_weighted', 'deduplicated'.
    """
    valid_modes = {"raw", "area_weighted", "deduplicated"}
    mode = calibration_mode if calibration_mode in valid_modes else "area_weighted"

    result = get_hotspot_dataset(
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
        start_date=start_date,
        end_date=end_date,
        calibration_mode=mode,  # type: ignore
    )
    return result


@app.get("/api/aoi/export.csv")
def export_aoi_csv(
    min_lon: float = Query(-65.0, description="Minimum longitude"),
    min_lat: float = Query(-35.0, description="Minimum latitude"),
    max_lon: float = Query(-58.0, description="Maximum longitude"),
    max_lat: float = Query(-29.0, description="Maximum latitude"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    calibration_mode: str = Query("area_weighted", description="Calibration mode: raw, area_weighted, deduplicated"),
):
    """
    Exports harmonized hotspots for the selected AOI as a downloadable CSV file.
    Complies with RFC-4180 and includes all 10 canonical concepts plus scientific harmonization metrics.
    """
    valid_modes = {"raw", "area_weighted", "deduplicated"}
    mode = calibration_mode if calibration_mode in valid_modes else "area_weighted"

    dataset = get_hotspot_dataset(
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
        start_date=start_date,
        end_date=end_date,
        calibration_mode=mode,  # type: ignore
    )

    # Reconstruct UnifiedHotspot models from the harmonized dicts
    hotspots = [
        parse_team_record(
            {
                "datetime_utc": h["datetime_utc"],
                "satellite": h["satellite"],
                "lat": h["lat"],
                "lon": h["lon"],
                "temp_1": h.get("temp_1"),
                "temp_2": h.get("temp_2"),
                "pixel_area_km2": h.get("pixel_geom"),
                "frp": h["frp"],
                "confidence": h["confidence"],
                "type": h.get("fire_type"),
                "daynight": h.get("day_night"),
                "analysis_metrics": h.get("analysis_metrics"),
            }
        )
        for h in dataset["hotspots"]
    ]

    csv_content = export_hotspots_csv(hotspots, calibration_mode=mode)
    filename = f"harmonized_hotspots_{mode}_{dataset['start_date']}_{dataset['end_date']}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/cell-month/aoi")
def inspect_cell_month_aoi(
    min_lon: float = Query(-65.0, description="Minimum longitude"),
    min_lat: float = Query(-35.0, description="Minimum latitude"),
    max_lon: float = Query(-58.0, description="Maximum longitude"),
    max_lat: float = Query(-29.0, description="Maximum latitude"),
    start_date: Optional[str] = Query(None, description="Start month/date (YYYY-MM or YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End month/date (YYYY-MM or YYYY-MM-DD)"),
    metric: Literal["n_eq", "f_eq"] = Query("n_eq", description="Anomaly metric: n_eq or f_eq"),
):
    """
    Queries the `harmonized.cell_month` (0.25° x 0.25°) pipeline for the selected AOI.
    Computes multi-year percentile & robust log1p-MAD anomalies over 2012-2026 while
    slicing active grid cells and KPIs to `[start_date, end_date]`.
    """
    return query_cell_month_aoi(
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
        start_date=start_date,
        end_date=end_date,
        metric=metric,
    )


@app.get("/api/cell-month/export.csv")
def export_cell_month_aoi_csv(
    min_lon: float = Query(-65.0, description="Minimum longitude"),
    min_lat: float = Query(-35.0, description="Minimum latitude"),
    max_lon: float = Query(-58.0, description="Maximum longitude"),
    max_lat: float = Query(-29.0, description="Maximum latitude"),
    start_date: Optional[str] = Query(None, description="Start month/date (YYYY-MM or YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End month/date (YYYY-MM or YYYY-MM-DD)"),
):
    """
    Streams `harmonized.cell_month` monthly rows inside the AOI and date range (Option 1:
    0.25° center-of-cell selection), enforcing the 1,000,000-row safety cap.
    """
    try:
        win_start, win_end, row_count, csv_stream = prepare_cell_month_csv_stream(
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    filename = f"harmonized_cell_month_{win_start.isoformat()}_{win_end.isoformat()}.csv"
    return StreamingResponse(
        csv_stream,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Row-Count": str(row_count),
            "X-Cell-Selection-Policy": "0.25deg cell center inside AOI",
        },
    )
