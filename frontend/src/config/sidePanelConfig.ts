import type { UnifiedHotspot } from '../services/apiClient';
import { getSatelliteGeneration } from '../utils/satelliteGenerations';
import type { VisualizationSlotSpec } from '../components/visualizations/contracts';
import type { Language, LocalizedText } from '../i18n/LanguageContext';
import { TRANSLATIONS } from '../i18n/LanguageContext';

export interface CanonicalAttributeDescriptor {
  key: keyof UnifiedHotspot;
  number: string;
  label: LocalizedText;
  format: (hs: UnifiedHotspot, lang: Language) => string;
  highlight?: boolean;
  fullWidth?: boolean;
}

function formatConfidence(conf: string, lang: Language): string {
  const c = (conf || '').trim().toUpperCase();
  if (c === 'H' || c === 'HIGH' || Number(c) >= 80) {
    return lang === 'es' ? `${c} — Alta (High)` : `${c} — High Confidence`;
  }
  if (c === 'N' || c === 'NOMINAL' || (Number(c) >= 30 && Number(c) < 80)) {
    return lang === 'es' ? `${c} — Nominal` : `${c} — Nominal Confidence`;
  }
  if (c === 'L' || c === 'LOW' || (!Number.isNaN(Number(c)) && Number(c) < 30)) {
    return lang === 'es' ? `${c} — Baja (Low)` : `${c} — Low Confidence`;
  }
  return c;
}

function formatFireType(ft: number | null, lang: Language): string {
  if (ft === null || ft === undefined) return 'N/A';
  const mapEs: Record<number, string> = {
    0: 'Tipo 0 (Incendio de Vegetación Presunto)',
    1: 'Tipo 1 (Volcán Activo)',
    2: 'Tipo 2 (Fuente Terrestre Estática / Industrial)',
    3: 'Tipo 3 (Detección Costera / Offshore)',
  };
  const mapEn: Record<number, string> = {
    0: 'Type 0 (Presumed Vegetation Fire)',
    1: 'Type 1 (Active Volcano)',
    2: 'Type 2 (Static Land Source / Gas Flare)',
    3: 'Type 3 (Offshore Detection)',
  };
  return lang === 'es'
    ? (mapEs[ft] ?? `Tipo ${ft}`)
    : (mapEn[ft] ?? `Type ${ft}`);
}

