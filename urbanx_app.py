import streamlit as st
import folium
from streamlit_folium import st_folium
from shapely.geometry import Polygon, Point
import requests
import pydeck as pdk

st.set_page_config(layout="wide")
st.title("UrbanX ENTERPRISE – Analiză urbanistică AI")

# =========================
# INPUT ADRESĂ
# =========================
st.header("1. Introdu adresă / locație")

adresa = st.text_input("Adresă (ex: Strada Grivita Botosani)")

teren = None

if adresa:
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={adresa}"
    data = requests.get(url).json()

    if data:
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])

        # teren automat (buffer)
        size = 0.00015
        teren = Polygon([
            (lon-size, lat-size),
            (lon+size, lat-size),
            (lon+size, lat+size),
            (lon-size, lat+size)
        ])

        st.success("Teren identificat automat")

# =========================
# HARTĂ
# =========================
m = folium.Map(location=[47.75, 26.66], zoom_start=16)

map_data = st_folium(m, width=900, height=500)

# fallback click
if not teren and map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

    size = 0.0001
    teren = Polygon([
        (lon-size, lat-size),
        (lon+size, lat-size),
        (lon+size, lat+size),
        (lon-size, lat+size)
    ])

# =========================
# ANALIZĂ
# =========================
if teren:

    st.header("2. Teren")

    suprafata = teren.area * 10000000
    st.write(f"Suprafață: {round(suprafata)} mp")

    centru = teren.centroid

    # =========================
    # STRADĂ
    # =========================
    st.header("3. Stradă")

    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={centru.y}&lon={centru.x}"
        r = requests.get(url).json()
        strada = r.get("address", {}).get("road", "necunoscută")
    except:
        strada = "necunoscută"

    st.write(strada)

    # =========================
    # CLĂDIRI
    # =========================
    st.header("4. Clădiri din jur")

    try:
        overpass_url = "http://overpass-api.de/api/interpreter"
        query = f"""
        [out:json];
        (
          way["building"](around:100,{centru.y},{centru.x});
        );
        out body;
        """

        data = requests.post(overpass_url, data=query).json()
        nr_cladiri = len(data["elements"])
        st.success(f"{nr_cladiri} clădiri identificate")

    except:
        nr_cladiri = 10
        st.warning("Fallback clădiri")

    # =========================
    # REGULI
    # =========================
    st.header("5. Reguli urbanistice")

    POT = 0.4
    CUT = 1.2

    st.write("POT:", POT)
    st.write("CUT:", CUT)

    # =========================
    # RETRAGERI
    # =========================
    st.header("6. Retrageri")

    retragere = st.slider("Retragere (m)", 1, 10, 3)

    max_retragere = min(
        teren.bounds[2] - teren.bounds[0],
        teren.bounds[3] - teren.bounds[1]
    ) / 4

    if retragere > max_retragere:
        st.warning("Retragere ajustată automat")
        retragere = max_retragere

    teren_retras = teren.buffer(-retragere)

    # =========================
    # CALCUL
    # =========================
    amprenta = teren_retras.area * 10000000 * POT
    suprafata_desfasurata = amprenta * (CUT / POT)

    st.header("7. Indicatori")

    st.write("Amprentă:", round(amprenta))
    st.write("Suprafață desfășurată:", round(suprafata_desfasurata))

    # =========================
    # 3D PROPUS
    # =========================
    st.header("8. Volum 3D PROPUS")

    niveluri = int(CUT / POT)

    coords = list(teren_retras.exterior.coords)

    polygon = [{
        "polygon": [[c[0], c[1]] for c in coords],
        "height": niveluri * 3
    }]

    deck = pdk.Deck(
        map_style="mapbox://styles/mapbox/light-v9",
        initial_view_state=pdk.ViewState(
            latitude=centru.y,
            longitude=centru.x,
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
                wireframe=True,
            )
        ],
    )

    st.pydeck_chart(deck)
