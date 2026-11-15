import { useState } from 'react';
import type { AoiBounds, CalibrationMode, MonthlyCalendarCell, UnifiedHotspot } from '../services/apiClient';
import { InteractiveCalendar } from './InteractiveCalendar';
import { SeasonalAnomalyBarChart } from './SeasonalAnomalyBarChart';
import { getSatelliteGeneration } from '../utils/satelliteGenerations';

export interface HotspotSidePanelProps {
  status: string;
  totalHotspots: number;
  selectedHotspot: UnifiedHotspot | null;
  bounds: AoiBounds;
  calendarCells: MonthlyCalendarCell[];
  startDate: string;
  endDate: string;
  calibrationMode: CalibrationMode;
  onDateRangeChange: (start: string, end: string) => void;
  onCalibrationModeChange: (mode: CalibrationMode) => void;
  onRefresh: () => void;
  isLoading?: boolean;
}

interface AttributeDescriptor {
  key: keyof UnifiedHotspot;
  number: string;
  label: string;
  format: (hs: UnifiedHotspot) => string;
  highlight?: boolean;
  fullWidth?: boolean;
}

// Declarative Schema for the 10 Canonical Concepts of TEAM_DATA_CONTRACT.md
const CANONICAL_ATTRIBUTES: AttributeDescriptor[] = [
  {
    key: 'datetime_utc',
    number: '1',
    label: 'Fecha y Hora UTC (datetime_utc)',
    format: (hs) => hs.datetime_utc,
    fullWidth: true,
  },
  {
    key: 'satellite',
    number: '2',
    label: 'Satélite (satellite)',
    format: (hs) => {
      const gen = getSatelliteGeneration(hs.satellite);
      return `${hs.satellite} (${gen.generation} — ${gen.name})`;
    },
  },
  {
    key: 'day_night',
    number: '10',
    label: 'Día / Noche (day_night)',
    format: (hs) => (hs.day_night === 'D' ? 'Diurno (D)' : hs.day_night === 'N' ? 'Nocturno (N)' : 'N/A'),
  },
  {
    key: 'lat',
    number: '3a',
    label: 'Latitud (lat)',
    format: (hs) => `${hs.lat.toFixed(4)}°`,
  },
  {
    key: 'lon',
    number: '3b',
    label: 'Longitud (lon)',
    format: (hs) => `${hs.lon.toFixed(4)}°`,
  },
  {
    key: 'temp_1',
    number: '4',
    label: 'Temperatura 1 / Brillo (temp_1)',
    format: (hs) => (hs.temp_1 !== null ? `${hs.temp_1.toFixed(1)} K` : 'N/A'),
  },
  {
    key: 'temp_2',
    number: '5',
    label: 'Temperatura 2 (temp_2)',
    format: (hs) => (hs.temp_2 !== null ? `${hs.temp_2.toFixed(1)} K` : 'N/A'),
  },
  {
    key: 'pixel_geom',
    number: '6',
    label: 'Geometría Píxel (pixel_geom)',
    format: (hs) => (hs.pixel_geom !== null ? `${hs.pixel_geom.toFixed(2)} km²` : 'N/A'),
  },
  {
    key: 'frp',
    number: '7',
    label: 'Potencia Radiativa (frp)',
    format: (hs) => `${hs.frp.toFixed(1)} MW`,
    highlight: true,
  },
  {
    key: 'confidence',
    number: '8',
    label: 'Confianza (confidence)',
    format: (hs) => hs.confidence.toUpperCase(),
  },
  {
    key: 'fire_type',
    number: '9',
    label: 'Tipo de Anomalía (fire_type)',
    format: (hs) => (hs.fire_type !== null ? `Tipo ${hs.fire_type} (Vegetación)` : 'N/A'),
  },
];

