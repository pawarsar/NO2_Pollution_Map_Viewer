"""
NO₂ Pollution Map Viewer — Live Sentinel-5P via Google Earth Engine
POC application — not a regulatory AQI tool.
"""

import streamlit as st
import json
import datetime
import time
from typing import Optional

# ── Page config (must be first Streamlit call) ──────────────────────────────
st.set_page_config(
    page_title="NO₂ Pollution Map | Sentinel-5P GEE",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Lazy imports with friendly error handling ────────────────────────────────
try:
    import ee
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False

try:
    import geemap
    import folium
    from folium.plugins.draw import Draw
    from folium.plugins.measure_control import MeasureControl
    GEEMAP_AVAILABLE = True
except ImportError:
    GEEMAP_AVAILABLE = False

try:
    from streamlit_folium import folium_static
    ST_FOLIUM_AVAILABLE = True
except ImportError:
    ST_FOLIUM_AVAILABLE = False

# ── Theme state ──────────────────────────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
if "polygon_geojson" not in st.session_state:
    st.session_state.polygon_geojson = None
if "drawn_polygon" not in st.session_state:
    st.session_state.drawn_polygon = None

DARK = st.session_state.dark_mode

# ── CSS themes ───────────────────────────────────────────────────────────────
LIGHT_CSS = """
:root {
    --bg:          #F0F4F8;
    --surface:     #FFFFFF;
    --surface2:    #EDF2F7;
    --text:        #0F172A;
    --muted:       #475569;
    --primary:     #1E88E5;
    --accent:      #00B8D9;
    --border:      #CBD5E0;
    --card-shadow: 0 2px 12px rgba(0,0,0,0.08);
    --warn-bg:     #FFF8E1;
    --warn-text:   #7B4F00;
    --success-bg:  #E6F4EA;
    --success-text:#1B5E20;
    --err-bg:      #FEECEC;
    --err-text:    #7F1D1D;
}
"""

DARK_CSS = """
:root {
    --bg:          #0B1220;
    --surface:     #111827;
    --surface2:    #1A2333;
    --text:        #E5E7EB;
    --muted:       #9CA3AF;
    --primary:     #60A5FA;
    --accent:      #34D399;
    --border:      #2D3748;
    --card-shadow: 0 2px 16px rgba(0,0,0,0.4);
    --warn-bg:     #2D2410;
    --warn-text:   #FCD34D;
    --success-bg:  #0D2E1A;
    --success-text:#6EE7B7;
    --err-bg:      #2D1010;
    --err-text:    #FCA5A5;
}
"""

COMMON_CSS = """
/* ── Reset & Base ─────────────────────────────────────────────────────────── */
html, body, [data-testid="stApp"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'IBM Plex Sans', 'Helvetica Neue', sans-serif;
}

/* ── Hide Streamlit chrome ─────────────────────────────────────────────────── */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
.block-container { padding-top: 0 !important; max-width: 1400px; }

/* ── Google Fonts ──────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=Space+Grotesk:wght@300;600;700&display=swap');

/* ── Hero Header ───────────────────────────────────────────────────────────── */
.hero {
    background: linear-gradient(135deg, var(--bg) 0%, var(--surface2) 100%);
    border-bottom: 1px solid var(--border);
    padding: 2rem 2.5rem 1.5rem;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -60px; right: -80px;
    width: 300px; height: 300px;
    border-radius: 50%;
    background: radial-gradient(circle, var(--primary)18, transparent 70%);
    pointer-events: none;
}
.hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0.25rem 0.75rem;
    font-size: 0.72rem;
    font-family: 'IBM Plex Mono', monospace;
    color: var(--accent);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 0.75rem;
}
.hero-badge::before { content: '●'; font-size: 0.6rem; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

.hero h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: clamp(1.6rem, 3vw, 2.4rem);
    font-weight: 700;
    color: var(--text);
    margin: 0 0 0.4rem;
    letter-spacing: -0.03em;
    line-height: 1.15;
}
.hero h1 sup {
    font-size: 0.6em;
    vertical-align: super;
}
.hero p {
    font-size: 0.95rem;
    color: var(--muted);
    max-width: 640px;
    line-height: 1.6;
    margin: 0;
}
.hero-meta {
    display: flex; gap: 1.5rem; margin-top: 1rem;
    flex-wrap: wrap;
}
.hero-meta span {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: var(--muted);
    letter-spacing: 0.04em;
}
.hero-meta strong { color: var(--primary); }

/* ── Stat Cards ────────────────────────────────────────────────────────────── */
.stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
    margin: 1.25rem 0;
}
.stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.1rem 1.25rem;
    box-shadow: var(--card-shadow);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.stat-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 24px rgba(0,0,0,0.12);
}
.stat-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    font-family: 'IBM Plex Mono', monospace;
    margin-bottom: 0.35rem;
}
.stat-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.3rem;
    font-weight: 600;
    color: var(--text);
    line-height: 1.2;
}
.stat-unit {
    font-size: 0.65rem;
    color: var(--muted);
    margin-top: 0.2rem;
}
.stat-accent { color: var(--accent) !important; }

/* ── Banner messages ───────────────────────────────────────────────────────── */
.banner {
    border-radius: 10px;
    padding: 0.75rem 1rem;
    margin: 0.75rem 0;
    font-size: 0.88rem;
    display: flex; align-items: flex-start; gap: 0.6rem;
    border-left: 3px solid;
}
.banner-warn { background: var(--warn-bg); color: var(--warn-text); border-color: #F59E0B; }
.banner-success { background: var(--success-bg); color: var(--success-text); border-color: #10B981; }
.banner-err { background: var(--err-bg); color: var(--err-text); border-color: #EF4444; }
.banner-info { background: var(--surface2); color: var(--muted); border-color: var(--primary); }

/* ── Legend ────────────────────────────────────────────────────────────────── */
.legend-container {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.9rem 1.1rem;
    box-shadow: var(--card-shadow);
}
.legend-title {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    font-family: 'IBM Plex Mono', monospace;
    margin-bottom: 0.5rem;
}
.legend-bar {
    height: 14px;
    border-radius: 7px;
    margin: 0.3rem 0;
}
.legend-labels {
    display: flex;
    justify-content: space-between;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    color: var(--muted);
}
.legend-bar-light { background: linear-gradient(to right, #FFFFB2, #FED976, #FEB24C, #FD8D3C, #FC4E2A, #E31A1C, #B10026); }
.legend-bar-dark  { background: linear-gradient(to right, #000004, #1B0C41, #4A0C6B, #781C6D, #A52C60, #CF4446, #ED6925, #FB9906, #F7D03C, #FCFFA4); }

/* ── Info Drawer ───────────────────────────────────────────────────────────── */
.info-section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin: 1rem 0;
}
.info-section h4 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--primary);
    margin: 0 0 0.5rem;
}
.info-section p, .info-section li {
    font-size: 0.85rem;
    color: var(--muted);
    line-height: 1.65;
    margin: 0.2rem 0;
}
.info-section code {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    background: var(--surface2);
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    color: var(--accent);
}

/* ── Footer ────────────────────────────────────────────────────────────────── */
.footer {
    border-top: 1px solid var(--border);
    padding: 1.25rem 2.5rem;
    margin-top: 2rem;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.5rem;
    font-size: 0.78rem;
    color: var(--muted);
    font-family: 'IBM Plex Mono', monospace;
}
.footer a { color: var(--primary); text-decoration: none; }
.footer a:hover { text-decoration: underline; }

/* ── Section headers ───────────────────────────────────────────────────────── */
.section-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin: 1.5rem 0 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
}
.section-header h3 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text);
    margin: 0;
    letter-spacing: -0.01em;
}
.section-icon {
    font-size: 1rem;
    line-height: 1;
}

/* ── Upload zone ────────────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    border: 2px dashed var(--border) !important;
    border-radius: 10px !important;
    background: var(--surface2) !important;
    transition: border-color 0.2s;
}
[data-testid="stFileUploader"]:hover { border-color: var(--primary) !important; }

/* ── Buttons ────────────────────────────────────────────────────────────────── */
.stButton > button {
    border-radius: 8px !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em !important;
    transition: all 0.15s ease !important;
    border: 1px solid var(--border) !important;
    background: var(--surface) !important;
    color: var(--text) !important;
}
.stButton > button:hover {
    background: var(--primary) !important;
    color: white !important;
    border-color: var(--primary) !important;
    transform: translateY(-1px);
}
button[kind="primary"] {
    background: var(--primary) !important;
    color: white !important;
    border-color: var(--primary) !important;
}

/* ── Sidebar ────────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}

/* ── Date input ─────────────────────────────────────────────────────────────── */
[data-testid="stDateInput"] input {
    background: var(--surface2) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
    font-family: 'IBM Plex Mono', monospace !important;
}

/* ── Selectbox ───────────────────────────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div {
    background: var(--surface2) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
}

/* ── Tooltips ─────────────────────────────────────────────────────────────── */
.tooltip {
    display: inline-block;
    background: var(--surface2);
    color: var(--muted);
    font-size: 0.75rem;
    border-radius: 6px;
    padding: 0.3rem 0.6rem;
    font-family: 'IBM Plex Mono', monospace;
    border: 1px solid var(--border);
}

/* ── Zoom warning badge ────────────────────────────────────────────────────── */
.zoom-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: var(--warn-bg);
    color: var(--warn-text);
    border-radius: 999px;
    padding: 0.25rem 0.7rem;
    font-size: 0.72rem;
    font-family: 'IBM Plex Mono', monospace;
    border: 1px solid #F59E0B44;
    margin-left: 0.5rem;
}
"""

theme_css = DARK_CSS if DARK else LIGHT_CSS
st.markdown(f"<style>{theme_css}{COMMON_CSS}</style>", unsafe_allow_html=True)

# ── GEE initialisation ────────────────────────────────────────────────────────
SERVICE_ACCOUNT = "synapse-earth@biopulse-486310.iam.gserviceaccount.com"
KEY_FILE = "biopulse-486310-f58108b6b328.json"

# @st.cache_resource
# def init_ee():
#     """Initialize GEE. Returns (success, message)."""
#     if not EE_AVAILABLE:
#         return False, "earthengine-api not installed. Run: pip install earthengine-api"
#     try:
#         ee.Initialize(opt_url='https://earthengine.googleapis.com')
#         return True, "GEE authenticated"
#     except Exception as e:
#         try:
#             ee.Initialize()
#             return True, "GEE authenticated (default project)"
#         except Exception as e2:
#             return False, str(e2)
@st.cache_resource
def init_gee():
    """Initialize Earth Engine with service account if provided.

    Why: Ensures authenticated access to datasets and operations; service
    accounts are reliable for headless scripts and CI.
    """
    # Use service account credentials when available; fall back to user auth
    if SERVICE_ACCOUNT and KEY_FILE:
        credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_FILE)
        ee.Initialize(credentials)  # Auth via service account
        return True, "GEE authenticated"
    else:
        ee.Initialize()  # Implicit auth (may prompt if not already authenticated)
        return True, "GEE authenticated (default project)"
    
