import React from 'react';
import type { MonthlyCalendarCell } from '../services/apiClient';

export interface SeasonalAnomalyBarChartProps {
  calendarCells: MonthlyCalendarCell[];
  year?: number;
}

const MONTH_LABELS = ['E', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];

export function SeasonalAnomalyBarChart({
  calendarCells,
  year = 2024,
}: SeasonalAnomalyBarChartProps) {
  // Filter cells for the requested year
  const yearCells = calendarCells.filter((c) => c.year === year);
  const cellByMonth = new Map<number, MonthlyCalendarCell>();
  for (const c of yearCells) {
    cellByMonth.set(c.month, c);
  }

  // Determine scale maximum (highest count or median)
  let maxVal = 10;
  for (let m = 1; m <= 12; m++) {
    const c = cellByMonth.get(m);
    if (c) {
      if (c.count > maxVal) maxVal = c.count;
      if (c.historical_median > maxVal) maxVal = c.historical_median;
    }
  }
  maxVal = Math.ceil(maxVal * 1.15); // Add headroom

  const chartWidth = 320;
  const chartHeight = 150;
  const paddingLeft = 32;
  const paddingRight = 12;
  const paddingTop = 18;
  const paddingBottom = 24;

  const plotWidth = chartWidth - paddingLeft - paddingRight;
  const plotHeight = chartHeight - paddingTop - paddingBottom;
  const colWidth = plotWidth / 12;
  const barWidth = Math.max(colWidth * 0.65, 8);

  const getSeverityColor = (sev: string) => {
    switch (sev) {
      case 'low': return '#38bdf8'; // Sky blue
      case 'normal': return '#eab308'; // Amber/Yellow
      case 'elevated': return '#f97316'; // Orange
      case 'extreme': return '#ef4444'; // Red
      default: return '#94a3b8';
    }
  };

  return (
    <div style={{ background: '#ffffff', borderRadius: '6px', padding: '10px', border: '1px solid #e2e8f0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <strong style={{ fontSize: '12px', color: '#0f172a' }}>
          Anomalía Estacional vs Mediana Histórica ({year})
        </strong>
        <span style={{ fontSize: '10px', color: '#64748b' }}>
          Escala máx: {maxVal} focos
        </span>
      </div>

      <svg width="100%" height={chartHeight} viewBox={`0 0 ${chartWidth} ${chartHeight}`} style={{ overflow: 'visible' }}>
        {/* Y-axis grid lines */}
        {[0, 0.5, 1.0].map((ratio) => {
          const y = paddingTop + plotHeight * (1 - ratio);
          const val = Math.round(maxVal * ratio);
          return (
            <g key={ratio}>
              <line
                x1={paddingLeft}
                y1={y}
                x2={chartWidth - paddingRight}
                y2={y}
                stroke="#f1f5f9"
                strokeWidth="1"
              />
              <text
                x={paddingLeft - 4}
                y={y + 3}
                textAnchor="end"
                fontSize="8"
                fill="#94a3b8"
                fontFamily="sans-serif"
              >
                {val}
              </text>
            </g>
          );
        })}

        {/* 12 Monthly Bars and Median markers */}
        {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => {
          const cell = cellByMonth.get(m);
          const count = cell?.count ?? 0;
          const median = cell?.historical_median ?? 0;
          const severity = cell?.severity ?? 'normal';
          const anomalyPct = cell?.anomaly_pct ?? 0;

          const barH = (count / maxVal) * plotHeight;
          const x = paddingLeft + (m - 1) * colWidth + (colWidth - barWidth) / 2;
          const y = paddingTop + plotHeight - barH;

          // Median line position
          const medianY = paddingTop + plotHeight - (median / maxVal) * plotHeight;

          return (
            <g key={m}>
              {/* Monthly Count Bar */}
              <rect
                x={x}
                y={y}
                width={barWidth}
                height={Math.max(barH, 1)}
                fill={getSeverityColor(severity)}
                rx="2"
                opacity={count > 0 ? 0.9 : 0.3}
              >
                <title>
                  {`${MONTH_LABELS[m - 1]}: ${count} focos (Mediana: ${median}, Anomalía: ${anomalyPct > 0 ? '+' : ''}${anomalyPct}%)`}
                </title>
              </rect>

              {/* Historical Median Indicator Marker */}
              {median > 0 && (
                <line
                  x1={x - 2}
                  y1={medianY}
                  x2={x + barWidth + 2}
                  y2={medianY}
                  stroke="#1e3a8a"
                  strokeWidth="2"
                  strokeDasharray="2, 1"
                >
                  <title>{`Mediana Histórica: ${median} focos`}</title>
                </line>
              )}

              {/* Month label on X axis */}
              <text
                x={x + barWidth / 2}
                y={chartHeight - 6}
                textAnchor="middle"
                fontSize="9"
                fill="#64748b"
                fontWeight={count > 0 ? 700 : 400}
              >
                {MONTH_LABELS[m - 1]}
              </text>
            </g>
          );
        })}
      </svg>

      {/* CHART LEGEND */}
      <div style={{ display: 'flex', gap: '12px', marginTop: '6px', fontSize: '10px', color: '#64748b', justifyContent: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '8px', height: '8px', background: '#f97316', borderRadius: '2px', display: 'inline-block' }} />
          <span>Focos Detectados ({year})</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '12px', height: '2px', background: '#1e3a8a', display: 'inline-block', borderTop: '2px dashed #1e3a8a' }} />
          <span>Mediana Histórica (2001-2026)</span>
        </div>
      </div>
    </div>
  );
}
