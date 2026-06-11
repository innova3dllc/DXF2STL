find dxf -type f -iname '*.dxf' -printf '%h\n' | sort -u | while read -r folder; do
  rel="${folder#dxf/}"
  out="stl/$rel"
  mkdir -p "$out"

  python3 batch_convert_dxf_to_stl.py "$folder" "$out" \
    --thickness 4 \
    --scale-x 2 \
    --scale-y 2 \
    --suffix _60x140mmx4mm \
    --overwrite

  python3 folders_to_3mf.py "$out" \
    --skip-convert \
    --overwrite \
    --orca-settings process_preset/process.json \
    --orca-settings printer_preset/p1p.json \
    --orca-filament filament_preset/pla.json \
    --log-file "$out/grid-arrange-check.log"
done
