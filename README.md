# DXF Converter

Utilities for converting DXF outlines into extruded STL files, then optionally packing those STLs into OrcaSlicer 3MF projects with previews.

## Dependencies

### Core Python Requirements

The active DXF-to-STL path uses Python 3 plus these packages:

- `ezdxf`
- `manifold3d`
- `trimesh`

Install them with:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install ezdxf manifold3d trimesh
```

Platform-specific examples:

#### Windows

```powershell
py -3 -m venv .venv
.venv\Scripts\activate
py -3 -m pip install --upgrade pip
py -3 -m pip install ezdxf manifold3d trimesh
```

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install ezdxf manifold3d trimesh
```

### 3MF Workflow Requirements

`folders_to_3mf.py` shells out to the OrcaSlicer CLI.

The script tries OrcaSlicer in this order:

- `orca-slicer` on `PATH`
- `OrcaSlicer` on `PATH`
- common Windows install paths under `C:\Program Files\OrcaSlicer\`
- `/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer`
- Linux Flatpak via `flatpak run --command=orca-slicer com.orcaslicer.OrcaSlicer`

If OrcaSlicer is installed in a nonstandard location, you can override the command with either:

Windows PowerShell:

```powershell
$env:ORCA_SLICER_COMMAND="C:\path\to\OrcaSlicer.exe"
```

macOS / Linux:

```bash
export ORCA_SLICER_COMMAND="/path/to/OrcaSlicer"
```

Or pass it directly on the command line:

```bash
python3 folders_to_3mf.py dxf/1 --orca-command "/path/to/OrcaSlicer"
```

#### Windows

Typical installer location:

```text
C:\Program Files\OrcaSlicer\OrcaSlicer.exe
```

Some installs may use:

```text
C:\Program Files\OrcaSlicer\orca-slicer.exe
```

If OrcaSlicer is not on `PATH`, run the 3MF workflow with:

```powershell
py -3 folders_to_3mf.py dxf\1 --orca-command "C:\Program Files\OrcaSlicer\OrcaSlicer.exe"
```

#### macOS

Typical `.app` location:

```bash
/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer
```

The script auto-detects that location. You can verify the CLI is reachable with:

```bash
"/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer" --help
```

#### Linux

Common approaches:

- `orca-slicer` on `PATH`
- AppImage started from the folder where you downloaded it
- Flatpak:

```bash
flatpak run --command=orca-slicer com.orcaslicer.OrcaSlicer
```

If you use Flatpak, install it with:

```bash
flatpak install flathub com.orcaslicer.OrcaSlicer
```

If you use an AppImage, a common pattern is:

```bash
chmod +x OrcaSlicer_*.AppImage
./OrcaSlicer_*.AppImage --help
```

In that case, pass the AppImage path explicitly:

```bash
python3 folders_to_3mf.py dxf/1 --orca-command "/path/to/OrcaSlicer_2.x.x.AppImage"
```

### Running the Project

#### Windows

DXF to STL:

```powershell
py -3 batch_convert_dxf_to_stl.py dxf\5
```

DXF folder to 3MF:

```powershell
py -3 folders_to_3mf.py dxf\1 --orca-command "C:\Program Files\OrcaSlicer\OrcaSlicer.exe"
```

#### macOS

DXF to STL:

```bash
python3 batch_convert_dxf_to_stl.py dxf/5
```

DXF folder to 3MF:

```bash
python3 folders_to_3mf.py dxf/1
```

#### Linux

DXF to STL:

```bash
python3 batch_convert_dxf_to_stl.py dxf/5
```

DXF folder to 3MF with Flatpak:

```bash
python3 folders_to_3mf.py dxf/1
```

DXF folder to 3MF with AppImage:

```bash
python3 folders_to_3mf.py dxf/1 --orca-command "/path/to/OrcaSlicer_2.x.x.AppImage"
```

### Optional Script-Specific Dependencies

These are only needed for the older or standalone helper scripts:

- `convert_dxf_splines_to_stl.py`: `shapely`
- `repair_stl_pymeshlab.py`: `pymeshlab`
- `convert_dxf_to_stl.py`: FreeCAD with Python modules `FreeCAD`, `Mesh`, `Part`, and `importDXF`

Install the optional Python packages with:

```bash
python3 -m pip install shapely pymeshlab
```

The FreeCAD-based converter is separate from the active workflow and usually requires a FreeCAD installation provided by your OS package manager or the official FreeCAD distribution, not `pip`.

### Quick Install Summary

If you only want the current supported conversion path, install:

```bash
python3 -m pip install ezdxf manifold3d trimesh
```

If you also want 3MF export, install the core Python packages above and install OrcaSlicer in a location the script can detect, or pass `--orca-command`.

## Active Conversion Path

The current batch DXF-to-STL path is:

- `batch_convert_dxf_to_stl.py` - command-line batch entry point for a single folder of DXFs.
- `convert_dxf_manifold_to_stl.py` - actual DXF-to-STL converter used by the batch script and 3MF workflow.

The broader folder-to-3MF workflow is:

- `folders_to_3mf.py` - converts DXFs, exports one 3MF per folder with OrcaSlicer, and writes a log.
- `grid_arrange_3mf.py` - optional no-rotation grid layout pass.
- `render_3mf_plate_preview.py` - optional top-down PNG preview renderer.

Older/alternate standalone converters are still present, but are not used by the current batch path:

- `convert_dxf_to_stl.py` - FreeCAD-based converter.
- `convert_dxf_splines_to_stl.py` - alternate spline/Shapely converter.
- `repair_stl_pymeshlab.py` - standalone STL repair helper.

## DXF to STL

Convert all DXFs directly inside one folder into that folder's `stl` subfolder:

```bash
python3 batch_convert_dxf_to_stl.py dxf/5
```

Convert a folder into a separate output folder, matching the earlier `stl_batch` style:

```bash
python3 batch_convert_dxf_to_stl.py dxf/1 stl_batch --suffix _3mm_fixed
```

Overwrite existing STL files:

```bash
python3 batch_convert_dxf_to_stl.py dxf/1 stl_batch --suffix _3mm_fixed --overwrite
```

Use a different extrusion thickness or cleanup offset:

```bash
python3 batch_convert_dxf_to_stl.py dxf/5 --thickness 3 --cleanup 0.0005
```

Scale the generated STLs uniformly:

```bash
python3 batch_convert_dxf_to_stl.py dxf/5 --scale 1.02 --suffix _scaled --overwrite
```

Scale only one or two axes:

```bash
python3 batch_convert_dxf_to_stl.py dxf/5 --scale-x 1.02 --scale-y 0.98 --suffix _xy_scaled --overwrite
```

Scale Z separately from the DXF outline. This keeps the X/Y footprint unchanged and makes the extrusion thicker:

```bash
python3 batch_convert_dxf_to_stl.py dxf/5 --thickness 3 --scale-z 1.25 --suffix _taller --overwrite
```

Convert inch-based DXF coordinates to millimeters by scaling all axes by `25.4`:

```bash
python3 batch_convert_dxf_to_stl.py dxf/5 --scale 25.4 --suffix _mm --overwrite
```

Convert one DXF directly with the underlying converter:

```bash
python3 convert_dxf_manifold_to_stl.py dxf/5/64.dxf stl/64_3mm_fixed.stl 3 0.0005
```

Convert one DXF directly with scaling:

```bash
python3 convert_dxf_manifold_to_stl.py dxf/5/64.dxf stl/64_scaled.stl 3 0.0005 --scale 1.02
```

## DXF Folders to 3MF

Create one arranged OrcaSlicer 3MF for a single folder:

```bash
python3 folders_to_3mf.py dxf/1
```

Process every descendant folder that directly contains DXFs, like the earlier `dxf/110-145` run:

```bash
python3 folders_to_3mf.py dxf/110-145 --recursive --skip-preview
```

Process every descendant folder and bake a scale into the converted STLs before 3MF export:

```bash
python3 folders_to_3mf.py dxf/110-145 --recursive --scale 1.02 --overwrite --skip-preview
```

Use existing STLs in `<folder>/stl` and only create the 3MF:

```bash
python3 folders_to_3mf.py dxf/1 --skip-convert --overwrite
```

Package an STL-only folder directly, such as STLs generated under the root `stl` output tree:

```bash
python3 folders_to_3mf.py stl/1 --overwrite
```

Package every STL-only folder under the root `stl` output tree:

```bash
python3 folders_to_3mf.py stl --recursive --overwrite
```

Use the saved printer/process/filament presets:

```bash
python3 folders_to_3mf.py dxf/1 \
  --skip-convert \
  --overwrite \
  --orca-settings process_preset/process.json \
  --orca-settings printer_preset/p1p.json \
  --orca-filament filament_preset/pla.json \
  --log-file dxf/1/p1p-profile-final-check.log