GEE_OK, GEE_MSG = init_gee()

# ── GEE data helpers ──────────────────────────────────────────────────────────
OFFL = "COPERNICUS/S5P/OFFL/L3_NO2"
NRTI = "COPERNICUS/S5P/NRTI/L3_NO2"
OFFL_BAND = "tropospheric_NO2_column_number_density"
FB_BAND   = "NO2_column_number_density"

@st.cache_data(ttl=7200, show_spinner=False)
def fetch_no2_image(date_str: str, geojson_str: str):
    """
    Fetch best NO2 image for given date ± 7 days within AOI.
    Returns (image, actual_date_str, dataset_used, band_used, is_fallback, error_msg)
    """
    if not GEE_OK:
        return None, None, None, None, False, "GEE not available"
    try:
        aoi_geojson = json.loads(geojson_str)
        aoi = ee.Geometry(aoi_geojson)

        target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        start = (target_date - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        end   = (target_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        # def try_collection(dataset, band, qa_thresh):
        #     col = (ee.ImageCollection(dataset)
        #            .filterDate(start, end)
        #            .filterBounds(aoi)
        #            .select([band, "qa_value"]))
        #     def mask_qa(img):
        #         qa = img.select("qa_value")
        #         return img.updateMask(qa.gte(qa_thresh))
        #     col = col.map(mask_qa)
        #     return col.select(band)

        def try_collection(dataset, band, qa_thresh):
            """
            Build a filtered collection and, if a qa_value band exists,
            mask it by the supplied threshold.  `select` is called with
            strict=False so that missing qa bands do not raise.
            """
            col = (ee.ImageCollection(dataset)
                   .filterDate(start, end)
                   .filterBounds(aoi)
                   # do not error if qa_value is absent
                   .select([band, "qa_value"], None, False))

            def mask_qa(img):
                names = img.bandNames()
                def do_mask():
                    qa = img.select("qa_value", None, False)
                    return img.updateMask(qa.gte(qa_thresh))
                # only call the masking expression when the band exists
                return ee.Image(ee.Algorithms.If(names.contains("qa_value"),
                                                do_mask(),
                                                img))
            col = col.map(mask_qa)  # ← ADD THIS LINE after mask_qa definition
            return col.select(band)
    
        # Try OFFL first
        col = try_collection(OFFL, OFFL_BAND, 0.75)
        count = col.size().getInfo()
        dataset_used, band_used, qa_thresh = OFFL, OFFL_BAND, 0.75

        if count == 0:
            col = try_collection(NRTI, FB_BAND, 0.5)
            count = col.size().getInfo()
            dataset_used, band_used, qa_thresh = NRTI, FB_BAND, 0.5

        if count == 0:
            return None, None, None, None, False, f"No NO₂ imagery found within ±7 days of {date_str}"

        # Find closest image to target date
        def add_diff(img):
            img_date = ee.Date(img.date())
            target = ee.Date(date_str)
            diff = img_date.difference(target, "day").abs()
            return img.set("date_diff", diff)

        col_with_diff = col.map(add_diff)
        best = col_with_diff.sort("date_diff").first()
        actual_date = best.date().format("YYYY-MM-dd").getInfo()

        is_fallback = actual_date != date_str
        return best, actual_date, dataset_used, band_used, is_fallback, None

    except Exception as e:
        return None, None, None, None, False, str(e)


@st.cache_data(ttl=7200, show_spinner=False)
def compute_stats(date_str: str, geojson_str: str):
    """Compute mean/min/max/coverage stats for AOI."""
    image, actual_date, dataset, band, is_fallback, err = fetch_no2_image(date_str, st.session_state.geojson_str)
    if err or image is None:
        return None, err

    try:
        aoi = ee.Geometry(json.loads(geojson_str))
        stats = image.reduceRegion(
            reducer=ee.Reducer.mean().combine(ee.Reducer.min(), sharedInputs=True)
                         .combine(ee.Reducer.max(), sharedInputs=True)
                         .combine(ee.Reducer.count(), sharedInputs=True),
            geometry=aoi,
            scale=7000,
            maxPixels=1e13,
            bestEffort=True,
        ).getInfo()

        b = band
        mean_val  = stats.get(f"{b}_mean")
        min_val   = stats.get(f"{b}_min")
        max_val   = stats.get(f"{b}_max")
        count_val = stats.get(f"{b}_count")

        # Total pixels (unmasked)
        total = image.unmask(0).reduceRegion(
            reducer=ee.Reducer.count(),
            geometry=aoi,
            scale=7000,
            maxPixels=1e13,
            bestEffort=True,
        ).getInfo()
        total_count = total.get(b, 1) or 1
        coverage = round((count_val or 0) / max(total_count, 1) * 100, 1)

        return {
            "mean":      mean_val,
            "min":       min_val,
            "max":       max_val,
            "count":     count_val,
            "coverage":  coverage,
            "date":      actual_date,
            "dataset":   dataset,
            "band":      band,
            "fallback":  is_fallback,
        }, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=7200, show_spinner=False)
def get_tile_url(date_str: str, geojson_str: str, dark: bool):
    """Get XYZ tile URL from GEE for the NO2 layer."""
    image, actual_date, dataset, band, is_fallback, err = fetch_no2_image(date_str, st.session_state.geojson_str)
    if err or image is None:
        return None, err

    try:
        palette = ["000004","1B0C41","4A0C6B","781C6D","A52C60","CF4446","ED6925","FB9906","F7D03C","FCFFA4"] if dark \
             else ["FFFFB2","FED976","FEB24C","FD8D3C","FC4E2A","E31A1C","B10026"]

        vis_params = {
            "min": 0,
            "max": 0.0003,
            "palette": palette,
        }
        map_id = ee.Image(image).getMapId(vis_params)
        tile_url = map_id["tile_fetcher"].url_format
        return tile_url, None
    
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=7200, show_spinner=False)
def fetch_trend(geojson_str: str, end_date_str: str):
    """Fetch 7-day mean NO2 trend."""
    if not GEE_OK:
        return None
    try:
        aoi = ee.Geometry(json.loads(geojson_str))
        end   = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")
        start = end - datetime.timedelta(days=6)

        results = []
        for i in range(7):
            d = (start + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            next_d = (start + datetime.timedelta(days=i+1)).strftime("%Y-%m-%d")
            col = (ee.ImageCollection(OFFL)
                   .filterDate(d, next_d)
                   .filterBounds(aoi)
                   .select([OFFL_BAND, "qa_value"]))
            col = col.map(lambda img: img.updateMask(img.select("qa_value").gte(0.75)))
            img = col.select(OFFL_BAND).mean()
            stats = img.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi, scale=7000, maxPixels=1e13, bestEffort=True
            ).getInfo()
            val = stats.get(OFFL_BAND)
            results.append({"date": d, "mean": val})
        return results
    except Exception:
        return None


