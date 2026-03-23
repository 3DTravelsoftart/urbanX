import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import pydeck as pdk
from shapely.geometry import Polygon
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from pyproj import Transformer

st.set_page_config(layout="wide")

st.title("🏙️ UrbanX PRO – Analiză urbanistică")

# =========================
# SESSION
# =========================
if "points" not in st.session_state:
    st.session_state.points = []

# =========================
# FUNCTIONS
# =========================

def calc_area_m2(points):
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    projected = [transformer.transform(p[0], p[1]) for p in points]
    poly = Polygon(projected)
    return poly.area

def load_buildings(lat, lon):
    url = "https://overpass-api.de/api/interpreter"

    query = f"""
    [out:json];
    (
      way["building"](around:200,{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        r = requests.get(url, params={'data': query}, timeout=10)
        data = r.json()

        nodes = {}
        buildings = []

        for el in data["elements"]:
            if el["type"] == "node":
                nodes[el["id"]] = (el["lon"], el["lat"])

        for el in data["elements"]:
            if el["type"] == "way":
                coords = [nodes[n] for n in el["nodes"] if n in nodes]
                if len(coords) < 3:
                    continue

                tags = el.get("tags", {})

                if "height" in tags:
                    h = float(tags["height"])
                elif "building:levels" in tags:
                    h = float(tags["building:levels"]) * 3
                else:
                    h = 10  # fallback mai realist

                buildings.append({
                    "polygon": coords,
                    "height": h
                })

        return buildings

    except:
        return []

def generate_volume(points, buildings):
    if len(points) < 3:
        return None

    poly = Polygon(points)
    minx, miny, maxx, maxy = poly.bounds

    footprint = [
        (minx + 0.00002, miny + 0.00002),
        (maxx - 0.00002, miny + 0.00002),
        (maxx - 0.00002, maxy - 0.00002),
        (minx + 0.00002, maxy - 0.00002),
    ]

    avg_height = sum(b["height"] for b in buildings)/len(buildings) if buildings else 12

    return {
        "polygon": footprint,
        "height": avg_height * 1.2
    }

def generate_pdf(area, pot, cut):
    doc = SimpleDocTemplate("raport.pdf")
    styles = getSampleStyleSheet()

    content = []
    content.append(Paragraph("UrbanX – Studiu Urbanistic", styles["Title"]))
    content.append(Spacer(1, 20))
    content.append(Paragraph(f"Suprafață teren: {round(area)} mp", styles["Normal"]))
    content.append(Paragraph(f"POT: {pot}", styles["Normal"]))
    content.append(Paragraph(f"CUT: {cut}", styles["Normal"]))

    doc.build(content)

# =========================
# TABS
# =========================

tabs = st.tabs(["🗺 Hartă", "📊 Indicatori", "🧠 Analiză", "🧱 3D", "📄 PDF"])

lat, lon = 47.746, 26.669

# =========================
# TAB 1 MAP
# =========================

with tabs[0]:

    st.info("Click pe hartă pentru a defini parcela")

    m = folium.Map(location=[lat, lon], zoom_start=17)

    for p in st.session_state.points:
        folium.CircleMarker([p[1], p[0]], radius=5).add_to(m)

    if len(st.session_state.points) >= 3:
        folium.Polygon(
            locations=[(p[1], p[0]) for p in st.session_state.points],
            color="blue"
        ).add_to(m)

    map_data = st_folium(m, height=500, width=700)

    if map_data and map_data.get("last_clicked"):
        lat_click = map_data["last_clicked"]["lat"]
        lon_click = map_data["last_clicked"]["lng"]
        st.session_state.points.append((lon_click, lat_click))
        st.rerun()

    if st.button("Reset teren"):
        st.session_state.points = []
        st.rerun()

# =========================
# TAB 2 INDICATORI
# =========================

with tabs[1]:

    if len(st.session_state.points) >= 3:
        area = calc_area_m2(st.session_state.points)
    else:
        area = 0

    pot = 0.4
    cut = 1.2

    st.metric("Suprafață teren", f"{round(area)} mp")
    st.metric("POT", pot)
    st.metric("CUT", cut)
    st.metric("Suprafață construită", round(area * pot))
    st.metric("Suprafață desfășurată", round(area * cut))

# =========================
# TAB 3 ANALIZA
# =========================

with tabs[2]:

    st.write("Zonă urbană existentă")
    st.write("Regim estimat: P+2 – P+5")
    st.write("Funcțiune: mixt rezidențial")

# =========================
# TAB 4 3D (CORE)
# =========================

with tabs[3]:

    st.subheader("Vizualizare urbană 3D")

    st.markdown("""
    🔵 Volum propus  
    ⚪ Clădiri existente  
    📏 Etichete = înălțime reală (m)
    """)

    VISUAL_SCALE = 3

    buildings = load_buildings(lat, lon)
    volume = generate_volume(st.session_state.points, buildings)

    polygons = []
    labels = []

    # EXISTENTE
    for b in buildings:
        h_real = b["height"]
        h_visual = h_real * VISUAL_SCALE

        polygons.append({
            "polygon": b["polygon"],
            "height": h_visual,
            "real_height": h_real,
            "color": [180, 180, 180],
            "type": "Clădire existentă"
        })

        poly = Polygon(b["polygon"])
        c = poly.centroid

        labels.append({
            "position": [c.x, c.y],
            "text": f"{int(h_real)}m"
        })

    # PROPUS
    if volume:
        polygons.append({
            "polygon": volume["polygon"],
            "height": volume["height"] * VISUAL_SCALE,
            "real_height": volume["height"],
            "color": [0, 120, 255],
            "type": "Volum propus"
        })

        poly = Polygon(volume["polygon"])
        c = poly.centroid

        labels.append({
            "position": [c.x, c.y],
            "text": f"{int(volume['height'])}m"
        })

    polygon_layer = pdk.Layer(
        "PolygonLayer",
        polygons,
        get_polygon="polygon",
        get_elevation="height",
        get_fill_color="color",
        extruded=True,
        wireframe=True,
        pickable=True
    )

    text_layer = pdk.Layer(
        "TextLayer",
        labels,
        get_position="position",
        get_text="text",
        get_size=18,
        get_color=[255,255,255],
        billboard=True
    )

    st.pydeck_chart(pdk.Deck(
        layers=[polygon_layer, text_layer],
        initial_view_state=pdk.ViewState(
            latitude=lat,
            longitude=lon,
            zoom=17,
            pitch=60,
            bearing=40
        ),
        tooltip={
            "html": "<b>{type}</b><br/>Înălțime: {real_height} m",
            "style": {"backgroundColor": "black", "color": "white"}
        }
    ))

# =========================
# TAB 5 PDF
# =========================

with tabs[4]:

    if st.button("Generează PDF"):
        area = calc_area_m2(st.session_state.points) if len(st.session_state.points)>=3 else 0
        generate_pdf(area, 0.4, 1.2)

        with open("raport.pdf", "rb") as f:
            st.download_button("Download PDF", f, file_name="raport.pdf")
