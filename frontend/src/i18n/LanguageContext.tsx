import React, { createContext, useContext, useState, useEffect } from 'react';

export type Language = 'es' | 'en';

export type LocalizedText = string | { es: string; en: string };

export function resolveText(text: LocalizedText | undefined, lang: Language): string {
  if (!text) return '';
  if (typeof text === 'string') return text;
  return text[lang] ?? text.es;
}

export const TRANSLATIONS = {
  es: {
    // Top Bar & Global Status
    aoiCenteredLabel: 'AOI Centrada ( Marco de Muestreo ):',
    queryAoiBtn: 'Consultar AOI',
    loadingBtn: 'Procesando...',
    calibrationLabel: 'Algoritmo:',
    mapViewLabel: 'Modo Cartográfico:',
    statusIdle: 'Inactivo — Pulsa "Consultar AOI" o desplaza el visor geográfico',
    statusQuerying: 'Consultando telemetría satelital y aplicando armonización radiométrica...',
    statusConnectedPrefix: 'Conectado',
    statusModeLabel: 'Calibración',
    statusSourceLabel: 'Fuente',
    hotspotsInAoiSuffix: 'focos térmicos armonizados en el AOI',

    // Calibration Mode Short Names
    calModeShort: {
      area_weighted: 'Ponderado por Huella (IFOV)',
      deduplicated: 'Deduplicación Coincidente',
      raw: 'Observación Bruta (Sin Calibrar)',
    },
    mapModeShort: {
      harmonized: 'Homogéneo Calibrado',
      footprint: 'Huella Física IFOV (m)',
    },

    // Map Floating Control & Tooltips
    mapControlTitle: 'Representación Espacial de Detecciones',
    mapRadioHarmonized: 'Focos Armonizados (Simbología Homogénea)',
    mapRadioFootprint: 'Discriminar por Sensor y Huella Física IFOV (m)',
    mapFootprintLegendTitle: 'Huella Instantánea de Proyección en Tierra (Nadir):',
    mapClusterBadge: 'Clúster fusionado (copasada simultánea)',
    mapTooltipFootprint: 'Resolución espacial nadir',
    mapTooltipRadius: 'radio de huella',
    mapTooltipConfidence: 'Confianza',

    // Side Panel Header & Sections
    panelMainTitle: 'Armonización Inter-Sensor MODIS & VIIRS',
    panelStatusLabel: 'Estado del Sistema:',
    sectionCanonicalTitle: 'Telemetría Canónica del Foco (10 Variables FIRMS)',
    emptyHotspotPrompt: 'Selecciona cualquier foco térmico en el mapa para inspeccionar su telemetría radiométrica, geometría de barrido y calibración.',
    sectionVisualizationsTitle: 'Módulos de Visualización Científica y Diagnóstico',
    sectionVisualizationsSubtitle: 'Configurables por código en src/config/sidePanelConfig.ts',

    // Interactive Calendar
    calendarTitle: 'Calendario Multianual de Actividad Ígnea y Anomalías',
    calendarSubtitle: 'Matriz mensual armonizada vs. Climatología Mediana P50 (2001–2026)',
    exportCsvBtn: 'Exportar CSV Armonizado',
    exportCsvTooltip: 'Descargar serie armonizada conforme al estándar RFC-4180 CSV',
    algorithmBoxTitle: 'Algoritmo de Armonización Inter-Calibrada:',
    algAreaWeightedTitle: 'Ponderación por Área de Píxel (IFOV)',
    algAreaWeightedDesc: '(1.0 km² MODIS vs. 0.14 km² VIIRS I-Band) — Recomendado',
    algDeduplicatedTitle: 'Deduplicación Espacio-Temporal',
    algDeduplicatedDesc: '(Fusión de detecciones en copasadas orbitales simultáneas)',
    algRawTitle: 'Conteo Bruto Sin Armonizar',
    algRawDesc: '(Detecciones nativas del sensor sin corrección geométrica)',
    dateFrom: 'Fecha Inicial (UTC)',
    dateTo: 'Fecha Final (UTC)',
    refreshBtn: 'Actualizar',
    presetsLabel: 'Ventanas:',
    preset2024All: 'Año 2024',
    preset2024Peak: 'Pico Estacional 2024 (Ago–Oct)',
    preset2020Peak: 'Anomalía Extrema 2020 (Récord)',
    presetAllHistory: 'Serie Histórica (2001–2026)',
    matrixHeaderTitle: 'Matriz Anual × Mensual de Focos Armonizados',
    matrixToggleAll: 'Ver serie completa (2001–2026)',
    matrixToggleRecent: 'Ver período reciente (2018–2026)',
    matrixEmpty: 'No se registran celdas temporales para la ventana actual.',
    matrixYearCol: 'Año',
    monthsShort: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
    severityLegendTitle: 'Índice de Anomalía Estacional vs. Mediana Climatológica (P50):',
    severityLabels: {
      low: 'Sub-normal (<-25%)',
      normal: 'Rango Nominal (±25%)',
      elevated: 'Anomalía Moderada (+25% a +100%)',
      extreme: 'Anomalía Crítica (>+100%)',
    },
    calendarCellTooltip: (monthName: string, year: number, count: number, median: number, anomalyPct: number, sevLabel: string) =>
      `${monthName} ${year}: ${count} focos armonizados | Mediana climatológica (P50): ${median} | Desviación: ${anomalyPct > 0 ? '+' : ''}${anomalyPct}% (${sevLabel})\nHaz clic para acotar la ventana temporal a este mes`,
    calendarFooterHint: '💡 Pulsa cualquier celda mensual para acotar automáticamente el filtro temporal y el mapa a ese período.',

    // Visualization Widgets Internal Strings
    vizEmptyNotice: 'Selecciona un foco térmico o ejecuta la consulta sobre el AOI para calcular este módulo.',
    vizMaxLabel: 'Máx',
    vizMinLabel: 'Mín',
    vizBaseLabel: 'Referencia',
    vizSelectedHotspotPin: 'Foco activo seleccionado',
    vizMedianTooltip: 'Mediana Estadística (Percentil 50)',
    vizCurrentValueTooltip: 'Valor radiométrico del foco activo',
  },

  en: {
    // Top Bar & Global Status
    aoiCenteredLabel: 'Centered AOI (Sampling Frame):',
    queryAoiBtn: 'Query AOI',
    loadingBtn: 'Processing...',
    calibrationLabel: 'Algorithm:',
    mapViewLabel: 'Cartographic Mode:',
    statusIdle: 'Idle — Click "Query AOI" or pan the geographic viewfinder',
    statusQuerying: 'Querying satellite telemetry and applying radiometric harmonization...',
    statusConnectedPrefix: 'Connected',
    statusModeLabel: 'Calibration',
    statusSourceLabel: 'Source',
    hotspotsInAoiSuffix: 'harmonized thermal hotspots in AOI',

    // Calibration Mode Short Names
    calModeShort: {
      area_weighted: 'Footprint Area-Weighted (IFOV)',
      deduplicated: 'Coincident Deduplication',
      raw: 'Raw Observation (Uncalibrated)',
    },
    mapModeShort: {
      harmonized: 'Calibrated Homogeneous',
      footprint: 'Physical IFOV Footprint (m)',
    },

    // Map Floating Control & Tooltips
    mapControlTitle: 'Spatial Detection Representation',
    mapRadioHarmonized: 'Harmonized Hotspots (Homogeneous Symbology)',
    mapRadioFootprint: 'Discriminate by Sensor & True IFOV Footprint (m)',
    mapFootprintLegendTitle: 'Instantaneous Ground Projected Footprint (Nadir):',
    mapClusterBadge: 'Merged cluster (coincident overpass)',
    mapTooltipFootprint: 'Nadir spatial resolution',
    mapTooltipRadius: 'footprint radius',
    mapTooltipConfidence: 'Confidence',

    // Side Panel Header & Sections
    panelMainTitle: 'MODIS & VIIRS Inter-Sensor Harmonization',
    panelStatusLabel: 'System Status:',
    sectionCanonicalTitle: 'Canonical Hotspot Telemetry (10 FIRMS Variables)',
    emptyHotspotPrompt: 'Click any thermal hotspot on the map to inspect its radiometric telemetry, scan-track pixel geometry, and calibration.',
    sectionVisualizationsTitle: 'Scientific Visualization & Diagnostic Modules',
    sectionVisualizationsSubtitle: 'Code-configurable via src/config/sidePanelConfig.ts',

    // Interactive Calendar
    calendarTitle: 'Multi-Year Burning Activity & Anomaly Calendar',
    calendarSubtitle: 'Harmonized monthly matrix vs. Climatological Median P50 (2001–2026)',
    exportCsvBtn: 'Export Harmonized CSV',
    exportCsvTooltip: 'Download harmonized dataset in RFC-4180 compliant CSV format',
    algorithmBoxTitle: 'Inter-Calibrated Harmonization Algorithm:',
    algAreaWeightedTitle: 'Pixel Footprint Area-Weighting (IFOV)',
    algAreaWeightedDesc: '(1.0 km² MODIS vs. 0.14 km² VIIRS I-Band) — Recommended',
    algDeduplicatedTitle: 'Spatio-Temporal Deduplication',
    algDeduplicatedDesc: '(Coincident orbital overpass cluster merging)',
    algRawTitle: 'Unharmonized Raw Count',
    algRawDesc: '(Native sensor detections without geometric normalization)',
    dateFrom: 'Start Date (UTC)',
    dateTo: 'End Date (UTC)',
    refreshBtn: 'Refresh',
    presetsLabel: 'Presets:',
    preset2024All: 'Full Year 2024',
    preset2024Peak: '2024 Burning Peak (Aug–Oct)',
    preset2020Peak: '2020 Extreme Anomaly (Record)',
    presetAllHistory: 'Full Time Series (2001–2026)',
    matrixHeaderTitle: 'Annual × Monthly Harmonized Hotspot Matrix',
    matrixToggleAll: 'Show full record (2001–2026)',
    matrixToggleRecent: 'Show recent period (2018–2026)',
    matrixEmpty: 'No temporal matrix cells available for the current query.',
    matrixYearCol: 'Year',
    monthsShort: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    severityLegendTitle: 'Seasonal Anomaly Index vs. Climatological Median (P50):',
    severityLabels: {
      low: 'Below Normal (<-25%)',
      normal: 'Nominal Range (±25%)',
      elevated: 'Elevated Anomaly (+25% to +100%)',
      extreme: 'Extreme Anomaly (>+100%)',
    },
    calendarCellTooltip: (monthName: string, year: number, count: number, median: number, anomalyPct: number, sevLabel: string) =>
      `${monthName} ${year}: ${count} harmonized hotspots | Climatological median (P50): ${median} | Departure: ${anomalyPct > 0 ? '+' : ''}${anomalyPct}% (${sevLabel})\nClick to filter map and time window to this month`,
    calendarFooterHint: '💡 Click any monthly cell to automatically focus the temporal filter and map on that period.',

    // Visualization Widgets Internal Strings
    vizEmptyNotice: 'Select a thermal hotspot or query the AOI to populate this diagnostic module.',
    vizMaxLabel: 'Max',
    vizMinLabel: 'Min',
    vizBaseLabel: 'Baseline',
    vizSelectedHotspotPin: 'Active selected hotspot',
    vizMedianTooltip: 'Statistical Median (50th Percentile)',
    vizCurrentValueTooltip: 'Active hotspot radiometric value',
  },
} as const;

