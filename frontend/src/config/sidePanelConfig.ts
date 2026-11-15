import type { UnifiedHotspot } from '../services/apiClient';
import { getSatelliteGeneration } from '../utils/satelliteGenerations';
import type { VisualizationSlotSpec } from '../components/visualizations/contracts';

export interface CanonicalAttributeDescriptor {
  key: keyof UnifiedHotspot;
  number: string;
  label: string;
  format: (hs: UnifiedHotspot) => string;
  highlight?: boolean;
  fullWidth?: boolean;
}

// ============================================================================
// 1. DECLARATIVE BASE TELEMETRY CONTRACT (10 Concepts of TEAM_DATA_CONTRACT.md)
// ============================================================================
export const CANONICAL_ATTRIBUTES_CONFIG: CanonicalAttributeDescriptor[] = [
  {
    key: 'datetime_utc',
    number: '1',
    label: '1. Fecha y Hora UTC (datetime_utc)',
    format: (hs) => hs.datetime_utc,
    fullWidth: true,
  },
  {
    key: 'satellite',
    number: '2',
    label: '2. Satélite (satellite)',
    format: (hs) => {
      const gen = getSatelliteGeneration(hs.satellite);
      return `${hs.satellite} (${gen.generation} — ${gen.name})`;
    },
  },
  {
    key: 'day_night',
    number: '10',
    label: '10. Día / Noche (day_night)',
    format: (hs) => (hs.day_night === 'D' ? 'Diurno (D)' : hs.day_night === 'N' ? 'Nocturno (N)' : 'N/A'),
  },
  {
    key: 'lat',
    number: '3a',
    label: '3a. Latitud (lat)',
    format: (hs) => `${hs.lat.toFixed(4)}°`,
  },
  {
    key: 'lon',
    number: '3b',
    label: '3b. Longitud (lon)',
    format: (hs) => `${hs.lon.toFixed(4)}°`,
  },
  {
    key: 'temp_1',
    number: '4',
    label: '4. Temperatura 1 / Brillo (temp_1)',
    format: (hs) => (hs.temp_1 !== null ? `${hs.temp_1.toFixed(1)} K` : 'N/A'),
  },
  {
    key: 'temp_2',
    number: '5',
    label: '5. Temperatura 2 (temp_2)',
    format: (hs) => (hs.temp_2 !== null ? `${hs.temp_2.toFixed(1)} K` : 'N/A'),
  },
  {
    key: 'pixel_geom',
    number: '6',
    label: '6. Geometría Píxel (pixel_geom)',
    format: (hs) => (hs.pixel_geom !== null ? `${hs.pixel_geom.toFixed(2)} km²` : 'N/A'),
  },
  {
    key: 'frp',
    number: '7',
    label: '7. Potencia Radiativa (frp)',
    format: (hs) => `${hs.frp.toFixed(1)} MW`,
    highlight: true,
  },
  {
    key: 'confidence',
    number: '8',
    label: '8. Confianza (confidence)',
    format: (hs) => hs.confidence.toUpperCase(),
  },
  {
    key: 'fire_type',
    number: '9',
    label: '9. Tipo de Anomalía (fire_type)',
    format: (hs) => (hs.fire_type !== null ? `Tipo ${hs.fire_type} (Vegetación)` : 'N/A'),
  },
];

// ============================================================================
// 2. DEVELOPER VISUALIZATION REGISTRY (8 Plug-and-Play Modules)
// Change `enabled: true | false` or swap `kind` ('bar_series' | 'histogram' |
// 'quantile_band' | 'dual_compare' | 'stacked_share' | 'gauge_meter' |
// 'sparkline' | 'kv_table') when the database schema is finalized.
// ============================================================================
const MONTH_LABELS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

