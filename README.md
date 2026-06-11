# DXF Converter

Utilities for converting DXF outlines into extruded STL files, then optionally packing those STLs into OrcaSlicer 3MF projects with previews.

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
