# Technical notes (Anycubic Slicer Next 2.0.0.3 and 2.0.0.7, command line)

MakerWorld to Any - Megatic (https://megatic.pt).

The scripts already handle everything marked (auto). After an Anycubic Slicer Next update, run
`diagnostico.py --teste`: if it passes, these notes still hold.

## Anycubic's command line

- Export a project: `AnycubicSlicerNext.exe --arrange 0 --load-settings "maquina.json;processo.json"
  --load-filaments "f1.json;f2.json" --export-3mf saida.3mf --outputdir <folder> <entrada.3mf|.stl>`.
  Slice: `--slice 0 --outputdir <folder> <projeto.3mf>` (every plate -> `plate_N.gcode`).
- Paths must be Windows paths (`C:\...`); in bash, `cygpath -w`. A `/c/...` inside the `;` list gives
  "can not find setting file" (code 127).
- It writes the printer's certificates/keys (files with hexadecimal names) in the working folder -> run it in a
  temporary folder (auto).
- **Crashes** (segfault) with non-empty plate names (`plater_name`), even ASCII ones (auto: they are left empty).
- **Crashes** with a mesh that is half below z=0. Bambu stores centered meshes (z -h/2..h/2): this only matters if
  the mesh is extracted to STL; from the original 3MF it doesn't happen.
- A loose STL only loads if it is roughly between 60 and 125 mm, whatever the bed (at the origin, or from ~150 mm
  up, it gives "Loading of a model file failed") -> the reference cube is always 100 mm (auto).
- It centers the plates on the target printer's bed (Kobra X: +2,+2 from a 256 bed; +40 from the A1 mini's 180).
  Plates are spaced at bed x 1.2 (Kobra X 312, S1 300, Kobra 3 306, 3 Max 511.2 x 504); columns = round up of
  sqrt(n); rows grow towards negative y. The assemble view is visual only.
- It writes `different_settings_to_system` wrong; it must be `[process, "" per filament..., "machine_end_gcode"]`
  (auto).
- With fewer filament files than the project had, it only replaces the first ones and leaves the rest as Bambu
  profiles (wrong temperatures, High Flow at 220 C...) -> cut every per-filament list (auto). `*_group` lists are
  [process, filaments..., printer].
- With **more** filament files than the project had, it extends every list (good), but everything that pointed to a
  filament the input didn't have yet goes back to filament 1 -> each object's/part's filament is written again after
  exporting (auto). In `model_settings` the object's filament is always written and the part's only when it differs.
- In Bambu 2.x, the profile's `wall_filament`/`sparse_infill_filament`/`solid_infill_filament` default to 1 (= the
  object's filament): they don't count as "used" (auto).
- It turns off the prime tower (`enable_prime_tower` 0) even with 2 colors; the profiles with an ACE have 1 (auto,
  plus a free position per plate). Footprint measured on a Kobra X: x from X-6 to X+width+1, y from Y-7.5 to Y+20
  with 2 colors.
- The parts' `matrix` in `model_settings` comes out "doubled" (scale 1.21 for 1.1): harmless, the G-code is right.
- Normalization differences that always show up (internal_solid_infill_pattern rectilinear, wall_direction ccw,
  ironing_angle 0) come from Anycubic itself.
- Known errors get a hint at the end of the message (`anycubic.DICAS_CLI`); the `calc_exclude_triangles` lines in
  the log are noise.
- It **refuses** any project with a non-empty `post_process` ("normative_check: postprocess not supported"), both
  when exporting and when slicing: in other words, the command line never runs those scripts. `adaptar.py` removes
  them from the input copy and from the final project (auto) and the report says they didn't pass; `fatia()` slices
  a copy without them when an already adapted project has them. The skill never writes `post_process` into a
  project.
- **2.0.0.7**: the summary at the end of the G-code (`; filament used [g] = 0.00, 34.07`) puts all the weight on the
  last filament used on the plate; the total and the G-code are right. `resumo_gcode()` adds up the E of each tool
  (relative extrusion, `M83`) and, when the summary doesn't match that, splits the total by the mass each one
  extrudes.

## Purging between colors

- The command line **never recalculates** `flush_volumes_matrix`: it inherits the original's (a 1-filament project
  keeps 16 "280" values even after it gets 2). A k x k matrix is always written (auto): the designer's values where
  the two colors didn't change, and recalculated ones where they changed or where the filament is new.