export const DEVELOPER_PANEL_VISUALIZATIONS: VisualizationSlotSpec[] = [
  // MODULE 1: BarSeriesWidget — Seasonal Activity vs Historical Median
  {
    id: 'seasonal-anomaly-bars',
    title: 'Actividad Mensual vs. Mediana Histórica',
    subtitle: 'Módulo: bar_series (Conteo armonizado vs P50 multianual)',
    enabled: true,
    kind: 'bar_series',
    resolveData: ({ calendarCells, activeYear }) => {
      const yearCells = calendarCells.filter((c) => c.year === activeYear);
      if (!yearCells.length) return null;
      return {
        unit: 'focos',
        baselineLabel: `Mediana histórica P50 (${activeYear})`,
        bars: MONTH_LABELS.map((label, idx) => {
          const cell = yearCells.find((c) => c.month === idx + 1);
          return {
            label,
            value: cell?.count ?? 0,
            baseline: cell?.historical_median ?? 0,
            severity: cell?.severity ?? 'normal',
          };
        }),
      };
    },
  },

  // MODULE 2: DualSensorCompareWidget — Raw FRP vs Calibrated/Harmonized FRP
  {
    id: 'dual-frp-comparison',
    title: 'Comparativa de Calibración (Crudo vs. Armonizado)',
    subtitle: 'Módulo: dual_compare (Efecto del factor de armonización en el foco)',
    enabled: true,
    kind: 'dual_compare',
    resolveData: ({ selectedHotspot }) => {
      if (!selectedHotspot) return null;
      const metrics = selectedHotspot.analysis_metrics ?? {};
      const rawFrp = Number(metrics.raw_frp ?? selectedHotspot.frp);
      const calFrp = Number(metrics.calibrated_frp ?? selectedHotspot.frp);
      return {
        leftLabel: 'FRP Sensor Crudo',
        leftValue: rawFrp,
        rightLabel: 'FRP Armonizado',
        rightValue: calFrp,
        unit: 'MW',
        caption: `Factor aplicado: ${metrics.harmonization_factor ?? 1.0}x (${selectedHotspot.satellite})`,
      };
    },
  },

  // MODULE 3: QuantileBoxWidget — Position of Selected Hotspot in AOI FRP Distribution
  {
    id: 'frp-quantile-box',
    title: 'Posición en Distribución de Cuantiles (CDF / BoxPlot)',
    subtitle: 'Módulo: quantile_band ([Mín, P25, Mediana, P75, Máx] en el AOI)',
    enabled: true,
    kind: 'quantile_band',
    resolveData: ({ hotspots, selectedHotspot }) => {
      if (!hotspots.length) return null;
      const sorted = [...hotspots.map((h) => h.frp)].sort((a, b) => a - b);
      const q = (p: number) => sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
      return {
        min: sorted[0],
        p25: q(0.25),
        median: q(0.5),
        p75: q(0.75),
        max: sorted[sorted.length - 1],
        current: selectedHotspot?.frp ?? null,
        unit: 'MW',
      };
    },
  },

  // MODULE 4: HistogramWidget — FRP Intensity Distribution across AOI
  {
    id: 'frp-distribution-histogram',
    title: 'Histograma de Potencia Radiativa (FRP)',
    subtitle: 'Módulo: histogram (Resalta el rango donde cae el foco activo)',
    enabled: true,
    kind: 'histogram',
    resolveData: ({ hotspots, selectedHotspot }) => {
      if (!hotspots.length) return null;
      const ranges = [
        { label: '<20 MW', min: 0, max: 20 },
        { label: '20-50', min: 20, max: 50 },
        { label: '50-90', min: 50, max: 90 },
        { label: '>90 MW', min: 90, max: Infinity },
      ];
      const curFrp = selectedHotspot?.frp ?? -1;
      return {
        unit: 'focos',
        activeValueLabel: selectedHotspot ? `${selectedHotspot.frp.toFixed(1)} MW` : undefined,
        bins: ranges.map((r) => ({
          label: r.label,
          count: hotspots.filter((h) => h.frp >= r.min && h.frp < r.max).length,
          highlight: curFrp >= r.min && curFrp < r.max,
        })),
      };
    },
  },

  // MODULE 5: StackedShareWidget — Breakdown by Satellite Generation G1-G4
  {
    id: 'generation-stacked-share',
    title: 'Proporción por Generación Satelital (G1–G4)',
    subtitle: 'Módulo: stacked_share (Aporte relativo por familia de sensores)',
    enabled: true,
    kind: 'stacked_share',
    resolveData: ({ hotspots }) => {
      if (!hotspots.length) return null;
      const counts = { G1: 0, G2: 0, G3: 0, G4: 0 };
      hotspots.forEach((h) => {
        const g = getSatelliteGeneration(h.satellite).generation;
        counts[g] = (counts[g] ?? 0) + 1;
      });
      return {
        segments: [
          { label: 'G1 MODIS (1000m)', value: counts.G1, color: '#9333ea' },
          { label: 'G2 S-NPP (750m)', value: counts.G2, color: '#2563eb' },
          { label: 'G3 NOAA-20 (375m)', value: counts.G3, color: '#ea580c' },
          { label: 'G4 NOAA-21 (375m)', value: counts.G4, color: '#dc2626' },
        ],
      };
    },
  },

  // MODULE 6: GaugeMeterWidget — Thermal Gradient / Brightness Intensity Gauge (Ready to toggle)
  {
    id: 'thermal-gradient-gauge',
    title: 'Medidor de Diferencial Térmico (ΔT = T1 - T2)',
    subtitle: 'Módulo: gauge_meter (Intensidad térmica respecto a fondo)',
    enabled: false, // <-- Cambia a `true` en 1 línea si el equipo entrega índices o umbrales
    kind: 'gauge_meter',
    resolveData: ({ selectedHotspot }) => {
      if (!selectedHotspot || selectedHotspot.temp_1 === null || selectedHotspot.temp_2 === null) {
        return null;
      }
      const deltaT = Math.max(0, selectedHotspot.temp_1 - selectedHotspot.temp_2);
      return {
        value: deltaT,
        min: 0,
        max: 80,
        unit: 'K',
        statusLabel: deltaT >= 45 ? 'Anomalía Intensa' : deltaT >= 25 ? 'Moderada' : 'Baja',
        thresholds: { warn: 25, danger: 45 },
      };
    },
  },

  // MODULE 7: SparklineTrendWidget — Multi-Year Historical Trend for Active Month (Ready to toggle)
  {
    id: 'multiyear-month-sparkline',
    title: 'Tendencia Histórica Multianual (2001–2026)',
    subtitle: 'Módulo: sparkline (Evolución interanual para el mes activo)',
    enabled: false, // <-- Cambia a `true` en 1 línea si el equipo entrega series largas
    kind: 'sparkline',
    resolveData: ({ calendarCells, activeYear }) => {
      const augustCells = calendarCells.filter((c) => c.month === 8);
      if (augustCells.length < 2) return null;
      return {
        unit: 'focos',
        highlightIndex: augustCells.findIndex((c) => c.year === activeYear),
        points: augustCells.map((c) => ({
          label: String(c.year),
          value: c.count,
        })),
      };
    },
  },

  // MODULE 8: KeyValueTableWidget — Complete Harmonization & Extra DB Metrics Audit Table
  {
    id: 'harmonization-audit-table',
    title: 'Parámetros de Armonización y Datos Extra de BD',
    subtitle: 'Módulo: kv_table (Absorbe automáticamente nuevas columnas de analysis_metrics)',
    enabled: true,
    kind: 'kv_table',
    resolveData: ({ selectedHotspot, calibrationMode }) => {
      if (!selectedHotspot) return null;
      const m = selectedHotspot.analysis_metrics ?? {};
      const baseRows = [
        { label: 'Modo de Calibración', value: String(m.harmonization_mode ?? calibrationMode) },
        { label: 'Factor de Ponderación Espacial', value: `${m.harmonization_factor ?? 1.0}x` },
        {
          label: 'Área Efectiva del Píxel',
          value: `${m.effective_area_km2 ?? selectedHotspot.pixel_geom ?? 1.0} km²`,
        },
        {
          label: '¿Foco Fusionado (Cluster)?',
          value: m.is_cluster ? `Sí (${m.merged_count} detecciones)` : 'No (Individual)',
        },
      ];

      // Cualquier clave nueva que devuelva la BD del otro equipo se agrega sola aquí:
      const knownKeys = new Set([
        'harmonization_mode',
        'harmonization_factor',
        'effective_area_km2',
        'calibrated_frp',
        'raw_frp',
        'is_cluster',
        'merged_count',
      ]);

      const dynamicRows = Object.entries(m)
        .filter(([k]) => !knownKeys.has(k))
        .map(([k, v]) => ({
          label: k,
          value: Array.isArray(v) ? v.join(', ') : String(v),
          accent: true,
        }));

      return { rows: [...baseRows, ...dynamicRows] };
    },
  },
];
