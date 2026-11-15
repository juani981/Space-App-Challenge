export interface SatelliteGenerationInfo {
  generation: 'G1' | 'G2' | 'G3' | 'G4';
  name: string;
  satellites: string[];
  sensor: string;
  period: string;
  resolutionMeters: number;
  footprintRadiusMeters: number;
  color: string;
  strokeColor: string;
  fillOpacity: number;
  zIndex: number;
  description: string;
}

export const SATELLITE_GENERATIONS: Record<'G1' | 'G2' | 'G3' | 'G4', SatelliteGenerationInfo> = {
  G1: {
    generation: 'G1',
    name: 'MODIS (Terra / Aqua)',
    satellites: ['T', 'A', 'TERRA', 'AQUA'],
    sensor: 'MODIS',
    period: '2000–2026',
    resolutionMeters: 1000,
    footprintRadiusMeters: 500,
    color: '#f59e0b', // Amber
    strokeColor: '#b45309',
    fillOpacity: 0.25,
    zIndex: 10,
    description: 'Píxel amplio de 1 km² — Base histórica multidecadal',
  },
  G2: {
    generation: 'G2',
    name: 'VIIRS Suomi-NPP',
    satellites: ['N', 'SNPP', 'S-NPP'],
    sensor: 'VIIRS',
    period: '2012–2026',
    resolutionMeters: 750,
    footprintRadiusMeters: 375,
    color: '#3b82f6', // Blue
    strokeColor: '#1d4ed8',
    fillOpacity: 0.4,
    zIndex: 20,
    description: 'Transición MODIS -> VIIRS (750m / 375m I-Band)',
  },
  G3: {
    generation: 'G3',
    name: 'VIIRS NOAA-20 (JPSS-1)',
    satellites: ['N20', 'NOAA-20', 'JPSS-1'],
    sensor: 'VIIRS',
    period: '2017–2026',
    resolutionMeters: 375,
    footprintRadiusMeters: 187.5,
    color: '#10b981', // Emerald green
    strokeColor: '#047857',
    fillOpacity: 0.55,
    zIndex: 30,
    description: 'Alta resolución espacial 375m en nadir',
  },
  G4: {
    generation: 'G4',
    name: 'VIIRS NOAA-21 (JPSS-2)',
    satellites: ['N21', 'NOAA-21', 'JPSS-2'],
    sensor: 'VIIRS',
    period: '2023–2026',
    resolutionMeters: 375,
    footprintRadiusMeters: 187.5,
    color: '#8b5cf6', // Violet
    strokeColor: '#6d28d9',
    fillOpacity: 0.7,
    zIndex: 40,
    description: 'Constelación moderna más reciente a 375m',
  },
};

/**
 * Returns generation metadata given a satellite code (e.g. 'T', 'A', 'N', 'N20', 'N21').
 */
export function getSatelliteGeneration(satellite: string): SatelliteGenerationInfo {
  const satUpper = (satellite || '').trim().toUpperCase();

  if (SATELLITE_GENERATIONS.G1.satellites.includes(satUpper)) {
    return SATELLITE_GENERATIONS.G1;
  }
  if (SATELLITE_GENERATIONS.G2.satellites.includes(satUpper)) {
    return SATELLITE_GENERATIONS.G2;
  }
  if (SATELLITE_GENERATIONS.G3.satellites.includes(satUpper)) {
    return SATELLITE_GENERATIONS.G3;
  }
  if (SATELLITE_GENERATIONS.G4.satellites.includes(satUpper)) {
    return SATELLITE_GENERATIONS.G4;
  }

  // Default to G3 if unspecified
  return SATELLITE_GENERATIONS.G3;
}

/**
 * Sorts hotspots by z-order so large footprint sensors (G1 1000m) are rendered first
 * in the background, and sharp high-resolution sensors (G4 375m) render in the foreground.
 */
export function sortHotspotsByZOrder<T extends { satellite: string }>(hotspots: T[]): T[] {
  return [...hotspots].sort((a, b) => {
    const genA = getSatelliteGeneration(a.satellite);
    const genB = getSatelliteGeneration(b.satellite);
    return genA.zIndex - genB.zIndex;
  });
}