- Calculation in `purga.py`: it is Bambu Studio's formula (color difference in HSV + luminance) plus the printer
  profile's `nozzle_volume` (Kobra X 79, Bambu A1 92). Checked against a real project: it reproduces the values
  saved by Bambu Studio to the mm3. Going to a lighter color purges much more (white -> dark blue 204, the reverse
  604 on the Kobra X). Maximum 800.
- The printer multiplies by `flush_multiplier` (0.7 on the Kobra X): the report shows the mm3 before multiplying.

## Plates, gaps and tower

- `model_settings.config`: one `<plate>` block per plate with `plater_id`, `plater_name`, thumbnails and one
  `<model_instance>` (object_id, instance_id, identify_id) per object. `pratos.py` rewrites the blocks, removes the
  thumbnails of the plates that changed and deletes the ones left empty.
- `custom_gcode_per_layer.xml`: one `<plate>` block per plate (`<plate_info id="N"/>`) with the color changes and
  pauses by layer (`<layer top_z="..." .../>`). They apply to the whole plate. `pratos.py` carries them with the
  parts (and warns when a plate ends up with parts from different plates), `separar_pratos.py` keeps only those of
  the plates that stay, and `escalar.py` multiplies `top_z` when every part on the plate changes size.
- An object's plate is just its position (the center of its box divided by the step between plates); the slicer
  confirms it through the `<plate>` block.
- Real gap: `distancias.py` draws each part's footprint (projection of the triangles, 0.25 mm cells) and measures
  the distance between footprints. Boxes are misleading (a diagonal bar "takes up" the whole plate). It warns below
  2 mm. Needs numpy; without it there is only the warning for overlapping boxes.
- The prime tower goes in the free spot closest to the center (using the real footprints) and is checked in the
  G-code.

## Printers

- Machines: `%APPDATA%\AnycubicSlicerNext\system\Anycubic\machine\*.json`, named `Anycubic <model> <nozzle> nozzle`;
  processes and filaments are called `<name> @<machine>` (or have the machine in `compatible_printers`) (auto).
- Bed: `printable_area` + `printable_height` (Kobra 1/2/2 Neo/2 Pro 220; Kobra 3 255; S1 250; Kobra X and 4 260;
  1 Plus 300; 2 Plus 320; S1 Max 350; 1 Max 400; 2 Max 426; 3 Max 426 x 420 x 501).
- ACE (several colors): the machines with `change_filament_gcode` (Kobra X, 4, 3, 3 V2, 3 Max, S1, S1 Max). The
  Kobra 1 and 2 don't have it: the project goes on a single filament and the report gives the designer's colors per
  object.
- Stock print end that doesn't lift the nozzle: Kobra X, Kobra 4, S1 Max -> the lift is added (auto). S1, Kobra 3
  and Kobra 1/2 already lift and are left as they are.
- Speeds: the designer's were meant for their printer; on any printer only those lower than the profile's pass
  (auto). Exception: `ironing_speed`, which is part of the designer's ironing recipe (with the flow and the spacing)
  and passes as it is.
- Filaments vary a lot between printers (Kobra 1 only has Generic PLA/PETG/ABS; Kobra 2 Neo only Anycubic
  PLA/PETG): the closest one is used, Anycubic first, then Generic (auto).
- Slicer version: `%APPDATA%\AnycubicSlicerNext\AnycubicSlicerNext.conf`, key `app.version` (the diagnostics only
  read that key; the rest of the file has account data).

## The user's profiles

- They live in `%APPDATA%\AnycubicSlicerNext\user\<account>\{machine,process,filament}\*.json` (plus an `.info`):
  only the differences, with `"inherits": "<system profile>"` and `"from": "User"`.
- When passing a user profile to the command line, the (already resolved) JSON must keep `inherits` = the base system
  profile; with an empty `inherits` the CLI refuses with "process not compatible with printer" (only when exporting
  an STL, the reference cube) (auto).
