import { useCallback, useEffect } from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import type { AoiBounds, UnifiedHotspot } from '../services/apiClient';

export interface CenteredAoiMapProps {
  /** Callback fired whenever the map is dragged or zoomed underneath the centered box */
  onBoundsChange: (bounds: AoiBounds) => void;
  /** Harmonized hotspots returned by the backend to display inside the AOI */
  hotspots?: UnifiedHotspot[];
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
 * and optional hotspot markers inside the queried region.
 */
export function CenteredAoiMap({
  onBoundsChange,
  hotspots = [],
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

        {hotspots.map((hs, idx) => (
          <CircleMarker
            key={`${hs.datetime_utc}-${hs.lat}-${hs.lon}-${idx}`}
            center={[hs.lat, hs.lon]}
            radius={6}
            pathOptions={{
              color: '#991b1b',
              fillColor: '#ef4444',
              fillOpacity: 0.85,
              weight: 1.5,
            }}
          >
            <Popup>
              <div style={{ fontSize: '12px', lineHeight: 1.4 }}>
                <strong>Satellite:</strong> {hs.satellite} ({hs.day_night})<br />
                <strong>UTC:</strong> {hs.datetime_utc}<br />
                <strong>FRP:</strong> {hs.frp} MW<br />
                <strong>Confidence:</strong> {hs.confidence}<br />
                <strong>Coords:</strong> {hs.lat}, {hs.lon}
              </div>
            </Popup>
          </CircleMarker>
        ))}
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
