import os
import shlex
import sys

import FreeCAD as App
import Mesh
import Part
import importDXF


def log(message):
    print(message, flush=True)


def collect_edges(doc):
    edges = []
    for obj in doc.Objects:
        shape = getattr(obj, "Shape", None)
        if shape is None or shape.isNull():
            continue
        edges.extend(shape.Edges)
    return edges


def make_closed_wires(edges):
    if hasattr(Part, "sortEdges"):
        groups = Part.sortEdges(edges)
    else:
        groups = Part.__sortEdges__(edges)

    wires = []
    for group in groups:
        try:
            wire = Part.Wire(group)
        except Exception:
            continue
        if wire.isClosed():
            wires.append(wire)
    return wires


def polygon_face_from_wire(wire):
    points = []
    for edge in wire.Edges:
        try:
            edge_points = edge.discretize(Deflection=0.05)
        except Exception:
            edge_points = edge.discretize(200)
        if points and edge_points:
            edge_points = edge_points[1:]
        points.extend(edge_points)

    if len(points) < 3:
        return None
    if points[0].distanceToPoint(points[-1]) > 0.001:
        points.append(points[0])

    try:
        return Part.Face(Part.Wire(Part.makePolygon(points)))
    except Exception:
        return None


def main():
    args = sys.argv[1:]
    if args and os.path.basename(args[0]) == os.path.basename(__file__):
        args = args[1:]
    if args and args[0] == "--pass":
        args = shlex.split(args[1]) if len(args) == 2 else args[1:]

    if not args and os.environ.get("DXF_INPUT") and os.environ.get("STL_OUTPUT"):
        args = [
            os.environ["DXF_INPUT"],
            os.environ["STL_OUTPUT"],
            os.environ.get("THICKNESS_MM", "3"),
        ]

    if len(args) != 3:
        raise SystemExit("usage: convert_dxf_to_stl.py input.dxf output.stl thickness_mm")

    input_path = os.path.abspath(args[0])
    output_path = os.path.abspath(args[1])
    thickness = float(args[2])

    if not os.path.exists(input_path):
        raise FileNotFoundError(input_path)

    log(f"Importing {input_path}")
    doc = importDXF.open(input_path)
    if doc is None:
        doc = App.ActiveDocument
    doc.recompute()

    edges = collect_edges(doc)
    log(f"Imported {len(edges)} edges")
    if not edges:
        raise RuntimeError("No edges imported from DXF")

    wires = make_closed_wires(edges)
    log(f"Found {len(wires)} closed wires")
    if not wires:
        raise RuntimeError("No closed wires found; cannot make a 3D solid")

    faces = []
    for wire in wires:
        try:
            faces.append(Part.Face(wire))
        except Exception:
            face = polygon_face_from_wire(wire)
            if face is not None:
                faces.append(face)

    log(f"Built {len(faces)} planar faces")
    if not faces:
        raise RuntimeError("Closed wires were found, but none could be converted to faces")

    solids = [face.extrude(App.Vector(0, 0, thickness)) for face in faces]
    shape = Part.makeCompound(solids) if len(solids) > 1 else solids[0]

    solid_obj = doc.addObject("Part::Feature", "ExtrudedDXF")
    solid_obj.Shape = shape
    doc.recompute()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    log(f"Exporting {output_path}")
    Mesh.export([solid_obj], output_path)
    log("Done")


main()
