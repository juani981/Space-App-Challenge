export interface AoiBounds {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

/**
 * Mirrors `UnifiedHotspot` in `backend/team_contract.py` and `docs/TEAM_DATA_CONTRACT.md` (10 concepts).
 * Extensible via `analysis_metrics` without altering the core 10 fields.
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
  analysis_metrics?: Record<string, any> | null;
}

export interface MonthlyCalendarCell {
  year: number;
  month: number;
  count: number;
  historical_median: number;
  anomaly_pct: number;
  severity: 'low' | 'normal' | 'elevated' | 'extreme';
  harmonized_frp: number;
}

export interface AoiResponse {
  bounds: [number, number, number, number];
  calibration_mode: string;
  start_date: string;
  end_date: string;
  total_hotspots: number;
  calendar_cells: MonthlyCalendarCell[];
  hotspots: UnifiedHotspot[];
  data_source: string;
  summary: {
    total_detections: number;
    total_frp_mw: number;
    satellites: string[];
    calibration_mode: string;
  };
}

export type CalibrationMode = 'raw' | 'area_weighted' | 'deduplicated';

export interface QueryAoiOptions {
  startDate?: string;
  endDate?: string;
  calibrationMode?: CalibrationMode;
}

/**
 * Single communication interface between Frontend UI and FastAPI Backend.
 * Requests go through Vite's /api proxy -> http://127.0.0.1:8000/api/aoi
 */
export async function fetchAoi(
  bounds: AoiBounds,
  options?: QueryAoiOptions,
): Promise<AoiResponse> {
  const params = new URLSearchParams({
    min_lon: bounds.minLon.toString(),
    min_lat: bounds.minLat.toString(),
    max_lon: bounds.maxLon.toString(),
    max_lat: bounds.maxLat.toString(),
  });

  if (options?.startDate) params.set('start_date', options.startDate);
  if (options?.endDate) params.set('end_date', options.endDate);
  if (options?.calibrationMode) params.set('calibration_mode', options.calibrationMode);

  const response = await fetch(`/api/aoi?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Backend error: ${response.status}`);
  }
  return response.json();
}

/**
 * Generates the direct download URL for the harmonized RFC-4180 CSV export.
 */
export function getExportCsvUrl(
  bounds: AoiBounds,
  options?: QueryAoiOptions,
): string {
  const params = new URLSearchParams({
    min_lon: bounds.minLon.toString(),
    min_lat: bounds.minLat.toString(),
    max_lon: bounds.maxLon.toString(),
    max_lat: bounds.maxLat.toString(),
  });

  if (options?.startDate) params.set('start_date', options.startDate);
  if (options?.endDate) params.set('end_date', options.endDate);
  if (options?.calibrationMode) params.set('calibration_mode', options.calibrationMode);

  return `/api/aoi/export.csv?${params.toString()}`;
}
