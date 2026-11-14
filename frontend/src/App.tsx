import { useState } from 'react';
import { MapContainer, TileLayer, Rectangle, useMapEvents } from 'react-leaflet';
import type { LatLngBoundsExpression } from 'leaflet';
import { fetchAoi, type AoiBounds, type AoiResponse } from './services/apiClient';

/**
 * Listens for 2 map clicks to define opposite corners of the AOI bounding box.
 */
function BoxClickSelector({ onSelectBounds }: { onSelectBounds: (b: AoiBounds) => void }) {
  const [firstCorner, setFirstCorner] = useState<[number, number] | null>(null);

  useMapEvents({
    click(e) {
      const { lat, lng } = e.latlng;
      if (!firstCorner) {
        setFirstCorner([lat, lng]);
      } else {
        const [lat1, lon1] = firstCorner;
        onSelectBounds({
          minLon: Number(Math.min(lon1, lng).toFixed(4)),
          minLat: Number(Math.min(lat1, lat).toFixed(4)),
          maxLon: Number(Math.max(lon1, lng).toFixed(4)),
          maxLat: Number(Math.max(lat1, lat).toFixed(4)),
        });
        setFirstCorner(null);
      }
    },
  });

  return null;
}

export default function App() {
  const [bounds, setBounds] = useState<AoiBounds>({
    minLon: -65.0,
    minLat: -35.0,
    maxLon: -58.0,
    maxLat: -29.0,
  });
  const [backendData, setBackendData] = useState<AoiResponse | null>(null);
  const [status, setStatus] = useState<string>('Idle — Click "Query AOI" to test backend connection');

  const leafletBounds: LatLngBoundsExpression = [
    [bounds.minLat, bounds.minLon],
    [bounds.maxLat, bounds.maxLon],
  ];

  async function handleQueryAoi() {
    setStatus('Loading...');
    try {
      const res = await fetchAoi(bounds);
      setBackendData(res);
      setStatus('Connected to Backend');
    } catch (err) {
      setStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', height: '100vh' }}>
      {/* LEFT BLOCK: Live Leaflet Map + Coordinate Inputs */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '10px 14px', background: '#1e293b', color: '#f8fafc', display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <strong>AOI Bounds:</strong>
          {(['minLon', 'minLat', 'maxLon', 'maxLat'] as const).map((key) => (
            <label key={key} style={{ fontSize: '13px' }}>
              {key}:{' '}
              <input
                type="number"
                step="0.5"
                value={bounds[key]}
                onChange={(e) => setBounds({ ...bounds, [key]: parseFloat(e.target.value) || 0 })}
                style={{ width: '72px', padding: '2px 4px' }}
              />
            </label>
          ))}
          <button
            onClick={handleQueryAoi}
            style={{ padding: '6px 12px', background: '#ea580c', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600 }}
          >
            Query AOI
          </button>
          <span style={{ fontSize: '12px', opacity: 0.8 }}>
            (Tip: Click any 2 corners on the map to redraw box)
          </span>
        </div>

        <div style={{ flex: 1 }}>
          <MapContainer center={[-32.0, -61.5]} zoom={5} style={{ height: '100%', width: '100%' }}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <Rectangle bounds={leafletBounds} pathOptions={{ color: '#ea580c', weight: 2 }} />
            <BoxClickSelector onSelectBounds={setBounds} />
          </MapContainer>
        </div>
      </div>

      {/* RIGHT BLOCK: Backend Response & Future Calendar Slot */}
      <div style={{ padding: '20px', borderLeft: '1px solid #cbd5e1', background: '#f8fafc' }}>
        <h3 style={{ marginTop: 0 }}>Backend Interface Panel</h3>
        <p style={{ fontSize: '14px' }}>
          <strong>Status:</strong> {status}
        </p>

        <h4>Response from FastAPI (<code>/api/aoi</code>):</h4>
        <pre style={{ background: '#0f172a', color: '#38bdf8', padding: '12px', borderRadius: '6px', overflowX: 'auto' }}>
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
