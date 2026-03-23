from shapely.geometry import Polygon

def generate_urban_volume(points):

    if len(points) < 3:
        return None, 0

    poly = Polygon(points)

    # 🔹 setback urbanistic (retragere)
    setback = 0.00005
    inner = poly.buffer(-setback)

    if inner.is_empty:
        inner = poly

    coords = list(inner.exterior.coords)

    # 🔹 calcul urbanistic
    area = poly.area * 10000000

    POT = 0.6
    CUT = 3.0

    footprint = area * POT
    total = area * CUT

    height = total / footprint if footprint > 0 else 0
    height = min(height * 3, 45)

    return coords, height
