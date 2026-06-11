import argparse
import os
import shlex
import shutil
import struct
import subprocess
from datetime import datetime
from pathlib import Path

from convert_dxf_manifold_to_stl import convert_dxf_to_stl, positive_float
from grid_arrange_3mf import grid_arrange_3mf
from render_3mf_plate_preview import render_preview


ORCA_FLATPAK_COMMAND = [
    "flatpak",
    "run",
    "--command=orca-slicer",
    "com.orcaslicer.OrcaSlicer",
]
ORCA_MAC_APP_COMMAND = [
    "/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer",
]
ORCA_WINDOWS_CANDIDATES = [
    Path(r"C:\Program Files\OrcaSlicer\OrcaSlicer.exe"),
    Path(r"C:\Program Files\OrcaSlicer\orca-slicer.exe"),
    Path(r"C:\Program Files (x86)\OrcaSlicer\OrcaSlicer.exe"),
    Path(r"C:\Program Files (x86)\OrcaSlicer\orca-slicer.exe"),
]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_ORCA_SETTINGS = [
    SCRIPT_DIR / "process_preset" / "process.json",
    SCRIPT_DIR / "printer_preset" / "p1p.json",
]
DEFAULT_ORCA_FILAMENTS = [
    SCRIPT_DIR / "filament_preset" / "pla.json",
]


def resolve_orca_command(command_text=None):
    if command_text:
        return shlex.split(command_text)

    env_command = os.environ.get("ORCA_SLICER_COMMAND")
    if env_command:
        return shlex.split(env_command)

    for candidate in ("orca-slicer", "OrcaSlicer"):
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved]

    if os.name == "nt":
        windows_roots = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
        ]
        for root in windows_roots:
            if not root:
                continue
            for exe_name in ("OrcaSlicer.exe", "orca-slicer.exe"):
                candidate = Path(root) / "OrcaSlicer" / exe_name
                if candidate.is_file():
                    return [str(candidate)]
        for candidate in ORCA_WINDOWS_CANDIDATES:
            if candidate.is_file():
                return [str(candidate)]

    if Path(ORCA_MAC_APP_COMMAND[0]).is_file():
        return ORCA_MAC_APP_COMMAND[:]

    if shutil.which("flatpak"):
        return ORCA_FLATPAK_COMMAND[:]

    raise SystemExit(
        "Could not find OrcaSlicer. Install OrcaSlicer, add it to PATH, "
        "set ORCA_SLICER_COMMAND, or pass --orca-command."
    )


class Logger:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.handle = None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.handle = self.path.open("a", encoding="utf-8")

    def close(self):
        if self.handle:
            self.handle.close()
            self.handle = None

    def print(self, message=""):
        print(message, flush=True)
        if self.handle:
            self.handle.write(f"{message}\n")
            self.handle.flush()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


def direct_dxf_files(folder):
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() == ".dxf"
    )


def direct_stl_files(folder):
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() == ".stl"
    )


def find_dxf_folders(root, recursive):
    root = root.resolve()
    if direct_dxf_files(root):
        yield root

    if not recursive:
        return

    for folder in sorted(path for path in root.rglob("*") if path.is_dir()):
        if folder.name.lower() == "stl":
            continue
        if direct_dxf_files(folder):
            yield folder


def find_stl_folders(root, recursive):
    root = root.resolve()
    if direct_stl_files(root):
        yield root

    if not recursive:
        return

    for folder in sorted(path for path in root.rglob("*") if path.is_dir()):
        if direct_stl_files(folder):
            yield folder


def convert_folder(folder, thickness, cleanup, suffix, overwrite, scale, scale_x, scale_y, scale_z):
    output_folder = folder / "stl"
    output_folder.mkdir(parents=True, exist_ok=True)

    results = []
    for input_path in direct_dxf_files(folder):
        output_path = output_folder / f"{input_path.stem}{suffix}.stl"
        if output_path.exists() and not overwrite:
            results.append((input_path, output_path, "skipped"))
            continue

        try:
            result = convert_dxf_to_stl(
                str(input_path),
                str(output_path),
                thickness,
                cleanup,
                scale,
                scale_x,
                scale_y,
                scale_z,
            )
            results.append((input_path, output_path, result))
        except Exception as exc:
            if output_path.exists() and output_path.stat().st_size <= 84:
                output_path.unlink()
            results.append((input_path, output_path, exc))

    return results


