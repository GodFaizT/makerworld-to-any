"""Verificacoes do repositorio antes de publicar (tambem correm no CI do GitHub e no tools/publica.py).

    python tools/verifica.py

- a versao e a mesma nos 4 sitios (package.json, plugin.json, marketplace.json, VERSION) e tem entrada no CHANGELOG;
- os comandos de skills/ correspondem ao que tools/gera_comandos.py gera;
- os scripts da skill tem sintaxe valida para Python 3.8+ e cada SKILL.md tem o cabecalho certo;
- nao ha dados pessoais (caminhos de utilizadores, emails) nem projetos (.3mf, .gcode) nos ficheiros a publicar;
- fins de linha LF (so os .bat sao CRLF).

Padroes privados de quem publica (nomes de clientes, pastas...) ficam em tools/privado.local.txt, um por linha
(expressoes regulares, sem distinguir maiusculas). Esse ficheiro nunca vai para o repositorio (.gitignore).
"""
import ast
import io
import json
import os
import re
import subprocess
import sys
import tokenize

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gera_comandos  # noqa: E402

BINARIOS = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".woff", ".woff2", ".ttf")
PROIBIDOS = (".3mf", ".gcode", ".stl", ".step", ".zip")
GENERICOS = [
    (re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+(?!\.\.\.|<|%|Public\b|utilizador\b|nome\b)[^\\/\s\"'<>|)]+", re.I),
     "caminho da pasta de um utilizador do Windows"),
    (re.compile(r"/(?:home|Users)/(?!\.\.\.|<|utilizador\b|user\b|runner\b)[A-Za-z0-9_.-]+/"), "caminho de uma pasta pessoal"),
    (re.compile(r"[\w.+-]+@(?!users\.noreply\.github\.com\b|anthropic\.com\b|example\.(?:com|org)\b)[\w-]+(?:\.[\w-]+)+"),
     "endereco de email"),
]


def le(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8", newline="") as f:
        return f.read()


def ficheiros():
    """O que `git add -A` publicaria: ficheiros seguidos e novos nao ignorados."""
    try:
        r = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0 and r.stdout.strip():
            return sorted(x for x in r.stdout.splitlines() if x and os.path.isfile(os.path.join(RAIZ, x)))
    except OSError:
        pass
    out = []
    for base, dirs, fs in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "dist", "__pycache__")]
        out += [os.path.relpath(os.path.join(base, f), RAIZ).replace("\\", "/") for f in fs]
    return sorted(out)


def versoes():
    return {
        "package.json": json.loads(le("package.json")).get("version"),
        ".claude-plugin/plugin.json": json.loads(le(".claude-plugin/plugin.json")).get("version"),
        ".claude-plugin/marketplace.json": json.loads(le(".claude-plugin/marketplace.json"))["plugins"][0].get("version"),
        "skills/makerworld-to-any/VERSION": le("skills/makerworld-to-any/VERSION").strip(),
    }


def padroes_privados():
    p = os.path.join(RAIZ, "tools", "privado.local.txt")
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [(re.compile(l.strip(), re.I), "padrao privado") for l in f if l.strip() and not l.startswith("#")]


def fstrings_novos(texto):
    """Linhas com f-strings que so funcionam no Python 3.12+: aspas iguais as de fora, ou uma barra invertida, dentro
    de uma expressao. (O ast.parse com feature_version nao os apanha: no 3.12 passaram a ser sintaxe valida.)"""
    if sys.version_info < (3, 12):
        return []                        # num Python mais antigo ja sao erro de sintaxe (apanhado no ast.parse)
    linhas, pilha, prof = [], [], []
    for tok in tokenize.generate_tokens(io.StringIO(texto).readline):
        nome = tokenize.tok_name[tok.type]
        if nome == "FSTRING_START":
            aspas = tok.string.lstrip("rRfFbBuU")
            if pilha and prof[-1] > 0 and aspas[0] == pilha[-1][0] and (len(pilha[-1]) == 1 or len(aspas) == 3):
                linhas.append(tok.start[0])
            pilha.append(aspas)
            prof.append(0)
        elif nome == "FSTRING_END":
            pilha.pop()
            prof.pop()
        elif pilha:
            if nome == "OP" and tok.string in "{}":
                prof[-1] += 1 if tok.string == "{" else -1
            elif prof[-1] > 0 and nome == "STRING":
                s = tok.string.lstrip("rRbBuU")
                tripla = s[:3] in ('"""', "'''")
                if (s[0] == pilha[-1][0] and (len(pilha[-1]) == 1 or tripla)) or "\\" in tok.string:
                    linhas.append(tok.start[0])
    return linhas


