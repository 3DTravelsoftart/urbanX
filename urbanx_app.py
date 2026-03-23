import streamlit as st
import requests
import pydeck as pdk
from streamlit_folium import st_folium
import folium
from shapely.geometry import Polygon
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image
from reportlab.lib.styles import getSampleStyleSheet
import tempfile
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")

# =========================
# STATE
# =========================
if "lat" not in st.session_state:
    st.session_state.lat = 47.7486
    st.session_state.lon = 26.669

if "parcels" not in st.session_state:
    st.session_state.parcels = []

# =========================
# BUILDINGS SAFE
# =========================
def load_buildings(lat, lon):

    try:
        query = f"""
        [out:json];
        (way["building"](around:120,{lat},{lon}););
        out body;
        >;
        out skel qt;
        """

        r = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query,
            timeout=10
        )

        data = r.json()

        nodes = {}
        buildings = []

        for el in data["elements"]:
            if el["type"] == "node":
                nodes[el["id"]] = (el["lon"], el["lat"])

        for el in data["elements"]:
            if el["type"] == "way":
                coords = [nodes[n] for n in el["nodes"] if n in nodes]

                if len(coords) > 2:
                    h = 12
                    if "tags" in el and "building:levels" in el["tags"]:
                        try:
                            h = int(el["tags"]["building:levels"]) * 3
                        except:
                            pass

                    buildings.append({
                        "polygon": coords,
                        "height": h
                    })

        if len(buildings) == 0:
            raise Exception("fallback")

        return buildings

    except:
        return [{
            "polygon": [
                [lon-0.0003, lat-0.0003],
                [lon-0.0001, lat-0.0003],
                [lon-0.0001, lat-0.0001],
                [lon-0.0003, lat-0.0001]
            ],
            "height": 15
        }]

# =========================
# PUZ AI
# =========================
def generate_puz(points):

    if len(points) < 3:
        return None

    poly = Polygon(points)
    area = poly.area * 10000000

    POT = 0.6
    CUT = 3.0

    footprint = area * POT
    total_area = area * CUT

    height = min((total_area / footprint) * 3, 45)

    return {
        "polygon": points,
        "area": area,
        "footprint": footprint,
        "height": height
    }

# =========================
# SNAPSHOT 3D
# =========================
def create_image():

    fig = plt.figure()
    plt.plot([0,1],[0,1])
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    plt.savefig(tmp.name)
    return tmp.name

# =========================
# PDF
# =========================
def generate_pdf(adresa, data, image_path):

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")

    doc = SimpleDocTemplate(tmp.name)
    styles = getSampleStyleSheet()

    story = []

    story.append(Paragraph("UrbanX – Studiu Urbanistic", styles["Title"]))
    story.append(Paragraph(f"Adresă: {adresa}", styles["Normal"]))
    story.append(Paragraph(f"Suprafață: {round(data['area'],1)} mp", styles["Normal"]))
    story.append(Paragraph(f"Înălțime: {round(data['height'],1)} m", styles["Normal"]))

    story.append(Image(image_path, width=400, height=200))

    doc.build(story)

    return tmp.name

# =========================
# UI
# =========================
st.title("UrbanX ENTERPRISE – INVESTOR MODE")

adresa = st.text_input("Adresă")

tabs = st.tabs(["Hartă", "Clădiri", "3D", "PDF"])

lat = st.session_state.lat
lon = st.session_state.lon

# =========================
# HARTA
# =========================
with tabs[0]:

    m = folium.Map(location=[lat, lon], zoom_start=16)

    for p in st.session_state.parcels:
        folium.CircleMarker(location=(p[1], p[0]), color="red").add_to(m)

    map_data = st_folium(m, height=500)

    if map_data and map_data.get("last_clicked"):
        c = map_data["last_clicked"]
        st.session_state.parcels.append((c["lng"], c["lat"]))

    st.info(f"{len(st.session_state.parcels)} puncte")

    if st.button("Reset"):
        st.session_state.parcels = []

# =========================
# CLADIRI
# =========================
with tabs[1]:

    buildings = load_buildings(lat, lon)

    st.metric("Clădiri detectate", len(buildings))

# =========================
# 3D
# =========================
with tabs[2]:

    buildings = load_buildings(lat, lon)
    puz = generate_puz(st.session_state.parcels)

    if not puz:
        st.warning("Selectează parcelă")
    else:

        col1, col2, col3 = st.columns(3)

        col1.metric("Suprafață", round(puz["area"],1))
        col2.metric("Footprint", round(puz["footprint"],1))
        col3.metric("Înălțime", round(puz["height"],1))

        data = []

        for b in buildings:
            data.append({
                "polygon": b["polygon"],
                "height": b["height"],
                "color": [150,150,150]
            })

        data.append({
            "polygon": puz["polygon"],
            "height": puz["height"],
            "color": [0,100,255]
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
            pitch=50
        )

        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view))

# =========================
# PDF
# =========================
with tabs[3]:

    puz = generate_puz(st.session_state.parcels)

    if puz and st.button("Generează PDF"):

        img = create_image()
        pdf = generate_pdf(adresa, puz, img)

        with open(pdf, "rb") as f:
            st.download_button("Download PDF", f)
