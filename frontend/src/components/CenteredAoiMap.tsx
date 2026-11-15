import { useCallback, useEffect } from 'react';
import { CircleMarker, MapContainer, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import type { AoiBounds, UnifiedHotspot } from '../services/apiClient';

export interface CenteredAoiMapProps {
  /** Callback fired whenever the map is dragged or zoomed underneath the centered box */
  onBoundsChange: (bounds: AoiBounds) => void;
  /** Harmonized hotspots returned by the backend to display inside the AOI */
  hotspots?: UnifiedHotspot[];
  /** Currently selected hotspot to highlight on the map */
  selectedHotspot?: UnifiedHotspot | null;
  /** Callback fired when the user clicks a red hotspot marker */
  onSelectHotspot?: (hotspot: UnifiedHotspot) => void;
  /** Fraction of the map viewport width/height occupied by the centered orange box (0.1 to 0.9) */
  boxRatio?: number;
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
 * SRP & OCP: Self-contained map component with a fixed, centered orange AOI reticle
 * and clickable red hotspot markers that delegate inspection to the right side panel.
 */
export function CenteredAoiMap({
  onBoundsChange,
  hotspots = [],
  selectedHotspot = null,
  onSelectHotspot,
  boxRatio = 0.5,
}: CenteredAoiMapProps) {
  const offsetPct = ((1 - boxRatio) / 2) * 100;
  const sizePct = boxRatio * 100;

  return (
    <div style={{ position: 'relative', height: '100%', width: '100%' }}>
      <MapContainer center={[-32.0, -61.5]} zoom={5} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ViewportBoxTracker boxRatio={boxRatio} onBoundsChange={onBoundsChange} />

        {hotspots.map((hs, idx) => {
          const isSelected =
            selectedHotspot !== null &&
            selectedHotspot.lat === hs.lat &&
            selectedHotspot.lon === hs.lon &&
            selectedHotspot.datetime_utc === hs.datetime_utc;

          return (
            <CircleMarker
              key={`${hs.datetime_utc}-${hs.lat}-${hs.lon}-${idx}`}
              center={[hs.lat, hs.lon]}
              radius={isSelected ? 9 : 6}
              eventHandlers={{
                click: () => onSelectHotspot?.(hs),
              }}
              pathOptions={{
                color: isSelected ? '#0f172a' : '#991b1b',
                fillColor: '#ef4444',
                fillOpacity: isSelected ? 1.0 : 0.85,
                weight: isSelected ? 3 : 1.5,
              }}
            />
          );
        })}
      </MapContainer>

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
