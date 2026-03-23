import streamlit as st
import folium
from streamlit_folium import st_folium
from shapely.geometry import Polygon, Point
import requests
import pydeck as pdk

st.set_page_config(layout="wide")

st.title("UrbanX PRO – GIS + AI + Auto Parcel")

# =========================
# 1. SEARCH (ADRESA / COORD)
# =========================

st.header("🔎 Caută teren")

adresa = st.text_input("Adresă")
lat = st.text_input("Latitudine")
lon = st.text_input("Longitudine")

center = [47.75, 26.66]

if adresa:
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": adresa, "format": "json"}
    r = requests.get(url, params=params)

    if r.status_code == 200 and len(r.json()) > 0:
        res = r.json()[0]
        center = [float(res["lat"]), float(res["lon"])]
        st.success(res["display_name"])

if lat and lon:
    try:
        center = [float(lat), float(lon)]
    except:
        st.error("Coordonate invalide")

# =========================
# 2. HARTĂ + CLICK
# =========================

st.header("🗺️ Selectare automată teren")

m = folium.Map(location=center, zoom_start=18)

draw = folium.plugins.Draw(export=True)
draw.add_to(m)

map_data = st_folium(m, width=900, height=500)

teren = None

# =========================
# 3. AUTO PARCEL (PRO)
# =========================

if map_data and map_data.get("last_clicked"):
    lat_click = map_data["last_clicked"]["lat"]
    lon_click = map_data["last_clicked"]["lng"]

    st.success(f"Click detectat: {lat_click}, {lon_click}")

    # PARCELĂ SIMULATĂ (PRO)
    size = 0.00015  # ~15-20m

    coords = [
        (lon_click - size, lat_click - size),
        (lon_click + size, lat_click - size),
        (lon_click + size, lat_click + size),
        (lon_click - size, lat_click + size),
    ]

    teren = Polygon(coords)

# fallback desen manual
if map_data and map_data.get("all_drawings"):
    coords = map_data["all_drawings"][-1]["geometry"]["coordinates"][0]
    coords_corrected = [(c[0], c[1]) for c in coords]
    teren = Polygon(coords_corrected)

# validare
if teren and not teren.is_valid:
    teren = teren.buffer(0)

# =========================
# 4. SUPRAFAȚĂ
# =========================

if teren:
    suprafata = teren.area * 100000
    st.success(f"Teren: {int(suprafata)} mp")

# =========================
# 5. CLĂDIRI
# =========================

cladiri = []

if teren:
    st.header("🏢 Clădiri")

    bbox = f"{teren.bounds[1]},{teren.bounds[0]},{teren.bounds[3]},{teren.bounds[2]}"

    query = f"""
    [out:json];
    (
      way["building"]({bbox});
    );
    out body geom;
    """

    r = requests.get("https://overpass-api.de/api/interpreter", params={"data": query})

    if r.status_code == 200:
        data = r.json()

        for el in data["elements"]:
            if el["type"] == "way" and "geometry" in el:
                cladiri.append(el)

        st.success(f"{len(cladiri)} clădiri")
    else:
        st.warning("Fără date clădiri")

# =========================
# 6. STRADĂ
# =========================

st.header("🛣️ Stradă")

strada = "necunoscută"

if teren:
    query = f"""
    [out:json];
    way["highway"]({bbox});
    out tags;
    """

    r = requests.get("https://overpass-api.de/api/interpreter", params={"data": query})

    if r.status_code == 200:
        for el in r.json()["elements"]:
            if "tags" in el and "name" in el["tags"]:
                strada = el["tags"]["name"]
                break

st.write(strada)

# =========================
# 7. PUG AI
# =========================

st.header("📐 Reguli urbanistice")

if "Nationala" in strada:
    POT, CUT = 0.6, 2.5
elif "Grivita" in strada:
    POT, CUT = 0.5, 2.0
else:
    POT, CUT = 0.4, 1.2

st.write(f"POT: {POT}")
st.write(f"CUT: {CUT}")

# =========================
# 8. RETRAGERI
# =========================

st.header("📏 Retrageri")

retragere = st.slider("Retragere", 1, 10, 5)

if teren:
    max_r = min(
        teren.bounds[2] - teren.bounds[0],
        teren.bounds[3] - teren.bounds[1]
    ) / 4

    if retragere > max_r:
        retragere = max_r
        st.warning("Retragere ajustată")

    teren_retras = teren.buffer(-retragere)

# =========================
# 9. INDICATORI
# =========================

st.header("📊 Indicatori")

if teren:
    amprenta = suprafata * POT
    desfasurata = suprafata * CUT

    st.write(f"Amprentă: {int(amprenta)} mp")
    st.write(f"Desfășurată: {int(desfasurata)} mp")

# =========================
# 10. 3D
# =========================

st.header("🌆 3D")

if cladiri:
    layers = []

    for el in cladiri:
        try:
            coords = [(p["lon"], p["lat"]) for p in el["geometry"]]
            height = float(el.get("tags", {}).get("height", 12))

            layers.append({
                "polygon": coords,
                "height": height
            })
        except:
            pass

    layer = pdk.Layer(
        "PolygonLayer",
        layers,
        get_polygon="polygon",
        get_elevation="height",
        extruded=True,
    )

    view = pdk.ViewState(
        latitude=center[0],
        longitude=center[1],
        zoom=16,
        pitch=45,
    )

    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view))
