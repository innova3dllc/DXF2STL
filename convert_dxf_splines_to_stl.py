import math
import os
import sys

import ezdxf
import trimesh
from shapely import symmetric_difference_all
from shapely.geometry import Polygon


def clean_points(points, tolerance=1e-5):
    cleaned = []
    for point in points:
        xy = (float(point.x), float(point.y))
        if not cleaned or math.dist(xy, cleaned[-1]) > tolerance:
            cleaned.append(xy)
    if len(cleaned) > 2 and math.dist(cleaned[0], cleaned[-1]) > tolerance:
        cleaned.append(cleaned[0])
    return cleaned


def entity_to_polygon(entity, flattening_distance):
    if not hasattr(entity, "flattening"):
        return None

    points = clean_points(entity.flattening(flattening_distance))
    if len(points) < 4:
        return None

    polygon = Polygon(points)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty or polygon.area <= 1e-6:
        return None
    return polygon


def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: convert_dxf_splines_to_stl.py input.dxf output.stl thickness_mm")

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    thickness = float(sys.argv[3])

    doc = ezdxf.readfile(input_path)
    polygons = []
    for entity in doc.modelspace():
        polygon = entity_to_polygon(entity, flattening_distance=0.02)
        if polygon is not None:
            polygons.append(polygon)

    if not polygons:
        raise RuntimeError("No usable closed contours found in DXF")

    filled = symmetric_difference_all(polygons)
    parts = list(filled.geoms) if hasattr(filled, "geoms") else [filled]
    meshes = [
        trimesh.creation.extrude_polygon(part, height=thickness)
        for part in parts
        if not part.is_empty and part.area > 1e-6
    ]

    if not meshes:
        raise RuntimeError("Contours were found, but no meshes could be created")

    mesh = trimesh.util.concatenate(meshes)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    mesh.export(output_path)

    print(f"Read {len(polygons)} contours")
    print(f"Exported {output_path}")
    print(f"Mesh vertices: {len(mesh.vertices)}")
    print(f"Mesh faces: {len(mesh.faces)}")


if __name__ == "__main__":
    main()
