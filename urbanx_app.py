import streamlit as st
import folium
from streamlit_folium import st_folium
from shapely.geometry import Polygon, Point
import requests
import pydeck as pdk

st.set_page_config(layout="wide")

st.title("UrbanX – Analiză urbanistică (GIS + 3D)")

# =============================
# HARTĂ + DESEN
# =============================
st.header("1. Desenează terenul")

m = folium.Map(location=[47.75, 26.66], zoom_start=16)

draw = folium.plugins.Draw(export=True)
draw.add_to(m)

map_data = st_folium(m, width=900, height=500)

teren = None

if map_data and map_data["all_drawings"]:
    coords = map_data["all_drawings"][-1]["geometry"]["coordinates"][0]
    coords = [(c[1], c[0]) for c in coords]

    teren = Polygon(coords)

# =============================
# SUPRAFAȚĂ
# =============================
if teren:
    st.success("Teren definit")

    suprafata = teren.area * 100000  # aproximare
    st.write(f"Suprafață: {int(suprafata)} mp")

    center = teren.centroid

# =============================
# OSM BUILDINGS
# =============================
    st.header("2. Clădiri din jur")

    query = f"""
    [out:json];
    way["building"](around:100,{center.x},{center.y});
    out geom;
    """

    url = "https://overpass-api.de/api/interpreter"
    data = None

    try:
        response = requests.get(url, params={'data': query})

        if response.status_code == 200:
            data = response.json()
        else:
            st.warning("Nu s-au putut încărca clădirile")

    except:
        st.warning("Eroare conexiune OSM")

    heights = []

    if data and "elements" in data:
        for el in data["elements"]:
            tags = el.get("tags", {})

            height = 10

            if "height" in tags:
                try:
                    height = float(tags["height"].replace(" m", ""))
                except:
                    height = 10

            elif "building:levels" in tags:
                try:
                    height = float(tags["building:levels"]) * 3
                except:
                    height = 10

            heights.append(height)

    if heights:
        regim_vecini = sum(heights) / len(heights)
    else:
        regim_vecini = 12

    st.write(f"Înălțime medie zonă: {int(regim_vecini)} m")

# =============================
# DETECTARE STRADĂ
# =============================
    st.header("3. Detectare stradă")

    road_query = f"""
    [out:json];
    way["highway"](around:50,{center.x},{center.y});
    out tags;
    """

    strada = "necunoscută"

    try:
        r = requests.get(url, params={'data': road_query})
        road_data = r.json()

        if road_data["elements"]:
            strada = road_data["elements"][0]["tags"].get("name", "stradă fără nume")

    except:
        pass

    st.write(f"Stradă detectată: **{strada}**")

# =============================
# RETRAGERI
# =============================
    st.header("4. Retrageri urbanistice")

    retragere = st.slider("Retragere (m)", 1, 10, 5)

    max_retragere = min(
        teren.bounds[2] - teren.bounds[0],
        teren.bounds[3] - teren.bounds[1]
    ) / 4

    if retragere > max_retragere:
        st.warning("Retragerea a fost ajustată automat")
        retragere = max_retragere

    teren_retras = teren.buffer(-retragere)

    if teren_retras.is_empty:
        st.error("Teren invalid după retragere")
    else:
        st.success("Retrageri aplicate")

# =============================
# INDICATORI
# =============================
        st.header("5. Indicatori urbanistici")

        POT = 0.4
        CUT = 1.2

        amprenta = suprafata * POT
        suprafata_desfasurata = suprafata * CUT

        st.write(f"POT: {POT}")
        st.write(f"CUT: {CUT}")
        st.write(f"Amprentă: {int(amprenta)} mp")
        st.write(f"Suprafață desfășurată: {int(suprafata_desfasurata)} mp")

# =============================
# 3D VIEW
# =============================
        st.header("6. Vizualizare 3D")

        layers = []

        # TEREN
        teren_layer = pdk.Layer(
            "PolygonLayer",
            data=[{"polygon": list(teren.exterior.coords)}],
            get_polygon="polygon",
            get_fill_color=[255, 0, 0, 80],
            extruded=True,
            get_elevation=1,
        )
        layers.append(teren_layer)

        # VOLUM PROPUS
        volum_layer = pdk.Layer(
            "PolygonLayer",
            data=[{"polygon": list(teren_retras.exterior.coords)}],
            get_polygon="polygon",
            get_fill_color=[0, 255, 0, 120],
            extruded=True,
            get_elevation=regim_vecini,
        )
        layers.append(volum_layer)

        # CLĂDIRI
        building_polygons = []

        if data and "elements" in data:
            for el in data["elements"]:
                if "geometry" in el:
                    coords_b = [(p["lat"], p["lon"]) for p in el["geometry"]]

                    height = 10
                    tags = el.get("tags", {})

                    if "height" in tags:
                        try:
                            height = float(tags["height"].replace(" m", ""))
                        except:
                            pass

                    elif "building:levels" in tags:
                        try:
                            height = float(tags["building:levels"]) * 3
                        except:
                            pass

                    building_polygons.append({
                        "polygon": coords_b,
                        "height": height
                    })

        buildings_layer = pdk.Layer(
            "PolygonLayer",
            data=building_polygons,
            get_polygon="polygon",
            get_fill_color=[200, 200, 200, 150],
            extruded=True,
            get_elevation="height",
        )
        layers.append(buildings_layer)

        view_state = pdk.ViewState(
            latitude=center.x,
            longitude=center.y,
            zoom=16,
            pitch=45,
        )

        deck = pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
        )

        st.pydeck_chart(deck)
