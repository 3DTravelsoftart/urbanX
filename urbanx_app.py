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

# =========================
# TAB 1 – ADRESA + HARTA
# =========================
with tab1:
    st.header("Introdu adresă")

    adresa = st.text_input("Adresă (ex: Strada Grivita Botosani)")

    lat, lon = 47.7486, 26.669

    if adresa:
        try:
            url = f"https://nominatim.openstreetmap.org/search?format=json&q={adresa}"
            headers = {"User-Agent": "urbanx-app"}

            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()

                if len(data) > 0:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    st.success("Adresă găsită")
                else:
                    st.warning("Adresă negăsită")

        except:
            st.error("Eroare geocoding")

    m = folium.Map(location=[lat, lon], zoom_start=17)
    folium.Marker([lat, lon]).add_to(m)

    st_folium(m, width=1000, height=500)

# =========================
# TAB 2 – CLADIRI REALE (OSM)
# =========================
with tab2:
    st.header("Clădiri din jur")

    buildings = []

    try:
        query = f"""
        [out:json];
        (
          way["building"](around:150,{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """

        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query
        )

        data = response.json()

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

                    if "tags" in el:
                        if "building:levels" in el["tags"]:
                            try:
                                height = int(el["tags"]["building:levels"]) * 3
                            except:
                                pass

                    buildings.append({
                        "coords": coords,
                        "height": height
                    })

        st.success(f"{len(buildings)} clădiri detectate")

    except:
        st.warning("Nu s-au putut încărca clădirile")

# =========================
# TAB 3 – INDICATORI
# =========================
with tab3:
    st.header("Indicatori urbanistici")

    pot = 0.4
    cut = 1.2

    st.metric("POT", pot)
    st.metric("CUT", cut)

# =========================
# TAB 4 – 3D REAL
# =========================
with tab4:
    st.header("Vizualizare 3D")

    if buildings:
        data_3d = []

        for b in buildings:
            poly = [[c[1], c[0]] for c in b["coords"]]

            data_3d.append({
                "polygon": poly,
                "height": b["height"]
            })

        df = pd.DataFrame(data_3d)

        layer = pdk.Layer(
            "PolygonLayer",
            df,
            get_polygon="polygon",
            get_elevation="height",
            elevation_scale=1,
            extruded=True,
            wireframe=True,
        )

        view_state = pdk.ViewState(
            latitude=lat,
            longitude=lon,
            zoom=17,
            pitch=45,
        )

        deck = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_style="mapbox://styles/mapbox/dark-v10",
        )

        st.pydeck_chart(deck)

    else:
        st.info("Nu există date 3D")
