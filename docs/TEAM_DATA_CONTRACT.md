# Provisional Team Data Contract (`TEAM_DATA_CONTRACT.md`)

> **Persistent Context Guard:** Any time a data model, Pydantic schema, TypeScript interface, or adapter mapping is created or modified in this repository, the agent **must** first assess this document and [backend/team_contract.py](../backend/team_contract.py) for contrast.

---

## 1. Architectural Context
* Teammates 1 & 2 are harmonizing **MODIS (`UMD, MCD14ML`)** and **VIIRS (`FIRMS, NOAA-20 / S-NPP / NOAA-21`)** upstream into a **single unified dataset/interface**.
* Because their exact output column names are still a Work in Progress (WIP), our system isolates their naming choices inside `TEAM_FIELD_MAP` in [backend/team_contract.py](../backend/team_contract.py) and exposes a stable internal `UnifiedHotspot` model to the rest of the application.
* **Excluded Concept:** Dataset `version` (`061.03` vs `2` / `2.0NRT`) was explicitly deemed irrelevant for our application domain and is excluded from the contract.

---

## 2. The 10 Canonical Concepts & Provisional Mapping

Reference image: [WhatsApp Image 2026-11-14 at 19.32.45.jpeg](./WhatsApp%20Image%202026-11-14%20at%2019.32.45.jpeg)

| # | Concept (Spanish) | Internal Field (`UnifiedHotspot`) | Provisional Team Key (`TEAM_FIELD_MAP`) | Type | Upstream MODIS (`MCD14ML`) Origin | Upstream VIIRS (`FIRMS`) Origin |
| :- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **Fecha y hora UTC** | `datetime_utc` | `"datetime_utc"` | `str` | `YYYYMMDD` + `HHMM` | `acq_date` + `acq_time` (`HHMM`) |
| 2 | **Satélite** | `satellite` | `"satellite"` | `str` | `sat` (`T` or `A`) | `satellite` (`N20`, `N`, `N21`) |
| 3a | **Posición (Lat)** | `lat` | `"lat"` | `float` | `lat` | `latitude` |
| 3b | **Posición (Lon)** | `lon` | `"lon"` | `float` | `lon` | `longitude` |
| 4 | **Temperatura 1** | `temp_1` | `"temp_1"` | `float \| None` | `T21` | `brightness` (Band I-4) |
| 5 | **Temperatura 2** | `temp_2` | `"temp_2"` | `float \| None` | `T31` | `bright_t31` (Band I-5) |
| 6 | **Geometría del píxel** | `pixel_geom` | `"pixel_area_km2"` | `float \| None` | `sample` (`0–1353`) | `scan`, `track` (in km) |
| 7 | **Potencia radiativa** | `frp` | `"frp"` | `float` | `FRP` (MW) | `frp` |
| 8 | **Confianza** | `confidence` | `"confidence"` | `str` | `conf` (`0–100`) | `confidence` (`l` / `n` / `h`) |
| 9 | **Tipo** | `fire_type` | `"type"` | `int \| None` | `type` (`0–3`) | `type` (archive only) |
| 10 | **Día/noche** | `day_night` | `"daynight"` | `str \| None` | `dn` | `daynight` |

---

## 3. How to Update When Teammates Freeze Their Schema
1. Open [backend/team_contract.py](../backend/team_contract.py).
2. Update the right-hand string values in `TEAM_FIELD_MAP` to match the final column/JSON keys delivered by Teammates 1 & 2.
3. Update the **Provisional Team Key** column in the table above so persistent documentation stays in sync.