def stl_folder_for(folder, converted):
    if converted or direct_dxf_files(folder):
        return folder / "stl"
    return folder


def stl_facet_count(path):
    size = path.stat().st_size
    if size < 84:
        return 0

    with path.open("rb") as handle:
        header = handle.read(84)

    if len(header) < 84:
        return 0

    binary_count = struct.unpack("<I", header[80:84])[0]
    if size == 84 + (50 * binary_count):
        return binary_count

    if size == 84 and binary_count == 0:
        return 0

    # Non-binary-exact STL, usually ASCII. Let Orca try it unless it is tiny.
    return 1 if size > 128 else 0


def valid_stl_paths(stl_folder):
    valid = []
    invalid = []
    for path in sorted(stl_folder.glob("*.stl")):
        facets = stl_facet_count(path)
        if facets > 0:
            valid.append(path)
        else:
            invalid.append(path)
    return valid, invalid


def existing_paths(paths):
    return [path for path in paths if path.is_file()]


def export_3mf(
    folder,
    stl_paths,
    output_name,
    overwrite,
    allow_rotations,
    settings,
    filaments,
    datadir,
    orca_command,
):
    output_path = folder / output_name
    if output_path.exists() and not overwrite:
        return output_path, "skipped"

    command = orca_command[:]
    if datadir:
        command += ["--datadir", str(datadir)]
    if settings:
        command += ["--load-settings", ";".join(str(path) for path in settings)]
    if filaments:
        command += ["--load-filaments", ";".join(str(path) for path in filaments)]
    command += ["--arrange", "1", "--ensure-on-bed"]
    if allow_rotations:
        command.append("--allow-rotations")
    command += ["--export-3mf", str(output_path)]
    command += [str(path) for path in stl_paths]

    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout.strip() or "OrcaSlicer failed")

    return output_path, completed.stdout.strip()


