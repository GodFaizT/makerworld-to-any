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
  ${NOME} — skill do Claude Code: projetos Bambu Lab / MakerWorld -> impressoras Anycubic

  npx github:GodFaizT/${NOME}               instala para todos os projetos (~/.claude/skills)
  npx github:GodFaizT/${NOME} --projeto     instala so neste projeto (./.claude/skills)
  npx github:GodFaizT/${NOME} --destino D   instala na pasta de skills D
  npx github:GodFaizT/${NOME} --desinstalar remove
  npx github:GodFaizT/${NOME} --verificar   so verifica Python e Anycubic Slicer Next
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
  if (py) ok(`Python 3 encontrado (${py})`);
  else {
    tudoBem = false;
    aviso("Nao encontrei o Python 3 — instala-o em https://www.python.org/downloads/ (marca 'Add to PATH')");
  }
  const slicer = process.env.ANYCUBIC_SLICER || "C:\\Program Files\\AnycubicSlicerNext\\AnycubicSlicerNext.exe";
  if (fs.existsSync(slicer)) ok("Anycubic Slicer Next encontrado");
  else {
    tudoBem = false;
    aviso(`Nao encontrei o Anycubic Slicer Next em ${slicer}` +
      (process.platform === "win32" ? "" : " (a skill foi feita para Windows)") +
      " — instala-o ou define ANYCUBIC_SLICER com o caminho do executavel");
  }
  return tudoBem;
}

console.log(cor("1", `\n  ${NOME}`) + cor("2", "  ·  feito pela Megatic — https://megatic.pt") + "\n");

if (tem("--verificar")) {
  if (!fs.existsSync(path.join(ORIGEM, "SKILL.md"))) {
    erro("Falta skills/" + NOME + "/SKILL.md");
    process.exit(1);
  }
  ok("Pacote completo");
  verificar();
  process.exit(0);
}

const destino = path.join(pastaSkills(), NOME);

if (tem("--desinstalar")) {
  if (fs.existsSync(destino)) {
    fs.rmSync(destino, { recursive: true, force: true });
    ok(`Removida de ${destino}`);
  } else aviso(`Nao estava instalada em ${destino}`);
  process.exit(0);
}

try {
  if (fs.existsSync(destino)) fs.rmSync(destino, { recursive: true, force: true });
  fs.mkdirSync(path.dirname(destino), { recursive: true });
  fs.cpSync(ORIGEM, destino, {
    recursive: true,
    filter: (src) => !/__pycache__|\.pyc$/.test(src),
  });
  ok(`Skill instalada em ${destino}`);
} catch (e) {
  erro(`Falhou a copia: ${e.message}`);
  process.exit(1);
}
verificar();
console.log(`
  Abre uma sessao nova do Claude Code e pede, por exemplo:
    ${cor("36", '"adapta este ficheiro para a kobra x: C:\\...\\modelo.3mf"')}
  ou chama ${cor("36", "/" + NOME)}.
`);
