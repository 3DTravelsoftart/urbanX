import streamlit as st
import requests
import pydeck as pdk
from streamlit_folium import st_folium
import folium
from shapely.geometry import Polygon
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import tempfile

st.set_page_config(layout="wide")

# =========================
# STATE
# =========================
if "lat" not in st.session_state:
    st.session_state.lat = 47.7486
    st.session_state.lon = 26.669

if "parcel" not in st.session_state:
    st.session_state.parcel = None

# =========================
# BUILDINGS
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

        return buildings

    except:
        return []

# =========================
# AUTO PARCEL (SMART)
# =========================
def generate_auto_parcel(lat, lon):

    size = 0.0003

    return [
        (lon - size, lat - size),
        (lon + size, lat - size),
        (lon + size, lat + size),
        (lon - size, lat + size)
    ]

# =========================
# AI PUZ
# =========================
def generate_puz(polygon):

    if not polygon:
        return None

    poly = Polygon(polygon)
    area = poly.area * 10000000

    POT = 0.6
    CUT = 3.0

    footprint = area * POT
    total_area = area * CUT

    height = min((total_area / footprint) * 3, 45)

    return {
        "polygon": polygon,
        "area": area,
        "footprint": footprint,
        "height": height,
        "POT": POT,
        "CUT": CUT
    }

# =========================
# PDF
# =========================
def generate_pdf(adresa, data):

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")

    doc = SimpleDocTemplate(tmp.name)
    styles = getSampleStyleSheet()

    story = []

    story.append(Paragraph("UrbanX – Studiu Urbanistic", styles["Title"]))
    story.append(Paragraph(f"Adresă: {adresa}", styles["Normal"]))
    story.append(Paragraph(f"Suprafață: {round(data['area'],1)} mp", styles["Normal"]))
    story.append(Paragraph(f"POT: {data['POT']}", styles["Normal"]))
    story.append(Paragraph(f"CUT: {data['CUT']}", styles["Normal"]))
    story.append(Paragraph(f"Hmax: {round(data['height'],1)} m", styles["Normal"]))

    doc.build(story)
    return tmp.name

# =========================
# UI
# =========================
st.title("UrbanX ENTERPRISE – Auto Parcel + AI")

adresa = st.text_input("Adresă proiect")

tabs = st.tabs(["Hartă", "Clădiri", "Indicatori", "3D", "PDF"])

lat = st.session_state.lat
lon = st.session_state.lon

# =========================
# TAB HARTA
# =========================
with tabs[0]:

    st.info("Click pe hartă pentru selecție automată parcelă")

    m = folium.Map(location=[lat, lon], zoom_start=16)

    if st.session_state.parcel:
        folium.Polygon(
            locations=[(p[1], p[0]) for p in st.session_state.parcel],
            color="blue"
        ).add_to(m)

    map_data = st_folium(m, height=500)

    if map_data and map_data.get("last_clicked"):
        c = map_data["last_clicked"]

        st.session_state.lat = c["lat"]
        st.session_state.lon = c["lng"]

        st.session_state.parcel = generate_auto_parcel(c["lat"], c["lng"])

        st.success("Parcelă generată automat ✔")

# =========================
# TAB CLADIRI
# =========================
with tabs[1]:

    buildings = load_buildings(lat, lon)

    st.success(f"{len(buildings)} clădiri detectate")

# =========================
# TAB INDICATORI
# =========================
with tabs[2]:

    puz = generate_puz(st.session_state.parcel)

    if puz:
        col1, col2, col3 = st.columns(3)
        col1.metric("Suprafață", round(puz["area"],1))
        col2.metric("POT", puz["POT"])
        col3.metric("CUT", puz["CUT"])

# =========================
# TAB 3D
# =========================
with tabs[3]:

    buildings = load_buildings(lat, lon)
    puz = generate_puz(st.session_state.parcel)

    if not puz:
        st.warning("Selectează parcela")
    else:

        st.markdown("🔵 Volum propus | ⚪ Clădiri existente")

        data = []

        for b in buildings:
            data.append({
                "polygon": b["polygon"],
                "height": b["height"],
                "color": [180,180,180]
            })

        data.append({
            "polygon": puz["polygon"],
            "height": puz["height"],
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
            pitch=50
        )

        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view))

# =========================
# TAB PDF
# =========================
with tabs[4]:

    puz = generate_puz(st.session_state.parcel)

    if puz and st.button("Generează PDF"):

        pdf = generate_pdf(adresa, puz)

        with open(pdf, "rb") as f:
            st.download_button("Download PDF", f)