- `different_settings_to_system` includes the user's changes relative to the system profile (auto).
- A project that is already for this printer (changing colors or material of an adapted one): what is in
  `different_settings_to_system` ([process, filament 1..n, printer]) belongs to the user and all of it passes,
  without the filters used for originals (accelerations, speeds above the profile, temperatures) - except
  `post_process`, which never passes, and the G-code and `machine_max_*`, which run on the printer and stay the
  printer's (any file can claim to be "for this printer"). The user's G-code comes from their profiles
  (`--perfis meus`), which only they can create; `--manter-gcode` exists for someone who explicitly asks to keep the
  one from a project of their own. The print end the skill itself adds doesn't count: it is added again.

## Profiles

- System profiles: `%APPDATA%\AnycubicSlicerNext\system\Anycubic\{machine,process,filament}\*.json` with inheritance
  through `inherits` (auto).
- Kobra X 0.20mm Standard ~ Bambu A1 0.20mm Standard (2 walls, 15 % grid, tree(auto) at 30 degrees). The Anycubic
  profiles come with supports off and on the build plate only.
- The designer changes settings relative to their base profile -> use the printer's profile with the **same name as
  the base profile** and their layer height as a change (auto). E.g. an "optimised" profile at 0.12 made on top of
  0.20 Standard.
- The report separates: `[designer changed]` (it is in the project's list of changes), `[designer's profile value]`
  (an "intent" setting that differs from Anycubic's profile) and `[skill fix]`; and what didn't pass: because it
  belongs to the designer's printer, because it doesn't exist in Anycubic, or because it is a speed above the
  profile.
- Tree support styles: default, tree_slim, tree_strong, tree_hybrid. Bambu's `tree_organic` value doesn't exist,
  but with tree supports `default` **is** the organic tree (that's what the slicer says when validating) -> the
  designer's `tree_organic` becomes `default` (auto). Bambu's `zig-zag` -> `zigzag` (auto). Painted fuzzy skin
  (`paint_fuzzy_skin`) is supported.
- Print end: where the stock one switches off with the nozzle resting on the part (string/blob on top) -> lifts
  5 mm and goes to the corner (bed - 10 mm) (auto).

## Variable layer heights

- `Metadata/layer_heights_profile.txt`: one line per object, `object_id=N|z;height;z;height;...`. N is the object's
  **position** in the project (1, 2, ...), not its id in the 3MF. They override `layer_height` (in Bambu too): a
  "0.12" profile with the designer's variable profile at 0.2 prints at 0.2.
- The first layer of the variable profile must have the print profile's first layer height; otherwise the slicer
  throws the variable profile away without warning.
- The report gives the real average height (height / number of layers in the G-code) when it differs by more than
  20 % from the profile's. `--sem-camadas-variaveis` removes the file (auto) and the profile's height applies.
- With organic tree supports Anycubic refuses to slice ("Variable layer height is not supported with Organic
  supports") -> the supports become hybrid tree and the report says so (auto).
- `escalar.py` multiplies the z values of the variable profile (the heights stay) of the objects that change size;
  `separar_pratos.py` renumbers the lines (the position changes when objects leave).

## Settings and backups

- `%APPDATA%\makerworld-to-any\config.json` (elsewhere: `MAKERWORLD_TO_ANY_CONFIG`): `perfis`, `impressora`,
  `saida`, `originais`, `precos` ({material: EUR/kg}), `preco_hora`. Outside the skill folder, so it survives
  updates. Read with or without a BOM (Notepad may add one). If it is broken there is a warning and, before it is
  overwritten, a copy `config.json.estragado` is kept.
- Before replacing a file, the scripts save it in `%APPDATA%\makerworld-to-any\copias\` (the last 30, with
  `indice.json`). `desfazer.py` restores it; the restored file is saved too.

## Parts with text (manual work)

- **OpenSCAD pendants/ornaments** (MakerLab or the designer's OpenSCAD): the text is a flat extrusion. To change the
  name: slice the mesh in 2D (e.g. manifold3d), find the font and size of the original text, generate the new text
  with the same font and the same `offset`, extrude it and replace the mesh of the text part in the original 3MF, and
  only then run `adaptar.py`.
- Dots on i/j and accents are often loose (floating parts): join them to the stem itself with a ~1 mm "neck" (and
  check it doesn't join the next letter), or lower the accent until it touches the letter.
- Parts that spin (a ring inside a frame): check at several heights that the ring with the text is one part and the
  frame another, so it keeps spinning.
- Names written without accents: ask whether they have one (Ines or Inês).
