import { useState } from 'react';
import { CenteredAoiMap } from './components/CenteredAoiMap';
import { HotspotSidePanel } from './components/HotspotSidePanel';
import { fetchAoi, type AoiBounds, type AoiResponse, type UnifiedHotspot } from './services/apiClient';

export default function App() {
  const [bounds, setBounds] = useState<AoiBounds>({
    minLon: -65.0,
    minLat: -35.0,
    maxLon: -58.0,
    maxLat: -29.0,
  });
  const [backendData, setBackendData] = useState<AoiResponse | null>(null);
  const [selectedHotspot, setSelectedHotspot] = useState<UnifiedHotspot | null>(null);
  const [status, setStatus] = useState<string>('Inactivo — Arrastra el mapa y pulsa "Query AOI"');

  async function handleQueryAoi() {
    setStatus('Cargando...');
    try {
      const res = await fetchAoi(bounds);
      setBackendData(res);
      setSelectedHotspot(res.hotspots[0] ?? null);
      setStatus('Conectado al Backend');
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
            (Haz clic en cualquier punto rojo para ver todos sus datos a la derecha)
          </span>
        </div>

        <div style={{ flex: 1 }}>
          <CenteredAoiMap
            onBoundsChange={setBounds}
            hotspots={backendData?.hotspots}
            selectedHotspot={selectedHotspot}
            onSelectHotspot={setSelectedHotspot}
          />
        </div>
      </div>

      {/* RIGHT BLOCK: Full Point Inspector + Calendar UI Mock + Collapsible WIP Analysis */}
      <HotspotSidePanel
        status={status}
        totalHotspots={backendData?.hotspots.length ?? 0}
        selectedHotspot={selectedHotspot}
      />
    </div>
  );
}
