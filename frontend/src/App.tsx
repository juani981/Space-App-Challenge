import { useCallback, useEffect, useRef, useState } from 'react';
import { CenteredAoiMap } from './components/CenteredAoiMap';
import { HarmonizedSidePanel } from './components/HarmonizedSidePanel';
import {
  fetchCellMonthAoi,
  type AoiBounds,
  type CellMonthAoiResponse,
  type CellMonthMapCell,
  type CellMonthMetric,
} from './services/apiClient';
import { LanguageProvider, useLanguage } from './i18n/LanguageContext';

/**
 * La aplicación consulta SOLO la tabla armonizada `harmonized.cell_month` (`/api/cell-month/aoi`):
 * mapa de celdas de 0,25° (o bloques de 1° en vistas amplias), calendario de percentiles 2012–2026,
 * alertas de calidad y CSV. Los modos de puntos individuales (endpoint `/api/aoi`) no se usan:
 * la base armonizada no tiene puntos individuales, solo celdas.
 */
function AppContent() {
  const { lang, t } = useLanguage();
  const es = lang === 'es';

  const [bounds, setBounds] = useState<AoiBounds>({
    minLon: -65.0,
    minLat: -35.0,
    maxLon: -58.0,
    maxLat: -29.0,
  });

  const [startDate, setStartDate] = useState<string>('2024-01-01');
  const [endDate, setEndDate] = useState<string>('2024-12-31');
  const [cellMonthMetric, setCellMonthMetric] = useState<CellMonthMetric>('n_eq');

  const [cellMonthData, setCellMonthData] = useState<CellMonthAoiResponse | null>(null);
  const [selectedCell, setSelectedCell] = useState<CellMonthMapCell | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  const executeQuery = useCallback(
    async (targetBounds = bounds, start = startDate, end = endDate, cmMetric = cellMonthMetric) => {
      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setIsLoading(true);
      setErrorMsg(null);
      try {
        const result = await fetchCellMonthAoi(targetBounds, {
          startDate: start,
          endDate: end,
          metric: cmMetric,
          signal: controller.signal,
        });
        setCellMonthData(result);
        // Conservar la celda seleccionada si sigue en la vista; si no, la de mayor valor
        setSelectedCell((prev) => result.cells.find((c) => c.cell_id === prev?.cell_id) ?? result.cells[0] ?? null);
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        // No dejar en pantalla datos viejos como si fueran de la consulta actual
        setCellMonthData(null);
        setSelectedCell(null);
        setErrorMsg(err instanceof Error ? err.message : String(err));
      } finally {
        if (abortControllerRef.current === controller) {
          setIsLoading(false);
        }
      }
    },
    [bounds, startDate, endDate, cellMonthMetric],
  );

  // Consulta con retardo cada vez que el usuario mueve o hace zoom en el mapa
  useEffect(() => {
    const timer = window.setTimeout(() => {
      executeQuery(bounds, startDate, endDate, cellMonthMetric);
    }, 200);
    return () => window.clearTimeout(timer);
  }, [bounds]);

  const handleDateRangeChange = (newStart: string, newEnd: string) => {
    setStartDate(newStart);
    setEndDate(newEnd);
    executeQuery(bounds, newStart, newEnd, cellMonthMetric);
  };

  const handleCellMonthMetricChange = (newMetric: CellMonthMetric) => {
    setCellMonthMetric(newMetric);
    executeQuery(bounds, startDate, endDate, newMetric);
  };

  const cellsShown = cellMonthData?.cells.length ?? 0;
  const resolution = cellMonthData?.resolution_deg ?? 0.25;
  const cellsBadge = es
    ? `${cellsShown.toLocaleString('es-AR')} ${resolution >= 1 ? 'bloques de 1°' : 'celdas de 0,25°'} con actividad`
    : `${cellsShown.toLocaleString('en-US')} active ${resolution >= 1 ? '1° blocks' : '0.25° cells'}`;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.9fr 1.1fr', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      {/* IZQUIERDA: mapa mundial con la región visible como AOI */}
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
            onClick={() => executeQuery(bounds, startDate, endDate, cellMonthMetric)}
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
              color: errorMsg ? '#fca5a5' : '#38bdf8',
              padding: '3px 8px',
              borderRadius: '999px',
              fontWeight: 600,
            }}
          >
            {errorMsg ? (es ? 'Sin datos: base no disponible' : 'No data: database unavailable') : cellsBadge}
          </span>

          <span style={{ fontSize: '11px', opacity: 0.85 }}>
            {es ? 'Período' : 'Period'} <strong>{startDate.slice(0, 7)} → {endDate.slice(0, 7)}</strong> |{' '}
            {es ? 'Métrica' : 'Metric'} <strong>{cellMonthMetric === 'n_eq' ? (es ? 'focos equivalentes' : 'equivalent hotspots') : 'FRP (MW)'}</strong>
          </span>
        </div>

        <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
          <CenteredAoiMap
            onBoundsChange={setBounds}
            renderMode="cell_grid"
            cellMonthCells={cellMonthData?.cells ?? []}
            cellMonthMetric={cellMonthMetric}
            selectedCellId={selectedCell?.cell_id ?? null}
            onSelectCell={setSelectedCell}
            showCellGrid
          />
        </div>
      </div>

      {/* DERECHA: estado, período, calendario de percentiles 2012–2026, alertas, inspector de celda y CSV */}
      <div style={{ height: '100%', overflowY: 'auto', minWidth: 0 }}>
        <HarmonizedSidePanel
          bounds={bounds}
          data={cellMonthData}
          metric={cellMonthMetric}
          selectedCell={selectedCell}
          startDate={startDate}
          endDate={endDate}
          isLoading={isLoading}
          errorMsg={errorMsg}
          onMetricChange={handleCellMonthMetricChange}
          onDateRangeChange={handleDateRangeChange}
          onRefresh={() => executeQuery(bounds, startDate, endDate, cellMonthMetric)}
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