def dados_pessoais(nome, texto, padroes):
    out = []
    for n, linha in enumerate(texto.splitlines(), 1):
        for rx, que in padroes:
            m = rx.search(linha)
            if m:
                out.append(f"{nome}:{n}: {que}: {m.group(0)[:60]}")
    return out


def problemas():
    out = []
    vs = versoes()
    if len(set(vs.values())) != 1:
        out.append("a versao nao e igual em todo o lado: " + ", ".join(f"{k}={v}" for k, v in vs.items()))
    versao = vs["skills/makerworld-to-any/VERSION"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", versao or ""):
        out.append(f"versao '{versao}' nao tem o formato X.Y.Z")
    try:
        if not re.search(r"^## %s\b" % re.escape(versao), le("CHANGELOG.md"), re.M):
            out.append(f"CHANGELOG.md nao tem a seccao '## {versao}'")
    except OSError:
        out.append("falta o CHANGELOG.md")

    mudados, estranhos = gera_comandos.diferencas()
    out += [f"skills/{c}/SKILL.md nao corresponde ao gerado (python tools/gera_comandos.py)" for c in mudados]
    out += [f"skills/{d}: pasta que tools/gera_comandos.py nao conhece" for d in estranhos]

    padroes = GENERICOS + padroes_privados()
    for rel in ficheiros():
        baixo = rel.lower()
        if baixo.endswith(PROIBIDOS):
            out.append(f"{rel}: este tipo de ficheiro nao deve ir para o repositorio")
            continue
        if baixo.endswith(BINARIOS):
            continue
        try:
            t = le(rel)
        except UnicodeDecodeError:
            out.append(f"{rel}: nao e texto UTF-8")
            continue
        if "\r\n" in t and not baixo.endswith(".bat"):
            out.append(f"{rel}: tem fins de linha CRLF (o repositorio usa LF)")
        out += dados_pessoais(rel, t, padroes)
        out += dados_pessoais(rel, rel, padroes)[:1]
        if baixo.endswith(".py"):
            try:
                if rel.startswith("skills/"):
                    ast.parse(t, rel, feature_version=(3, 8))      # a skill corre com o Python de quem a instala
                    out += [f"{rel}:{n}: f-string que so funciona no Python 3.12 ou mais novo" for n in fstrings_novos(t)]
                else:
                    ast.parse(t, rel)
            except SyntaxError as e:
                out.append(f"{rel}:{e.lineno}: erro de sintaxe: {e.msg}")
        if rel.startswith("skills/") and rel.endswith("/SKILL.md"):
            pasta = rel.split("/")[1]
            m = re.match(r"---\n(.*?)\n---\n", t, re.S)
            if not m:
                out.append(f"{rel}: falta o cabecalho ---")
                continue
            nome = re.search(r"^name:\s*(.+)$", m.group(1), re.M)
            desc = re.search(r"^description:\s*(.+)$", m.group(1), re.M)
            if not nome or nome.group(1).strip().strip('"') != pasta:
                out.append(f"{rel}: 'name' tem de ser '{pasta}'")
            if not desc:
                out.append(f"{rel}: falta 'description'")
            elif len(desc.group(1).strip().strip('"')) > 1024:
                out.append(f"{rel}: 'description' com mais de 1024 caracteres")
    return out


def main():
    ps = problemas()
    for p in ps:
        print("PROBLEMA:", p)
    print(f"verificacao: {'tudo bem' if not ps else str(len(ps)) + ' problema(s)'} (versao {versoes()['skills/makerworld-to-any/VERSION']}, "
          f"{len(ficheiros())} ficheiros" + (", com padroes privados" if padroes_privados() else "") + ")")
    return 1 if ps else 0


if __name__ == "__main__":
    sys.exit(main())
