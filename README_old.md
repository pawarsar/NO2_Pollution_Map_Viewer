# NO₂ Pollution Map Viewer — Live Sentinel-5P via Google Earth Engine

A POC-level Streamlit web application that visualizes near-real-time tropospheric NO₂
concentration over any user-provided polygon using live Google Earth Engine satellite data.

---

## ✅ Features

| Feature | Status |
|---|---|
| Live GEE data fetch (OFFL + NRTI fallback) | ✅ |
| Draw polygon on map or upload GeoJSON | ✅ |
| Date selector with ±7 day fallback logic | ✅ |
| NO₂ heatmap tile overlay (YlOrRd / Inferno) | ✅ |
| Color legend with units | ✅ |
| Statistics card (mean / min / max / coverage) | ✅ |
| Light / Dark theme toggle | ✅ |
| Max zoom ~200 m (zoom level 15) | ✅ |
| QA mask (≥0.75 OFFL, ≥0.5 NRTI) | ✅ |
| 7-day trend chart (optional) | ✅ |
| Info drawer | ✅ |
| GEE result caching (TTL 2h) | ✅ |
| Graceful error handling | ✅ |

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Authenticate with Google Earth Engine

You need a GEE account: https://earthengine.google.com/

```bash
earthengine authenticate
```

This creates a credentials file at `~/.config/earthengine/credentials`.

**Or** for service account / CI use, set:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

Then initialize with your project:
```bash
python -c "import ee; ee.Initialize(project='your-gee-project-id')"
```

### 3. Run the app

```bash
streamlit run app.py
```

Then open http://localhost:8501

---

## 🗺️ How to Use

1. **Select a date** — the app will find the closest available Sentinel-5P image within ±7 days
2. **Define your AOI** (Area of Interest) — choose one of:
   - **Draw on map** — use the polygon draw tool in the map toolbar, then copy the GeoJSON coordinates into the text box below the map
   - **Upload GeoJSON** — upload a `.geojson` file
3. **View the NO₂ heatmap** — live GEE tiles will appear on the map
4. **Read statistics** — mean/min/max NO₂ column density and pixel coverage are shown below the map
5. **Toggle 7-day trend** and **Info drawer** using the checkboxes

---

## 📐 Data Pipeline

```
User selects date + AOI polygon
        │
        ▼
GEE: COPERNICUS/S5P/OFFL/L3_NO2
   filter by date ±7d, bounds
   mask QA ≥ 0.75
        │
        ├─ No data? ──► fallback: COPERNICUS/S5P/NRTI/L3_NO2 (QA ≥ 0.5)
        │
        ├─► Sort by date_diff, select closest image
        │
        ├─► Visualize (YlOrRd / Inferno) → getMapId() → XYZ tile → Folium
        │
        └─► reduceRegion(mean/min/max/count, scale=7000) → stats cards
```

---

## ⚠️ Zoom Restriction

Map zoom is capped at **level 15** (~200–250 m/pixel at equator).
Sentinel-5P pixel size is ~3.5–7 km; finer zoom would misrepresent spatial detail.

---

## 📦 Architecture

```
app.py                  # Main Streamlit application
requirements.txt        # Python dependencies
README.md               # This file
```

---

## 🎨 Themes

| | Light (Marine Light) | Dark (Marine Night) |
|---|---|---|
| Background | #F0F4F8 | #0B1220 |
| Surface | #FFFFFF | #111827 |
| Primary | #1E88E5 | #60A5FA |
| Accent | #00B8D9 | #34D399 |
| Basemap | CartoDB Positron | CartoDB Dark Matter |
| NO₂ Palette | YlOrRd | Inferno |

---

## 📋 Dataset Details

| Property | Value |
|---|---|
| Primary dataset | `COPERNICUS/S5P/OFFL/L3_NO2` |
| Fallback dataset | `COPERNICUS/S5P/NRTI/L3_NO2` |
| Primary band | `tropospheric_NO2_column_number_density` |
| Fallback band | `NO2_column_number_density` |
| QA threshold (OFFL) | ≥ 0.75 |
| QA threshold (NRTI) | ≥ 0.50 |
| Spatial resolution | ~3.5–7 km |
| Temporal coverage | May 2018 – present |
| Units | mol/m² (column density) |
| Vis range | 0 – 0.0003 mol/m² |

---

## ⚠️ Disclaimer

This is a **proof-of-concept (POC)** tool for exploratory visualization only.
It is **not** a regulatory air quality index (AQI) tool.
Values represent tropospheric column density (mol/m²), not ground-level concentrations.
Do not use for health, regulatory, or policy decisions.

---

## 🔧 Troubleshooting

| Issue | Fix |
|---|---|
| `EEException: Not signed up for Google Earth Engine` | Register at https://earthengine.google.com and run `earthengine authenticate` |
| `EEException: project is not registered` | Set project with `ee.Initialize(project='my-project')` |
| Map tiles not loading | Check GEE quota; wait for rate limit reset |
| `ImportError: geemap` | Run `pip install geemap streamlit-folium` |
| Statistics very slow | Normal for large polygons; GEE compute time scales with AOI size |

---

Built with ❤️ using **Google Earth Engine** · **Python** · **Streamlit** · **geemap** · **Folium**