def format_no2(val):
    if val is None:
        return "N/A"
    return f"{val:.2e}"


def polygon_from_geojson(geojson_dict):
    """Extract first polygon geometry from a GeoJSON dict."""
    if not geojson_dict:
        return None
    t = geojson_dict.get("type")
    if t == "FeatureCollection":
        features = geojson_dict.get("features", [])
        if features:
            return features[0].get("geometry")
    elif t == "Feature":
        return geojson_dict.get("geometry")
    elif t in ("Polygon", "MultiPolygon"):
        return geojson_dict
    return None


# ── HEADER ───────────────────────────────────────────────────────────────────
theme_icon = "🌙" if DARK else "☀️"
theme_label = "Switch to Light" if DARK else "Switch to Dark"
basemap = "CartoDB.DarkMatter" if DARK else "CartoDB.Positron"

col_head, col_theme = st.columns([6, 1])
with col_head:
    st.markdown("""
    <div class="hero">
        <div class="hero-badge">🛰️ Live GEE Data &nbsp;·&nbsp; Sentinel-5P TROPOMI</div>
        <h1>NO<sup>₂</sup> Pollution Map</h1>
        <p>Visualizing tropospheric nitrogen dioxide over your selected region using live Google Earth Engine satellite data.</p>
        <div class="hero-meta">
            <span>Dataset: <strong>COPERNICUS/S5P/OFFL/L3_NO2</strong></span>
            <span>Resolution: <strong>~3.5–7 km</strong></span>
            <span>Band: <strong>tropospheric_NO₂_column_number_density</strong></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_theme:
    st.write("")
    st.write("")
    if st.button(f"{theme_icon} {theme_label}", key="theme_toggle"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

# ── GEE status banner ─────────────────────────────────────────────────────────
if not GEE_OK:
    st.markdown(f"""
    <div class="banner banner-err">
        ⚠️ <div><strong>GEE Not Connected</strong><br>
        {GEE_MSG}<br>
        <small>Run <code>earthengine authenticate</code> then restart, or set GOOGLE_APPLICATION_CREDENTIALS.</small></div>
    </div>""", unsafe_allow_html=True)
else:
    st.markdown("""<div class="banner banner-success">✅ <span>Google Earth Engine connected. Live satellite data active.</span></div>""",
                unsafe_allow_html=True)

# ── CONTROLS ROW ──────────────────────────────────────────────────────────────
st.markdown("""<div class="section-header"><span class="section-icon">⚙️</span><h3>Analysis Configuration</h3></div>""",
            unsafe_allow_html=True)

ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 2, 2])

with ctrl_col1:
    selected_date = st.date_input(
        "📅 Select Date",
        value=datetime.date.today() - datetime.timedelta(days=3),
        max_value=datetime.date.today(),
        min_value=datetime.date(2018, 5, 1),
        help="Sentinel-5P TROPOMI data available from May 2018.",
    )

with ctrl_col2:
    polygon_source = st.selectbox(
        "📐 Polygon Source",
        ["Draw on map", "Upload GeoJSON", "Upload KML/SHP → GeoJSON"],
        help="Choose how to define your area of interest.",
    )

with ctrl_col3:
    show_trend = st.checkbox("📈 Show 7-day trend", value=False)
    show_info  = st.checkbox("ℹ️ Show info drawer", value=False)

# ── POLYGON INPUT ─────────────────────────────────────────────────────────────
active_polygon = None

if polygon_source == "Upload GeoJSON":
    uploaded = st.file_uploader(
        "Upload GeoJSON file",
        type=["geojson", "json"],
        help="Upload a GeoJSON polygon/feature/featurecollection.",
    )
    if uploaded:
        try:
            raw = json.loads(uploaded.read())
            geom = polygon_from_geojson(raw)
            if geom:
                active_polygon = geom
                st.session_state.polygon_geojson = json.dumps(geom)
                st.markdown("""<div class="banner banner-success">✅ GeoJSON polygon loaded successfully.</div>""",
                            unsafe_allow_html=True)
            else:
                st.markdown("""<div class="banner banner-err">❌ Could not extract polygon from uploaded file.</div>""",
                            unsafe_allow_html=True)
        except Exception as e:
            st.markdown(f"""<div class="banner banner-err">❌ Invalid GeoJSON: {e}</div>""", unsafe_allow_html=True)

elif polygon_source == "Upload KML/SHP → GeoJSON":
    st.markdown("""<div class="banner banner-info">ℹ️ Convert KML/SHP to GeoJSON at <a href="https://mygeodata.cloud/converter/" target="_blank">mygeodata.cloud</a> then upload here as GeoJSON.</div>""",
                unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload converted GeoJSON", type=["geojson", "json"])
    if uploaded:
        try:
            raw = json.loads(uploaded.read())
            geom = polygon_from_geojson(raw)
            if geom:
                active_polygon = geom
                st.session_state.polygon_geojson = json.dumps(geom)
        except Exception as e:
            st.error(f"Invalid file: {e}")

# ── MAP ───────────────────────────────────────────────────────────────────────
st.markdown("""<div class="section-header"><span class="section-icon">🗺️</span><h3>Interactive Map <span class="zoom-badge">⚠ Max zoom ~200 m (Sentinel-5P resolution)</span></h3></div>""",
            unsafe_allow_html=True)

# Build map
if GEEMAP_AVAILABLE and ST_FOLIUM_AVAILABLE:
    m = geemap.Map(
        center=[20, 0],
        zoom=3,
        max_zoom=15,  # ~200–250 m at equator
        draw_export=True,
        search_control=False,
        measure_control=True,
        fullscreen_control=True,
    )
    m.add_basemap(basemap)

    # Add drawn polygon from session if available
    if st.session_state.drawn_polygon:
        active_polygon = st.session_state.drawn_polygon
        try:
            fg = folium.FeatureGroup(name="AOI Polygon")
            folium.GeoJson(
                active_polygon,
                style_function=lambda _: {
                    "fillColor": "#60A5FA" if DARK else "#1E88E5",
                    "color": "#60A5FA" if DARK else "#1E88E5",
                    "weight": 2,
                    "fillOpacity": 0.15,
                },
                tooltip="Your AOI",
            ).add_to(fg)
            fg.add_to(m)
            m.fit_bounds(folium.GeoJson(active_polygon).get_bounds())
        except Exception:
            pass

    # Add NO2 tile if polygon ready
    if active_polygon and GEE_OK:
        with st.spinner("Fetching NO₂ tile from GEE…"):
            tile_url, tile_err = get_tile_url(
                str(selected_date),
                json.dumps(active_polygon),
                DARK,
            )
        if tile_url:
            folium.TileLayer(
                tiles=tile_url,
                attr="Google Earth Engine · Sentinel-5P TROPOMI",
                name="NO₂ Column Density",
                overlay=True,
                control=True,
                opacity=0.8,
            ).add_to(m)
            folium.LayerControl().add_to(m)
        elif tile_err:
            st.markdown(f"""<div class="banner banner-err">❌ Tile error: {tile_err}</div>""", unsafe_allow_html=True)

    m.to_streamlit(height=520, returned_objects=["all_drawings"])

    # Capture drawn polygon
    # (geemap returns drawn features; user should click "Draw" toolbar on map)
    st.markdown("""<div class="banner banner-info">ℹ️ Draw a polygon using the toolbar (✏️ pentagon icon) on the map, then click <b>Load Drawn Polygon</b> below.</div>""",
                unsafe_allow_html=True)

    drawn_col1, drawn_col2 = st.columns([2, 3])
    with drawn_col1:
        geojson_text = st.text_area(
            "Paste drawn GeoJSON geometry here (from map export or manual)",
            height=80,
            placeholder='{"type":"Polygon","coordinates":[[[lon,lat],...]]}',
            help="Copy from the map's export button or paste manually.",
        )
    with drawn_col2:
        st.write("")
        if st.button("📌 Load Polygon from Text", use_container_width=True):
            if geojson_text.strip():
                try:
                    geom = json.loads(geojson_text)
                    if "geometry" in geom:
                        geom = geom["geometry"]
                    st.session_state.drawn_polygon = geom
                    st.session_state.polygon_geojson = json.dumps(geom)
                    active_polygon = geom
                    st.rerun()
                except Exception as e:
                    st.markdown(f"""<div class="banner banner-err">❌ Invalid GeoJSON: {e}</div>""", unsafe_allow_html=True)

else:
    # Fallback: simple Folium map if geemap unavailable
    import folium
    from streamlit_folium import st_folium as _stf

    m = folium.Map(location=[20, 0], zoom_start=3, max_zoom=15)
    if basemap == "CartoDB.DarkMatter":
        folium.TileLayer("CartoDB dark_matter").add_to(m)
    else:
        folium.TileLayer("CartoDB positron").add_to(m)

    # Draw control
    draw = Draw(
        draw_options={
            "polyline": False, "rectangle": True, "polygon": True,
            "circle": False, "circlemarker": False, "marker": False,
        },
        edit_options={"edit": True, "remove": True},
    )
    draw.add_to(m)

    result = _stf(m, height=520, returned_objects=["all_drawings"])

    if result and result.get("all_drawings"):
        drawings = result["all_drawings"]
        if drawings:
            geom = drawings[-1].get("geometry")
            if geom:
                st.session_state.drawn_polygon = geom
                st.session_state.polygon_geojson = json.dumps(geom)
                active_polygon = geom

    if active_polygon:
        st.markdown("""<div class="banner banner-success">✅ Polygon captured from map drawing.</div>""",
                    unsafe_allow_html=True)

# Set active polygon from session if not yet set
if not active_polygon and st.session_state.polygon_geojson:
    try:
        active_polygon = json.loads(st.session_state.polygon_geojson)
    except Exception:
        pass

# ── LEGEND ────────────────────────────────────────────────────────────────────
bar_class = "legend-bar-dark" if DARK else "legend-bar-light"
st.markdown(f"""
<div class="legend-container" style="margin-top:0.75rem">
    <div class="legend-title">NO₂ Column Density Legend · mol/m² × 10⁻⁵</div>
    <div class="legend-bar {bar_class}"></div>
    <div class="legend-labels">
        <span>0</span><span>0.5</span><span>1.0</span><span>1.5</span>
        <span>2.0</span><span>2.5</span><span>3.0+</span>
    </div>
    <div style="font-size:0.68rem;color:var(--muted);margin-top:0.35rem;font-family:'IBM Plex Mono',monospace">
        Palette: {"Inferno (dark)" if DARK else "YlOrRd (light)"} &nbsp;·&nbsp; QA ≥ {"0.75 (OFFL)" if True else "0.5 (NRTI)"}
    </div>
</div>
""", unsafe_allow_html=True)

# ── STATISTICS ────────────────────────────────────────────────────────────────
st.markdown("""<div class="section-header"><span class="section-icon">📊</span><h3>Statistics Summary</h3></div>""",
            unsafe_allow_html=True)

if not active_polygon:
    st.markdown("""<div class="banner banner-warn">⚠️ No polygon selected. Upload a GeoJSON or draw a polygon on the map to compute statistics.</div>""",
                unsafe_allow_html=True)
elif not GEE_OK:
    st.markdown("""<div class="banner banner-err">❌ GEE not connected. Statistics unavailable.</div>""",
                unsafe_allow_html=True)
else:
    with st.spinner("Computing statistics from GEE…"):
        stats, stats_err = compute_stats(
            str(selected_date),
            json.dumps(active_polygon),
        )

    if stats_err:
        st.markdown(f"""<div class="banner banner-err">❌ Stats error: {stats_err}</div>""", unsafe_allow_html=True)
    elif stats:
        if stats["fallback"]:
            st.markdown(f"""
            <div class="banner banner-warn">⚠️ No data for <strong>{selected_date}</strong>. 
            Displaying imagery from <strong>{stats['date']}</strong> instead (closest within ±7 days).</div>
            """, unsafe_allow_html=True)

        def _mol(val):
            if val is None: return "N/A"
            return f"{val * 1e5:.3f}"

        st.markdown(f"""
        <div class="stat-grid">
            <div class="stat-card">
                <div class="stat-label">Imagery Date</div>
                <div class="stat-value stat-accent">{stats['date']}</div>
                <div class="stat-unit">{'⚠ fallback date' if stats['fallback'] else '✓ exact match'}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Mean NO₂</div>
                <div class="stat-value">{_mol(stats['mean'])}</div>
                <div class="stat-unit">mol/m² × 10⁻⁵</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Min NO₂</div>
                <div class="stat-value">{_mol(stats['min'])}</div>
                <div class="stat-unit">mol/m² × 10⁻⁵</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Max NO₂</div>
                <div class="stat-value">{_mol(stats['max'])}</div>
                <div class="stat-unit">mol/m² × 10⁻⁵</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Valid Pixels</div>
                <div class="stat-value">{stats['count'] or 'N/A'}</div>
                <div class="stat-unit">after QA mask</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Coverage</div>
                <div class="stat-value">{stats['coverage']}%</div>
                <div class="stat-unit">of AOI</div>
            </div>
        </div>
        <div class="tooltip">Dataset: {stats['dataset']} &nbsp;·&nbsp; Band: {stats['band']}</div>
        """, unsafe_allow_html=True)

        # ── 7-day trend ───────────────────────────────────────────────────────
        if show_trend:
            st.markdown("""<div class="section-header" style="margin-top:1.25rem"><span class="section-icon">📈</span><h3>7-Day NO₂ Trend</h3></div>""",
                        unsafe_allow_html=True)
            with st.spinner("Fetching 7-day trend…"):
                trend = fetch_trend(json.dumps(active_polygon), str(selected_date))

            if trend:
                try:
                    import pandas as pd
                    df = pd.DataFrame(trend)
                    df["mean_scaled"] = df["mean"].apply(lambda v: (v * 1e5) if v else None)
                    df.set_index("date", inplace=True)
                    st.line_chart(df["mean_scaled"], use_container_width=True, height=180)
                    st.caption("Mean NO₂ (mol/m² × 10⁻⁵) — past 7 days within AOI")
                except ImportError:
                    st.write(trend)
            else:
                st.markdown("""<div class="banner banner-warn">⚠️ Could not fetch trend data.</div>""", unsafe_allow_html=True)

# ── INFO DRAWER ───────────────────────────────────────────────────────────────
if show_info:
    st.markdown("""<div class="section-header"><span class="section-icon">ℹ️</span><h3>About This Tool</h3></div>""",
                unsafe_allow_html=True)

    st.markdown("""
    <div class="info-section">
        <h4>What is NO₂?</h4>
        <p>Nitrogen dioxide (NO₂) is a reddish-brown gas and a key air pollutant produced primarily by combustion in vehicle engines, 
        power plants, and industrial facilities. It is a precursor to tropospheric ozone and secondary particulate matter, 
        contributing to smog and acid rain.</p>
    </div>

    <div class="info-section">
        <h4>Health Impacts</h4>
        <p>Short-term exposure causes irritation of airways, aggravated asthma, and increased susceptibility to respiratory infections. 
        Long-term exposure is linked to development of asthma and increased risk of cardiovascular disease. 
        Vulnerable populations include children, elderly, and those with pre-existing respiratory conditions.</p>
    </div>

    <div class="info-section">
        <h4>Data Source</h4>
        <p><strong>Primary:</strong> <code>COPERNICUS/S5P/OFFL/L3_NO2</code> (Offline, high accuracy, QA ≥ 0.75)</p>
        <p><strong>Fallback:</strong> <code>COPERNICUS/S5P/NRTI/L3_NO2</code> (Near-real-time, QA ≥ 0.5)</p>
        <p>Band: <code>tropospheric_NO2_column_number_density</code> (or <code>NO2_column_number_density</code> for NRTI)</p>
        <p>Sentinel-5P TROPOMI instrument provides daily global coverage at ~3.5×5.5 km nadir resolution.</p>
    </div>

    <div class="info-section">
        <h4>QA Mask Explanation</h4>
        <p>The <code>qa_value</code> band ranges 0–1. Values ≥ 0.75 (OFFL) or ≥ 0.5 (NRTI) indicate high confidence, 
        cloud-free retrievals. Pixels below these thresholds are masked and excluded from statistics and visualization.</p>
    </div>

    <div class="info-section">
        <h4>Zoom Restriction</h4>
        <p>Maximum zoom is limited to level 15 (~200–250 m/pixel). Sentinel-5P pixel resolution is ~3.5–7 km; 
        zooming below this would create a false impression of fine-grained spatial detail. Use the data for regional-scale analysis only.</p>
    </div>

    <div class="info-section">
        <h4>⚠️ Disclaimer</h4>
        <p>This is a <strong>proof-of-concept (POC)</strong> tool for exploratory data visualization only. 
        It is <strong>not</strong> a regulatory air quality index (AQI) tool. 
        Values represent tropospheric column density (mol/m²), not ground-level concentrations. 
        Do not use for health or regulatory decisions.</p>
    </div>
    """, unsafe_allow_html=True)

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
    <span>🛰️ Built with <strong>Google Earth Engine</strong> · <strong>Python</strong> · <strong>Streamlit</strong></span>
    <span>Dataset: Sentinel-5P TROPOMI OFFL/NRTI L3 NO₂</span>
    <span>🔒 No user data stored · POC only</span>
</div>
""", unsafe_allow_html=True)