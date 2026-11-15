import { useCallback, useEffect, useRef, useState } from 'react';
import { Circle, CircleMarker, MapContainer, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import type { AoiBounds, UnifiedHotspot } from '../services/apiClient';
import {
  SATELLITE_GENERATIONS,
  getSatelliteGeneration,
  sortHotspotsByZOrder,
} from '../utils/satelliteGenerations';
import { useLanguage } from '../i18n/LanguageContext';

export type MapRenderMode = 'harmonized' | 'footprint';

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
}

/**
 * Tracks the full visible map viewport rectangle (`map.getBounds()`), ensures Leaflet's
 * container size is invalidated before centering (`map.invalidateSize()`), and handles
 * one-shot browser Geolocation centering + manual location picking without re-render loops.
 */
function ViewportAndGeolocationController({
  onBoundsChange,
  onUserLocationFound,
  onGeoError,
  locateTrigger,
  isPickingLocation,
  onLocationPicked,
}: {
  onBoundsChange: (bounds: AoiBounds) => void;
  onUserLocationFound: (coords: [number, number]) => void;
  onGeoError: () => void;
  locateTrigger: number;
  isPickingLocation: boolean;
  onLocationPicked: (coords: [number, number]) => void;
}) {
  const map = useMap();

  // Keep latest callbacks in refs so effects never re-run due to parent re-renders
  const callbacksRef = useRef({
    onBoundsChange,
    onUserLocationFound,
    onGeoError,
    onLocationPicked,
  });
  callbacksRef.current = {
    onBoundsChange,
    onUserLocationFound,
    onGeoError,
    onLocationPicked,
  };

  const hasRequestedInitialGeo = useRef(false);
  const lastHandledTrigger = useRef(0);
  const lastBoundsKey = useRef('');

  const emitViewportBounds = useCallback(() => {
    const size = map.getSize();
    if (size.x === 0 || size.y === 0) return;

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
  }, [map]);

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
        callbacksRef.current.onUserLocationFound([lat, lon]);
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

  useMapEvents({
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
  onRenderModeChange,
}: CenteredAoiMapProps) {
  const { t } = useLanguage();
  const [internalMode, setInternalMode] = useState<MapRenderMode>('harmonized');
  const [userCoords, setUserCoords] = useState<[number, number] | null>(null);
  const [locateTrigger, setLocateTrigger] = useState<number>(0);
  const [isPickingLocation, setIsPickingLocation] = useState<boolean>(false);
  const [geoHasError, setGeoHasError] = useState<boolean>(false);

  const activeMode = controlledMode ?? internalMode;

  const handleModeChange = (mode: MapRenderMode) => {
    setInternalMode(mode);
    onRenderModeChange?.(mode);
  };

  // In footprint mode, sort by zOrder (G1 at bottom -> G4 on top)
  const orderedHotspots = activeMode === 'footprint'
    ? sortHotspotsByZOrder(hotspots)
    : hotspots;

  return (
    <div
      style={{
        position: 'relative',
        height: '100%',
        width: '100%',
        cursor: isPickingLocation ? 'crosshair' : 'grab',
      }}
    >
      <MapContainer center={[-32.0, -61.5]} zoom={6} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ViewportAndGeolocationController
          onBoundsChange={onBoundsChange}
          onUserLocationFound={(coords) => {
            setUserCoords(coords);
            setGeoHasError(false);
          }}
          onGeoError={() => setGeoHasError(true)}
          locateTrigger={locateTrigger}
          isPickingLocation={isPickingLocation}
          onLocationPicked={(coords) => {
            setUserCoords(coords);
            setIsPickingLocation(false);
            setGeoHasError(false);
          }}
        />

        {/* USER LOCATION MARKER (centered via GPS or manual pick) */}
        {userCoords && (
          <CircleMarker
            center={userCoords}
            radius={9}
            pathOptions={{
              color: '#ffffff',
              fillColor: '#0284c7',
              fillOpacity: 0.95,
              weight: 3,
            }}
          >
            <Tooltip direction="top" offset={[0, -8]} opacity={0.95} permanent>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#0369a1' }}>
                📍 {t.userLocationTooltip}: {userCoords[0].toFixed(4)}°, {userCoords[1].toFixed(4)}°
              </div>
            </Tooltip>
          </CircleMarker>
        )}

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
                eventHandlers={{
                  click: () => onSelectHotspot?.(hs),
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
                eventHandlers={{
                  click: () => onSelectHotspot?.(hs),
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

      {/* Floating Spatial Representation & Geolocation Card */}
      <div
        style={{
          position: 'absolute',
          top: '12px',
          right: '12px',
          zIndex: 1001,
          background: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(4px)',
          borderRadius: '8px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.18)',
          padding: '10px 14px',
          border: '1px solid #cbd5e1',
          maxWidth: '355px',
        }}
      >
        <div style={{ fontSize: '12px', fontWeight: 700, color: '#0f172a', marginBottom: '6px' }}>
          {t.mapControlTitle}
        </div>

        {/* Geolocation Controls: Auto-GPS + Manual Map Pin */}
        <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => {
              setIsPickingLocation(false);
              setGeoHasError(false);
              setLocateTrigger((n) => n + 1);
            }}
            style={{
              padding: '4px 8px',
              fontSize: '11px',
              fontWeight: 600,
              background: '#f0f9ff',
              color: '#0369a1',
              border: '1px solid #bae6fd',
              borderRadius: '5px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {t.locateMeBtn}
          </button>

          <button
            type="button"
            onClick={() => {
              setGeoHasError(false);
              setIsPickingLocation((prev) => !prev);
            }}
            style={{
              padding: '4px 8px',
              fontSize: '11px',
              fontWeight: 600,
              background: isPickingLocation ? '#0284c7' : '#f8fafc',
              color: isPickingLocation ? '#ffffff' : '#334155',
              border: `1px solid ${isPickingLocation ? '#0369a1' : '#cbd5e1'}`,
              borderRadius: '5px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {isPickingLocation ? t.pickLocationActiveBtn : t.pickLocationBtn}
          </button>
        </div>

        {geoHasError && (
          <div
            style={{
              fontSize: '10px',
              color: '#b45309',
              background: '#fffbeb',
              border: '1px solid #fde68a',
              borderRadius: '4px',
              padding: '4px 8px',
              marginBottom: '8px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>⚠️ {t.geoErrorNotice}</span>
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
              }}
            >
              ×
            </button>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              cursor: 'pointer',
              color: activeMode === 'harmonized' ? '#0f172a' : '#64748b',
              fontWeight: activeMode === 'harmonized' ? 600 : 400,
            }}
          >
            <input
              type="radio"
              name="mapRenderMode"
              value="harmonized"
              checked={activeMode === 'harmonized'}
              onChange={() => handleModeChange('harmonized')}
              style={{ cursor: 'pointer' }}
            />
            {t.mapRadioHarmonized}
          </label>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              cursor: 'pointer',
              color: activeMode === 'footprint' ? '#0f172a' : '#64748b',
              fontWeight: activeMode === 'footprint' ? 600 : 400,
            }}
          >
            <input
              type="radio"
              name="mapRenderMode"
              value="footprint"
              checked={activeMode === 'footprint'}
              onChange={() => handleModeChange('footprint')}
              style={{ cursor: 'pointer' }}
            />
            {t.mapRadioFootprint}
          </label>
        </div>

        {/* Legend for 4 Satellite Generations (when footprint mode is active) */}
        {activeMode === 'footprint' && (
          <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid #e2e8f0', fontSize: '11px' }}>
            <div style={{ fontWeight: 600, color: '#475569', marginBottom: '4px' }}>
              {t.mapFootprintLegendTitle}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
              {(['G1', 'G2', 'G3', 'G4'] as const).map((genKey) => {
                const info = SATELLITE_GENERATIONS[genKey];
                return (
                  <div key={genKey} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span
                      style={{
                        width: '12px',
                        height: '12px',
                        borderRadius: '50%',
                        backgroundColor: info.color,
                        border: `1.5px solid ${info.strokeColor}`,
                        display: 'inline-block',
                      }}
                    />
                    <span style={{ color: '#1e293b' }}>
                      <strong>{genKey}:</strong> {info.name} ({info.resolutionMeters}m)
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
