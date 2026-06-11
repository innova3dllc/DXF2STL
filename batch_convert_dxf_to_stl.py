import argparse
import os
from pathlib import Path

from convert_dxf_manifold_to_stl import convert_dxf_to_stl, positive_float


def dxf_files(folder):
    return sorted(
        path
        for path in Path(folder).iterdir()
        if path.is_file() and path.suffix.lower() == ".dxf"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Convert all DXF files directly inside a folder to STL."
    )
    parser.add_argument("input_folder", help="Folder containing DXF files; subdirectories are ignored.")
    parser.add_argument(
        "output_folder",
        nargs="?",
        help="Folder for STL output. Default: <input_folder>/stl",
    )
    parser.add_argument(
        "--thickness",
        "-t",
        type=float,
        default=3.0,
        help="Extrusion thickness in mm. Default: 3.0",
    )
    parser.add_argument(
        "--cleanup",
        "-c",
        type=float,
        default=0.0005,
        help="2D cleanup offset in mm before extrusion. Default: 0.0005",
    )
    parser.add_argument(
        "--scale",
        type=positive_float,
        default=1.0,
        help="Uniform scale multiplier for X, Y, and Z. Default: 1.0",
    )
    parser.add_argument(
        "--scale-x",
        type=positive_float,
        default=1.0,
        help="Extra X-axis scale multiplier. Default: 1.0",
    )
    parser.add_argument(
        "--scale-y",
        type=positive_float,
        default=1.0,
        help="Extra Y-axis scale multiplier. Default: 1.0",
    )
    parser.add_argument(
        "--scale-z",
        type=positive_float,
        default=1.0,
        help="Extra Z-axis scale multiplier. Default: 1.0",
    )
    parser.add_argument(
        "--suffix",
        default="",
        help="Suffix added to each STL filename before .stl.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing STL files.",
    )
    args = parser.parse_args()

    input_folder = Path(args.input_folder)
    output_folder = Path(args.output_folder) if args.output_folder else input_folder / "stl"

    if not input_folder.is_dir():
        raise SystemExit(f"Input folder does not exist: {input_folder}")

    files = dxf_files(input_folder)
    if not files:
        raise SystemExit(f"No DXF files found directly in: {input_folder}")

    output_folder.mkdir(parents=True, exist_ok=True)
    failures = []

    print(f"Found {len(files)} DXF files in {input_folder}")
    for input_path in files:
        output_name = f"{input_path.stem}{args.suffix}.stl"
        output_path = output_folder / output_name

        if output_path.exists() and not args.overwrite:
            print(f"SKIP {input_path.name} -> {output_path} already exists")
            continue

        print(f"CONVERT {input_path.name} -> {output_path}")
        try:
            result = convert_dxf_to_stl(
                str(input_path),
                str(output_path),
                args.thickness,
                args.cleanup,
                args.scale,
                args.scale_x,
                args.scale_y,
                args.scale_z,
            )
            print(
                "  OK "
                f"contours={result['contours']} "
                f"faces={result['faces']} "
                f"watertight={result['watertight']} "
                f"scale=({result['scale_x']}, {result['scale_y']}, {result['scale_z']})"
            )
        except Exception as exc:
            failures.append((input_path, exc))
            print(f"  FAIL {type(exc).__name__}: {exc}")

    if failures:
        print()
        print(f"Failed: {len(failures)}")
        for input_path, exc in failures:
            print(f"  {input_path}: {type(exc).__name__}: {exc}")
        raise SystemExit(1)

    print("Done")


if __name__ == "__main__":
    main()
