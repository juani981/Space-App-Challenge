import { useState } from 'react';
import {
  getCellMonthExportCsvUrl,
  type AoiBounds,
  type CellMonthAnomalyCell,
  type CellMonthAoiResponse,
  type CellMonthMapCell,
  type CellMonthMetric,
} from '../services/apiClient';
import { useLanguage } from '../i18n/LanguageContext';

export interface CellMonthPanelProps {
  bounds: AoiBounds;
  data: CellMonthAoiResponse | null;
  metric: CellMonthMetric;
  selectedCell?: CellMonthMapCell | null;
  startDate: string;
  endDate: string;
  onMetricChange: (metric: CellMonthMetric) => void;
  onDateRangeChange: (start: string, end: string) => void;
}

const PERCENTILE_CLASS_STYLE: Record<
  CellMonthAnomalyCell['severity_class'],
  { bg: string; text: string; border: string }
> = {
  lte_50: { bg: '#e0f2fe', text: '#0369a1', border: '#bae6fd' },
  '50_75': { bg: '#fef9c3', text: '#854d0e', border: '#fde047' },
  '75_90': { bg: '#ffedd5', text: '#c2410c', border: '#fdba74' },
  gt_90: { bg: '#fee2e2', text: '#991b1b', border: '#f87171' },
  unavailable: { bg: '#f1f5f9', text: '#64748b', border: '#cbd5e1' },
};

const HATCH_PATTERN =
  'repeating-linear-gradient(45deg, transparent, transparent 3px, rgba(15, 23, 42, 0.14) 3px, rgba(15, 23, 42, 0.14) 5px)';

function buildTooltip(cell: CellMonthAnomalyCell, metric: CellMonthMetric, isEs: boolean): string {
  const val = metric === 'n_eq' ? `${cell.n_eq} n_eq` : `${cell.f_eq} MW (f_eq)`;
  const pct =
    cell.anomaly_available && cell.percentile !== null
      ? `P${Math.round(cell.percentile * 100)}`
      : isEs
      ? `Sin anomalía (<10 años base: ${cell.baseline_years_count})`
      : `No anomaly (<10 baseline yrs: ${cell.baseline_years_count})`;

  const zPart =
    cell.z_robust_log1p !== null
      ? ` | z_rob=${cell.z_robust_log1p.toFixed(2)}`
      : cell.ratio_to_median !== null
      ? ` | ×med=${cell.ratio_to_median.toFixed(2)}`
      : '';

  const flags =
    cell.quality_flags_decoded.length > 0
      ? ` | Flags: ${cell.quality_flags_decoded.map((f) => f.label_es).join(', ')}`
      : '';

  const rec = cell.is_series_record ? (isEs ? ' | ★ Récord serie' : ' | ★ Series record') : '';
  return `${cell.month}: ${val} | ${pct}${zPart}${rec}${flags}`;
}