interface LanguageContextValue {
  lang: Language;
  setLang: (lang: Language) => void;
  t: (typeof TRANSLATIONS)[Language];
}

const LanguageContext = createContext<LanguageContextValue>({
  lang: 'es',
  setLang: () => {},
  t: TRANSLATIONS.es,
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Language>(() => {
    try {
      const saved = localStorage.getItem('nasa_firms_lang');
      return saved === 'en' || saved === 'es' ? saved : 'es';
    } catch {
      return 'es';
    }
  });

  const setLang = (next: Language) => {
    setLangState(next);
    try {
      localStorage.setItem('nasa_firms_lang', next);
    } catch {
      // ignore storage errors
    }
  };

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  return (
    <LanguageContext.Provider value={{ lang, setLang, t: TRANSLATIONS[lang] }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}

/**
 * Compact top-right bilingual toggle component (ES | EN)
 */
export function LanguageToggle() {
  const { lang, setLang } = useLanguage();

  return (
    <div
      role="group"
      aria-label="Language selector / Selector de idioma"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        background: '#e2e8f0',
        borderRadius: '6px',
        padding: '2px',
        border: '1px solid #cbd5e1',
        flexShrink: 0,
      }}
    >
      <button
        type="button"
        onClick={() => setLang('es')}
        title="Español (Terminología Técnica CONAE / FIRMS)"
        style={{
          padding: '3px 8px',
          fontSize: '11px',
          fontWeight: 700,
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          background: lang === 'es' ? '#0f172a' : 'transparent',
          color: lang === 'es' ? '#ffffff' : '#475569',
          transition: 'all 0.15s ease',
        }}
      >
        ES
      </button>
      <button
        type="button"
        onClick={() => setLang('en')}
        title="English (NASA FIRMS / VIIRS Technical Terminology)"
        style={{
          padding: '3px 8px',
          fontSize: '11px',
          fontWeight: 700,
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          background: lang === 'en' ? '#0f172a' : 'transparent',
          color: lang === 'en' ? '#ffffff' : '#475569',
          transition: 'all 0.15s ease',
        }}
      >
        EN
      </button>
    </div>
  );
}
