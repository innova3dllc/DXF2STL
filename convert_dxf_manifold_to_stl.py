import argparse
import math
import os

import ezdxf
import manifold3d as mf
import trimesh


def positive_float(value):
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return number


def clean_contour(points, scale_x=1.0, scale_y=1.0, tolerance=1e-5):
    contour = []
    for point in points:
        xy = [float(point.x) * scale_x, float(point.y) * scale_y]
        if not contour or math.dist(xy, contour[-1]) > tolerance:
            contour.append(xy)
    if len(contour) > 2 and math.dist(contour[0], contour[-1]) <= tolerance:
        contour.pop()
    return contour if len(contour) >= 3 else None


def signed_area(contour):
    area = 0.0
    for i, point in enumerate(contour):
        next_point = contour[(i + 1) % len(contour)]
        area += point[0] * next_point[1] - next_point[0] * point[1]
    return area / 2.0


def convert_dxf_to_stl(
    input_path,
    output_path,
    thickness,
    cleanup=0.0,
    scale=1.0,
    scale_x=1.0,
    scale_y=1.0,
    scale_z=1.0,
):
    effective_scale_x = scale * scale_x
    effective_scale_y = scale * scale_y
    effective_scale_z = scale * scale_z
    effective_thickness = thickness * effective_scale_z

    doc = ezdxf.readfile(input_path)
    contours = []
    for entity in doc.modelspace():
        if not hasattr(entity, "flattening"):
            continue
        contour = clean_contour(entity.flattening(0.02), effective_scale_x, effective_scale_y)
        if contour is None or abs(signed_area(contour)) <= 1e-6:
            continue
        contours.append(contour)

    if not contours:
        raise RuntimeError("No usable closed contours found in DXF")

    cross_section = mf.CrossSection(contours, mf.FillRule.EvenOdd)
    if cleanup:
        cross_section = cross_section.offset(-cleanup).offset(cleanup).simplify()
    solid = cross_section.extrude(effective_thickness)
    mesh = solid.to_mesh()
    trimesh_mesh = trimesh.Trimesh(
        vertices=mesh.vert_properties,
        faces=mesh.tri_verts,
        process=True,
    )
    if len(trimesh_mesh.faces) == 0:
        raise RuntimeError("Generated mesh has zero faces")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    trimesh_mesh.export(output_path)

    return {
        "input": input_path,
        "output": output_path,
        "contours": len(contours),
        "cross_section_contours": cross_section.num_contour(),
        "status": solid.status(),
        "vertices": len(trimesh_mesh.vertices),
        "faces": len(trimesh_mesh.faces),
        "watertight": trimesh_mesh.is_watertight,
        "scale_x": effective_scale_x,
        "scale_y": effective_scale_y,
        "scale_z": effective_scale_z,
        "thickness": effective_thickness,
    }


def main():
    parser = argparse.ArgumentParser(description="Convert one DXF file to an extruded STL.")
    parser.add_argument("input_dxf")
    parser.add_argument("output_stl")
    parser.add_argument("thickness_mm", type=positive_float)
    parser.add_argument("cleanup_mm", nargs="?", type=float, default=0.0)
    parser.add_argument("--scale", type=positive_float, default=1.0, help="Uniform scale multiplier. Default: 1.0")
    parser.add_argument("--scale-x", type=positive_float, default=1.0, help="Extra X-axis scale multiplier. Default: 1.0")
    parser.add_argument("--scale-y", type=positive_float, default=1.0, help="Extra Y-axis scale multiplier. Default: 1.0")
    parser.add_argument("--scale-z", type=positive_float, default=1.0, help="Extra Z-axis scale multiplier. Default: 1.0")
    args = parser.parse_args()

    result = convert_dxf_to_stl(
        args.input_dxf,
        args.output_stl,
        args.thickness_mm,
        args.cleanup_mm,
        args.scale,
        args.scale_x,
        args.scale_y,
        args.scale_z,
    )

    print(f"Read {result['contours']} contours")
    print(f"Cross-section contours: {result['cross_section_contours']}")
    print(f"Manifold status: {result['status']}")
    print(f"Scale: x={result['scale_x']} y={result['scale_y']} z={result['scale_z']}")
    print(f"Effective thickness: {result['thickness']}")
    print(f"Exported {args.output_stl}")
    print(f"Mesh vertices: {result['vertices']}")
    print(f"Mesh faces: {result['faces']}")
    print(f"Watertight: {result['watertight']}")


if __name__ == "__main__":
    main()