```

If no Orca preset flags are passed, `folders_to_3mf.py` automatically loads the repo presets from `printer_preset`, `process_preset`, and `filament_preset`. These portable presets target the built-in Bambu P1P, 0.20mm Standard, and Bambu PLA Basic profiles, so they do not depend on files from `$HOME`.

Create a 3MF, rewrite it into a no-rotation grid layout, and render a preview:

```bash
python3 folders_to_3mf.py dxf/1 \
  --skip-convert \
  --overwrite \
  --grid-arrange \
  --grid-spacing 2 \
  --log-file dxf/1/grid-arrange-check.log
```

The 3MF workflow calls OrcaSlicer through Flatpak:

```bash
flatpak run --command=orca-slicer com.orcaslicer.OrcaSlicer
```

## Standalone 3MF Helpers

Grid-arrange an existing 3MF in place:

```bash
python3 grid_arrange_3mf.py dxf/1/1.3mf --spacing 2
```

Render a PNG preview for an existing 3MF:

```bash
python3 render_3mf_plate_preview.py dxf/1/1.3mf dxf/1/1.png --size 1600
```

## Output Notes

- `batch_convert_dxf_to_stl.py` only scans DXF files directly inside the input folder; it ignores subdirectories.
- By default, `batch_convert_dxf_to_stl.py` writes STLs to `<input_folder>/stl`.
- By default, `folders_to_3mf.py` adds `_3mm_fixed` before each STL extension.
- `folders_to_3mf.py` writes logs as `folders_to_3mf-<timestamp>.log` unless `--log-file` is provided.
- Existing STLs and 3MFs are skipped unless `--overwrite` is passed.
- `--scale` is a uniform multiplier applied to X, Y, and Z.
- `--scale-x`, `--scale-y`, and `--scale-z` are additional per-axis multipliers. For example, `--scale 25.4 --scale-z 0.5` makes final Z scale `12.7`.
