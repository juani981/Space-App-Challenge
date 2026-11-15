from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stubs.team_data_stub import generate_stub_team_rows
from team_contract import UnifiedHotspot, parse_team_record

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.get("/api/aoi")
def inspect_aoi(
    min_lon: float = -65.0,
    min_lat: float = -35.0,
    max_lon: float = -58.0,
    max_lat: float = -29.0,
):
    # 1. Fetch raw rows from the disposable stub (later replaced by real team dataset)
    raw_team_rows = generate_stub_team_rows(min_lon, min_lat, max_lon, max_lat)

    # 2. Translate every raw row through our single provisional contract
    hotspots: list[UnifiedHotspot] = [parse_team_record(row) for row in raw_team_rows]

    return {
        "bounds": [min_lon, min_lat, max_lon, max_lat],
        "message": f"Loaded {len(hotspots)} stub hotspots via team_contract",
        "hotspots": hotspots,
    }
