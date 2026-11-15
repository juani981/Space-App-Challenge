import { useCallback, useEffect, useState } from 'react';
import { Circle, CircleMarker, MapContainer, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import type { AoiBounds, UnifiedHotspot } from '../services/apiClient';
import {
  SATELLITE_GENERATIONS,
  getSatelliteGeneration,
  sortHotspotsByZOrder,
} from '../utils/satelliteGenerations';

export type MapRenderMode = 'harmonized' | 'footprint';

export interface CenteredAoiMapProps {
  /** Callback fired whenever the map is dragged or zoomed underneath the centered box */
  onBoundsChange: (bounds: AoiBounds) => void;
  /** Harmonized hotspots returned by the backend to display inside the AOI */
  hotspots?: UnifiedHotspot[];
  /** Currently selected hotspot to highlight on the map */
  selectedHotspot?: UnifiedHotspot | null;
  /** Callback fired when the user clicks a hotspot marker */
  onSelectHotspot?: (hotspot: UnifiedHotspot) => void;
  /** Fraction of the map viewport width/height occupied by the centered orange box (0.1 to 0.9) */
  boxRatio?: number;
  /** Controlled render mode ('harmonized' vs 'footprint') */
  renderMode?: MapRenderMode;
  /** Callback fired when render mode changes */
  onRenderModeChange?: (mode: MapRenderMode) => void;
}

/**
 * SRP: Only responsible for reading the Leaflet viewport and converting the
 * centered viewfinder pixel rectangle into geographic (lat/lon) coordinates.
 */
function ViewportBoxTracker({
  boxRatio,
  onBoundsChange,
}: {
  boxRatio: number;
  onBoundsChange: (bounds: AoiBounds) => void;
}) {
  const map = useMap();

  const syncBoundsFromCenterBox = useCallback(() => {
    const size = map.getSize();
    if (size.x === 0 || size.y === 0) return;

    const marginFactor = (1 - boxRatio) / 2;
    const leftX = size.x * marginFactor;
    const rightX = size.x * (1 - marginFactor);
    const topY = size.y * marginFactor;
    const bottomY = size.y * (1 - marginFactor);

    const southWest = map.containerPointToLatLng([leftX, bottomY]);
    const northEast = map.containerPointToLatLng([rightX, topY]);

    onBoundsChange({
      minLon: Number(southWest.lng.toFixed(4)),
      minLat: Number(southWest.lat.toFixed(4)),
      maxLon: Number(northEast.lng.toFixed(4)),
      maxLat: Number(northEast.lat.toFixed(4)),
    });
  }, [map, boxRatio, onBoundsChange]);

  useEffect(() => {
    syncBoundsFromCenterBox();
  }, [syncBoundsFromCenterBox]);

  useMapEvents({
    move: syncBoundsFromCenterBox,
    zoom: syncBoundsFromCenterBox,
    resize: syncBoundsFromCenterBox,
  });

  return null;
}

/**
 * Map component with centered orange AOI viewfinder, clickable hotspot markers,
 * and a Radio Toggle between:
 * 1. "Ver puntos armonizados" (estilo homogéneo calibrado)
 * 2. "Discriminar por satélite y huella real en metros" (huellas físicas con <Circle> y zOrder G1->G4).
 */
export function CenteredAoiMap({
  onBoundsChange,
  hotspots = [],
  selectedHotspot = null,
  onSelectHotspot,
  boxRatio = 0.5,
  renderMode: controlledMode,
  onRenderModeChange,
}: CenteredAoiMapProps) {
  const [internalMode, setInternalMode] = useState<MapRenderMode>('harmonized');
  const activeMode = controlledMode ?? internalMode;

  const handleModeChange = (mode: MapRenderMode) => {
    setInternalMode(mode);
    onRenderModeChange?.(mode);
  };

  const offsetPct = ((1 - boxRatio) / 2) * 100;
  const sizePct = boxRatio * 100;

  // In footprint mode, sort by zOrder (G1 at bottom -> G4 on top)
  const orderedHotspots = activeMode === 'footprint'
    ? sortHotspotsByZOrder(hotspots)
    : hotspots;

  return (
    <div style={{ position: 'relative', height: '100%', width: '100%' }}>
      <MapContainer center={[-32.0, -61.5]} zoom={6} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ViewportBoxTracker boxRatio={boxRatio} onBoundsChange={onBoundsChange} />

        {/* HOTSPOT RENDERING LAYER */}
        {orderedHotspots.map((hs, idx) => {
          const isSelected =
            selectedHotspot !== null &&
            selectedHotspot.lat === hs.lat &&
            selectedHotspot.lon === hs.lon &&
            selectedHotspot.datetime_utc === hs.datetime_utc;

          const gen = getSatelliteGeneration(hs.satellite);
          const key = `${hs.datetime_utc}-${hs.lat}-${hs.lon}-${idx}`;

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
                    {isCluster && <span style={{ color: '#d97706', fontWeight: 600 }}>Foco fusionado (cluster)</span>}
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
                    Huella física: {gen.resolutionMeters}m ({gen.footprintRadiusMeters}m radio)<br />
                    FRP: {hs.frp} MW | Confianza: {hs.confidence}<br />
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

      {/* Floating Mode Selector Card (Radio Toggle) */}
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
          maxWidth: '310px',
        }}
      >
        <div style={{ fontSize: '12px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
          Modo de Visualización Espacial
        </div>
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
            Ver puntos armonizados (Homogéneo)
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
            Discriminar por satélite y huella real (metros)
          </label>
        </div>

        {/* Legend for 4 Satellite Generations (when footprint mode is active) */}
        {activeMode === 'footprint' && (
          <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid #e2e8f0', fontSize: '11px' }}>
            <div style={{ fontWeight: 600, color: '#475569', marginBottom: '4px' }}>
              Huella física en el suelo:
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

      {/* Fixed Centered Orange AOI Box Overlay (pointerEvents: 'none' lets map drag freely underneath) */}
      <div
        style={{
          position: 'absolute',
          top: `${offsetPct}%`,
          left: `${offsetPct}%`,
          width: `${sizePct}%`,
          height: `${sizePct}%`,
          border: '3px solid #ea580c',
          backgroundColor: 'rgba(234, 88, 12, 0.12)',
          boxSizing: 'border-box',
          pointerEvents: 'none',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: '#ea580c',
          }}
        />
      </div>
    </div>
  );
}
