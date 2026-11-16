import { useEffect, useState } from 'react';
import type { AoiBounds, CellMonthAoiResponse, CellMonthMapCell, CellMonthMetric } from '../services/apiClient';
import { CellMonthPanel } from './CellMonthPanel';
import { LanguageToggle, useLanguage } from '../i18n/LanguageContext';

/** Rango de la serie armonizada v0.2 (`harmonized.cell_month`). */
export const SERIES_FIRST_MONTH = '2012-01';
export const SERIES_LAST_MONTH = '2026-08';

export interface HarmonizedSidePanelProps {
  bounds: AoiBounds;
  data: CellMonthAoiResponse | null;
  metric: CellMonthMetric;
  selectedCell: CellMonthMapCell | null;
  startDate: string;
  endDate: string;
  isLoading: boolean;
  errorMsg: string | null;
  onMetricChange: (metric: CellMonthMetric) => void;
  onDateRangeChange: (start: string, end: string) => void;
  onRefresh: () => void;
}

function lastDayOfMonth(yyyyMm: string): string {
  const [y, m] = yyyyMm.split('-').map(Number);
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
  return `${yyyyMm}-${String(last).padStart(2, '0')}`;
}

/**
 * Panel lateral conectado SOLO a la tabla armonizada (`/api/cell-month/aoi`):
 * estado de la conexión, selector de rango de meses y `CellMonthPanel`
 * (calendario de percentiles 2012–2026, alertas, inspector de celda y CSV).
 */
export function HarmonizedSidePanel({
  bounds,
  data,
  metric,
  selectedCell,
  startDate,
  endDate,
  isLoading,
  errorMsg,
  onMetricChange,
  onDateRangeChange,
  onRefresh,
}: HarmonizedSidePanelProps) {
  const { lang, t } = useLanguage();
  const es = lang === 'es';
  const [fromMonth, setFromMonth] = useState(startDate.slice(0, 7));
  const [toMonth, setToMonth] = useState(endDate.slice(0, 7));

  // Mantener el selector sincronizado cuando el rango cambia desde el calendario (clic en un mes)
  useEffect(() => setFromMonth(startDate.slice(0, 7)), [startDate]);
  useEffect(() => setToMonth(endDate.slice(0, 7)), [endDate]);

  const rangeInvalid = !fromMonth || !toMonth || fromMonth > toMonth;

  let statusText: string;
  let statusColor: string;
  if (isLoading) {
    statusText = es ? 'Consultando la base armonizada…' : 'Querying the harmonized database…';
    statusColor = '#475569';
  } else if (errorMsg) {
    statusText = errorMsg;
    statusColor = '#b91c1c';
  } else if (data) {
    const source = data.data_source === 'postgres' ? 'PostgreSQL' : es ? 'DATOS SINTÉTICOS (modo stub)' : 'SYNTHETIC DATA (stub mode)';
    statusText = `${es ? 'Conectado' : 'Connected'} · ${source} · ${data.method_version}`;
    statusColor = data.data_source === 'postgres' ? '#15803d' : '#b45309';
  } else {
    statusText = es ? 'Mové o hacé zoom en el mapa para consultar la región visible' : 'Pan or zoom the map to query the visible region';
    statusColor = '#475569';
  }

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
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <h3 style={{ margin: 0, color: '#0f172a', fontSize: '15px' }}>{t.panelMainTitle}</h3>
          <LanguageToggle />
        </div>
        <div style={{ fontSize: '12px', color: statusColor }} role={errorMsg ? 'alert' : 'status'}>
          <strong style={{ color: '#475569' }}>{t.panelStatusLabel}</strong> {statusText}
        </div>
      </div>

      <section style={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '8px', padding: '12px 14px' }}>
        <div style={{ fontSize: '12px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
          {es ? 'Período del mapa y del CSV' : 'Map and CSV period'}
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end', flexWrap: 'wrap', fontSize: '12px' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
            {es ? 'Desde' : 'From'}
            <input type="month" value={fromMonth} min={SERIES_FIRST_MONTH} max={SERIES_LAST_MONTH} onChange={(e) => setFromMonth(e.target.value)} />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
            {es ? 'Hasta' : 'To'}
            <input type="month" value={toMonth} min={SERIES_FIRST_MONTH} max={SERIES_LAST_MONTH} onChange={(e) => setToMonth(e.target.value)} />
          </label>
          <button
            type="button"
            disabled={rangeInvalid || isLoading}
            onClick={() => onDateRangeChange(`${fromMonth}-01`, lastDayOfMonth(toMonth))}
            style={{ padding: '5px 12px', background: '#ea580c', color: 'white', border: 'none', borderRadius: '4px', fontWeight: 700, cursor: rangeInvalid || isLoading ? 'not-allowed' : 'pointer', opacity: rangeInvalid ? 0.5 : 1 }}
          >
            {es ? 'Aplicar' : 'Apply'}
          </button>
          <button
            type="button"
            disabled={isLoading}
            onClick={onRefresh}
            style={{ padding: '5px 10px', background: '#ffffff', color: '#334155', border: '1px solid #cbd5e1', borderRadius: '4px', cursor: isLoading ? 'wait' : 'pointer' }}
          >
            {es ? 'Actualizar' : 'Refresh'}
          </button>
        </div>
        <div style={{ fontSize: '11px', color: '#64748b', marginTop: '6px' }}>
          {es
            ? `Serie disponible: ${SERIES_FIRST_MONTH} a ${SERIES_LAST_MONTH}. El calendario de anomalías siempre usa la serie completa.`
            : `Available series: ${SERIES_FIRST_MONTH} to ${SERIES_LAST_MONTH}. The anomaly calendar always uses the full series.`}
        </div>
        {rangeInvalid && (
          <div style={{ fontSize: '11px', color: '#b91c1c', marginTop: '4px' }}>
            {es ? 'El mes "Desde" debe ser anterior o igual a "Hasta".' : '"From" must be before or equal to "To".'}
          </div>
        )}
      </section>

      <CellMonthPanel
        bounds={bounds}
        data={data}
        metric={metric}
        selectedCell={selectedCell}
        startDate={startDate}
        endDate={endDate}
        onMetricChange={onMetricChange}
        onDateRangeChange={onDateRangeChange}
      />
    </aside>
  );
}
