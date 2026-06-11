import sys

import pymeshlab as ml


def save_stats(path):
    ms = ml.MeshSet()
    ms.load_new_mesh(path)
    mesh = ms.current_mesh()
    return mesh.vertex_number(), mesh.face_number()


def repair(input_path, output_path, aggressive=False):
    ms = ml.MeshSet()
    ms.load_new_mesh(input_path)

    ms.meshing_remove_duplicate_vertices()
    ms.meshing_remove_duplicate_faces()
    ms.meshing_remove_null_faces()
    ms.meshing_remove_folded_faces()
    ms.meshing_remove_unreferenced_vertices()

    if aggressive:
        ms.meshing_repair_non_manifold_edges(method="Remove Faces")
        ms.meshing_repair_non_manifold_vertices()
        ms.meshing_remove_t_vertices(method="Edge Collapse", threshold=40, repeat=True)
        ms.meshing_remove_duplicate_vertices()
        ms.meshing_remove_duplicate_faces()
        ms.meshing_remove_null_faces()
        ms.meshing_remove_unreferenced_vertices()

    ms.save_current_mesh(output_path, binary=True)


def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: repair_stl_pymeshlab.py input.stl output.stl conservative|aggressive")

    input_path, output_path, mode = sys.argv[1:]
    repair(input_path, output_path, aggressive=(mode == "aggressive"))
    vertices, faces = save_stats(output_path)
    print(f"Saved {output_path}")
    print(f"Vertices: {vertices}")
    print(f"Faces: {faces}")


if __name__ == "__main__":
    main()