// ============================================================================
// 1. DECLARATIVE BASE TELEMETRY CONTRACT (10 Concepts of TEAM_DATA_CONTRACT.md)
// Includes full radiometric & remote-sensing technical terminology (ES / EN).
// ============================================================================
export const CANONICAL_ATTRIBUTES_CONFIG: CanonicalAttributeDescriptor[] = [
  {
    key: 'datetime_utc',
    number: '1',
    label: {
      es: '1. Tiempo de Adquisición Orbital UTC (datetime_utc)',
      en: '1. Orbital Acquisition Timestamp UTC (datetime_utc)',
    },
    format: (hs) => hs.datetime_utc,
    fullWidth: true,
  },
  {
    key: 'satellite',
    number: '2',
    label: {
      es: '2. Plataforma Satelital y Sensor (satellite)',
      en: '2. Satellite Platform & Sensor (satellite)',
    },
    format: (hs) => {
      const gen = getSatelliteGeneration(hs.satellite);
      return `${hs.satellite} (${gen.generation} — ${gen.name})`;
    },
  },
  {
    key: 'day_night',
    number: '10',
    label: {
      es: '10. Régimen de Pasada Orbital (day_night)',
      en: '10. Orbital Overpass Regime (day_night)',
    },
    format: (hs, lang) => {
      if (hs.day_night === 'D') {
        return lang === 'es' ? 'Diurno / Ascendente (D)' : 'Daytime / Ascending (D)';
      }
      if (hs.day_night === 'N') {
        return lang === 'es' ? 'Nocturno / Descendente (N)' : 'Nighttime / Descending (N)';
      }
      return 'N/A';
    },
  },
  {
    key: 'lat',
    number: '3a',
    label: {
      es: '3a. Latitud Geodésica WGS84 (lat)',
      en: '3a. Geodetic Latitude WGS84 (lat)',
    },
    format: (hs) => `${hs.lat.toFixed(4)}°`,
  },
  {
    key: 'lon',
    number: '3b',
    label: {
      es: '3b. Longitud Geodésica WGS84 (lon)',
      en: '3b. Geodetic Longitude WGS84 (lon)',
    },
    format: (hs) => `${hs.lon.toFixed(4)}°`,
  },
  {
    key: 'temp_1',
    number: '4',
    label: {
      es: '4. Temp. de Brillo MIR ~4 µm T4/TI4 (temp_1)',
      en: '4. MIR Brightness Temp ~4 µm T4/TI4 (temp_1)',
    },
    format: (hs) => (hs.temp_1 !== null ? `${hs.temp_1.toFixed(1)} K` : 'N/A'),
  },
  {
    key: 'temp_2',
    number: '5',
    label: {
      es: '5. Temp. de Brillo Fondo TIR ~11 µm T31/TI5 (temp_2)',
      en: '5. TIR Background Brightness Temp ~11 µm T31/TI5 (temp_2)',
    },
    format: (hs) => (hs.temp_2 !== null ? `${hs.temp_2.toFixed(1)} K` : 'N/A'),
  },
  {
    key: 'pixel_geom',
    number: '6',
    label: {
      es: '6. Geometría de Píxel Scan×Track IFOV (pixel_geom)',
      en: '6. Scan×Track Pixel Footprint Area IFOV (pixel_geom)',
    },
    format: (hs) => (hs.pixel_geom !== null ? `${hs.pixel_geom.toFixed(2)} km²` : 'N/A'),
  },
  {
    key: 'frp',
    number: '7',
    label: {
      es: '7. Potencia Radiativa del Fuego (frp)',
      en: '7. Fire Radiative Power (frp)',
    },
    format: (hs) => `${hs.frp.toFixed(1)} MW`,
    highlight: true,
  },
  {
    key: 'confidence',
    number: '8',
    label: {
      es: '8. Confianza Algorítmica de Detección (confidence)',
      en: '8. Algorithmic Detection Confidence (confidence)',
    },
    format: (hs, lang) => formatConfidence(hs.confidence, lang),
  },
  {
    key: 'fire_type',
    number: '9',
    label: {
      es: '9. Clasificación de Anomalía Térmica (fire_type)',
      en: '9. Thermal Anomaly Classification (fire_type)',
    },
    format: (hs, lang) => formatFireType(hs.fire_type, lang),
  },
];

// ============================================================================
// 2. DEVELOPER VISUALIZATION REGISTRY (8 Plug-and-Play Modules)
// Change `enabled: true | false` or swap `kind` ('bar_series' | 'histogram' |
// 'quantile_band' | 'dual_compare' | 'stacked_share' | 'gauge_meter' |
// 'sparkline' | 'kv_table') when the database schema is finalized.
// ============================================================================

