import type { CalibrationMode, MonthlyCalendarCell, UnifiedHotspot } from '../../services/apiClient';
import type { Language, LocalizedText } from '../../i18n/LanguageContext';

/**
 * Context passed automatically to every visualization module's `resolveData(ctx)` adapter.
 * When the database returns new fields inside `selectedHotspot.analysis_metrics` or `calendarCells`,
 * they are immediately accessible here along with the active language (`es` | `en`).
 */
export interface SidePanelVisualizationContext {
  selectedHotspot: UnifiedHotspot | null;
  hotspots: UnifiedHotspot[];
  calendarCells: MonthlyCalendarCell[];
  calibrationMode: CalibrationMode;
  activeYear: number;
  lang: Language;
}

// ---------------------------------------------------------------------------
// 8 STANDARDIZED VISUALIZATION MODULE CONTRACTS
// ---------------------------------------------------------------------------

/** 1. Vertical Bar Series with optional horizontal reference line (e.g. Monthly Count vs Median) */
export interface BarSeriesData {
  bars: Array<{
    label: string;
    value: number;
    baseline?: number;
    severity?: 'low' | 'normal' | 'elevated' | 'extreme';
  }>;
  unit?: string;
  baselineLabel?: string;
}

/** 2. Frequency Distribution Histogram (e.g. FRP MW bins or Brightness Temp K bins) */
export interface HistogramData {
  bins: Array<{
    label: string;
    count: number;
    highlight?: boolean;
  }>;
  unit?: string;
  activeValueLabel?: string;
}

/** 3. Statistical Box / Quantile Range [Min, P25, Median, P75, Max] + current point marker */
export interface QuantileBandData {
  min: number;
  p25: number;
  median: number;
  p75: number;
  max: number;
  current: number | null;
  unit?: string;
}

/** 4. Side-by-Side A vs B Comparison (e.g. Raw Sensor Value vs Harmonized Value) */
export interface DualCompareData {
  leftLabel: string;
  leftValue: number;
  rightLabel: string;
  rightValue: number;
  unit?: string;
  caption?: string;
}

/** 5. 100% Stacked Horizontal Proportion Bar (e.g. Share by Satellite Generation G1-G4 or Day/Night) */
export interface StackedShareData {
  segments: Array<{
    label: string;
    value: number;
    color: string;
  }>;
  unit?: string;
}

/** 6. Threshold / Severity Gauge Meter (e.g. Anomaly Index % or Calibration Confidence) */
export interface GaugeMeterData {
  value: number;
  min: number;
  max: number;
  unit?: string;
  statusLabel?: string;
  thresholds?: {
    warn: number;
    danger: number;
  };
}

/** 7. Continuous SVG Sparkline / Time-Series Curve (e.g. Multi-Year or Diurnal Evolution) */
export interface SparklineTrendData {
  points: Array<{
    label: string;
    value: number;
  }>;
  unit?: string;
  highlightIndex?: number;
}

/** 8. Structured Key-Value / Audit Telemetry Grid */
export interface KeyValueTableData {
  rows: Array<{
    label: string;
    value: string | number;
    accent?: boolean;
  }>;
}

export type VisualizationSlotSpec =
  | {
      id: string;
      title: LocalizedText;
      subtitle?: LocalizedText;
      enabled: boolean;
      kind: 'bar_series';
      resolveData: (ctx: SidePanelVisualizationContext) => BarSeriesData | null;
    }
  | {
      id: string;
      title: LocalizedText;
      subtitle?: LocalizedText;
      enabled: boolean;
      kind: 'histogram';
      resolveData: (ctx: SidePanelVisualizationContext) => HistogramData | null;
    }
  | {
      id: string;
      title: LocalizedText;
      subtitle?: LocalizedText;
      enabled: boolean;
      kind: 'quantile_band';
      resolveData: (ctx: SidePanelVisualizationContext) => QuantileBandData | null;
    }
  | {
      id: string;
      title: LocalizedText;
      subtitle?: LocalizedText;
      enabled: boolean;
      kind: 'dual_compare';
      resolveData: (ctx: SidePanelVisualizationContext) => DualCompareData | null;
    }
  | {
      id: string;
      title: LocalizedText;
      subtitle?: LocalizedText;
      enabled: boolean;
      kind: 'stacked_share';
      resolveData: (ctx: SidePanelVisualizationContext) => StackedShareData | null;
    }
  | {
      id: string;
      title: LocalizedText;
      subtitle?: LocalizedText;
      enabled: boolean;
      kind: 'gauge_meter';
      resolveData: (ctx: SidePanelVisualizationContext) => GaugeMeterData | null;
    }
  | {
      id: string;
      title: LocalizedText;
      subtitle?: LocalizedText;
      enabled: boolean;
      kind: 'sparkline';
      resolveData: (ctx: SidePanelVisualizationContext) => SparklineTrendData | null;
    }
  | {
      id: string;
      title: LocalizedText;
      subtitle?: LocalizedText;
      enabled: boolean;
      kind: 'kv_table';
      resolveData: (ctx: SidePanelVisualizationContext) => KeyValueTableData | null;
    };
