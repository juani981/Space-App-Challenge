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
import { LanguageProvider, useLanguage } from './i18n/LanguageContext';

function AppContent() {
  const { t } = useLanguage();

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
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const executeQuery = useCallback(
    async (
      targetBounds = bounds,
      start = startDate,
      end = endDate,
      calMode = calibrationMode,
    ) => {
      setIsLoading(true);
      setErrorMsg(null);
      try {
        const res = await fetchAoi(targetBounds, {
          startDate: start,
          endDate: end,
          calibrationMode: calMode,
        });
        setBackendData(res);
        setSelectedHotspot(res.hotspots[0] ?? null);
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : String(err));
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

  const localizedStatus = isLoading
    ? t.statusQuerying
    : errorMsg
    ? `Error: ${errorMsg}`
    : backendData
    ? `${t.statusConnectedPrefix} — ${t.statusModeLabel}: ${t.calModeShort[backendData.calibration_mode as CalibrationMode] ?? backendData.calibration_mode} | ${t.statusSourceLabel}: ${backendData.data_source.toUpperCase()}`
    : t.statusIdle;

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
          <strong style={{ fontSize: '13px' }}>{t.aoiCenteredLabel}</strong>
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
            {isLoading ? t.loadingBtn : t.queryAoiBtn}
          </button>

          <span style={{ fontSize: '11px', opacity: 0.85 }}>
            {t.calibrationLabel} <strong>{t.calModeShort[calibrationMode]}</strong> | {t.mapViewLabel} <strong>{t.mapModeShort[mapRenderMode]}</strong>
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
          status={localizedStatus}
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

export default function App() {
  return (
    <LanguageProvider>
      <AppContent />
    </LanguageProvider>
  );
}
