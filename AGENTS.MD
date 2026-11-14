# AGENT.md — Project Context & Architectural Guidelines

## 1. Project Overview
* **Event:** 2026 NASA Space Apps Challenge
* **Challenge:** Harmonization of MODIS and VIIRS Hot Spots (authored by Marina Campanucci, CONAE — Argentina's space agency).
* **Core Objective:** Build an interactive web application featuring a **Burning Activity Calendar** (2000–present) based on harmonized active fire hotspot records from NASA FIRMS (MODIS and VIIRS). The application must eliminate sensor discrepancies so emergency responders, scientists, and land managers can examine seasonal fire patterns, historical baselines, and anomalies within a user-selected Area of Interest (AOI).
* **Key Functional Requirements:**
  * Interactive map with a sliding/resizable coordinate window (bounding box, polygon, or lat/lon + radius) that dynamically queries the backend for spatial-temporal fire data.
  * Multi-year **Burning Activity Calendar** (Year × Month matrix heatmap, ~2001–2026) using accessible, colorblind-safe sequential color ramps.
  * Statistical anomaly comparisons (current/selected period vs. multi-year historical median and percentiles).
  * One-click **CSV export** of harmonized hotspot detections and summary metrics for the selected AOI and date range.

---

## 2. Team Topology & Parallel Workflow
The team consists of **3 members** working in parallel:
1. **Teammate 1 (MODIS Track):** Cleans, filters, and spatially bins historical & near-real-time MODIS (`MODIS_SP`, `MODIS_NRT`, 1 km resolution, 2000–present) data.
2. **Teammate 2 (VIIRS & Calibration Track):** Cleans, deduplicates multi-satellite passes (`VIIRS_SNPP`, `VIIRS_NOAA20`, `VIIRS_NOAA21`, 375 m resolution, 2012–present), spatially bins records, and builds the statistical calibration model (e.g., quantile mapping, overlap regression, or CDF matching over the 2012–present overlap window) to produce a unified, sensor-agnostic hotspot series.
3. **Lead Web Developer (Current Context / User):** Scaffolds and builds the full-stack web application immediately using decoupled mock data while Teammates 1 & 2 finalize their data analysis and schema contract.

---

## 3. Architectural Principles & Decoupling Strategy
Because the exact output schema and spatial grid system (e.g., H3 hexagons vs. regular lat/lon grid cells) from the data tracks are still being finalized, **all frontend and API layers must be strictly decoupled from raw dataset schemas**:

* **Adapter / Repository Pattern:** Isolate all data ingestion and column mapping inside a single adapter module (`src/services/dataAdapter.ts` on frontend, `backend/adapters/team_schema_mapper.py` on backend). UI components must never depend on raw NASA FIRMS or teammate CSV column names.
* **Mock-First Development:** Use a deterministic mock data generator (`mockGenerator.ts`) that simulates 2001–2026 seasonal fire spikes and extreme anomaly years inside any queried bounding box (`bbox`). Once teammates freeze their schema contract, only the adapter layer is updated.

---

## 4. Recommended Tech Stack (100% FOSS / Libre)
* **Frontend Framework:** React + TypeScript (Vite).
* **Mapping & Spatial Selection (Strict FOSS Requirement):**
  * **Primary Option:** **MapLibre GL JS** (`maplibre-gl`, BSD-3-Clause) paired with **`terra-draw`** (MIT) or **`@mapbox/mapbox-gl-draw`** (MIT) for resizable/draggable bounding-box and polygon windows, plus free vector tiles from **OpenFreeMap** (`https://tiles.openfreemap.org/styles/liberty`) or **NASA GIBS** satellite raster overlays.
  * **Alternative Option:** **Leaflet** (`react-leaflet`, BSD-2-Clause) + **`@geoman-io/leaflet-geoman-free`** (MIT) for rapid DOM-based bounding-box selection.
* **Backend / Query Engine:** Python **FastAPI** + **DuckDB** (or client-side **DuckDB-Wasm** for zero-server static deployment) querying pre-aggregated Parquet/CSV files, plus optional live proxy to NASA FIRMS NRT API.

---

## 5. Core Domain Models & Data Contracts

### Internal UI TypeScript Interfaces (`src/types/hotspot.ts`)
```typescript
export interface AreaOfInterest {
  type: 'bbox' | 'polygon' | 'point_radius';
  bounds: [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]
  geojson?: GeoJSON.Polygon;
  label?: string;
}

export interface HarmonizedCellRecord {
  id: string;
  lat: number;
  lon: number;
  date: string;              // YYYY-MM-DD
  year: number;
  month: number;             // 1-12
  harmonizedCount: number;   // Calibrated hotspot count (sensor-agnostic)
  harmonizedFrp: number;     // Calibrated Fire Radiative Power (MW)
  sourceSensor?: 'MODIS' | 'VIIRS' | 'BLENDED'; // Audit/tooltip metadata only
}

export interface MonthlyCalendarCell {
  year: number;
  month: number;             // 1-12
  count: number;
  historicalMedian: number;
  anomalyPct: number;        // % deviation vs. multi-year median
  severity: 'low' | 'normal' | 'elevated' | 'extreme';
}