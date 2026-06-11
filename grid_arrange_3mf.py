import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from render_3mf_plate_preview import (
    NS,
    parse_transform,
    production_attr,
    read_model,
    transform_point,
)


PRODUCTION_NS = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"


def parse_point(value):
    x, y = value.split("x", 1)
    return float(x), float(y)


def printable_bounds(zip_file):
    settings = json.loads(zip_file.read("Metadata/project_settings.config"))
    points = [parse_point(point) for point in settings["printable_area"]]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def model_bounds(zip_file, component):
    component_path = production_attr(component, "path")
    component_root = read_model(zip_file, component_path)
    component_matrix = parse_transform(component.attrib.get("transform"))
    object_id = component.attrib["objectid"]
    object_node = component_root.find(f".//m:object[@id='{object_id}']", NS)
    vertices_node = object_node.find(".//m:vertices", NS)

    points = []
    for vertex in vertices_node:
        point = (
            float(vertex.attrib["x"]),
            float(vertex.attrib["y"]),
            float(vertex.attrib["z"]),
        )
        points.append(transform_point(component_matrix, point))

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)


def transform_string(tx, ty, tz=0.0):
    return f"1 0 0 0 1 0 0 0 1 {tx:.6f} {ty:.6f} {tz:.6f}"


def arrange_items(zip_file, root, spacing):
    bed_min_x, bed_min_y, bed_max_x, bed_max_y = printable_bounds(zip_file)
    bed_width = bed_max_x - bed_min_x
    if bed_width <= 0:
        raise RuntimeError("Invalid printable_area width")

    object_nodes = {
        node.attrib["id"]: node
        for node in root.findall(".//m:object", NS)
    }
    items = root.findall(".//m:build/m:item", NS)
    arranged = []
    for item in items:
        parent = object_nodes[item.attrib["objectid"]]
        component = parent.find(".//m:component", NS)
        if component is None:
            continue
        min_x, min_y, min_z, max_x, max_y, _max_z = model_bounds(zip_file, component)
        arranged.append(
            {
                "item": item,
                "min_x": min_x,
                "min_y": min_y,
                "min_z": min_z,
                "width": max_x - min_x,
                "height": max_y - min_y,
            }
        )

    x = bed_min_x
    y = bed_min_y
    row_height = 0.0
    for entry in arranged:
        if x > bed_min_x and x + entry["width"] > bed_max_x:
            x = bed_min_x
            y += row_height + spacing
            row_height = 0.0

        tx = x - entry["min_x"]
        ty = y - entry["min_y"]
        tz = -entry["min_z"]
        entry["item"].set("transform", transform_string(tx, ty, tz))

        x += entry["width"] + spacing
        row_height = max(row_height, entry["height"])

    used_height = (y + row_height) - bed_min_y
    bed_height = bed_max_y - bed_min_y
    if used_height > bed_height:
        raise RuntimeError(
            f"Grid arrangement needs {used_height:.2f} mm height, bed has {bed_height:.2f} mm"
        )


def write_updated_3mf(input_path, output_path, model_bytes):
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "updated.3mf"
        with zipfile.ZipFile(input_path) as source, zipfile.ZipFile(temp_path, "w") as target:
            for info in source.infolist():
                data = model_bytes if info.filename == "3D/3dmodel.model" else source.read(info.filename)
                target.writestr(info, data)
        shutil.move(temp_path, output_path)


def grid_arrange_3mf(input_path, output_path=None, spacing=2.0):
    input_path = Path(input_path)
    output_path = Path(output_path) if output_path else input_path

    ET.register_namespace("", "http://schemas.microsoft.com/3dmanufacturing/core/2015/02")
    ET.register_namespace("p", PRODUCTION_NS)
    ET.register_namespace("BambuStudio", "http://schemas.bambulab.com/package/2021")

    with zipfile.ZipFile(input_path) as zip_file:
        root = read_model(zip_file, "3D/3dmodel.model")
        arrange_items(zip_file, root, spacing)

    model_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    write_updated_3mf(input_path, output_path, model_bytes)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Rewrite a 3MF as a no-rotation grid layout.")
    parser.add_argument("input_3mf")
    parser.add_argument("output_3mf", nargs="?")
    parser.add_argument("--spacing", type=float, default=2.0)
    args = parser.parse_args()

    output_path = grid_arrange_3mf(args.input_3mf, args.output_3mf, args.spacing)
    print(f"Grid arranged {output_path}")


if __name__ == "__main__":
    main()
