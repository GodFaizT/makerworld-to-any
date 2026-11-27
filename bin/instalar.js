#!/usr/bin/env node
// Instala (ou remove) a skill makerworld-to-any no Claude Code.
//
//   npx github:GodFaizT/makerworld-to-any              -> ~/.claude/skills/makerworld-to-any
//   npx github:GodFaizT/makerworld-to-any --projeto    -> ./.claude/skills/makerworld-to-any
//   npx github:GodFaizT/makerworld-to-any --desinstalar
//   ... --destino <pasta>   instala noutra pasta de skills
//   ... --verificar         so verifica Python e Anycubic Slicer Next
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const NOME = "makerworld-to-any";
const ORIGEM = path.join(__dirname, "..", "skills", NOME);
const args = process.argv.slice(2);
const tem = (f) => args.includes(f);
const valor = (f) => {
  const i = args.indexOf(f);
  return i >= 0 ? args[i + 1] : undefined;
};

const cor = (c, t) => (process.stdout.isTTY ? `\x1b[${c}m${t}\x1b[0m` : t);
const ok = (t) => console.log(cor("32", "  ✔ ") + t);
const aviso = (t) => console.log(cor("33", "  ! ") + t);
const erro = (t) => console.log(cor("31", "  ✖ ") + t);

if (tem("--ajuda") || tem("-h") || tem("--help")) {
  console.log(`
  ${NOME} — Claude Code skill: Bambu Lab / MakerWorld projects -> Anycubic printers

  npx github:GodFaizT/${NOME}               installs for all projects (~/.claude/skills)
  npx github:GodFaizT/${NOME} --projeto     installs in this project only (./.claude/skills)
  npx github:GodFaizT/${NOME} --destino D   installs in the skills folder D
  npx github:GodFaizT/${NOME} --desinstalar removes it
  npx github:GodFaizT/${NOME} --verificar   only checks Python and Anycubic Slicer Next
`);
  process.exit(0);
}

function pastaSkills() {
  if (valor("--destino")) return path.resolve(valor("--destino"));
  if (tem("--projeto")) return path.join(process.cwd(), ".claude", "skills");
  return path.join(os.homedir(), ".claude", "skills");
}

function verificar() {
  let tudoBem = true;
  const py = ["python", "py", "python3"].find((c) => {
    const r = spawnSync(c, c === "py" ? ["-3", "--version"] : ["--version"], { encoding: "utf8" });
    return r.status === 0 && /Python 3/.test((r.stdout || "") + (r.stderr || ""));
  });
  if (py) ok(`Python 3 found (${py})`);
  else {
    tudoBem = false;
    aviso("Python 3 not found — install it from https://www.python.org/downloads/ (tick 'Add to PATH')");
  }
  const slicer = process.env.ANYCUBIC_SLICER || "C:\\Program Files\\AnycubicSlicerNext\\AnycubicSlicerNext.exe";
  if (fs.existsSync(slicer)) ok("Anycubic Slicer Next found");
  else {
    tudoBem = false;
    aviso(`Anycubic Slicer Next not found in ${slicer}` +
      (process.platform === "win32" ? "" : " (the skill was made for Windows)") +
      " — install it or set ANYCUBIC_SLICER to the path of the executable");
  }
  return tudoBem;
}

console.log(cor("1", `\n  ${NOME}`) + cor("2", "  ·  made by Megatic — https://megatic.pt") + "\n");

if (tem("--verificar")) {
  if (!fs.existsSync(path.join(ORIGEM, "SKILL.md"))) {
    erro("Missing skills/" + NOME + "/SKILL.md");
    process.exit(1);
  }
  ok("Package complete");
  verificar();
  process.exit(0);
}

// skill principal + comandos (/kobrax, /kobras1, ... /anycubic): cada pasta de skills/ e uma skill
const PASTAS = fs.readdirSync(path.join(__dirname, "..", "skills"), { withFileTypes: true })
  .filter((d) => d.isDirectory() && fs.existsSync(path.join(__dirname, "..", "skills", d.name, "SKILL.md")))
  .map((d) => d.name);
const base = pastaSkills();
// comandos que mudaram de nome: makerworld-update -> any-update (1.4.1); os /any-* em portugues -> ingles (2.1.0)
const OBSOLETAS = ["makerworld-update", "any-pratos", "any-cores", "any-perfil", "any-desfazer", "any-diagnostico"];

if (tem("--desinstalar")) {
  for (const p of PASTAS) {
    const d = path.join(base, p);
    if (fs.existsSync(d)) {
      fs.rmSync(d, { recursive: true, force: true });
      ok(`Removed ${d}`);
    }
  }
  process.exit(0);
}

for (const p of OBSOLETAS) {
  const d = path.join(base, p);
  const sk = path.join(d, "SKILL.md");
  if (fs.existsSync(sk) && fs.readFileSync(sk, "utf8").includes("MakerWorld to Any")) fs.rmSync(d, { recursive: true, force: true });
}

try {
  fs.mkdirSync(base, { recursive: true });
  for (const p of PASTAS) {
    const d = path.join(base, p);
    if (fs.existsSync(d)) fs.rmSync(d, { recursive: true, force: true });
    fs.cpSync(path.join(__dirname, "..", "skills", p), d, {
      recursive: true,
      filter: (src) => !/__pycache__|\.pyc$/.test(src),
    });
  }
  ok(`Skill installed in ${path.join(base, NOME)}`);
  const cmds = PASTAS.filter((p) => p !== NOME).map((p) => "/" + p);
  if (cmds.length) ok(`Commands: ${cmds.join(" ")}`);
} catch (e) {
  erro(`Copy failed: ${e.message}`);
  process.exit(1);
}
verificar();
console.log(`
  Open a new Claude Code session and use, for example:
    ${cor("36", '/kobrax "C:\\...\\model.3mf"')}
    ${cor("36", '/kobras1 "C:\\...\\model.3mf" 10 cm tall')}
    ${cor("36", '/anycubic Kobra 2 Neo "C:\\...\\model.3mf"')}
    ${cor("36", "/any-doctor test")}   checks that everything works
  or just ask ${cor("36", '"adapt this file for the kobra x: ..."')}.
`);
