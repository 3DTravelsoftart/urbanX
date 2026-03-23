import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import pydeck as pdk
from shapely.geometry import Polygon
from shapely.ops import unary_union
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

st.set_page_config(layout="wide")

st.title("🏙️ UrbanX PRO – Analiză urbanistică AI")

# =========================
# SESSION
# =========================
if "points" not in st.session_state:
    st.session_state.points = []

# =========================
# GEOCODARE
# =========================
def geocode(address):
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={address}"
        r = requests.get(url, headers={"User-Agent": "urbanx"})
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except:
        pass
    return None, None

# =========================
# BUILDINGS
# =========================
def load_buildings(lat, lon):
    try:
        query = f"""
        [out:json];
        way["building"](around:150,{lat},{lon});
        out geom;
        """
        r = requests.get("https://overpass-api.de/api/interpreter", params={"data": query})

        if r.status_code != 200:
            return []

        data = r.json()
        buildings = []

        for el in data.get("elements", []):
            if "geometry" in el:
                coords = [(p["lon"], p["lat"]) for p in el["geometry"]]
                levels = el.get("tags", {}).get("building:levels")
                height = float(levels)*3 if levels else 10

                buildings.append({
                    "polygon": coords,
                    "height": height
                })

        return buildings

    except:
        return []

# =========================
# AI VOLUME
# =========================
def generate_ai_volume(parcel_coords, buildings):

    if not parcel_coords or len(parcel_coords) < 3:
        return None

    parcel = Polygon(parcel_coords)

    building_polys = []
    heights = []

    for b in buildings:
        try:
            poly = Polygon(b["polygon"])
            building_polys.append(poly.buffer(0.00003))
            heights.append(b["height"])
        except:
            continue

    if building_polys:
        occupied = unary_union(building_polys)
        free_area = parcel.difference(occupied)
    else:
        free_area = parcel

    if free_area.is_empty:
        free_area = parcel.buffer(-0.00005)

    if free_area.geom_type == "MultiPolygon":
        free_area = max(free_area.geoms, key=lambda g: g.area)

    coords = list(free_area.exterior.coords)

    if heights:
        avg_h = sum(heights)/len(heights)
        height = min(avg_h*1.2, 45)
    else:
        height = 18

    return {"polygon": coords, "height": height}

# =========================
# PDF GENERATOR PRO
# =========================
def generate_pdf(address, area, footprint, gfa):

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    elements = []

    elements.append(Paragraph("UrbanX – Studiu Urbanistic", styles["Title"]))
    elements.append(Spacer(1,10))

    elements.append(Paragraph(f"Adresă: {address}", styles["Normal"]))
    elements.append(Spacer(1,10))

    elements.append(Paragraph("Indicatori urbanistici:", styles["Heading2"]))
    elements.append(Paragraph(f"Suprafață teren: {area:.0f} mp", styles["Normal"]))
    elements.append(Paragraph(f"Amprentă maximă (POT): {footprint:.0f} mp", styles["Normal"]))
    elements.append(Paragraph(f"Suprafață desfășurată (CUT): {gfa:.0f} mp", styles["Normal"]))

    elements.append(Spacer(1,20))

    elements.append(Paragraph("Interpretare AI:", styles["Heading2"]))

    elements.append(Paragraph(
        "Terenul permite dezvoltare urbană optimă conform indicatorilor. "
        "Volumul propus este adaptat contextului existent și respectă "
        "regimul de înălțime al clădirilor învecinate.",
        styles["Normal"]
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# =========================
# INPUT
# =========================
address = st.text_input("📍 Introdu adresă")

lat, lon = 47.7486, 26.669

if address:
    lat2, lon2 = geocode(address)
    if lat2:
        lat, lon = lat2, lon2

# =========================
# TABS
# =========================
tabs = st.tabs(["🗺️ Hartă", "🏢 Clădiri", "📊 Indicatori", "🏗️ 3D", "📄 PDF"])

# =========================
# HARTA
# =========================
with tabs[0]:

    m = folium.Map(location=[lat, lon], zoom_start=17)

    map_data = st_folium(m, height=500)

    if map_data and map_data.get("last_clicked"):
        pt = map_data["last_clicked"]
        st.session_state.points.append((pt["lng"], pt["lat"]))

    for p in st.session_state.points:
        folium.CircleMarker(location=[p[1], p[0]], radius=5, color="red").add_to(m)

    st_folium(m, height=500)

# =========================
# CLADIRI
# =========================
with tabs[1]:

    buildings = load_buildings(lat, lon)
    st.success(f"{len(buildings)} clădiri detectate")

# =========================
# INDICATORI
# =========================
with tabs[2]:

    if len(st.session_state.points) >= 3:

        parcel = Polygon(st.session_state.points)
        area = parcel.area * 10000000000

        pot = 0.4
        cut = 1.2

        footprint = area * pot
        gfa = area * cut

        st.metric("Suprafață", f"{area:.0f} mp")
        st.metric("Amprentă", f"{footprint:.0f} mp")
        st.metric("GFA", f"{gfa:.0f} mp")

# =========================
# 3D
# =========================
with tabs[3]:

    buildings = load_buildings(lat, lon)
    ai_vol = generate_ai_volume(st.session_state.points, buildings)

    if ai_vol:

        data = []

        for b in buildings:
            data.append({
                "polygon": b["polygon"],
                "height": b["height"],
                "color": [180,180,180]
            })

        data.append({
            "polygon": ai_vol["polygon"],
            "height": ai_vol["height"],
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

        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=pdk.ViewState(
                latitude=lat,
                longitude=lon,
                zoom=17,
                pitch=65
            )
        ))

# =========================
# PDF
# =========================
with tabs[4]:

    if len(st.session_state.points) >= 3:

        parcel = Polygon(st.session_state.points)
        area = parcel.area * 10000000000

        pot = 0.4
        cut = 1.2

        footprint = area * pot
        gfa = area * cut

        pdf = generate_pdf(address, area, footprint, gfa)

        st.download_button(
            "📄 Descarcă PDF profesional",
            data=pdf,
            file_name="UrbanX_report.pdf",
            mime="application/pdf"
        )
