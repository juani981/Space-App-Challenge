import { useCallback, useEffect, useRef, useState } from 'react';
import { CenteredAoiMap, type MapRenderMode } from './components/CenteredAoiMap';
import { HotspotSidePanel } from './components/HotspotSidePanel';
import {
  fetchAoi,
  fetchCellMonthAoi,
  type AoiBounds,
  type AoiResponse,
  type CalibrationMode,
  type CellMonthAoiResponse,
  type CellMonthMapCell,
  type CellMonthMetric,
  type UnifiedHotspot,
} from './services/apiClient';
import { LanguageProvider, useLanguage } from './i18n/LanguageContext';

const MAX_CACHED_WORLD_POINTS = 2500;

function hotspotKey(hs: UnifiedHotspot): string {
  return `${hs.datetime_utc}|${hs.lat.toFixed(4)}|${hs.lon.toFixed(4)}|${hs.satellite}`;
}

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
  const [mapRenderMode, setMapRenderMode] = useState<MapRenderMode>('cell_grid');
  const [cellMonthMetric, setCellMonthMetric] = useState<CellMonthMetric>('n_eq');
  const [showCellGrid, setShowCellGrid] = useState<boolean>(true);

  const [backendData, setBackendData] = useState<AoiResponse | null>(null);
  const [cellMonthData, setCellMonthData] = useState<CellMonthAoiResponse | null>(null);
  const [selectedCell, setSelectedCell] = useState<CellMonthMapCell | null>(null);
  const [worldHotspots, setWorldHotspots] = useState<UnifiedHotspot[]>([]);
  const [selectedHotspot, setSelectedHotspot] = useState<UnifiedHotspot | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  const executeQuery = useCallback(
    async (
      targetBounds = bounds,
      start = startDate,
      end = endDate,
      calMode = calibrationMode,
      resetWorldCache = false,
      cmMetric = cellMonthMetric,
    ) => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setIsLoading(true);
      setErrorMsg(null);
      try {
        const [aoiResult, cellMonthResult] = await Promise.allSettled([
          fetchAoi(targetBounds, {
            startDate: start,
            endDate: end,
            calibrationMode: calMode,
            signal: controller.signal,
          }),
          fetchCellMonthAoi(targetBounds, {
            startDate: start,
            endDate: end,
            metric: cmMetric,
            signal: controller.signal,
          }),
        ]);

        if (aoiResult.status === 'rejected') {
          throw aoiResult.reason;
        }
        const res = aoiResult.value;
        setBackendData(res);

        if (cellMonthResult.status === 'fulfilled') {
          setCellMonthData(cellMonthResult.value);
          setSelectedCell((prev) => prev ?? cellMonthResult.value.cells[0] ?? null);
        }

        // Merge newly lazy-loaded viewport hotspots into the progressive world map cache
        setWorldHotspots((prev) => {
          const base = resetWorldCache ? [] : prev;
          const map = new Map<string, UnifiedHotspot>();
          for (const item of base) {
            map.set(hotspotKey(item), item);
          }
          for (const item of res.hotspots) {
            map.set(hotspotKey(item), item);
          }
          const merged = Array.from(map.values());
          if (merged.length > MAX_CACHED_WORLD_POINTS) {
            return merged.slice(merged.length - MAX_CACHED_WORLD_POINTS);
          }
          return merged;
        });

        setSelectedHotspot((prev) => prev ?? res.hotspots[0] ?? null);
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        setErrorMsg(err instanceof Error ? err.message : String(err));
      } finally {
        if (abortControllerRef.current === controller) {
          setIsLoading(false);
        }
      }
    },
    [bounds, startDate, endDate, calibrationMode, cellMonthMetric]
  );

  // Automatic debounced lazy-loading whenever the user pans/zooms the map viewport
  useEffect(() => {
    const timer = window.setTimeout(() => {
      executeQuery(bounds, startDate, endDate, calibrationMode, false);
    }, 200);
    return () => window.clearTimeout(timer);
  }, [bounds]);

  const handleDateRangeChange = (newStart: string, newEnd: string) => {
    setStartDate(newStart);
    setEndDate(newEnd);
    setSelectedHotspot(null);
    executeQuery(bounds, newStart, newEnd, calibrationMode, true);
  };

  const handleCalibrationModeChange = (newMode: CalibrationMode) => {
    setCalibrationMode(newMode);
    setSelectedHotspot(null);
    executeQuery(bounds, startDate, endDate, newMode, true);
  };

  const handleCellMonthMetricChange = (newMetric: CellMonthMetric) => {
    setCellMonthMetric(newMetric);
    executeQuery(bounds, startDate, endDate, calibrationMode, false, newMetric);
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
      {/* LEFT BLOCK: Full-Viewport Lazy-Loaded World Map + Live Coordinate & Mode Bar */}
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
            onClick={() => executeQuery(bounds, startDate, endDate, calibrationMode, false)}
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

          <span
            style={{
              fontSize: '11px',
              background: '#0f172a',
              color: '#38bdf8',
              padding: '3px 8px',
              borderRadius: '999px',
              fontWeight: 600,
            }}
          >
            {backendData?.hotspots.length ?? 0} {t.inViewportBadge} · {worldHotspots.length} {t.accumulatedBadge}
          </span>

          <span style={{ fontSize: '11px', opacity: 0.85 }}>
            {t.calibrationLabel} <strong>{t.calModeShort[calibrationMode]}</strong> | {t.mapViewLabel} <strong>{t.mapModeShort[mapRenderMode]}</strong>
          </span>
        </div>

        <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
          <CenteredAoiMap
            onBoundsChange={setBounds}
            hotspots={worldHotspots}
            selectedHotspot={selectedHotspot}
            onSelectHotspot={setSelectedHotspot}
            renderMode={mapRenderMode}
            onRenderModeChange={setMapRenderMode}
            cellMonthCells={cellMonthData?.cells ?? []}
            cellMonthMetric={cellMonthMetric}
            selectedCellId={selectedCell?.cell_id ?? null}
            onSelectCell={setSelectedCell}
            showCellGrid={showCellGrid}
            onToggleCellGrid={() => setShowCellGrid((p) => !p)}
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
          mapRenderMode={mapRenderMode}
          onMapRenderModeChange={setMapRenderMode}
          onDateRangeChange={handleDateRangeChange}
          onCalibrationModeChange={handleCalibrationModeChange}
          onRefresh={() => executeQuery(bounds, startDate, endDate, calibrationMode, false)}
          isLoading={isLoading}
          cellMonthData={cellMonthData}
          cellMonthMetric={cellMonthMetric}
          selectedCell={selectedCell}
          onCellMonthMetricChange={handleCellMonthMetricChange}
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
