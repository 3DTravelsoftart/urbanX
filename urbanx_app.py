import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import pandas as pd
import pydeck as pdk

st.set_page_config(layout="wide")

st.title("UrbanX ENTERPRISE – Analiză urbanistică AI")

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4 = st.tabs([
    "📍 Adresă",
    "🏗️ Clădiri",
    "📊 Indicatori",
    "🏙️ 3D"
])

lat, lon = 47.7486, 26.669
buildings = []

# =========================
# TAB 1 – ADRESĂ
# =========================
with tab1:
    adresa = st.text_input("Adresă")

    if adresa:
        try:
            url = f"https://nominatim.openstreetmap.org/search?format=json&q={adresa}"
            headers = {"User-Agent": "urbanx-app"}

            r = requests.get(url, headers=headers)
            data = r.json()

            if len(data) > 0:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                st.success("Adresă găsită")

        except:
            st.error("Eroare adresă")

    m = folium.Map(location=[lat, lon], zoom_start=17)
    folium.Marker([lat, lon]).add_to(m)
    st_folium(m, width=1000, height=500)

# =========================
# EXTRAGERE CLĂDIRI
# =========================
def load_buildings(lat, lon):
    buildings = []

    query = f"""
    [out:json];
    (
      way["building"](around:150,{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    r = requests.post("https://overpass-api.de/api/interpreter", data=query)
    data = r.json()

    nodes = {}
    for el in data["elements"]:
        if el["type"] == "node":
            nodes[el["id"]] = (el["lat"], el["lon"])

    for el in data["elements"]:
        if el["type"] == "way":
            coords = []

            for n in el["nodes"]:
                if n in nodes:
                    coords.append(nodes[n])

            if len(coords) > 2:
                height = 10
                levels = "?"

                if "tags" in el:
                    if "building:levels" in el["tags"]:
                        try:
                            levels = int(el["tags"]["building:levels"])
                            height = levels * 3
                        except:
                            pass

                buildings.append({
                    "coords": coords,
                    "height": height,
                    "levels": levels
                })

    return buildings


buildings = load_buildings(lat, lon)

# =========================
# TAB 2 – HARTĂ CLĂDIRI
# =========================
with tab2:
    st.header("Clădiri din jur")

    st.success(f"{len(buildings)} clădiri detectate")

    m2 = folium.Map(location=[lat, lon], zoom_start=17)

    for b in buildings:
        folium.Polygon(
            locations=b["coords"],
            color="blue",
            fill=True,
            fill_opacity=0.3,
            tooltip=f"Inaltime: {b['height']} m | Etaje: {b['levels']}"
        ).add_to(m2)

    st_folium(m2, width=1000, height=500)

# =========================
# TAB 3 – INDICATORI + VOLUM
# =========================
with tab3:
    st.header("Indicatori urbanistici")

    pot = st.slider("POT", 0.1, 1.0, 0.4)
    cut = st.slider("CUT", 0.1, 5.0, 1.2)

    suprafata = 1000  # mp default

    amprenta = suprafata * pot
    suprafata_desfasurata = suprafata * cut

    st.metric("Amprentă propusă", f"{int(amprenta)} mp")
    st.metric("Suprafață desfășurată", f"{int(suprafata_desfasurata)} mp")

    st.info("Volumul propus = ROȘU în 3D")

# =========================
# TAB 4 – 3D CLAR
# =========================
with tab4:
    st.header("3D – existent vs propus")

    layers = []

    # EXISTENTE
    existing = []
    for b in buildings:
        poly = [[c[1], c[0]] for c in b["coords"]]

        existing.append({
            "polygon": poly,
            "height": b["height"]
        })

    if existing:
        df_existing = pd.DataFrame(existing)

        layers.append(
            pdk.Layer(
                "PolygonLayer",
                df_existing,
                get_polygon="polygon",
                get_elevation="height",
                extruded=True,
                get_fill_color=[150, 150, 150, 180],
            )
        )

    # PROPUS (simplificat ca footprint central)
    propus = [{
        "polygon": [
            [lon-0.0002, lat-0.0002],
            [lon+0.0002, lat-0.0002],
            [lon+0.0002, lat+0.0002],
            [lon-0.0002, lat+0.0002],
        ],
        "height": 20
    }]

    df_prop = pd.DataFrame(propus)

    layers.append(
        pdk.Layer(
            "PolygonLayer",
            df_prop,
            get_polygon="polygon",
            get_elevation="height",
            extruded=True,
            get_fill_color=[255, 0, 0, 200],
        )
    )

    view_state = pdk.ViewState(
        latitude=lat,
        longitude=lon,
        zoom=17,
        pitch=45,
    )

    st.pydeck_chart(pdk.Deck(
        layers=layers,
        initial_view_state=view_state
    ))
