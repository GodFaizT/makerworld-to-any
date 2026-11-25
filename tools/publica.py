"""Prepara e publica uma versao da MakerWorld to Any.

    python tools/publica.py 2.1.0         prepara: escreve a versao nos 4 sitios, gera os comandos, verifica o
                                          repositorio, corre os testes e constroi os ZIPs em dist/
    python tools/publica.py               o mesmo, sem mudar a versao
    python tools/publica.py --zips        so constroi os ZIPs
    python tools/publica.py --publicar    publica a versao atual: envia o ramo e cria a release no GitHub com os ZIPs
                                          (precisa do `gh` autenticado e de estar tudo em commits)

Passos de uma versao nova:
    1. acrescentar a seccao "## X.Y.Z - AAAA-MM-DD · titulo curto" ao CHANGELOG.md
    2. python tools/publica.py X.Y.Z
    3. git add -A && git commit -m "vX.Y.Z: ..."
    4. python tools/publica.py --publicar

ZIPs:
    dist/makerworld-to-any-vX.Y.Z.zip    cada pasta de skills/ na raiz + instalar.bat + LEIA-ME.txt (e o que o
                                         /any-update descarrega)
    dist/makerworld-to-any-skill.zip     so a pasta makerworld-to-any/ (para carregar no claude.ai)
"""
import json
import os
import re
import subprocess
import sys
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gera_comandos  # noqa: E402
import verifica  # noqa: E402

SKILLS = os.path.join(RAIZ, "skills")
DIST = os.path.join(RAIZ, "dist")
PRINCIPAL = "makerworld-to-any"
FIXA = (2026, 1, 1, 0, 0, 0)      # data dos ficheiros dentro dos ZIPs: o mesmo conteudo da o mesmo ZIP


def corre(args, **kw):
    print("  $", " ".join(args))
    return subprocess.run(args, cwd=RAIZ, **kw)


