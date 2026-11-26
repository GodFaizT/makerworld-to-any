"""Atualiza a MakerWorld to Any (skill + comandos /kobrax, /kobras1, ...) para a ultima versao do GitHub.
Feito pela Megatic - https://megatic.pt

Uso:
    python atualizar.py              atualiza, se houver versao nova
    python atualizar.py --verificar  so diz se ha versao nova

- Instalada como plugin do Claude Code: usa `claude plugin marketplace update` + `claude plugin update`.
- Instalada com o `npx skills add` (skills.sh): as pastas em ~/.claude/skills sao ligacoes (no Windows, juncoes)
  para ~/.agents/skills, ou copias registadas em ~/.agents/.skill-lock.json, geridas pelo `npx skills`. Nao mexe
  em nada e diz para correr `npx skills update`.
- Instalada como skill (ZIP, `npx github:`, a mao): descarrega o ZIP da ultima release, confere o SHA-256 que o
  GitHub publica para ele e substitui so as pastas da skill e dos comandos que vem nele (as outras skills nao sao
  tocadas). Nunca apaga uma ligacao e nunca executa o que descarregou.
"""
import hashlib
import json
import os
import re
import shutil
import stat
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
# comandos que mudaram de nome: makerworld-update -> any-update (1.4.1); os /any-* em portugues -> ingles (2.1.0)
RENOMEADOS = {"makerworld-update": "any-update", "any-pratos": "any-plates", "any-cores": "any-colors",
              "any-perfil": "any-settings", "any-desfazer": "any-undo", "any-diagnostico": "any-doctor"}
OBSOLETAS = list(RENOMEADOS)


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


