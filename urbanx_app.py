import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import pydeck as pdk
from shapely.geometry import Polygon
from shapely.ops import unary_union

st.set_page_config(layout="wide")

st.title("🏙️ UrbanX PRO – Analiză urbanistică AI")

# =========================
# SESSION
# =========================
if "points" not in st.session_state:
    st.session_state.points = []

# =========================
# GEOCODARE
# =========================
def geocode(address):
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={address}"
        r = requests.get(url, headers={"User-Agent": "urbanx"})
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except:
        return None, None
    return None, None

# =========================
# LOAD BUILDINGS (ROBUST)
# =========================
def load_buildings(lat, lon):
    try:
        query = f"""
        [out:json];
        way["building"](around:150,{lat},{lon});
        out geom;
        """
        r = requests.get("https://overpass-api.de/api/interpreter", params={"data": query})

        if r.status_code != 200:
            return []

        try:
            data = r.json()
        except:
            return []

        buildings = []

        for el in data.get("elements", []):
            if "geometry" in el:
                coords = [(p["lon"], p["lat"]) for p in el["geometry"]]

                levels = el.get("tags", {}).get("building:levels")
                if levels:
                    height = float(levels) * 3
                else:
                    height = 10

                buildings.append({
                    "polygon": coords,
                    "height": height
                })

        return buildings

    except:
        return []

# =========================
# AI VOLUME (NO OVERLAP)
# =========================
def generate_ai_volume(parcel_coords, buildings):

    if not parcel_coords or len(parcel_coords) < 3:
        return None

    parcel = Polygon(parcel_coords)

    building_polys = []
    heights = []

    for b in buildings:
        try:
            poly = Polygon(b["polygon"])
            building_polys.append(poly.buffer(0.00003))
            heights.append(b["height"])
        except:
            continue

    if building_polys:
        occupied = unary_union(building_polys)
        free_area = parcel.difference(occupied)
    else:
        free_area = parcel

    if free_area.is_empty:
        free_area = parcel.buffer(-0.00005)

    if free_area.geom_type == "MultiPolygon":
        free_area = max(free_area.geoms, key=lambda g: g.area)

    coords = list(free_area.exterior.coords)

    if heights:
        avg_h = sum(heights) / len(heights)
        height = min(avg_h * 1.2, 45)
    else:
        height = 18

    return {
        "polygon": coords,
        "height": height
    }

# =========================
# INPUT
# =========================
address = st.text_input("📍 Introdu adresă")

lat, lon = 47.7486, 26.669

if address:
    lat2, lon2 = geocode(address)
    if lat2:
        lat, lon = lat2, lon2

# =========================
# TABS
# =========================
tabs = st.tabs(["🗺️ Hartă", "🏢 Clădiri", "📊 Indicatori", "🏗️ 3D"])

# =========================
# TAB 1 – HARTA
# =========================
with tabs[0]:

    st.markdown("### Selectează parcela (click pe hartă)")

    m = folium.Map(location=[lat, lon], zoom_start=17)

    # click handler
    map_data = st_folium(m, height=500)

    if map_data and map_data.get("last_clicked"):
        pt = map_data["last_clicked"]
        st.session_state.points.append((pt["lng"], pt["lat"]))

    # desen puncte
    for p in st.session_state.points:
        folium.CircleMarker(location=[p[1], p[0]], radius=5, color="red").add_to(m)

    # redesen
    st_folium(m, height=500)

    if len(st.session_state.points) >= 3:
        st.success("Parcelă definită")

# =========================
# TAB 2 – CLADIRI
# =========================
with tabs[1]:

    buildings = load_buildings(lat, lon)

    st.success(f"{len(buildings)} clădiri detectate")

    if buildings:
        st.map({
            "lat": [p[1] for b in buildings for p in b["polygon"]],
            "lon": [p[0] for b in buildings for p in b["polygon"]],
        })

# =========================
# TAB 3 – INDICATORI
# =========================
with tabs[2]:

    if len(st.session_state.points) >= 3:

        parcel = Polygon(st.session_state.points)
        area = parcel.area * 10000000000

        pot = 0.4
        cut = 1.2

        footprint = area * pot
        gfa = area * cut

        st.metric("Suprafață teren", f"{area:.0f} mp")
        st.metric("Amprentă max", f"{footprint:.0f} mp")
        st.metric("Suprafață desfășurată", f"{gfa:.0f} mp")

# =========================
# TAB 4 – 3D
# =========================
with tabs[3]:

    buildings = load_buildings(lat, lon)
    ai_vol = generate_ai_volume(st.session_state.points, buildings)

    if not ai_vol:
        st.warning("Selectează parcela")
    else:

        st.markdown("""
### Legendă:
🔵 Volum propus  
⚪ Clădiri existente  
""")

        data = []

        # EXISTENTE
        for b in buildings:
            data.append({
                "polygon": b["polygon"],
                "height": b["height"],
                "color": [200,200,200]
            })

        # PROPUS
        data.append({
            "polygon": ai_vol["polygon"],
            "height": ai_vol["height"],
            "color": [0,120,255]
        })

        layer = pdk.Layer(
            "PolygonLayer",
            data,
            get_polygon="polygon",
            get_elevation="height",
            get_fill_color="color",
            extruded=True
        )

        view = pdk.ViewState(
            latitude=lat,
            longitude=lon,
            zoom=17,
            pitch=65,
            bearing=30
        )

        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view,
            map_style="mapbox://styles/mapbox/dark-v10"
        ))
