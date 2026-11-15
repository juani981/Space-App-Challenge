import { useState } from 'react';
import { CenteredAoiMap } from './components/CenteredAoiMap';
import { fetchAoi, type AoiBounds, type AoiResponse } from './services/apiClient';

export default function App() {
  const [bounds, setBounds] = useState<AoiBounds>({
    minLon: -65.0,
    minLat: -35.0,
    maxLon: -58.0,
    maxLat: -29.0,
  });
  const [backendData, setBackendData] = useState<AoiResponse | null>(null);
  const [status, setStatus] = useState<string>('Idle — Drag or zoom map to frame your AOI, then click "Query AOI"');

  async function handleQueryAoi() {
    setStatus('Loading...');
    try {
      const res = await fetchAoi(bounds);
      setBackendData(res);
      setStatus(`Connected — ${res.hotspots.length} stub hotspots loaded`);
    } catch (err) {
      setStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', height: '100vh' }}>
      {/* LEFT BLOCK: Centered-Box Map + Live Coordinate Readout Bar */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <div
          style={{
            padding: '10px 14px',
            background: '#1e293b',
            color: '#f8fafc',
            display: 'flex',
            gap: '14px',
            alignItems: 'center',
            flexWrap: 'wrap',
          }}
        >
          <strong>Centered AOI Bounds:</strong>
          <span style={{ fontSize: '13px', fontFamily: 'monospace', background: '#0f172a', padding: '4px 8px', borderRadius: '4px' }}>
            minLon: {bounds.minLon.toFixed(4)} | minLat: {bounds.minLat.toFixed(4)} | maxLon: {bounds.maxLon.toFixed(4)} | maxLat: {bounds.maxLat.toFixed(4)}
          </span>
          <button
            onClick={handleQueryAoi}
            style={{
              padding: '6px 12px',
              background: '#ea580c',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            Query AOI
          </button>
          <span style={{ fontSize: '12px', opacity: 0.8 }}>
            (Drag or zoom the map — the orange box stays centered)
          </span>
        </div>

        <div style={{ flex: 1 }}>
          <CenteredAoiMap
            onBoundsChange={setBounds}
            hotspots={backendData?.hotspots}
          />
        </div>
      </div>

      {/* RIGHT BLOCK: Backend Response & Future Calendar Slot */}
      <div style={{ padding: '20px', borderLeft: '1px solid #cbd5e1', background: '#f8fafc', overflowY: 'auto' }}>
        <h3 style={{ marginTop: 0 }}>Backend Interface Panel</h3>
        <p style={{ fontSize: '14px' }}>
          <strong>Status:</strong> {status}
        </p>

        <h4>Response from FastAPI (<code>/api/aoi</code>):</h4>
        <pre style={{ background: '#0f172a', color: '#38bdf8', padding: '12px', borderRadius: '6px', overflowX: 'auto', maxHeight: '340px' }}>
          {backendData ? JSON.stringify(backendData, null, 2) : '// No request sent yet'}
        </pre>

        <div style={{ marginTop: '24px', padding: '16px', border: '1px dashed #94a3b8', borderRadius: '6px', color: '#475569', fontSize: '13px' }}>
          <strong>Reserved Slot:</strong>
          <ul style={{ margin: '8px 0 0 16px', padding: 0 }}>
            <li>Burning Activity Calendar (Year × Month Heatmap)</li>
            <li>CSV Export Button</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
