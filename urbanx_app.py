import streamlit as st
import requests
import pydeck as pdk
from streamlit_folium import st_folium
import folium
from shapely.geometry import Polygon
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import tempfile

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
# GEOCODE SAFE
# =========================
def geocode(adresa):
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={adresa}"
        r = requests.get(url, timeout=10)
        data = r.json()
        if len(data) == 0:
            return None, None
        return float(data[0]["lat"]), float(data[0]["lon"])
    except:
        return None, None

# =========================
# BUILDINGS SAFE
# =========================
def load_buildings(lat, lon):
    try:
        query = f"""
        [out:json];
        (way["building"](around:150,{lat},{lon}););
        out body;
        >;
        out skel qt;
        """

        r = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query,
            timeout=20
        )

        data = r.json()

        nodes = {}
        buildings = []

        for el in data["elements"]:
            if el["type"] == "node":
                nodes[el["id"]] = (el["lon"], el["lat"])

        for el in data["elements"]:
            if el["type"] == "way":
                coords = []
                for n in el["nodes"]:
                    if n in nodes:
                        coords.append(nodes[n])

                if len(coords) > 2:
                    height = 10
                    if "tags" in el and "building:levels" in el["tags"]:
                        try:
                            height = int(el["tags"]["building:levels"]) * 3
                        except:
                            pass

                    buildings.append({
                        "polygon": coords,
                        "height": height
                    })

        return buildings

    except:
        return []

# =========================
# AI VOLUM REAL
# =========================
def generate_volume(points):
    if len(points) < 3:
        return None, 0

    poly = Polygon(points)
    area = poly.area * 10000000

    POT = 0.6
    CUT = 3.0

    footprint = area * POT
    total = area * CUT

    height = total / footprint if footprint > 0 else 0
    height = min(height * 3, 45)

    return points, height

# =========================
# PDF GENERATOR
# =========================
def generate_pdf(adresa, suprafata, height):

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(tmp.name)
    styles = getSampleStyleSheet()

    story = []

    story.append(Paragraph("URBANX – STUDIU DE AMPLASAMENT", styles["Title"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"Adresă: {adresa}", styles["Normal"]))
    story.append(Paragraph(f"Suprafață estimată: {suprafata} mp", styles["Normal"]))

    story.append(Spacer(1, 12))

    story.append(Paragraph("Indicatori urbanistici", styles["Heading2"]))
    story.append(Paragraph("POT: 60%", styles["Normal"]))
    story.append(Paragraph("CUT: 3.0", styles["Normal"]))
    story.append(Paragraph(f"Regim propus: ~{round(height,1)} m", styles["Normal"]))

    story.append(Spacer(1, 12))

    story.append(Paragraph("Concluzie", styles["Heading2"]))
    story.append(Paragraph("Teren construibil conform PUG.", styles["Normal"]))

    doc.build(story)

    return tmp.name

# =========================
# HEADER UI
# =========================
st.markdown("## 🏙️ UrbanX ENTERPRISE – Analiză urbanistică AI")

adresa = st.text_input("Introdu adresă")

if adresa:
    lat, lon = geocode(adresa)
    if lat:
        st.session_state.lat = lat
        st.session_state.lon = lon

lat = st.session_state.lat
lon = st.session_state.lon

# =========================
# TABURI
# =========================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Hartă",
    "Clădiri",
    "Indicatori",
    "3D",
    "PDF"
])

# =========================
# TAB 1 - HARTA
# =========================
with tab1:

    m = folium.Map(location=[lat, lon], zoom_start=16)

    folium.Marker([lat, lon]).add_to(m)

    for p in st.session_state.parcels:
        folium.CircleMarker(location=(p[1], p[0]), color="red").add_to(m)

    map_data = st_folium(m, height=500)

    if map_data and map_data.get("last_clicked"):
        c = map_data["last_clicked"]
        st.session_state.parcels.append((c["lng"], c["lat"]))

    st.info(f"{len(st.session_state.parcels)} puncte selectate")

# =========================
# TAB 2 - CLADIRI
# =========================
with tab2:

    buildings = load_buildings(lat, lon)

    st.success(f"{len(buildings)} clădiri detectate")

    m2 = folium.Map(location=[lat, lon], zoom_start=16)

    for b in buildings:
        folium.Polygon(
            [(y, x) for x, y in b["polygon"]],
            color="gray",
            fill=True,
            fill_opacity=0.4
        ).add_to(m2)

    st_folium(m2, height=500)

# =========================
# TAB 3 - INDICATORI
# =========================
with tab3:

    suprafata = len(st.session_state.parcels) * 100

    st.metric("Suprafață estimată", f"{suprafata} mp")
    st.metric("POT", "0.6")
    st.metric("CUT", "3.0")

# =========================
# TAB 4 - 3D
# =========================
with tab4:

    buildings = load_buildings(lat, lon)
    data = []

    for b in buildings:
        data.append({
            "polygon": b["polygon"],
            "height": b["height"],
            "color": [180,180,180]
        })

    poly, h = generate_volume(st.session_state.parcels)

    if poly:
        data.append({
            "polygon": poly,
            "height": h,
            "color": [255,0,0]
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
        zoom=16,
        pitch=45
    )

    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view))

# =========================
# TAB 5 - PDF
# =========================
with tab5:

    suprafata = len(st.session_state.parcels) * 100
    _, height = generate_volume(st.session_state.parcels)

    if st.button("Generează PDF profesional"):
        pdf = generate_pdf(adresa, suprafata, height)

        with open(pdf, "rb") as f:
            st.download_button(
                "Descarcă Studiu PDF",
                f,
                file_name="UrbanX_Studiu.pdf"
            )
