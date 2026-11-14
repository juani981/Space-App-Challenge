export interface AoiBounds {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

export interface AoiResponse {
  bounds: [number, number, number, number];
  message: string;
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