export function HotspotSidePanel({
  status,
  totalHotspots,
  selectedHotspot,
  bounds,
  calendarCells,
  startDate,
  endDate,
  calibrationMode,
  onDateRangeChange,
  onCalibrationModeChange,
  onRefresh,
  isLoading = false,
}: HotspotSidePanelProps) {
  const [isAnalysisOpen, setIsAnalysisOpen] = useState<boolean>(true);
  const activeYear = parseInt(startDate.slice(0, 4), 10) || 2024;

  const metrics = selectedHotspot?.analysis_metrics ?? null;

  return (
    <aside
      style={{
        padding: '16px',
        borderLeft: '1px solid #cbd5e1',
        background: '#f8fafc',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}
    >
      {/* HEADER & STATUS */}
      <div>
        <h3 style={{ margin: '0 0 4px 0', color: '#0f172a', fontSize: '16px' }}>
          Armonización MODIS & VIIRS — Ruta 1
        </h3>
        <div style={{ fontSize: '12px', color: '#475569' }}>
          <strong>Estado:</strong> {status} ({totalHotspots} focos armonizados en el AOI)
        </div>
      </div>

      {/* SECCIÓN A: CALENDARIO DE ACTIVIDAD 100% FUNCIONAL */}
      <InteractiveCalendar
        bounds={bounds}
        calendarCells={calendarCells}
        startDate={startDate}
        endDate={endDate}
        calibrationMode={calibrationMode}
        onDateRangeChange={onDateRangeChange}
        onCalibrationModeChange={onCalibrationModeChange}
        onRefresh={onRefresh}
        isLoading={isLoading}
      />

      {/* SECCIÓN B: INSPECCIÓN DECLARATIVA DE LOS 10 CONCEPTOS CANÓNICOS */}
      <section
        style={{
          background: '#ffffff',
          border: '1px solid #cbd5e1',
          borderRadius: '8px',
          padding: '14px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <strong style={{ fontSize: '13px', color: '#1e293b' }}>
            Atributos Canónicos del Foco (10 Conceptos)
          </strong>
          {selectedHotspot && (
            <span
              style={{
                fontSize: '11px',
                background: '#fee2e2',
                color: '#991b1b',
                padding: '2px 8px',
                borderRadius: '999px',
                fontWeight: 600,
              }}
            >
              {selectedHotspot.satellite}
            </span>
          )}
        </div>

        {!selectedHotspot ? (
          <div
            style={{
              padding: '18px 12px',
              textAlign: 'center',
              color: '#64748b',
              fontSize: '12px',
              background: '#f8fafc',
              borderRadius: '6px',
              border: '1px dashed #cbd5e1',
            }}
          >
            Haz clic sobre cualquier <strong>foco en el mapa</strong> para inspeccionar sus atributos canónicos y calibración.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
            {CANONICAL_ATTRIBUTES.map((attr) => (
              <div
                key={attr.key}
                style={{
                  gridColumn: attr.fullWidth ? '1 / -1' : undefined,
                  background: '#f8fafc',
                  padding: '7px 9px',
                  borderRadius: '5px',
                  border: '1px solid #f1f5f9',
                }}
              >
                <div style={{ fontSize: '10px', color: '#64748b' }}>{attr.label}</div>
                <strong
                  style={{
                    color: attr.highlight ? '#dc2626' : '#0f172a',
                    fontFamily: attr.key === 'datetime_utc' || attr.key === 'lat' || attr.key === 'lon' ? 'monospace' : 'inherit',
                  }}
                >
                  {attr.format(selectedHotspot)}
                </strong>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* SECCIÓN C: DESPLEGABLE CON GRÁFICO SVG Y FACTORES DE ARMONIZACIÓN CIENTÍFICA */}
      <section
        style={{
          background: '#ffffff',
          border: '1px solid #cbd5e1',
          borderRadius: '8px',
          overflow: 'hidden',
        }}
      >
        <button
          type="button"
          onClick={() => setIsAnalysisOpen((prev) => !prev)}
          style={{
            width: '100%',
            padding: '12px 14px',
            background: '#f1f5f9',
            border: 'none',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <div>
            <strong style={{ fontSize: '13px', color: '#0f172a', display: 'block' }}>
              Métricas Científicas y Factores de Armonización
            </strong>
            <span style={{ fontSize: '11px', color: '#64748b' }}>
              Gráfico de anomalías vs mediana histórica y contrato extensible
            </span>
          </div>
          <span style={{ fontSize: '14px', color: '#475569', fontWeight: 700 }}>
            {isAnalysisOpen ? '▼' : '▶'}
          </span>
        </button>

        {isAnalysisOpen && (
          <div style={{ padding: '14px', borderTop: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {/* SVG BAR CHART */}
            <SeasonalAnomalyBarChart
              calendarCells={calendarCells}
              year={activeYear}
            />

            {/* HARMONIZATION FACTORS TABLE FOR SELECTED POINT */}
            <div>
              <strong style={{ fontSize: '12px', color: '#1e293b', display: 'block', marginBottom: '6px' }}>
                Factores de Armonización del Foco Activo:
              </strong>

              {!selectedHotspot ? (
                <div style={{ fontSize: '11px', color: '#94a3b8', fontStyle: 'italic', padding: '6px 0' }}>
                  Selecciona un foco en el mapa para ver sus factores de calibración.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {[
                    {
                      label: 'Modo de Calibración',
                      val: metrics?.harmonization_mode ?? calibrationMode,
                    },
                    {
                      label: 'Factor de Ponderación Espacial',
                      val: metrics?.harmonization_factor !== undefined ? `${metrics.harmonization_factor}x` : '1.0x',
                    },
                    {
                      label: 'Área Efectiva del Píxel',
                      val: metrics?.effective_area_km2 !== undefined ? `${metrics.effective_area_km2} km²` : `${selectedHotspot.pixel_geom ?? 1.0} km²`,
                    },
                    {
                      label: 'FRP Calibrado',
                      val: metrics?.calibrated_frp !== undefined ? `${metrics.calibrated_frp} MW` : `${selectedHotspot.frp} MW`,
                    },
                    {
                      label: '¿Foco Fusionado (Cluster)?',
                      val: metrics?.is_cluster ? `Sí (${metrics.merged_count} detecciones unificadas)` : 'No (Detección individual)',
                    },
                    ...(metrics?.cluster_id
                      ? [{ label: 'Identificador de Cluster', val: String(metrics.cluster_id) }]
                      : []),
                    ...(metrics?.satellites_involved
                      ? [{ label: 'Satélites en el Foco', val: (metrics.satellites_involved as string[]).join(', ') }]
                      : []),
                  ].map((row) => (
                    <div
                      key={row.label}
                      style={{
                        padding: '6px 8px',
                        background: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        borderRadius: '4px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: '11px',
                      }}
                    >
                      <span style={{ color: '#475569', fontWeight: 500 }}>{row.label}:</span>
                      <strong style={{ color: '#0f172a' }}>{row.val}</strong>
                    </div>
                  ))}

                  {/* DYNAMIC EXTENSIBLE METRICS ITERATOR FOR FUTURE TEAM DATA ADDITIONS */}
                  {metrics &&
                    Object.entries(metrics)
                      .filter(
                        ([k]) =>
                          ![
                            'harmonization_mode',
                            'harmonization_factor',
                            'effective_area_km2',
                            'calibrated_frp',
                            'is_cluster',
                            'cluster_id',
                            'satellites_involved',
                          ].includes(k)
                      )
                      .map(([k, v]) => (
                        <div
                          key={k}
                          style={{
                            padding: '6px 8px',
                            background: '#eff6ff',
                            border: '1px solid #bfdbfe',
                            borderRadius: '4px',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            fontSize: '11px',
                          }}
                        >
                          <span style={{ color: '#1e40af', fontWeight: 500 }}>{k}:</span>
                          <strong style={{ color: '#1e3a8a' }}>{String(v)}</strong>
                        </div>
                      ))}
                </div>
              )}
            </div>
          </div>
        )}
      </section>
    </aside>
  );
}
