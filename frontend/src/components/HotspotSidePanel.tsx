import { useState } from 'react';
import type { AoiBounds, CalibrationMode, MonthlyCalendarCell, UnifiedHotspot } from '../services/apiClient';
import { InteractiveCalendar } from './InteractiveCalendar';
import {
  CANONICAL_ATTRIBUTES_CONFIG,
  DEVELOPER_PANEL_VISUALIZATIONS,
} from '../config/sidePanelConfig';
import { VisualizationModuleRenderer } from './visualizations/VisualizationLibrary';
import type { SidePanelVisualizationContext } from './visualizations/contracts';

export interface HotspotSidePanelProps {
  status: string;
  totalHotspots: number;
  hotspots: UnifiedHotspot[];
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

export function HotspotSidePanel({
  status,
  totalHotspots,
  hotspots,
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

  const vizContext: SidePanelVisualizationContext = {
    selectedHotspot,
    hotspots,
    calendarCells,
    calibrationMode,
    activeYear,
  };

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
          Armonización MODIS & VIIRS — Panel Modular
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
            {CANONICAL_ATTRIBUTES_CONFIG.map((attr) => (
              <div
                key={String(attr.key)}
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
                    fontFamily:
                      attr.key === 'datetime_utc' || attr.key === 'lat' || attr.key === 'lon'
                        ? 'monospace'
                        : 'inherit',
                  }}
                >
                  {attr.format(selectedHotspot)}
                </strong>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* SECCIÓN C: MÓDULOS DE INTERFAZ DE VISUALIZACIÓN (CONTROLADOS POR sidePanelConfig.ts) */}
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
              Módulos de Visualización y Datos Procesados
            </strong>
            <span style={{ fontSize: '11px', color: '#64748b' }}>
              Configurables por código en <code>src/config/sidePanelConfig.ts</code>
            </span>
          </div>
          <span style={{ fontSize: '14px', color: '#475569', fontWeight: 700 }}>
            {isAnalysisOpen ? '▼' : '▶'}
          </span>
        </button>

        {isAnalysisOpen && (
          <div
            style={{
              padding: '12px',
              borderTop: '1px solid #e2e8f0',
              background: '#f8fafc',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            {DEVELOPER_PANEL_VISUALIZATIONS.map((slot) => (
              <VisualizationModuleRenderer
                key={slot.id}
                slot={slot}
                context={vizContext}
              />
            ))}
          </div>
        )}
      </section>
    </aside>
  );
}
