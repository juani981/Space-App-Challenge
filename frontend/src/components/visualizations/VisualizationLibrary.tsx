import type {
  BarSeriesData,
  DualCompareData,
  GaugeMeterData,
  HistogramData,
  KeyValueTableData,
  QuantileBandData,
  SidePanelVisualizationContext,
  SparklineTrendData,
  StackedShareData,
  VisualizationSlotSpec,
} from './contracts';

const SEVERITY_COLORS: Record<string, string> = {
  low: '#38bdf8',
  normal: '#94a3b8',
  elevated: '#f97316',
  extreme: '#dc2626',
};

// ---------------------------------------------------------------------------
// 1. BAR SERIES WIDGET (Vertical Bars + Optional Baseline Line)
// ---------------------------------------------------------------------------
export function BarSeriesWidget({ data }: { data: BarSeriesData }) {
  if (!data.bars.length) return <EmptyNotice />;
  const maxVal = Math.max(
    1,
    ...data.bars.map((b) => Math.max(b.value, b.baseline ?? 0)),
  );
  const w = 320;
  const h = 115;
  const padB = 20;
  const padT = 10;
  const chartH = h - padB - padT;
  const slotW = w / data.bars.length;

  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
        {data.bars.map((b, i) => {
          const barH = Math.max(2, (b.value / maxVal) * chartH);
          const x = i * slotW + slotW * 0.18;
          const bw = slotW * 0.64;
          const y = padT + (chartH - barH);
          const fill = b.severity ? SEVERITY_COLORS[b.severity] : '#ea580c';
          const baseY =
            b.baseline !== undefined ? padT + (chartH - (b.baseline / maxVal) * chartH) : null;

          return (
            <g key={b.label}>
              <rect x={x} y={y} width={bw} height={barH} rx={2} fill={fill}>
                <title>
                  {b.label}: {b.value} {data.unit ?? ''}
                  {b.baseline !== undefined ? ` (Base: ${b.baseline})` : ''}
                </title>
              </rect>
              {baseY !== null && (
                <line
                  x1={i * slotW + 2}
                  x2={(i + 1) * slotW - 2}
                  y1={baseY}
                  y2={baseY}
                  stroke="#0f172a"
                  strokeWidth={1.5}
                  strokeDasharray="2,2"
                />
              )}
              <text
                x={i * slotW + slotW / 2}
                y={h - 5}
                textAnchor="middle"
                fontSize="8.5"
                fill="#475569"
              >
                {b.label}
              </text>
            </g>
          );
        })}
      </svg>
      {data.baselineLabel && (
        <div style={{ fontSize: '10px', color: '#64748b', marginTop: '4px', display: 'flex', justifyContent: 'space-between' }}>
          <span>--- {data.baselineLabel}</span>
          <span>Máx: {maxVal.toFixed(1)} {data.unit ?? ''}</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2. HISTOGRAM WIDGET (Distribution Bins + Active Point Highlight)
// ---------------------------------------------------------------------------
export function HistogramWidget({ data }: { data: HistogramData }) {
  if (!data.bins.length) return <EmptyNotice />;
  const maxCount = Math.max(1, ...data.bins.map((b) => b.count));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${data.bins.length}, 1fr)`, gap: '6px', alignItems: 'end', height: '78px', paddingTop: '12px' }}>
        {data.bins.map((bin) => {
          const heightPct = Math.max(6, Math.round((bin.count / maxCount) * 100));
          return (
            <div key={bin.label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
              <span style={{ fontSize: '9px', color: bin.highlight ? '#b91c1c' : '#64748b', fontWeight: bin.highlight ? 700 : 400, marginBottom: '2px' }}>
                {bin.count}
              </span>
              <div
                style={{
                  width: '100%',
                  height: `${heightPct}%`,
                  background: bin.highlight ? '#dc2626' : '#cbd5e1',
                  border: bin.highlight ? '1.5px solid #7f1d1d' : '1px solid #94a3b8',
                  borderRadius: '3px 3px 0 0',
                }}
              />
            </div>
          );
        })}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${data.bins.length}, 1fr)`, gap: '4px', textAlign: 'center' }}>
        {data.bins.map((bin) => (
          <span key={bin.label} style={{ fontSize: '9px', color: bin.highlight ? '#991b1b' : '#475569', fontWeight: bin.highlight ? 700 : 400 }}>
            {bin.label}
          </span>
        ))}
      </div>
      {data.activeValueLabel && (
        <div style={{ fontSize: '10px', color: '#991b1b', fontWeight: 600 }}>
          ● Foco seleccionado: {data.activeValueLabel}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. QUANTILE BOX WIDGET ([Min, P25, Median, P75, Max] + Current Pin)
// ---------------------------------------------------------------------------
export function QuantileBoxWidget({ data }: { data: QuantileBandData }) {
  const span = Math.max(0.001, data.max - data.min);
  const toPct = (v: number) => Math.min(100, Math.max(0, ((v - data.min) / span) * 100));

  const p25Pct = toPct(data.p25);
  const medPct = toPct(data.median);
  const p75Pct = toPct(data.p75);
  const curPct = data.current !== null ? toPct(data.current) : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ position: 'relative', height: '26px', display: 'flex', alignItems: 'center' }}>
        {/* Whisker line Min -> Max */}
        <div style={{ position: 'absolute', left: 0, right: 0, height: '2px', background: '#94a3b8' }} />
        {/* Interquartile Box P25 -> P75 */}
        <div
          style={{
            position: 'absolute',
            left: `${p25Pct}%`,
            width: `${Math.max(2, p75Pct - p25Pct)}%`,
            height: '16px',
            background: '#fed7aa',
            border: '1.5px solid #ea580c',
            borderRadius: '3px',
          }}
        />
        {/* Median Line P50 */}
        <div
          style={{
            position: 'absolute',
            left: `${medPct}%`,
            width: '2.5px',
            height: '20px',
            background: '#9a3412',
          }}
          title={`Mediana (P50): ${data.median} ${data.unit ?? ''}`}
        />
        {/* Active Point Marker */}
        {curPct !== null && (
          <div
            style={{
              position: 'absolute',
              left: `calc(${curPct}% - 6px)`,
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              background: '#dc2626',
              border: '2px solid #ffffff',
              boxShadow: '0 0 0 1.5px #7f1d1d',
            }}
            title={`Valor actual: ${data.current} ${data.unit ?? ''}`}
          />
        )}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#475569', fontFamily: 'monospace' }}>
        <span>Mín: {data.min.toFixed(1)}</span>
        <span>P25: {data.p25.toFixed(1)}</span>
        <strong>P50: {data.median.toFixed(1)}</strong>
        <span>P75: {data.p75.toFixed(1)}</span>
        <span>Máx: {data.max.toFixed(1)} {data.unit ?? ''}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4. DUAL SENSOR COMPARE WIDGET (Before vs After / Raw vs Calibrated)
// ---------------------------------------------------------------------------
export function DualSensorCompareWidget({ data }: { data: DualCompareData }) {
  const maxVal = Math.max(0.01, data.leftValue, data.rightValue);
  const leftPct = Math.round((data.leftValue / maxVal) * 100);
  const rightPct = Math.round((data.rightValue / maxVal) * 100);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '11px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
        <div style={{ background: '#f8fafc', padding: '8px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
          <div style={{ fontSize: '10px', color: '#64748b' }}>{data.leftLabel}</div>
          <strong style={{ fontSize: '14px', color: '#334155' }}>
            {data.leftValue.toFixed(1)} {data.unit ?? ''}
          </strong>
          <div style={{ height: '5px', background: '#e2e8f0', borderRadius: '3px', marginTop: '5px' }}>
            <div style={{ width: `${leftPct}%`, height: '100%', background: '#64748b', borderRadius: '3px' }} />
          </div>
        </div>

        <div style={{ background: '#fff7ed', padding: '8px', borderRadius: '6px', border: '1px solid #fed7aa' }}>
          <div style={{ fontSize: '10px', color: '#9a3412' }}>{data.rightLabel}</div>
          <strong style={{ fontSize: '14px', color: '#ea580c' }}>
            {data.rightValue.toFixed(1)} {data.unit ?? ''}
          </strong>
          <div style={{ height: '5px', background: '#ffedd5', borderRadius: '3px', marginTop: '5px' }}>
            <div style={{ width: `${rightPct}%`, height: '100%', background: '#ea580c', borderRadius: '3px' }} />
          </div>
        </div>
      </div>
      {data.caption && <div style={{ fontSize: '10px', color: '#64748b' }}>{data.caption}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 5. STACKED SHARE WIDGET (100% Proportion Bar + Legend)
// ---------------------------------------------------------------------------
export function StackedShareWidget({ data }: { data: StackedShareData }) {
  const total = data.segments.reduce((acc, s) => acc + s.value, 0);
  if (total <= 0) return <EmptyNotice />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', height: '14px', borderRadius: '999px', overflow: 'hidden', border: '1px solid #cbd5e1' }}>
        {data.segments.map((seg) => {
          const pct = (seg.value / total) * 100;
          if (pct <= 0) return null;
          return (
            <div
              key={seg.label}
              style={{ width: `${pct}%`, background: seg.color }}
              title={`${seg.label}: ${seg.value} (${pct.toFixed(1)}%)`}
            />
          );
        })}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', fontSize: '10px', color: '#334155' }}>
        {data.segments.map((seg) => {
          const pct = Math.round((seg.value / total) * 100);
          return (
            <span key={seg.label} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: seg.color, display: 'inline-block' }} />
              {seg.label}: <strong>{seg.value}</strong> ({pct}%)
            </span>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 6. GAUGE METER WIDGET (Linear Threshold Meter)
// ---------------------------------------------------------------------------
export function GaugeMeterWidget({ data }: { data: GaugeMeterData }) {
  const span = Math.max(0.001, data.max - data.min);
  const pct = Math.min(100, Math.max(0, ((data.value - data.min) / span) * 100));
  const danger = data.thresholds?.danger ?? data.max * 0.75;
  const warn = data.thresholds?.warn ?? data.max * 0.45;
  const barColor = data.value >= danger ? '#dc2626' : data.value >= warn ? '#ea580c' : '#16a34a';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', fontSize: '12px' }}>
        <strong style={{ color: barColor, fontSize: '15px' }}>
          {data.value.toFixed(1)} {data.unit ?? ''}
        </strong>
        {data.statusLabel && (
          <span style={{ fontSize: '10px', fontWeight: 700, color: barColor }}>
            {data.statusLabel}
          </span>
        )}
      </div>
      <div style={{ height: '10px', background: '#e2e8f0', borderRadius: '999px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: barColor, transition: 'width 0.2s ease' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: '#64748b' }}>
        <span>{data.min} {data.unit ?? ''}</span>
        <span>{data.max} {data.unit ?? ''}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 7. SPARKLINE TREND WIDGET (Continuous SVG Trend Curve)
// ---------------------------------------------------------------------------
export function SparklineTrendWidget({ data }: { data: SparklineTrendData }) {
  if (data.points.length < 2) return <EmptyNotice />;
  const w = 300;
  const h = 65;
  const pad = 8;
  const vals = data.points.map((p) => p.value);
  const minV = Math.min(...vals);
  const maxV = Math.max(minV + 1, ...vals);

  const coords = data.points.map((p, idx) => {
    const x = pad + (idx / (data.points.length - 1)) * (w - pad * 2);
    const y = h - pad - ((p.value - minV) / (maxV - minV)) * (h - pad * 2);
    return { x, y, label: p.label, value: p.value };
  });

  const polylinePoints = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');

  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
      <polyline
        fill="none"
        stroke="#ea580c"
        strokeWidth="2"
        points={polylinePoints}
      />
      {coords.map((c, idx) => (
        <circle
          key={c.label}
          cx={c.x}
          cy={c.y}
          r={idx === data.highlightIndex ? 4 : 2}
          fill={idx === data.highlightIndex ? '#991b1b' : '#ea580c'}
        >
          <title>{`${c.label}: ${c.value} ${data.unit ?? ''}`}</title>
        </circle>
      ))}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// 8. KEY-VALUE TABLE WIDGET (Structured Audit Rows)
// ---------------------------------------------------------------------------
export function KeyValueTableWidget({ data }: { data: KeyValueTableData }) {
  if (!data.rows.length) return <EmptyNotice />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
      {data.rows.map((row) => (
        <div
          key={row.label}
          style={{
            padding: '6px 8px',
            background: row.accent ? '#eff6ff' : '#f8fafc',
            border: `1px solid ${row.accent ? '#bfdbfe' : '#e2e8f0'}`,
            borderRadius: '4px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '11px',
          }}
        >
          <span style={{ color: row.accent ? '#1e40af' : '#475569', fontWeight: 500 }}>{row.label}:</span>
          <strong style={{ color: row.accent ? '#1e3a8a' : '#0f172a' }}>{row.value}</strong>
        </div>
      ))}
    </div>
  );
}

function EmptyNotice() {
  return (
    <div style={{ fontSize: '11px', color: '#94a3b8', fontStyle: 'italic', padding: '4px 0' }}>
      Selecciona un foco o consulta el AOI para poblar esta visualización.
    </div>
  );
}

// ---------------------------------------------------------------------------
// UNIVERSAL DISPATCHER FOR CONFIGURED PANEL SLOTS
// ---------------------------------------------------------------------------
export function VisualizationModuleRenderer({
  slot,
  context,
}: {
  slot: VisualizationSlotSpec;
  context: SidePanelVisualizationContext;
}) {
  if (!slot.enabled) return null;

  let body: JSX.Element | null = null;

  switch (slot.kind) {
    case 'bar_series': {
      const data = slot.resolveData(context);
      body = data ? <BarSeriesWidget data={data} /> : <EmptyNotice />;
      break;
    }
    case 'histogram': {
      const data = slot.resolveData(context);
      body = data ? <HistogramWidget data={data} /> : <EmptyNotice />;
      break;
    }
    case 'quantile_band': {
      const data = slot.resolveData(context);
      body = data ? <QuantileBoxWidget data={data} /> : <EmptyNotice />;
      break;
    }
    case 'dual_compare': {
      const data = slot.resolveData(context);
      body = data ? <DualSensorCompareWidget data={data} /> : <EmptyNotice />;
      break;
    }
    case 'stacked_share': {
      const data = slot.resolveData(context);
      body = data ? <StackedShareWidget data={data} /> : <EmptyNotice />;
      break;
    }
    case 'gauge_meter': {
      const data = slot.resolveData(context);
      body = data ? <GaugeMeterWidget data={data} /> : <EmptyNotice />;
      break;
    }
    case 'sparkline': {
      const data = slot.resolveData(context);
      body = data ? <SparklineTrendWidget data={data} /> : <EmptyNotice />;
      break;
    }
    case 'kv_table': {
      const data = slot.resolveData(context);
      body = data ? <KeyValueTableWidget data={data} /> : <EmptyNotice />;
      break;
    }
  }

  return (
    <div
      style={{
        padding: '10px 12px',
        background: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: '6px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
      }}
    >
      <div>
        <strong style={{ fontSize: '12px', color: '#0f172a', display: 'block' }}>{slot.title}</strong>
        {slot.subtitle && <span style={{ fontSize: '10px', color: '#64748b' }}>{slot.subtitle}</span>}
      </div>
      {body}
    </div>
  );
}
