import { useState } from 'react';
import type {
  AoiBounds,
  CalibrationMode,
  CellMonthAoiResponse,
  CellMonthMetric,
  MonthlyCalendarCell,
  UnifiedHotspot,
} from '../services/apiClient';
import type { MapRenderMode } from './CenteredAoiMap';
import { CellMonthPanel } from './CellMonthPanel';
import { InteractiveCalendar } from './InteractiveCalendar';
import {
  CANONICAL_ATTRIBUTES_CONFIG,
  DEVELOPER_PANEL_VISUALIZATIONS,
} from '../config/sidePanelConfig';
import { VisualizationModuleRenderer } from './visualizations/VisualizationLibrary';
import type { SidePanelVisualizationContext } from './visualizations/contracts';
import { LanguageToggle, resolveText, useLanguage } from '../i18n/LanguageContext';
import { SATELLITE_GENERATIONS } from '../utils/satelliteGenerations';

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
  mapRenderMode: MapRenderMode;
  onMapRenderModeChange: (mode: MapRenderMode) => void;
  onDateRangeChange: (start: string, end: string) => void;
  onCalibrationModeChange: (mode: CalibrationMode) => void;
  onRefresh: () => void;
  isLoading?: boolean;
  cellMonthData?: CellMonthAoiResponse | null;
  cellMonthMetric?: CellMonthMetric;
  onCellMonthMetricChange?: (metric: CellMonthMetric) => void;
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
  mapRenderMode,
  onMapRenderModeChange,
  onDateRangeChange,
  onCalibrationModeChange,
  onRefresh,
  isLoading = false,
  cellMonthData = null,
  cellMonthMetric = 'n_eq',
  onCellMonthMetricChange,
}: HotspotSidePanelProps) {
  const { lang, t } = useLanguage();
  const [isAnalysisOpen, setIsAnalysisOpen] = useState<boolean>(true);
  const activeYear = parseInt(startDate.slice(0, 4), 10) || 2024;

  const vizContext: SidePanelVisualizationContext = {
    selectedHotspot,
    hotspots,
    calendarCells,
    calibrationMode,
    activeYear,
    lang,
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
      {/* HEADER & TOP-RIGHT BILINGUAL TOGGLE (ES | EN) */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <h3 style={{ margin: 0, color: '#0f172a', fontSize: '15px' }}>
            {t.panelMainTitle}
          </h3>
          <LanguageToggle />
        </div>
        <div style={{ fontSize: '12px', color: '#475569' }}>
          <strong>{t.panelStatusLabel}</strong> {status} ({totalHotspots} {t.hotspotsInAoiSuffix})
        </div>
      </div>

      {/* TOP CONTROL: SPATIAL DETECTION REPRESENTATION RADIO SELECTOR */}
      <section
        style={{
          background: '#ffffff',
          border: '1px solid #cbd5e1',
          borderRadius: '8px',
          padding: '12px 14px',
        }}
      >
        <div style={{ fontSize: '12px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
          {t.mapControlTitle}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              cursor: 'pointer',
              color: mapRenderMode === 'harmonized' ? '#0f172a' : '#64748b',
              fontWeight: mapRenderMode === 'harmonized' ? 600 : 400,
            }}
          >
            <input
              type="radio"
              name="sidePanelMapRenderMode"
              value="harmonized"
              checked={mapRenderMode === 'harmonized'}
              onChange={() => onMapRenderModeChange('harmonized')}
              style={{ cursor: 'pointer' }}
            />
            {t.mapRadioHarmonized}
          </label>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              cursor: 'pointer',
              color: mapRenderMode === 'footprint' ? '#0f172a' : '#64748b',
              fontWeight: mapRenderMode === 'footprint' ? 600 : 400,
            }}
          >
            <input
              type="radio"
              name="sidePanelMapRenderMode"
              value="footprint"
              checked={mapRenderMode === 'footprint'}
              onChange={() => onMapRenderModeChange('footprint')}
              style={{ cursor: 'pointer' }}
            />
            {t.mapRadioFootprint}
          </label>
        </div>

        {/* Legend for 4 Satellite Generations (when footprint mode is active) */}
        {mapRenderMode === 'footprint' && (
          <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid #e2e8f0', fontSize: '11px' }}>
            <div style={{ fontWeight: 600, color: '#475569', marginBottom: '5px' }}>
              {t.mapFootprintLegendTitle}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 8px' }}>
              {(['G1', 'G2', 'G3', 'G4'] as const).map((genKey) => {
                const info = SATELLITE_GENERATIONS[genKey];
                return (
                  <div key={genKey} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span
                      style={{
                        width: '11px',
                        height: '11px',
                        borderRadius: '50%',
                        backgroundColor: info.color,
                        border: `1.5px solid ${info.strokeColor}`,
                        display: 'inline-block',
                        flexShrink: 0,
                      }}
                    />
                    <span style={{ color: '#1e293b' }}>
                      <strong>{genKey}:</strong> {info.name} ({info.resolutionMeters}m)
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </section>

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

      {/* SECCIÓN A2: GRILLA ARMONIZADA 0.25° (harmonized.cell_month 2012-2026) */}
      <CellMonthPanel
        bounds={bounds}
        data={cellMonthData}
        metric={cellMonthMetric}
        startDate={startDate}
        endDate={endDate}
        onMetricChange={(m) => onCellMonthMetricChange?.(m)}
        onDateRangeChange={onDateRangeChange}
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
            {t.sectionCanonicalTitle}
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
            {t.emptyHotspotPrompt}
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
                <div style={{ fontSize: '10px', color: '#64748b' }}>
                  {resolveText(attr.label, lang)}
                </div>
                <strong
                  style={{
                    color: attr.highlight ? '#dc2626' : '#0f172a',
                    fontFamily:
                      attr.key === 'datetime_utc' || attr.key === 'lat' || attr.key === 'lon'
                        ? 'monospace'
                        : 'inherit',
                  }}
                >
                  {attr.format(selectedHotspot, lang)}
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
              {t.sectionVisualizationsTitle}
            </strong>
            <span style={{ fontSize: '11px', color: '#64748b' }}>
              {t.sectionVisualizationsSubtitle}
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
