export interface AoiBounds {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

/**
 * Mirrors `UnifiedHotspot` in `backend/team_contract.py` and `docs/TEAM_DATA_CONTRACT.md` (10 concepts).
 */
export interface UnifiedHotspot {
  datetime_utc: string;
  satellite: string;
  lat: number;
  lon: number;
  temp_1: number | null;
  temp_2: number | null;
  pixel_geom: number | null;
  frp: number;
  confidence: string;
  fire_type: number | null;
  day_night: string | null;
}

export interface AoiResponse {
  bounds: [number, number, number, number];
  message: string;
  hotspots: UnifiedHotspot[];
}

/**
 * Single communication interface between Frontend UI and FastAPI Backend.
 * Requests go through Vite's /api proxy -> http://127.0.0.1:8000/api/aoi
 */
export async function fetchAoi(bounds: AoiBounds): Promise<AoiResponse> {
  const params = new URLSearchParams({
    min_lon: bounds.minLon.toString(),
    min_lat: bounds.minLat.toString(),
    max_lon: bounds.maxLon.toString(),
    max_lat: bounds.maxLat.toString(),
  });

  const response = await fetch(`/api/aoi?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Backend error: ${response.status}`);
  }
  return response.json();
}