def main():
    parser = argparse.ArgumentParser(
        description="Convert DXFs or package existing STLs into one arranged OrcaSlicer 3MF per folder."
    )
    parser.add_argument("root_folder", help="Folder to process.")
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Process every descendant folder that directly contains DXF or STL files.",
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
        default="_3mm_fixed",
        help="Suffix added to each STL filename before .stl. Default: _3mm_fixed",
    )
    parser.add_argument(
        "--project-name",
        default=None,
        help="3MF filename. Default: <folder-name>.3mf",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing STL and 3MF files.",
    )
    parser.add_argument(
        "--skip-convert",
        action="store_true",
        help="Use existing STLs and only create the arranged 3MF.",
    )
    parser.add_argument(
        "--allow-rotations",
        action="store_true",
        help="Allow OrcaSlicer to rotate models while arranging. Leave off for row/column-style orientation.",
    )
    parser.add_argument(
        "--orca-settings",
        action="append",
        default=[],
        help="OrcaSlicer process/machine settings JSON. Can be passed more than once.",
    )
    parser.add_argument(
        "--orca-filament",
        action="append",
        default=[],
        help="OrcaSlicer filament settings JSON. Can be passed more than once.",
    )
    parser.add_argument(
        "--orca-datadir",
        default=None,
        help="OrcaSlicer data directory to use for profiles/settings.",
    )
    parser.add_argument(
        "--orca-command",
        default=None,
        help=(
            "Exact OrcaSlicer command to run. Example: "
            "'/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer' on macOS."
        ),
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Write console output to this log file too. Default: <root_folder>/folders_to_3mf-<timestamp>.log",
    )
    parser.add_argument(
        "--skip-preview",
        action="store_true",
        help="Do not render a top-down PNG preview next to each generated 3MF.",
    )
    parser.add_argument(
        "--preview-size",
        type=int,
        default=1600,
        help="Maximum preview image size in pixels. Default: 1600",
    )
    parser.add_argument(
        "--grid-arrange",
        action="store_true",
        help="Rewrite the generated 3MF into a no-rotation grid layout before previewing.",
    )
    parser.add_argument(
        "--grid-spacing",
        type=float,
        default=2.0,
        help="Spacing in mm for --grid-arrange. Default: 2.0",
    )
    args = parser.parse_args()
    if not args.orca_settings:
        args.orca_settings = existing_paths(DEFAULT_ORCA_SETTINGS)
    if not args.orca_filament:
        args.orca_filament = existing_paths(DEFAULT_ORCA_FILAMENTS)
    orca_command = resolve_orca_command(args.orca_command)

    root = Path(args.root_folder)
    if not root.is_dir():
        raise SystemExit(f"Root folder does not exist: {root}")

    folders = list(find_dxf_folders(root, args.recursive))
    if not folders:
        folders = list(find_stl_folders(root, args.recursive))
    if not folders and args.skip_convert and (root / "stl").is_dir():
        folders = [root.resolve()]
    if not folders:
        raise SystemExit(f"No folders with direct DXF or STL files found under: {root}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = Path(args.log_file) if args.log_file else root / f"folders_to_3mf-{timestamp}.log"

    with Logger(log_file) as logger:
        logger.print(f"Log file: {log_file}")
        logger.print(f"Root folder: {root.resolve()}")
        logger.print(f"Folders to process: {len(folders)}")
        logger.print(f"Orca command: {shlex.join(orca_command)}")

        failures = []
        for folder in folders:
            logger.print(f"FOLDER {folder}")
            try:
                converted = False
                if direct_dxf_files(folder) and not args.skip_convert:
                    results = convert_folder(
                        folder,
                        args.thickness,
                        args.cleanup,
                        args.suffix,
                        args.overwrite,
                        args.scale,
                        args.scale_x,
                        args.scale_y,
                        args.scale_z,
                    )
                    converted = True
                    for input_path, output_path, result in results:
                        if result == "skipped":
                            logger.print(f"  SKIP {input_path.name} -> {output_path.name}")
                        elif isinstance(result, Exception):
                            logger.print(
                                f"  FAIL STL {input_path.name}: {type(result).__name__}: {result}"
                            )
                        else:
                            logger.print(
                                "  STL "
                                f"{input_path.name} -> {output_path.name} "
                                f"faces={result['faces']} "
                                f"watertight={result['watertight']} "
                                f"scale=({result['scale_x']}, {result['scale_y']}, {result['scale_z']})"
                            )

                stl_folder = stl_folder_for(folder, converted)
                stl_paths, invalid_stl_paths = valid_stl_paths(stl_folder)
                for invalid_path in invalid_stl_paths:
                    logger.print(f"  SKIP invalid STL {invalid_path.name} (empty or zero facets)")
                if not stl_paths:
                    raise RuntimeError(f"No valid STL files found in {stl_folder}")

                project_name = args.project_name or f"{folder.name}.3mf"
                output_path, status = export_3mf(
                    folder,
                    stl_paths,
                    project_name,
                    args.overwrite,
                    args.allow_rotations,
                    args.orca_settings,
                    args.orca_filament,
                    args.orca_datadir,
                    orca_command,
                )
                if status == "skipped":
                    logger.print(f"  SKIP 3MF {output_path.name}")
                else:
                    logger.print(f"  3MF {output_path.name}")

                if args.grid_arrange:
                    grid_arrange_3mf(output_path, spacing=args.grid_spacing)
                    logger.print(f"  grid arranged {output_path.name}")

                if not args.skip_preview:
                    preview_path = output_path.with_suffix(".png")
                    if preview_path.exists() and not args.overwrite:
                        logger.print(f"  SKIP preview {preview_path.name}")
                    else:
                        render_preview(output_path, preview_path, args.preview_size)
                        logger.print(f"  preview {preview_path.name}")
            except Exception as exc:
                failures.append((folder, exc))
                logger.print(f"  FAIL {type(exc).__name__}: {exc}")

        if failures:
            logger.print()
            logger.print(f"Failed folders: {len(failures)}")
            for folder, exc in failures:
                logger.print(f"  {folder}: {type(exc).__name__}: {exc}")
            raise SystemExit(1)

        logger.print("Done")


if __name__ == "__main__":
    main()
