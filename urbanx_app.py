import streamlit as st
import folium
from streamlit_folium import st_folium
from shapely.geometry import Polygon
import requests
import pydeck as pdk

st.set_page_config(layout="wide")
st.title("UrbanX ENTERPRISE – Cadastru + AI")

headers = {"User-Agent": "UrbanX-App"}

# =========================
# INPUT
# =========================
st.header("1. Adresă")

adresa = st.text_input("Adresă")

teren = None
centru = None

# =========================
# GEOCODARE
# =========================
if adresa:
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={adresa}"

    try:
        r = requests.get(url, headers=headers)

        if r.status_code == 200:
            data = r.json()
        else:
            data = []

        if data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            centru = (lat, lon)

            st.success("Locație găsită")

    except:
        st.error("Eroare geocodare")

# =========================
# HARTĂ
# =========================
m = folium.Map(location=[47.75, 26.66], zoom_start=16)
map_data = st_folium(m, width=900, height=500)

if not centru and map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]
    centru = (lat, lon)

# =========================
# PARCELĂ REALISTĂ (OSM)
# =========================
if centru:

    lat, lon = centru

    st.header("2. Parcelă detectată")

    try:
        overpass_url = "http://overpass-api.de/api/interpreter"

        query = f"""
        [out:json];
        (
          way["building"](around:50,{lat},{lon});
        );
        out geom;
        """

        r = requests.post(overpass_url, data=query)

        if r.status_code == 200:
            data = r.json()

            if data["elements"]:
                el = data["elements"][0]
                coords = [(p["lon"], p["lat"]) for p in el["geometry"]]

                teren = Polygon(coords)
                st.success("Parcelă realistă detectată (din footprint clădire)")

    except:
        teren = None

# fallback
if not teren and centru:
    lat, lon = centru
    size = 0.00015
    teren = Polygon([
        (lon-size, lat-size),
        (lon+size, lat-size),
        (lon+size, lat+size),
        (lon-size, lat+size)
    ])
    st.warning("Fallback parcelă (nu s-a găsit cadastru)")

# =========================
# ANALIZĂ
# =========================
if teren:

    if not teren.is_valid:
        teren = teren.buffer(0)

    st.header("3. Suprafață")

    suprafata = teren.area * 10000000
    st.write(round(suprafata), "mp")

    centru_geom = teren.centroid

    # =========================
    # STRADĂ
    # =========================
    st.header("4. Stradă")

    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={centru_geom.y}&lon={centru_geom.x}"
        r = requests.get(url, headers=headers)

        if r.status_code == 200:
            data = r.json()
            strada = data.get("address", {}).get("road", "necunoscută")
        else:
            strada = "necunoscută"

    except:
        strada = "necunoscută"

    st.write(strada)

    # =========================
    # REGULI
    # =========================
    st.header("5. Indicatori urbanistici")

    POT = 0.4
    CUT = 1.2

    # =========================
    # RETRAGERI
    # =========================
    st.header("6. Retrageri")

    retragere = st.slider("Retragere", 1, 10, 3)

    max_retragere = min(
        teren.bounds[2] - teren.bounds[0],
        teren.bounds[3] - teren.bounds[1]
    ) / 4

    if retragere > max_retragere:
        retragere = max_retragere

    teren_retras = teren.buffer(-retragere)

    if teren_retras.is_empty:
        st.error("Retrageri prea mari")
        st.stop()

    # =========================
    # VOLUM AI
    # =========================
    st.header("7. Volum propus (AI)")

    niveluri = max(1, int(CUT / POT))
    height = niveluri * 3

    coords = list(teren_retras.exterior.coords)

    polygon = [{
        "polygon": [[c[0], c[1]] for c in coords],
        "height": height
    }]

    deck = pdk.Deck(
        map_style="mapbox://styles/mapbox/light-v9",
        initial_view_state=pdk.ViewState(
            latitude=centru_geom.y,
            longitude=centru_geom.x,
            zoom=17,
            pitch=45,
        ),
        layers=[
            pdk.Layer(
                "PolygonLayer",
                polygon,
                get_polygon="polygon",
                get_elevation="height",
                extruded=True,
            )
        ],
    )

    st.pydeck_chart(deck)
