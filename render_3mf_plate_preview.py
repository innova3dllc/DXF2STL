import argparse
import json
import math
import struct
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET


CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PRODUCTION_NS = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
NS = {"m": CORE_NS}


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def production_attr(element, name, default=None):
    return element.attrib.get(f"{{{PRODUCTION_NS}}}{name}", default)


def parse_transform(value):
    if not value:
        return identity_matrix()

    numbers = [float(part) for part in value.split()]
    if len(numbers) != 12:
        raise ValueError(f"Expected 12 transform values, got {len(numbers)}")

    # 3MF stores the transform as a 3x4 affine matrix with translation in
    # the final three values. Bambu/Orca project files use the column-vector
    # convention below when applying that matrix to mesh vertices.
    return (
        (numbers[0], numbers[3], numbers[6], numbers[9]),
        (numbers[1], numbers[4], numbers[7], numbers[10]),
        (numbers[2], numbers[5], numbers[8], numbers[11]),
        (0.0, 0.0, 0.0, 1.0),
    )


def identity_matrix():
    return (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )


def multiply_matrix(left, right):
    return tuple(
        tuple(sum(left[row][k] * right[k][col] for k in range(4)) for col in range(4))
        for row in range(4)
    )


def transform_point(matrix, point):
    x, y, z = point
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3],
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3],
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3],
    )


def triangle_normal_z(a, b, c):
    ux, uy, _uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, _vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    return ux * vy - uy * vx


def read_model(zip_file, path):
    normalized = path.lstrip("/")
    return ET.fromstring(zip_file.read(normalized))


def mesh_triangles_from_model(root, object_id, matrix):
    object_node = root.find(f".//m:object[@id='{object_id}']", NS)
    if object_node is None:
        return []

    vertices_node = object_node.find(".//m:vertices", NS)
    triangles_node = object_node.find(".//m:triangles", NS)
    if vertices_node is None or triangles_node is None:
        return []

    vertices = []
    for vertex in vertices_node:
        if local_name(vertex.tag) != "vertex":
            continue
        vertices.append(
            transform_point(
                matrix,
                (
                    float(vertex.attrib["x"]),
                    float(vertex.attrib["y"]),
                    float(vertex.attrib["z"]),
                ),
            )
        )

    triangles = []
    for triangle in triangles_node:
        if local_name(triangle.tag) != "triangle":
            continue
        a = vertices[int(triangle.attrib["v1"])]
        b = vertices[int(triangle.attrib["v2"])]
        c = vertices[int(triangle.attrib["v3"])]
        if abs(triangle_normal_z(a, b, c)) > 1e-9:
            triangles.append((a, b, c))
    return triangles


def load_arranged_triangles(input_path):
    triangles = []
    with zipfile.ZipFile(input_path) as zip_file:
        root = read_model(zip_file, "3D/3dmodel.model")
        object_nodes = {
            node.attrib["id"]: node
            for node in root.findall(".//m:object", NS)
        }

        for item in root.findall(".//m:build/m:item", NS):
            parent_id = item.attrib["objectid"]
            parent = object_nodes[parent_id]
            parent_matrix = parse_transform(item.attrib.get("transform"))

            for component in parent.findall(".//m:component", NS):
                component_path = production_attr(component, "path")
                if not component_path:
                    continue
                component_root = read_model(zip_file, component_path)
                component_matrix = parse_transform(component.attrib.get("transform"))
                combined = multiply_matrix(parent_matrix, component_matrix)
                triangles.extend(
                    mesh_triangles_from_model(
                        component_root,
                        component.attrib["objectid"],
                        combined,
                    )
                )

    if not triangles:
        raise RuntimeError(f"No arranged mesh triangles found in {input_path}")
    return triangles


def triangle_bounds(triangles):
    xs = [point[0] for triangle in triangles for point in triangle]
    ys = [point[1] for triangle in triangles for point in triangle]
    return min(xs), min(ys), max(xs), max(ys)


def parse_point(value):
    x, y = value.split("x", 1)
    return float(x), float(y)


def load_printable_area_bounds(input_path):
    try:
        with zipfile.ZipFile(input_path) as zip_file:
            settings = json.loads(zip_file.read("Metadata/project_settings.config"))
    except (KeyError, json.JSONDecodeError, zipfile.BadZipFile):
        return None

    printable_area = settings.get("printable_area")
    if not printable_area:
        return None

    points = [parse_point(point) for point in printable_area]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, min_y, max_x, max_y = min(xs), min(ys), max(xs), max(ys)
    if max_x <= min_x or max_y <= min_y:
        return None
    return min_x, min_y, max_x, max_y


