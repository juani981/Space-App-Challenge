import { useCallback, useEffect, useRef, useState } from 'react';
import { Circle, CircleMarker, MapContainer, Rectangle, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import type { AoiBounds, CellMonthMapCell, CellMonthMetric, UnifiedHotspot } from '../services/apiClient';
import {
  SATELLITE_GENERATIONS,
  getSatelliteGeneration,
  sortHotspotsByZOrder,
} from '../utils/satelliteGenerations';
import { useLanguage } from '../i18n/LanguageContext';

export type MapRenderMode = 'harmonized' | 'footprint';

const HALF_CELL_DEG = 0.125;

function getGridCellColor(ratio: number): { fill: string; stroke: string } {
  if (ratio >= 0.75) return { fill: '#b91c1c', stroke: '#7f1d1d' };
  if (ratio >= 0.5) return { fill: '#ef4444', stroke: '#991b1b' };
  if (ratio >= 0.25) return { fill: '#f97316', stroke: '#c2410c' };
  return { fill: '#facc15', stroke: '#a16207' };
}

export interface CenteredAoiMapProps {
  /** Callback fired whenever the visible map viewport changes (pan, zoom, or geolocation center) */
  onBoundsChange: (bounds: AoiBounds) => void;
  /** Harmonized hotspots lazy-loaded across the world map */
  hotspots?: UnifiedHotspot[];
  /** Currently selected hotspot to highlight on the map */
  selectedHotspot?: UnifiedHotspot | null;
  /** Callback fired when the user clicks a hotspot marker */
  onSelectHotspot?: (hotspot: UnifiedHotspot) => void;
  /** Controlled render mode ('harmonized' vs 'footprint') */
  renderMode?: MapRenderMode;
  /** Callback fired when render mode changes */
  onRenderModeChange?: (mode: MapRenderMode) => void;
  /** Active 0.25° x 0.25° harmonized cells returned by `/api/cell-month/aoi` */
  cellMonthCells?: CellMonthMapCell[];
  /** Active metric used to scale grid cell intensity */
  cellMonthMetric?: CellMonthMetric;
  /** Whether the optional 0.25° grid cell overlay is visible */
  showCellGrid?: boolean;
  /** Toggle callback for the optional 0.25° grid cell overlay */
  onToggleCellGrid?: () => void;
}

/**
 * Tracks the full visible map viewport rectangle (`map.getBounds()`), ensures Leaflet's
 * container size is invalidated before centering (`map.invalidateSize()`), and handles
 * one-shot browser Geolocation centering + manual location picking without re-render loops.
 */
function ViewportAndGeolocationController({
  onBoundsChange,
  onVisualCenterChange,
  onGeoError,
  locateTrigger,
  isPickingLocation,
  onLocationPicked,
}: {
  onBoundsChange: (bounds: AoiBounds) => void;
  onVisualCenterChange: (coords: [number, number]) => void;
  onGeoError: () => void;
  locateTrigger: number;
  isPickingLocation: boolean;
  onLocationPicked: (coords: [number, number]) => void;
}) {
  const map = useMap();

  // Keep latest callbacks in refs so effects never re-run due to parent re-renders
  const callbacksRef = useRef({
    onBoundsChange,
    onVisualCenterChange,
    onGeoError,
    onLocationPicked,
  });
  callbacksRef.current = {
    onBoundsChange,
    onVisualCenterChange,
    onGeoError,
    onLocationPicked,
  };

  const hasRequestedInitialGeo = useRef(false);
  const lastHandledTrigger = useRef(0);
  const lastBoundsKey = useRef('');

  const syncVisualCenter = useCallback(() => {
    const size = map.getSize();
    if (size.x === 0 || size.y === 0) return;
    const c = map.getCenter();
    callbacksRef.current.onVisualCenterChange([
      Number(c.lat.toFixed(4)),
      Number(c.lng.toFixed(4)),
    ]);
  }, [map]);

  const emitViewportBounds = useCallback(() => {
    const size = map.getSize();
    if (size.x === 0 || size.y === 0) return;

    syncVisualCenter();

    const b = map.getBounds();
    const sw = b.getSouthWest();
    const ne = b.getNorthEast();
    const nextBounds: AoiBounds = {
      minLon: Number(Math.max(-180, sw.lng).toFixed(4)),
      minLat: Number(Math.max(-90, sw.lat).toFixed(4)),
      maxLon: Number(Math.min(180, ne.lng).toFixed(4)),
      maxLat: Number(Math.min(90, ne.lat).toFixed(4)),
    };

    const key = `${nextBounds.minLon},${nextBounds.minLat},${nextBounds.maxLon},${nextBounds.maxLat}`;
    if (key === lastBoundsKey.current) return;
    lastBoundsKey.current = key;

    callbacksRef.current.onBoundsChange(nextBounds);
  }, [map, syncVisualCenter]);

  const centerMapAccurately = useCallback(
    (lat: number, lon: number, targetZoom = 8) => {
      requestAnimationFrame(() => {
        map.invalidateSize({ pan: false });
        map.setView([lat, lon], targetZoom, { animate: false });
        window.setTimeout(() => {
          map.invalidateSize({ pan: false });
          map.setView([lat, lon], targetZoom, { animate: false });
          emitViewportBounds();
        }, 80);
      });
    },
    [map, emitViewportBounds],
  );

  const requestBrowserLocation = useCallback(
    (isManualClick: boolean) => {
      if (!('geolocation' in navigator)) {
        if (isManualClick) callbacksRef.current.onGeoError();
        emitViewportBounds();
        return;
      }

      const handleSuccess = (pos: GeolocationPosition) => {
        const lat = Number(pos.coords.latitude.toFixed(4));
        const lon = Number(pos.coords.longitude.toFixed(4));
        callbacksRef.current.onVisualCenterChange([lat, lon]);
        centerMapAccurately(lat, lon, 8);
      };

      navigator.geolocation.getCurrentPosition(
        handleSuccess,
        () => {
          navigator.geolocation.getCurrentPosition(
            handleSuccess,
            () => {
              if (isManualClick) {
                callbacksRef.current.onGeoError();
              }
              emitViewportBounds();
            },
            {
              enableHighAccuracy: false,
              timeout: 6000,
              maximumAge: 60000,
            },
          );
        },
        {
          enableHighAccuracy: true,
          timeout: 6000,
          maximumAge: 0,
        },
      );
    },
    [emitViewportBounds, centerMapAccurately],
  );

  // Keep Leaflet container size synchronized with CSS Grid/Flexbox via ResizeObserver
  useEffect(() => {
    const container = map.getContainer();
    const observer = new ResizeObserver(() => {
      map.invalidateSize({ pan: false });
      emitViewportBounds();
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [map, emitViewportBounds]);

  // Initial mount: run exactly once
  useEffect(() => {
    if (!hasRequestedInitialGeo.current) {
      hasRequestedInitialGeo.current = true;
      map.invalidateSize({ pan: false });
      emitViewportBounds();
      requestBrowserLocation(false);
    }
  }, [map, emitViewportBounds, requestBrowserLocation]);

  // Manual re-center: run ONLY when locateTrigger increments
  useEffect(() => {
    if (locateTrigger > lastHandledTrigger.current) {
      lastHandledTrigger.current = locateTrigger;
      requestBrowserLocation(true);
    }
  }, [locateTrigger, requestBrowserLocation]);

  // Synchronize Leaflet container cursor when "Pick on Map" mode is active
  useEffect(() => {
    const container = map.getContainer();
    if (isPickingLocation) {
      container.style.setProperty('cursor', 'crosshair', 'important');
    } else {
      container.style.removeProperty('cursor');
    }
    return () => {
      container.style.removeProperty('cursor');
    };
  }, [map, isPickingLocation]);

  useMapEvents({
    move: syncVisualCenter,
    moveend: emitViewportBounds,
    zoomend: emitViewportBounds,
    resize: emitViewportBounds,
    click(e) {
      if (isPickingLocation) {
        const lat = Number(e.latlng.lat.toFixed(4));
        const lon = Number(e.latlng.lng.toFixed(4));
        callbacksRef.current.onLocationPicked([lat, lon]);
        centerMapAccurately(lat, lon, Math.max(map.getZoom(), 8));
      }
    },
  });

  return null;
}

export function CenteredAoiMap({
  onBoundsChange,
  hotspots = [],
  selectedHotspot = null,
  onSelectHotspot,
  renderMode: controlledMode,
  cellMonthCells = [],
  cellMonthMetric = 'n_eq',
  showCellGrid = true,
  onToggleCellGrid,
}: CenteredAoiMapProps) {
  const { lang, t } = useLanguage();
  const [internalMode] = useState<MapRenderMode>('harmonized');
  const [visualCenter, setVisualCenter] = useState<[number, number]>([-32.0, -61.5]);
  const [locateTrigger, setLocateTrigger] = useState<number>(0);
  const [isPickingLocation, setIsPickingLocation] = useState<boolean>(false);
  const [geoHasError, setGeoHasError] = useState<boolean>(false);

  const activeMode = controlledMode ?? internalMode;

  const maxCellValue = cellMonthCells.reduce((acc, cell) => {
    const val = cellMonthMetric === 'n_eq' ? cell.n_eq : cell.f_eq;
    return val > acc ? val : acc;
  }, 0);

  // In footprint mode, sort by zOrder (G1 at bottom -> G4 on top)
  const orderedHotspots = activeMode === 'footprint'
    ? sortHotspotsByZOrder(hotspots)
    : hotspots;

  return (
    <div
      id="aoi-map-wrapper"
      className={isPickingLocation ? 'picking-location' : undefined}
      style={{
        position: 'relative',
        height: '100%',
        width: '100%',
        cursor: isPickingLocation ? 'crosshair' : 'grab',
      }}
    >
      {isPickingLocation && (
        <style>{`
          #aoi-map-wrapper.picking-location .leaflet-container,
          #aoi-map-wrapper.picking-location .leaflet-grab,
          #aoi-map-wrapper.picking-location .leaflet-dragging .leaflet-grab,
          #aoi-map-wrapper.picking-location .leaflet-interactive {
            cursor: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='28' height='28' viewBox='0 0 28 28'><circle cx='14' cy='14' r='9' fill='none' stroke='%230284c7' stroke-width='2'/><circle cx='14' cy='14' r='2' fill='%23ea580c'/><line x1='14' y1='1' x2='14' y2='7' stroke='%230284c7' stroke-width='2'/><line x1='14' y1='21' x2='14' y2='27' stroke='%230284c7' stroke-width='2'/><line x1='1' y1='14' x2='7' y2='14' stroke='%230284c7' stroke-width='2'/><line x1='21' y1='14' x2='27' y2='14' stroke='%230284c7' stroke-width='2'/></svg>") 14 14, crosshair !important;
          }
        `}</style>
      )}
      <MapContainer center={[-32.0, -61.5]} zoom={6} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ViewportAndGeolocationController
          onBoundsChange={onBoundsChange}
          onVisualCenterChange={setVisualCenter}
          onGeoError={() => setGeoHasError(true)}
          locateTrigger={locateTrigger}
          isPickingLocation={isPickingLocation}
          onLocationPicked={(coords) => {
            setVisualCenter(coords);
            setIsPickingLocation(false);
            setGeoHasError(false);
          }}
        />

        {/* OPTIONAL 0.25° x 0.25° HARMONIZED GRID CELLS OVERLAY (BELOW MARKERS) */}
        {showCellGrid &&
          cellMonthCells.map((cell) => {
            const val = cellMonthMetric === 'n_eq' ? cell.n_eq : cell.f_eq;
            const ratio = maxCellValue > 0 ? val / maxCellValue : 0;
            const palette = getGridCellColor(ratio);
            return (
              <Rectangle
                key={`cm-cell-${cell.cell_id}`}
                bounds={[
                  [cell.lat_center - HALF_CELL_DEG, cell.lon_center - HALF_CELL_DEG],
                  [cell.lat_center + HALF_CELL_DEG, cell.lon_center + HALF_CELL_DEG],
                ]}
                interactive={!isPickingLocation}
                pathOptions={{
                  color: palette.stroke,
                  fillColor: palette.fill,
                  fillOpacity: 0.26,
                  weight: 1,
                }}
              >
                <Tooltip direction="top" opacity={0.95}>
                  <div style={{ fontSize: '11px', lineHeight: 1.35 }}>
                    <strong>
                      {lang === 'es' ? 'Celda 0,25°' : '0.25° Cell'} #{cell.cell_id}
                    </strong>{' '}
                    ({cell.cell_area_km2.toFixed(0)} km²)<br />
                    n_eq: <strong>{cell.n_eq}</strong> | f_eq: <strong>{cell.f_eq} MW</strong><br />
                    {lang === 'es' ? 'Terra (propia)' : 'Terra (sep.)'}: {cell.n_terra} · {cell.sensors.join(', ')}
                    {cell.quality_flags_decoded.length > 0 && (
                      <>
                        <br />
                        <span style={{ color: '#b45309', fontWeight: 600 }}>
                          {cell.quality_flags_decoded.map((f) => f.label_es).join(', ')}
                        </span>
                      </>
                    )}
                  </div>
                </Tooltip>
              </Rectangle>
            );
          })}

        {/* ASYNCHRONOUSLY LAZY-LOADED HOTSPOT RENDERING LAYER */}
        {orderedHotspots.map((hs, idx) => {
          const isSelected =
            selectedHotspot !== null &&
            selectedHotspot.lat === hs.lat &&
            selectedHotspot.lon === hs.lon &&
            selectedHotspot.datetime_utc === hs.datetime_utc;

          const gen = getSatelliteGeneration(hs.satellite);
          const key = `${hs.datetime_utc}-${hs.lat}-${hs.lon}-${hs.satellite}-${idx}`;

          if (activeMode === 'harmonized') {
            const isCluster = hs.analysis_metrics?.is_cluster ?? false;
            return (
              <CircleMarker
                key={key}
                center={[hs.lat, hs.lon]}
                radius={isSelected ? 10 : isCluster ? 8 : 6}
                interactive={!isPickingLocation}
                eventHandlers={{
                  click: () => {
                    if (!isPickingLocation) onSelectHotspot?.(hs);
                  },
                }}
                pathOptions={{
                  color: isSelected ? '#0f172a' : isCluster ? '#d97706' : '#991b1b',
                  fillColor: isCluster ? '#f59e0b' : '#ef4444',
                  fillOpacity: isSelected ? 1.0 : 0.85,
                  weight: isSelected ? 3 : isCluster ? 2.5 : 1.5,
                }}
              >
                <Tooltip direction="top" offset={[0, -6]} opacity={0.9}>
                  <div style={{ fontSize: '11px', lineHeight: 1.3 }}>
                    <strong>{hs.satellite} ({gen.generation})</strong> — {hs.frp} MW<br />
                    {hs.datetime_utc.slice(0, 16).replace('T', ' ')} UTC<br />
                    {isCluster && <span style={{ color: '#d97706', fontWeight: 600 }}>{t.mapClusterBadge}</span>}
                  </div>
                </Tooltip>
              </CircleMarker>
            );
          }

          // FOOTPRINT MODE: Real physical ground footprint in meters using <Circle>
          return (
            <div key={key}>
              <Circle
                center={[hs.lat, hs.lon]}
                radius={gen.footprintRadiusMeters}
                interactive={!isPickingLocation}
                eventHandlers={{
                  click: () => {
                    if (!isPickingLocation) onSelectHotspot?.(hs);
                  },
                }}
                pathOptions={{
                  color: isSelected ? '#0f172a' : gen.strokeColor,
                  fillColor: gen.color,
                  fillOpacity: isSelected ? 0.9 : gen.fillOpacity,
                  weight: isSelected ? 3.5 : gen.generation === 'G1' ? 1.5 : 2,
                  dashArray: gen.generation === 'G1' ? '5, 5' : undefined,
                }}
              >
                <Tooltip direction="top" offset={[0, -10]} opacity={0.95}>
                  <div style={{ fontSize: '11px', lineHeight: 1.3 }}>
                    <strong>{gen.name} ({gen.generation})</strong><br />
                    {t.mapTooltipFootprint}: {gen.resolutionMeters}m ({gen.footprintRadiusMeters}m {t.mapTooltipRadius})<br />
                    FRP: {hs.frp} MW | {t.mapTooltipConfidence}: {hs.confidence}<br />
                    {hs.datetime_utc.slice(0, 16).replace('T', ' ')} UTC
                  </div>
                </Tooltip>
              </Circle>
              {/* Central pinpoint for easy targeting */}
              <CircleMarker
                center={[hs.lat, hs.lon]}
                radius={isSelected ? 4 : 2.5}
                eventHandlers={{
                  click: () => onSelectHotspot?.(hs),
                }}
                pathOptions={{
                  color: gen.strokeColor,
                  fillColor: '#ffffff',
                  fillOpacity: 1.0,
                  weight: 1,
                }}
              />
            </div>
          );
        })}
      </MapContainer>

      {/* Fixed Visual Center Reticle (always locked to the true visual center of the viewport) */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          pointerEvents: 'none',
          zIndex: 999,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="5" stroke="#0284c7" strokeWidth="2" fill="rgba(2, 132, 199, 0.18)" />
          <circle cx="12" cy="12" r="1.5" fill="#0284c7" />
          <line x1="12" y1="2" x2="12" y2="6" stroke="#0284c7" strokeWidth="1.5" />
          <line x1="12" y1="18" x2="12" y2="22" stroke="#0284c7" strokeWidth="1.5" />
          <line x1="2" y1="12" x2="6" y2="12" stroke="#0284c7" strokeWidth="1.5" />
          <line x1="18" y1="12" x2="22" y2="12" stroke="#0284c7" strokeWidth="1.5" />
        </svg>
      </div>

      {/* Bottom-Right Conventional Map Controls (Live Lat/Lon Readout + GPS Locate & Drop-Pin) */}
      <div
        style={{
          position: 'absolute',
          bottom: '28px',
          right: '12px',
          zIndex: 1001,
          display: 'flex',
          alignItems: 'flex-end',
          gap: '8px',
        }}
      >
        {/* Contextual helper pill (only shown when Picking mode is active or on manual GPS error) */}
        {(isPickingLocation || geoHasError) && (
          <div
            style={{
              background: isPickingLocation ? 'rgba(15, 23, 42, 0.92)' : '#fffbeb',
              color: isPickingLocation ? '#f8fafc' : '#b45309',
              border: `1px solid ${isPickingLocation ? '#334155' : '#fde68a'}`,
              borderRadius: '8px',
              padding: '6px 10px',
              fontSize: '11px',
              fontWeight: 600,
              boxShadow: '0 2px 6px rgba(0,0,0,0.28)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              maxWidth: '260px',
            }}
          >
            <span>{isPickingLocation ? t.pickLocationActiveBtn : `⚠️ ${t.geoErrorNotice}`}</span>
            {geoHasError && !isPickingLocation && (
              <button
                type="button"
                onClick={() => setGeoHasError(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#b45309',
                  fontWeight: 700,
                  cursor: 'pointer',
                  padding: '0 2px',
                  fontSize: '13px',
                  lineHeight: 1,
                }}
              >
                ×
              </button>
            )}
          </div>
        )}

        {/* Live Center Latitude & Longitude Legend (Matching Map Control Style) */}
        <div
          style={{
            background: '#ffffff',
            borderRadius: '8px',
            boxShadow: '0 2px 6px rgba(0,0,0,0.28)',
            border: '1px solid rgba(15, 23, 42, 0.14)',
            padding: '6px 10px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '11px',
            fontFamily: 'monospace',
            color: '#0f172a',
            whiteSpace: 'nowrap',
            height: '38px',
            boxSizing: 'border-box',
          }}
          title={t.userLocationTooltip}
        >
          <span style={{ fontWeight: 600 }}>
            {visualCenter[0].toFixed(4)}°, {visualCenter[1].toFixed(4)}°
          </span>
        </div>

        {/* Standard Map Control Button Stack (Google Maps / Leaflet style) */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            background: '#ffffff',
            borderRadius: '8px',
            boxShadow: '0 2px 6px rgba(0,0,0,0.28)',
            border: '1px solid rgba(15, 23, 42, 0.14)',
            overflow: 'hidden',
          }}
        >
          {/* 1. Conventional GPS "My Location" Button */}
          <button
            type="button"
            title={t.locateMeBtn.replace('📍 ', '')}
            aria-label={t.locateMeBtn.replace('📍 ', '')}
            onClick={() => {
              setIsPickingLocation(false);
              setGeoHasError(false);
              setLocateTrigger((n) => n + 1);
            }}
            style={{
              width: '38px',
              height: '38px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#ffffff',
              color: '#0284c7',
              border: 'none',
              borderBottom: '1px solid #e2e8f0',
              cursor: 'pointer',
              padding: 0,
              transition: 'background 0.15s ease, color 0.15s ease',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="7" />
              <circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none" />
              <line x1="12" y1="2" x2="12" y2="5" />
              <line x1="12" y1="19" x2="12" y2="22" />
              <line x1="2" y1="12" x2="5" y2="12" />
              <line x1="19" y1="12" x2="22" y2="12" />
            </svg>
          </button>

          {/* 2. Conventional Map Drop-Pin "Pick on Map" Button */}
          <button
            type="button"
            title={t.pickLocationBtn.replace('🎯 ', '')}
            aria-label={t.pickLocationBtn.replace('🎯 ', '')}
            onClick={() => {
              setGeoHasError(false);
              setIsPickingLocation((prev) => !prev);
            }}
            style={{
              width: '38px',
              height: '38px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: isPickingLocation ? '#0284c7' : '#ffffff',
              color: isPickingLocation ? '#ffffff' : '#334155',
              border: 'none',
              borderBottom: onToggleCellGrid ? '1px solid #e2e8f0' : 'none',
              cursor: 'pointer',
              padding: 0,
              transition: 'background 0.15s ease, color 0.15s ease',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 21s-7-6.58-7-12a7 7 0 1 1 14 0c0 5.42-7 12-7 12z" />
              <circle cx="12" cy="9" r="2.5" />
            </svg>
          </button>

          {/* 3. Toggle 0.25° Harmonized Grid Cell Overlay */}
          {onToggleCellGrid && (
            <button
              type="button"
              title={lang === 'es' ? 'Mostrar/ocultar grilla armonizada 0,25°' : 'Toggle 0.25° harmonized grid overlay'}
              aria-label={lang === 'es' ? 'Grilla 0,25°' : '0.25° Grid'}
              onClick={onToggleCellGrid}
              style={{
                width: '38px',
                height: '38px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: showCellGrid ? '#ea580c' : '#ffffff',
                color: showCellGrid ? '#ffffff' : '#334155',
                border: 'none',
                cursor: 'pointer',
                padding: 0,
                transition: 'background 0.15s ease, color 0.15s ease',
              }}
            >
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="1" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="12" y1="3" x2="12" y2="21" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
