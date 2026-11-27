# Changelog

## 2.3.0 - 2026-11-27 · Codex (ChatGPT) and Antigravity (Gemini)

- Works in **Codex**, ChatGPT's agent (the ChatGPT app for Windows, the CLI and the IDE extension):
  `npx skills add GodFaizT/makerworld-to-any --skill "*" -g -a codex -y`, then `$kobrax Vase.3mf`. Each command
  has an `agents/openai.yaml`, so Codex only runs it when you call it.
- Works in **Antigravity**, Google's agent that replaced the Gemini CLI: the repository is an Antigravity plugin
  (`plugin.json`), so `agy plugin install https://github.com/GodFaizT/makerworld-to-any`, then `/kobrax Vase.3mf`.
  The Gemini CLI works with `npx skills add ... -a gemini-cli`.
- The skill and the commands no longer assume Claude Code: they say how to load the main skill in other agents and
  where the request is when the agent doesn't fill in `$ARGUMENTS`.
- `/any-update` recognises installs for Codex, Antigravity and the Gemini CLI and gives the right command for each
  one. `npx github:GodFaizT/makerworld-to-any --agente codex|antigravity|gemini` installs for those agents.
- README: how to install and use it in each agent, and why the browser chats (claude.ai, ChatGPT, Gemini) can only
  advise.

## 2.2.0 - 2026-11-27 · reports, notes and installer in English

- The scripts' reports, warnings, notes, errors and `--help` texts are in English (`SLICED`, `WARNINGS`,
  `[designer changed]`, `ESTIMATED COST`...). Claude still answers in the language you write in.
- The technical notes (`referencia/notas.md`), this changelog and the ZIP installer (`LEIA-ME.txt`, `instalar.bat`)
  are in English too.
- Unchanged: the scripts' options and their values (`--impressora`, `--afastar`, `meus`...), the keys of the
  `--json` report and of the settings file. Requests, settings and programs made for 2.1 keep working.
- Projects adapted with an earlier version are still recognised (the end G-code comment that lifts the nozzle is
  now in English).

## 2.1.0 - 2026-11-26 · commands and instructions in English

- The commands have English names: `/any-pratos` → `/any-plates`, `/any-cores` → `/any-colors`,
  `/any-perfil` → `/any-settings`, `/any-desfazer` → `/any-undo`, `/any-diagnostico` → `/any-doctor`. `/kobrax`,
  `/anycubic` and the others stay the same. You can still ask in Portuguese, and Claude answers in the language you
  write in.
- The `SKILL.md` files (the skill and the 13 commands) are in English and start with what skills.sh shows: what it
  does, examples, printers, how to install. The instructions for Claude come below. The scripts, their options and
  the reports stay in Portuguese.
- Commands with the old names are removed by `/any-update` (ZIP and `npx github:` installs). With an `npx skills`
  install, `/any-update` says what to run to swap them: `npx skills remove` for the old ones and `npx skills add`
  again. `/any-doctor` warns if commands with the old names are still there.

## 2.0.3 - 2026-11-26 · Anycubic Slicer Next 2.0.0.7 and more security

Security (what the Snyk analysis on skills.sh pointed out):

- `/any-update` checks the SHA-256 GitHub publishes for the release ZIP before touching any folder, only accepts
  ZIPs from this repository's releases and no longer runs the new script it downloaded. If the check fails, nothing
  is changed.
- The G-code inside a project still stays out, and Claude no longer asks whether to keep it. To use your own G-code,
  save it in a printer profile in Anycubic and adapt with your profiles (`--perfis meus`). `--manter-gcode` is only
  used if you ask for it.
- Names that come from a 3MF (objects, parts) show up in the reports without line breaks or invisible characters,
  and at most 80 characters long. The skill and the commands tell Claude that what comes inside a 3MF is the model
  designer's data, never instructions.

Anycubic Slicer Next 2.0.0.7:

- Tested with Anycubic Slicer Next 2.0.0.7 (and 2.0.0.3): `/any-diagnostico` no longer warns with either.
- Correct grams per color with 2.0.0.7. This version writes, at the end of the G-code, the whole weight on the last
  color used on the plate (e.g. "0 g yellow, 34 g red" for a box that is almost all yellow). The G-code and the total
  are right. Now the skill checks that summary against what each color extrudes in the G-code and, if it doesn't
  match, redoes the split. The cost per material is right too.
- `/any-update` also recognises the `npx skills` install when it copies the folders instead of linking them (which
  it does with `-a claude-code`): it says to update with `npx skills update` and doesn't touch the folders.