def write_png(path, width, height, pixels):
    def chunk(name, data):
        payload = name + data
        return (
            struct.pack(">I", len(data))
            + payload
            + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
        )

    rows = []
    stride = width * 3
    for row in range(height):
        start = row * stride
        rows.append(b"\x00" + bytes(pixels[start : start + stride]))

    raw = b"".join(rows)
    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
        handle.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        handle.write(chunk(b"IEND", b""))


def draw_line(pixels, width, height, start, end, color):
    x0, y0 = start
    x1, y1 = end
    dx = x1 - x0
    dy = y1 - y0
    steps = max(abs(dx), abs(dy), 1)
    for step in range(steps + 1):
        x = round(x0 + dx * step / steps)
        y = round(y0 + dy * step / steps)
        if 0 <= x < width and 0 <= y < height:
            index = (y * width + x) * 3
            pixels[index : index + 3] = color


def fill_triangle(pixels, width, height, points, color):
    min_y = max(0, math.floor(min(point[1] for point in points)))
    max_y = min(height - 1, math.ceil(max(point[1] for point in points)))

    for y in range(min_y, max_y + 1):
        scan_y = y + 0.5
        intersections = []
        for i, point in enumerate(points):
            next_point = points[(i + 1) % 3]
            y0, y1 = point[1], next_point[1]
            if y0 == y1:
                continue
            if min(y0, y1) <= scan_y < max(y0, y1):
                t = (scan_y - y0) / (y1 - y0)
                intersections.append(point[0] + t * (next_point[0] - point[0]))
        if len(intersections) < 2:
            continue
        intersections.sort()
        for left, right in zip(intersections[0::2], intersections[1::2]):
            min_x = max(0, math.floor(left))
            max_x = min(width - 1, math.ceil(right))
            offset = (y * width + min_x) * 3
            for _x in range(min_x, max_x + 1):
                pixels[offset : offset + 3] = color
                offset += 3


def render_preview(input_path, output_path, image_size=1600, margin=48):
    triangles = load_arranged_triangles(input_path)
    min_x, min_y, max_x, max_y = load_printable_area_bounds(input_path) or triangle_bounds(triangles)
    width_mm = max_x - min_x
    height_mm = max_y - min_y
    if width_mm <= 0 or height_mm <= 0:
        raise RuntimeError("Arranged geometry has invalid bounds")

    scale = (image_size - margin * 2) / max(width_mm, height_mm)
    image_width = max(1, round(width_mm * scale + margin * 2))
    image_height = max(1, round(height_mm * scale + margin * 2))

    background = b"\xf8\xf8\xf5"
    bed = b"\xe7\xe4\xdc"
    part = b"\x4b\x72\xa4"
    edge = b"\x23\x34\x48"

    pixels = bytearray(background * (image_width * image_height))
    for y in range(margin, image_height - margin):
        start = (y * image_width + margin) * 3
        end = (y * image_width + image_width - margin) * 3
        pixels[start:end] = bed * (image_width - margin * 2)

    def project(point):
        return (
            (point[0] - min_x) * scale + margin,
            image_height - ((point[1] - min_y) * scale + margin),
        )

    for triangle in triangles:
        fill_triangle(pixels, image_width, image_height, [project(point) for point in triangle], part)

    border = [
        (margin, margin),
        (image_width - margin - 1, margin),
        (image_width - margin - 1, image_height - margin - 1),
        (margin, image_height - margin - 1),
    ]
    for start, end in zip(border, border[1:] + border[:1]):
        draw_line(pixels, image_width, image_height, start, end, edge)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_png(output_path, image_width, image_height, pixels)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Render a top-down PNG preview of an arranged 3MF plate.")
    parser.add_argument("input_3mf", help="Input arranged 3MF file.")
    parser.add_argument("output_png", nargs="?", help="Output PNG path. Default: input name with .png")
    parser.add_argument("--size", type=int, default=1600, help="Maximum preview image size in pixels.")
    args = parser.parse_args()

    input_path = Path(args.input_3mf)
    output_path = Path(args.output_png) if args.output_png else input_path.with_suffix(".png")
    render_preview(input_path, output_path, args.size)
    print(f"Rendered {output_path}")


if __name__ == "__main__":
    main()
