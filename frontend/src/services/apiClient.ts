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
  signal?: AbortSignal;
}

function buildAoiSearchParams(
  bounds: AoiBounds,
  extra?: Record<string, string | undefined>,
): URLSearchParams {
  const params = new URLSearchParams({
    min_lon: bounds.minLon.toString(),
    min_lat: bounds.minLat.toString(),
    max_lon: bounds.maxLon.toString(),
    max_lat: bounds.maxLat.toString(),
  });
  if (extra) {
    for (const [k, v] of Object.entries(extra)) {
      if (v !== undefined && v !== '') {
        params.set(k, v);
      }
    }
  }
  return params;
}

/**
 * Single communication interface between Frontend UI and FastAPI Backend.
 * Requests go through Vite's /api proxy -> http://127.0.0.1:8000/api/aoi
 */
export async function fetchAoi(
  bounds: AoiBounds,
  options?: QueryAoiOptions,
): Promise<AoiResponse> {
  const params = buildAoiSearchParams(bounds, {
    start_date: options?.startDate,
    end_date: options?.endDate,
    calibration_mode: options?.calibrationMode,
  });

  const response = await fetch(`/api/aoi?${params.toString()}`, {
    signal: options?.signal,
  });
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
  const params = buildAoiSearchParams(bounds, {
    start_date: options?.startDate,
    end_date: options?.endDate,
    calibration_mode: options?.calibrationMode,
  });

  return `/api/aoi/export.csv?${params.toString()}`;
}

// ============================================================================
// HARMONIZED.CELL_MONTH (0.25° x 0.25°, 2012-2026) CONTRACTS & CLIENT
// Reference: docs/DOCUMENTACION_TABLA_ARMONIZADA.md
// ============================================================================
export type CellMonthMetric = 'n_eq' | 'f_eq';

export interface QualityFlagDecoded {
  bit: number;
  code: string;
  label_es: string;
}

export interface CellMonthAnomalyCell {
  month: string;
  year: number;
  month_num: number;
  n_eq: number;
  f_eq: number;
  frp_density_mw_km2: number;
  quality_flag: number;
  quality_flags_decoded: QualityFlagDecoded[];
  excluded_from_baseline: boolean;
  baseline_years_count: number;
  anomaly_available: boolean;
  unavailable_reason: string | null;
  percentile: number | null;
  severity_class: 'lte_50' | '50_75' | '75_90' | 'gt_90' | 'unavailable';
  is_series_record: boolean;
  z_robust_log1p: number | null;
  ratio_to_median: number | null;
  method_version: string;
}

export interface CellMonthMapCell {
  cell_id: number;
  lat_center: number;
  lon_center: number;
  cell_area_km2: number;
  n_eq: number;
  f_eq: number;
  n_terra: number;
  months_active: number;
  sensors: string[];
  quality_flag: number;
  quality_flags_decoded: QualityFlagDecoded[];
}

export interface CellMonthAoiResponse {
  bounds: [number, number, number, number];
  start_date: string;
  end_date: string;
  metric: CellMonthMetric;
  method_version: string;
  data_source: 'postgres' | 'stub';
  area_region_km2: number;
  pending_confirmations: Record<string, unknown>;
  summary: {
    total_n_eq: number;
    total_f_eq_mw: number;
    frp_density_mw_km2: number;
    active_cells_count: number;
    window_rows_count: number;
    n_terra_separate_series: number;
  };
  calendar_anomalies: CellMonthAnomalyCell[];
  cells: CellMonthMapCell[];
}

export interface QueryCellMonthOptions {
  startDate?: string;
  endDate?: string;
  metric?: CellMonthMetric;
  signal?: AbortSignal;
}

export async function fetchCellMonthAoi(
  bounds: AoiBounds,
  options?: QueryCellMonthOptions,
): Promise<CellMonthAoiResponse> {
  const params = buildAoiSearchParams(bounds, {
    start_date: options?.startDate,
    end_date: options?.endDate,
    metric: options?.metric,
  });

  const response = await fetch(`/api/cell-month/aoi?${params.toString()}`, {
    signal: options?.signal,
  });
  if (!response.ok) {
    throw new Error(`Cell-month backend error: ${response.status}`);
  }
  return response.json();
}

export function getCellMonthExportCsvUrl(
  bounds: AoiBounds,
  options?: Omit<QueryCellMonthOptions, 'signal' | 'metric'>,
): string {
  const params = buildAoiSearchParams(bounds, {
    start_date: options?.startDate,
    end_date: options?.endDate,
  });
  return `/api/cell-month/export.csv?${params.toString()}`;
}