- README: `npx skills` needs Git (it's in the requirements), and there's a fix for the `spawn git ENOENT` error in
  "Problems".

## 2.0.2 - 2026-11-25 · install with npx skills and a step-by-step README

- Install with `npx skills add GodFaizT/makerworld-to-any --skill "*" -g -a claude-code -y` (skills.sh). The Claude
  Code plugin, the ZIP and `npx github:` still work.
- `/any-update` recognises an install made with `npx skills` (folders linked to `~/.agents/skills`): it leaves them
  alone and says to update with `npx skills update`. Before, it failed halfway. It also never deletes a link and
  checks every folder before replacing any.
- New README, in Portuguese and English: quick start, step-by-step install (what you need, the 4 ways to install,
  how to update and remove each one), the first adaptation step by step and a problems and fixes section.

## 2.0.1 - 2026-11-25 · a project's G-code only with permission

- When changing the colors or material of an already adapted project, the G-code and machine limits inside the file
  no longer pass on their own: they run on the printer, and any file can claim to be "for your printer". The report
  warns; if you tuned them yourself, repeat with `--manter-gcode`. The rest of what you tuned (accelerations,
  speeds, temperatures...) still passes.
- A project with broken settings is no longer adapted or sliced (before, it could go ahead unchecked).
- Tests on GitHub with the new versions of the actions (`checkout` and `setup-python` v7).
- The README image shows the conversation in Claude (the request and the answer), in Portuguese and English, with
  the numbers from a real adaptation.

## 2.0.0 - 2026-11-25 · plates, per-part colors, undo and diagnostics

Already adapted projects can be worked on without going back to the original, and the skill is tested end to end.

**New commands**
- `/any-pratos`: see what's on each plate, move objects between plates, one object per plate, merge everything,
  move apart parts that touch and center.
- `/any-cores`: see the filament of each object and part, put parts in another color, add a new color, change
  colors or the material. Purging is recalculated for the new colors.
- `/any-desfazer`: restore the previous version of a file. The scripts always keep a copy before replacing a file
  (the last 30).
- `/any-diagnostico`: checks Python, Anycubic Slicer Next (and its version), profiles and settings; with `teste` it
  adapts, changes colors, arranges plates, resizes and slices an example project in under a minute.

**Better**
- Real clearance between parts, from the parts' shape and not their boxes: warns about parts less than 2 mm apart,
  and the prime tower goes to a spot that is really free.
- Purging between colors recalculated when the colors change (Anycubic's command line doesn't do it); the
  designer's stays where the colors are theirs.
- Clearer report: what the designer changed on purpose, what came from their profile, and what didn't pass and why.
- The designer's speeds never go above the printer profile's, on every printer.
- Variable layer heights: the report gives the real average height; `--sem-camadas-variaveis` ignores them. With
  organic tree supports (which Anycubic refuses with variable layer heights) the supports become hybrid tree.
- `/any-perfil` also saves the adapted-files folder, the originals folder and prices (per kg of each material and
  per machine hour): the report then includes the estimated cost of each job.
- `--gcode PASTA` saves the sliced G-code of each plate; `--json` gives the report for programs.
- `medir.py --imagem` draws the plates seen from above.
- Object names in Chinese, with emoji, etc. no longer break the scripts on Windows.
- Known Anycubic errors come with a hint of what to do.
- When changing the colors or material of an already adapted project, what you tuned by hand in Anycubic
  (accelerations, temperatures, G-code...) stays as it was.
- Post-processing scripts inside a project never pass into the adapted project and are never run.
- Color changes by layer and variable layer heights follow the parts when they change plate or size.

**For people working on the code**
- Automated tests (`python -m unittest discover -s tests -t tests`) with fake profiles, no slicer needed; the
  end-to-end tests run when Anycubic Slicer Next is installed.
- Everything needed to publish is in the repository: `tools/publica.py` (version in one place, ZIPs, release),
  `tools/gera_comandos.py`, `tools/verifica.py`, `instalador/`.
- README in English (`README.en.md`) and images generated from a real adaptation (`tools/gera_docs.py`).

## 1.6.0 - 2026-11-24
- Each material with its own profile (PLA and variants, PETG, ABS, ASA, PC, PA, TPU, fiber-filled...) and
  `--material`.
- Profile guide in the README.

## 1.5.0 - 2026-11-24
- `/any-perfil` command: default profiles and printer.

## 1.4.0 to 1.4.2 - 2026-11-24
- The user's profiles (`--perfis meus`) and an update command, later renamed `/any-update`.

## 1.3.0 - 2026-11-24
- Commands `/kobrax`, `/kobra4`, `/kobras1`, `/kobras1max`, `/kobra3`, `/kobra3max` and `/anycubic`.

## 1.2.0 - 2026-11-24
- Several Anycubic printers (all the ones Anycubic Slicer Next ships).

## 1.1.0 - 2026-11-24
- New name: MakerWorld to Any.

## 1.0.0 - 2026-11-24
- First version: Bambu Lab / MakerWorld projects for the Anycubic Kobra X.
