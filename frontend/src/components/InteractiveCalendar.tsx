import React, { useState } from 'react';
import type { AoiBounds, CalibrationMode, MonthlyCalendarCell } from '../services/apiClient';
import { getExportCsvUrl } from '../services/apiClient';

export interface InteractiveCalendarProps {
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

const MONTH_NAMES = [
  'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
  'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
];

const SEVERITY_COLORS = {
  low: { bg: '#e0f2fe', text: '#0369a1', border: '#bae6fd', label: 'Baja (<-25%)' },
  normal: { bg: '#fef9c3', text: '#854d0e', border: '#fef08a', label: 'Normal (±25%)' },
  elevated: { bg: '#ffedd5', text: '#c2410c', border: '#fed7aa', label: 'Elevada (+25% a +100%)' },
  extreme: { bg: '#fee2e2', text: '#991b1b', border: '#fca5a5', label: 'Extrema (>+100%)' },
};

export function InteractiveCalendar({
  bounds,
  calendarCells,
  startDate,
  endDate,
  calibrationMode,
  onDateRangeChange,
  onCalibrationModeChange,
  onRefresh,
  isLoading = false,
}: InteractiveCalendarProps) {
  const [selectedCellKey, setSelectedCellKey] = useState<string | null>(null);
  const [viewYearRange, setViewYearRange] = useState<'recent' | 'all'>('recent');

  // Group cells by year
  const yearsMap = new Map<number, Map<number, MonthlyCalendarCell>>();
  for (const cell of calendarCells) {
    if (!yearsMap.has(cell.year)) {
      yearsMap.set(cell.year, new Map());
    }
    yearsMap.get(cell.year)!.set(cell.month, cell);
  }

  const allYears = Array.from(yearsMap.keys()).sort((a, b) => b - a);
  const displayYears = viewYearRange === 'recent'
    ? allYears.filter((y) => y >= 2018)
    : allYears;

  const handleCellClick = (year: number, month: number) => {
    const key = `${year}-${month}`;
    setSelectedCellKey(key);

    const padMonth = month.toString().padStart(2, '0');
    // Calculate last day of month
    const lastDay = new Date(year, month, 0).getDate();
    const newStart = `${year}-${padMonth}-01`;
    const newEnd = `${year}-${padMonth}-${lastDay.toString().padStart(2, '0')}`;

    onDateRangeChange(newStart, newEnd);
  };

  const handleExportCsv = () => {
    const url = getExportCsvUrl(bounds, {
      startDate,
      endDate,
      calibrationMode,
    });
    window.open(url, '_blank');
  };

  const setPreset = (preset: '2024_all' | '2024_peak' | '2020_peak' | 'all_history') => {
    if (preset === '2024_all') onDateRangeChange('2024-01-01', '2024-12-31');
    if (preset === '2024_peak') onDateRangeChange('2024-08-01', '2024-10-31');
    if (preset === '2020_peak') onDateRangeChange('2020-07-01', '2020-10-31');
    if (preset === 'all_history') onDateRangeChange('2001-01-01', '2026-12-31');
  };

  return (
    <section
      style={{
        background: '#ffffff',
        border: '1px solid #cbd5e1',
        borderRadius: '8px',
        padding: '14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}
    >
      {/* HEADER & EXPORT BUTTON */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <h4 style={{ margin: 0, fontSize: '14px', color: '#0f172a' }}>
            Calendario de Actividad y Anomalías
          </h4>
          <span style={{ fontSize: '11px', color: '#64748b' }}>
            Matriz multianual calibrada vs Mediana Histórica (2001–2026)
          </span>
        </div>

        <button
          onClick={handleExportCsv}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 12px',
            background: '#047857',
            color: '#ffffff',
            border: 'none',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          }}
          title="Descargar conjunto de datos armonizado en formato RFC-4180 CSV"
        >
          <span>📥</span> Exportar CSV Armonizado
        </button>
      </div>

      {/* ALGORITHM SELECTOR (RADIO BUTTONS) */}
      <div
        style={{
          background: '#f8fafc',
          padding: '10px 12px',
          borderRadius: '6px',
          border: '1px solid #e2e8f0',
        }}
      >
        <span style={{ fontSize: '11px', fontWeight: 700, color: '#334155', display: 'block', marginBottom: '6px' }}>
          Algoritmo de Armonización Científica:
        </span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer' }}>
            <input
              type="radio"
              name="calMode"
              value="area_weighted"
              checked={calibrationMode === 'area_weighted'}
              onChange={() => onCalibrationModeChange('area_weighted')}
            />
            <span style={{ color: '#0f172a', fontWeight: calibrationMode === 'area_weighted' ? 600 : 400 }}>
              <strong>Ponderado por Área</strong> (1 km² MODIS vs 0.14 km² VIIRS) — <em>Recomendado</em>
            </span>
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer' }}>
            <input
              type="radio"
              name="calMode"
              value="deduplicated"
              checked={calibrationMode === 'deduplicated'}
              onChange={() => onCalibrationModeChange('deduplicated')}
            />
            <span style={{ color: '#0f172a', fontWeight: calibrationMode === 'deduplicated' ? 600 : 400 }}>
              <strong>Deduplicado</strong> (Fusión espacio-temporal de pasadas simultáneas)
            </span>
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer' }}>
            <input
              type="radio"
              name="calMode"
              value="raw"
              checked={calibrationMode === 'raw'}
              onChange={() => onCalibrationModeChange('raw')}
            />
            <span style={{ color: '#0f172a', fontWeight: calibrationMode === 'raw' ? 600 : 400 }}>
              <strong>Crudo</strong> (Detecciones directas sin ponderación ni deduplicación)
            </span>
          </label>
        </div>
      </div>

      {/* DATE RANGE CONTROLS & PRESETS */}
      <div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '8px', alignItems: 'flex-end' }}>
          <label style={{ fontSize: '12px', color: '#475569', display: 'flex', flexDirection: 'column', gap: '3px' }}>
            Desde
            <input
              type="date"
              value={startDate}
              onChange={(e) => onDateRangeChange(e.target.value, endDate)}
              style={{ padding: '5px 8px', border: '1px solid #cbd5e1', borderRadius: '4px', fontSize: '12px' }}
            />
          </label>

          <label style={{ fontSize: '12px', color: '#475569', display: 'flex', flexDirection: 'column', gap: '3px' }}>
            Hasta
            <input
              type="date"
              value={endDate}
              onChange={(e) => onDateRangeChange(startDate, e.target.value)}
              style={{ padding: '5px 8px', border: '1px solid #cbd5e1', borderRadius: '4px', fontSize: '12px' }}
            />
          </label>

          <button
            onClick={onRefresh}
            disabled={isLoading}
            style={{
              padding: '6px 10px',
              background: '#0284c7',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: isLoading ? 'not-allowed' : 'pointer',
              height: '30px',
            }}
          >
            {isLoading ? '...' : 'Actualizar'}
          </button>
        </div>

        {/* Quick presets */}
        <div style={{ display: 'flex', gap: '4px', marginTop: '6px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '11px', color: '#64748b', alignSelf: 'center' }}>Atajos:</span>
          <button
            type="button"
            onClick={() => setPreset('2024_all')}
            style={{ fontSize: '11px', padding: '2px 6px', background: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: '3px', cursor: 'pointer' }}
          >
            Todo 2024
          </button>
          <button
            type="button"
            onClick={() => setPreset('2024_peak')}
            style={{ fontSize: '11px', padding: '2px 6px', background: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: '3px', cursor: 'pointer' }}
          >
            Pico 2024 (Ago-Oct)
          </button>
          <button
            type="button"
            onClick={() => setPreset('2020_peak')}
            style={{ fontSize: '11px', padding: '2px 6px', background: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: '3px', cursor: 'pointer' }}
          >
            Pico 2020 (Récord)
          </button>
          <button
            type="button"
            onClick={() => setPreset('all_history')}
            style={{ fontSize: '11px', padding: '2px 6px', background: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: '3px', cursor: 'pointer' }}
          >
            Serie Completa (2001-2026)
          </button>
        </div>
      </div>

      {/* CALENDAR MATRIX HEATMAP */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
          <span style={{ fontSize: '12px', fontWeight: 600, color: '#1e293b' }}>
            Matriz Anual × Mensual de Focos
          </span>
          <button
            type="button"
            onClick={() => setViewYearRange((prev) => (prev === 'recent' ? 'all' : 'recent'))}
            style={{ fontSize: '11px', background: 'none', border: 'none', color: '#0284c7', cursor: 'pointer', textDecoration: 'underline' }}
          >
            {viewYearRange === 'recent' ? 'Ver todos los años (2001-2026)' : 'Ver recientes (2018-2026)'}
          </button>
        </div>

        {calendarCells.length === 0 ? (
          <div style={{ fontSize: '12px', color: '#64748b', fontStyle: 'italic', padding: '10px 0' }}>
            No hay celdas de calendario disponibles para la consulta actual.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10px', textAlign: 'center' }}>
              <thead>
                <tr>
                  <th style={{ padding: '3px 4px', color: '#64748b', fontWeight: 600, textAlign: 'left' }}>Año</th>
                  {MONTH_NAMES.map((m) => (
                    <th key={m} style={{ padding: '3px 2px', color: '#64748b', fontWeight: 600, minWidth: '22px' }}>
                      {m}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {displayYears.map((year) => {
                  const months = yearsMap.get(year);
                  return (
                    <tr key={year}>
                      <td style={{ padding: '3px 4px', fontWeight: 700, color: '#334155', textAlign: 'left', whiteSpace: 'nowrap' }}>
                        {year}
                      </td>
                      {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => {
                        const cell = months?.get(m);
                        if (!cell) {
                          return (
                            <td key={m} style={{ padding: '2px' }}>
                              <div style={{ height: '20px', background: '#f8fafc', borderRadius: '3px' }} />
                            </td>
                          );
                        }

                        const sevStyle = SEVERITY_COLORS[cell.severity] ?? SEVERITY_COLORS.normal;
                        const isSelected = selectedCellKey === `${year}-${m}`;

                        return (
                          <td key={m} style={{ padding: '2px' }}>
                            <div
                              onClick={() => handleCellClick(year, m)}
                              title={`${MONTH_NAMES[m - 1]} ${year}: ${cell.count} focos | Mediana hist: ${cell.historical_median} | Anomalía: ${cell.anomaly_pct > 0 ? '+' : ''}${cell.anomaly_pct}% (${sevStyle.label})\nHaz clic para filtrar mapa en este mes`}
                              style={{
                                height: '22px',
                                minWidth: '22px',
                                background: cell.count === 0 ? '#f1f5f9' : sevStyle.bg,
                                color: cell.count === 0 ? '#94a3b8' : sevStyle.text,
                                border: isSelected
                                  ? '2px solid #0f172a'
                                  : `1px solid ${sevStyle.border}`,
                                borderRadius: '3px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                cursor: 'pointer',
                                fontWeight: cell.count > 0 ? 700 : 400,
                                fontSize: '10px',
                                transform: isSelected ? 'scale(1.08)' : 'none',
                                transition: 'all 0.1s ease',
                              }}
                            >
                              {cell.count > 0 ? cell.count : '·'}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* SEVERITY COLOR LEGEND */}
      <div style={{ paddingTop: '6px', borderTop: '1px solid #e2e8f0', fontSize: '11px' }}>
        <div style={{ color: '#475569', fontWeight: 600, marginBottom: '4px' }}>
          Nivel de Anomalía Estacional vs Mediana Histórica:
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '4px' }}>
          {(['low', 'normal', 'elevated', 'extreme'] as const).map((sev) => {
            const item = SEVERITY_COLORS[sev];
            return (
              <div key={sev} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span
                  style={{
                    width: '12px',
                    height: '12px',
                    background: item.bg,
                    border: `1px solid ${item.border}`,
                    borderRadius: '3px',
                    display: 'inline-block',
                  }}
                />
                <span style={{ color: '#334155' }}>{item.label}</span>
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: '6px', color: '#64748b', fontSize: '10px', fontStyle: 'italic' }}>
          💡 Haz clic sobre cualquier celda para enfocar automáticamente el mapa sobre ese mes.
        </div>
      </div>
    </section>
  );
}
