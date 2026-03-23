import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from shapely.geometry import shape
import requests
import pydeck as pdk

st.set_page_config(layout="wide")

st.title("UrbanX – Analiză urbanistică (cu retrageri)")

# ========================
# HARTĂ
# ========================

st.header("1. Desenează terenul")

m = folium.Map(location=[47.7486, 26.669], zoom_start=16)

draw = Draw(
    draw_options={
        "polygon": True,
        "rectangle": True,
        "circle": False,
        "marker": False,
        "polyline": False,
    }
)
draw.add_to(m)

map_data = st_folium(m, height=500, width=1000)

# ========================
# PROCESARE
# ========================

if map_data and map_data.get("last_active_drawing"):

    geojson = map_data["last_active_drawing"]
    geom = shape(geojson["geometry"])

    coords = list(geom.exterior.coords)
    polygon = [[lon, lat] for lon, lat in coords]

    surface = int(geom.area * (111000 ** 2))

    centroid = geom.centroid
    lat = centroid.y
    lon = centroid.x

    st.success("Teren definit")
    st.write("Suprafață:", surface, "mp")

    # ========================
    # RETRAGERI AUTOMATE
    # ========================

    st.markdown("## 📏 Retrageri urbanistice")

    setback = st.slider("Retragere generală (m)", 2, 10, 5)

    setback_deg = setback / 111000

    buildable_geom = geom.buffer(-setback_deg)

    if buildable_geom.is_empty:
        st.error("Retragerile sunt prea mari pentru acest teren")
        st.stop()

    buildable_coords = list(buildable_geom.exterior.coords)
    buildable_polygon = [[lon, lat] for lon, lat in buildable_coords]

    buildable_surface = int(buildable_geom.area * (111000 ** 2))

    st.write("Suprafață construibilă:", buildable_surface, "mp")

    # ========================
    # CLĂDIRI OSM
    # ========================

    query = f"""
    [out:json];
    (
      way["building"](around:200,{lat},{lon});
    );
    out geom;
    """

    url = "https://overpass-api.de/api/interpreter"

    response = requests.get(url, params={'data': query}, timeout=10)

    if response.status_code != 200:
        st.error("Eroare OSM")
        st.stop()

    try:
        data = response.json()
    except:
        st.error("OSM indisponibil")
        st.stop()

    buildings = []

    for el in data["elements"]:
        if "geometry" in el:
            coords_b = [[p["lon"], p["lat"]] for p in el["geometry"]]

            tags = el.get("tags", {})

            if "height" in tags:
                try:
                    height = float(tags["height"].replace("m", "").strip())
                except:
                    height = 10
            elif "building:levels" in tags:
                height = float(tags["building:levels"]) * 3
            else:
                height = 10

            buildings.append({
                "polygon": coords_b,
                "height": height
            })

    # ========================
    # STUDIU URBANISTIC
    # ========================

    st.markdown("## 🧠 Studiu urbanistic")

    num_buildings = len(buildings)

    heights = [b["height"] for b in buildings]
    avg_height = sum(heights) / len(heights) if heights else 0
    avg_levels = int(avg_height / 3) if avg_height else 0

    if num_buildings > 120:
        density = "Ridicată"
        pot = 60
        cut = 3.5
    elif num_buildings > 60:
        density = "Medie"
        pot = 40
        cut = 2.0
    else:
        density = "Scăzută"
        pot = 30
        cut = 1.2

    sc = buildable_surface * pot / 100
    sd = buildable_surface * cut

    levels = int(sd / sc) if sc else 0
    height_recommended = levels * 3

    st.write("Densitate:", density)
    st.write("Niveluri recomandate:", levels)

    # ========================
    # 3D VIZUALIZARE
    # ========================

    building_layer = pdk.Layer(
        "PolygonLayer",
        data=buildings,
        get_polygon="polygon",
        get_fill_color=[180, 180, 180, 160],
        extruded=True,
        get_elevation="height",
    )

    terrain_layer = pdk.Layer(
        "PolygonLayer",
        data=[{"polygon": polygon}],
        get_polygon="polygon",
        get_fill_color=[0, 100, 255, 120],
        extruded=True,
        get_elevation=1,
    )

    buildable_layer = pdk.Layer(
        "PolygonLayer",
        data=[{"polygon": buildable_polygon}],
        get_polygon="polygon",
        get_fill_color=[0, 255, 100, 120],
        extruded=True,
        get_elevation=1,
    )

    volume_layer = pdk.Layer(
        "PolygonLayer",
        data=[{"polygon": buildable_polygon}],
        get_polygon="polygon",
        get_fill_color=[255, 0, 0, 180],
        extruded=True,
        get_elevation=height_recommended,
    )

    view = pdk.ViewState(
        latitude=lat,
        longitude=lon,
        zoom=17,
        pitch=45,
    )

    st.pydeck_chart(
        pdk.Deck(
            layers=[
                building_layer,
                terrain_layer,
                buildable_layer,
                volume_layer
            ],
            initial_view_state=view,
        )
    )