def le(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8", newline="") as f:
        return f.read()


def escreve(rel, texto):
    with open(os.path.join(RAIZ, rel), "w", encoding="utf-8", newline="") as f:
        f.write(texto)


def poe_versao(v):
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        raise SystemExit(f"Versao '{v}': usa o formato X.Y.Z")
    for rel in ("package.json", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
        t = le(rel)
        novo, n = re.subn(r'("version"\s*:\s*")[^"]*(")', lambda m: m.group(1) + v + m.group(2), t)
        if n != 1:
            raise SystemExit(f'{rel}: esperava um "version", encontrei {n}')
        json.loads(novo)
        escreve(rel, novo)
    escreve(f"skills/{PRINCIPAL}/VERSION", v + "\n")
    print(f"versao {v} escrita em package.json, plugin.json, marketplace.json e VERSION")


def versao():
    vs = verifica.versoes()
    if len(set(vs.values())) != 1:
        raise SystemExit("A versao nao e igual em todo o lado: " + ", ".join(f"{k}={x}" for k, x in vs.items()))
    return vs[f"skills/{PRINCIPAL}/VERSION"]


def _junta(z, nome, dados):
    info = zipfile.ZipInfo(nome, FIXA)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    z.writestr(info, dados)


def _pasta(z, pasta, prefixo):
    for base, dirs, fs in os.walk(pasta):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for f in sorted(fs):
            if f.endswith((".pyc", ".local.txt")):
                continue
            caminho = os.path.join(base, f)
            with open(caminho, "rb") as fh:
                dados = fh.read()
            if not f.lower().endswith((".png", ".jpg")):
                dados = dados.replace(b"\r\n", b"\n")          # LF, venha a copia de trabalho como vier
            _junta(z, prefixo + os.path.relpath(caminho, pasta).replace("\\", "/"), dados)


def constroi(mostra=True):
    v = versao()
    os.makedirs(DIST, exist_ok=True)
    for velho in os.listdir(DIST):
        if velho.endswith(".zip"):
            os.remove(os.path.join(DIST, velho))
    pastas = sorted(d for d in os.listdir(SKILLS) if os.path.isfile(os.path.join(SKILLS, d, "SKILL.md")))
    completo = os.path.join(DIST, f"{PRINCIPAL}-v{v}.zip")
    with zipfile.ZipFile(completo, "w", zipfile.ZIP_DEFLATED) as z:
        for d in pastas:
            _pasta(z, os.path.join(SKILLS, d), d + "/")
        for nome in ("instalar.bat", "LEIA-ME.txt"):       # CRLF: abrem-se com duplo clique / Bloco de notas no Windows
            t = le("instalador/" + nome).replace("\r\n", "\n").replace("\n", "\r\n")
            _junta(z, nome, t.encode("cp1252" if nome.endswith(".bat") else "utf-8"))
    so_skill = os.path.join(DIST, f"{PRINCIPAL}-skill.zip")
    with zipfile.ZipFile(so_skill, "w", zipfile.ZIP_DEFLATED) as z:
        _pasta(z, os.path.join(SKILLS, PRINCIPAL), PRINCIPAL + "/")
    confere(completo, so_skill, v, pastas)
    for f in (completo, so_skill) if mostra else ():
        print(f"  {os.path.relpath(f, RAIZ)}  ({os.path.getsize(f) / 1024:.0f} KB)")
    return completo, so_skill


def confere(completo, so_skill, v, pastas):
    """Os ZIPs tem o que o instalador, o /any-update e o claude.ai esperam."""
    padroes = verifica.GENERICOS + verifica.padroes_privados()
    with zipfile.ZipFile(completo) as z:
        nomes = set(z.namelist())
        for d in pastas:
            if f"{d}/SKILL.md" not in nomes:
                raise SystemExit(f"ZIP: falta {d}/SKILL.md")
        if z.read(f"{PRINCIPAL}/VERSION").decode().strip() != v:
            raise SystemExit("ZIP: a VERSION nao e a desta versao")
        for nome in ("instalar.bat", "LEIA-ME.txt"):
            if nome not in nomes:
                raise SystemExit(f"ZIP: falta {nome}")
            t = z.read(nome)
            if b"\r\n" not in t or b"\n" in t.replace(b"\r\n", b""):
                raise SystemExit(f"ZIP: {nome} tem de ter fins de linha CRLF")
        if any(n.startswith(("/", "\\")) or ".." in n.split("/") or "__pycache__" in n for n in nomes):
            raise SystemExit("ZIP: caminhos estranhos")
        maus = []
        for n in sorted(nomes):
            if n.lower().endswith((".png", ".jpg")):
                continue
            maus += verifica.dados_pessoais(n, z.read(n).decode("utf-8", errors="replace"), padroes)
        if maus:
            raise SystemExit("ZIP com dados pessoais:\n  " + "\n  ".join(maus))
    with zipfile.ZipFile(so_skill) as z:
        if not all(n.startswith(PRINCIPAL + "/") for n in z.namelist()) or f"{PRINCIPAL}/SKILL.md" not in z.namelist():
            raise SystemExit("ZIP da skill: so pode ter a pasta makerworld-to-any/")


def notas(v):
    """A seccao desta versao do CHANGELOG.md (para o texto da release)."""
    m = re.search(r"^## %s\b[^\n]*\n(.*?)(?=^## |\Z)" % re.escape(v), le("CHANGELOG.md"), re.M | re.S)
    if not m:
        raise SystemExit(f"CHANGELOG.md nao tem a seccao '## {v}'")
    return m.group(1).strip() + "\n"


def titulo(v):
    """'vX.Y.Z — <o que vem depois de "·" no titulo da seccao do CHANGELOG>'"""
    m = re.search(r"^## %s\b[^\n]*?(?:·\s*([^\n]+))?$" % re.escape(v), le("CHANGELOG.md"), re.M)
    extra = (m.group(1) or "").strip() if m else ""
    return f"v{v}" + (f" — {extra}" if extra else "")


def prepara(nova):
    if nova:
        poe_versao(nova)
    v = versao()
    print(f"== MakerWorld to Any {v}")
    print("comandos:")
    gera_comandos.main()
    print("verificacao:")
    ps = verifica.problemas()
    for p in ps:
        print("  PROBLEMA:", p)
    if ps:
        raise SystemExit(f"{len(ps)} problema(s): corrige antes de publicar")
    print("  tudo bem")
    print("testes:")
    r = corre([sys.executable, "-W", "error::ResourceWarning", "-m", "unittest", "discover", "-s", "tests", "-t", "tests"])
    if r.returncode != 0:
        raise SystemExit("Os testes falharam")
    print("ZIPs:")
    constroi()
    print(f"\nPronto para o commit. Depois: python tools/publica.py --publicar   (release '{titulo(v)}')")


def publica():
    v = versao()
    ps = verifica.problemas()
    if ps:
        raise SystemExit("Verificacao falhou:\n  " + "\n  ".join(ps))
    sujo = subprocess.run(["git", "status", "--porcelain"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    if sujo:
        raise SystemExit("Ha alteracoes por guardar em commits:\n" + sujo)
    existe = subprocess.run(["gh", "release", "view", f"v{v}"], cwd=RAIZ, capture_output=True, text=True)
    if existe.returncode == 0:
        raise SystemExit(f"A release v{v} ja existe (sobe a versao com: python tools/publica.py X.Y.Z)")
    completo, so_skill = constroi()
    ramo = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    if corre(["git", "push", "origin", ramo]).returncode != 0:
        raise SystemExit("O git push falhou")
    ficheiro_notas = os.path.join(DIST, "notas.md")
    with open(ficheiro_notas, "w", encoding="utf-8", newline="\n") as f:
        f.write(notas(v))
    r = corre(["gh", "release", "create", f"v{v}", completo, so_skill, "--target", ramo, "--title", titulo(v), "--notes-file", ficheiro_notas])
    if r.returncode != 0:
        raise SystemExit("O gh release create falhou")
    print(f"Publicada a v{v}.")


def main():
    args = [a for a in sys.argv[1:]]
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    if "--publicar" in args:
        publica()
    elif "--zips" in args:
        constroi()
    else:
        prepara(next((a for a in args if not a.startswith("-")), None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