export function CellMonthPanel({
  bounds,
  data,
  metric,
  selectedCell = null,
  startDate,
  endDate,
  onMetricChange,
  onDateRangeChange,
}: CellMonthPanelProps) {
  const { lang } = useLanguage();
  const isEs = lang === 'es';
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [showFullYears, setShowFullYears] = useState<boolean>(false);

  const byYear = new Map<number, Map<number, CellMonthAnomalyCell>>();
  for (const item of data?.calendar_anomalies ?? []) {
    if (!byYear.has(item.year)) byYear.set(item.year, new Map());
    byYear.get(item.year)!.set(item.month_num, item);
  }
  const years = Array.from(byYear.keys()).sort((a, b) => b - a);
  const visibleYears = showFullYears ? years : years.filter((y) => y >= 2018);

  const monthLabels = isEs
    ? ['E', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
    : ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];

  return (
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
        onClick={() => setIsOpen((p) => !p)}
        style={{
          width: '100%',
          padding: '11px 14px',
          background: '#0f172a',
          color: '#f8fafc',
          border: 'none',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        <div>
          <strong style={{ fontSize: '12.5px', display: 'block' }}>
            {isEs
              ? 'Grilla Armonizada 0,25° (harmonized.cell_month)'
              : '0.25° Harmonized Grid (harmonized.cell_month)'}
          </strong>
          <span style={{ fontSize: '10.5px', color: '#94a3b8' }}>
            {data
              ? `${data.method_version} · ${data.data_source.toUpperCase()} · ${Math.round(data.area_region_km2).toLocaleString()} km²`
              : isEs
              ? 'Cargando serie 2012–2026...'
              : 'Loading 2012–2026 series...'}
          </span>
        </div>
        <span style={{ fontSize: '13px', fontWeight: 700 }}>{isOpen ? '▼' : '▶'}</span>
      </button>

      {isOpen && data && (
        <div style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {/* CONTROLS: Metric Toggle + CSV Option 1 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '6px' }}>
            <div style={{ display: 'flex', gap: '4px' }}>
              {(['n_eq', 'f_eq'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => onMetricChange(m)}
                  style={{
                    padding: '4px 8px',
                    fontSize: '11px',
                    fontWeight: 600,
                    borderRadius: '5px',
                    border: '1px solid #cbd5e1',
                    cursor: 'pointer',
                    background: metric === m ? '#0284c7' : '#f8fafc',
                    color: metric === m ? '#ffffff' : '#334155',
                  }}
                >
                  {m === 'n_eq'
                    ? isEs ? 'Conteo (n_eq)' : 'Count (n_eq)'
                    : isEs ? 'FRP (f_eq MW)' : 'FRP (f_eq MW)'}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() =>
                window.open(
                  getCellMonthExportCsvUrl(bounds, { startDate, endDate }),
                  '_blank',
                )
              }
              style={{
                padding: '4px 9px',
                fontSize: '11px',
                fontWeight: 600,
                borderRadius: '5px',
                border: 'none',
                background: '#0f766e',
                color: '#ffffff',
                cursor: 'pointer',
              }}
            >
              📥 {isEs ? 'CSV cell_month' : 'cell_month CSV'}
            </button>
          </div>

          {/* 4 KPI SUMMARY CARDS */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '6px' }}>
            <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '6px 8px' }}>
              <div style={{ fontSize: '10px', color: '#64748b' }}>n_eq ({isEs ? 'Equiv. Aqua' : 'Aqua-eq'})</div>
              <strong style={{ fontSize: '13px', color: '#0f172a' }}>{data.summary.total_n_eq.toLocaleString()}</strong>
            </div>
            <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '6px 8px' }}>
              <div style={{ fontSize: '10px', color: '#64748b' }}>f_eq / {isEs ? 'Densidad' : 'Density'}</div>
              <strong style={{ fontSize: '13px', color: '#0f172a' }}>
                {data.summary.total_f_eq_mw.toLocaleString()} MW ({data.summary.frp_density_mw_km2.toFixed(3)} MW/km²)
              </strong>
            </div>
            <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '6px 8px' }}>
              <div style={{ fontSize: '10px', color: '#64748b' }}>{isEs ? 'Celdas 0,25° activas' : 'Active 0.25° cells'}</div>
              <strong style={{ fontSize: '13px', color: '#0f172a' }}>{data.summary.active_cells_count}</strong>
            </div>
            <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '6px', padding: '6px 8px' }}>
              <div style={{ fontSize: '10px', color: '#92400e' }}>{isEs ? 'Terra (serie propia)' : 'Terra (separate)'}</div>
              <strong style={{ fontSize: '13px', color: '#78350f' }}>{data.summary.n_terra_separate_series.toLocaleString()}</strong>
            </div>
          </div>

          {/* PERCENTILE ANOMALY MATRIX */}
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: '2px', fontSize: '10px' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', color: '#64748b', paddingRight: '4px' }}>Año</th>
                  {monthLabels.map((lbl, idx) => (
                    <th key={idx} style={{ textAlign: 'center', color: '#64748b', fontWeight: 600 }}>{lbl}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleYears.map((yr) => {
                  const rowMap = byYear.get(yr)!;
                  return (
                    <tr key={yr}>
                      <td style={{ fontWeight: 700, color: '#334155', paddingRight: '4px' }}>{yr}</td>
                      {Array.from({ length: 12 }, (_, idx) => idx + 1).map((mNum) => {
                        const cell = rowMap.get(mNum);
                        if (!cell) {
                          return (
                            <td
                              key={mNum}
                              style={{
                                height: '20px',
                                background: '#f8fafc',
                                border: '1px dashed #e2e8f0',
                                borderRadius: '3px',
                                textAlign: 'center',
                                color: '#cbd5e1',
                              }}
                              title={`${yr}-${String(mNum).padStart(2, '0')}: 0`}
                            >
                              ·
                            </td>
                          );
                        }
                        const st = PERCENTILE_CLASS_STYLE[cell.severity_class];
                        const padM = String(mNum).padStart(2, '0');
                        const lastD = new Date(yr, mNum, 0).getDate();
                        return (
                          <td
                            key={mNum}
                            onClick={() => onDateRangeChange(`${yr}-${padM}-01`, `${yr}-${padM}-${String(lastD).padStart(2, '0')}`)}
                            title={buildTooltip(cell, metric, isEs)}
                            style={{
                              height: '20px',
                              minWidth: '22px',
                              backgroundColor: st.bg,
                              backgroundImage: cell.excluded_from_baseline ? HATCH_PATTERN : 'none',
                              color: st.text,
                              border: `1px solid ${st.border}`,
                              borderRadius: '3px',
                              textAlign: 'center',
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
                          >
                            {cell.is_series_record ? '★' : cell.anomaly_available && cell.percentile !== null ? Math.round(cell.percentile * 100) : '—'}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* LEGEND & FULL SERIES TOGGLE */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '6px', fontSize: '10px', color: '#475569' }}>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
              <span>≤50%</span>
              <span style={{ background: '#fef9c3', padding: '1px 4px', borderRadius: '3px' }}>50–75%</span>
              <span style={{ background: '#ffedd5', padding: '1px 4px', borderRadius: '3px' }}>75–90%</span>
              <span style={{ background: '#fee2e2', padding: '1px 4px', borderRadius: '3px' }}>&gt;90%</span>
              <span>★ {isEs ? 'Récord' : 'Record'}</span>
              <span style={{ backgroundImage: HATCH_PATTERN, padding: '1px 4px', border: '1px solid #cbd5e1', borderRadius: '3px' }}>
                {isEs ? 'Trama: Flag calidad' : 'Hatch: Quality flag'}
              </span>
            </div>

            {years.length > visibleYears.length || showFullYears ? (
              <button
                type="button"
                onClick={() => setShowFullYears((p) => !p)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#0284c7',
                  fontSize: '10.5px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                {showFullYears ? (isEs ? 'Ver recientes' : 'Recent only') : (isEs ? 'Ver 2012–2026' : 'Show 2012–2026')}
              </button>
            ) : null}
          </div>

          {/* SELECTED 0.25° CELL INSPECTOR */}
          {selectedCell && (
            <div
              style={{
                background: '#f8fafc',
                border: '1px solid #cbd5e1',
                borderRadius: '6px',
                padding: '8px 10px',
                fontSize: '11px',
                color: '#1e293b',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <strong>
                  {isEs ? 'Celda Seleccionada' : 'Selected Cell'} #{selectedCell.cell_id}
                </strong>
                <span style={{ fontFamily: 'monospace', color: '#475569' }}>
                  {selectedCell.lat_center.toFixed(3)}°, {selectedCell.lon_center.toFixed(3)}° · {selectedCell.cell_area_km2.toFixed(0)} km²
                </span>
              </div>
              <div>
                n_eq: <strong>{selectedCell.n_eq}</strong> | f_eq: <strong>{selectedCell.f_eq} MW</strong> | Terra:{' '}
                <strong>{selectedCell.n_terra}</strong> | {isEs ? 'Meses activos' : 'Active months'}:{' '}
                <strong>{selectedCell.months_active}</strong>
              </div>
              <div style={{ color: '#475569', marginTop: '2px' }}>
                {isEs ? 'Procedencia' : 'Sensors'}: {selectedCell.sensors.join(', ')}
                {selectedCell.quality_flags_decoded.length > 0 &&
                  ` · Flags: ${selectedCell.quality_flags_decoded.map((f) => f.label_es).join(', ')}`}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