def e_ligacao(p):
    """Atalho (symlink) ou juncao do Windows. O os.path.isjunction so existe no Python 3.12+, por isso ve-se o
    atributo de reparse point (Windows) no lstat."""
    try:
        if os.path.islink(p):
            return True
        st = os.lstat(p)
    except OSError:
        return False
    return bool(getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _no_registo(caminho):
    """O ficheiro de registo do `npx skills` (.skill-lock.json / skills-lock.json) tem esta skill, vinda deste repo."""
    try:
        with open(caminho, encoding="utf-8-sig") as f:
            dados = json.load(f)
        entrada = (dados.get("skills") or {}).get("makerworld-to-any") or {}
    except (OSError, ValueError, AttributeError):
        return False
    return "makerworld-to-any" in str(entrada.get("source", "")).lower()


def em_npx_skills():
    """Instalada com `npx skills add`: a pasta da skill e uma ligacao, a pasta real esta em .agents/skills, ou foi
    copiada (o que o `npx skills` faz quando so ha um agente) e esta no registo dele."""
    if e_ligacao(SKILL):
        return True
    partes = os.path.normcase(os.path.realpath(SKILL)).replace("/", os.sep).split(os.sep)
    if any(partes[i] == ".agents" and partes[i + 1] == "skills" for i in range(len(partes) - 1)):
        return True
    casa = os.path.expanduser("~")
    if os.path.normcase(os.path.realpath(BASE)) == os.path.normcase(os.path.realpath(os.path.join(casa, ".claude", "skills"))):
        registos = [os.path.join(casa, ".agents", ".skill-lock.json")]
        if os.environ.get("XDG_STATE_HOME"):
            registos.insert(0, os.path.join(os.environ["XDG_STATE_HOME"], "skills", ".skill-lock.json"))
    else:                                          # <projeto>/.claude/skills -> <projeto>/skills-lock.json
        registos = [os.path.join(os.path.dirname(os.path.dirname(BASE)), "skills-lock.json")]
    return any(_no_registo(r) for r in registos)


def atualiza_npx_skills():
    print("Instalada com o npx skills (skills.sh): as pastas sao geridas por ele e esta atualizacao nao lhes mexe.\n"
          "Para atualizar, corre num terminal:\n"
          "  npx skills update\n"
          "Depois abre uma sessao nova do Claude Code.")
    return 0


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


def descarrega(asset, destino):
    """Descarrega o ZIP da release e confere-o: tem de vir das releases deste repositorio e ter o SHA-256 que o GitHub
    publica para esse ficheiro (o campo `digest` da API). Se algo nao bater, nada e alterado."""
    url = str(asset.get("browser_download_url") or "")
    if not url.startswith(f"https://github.com/{REPO}/releases/download/"):
        raise SystemExit(f"O ZIP da release nao vem das releases de {REPO} ({url}); atualizacao cancelada, nada foi alterado")
    m = re.fullmatch(r"sha256:([0-9a-f]{64})", str(asset.get("digest") or "").lower())
    if not m:
        raise SystemExit("O GitHub nao da o SHA-256 do ZIP desta release, por isso nao o posso conferir; atualizacao cancelada, "
                         "nada foi alterado. Alternativa: npx skills add " + REPO)
    h = hashlib.sha256()
    pedido = urllib.request.Request(url, headers={"User-Agent": CABECALHOS["User-Agent"]})
    with urllib.request.urlopen(pedido, timeout=120) as r, open(destino, "wb") as f:
        for bloco in iter(lambda: r.read(1 << 16), b""):
            h.update(bloco)
            f.write(bloco)
    if h.hexdigest() != m.group(1):
        raise SystemExit("O ZIP descarregado nao tem o SHA-256 que o GitHub publica para ele; atualizacao cancelada, nada foi alterado")


def atualiza_pastas(rel):
    asset = next((a for a in rel.get("assets", []) if re.fullmatch(r"makerworld-to-any-v[\d.]+\.zip", a["name"])), None)
    if not asset:
        raise SystemExit("A release nao tem o ZIP da skill. Usa: npx github:" + REPO)
    tmp = tempfile.mkdtemp(prefix="mw2any_atualizar_")
    try:
        zipf = os.path.join(tmp, asset["name"])
        descarrega(asset, zipf)
        ext = os.path.join(tmp, "zip")
        with zipfile.ZipFile(zipf) as z:
            for n in z.namelist():                       # nada fora da pasta de extracao
                if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/"):
                    raise SystemExit(f"ZIP com caminho estranho ({n}); atualizacao cancelada")
            z.extractall(ext)
        pastas = [d for d in os.listdir(ext) if os.path.isfile(os.path.join(ext, d, "SKILL.md"))]
        if "makerworld-to-any" not in pastas:
            raise SystemExit("O ZIP nao tem a skill makerworld-to-any; atualizacao cancelada")
        ligacoes = [d for d in pastas if e_ligacao(os.path.join(BASE, d))]
        if ligacoes:                                     # confirmar antes de mexer em qualquer pasta
            raise SystemExit("Estas pastas sao ligacoes (instaladas com o npx skills): " + ", ".join(sorted(ligacoes))
                             + ". Nada foi alterado. Atualiza com: npx skills update")
        for d in pastas:
            destino = os.path.join(BASE, d)
            if os.path.isdir(destino):
                shutil.rmtree(destino)
            shutil.copytree(os.path.join(ext, d), destino)
        return pastas
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def obsoletas_presentes():
    """Comandos com o nome antigo que ainda estao instalados ao lado da skill."""
    return [d for d in OBSOLETAS if os.path.isfile(os.path.join(BASE, d, "SKILL.md"))]


def avisa_obsoletas_npx():
    """No npx skills as pastas sao dele: so diz como trocar os comandos antigos pelos novos."""
    velhas = obsoletas_presentes()
    if velhas:
        print("Os comandos mudaram de nome (" + ", ".join(f"/{d} -> /{RENOMEADOS[d]}" for d in velhas) + ").\n"
              "Para ficares com os novos, corre num terminal:\n"
              f"  npx skills remove {' '.join(velhas)} -g -y\n"
              f'  npx skills add {REPO} --skill "*" -g -a claude-code -y')


def limpa_obsoletas():
    """Apaga comandos antigos que mudaram de nome (so se forem mesmo da MakerWorld to Any)."""
    for d in OBSOLETAS:
        sk = os.path.join(BASE, d, "SKILL.md")
        if not os.path.isfile(sk) or e_ligacao(os.path.join(BASE, d)):
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
    npx_skills = not em_plugin() and em_npx_skills()
    if not em_plugin() and not npx_skills:
        limpa_obsoletas()
    elif npx_skills:
        avisa_obsoletas_npx()
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
    if npx_skills:
        return atualiza_npx_skills()
    pastas = atualiza_pastas(rel)
    # Nada do que se descarregou e executado aqui. Os comandos antigos que so a versao nova conhece sao apagados quando
    # ela correr (limpa_obsoletas no inicio do main).
    print(f"Atualizado para a {remota}: {', '.join(sorted(pastas))} em {BASE}")
    print("Abre uma sessao nova do Claude Code para usar a versao nova.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
