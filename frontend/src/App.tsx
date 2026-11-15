import { useCallback, useEffect, useState } from 'react';
import { CenteredAoiMap, type MapRenderMode } from './components/CenteredAoiMap';
import { HotspotSidePanel } from './components/HotspotSidePanel';
import {
  fetchAoi,
  type AoiBounds,
  type AoiResponse,
  type CalibrationMode,
  type UnifiedHotspot,
} from './services/apiClient';

export default function App() {
  const [bounds, setBounds] = useState<AoiBounds>({
    minLon: -65.0,
    minLat: -35.0,
    maxLon: -58.0,
    maxLat: -29.0,
  });

  const [startDate, setStartDate] = useState<string>('2024-01-01');
  const [endDate, setEndDate] = useState<string>('2024-12-31');
  const [calibrationMode, setCalibrationMode] = useState<CalibrationMode>('area_weighted');
  const [mapRenderMode, setMapRenderMode] = useState<MapRenderMode>('harmonized');

  const [backendData, setBackendData] = useState<AoiResponse | null>(null);
  const [selectedHotspot, setSelectedHotspot] = useState<UnifiedHotspot | null>(null);
  const [status, setStatus] = useState<string>('Inactivo — Pulsa "Consultar AOI" o ajusta el mapa');
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const executeQuery = useCallback(
    async (
      targetBounds = bounds,
      start = startDate,
      end = endDate,
      calMode = calibrationMode,
    ) => {
      setIsLoading(true);
      setStatus('Consultando API y aplicando armonización científica...');
      try {
        const res = await fetchAoi(targetBounds, {
          startDate: start,
          endDate: end,
          calibrationMode: calMode,
        });
        setBackendData(res);
        setSelectedHotspot(res.hotspots[0] ?? null);
        setStatus(
          `Conectado — Modo: ${res.calibration_mode} | Fuente: ${res.data_source.toUpperCase()}`
        );
      } catch (err) {
        setStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setIsLoading(false);
      }
    },
    [bounds, startDate, endDate, calibrationMode]
  );

  useEffect(() => {
    executeQuery();
  }, []);

  const handleDateRangeChange = (newStart: string, newEnd: string) => {
    setStartDate(newStart);
    setEndDate(newEnd);
    executeQuery(bounds, newStart, newEnd, calibrationMode);
  };

  const handleCalibrationModeChange = (newMode: CalibrationMode) => {
    setCalibrationMode(newMode);
    executeQuery(bounds, startDate, endDate, newMode);
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.9fr 1.1fr', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      {/* LEFT BLOCK: Centered-Box Map + Live Coordinate & Mode Bar */}
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0 }}>
        <div
          style={{
            padding: '8px 14px',
            background: '#1e293b',
            color: '#f8fafc',
            display: 'flex',
            gap: '12px',
            alignItems: 'center',
            flexWrap: 'wrap',
            zIndex: 10,
          }}
        >
          <strong style={{ fontSize: '13px' }}>AOI Centrada:</strong>
          <span
            style={{
              fontSize: '11px',
              fontFamily: 'monospace',
              background: '#0f172a',
              padding: '3px 8px',
              borderRadius: '4px',
            }}
          >
            lon: [{bounds.minLon.toFixed(3)}, {bounds.maxLon.toFixed(3)}] | lat: [{bounds.minLat.toFixed(3)}, {bounds.maxLat.toFixed(3)}]
          </span>

          <button
            onClick={() => executeQuery()}
            disabled={isLoading}
            style={{
              padding: '5px 12px',
              background: '#ea580c',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: isLoading ? 'wait' : 'pointer',
              fontWeight: 700,
              fontSize: '12px',
            }}
          >
            {isLoading ? 'Cargando...' : 'Consultar AOI'}
          </button>

          <span style={{ fontSize: '11px', opacity: 0.85 }}>
            Calibración: <strong>{calibrationMode}</strong> | Vista mapa: <strong>{mapRenderMode}</strong>
          </span>
        </div>

        <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
          <CenteredAoiMap
            onBoundsChange={setBounds}
            hotspots={backendData?.hotspots}
            selectedHotspot={selectedHotspot}
            onSelectHotspot={setSelectedHotspot}
            renderMode={mapRenderMode}
            onRenderModeChange={setMapRenderMode}
          />
        </div>
      </div>

      {/* RIGHT BLOCK: Point Inspector + Interactive Activity Calendar + Pluggable Visualization Modules */}
      <div style={{ height: '100%', overflowY: 'auto', minWidth: 0 }}>
        <HotspotSidePanel
          status={status}
          totalHotspots={backendData?.hotspots.length ?? 0}
          hotspots={backendData?.hotspots ?? []}
          selectedHotspot={selectedHotspot}
          bounds={bounds}
          calendarCells={backendData?.calendar_cells ?? []}
          startDate={startDate}
          endDate={endDate}
          calibrationMode={calibrationMode}
          onDateRangeChange={handleDateRangeChange}
          onCalibrationModeChange={handleCalibrationModeChange}
          onRefresh={() => executeQuery()}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
