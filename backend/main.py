from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    return {
        "bounds": [min_lon, min_lat, max_lon, max_lat],
        "message": "AOI received by backend",
    }