export const DEVELOPER_PANEL_VISUALIZATIONS: VisualizationSlotSpec[] = [
  // MODULE 1: BarSeriesWidget — Seasonal Activity vs Historical Median
  {
    id: 'seasonal-anomaly-bars',
    title: {
      es: 'Actividad Mensual Armonizada vs. Mediana Climatológica (P50)',
      en: 'Harmonized Monthly Activity vs. Climatological Median (P50)',
    },
    subtitle: {
      es: 'Módulo: bar_series (Conteo mensual calibrado frente a línea base multianual)',
      en: 'Module: bar_series (Calibrated monthly count vs. multi-year baseline)',
    },
    enabled: true,
    kind: 'bar_series',
    resolveData: ({ calendarCells, activeYear, lang }) => {
      const yearCells = calendarCells.filter((c) => c.year === activeYear);
      if (!yearCells.length) return null;
      const monthNames = TRANSLATIONS[lang].monthsShort;
      return {
        unit: lang === 'es' ? 'focos' : 'hotspots',
        baselineLabel:
          lang === 'es'
            ? `Mediana climatológica P50 (${activeYear})`
            : `Climatological median P50 (${activeYear})`,
        bars: monthNames.map((label, idx) => {
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
    title: {
      es: 'Comparativa Radiométrica: FRP Nativo vs. FRP Armonizado',
      en: 'Radiometric Comparison: Native Sensor FRP vs. Harmonized FRP',
    },
    subtitle: {
      es: 'Módulo: dual_compare (Efecto del factor de normalización inter-sensor)',
      en: 'Module: dual_compare (Effect of inter-sensor normalization factor)',
    },
    enabled: true,
    kind: 'dual_compare',
    resolveData: ({ selectedHotspot, lang }) => {
      if (!selectedHotspot) return null;
      const metrics = selectedHotspot.analysis_metrics ?? {};
      const rawFrp = Number(metrics.raw_frp ?? selectedHotspot.frp);
      const calFrp = Number(metrics.calibrated_frp ?? selectedHotspot.frp);
      return {
        leftLabel: lang === 'es' ? 'FRP Sensor Nativo (Bruto)' : 'Native Sensor FRP (Raw)',
        leftValue: rawFrp,
        rightLabel: lang === 'es' ? 'FRP Inter-Calibrado' : 'Inter-Calibrated FRP',
        rightValue: calFrp,
        unit: 'MW',
        caption:
          lang === 'es'
            ? `Factor de ponderación radiométrica: ${metrics.harmonization_factor ?? 1.0}x (${selectedHotspot.satellite})`
            : `Radiometric weighting factor: ${metrics.harmonization_factor ?? 1.0}x (${selectedHotspot.satellite})`,
      };
    },
  },

  // MODULE 3: QuantileBoxWidget — Position of Selected Hotspot in AOI FRP Distribution
  {
    id: 'frp-quantile-box',
    title: {
      es: 'Distribución No Paramétrica de Cuantiles FRP (Rango Intercuartílico IQR)',
      en: 'Non-Parametric FRP Quantile Distribution (Interquartile Range IQR)',
    },
    subtitle: {
      es: 'Módulo: quantile_band ([Mín, P25, Mediana P50, P75, Máx] en el AOI)',
      en: 'Module: quantile_band ([Min, P25, Median P50, P75, Max] within AOI)',
    },
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
    title: {
      es: 'Histograma de Densidad de Potencia Radiativa (Regímenes Energéticos FRP)',
      en: 'Fire Radiative Power Density Histogram (FRP Energy Regimes)',
    },
    subtitle: {
      es: 'Módulo: histogram (Resalta el intervalo de clase energética del foco activo)',
      en: 'Module: histogram (Highlights the energy class bin of the active hotspot)',
    },
    enabled: true,
    kind: 'histogram',
    resolveData: ({ hotspots, selectedHotspot, lang }) => {
      if (!hotspots.length) return null;
      const ranges = [
        { label: '<20 MW', min: 0, max: 20 },
        { label: '20–50 MW', min: 20, max: 50 },
        { label: '50–90 MW', min: 50, max: 90 },
        { label: '>90 MW', min: 90, max: Infinity },
      ];
      const curFrp = selectedHotspot?.frp ?? -1;
      return {
        unit: lang === 'es' ? 'focos' : 'hotspots',
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
    title: {
      es: 'Fracción de Muestreo por Generación Orbital (G1–G4)',
      en: 'Orbital Generation Sampling Fraction (G1–G4)',
    },
    subtitle: {
      es: 'Módulo: stacked_share (Aporte proporcional por resolución espacial nadir)',
      en: 'Module: stacked_share (Proportional contribution by nadir spatial resolution)',
    },
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
          { label: 'G1 MODIS (1000m)', value: counts.G1, color: '#f59e0b' },
          { label: 'G2 S-NPP (750m)', value: counts.G2, color: '#3b82f6' },
          { label: 'G3 NOAA-20 (375m)', value: counts.G3, color: '#10b981' },
          { label: 'G4 NOAA-21 (375m)', value: counts.G4, color: '#8b5cf6' },
        ],
      };
    },
  },

  // MODULE 6: GaugeMeterWidget — Thermal Gradient / Brightness Intensity Gauge (Ready to toggle)
  {
    id: 'thermal-gradient-gauge',
    title: {
      es: 'Gradiente Radiométrico de Temperatura de Brillo (ΔT = T_MIR − T_TIR)',
      en: 'Brightness Temperature Radiometric Gradient (ΔT = T_MIR − T_TIR)',
    },
    subtitle: {
      es: 'Módulo: gauge_meter (Contraste térmico en Kelvin respecto al fondo radiante)',
      en: 'Module: gauge_meter (Kelvin thermal contrast above background radiance)',
    },
    enabled: false, // <-- Cambia a `true` en 1 línea si el equipo entrega índices o umbrales
    kind: 'gauge_meter',
    resolveData: ({ selectedHotspot, lang }) => {
      if (!selectedHotspot || selectedHotspot.temp_1 === null || selectedHotspot.temp_2 === null) {
        return null;
      }
      const deltaT = Math.max(0, selectedHotspot.temp_1 - selectedHotspot.temp_2);
      const statusLabel =
        lang === 'es'
          ? deltaT >= 45
            ? 'Contraste Térmico Intenso'
            : deltaT >= 25
            ? 'Contraste Moderado'
            : 'Contraste Débil'
          : deltaT >= 45
          ? 'Intense Thermal Contrast'
          : deltaT >= 25
          ? 'Moderate Contrast'
          : 'Weak Contrast';
      return {
        value: deltaT,
        min: 0,
        max: 80,
        unit: 'K',
        statusLabel,
        thresholds: { warn: 25, danger: 45 },
      };
    },
  },

  // MODULE 7: SparklineTrendWidget — Multi-Year Historical Trend for Active Month (Ready to toggle)
  {
    id: 'multiyear-month-sparkline',
    title: {
      es: 'Serie Temporal Interanual del Mes Pico (2001–2026)',
      en: 'Interannual Peak-Month Time Series (2001–2026)',
    },
    subtitle: {
      es: 'Módulo: sparkline (Evolución secular multi-década en el AOI)',
      en: 'Module: sparkline (Multi-decadal secular evolution within AOI)',
    },
    enabled: false, // <-- Cambia a `true` en 1 línea si el equipo entrega series largas
    kind: 'sparkline',
    resolveData: ({ calendarCells, activeYear, lang }) => {
      const augustCells = calendarCells.filter((c) => c.month === 8);
      if (augustCells.length < 2) return null;
      return {
        unit: lang === 'es' ? 'focos' : 'hotspots',
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
    title: {
      es: 'Auditoría de Parámetros de Armonización y Metadatos Extendidos (BD)',
      en: 'Harmonization Parameter Audit & Extended Database Metadata',
    },
    subtitle: {
      es: 'Módulo: kv_table (Inspecciona en vivo parámetros físicos y claves dinámicas de analysis_metrics)',
      en: 'Module: kv_table (Live inspection of physical parameters and dynamic analysis_metrics keys)',
    },
    enabled: true,
    kind: 'kv_table',
    resolveData: ({ selectedHotspot, calibrationMode, lang }) => {
      if (!selectedHotspot) return null;
      const m = selectedHotspot.analysis_metrics ?? {};
      const baseRows =
        lang === 'es'
          ? [
              { label: 'Algoritmo de Calibración', value: String(m.harmonization_mode ?? calibrationMode) },
              { label: 'Factor de Ponderación IFOV', value: `${m.harmonization_factor ?? 1.0}x` },
              {
                label: 'Área Efectiva de Barrido (Scan×Track)',
                value: `${m.effective_area_km2 ?? selectedHotspot.pixel_geom ?? 1.0} km²`,
              },
              {
                label: 'Estado de Agrupamiento Orbital',
                value: m.is_cluster
                  ? `Clúster Fusionado (${m.merged_count} detecciones)`
                  : 'Píxel Individual Aislado',
              },
            ]
          : [
              { label: 'Calibration Algorithm', value: String(m.harmonization_mode ?? calibrationMode) },
              { label: 'IFOV Area-Weighting Factor', value: `${m.harmonization_factor ?? 1.0}x` },
              {
                label: 'Effective Scan×Track Footprint Area',
                value: `${m.effective_area_km2 ?? selectedHotspot.pixel_geom ?? 1.0} km²`,
              },
              {
                label: 'Orbital Clustering State',
                value: m.is_cluster
                  ? `Merged Cluster (${m.merged_count} detections)`
                  : 'Isolated Single Pixel',
              },
            ];

      // Any new key returned by Teammates 1 & 2's DB in analysis_metrics is automatically appended:
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
