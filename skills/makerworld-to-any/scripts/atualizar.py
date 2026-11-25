"""Atualiza a MakerWorld to Any (skill + comandos /kobrax, /kobras1, ...) para a ultima versao do GitHub.
Feito pela Megatic - https://megatic.pt

Uso:
    python atualizar.py              atualiza, se houver versao nova
    python atualizar.py --verificar  so diz se ha versao nova

- Instalada como plugin do Claude Code: usa `claude plugin marketplace update` + `claude plugin update`.
- Instalada como skill (npx, ZIP, a mao): descarrega o ZIP da ultima release e substitui so as pastas da skill e
  dos comandos que vem nele (as outras skills nao sao tocadas).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

for _f in (sys.stdout, sys.stderr):      # as novidades da release podem ter caracteres fora do cp1252
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

REPO = "GodFaizT/makerworld-to-any"
PLUGIN = "makerworld-to-any@makerworld-to-any"
AQUI = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(AQUI)              # .../makerworld-to-any
BASE = os.path.dirname(SKILL)              # pasta das skills (ou skills/ do plugin)
CABECALHOS = {"User-Agent": "makerworld-to-any-atualizar", "Accept": "application/vnd.github+json"}
OBSOLETAS = ["makerworld-update"]   # comandos que mudaram de nome (makerworld-update -> any-update na 1.4.1)


def versao_local():
    try:
        with open(os.path.join(SKILL, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0"


def tupla(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def ultima_release():
    pedido = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest", headers=CABECALHOS)
    with urllib.request.urlopen(pedido, timeout=30) as r:
        return json.load(r)


def novidades(rel, linhas=14):
    corpo = [l for l in (rel.get("body") or "").splitlines() if l.strip()]
    return "\n".join("  " + l for l in corpo[:linhas]) + ("\n  ..." if len(corpo) > linhas else "")


def em_plugin():
    partes = os.path.normcase(SKILL).replace("/", os.sep).split(os.sep)
    return any(partes[i] == ".claude" and partes[i + 1] == "plugins" for i in range(len(partes) - 1))


def atualiza_plugin():
    claude = shutil.which("claude")
    if not claude:
        print("Instalada como plugin. Dentro do Claude Code corre:\n"
              "  /plugin marketplace update makerworld-to-any\n"
              f"  /plugin update {PLUGIN}")
        return 1
    for args in (["plugin", "marketplace", "update", "makerworld-to-any"], ["plugin", "update", PLUGIN]):
        r = subprocess.run([claude] + args, capture_output=True, text=True, errors="ignore")
        print(((r.stdout or "") + (r.stderr or "")).strip())
        if r.returncode != 0:
            return r.returncode
    print("Plugin atualizado. Abre uma sessao nova do Claude Code para usar a versao nova.")
    return 0


def atualiza_pastas(rel):
    asset = next((a for a in rel.get("assets", []) if re.fullmatch(r"makerworld-to-any-v[\d.]+\.zip", a["name"])), None)
    if not asset:
        raise SystemExit("A release nao tem o ZIP da skill. Usa: npx github:" + REPO)
    tmp = tempfile.mkdtemp(prefix="mw2any_atualizar_")
    try:
        zipf = os.path.join(tmp, asset["name"])
        pedido = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": CABECALHOS["User-Agent"]})
        with urllib.request.urlopen(pedido, timeout=120) as r, open(zipf, "wb") as f:
            shutil.copyfileobj(r, f)
        ext = os.path.join(tmp, "zip")
        with zipfile.ZipFile(zipf) as z:
            for n in z.namelist():                       # nada fora da pasta de extracao
                if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/"):
                    raise SystemExit(f"ZIP com caminho estranho ({n}); atualizacao cancelada")
            z.extractall(ext)
        pastas = [d for d in os.listdir(ext) if os.path.isfile(os.path.join(ext, d, "SKILL.md"))]
        if "makerworld-to-any" not in pastas:
            raise SystemExit("O ZIP nao tem a skill makerworld-to-any; atualizacao cancelada")
        for d in pastas:
            destino = os.path.join(BASE, d)
            if os.path.isdir(destino):
                shutil.rmtree(destino)
            shutil.copytree(os.path.join(ext, d), destino)
        return pastas
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def limpa_obsoletas():
    """Apaga comandos antigos que mudaram de nome (so se forem mesmo da MakerWorld to Any)."""
    for d in OBSOLETAS:
        sk = os.path.join(BASE, d, "SKILL.md")
        if not os.path.isfile(sk):
            continue
        with open(sk, encoding="utf-8", errors="ignore") as f:
            nosso = "MakerWorld to Any" in f.read()
        if nosso:
            shutil.rmtree(os.path.join(BASE, d))
            print(f"Removido o comando antigo /{d}")


def main():
    if "--limpar" in sys.argv:
        limpa_obsoletas()
        return 0
    if not em_plugin():
        limpa_obsoletas()
    so_ver = "--verificar" in sys.argv
    local = versao_local()
    try:
        rel = ultima_release()
    except Exception as e:  # sem internet, limite do GitHub...
        raise SystemExit(f"Nao consegui ver a ultima versao no GitHub ({e}). Alternativa: npx github:{REPO}")
    remota = rel.get("tag_name", "").lstrip("v")
    print(f"MakerWorld to Any (Megatic) - instalada: {local} | ultima: {remota}")
    if tupla(remota) <= tupla(local):
        print("Ja tens a ultima versao.")
        return 0
    print("Novidades:\n" + novidades(rel))
    if so_ver:
        return 0
    if em_plugin():
        return atualiza_plugin()
    pastas = atualiza_pastas(rel)
    # a versao nova pode saber de mais comandos antigos para apagar: corre a limpeza dela
    novo = os.path.join(BASE, "makerworld-to-any", "scripts", "atualizar.py")
    if os.path.isfile(novo):
        subprocess.run([sys.executable, novo, "--limpar"])
    print(f"Atualizado para a {remota}: {', '.join(sorted(pastas))} em {BASE}")
    print("Abre uma sessao nova do Claude Code para usar a versao nova.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
