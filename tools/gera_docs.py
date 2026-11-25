r"""Gera as imagens do README a partir de uma adaptacao REAL do projeto de exemplo (precisa do Anycubic Slicer Next).

    python tools/gera_docs.py

    docs/demo.svg      a conversa no Claude: o pedido /kobrax e a resposta, em portugues
    docs/demo.en.svg   a mesma conversa em ingles (README.en.md)
    docs/pratos.png    os pratos vistos de cima (medir.py --fatiar --imagem), com a torre de purga

A resposta e montada aqui a partir do relatorio (--json) de uma adaptacao verdadeira, como a skill manda o Claude
responder: os numeros (tempo, gramas, cores, custo...) sao os reais. Corre tudo numa pasta temporaria, com
preferencias isoladas (so com precos de exemplo, para aparecer o custo). Os caminhos da pasta temporaria sao trocados
por C:\Modelos, para as imagens nao levarem caminhos de quem as gera.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape

for _f in (sys.stdout, sys.stderr):      # acentos e travessoes tambem quando a saida vai para um ficheiro ou pipe
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(RAIZ, "skills", "makerworld-to-any", "scripts")
DOCS = os.path.join(RAIZ, "docs")
PASTA_FALSA = r"C:\Modelos"
PEDIDO = r'/kobrax "C:\Modelos\Exemplo.3mf"'

# ---- aspeto de uma conversa na app (tema escuro). Sem logotipos: so a disposicao e as cores neutras.
FUNDO, BARRA, BOLHA, CAIXA, LINHA = "#262624", "#1f1e1d", "#3a3936", "#30302e", "#45443f"
TEXTO, SUAVE, FRACO, CODIGO, ACENTO, VERDE = "#ece9e1", "#b7b3a8", "#8c897f", "#e6dccb", "#c96f4e", "#7cc48a"
SERIFA = "Georgia, 'Times New Roman', serif"
SANS = "'Segoe UI', -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif"
MONO = "'Cascadia Code', Consolas, 'SF Mono', Menlo, 'DejaVu Sans Mono', monospace"
LARGURA, MARGEM = 900, 56

TEXTOS = {
    "pt": {
        "titulo": "Claude Code",
        "alt": "Conversa no Claude: /kobrax com o projeto de exemplo e a resposta, com perfil, cores na ACE, tempo, gramas e custo",
        "enchimento": "enchimento {d} em {p}",
        "skill": "Skill", "comando": "Bash",
        "pronto": "Pronto: ficou em ",
        "para": "para a {imp}.",
        "perfil": "Perfil {p} da Anycubic, com o que o autor mudou: {mud}.",
        "nao_passou": "A velocidade da {coisa} que o autor usava ({a} mm/s) ficou nos {b} do perfil da Kobra X.",
        "ace": "Cores na ACE:",
        "ranhura": "ranhura {n}",
        "pratos": "Pratos", "prato": "Prato",
        "troca": "{n} troca de cor", "trocas": "{n} trocas de cor",
        "custo": "Custo estimado: {t} € (filamento {f} + máquina {m}).",
        "sem_avisos": "Sem avisos: pode ir para a impressora.",
        "avisos": "Avisos:",
        "responder": "Responder…",
        "decimal": ",",
        "mud": {"enable_support": "suportes ligados", "sparse_infill_density": "enchimento {v}",
                "sparse_infill_pattern": "em {v}", "wall_loops": "{v} paredes", "layer_height": "camada de {v} mm",
                "ironing_type": "ironing ({v})", "brim_type": "brim ({v})"},
        "padrao": {"gyroid": "giroide", "grid": "grelha", "honeycomb": "favo de mel", "cubic": "cúbico",
                   "zigzag": "ziguezague", "rectilinear": "linhas", "line": "linhas"},
        "coisas": {"outer_wall_speed": "parede exterior", "inner_wall_speed": "parede interior",
                   "sparse_infill_speed": "enchimento", "travel_speed": "deslocação"},
        "cores": {"#FFFFFF": "branco", "#000000": "preto", "#808080": "cinzento", "#D32F2F": "vermelho",
                  "#F5C542": "amarelo", "#1E88E5": "azul", "#232C7C": "azul escuro", "#2E7D32": "verde",
                  "#F57C00": "laranja", "#800020": "bordô", "#F48FB1": "rosa", "#7B1FA2": "roxo", "#E8DBB7": "bege",
                  "#8B4513": "castanho", "#D4AF37": "dourado"},
    },
    "en": {
        "titulo": "Claude Code",
        "alt": "Conversation in Claude: /kobrax with the example project and the answer, with profile, ACE colours, time, grams and cost",
        "enchimento": "{d} {p} infill",
        "skill": "Skill", "comando": "Bash",
        "pronto": "Done: it's in ",
        "para": "for the {imp}.",
        "perfil": "Anycubic's {p} profile, with what the designer changed: {mud}.",
        "nao_passou": "The designer's {coisa} speed ({a} mm/s) stayed at the Kobra X profile's {b}.",
        "ace": "Colours in the ACE:",
        "ranhura": "slot {n}",
        "pratos": "Plates", "prato": "Plate",
        "troca": "{n} colour change", "trocas": "{n} colour changes",
        "custo": "Estimated cost: €{t} (filament {f} + machine {m}).",
        "sem_avisos": "No warnings: ready for the printer.",
        "avisos": "Warnings:",
        "responder": "Reply…",
        "decimal": ".",
        "mud": {"enable_support": "supports on", "sparse_infill_density": "{v} infill",
                "sparse_infill_pattern": "{v}", "wall_loops": "{v} walls", "layer_height": "{v} mm layers",
                "ironing_type": "ironing ({v})", "brim_type": "brim ({v})"},
        "padrao": {"gyroid": "gyroid", "grid": "grid", "honeycomb": "honeycomb", "cubic": "cubic",
                   "zigzag": "zig-zag", "rectilinear": "rectilinear", "line": "lines"},
        "coisas": {"outer_wall_speed": "outer wall", "inner_wall_speed": "inner wall",
                   "sparse_infill_speed": "infill", "travel_speed": "travel"},
        "cores": {"#FFFFFF": "white", "#000000": "black", "#808080": "grey", "#D32F2F": "red",
                  "#F5C542": "yellow", "#1E88E5": "blue", "#232C7C": "navy", "#2E7D32": "green",
                  "#F57C00": "orange", "#800020": "burgundy", "#F48FB1": "pink", "#7B1FA2": "purple", "#E8DBB7": "beige",
                  "#8B4513": "brown", "#D4AF37": "gold"},
    },
}


def corre(amb, script, *args):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)] + list(args), capture_output=True, env=amb)
    saida = (r.stdout + r.stderr).decode("utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"{script} falhou:\n{saida}")
    return r.stdout.decode("utf-8", errors="replace")


def nome_cor(hexa, t):
    """Nome da cor mais proxima (para escrever "amarelo" em vez de #F2C94C)."""
    def rgb(h):
        h = h.lstrip("#")[:6]
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    alvo = rgb(hexa)
    return min(t["cores"].items(), key=lambda kv: sum((a - b) ** 2 for a, b in zip(rgb(kv[0]), alvo)))[1]


def num(v, t, casas=2):
    return f"{v:.{casas}f}".replace(".", t["decimal"])


def resposta(rel, t):
    """Linhas da resposta, como a skill manda responder: [(tipo, conteudo)]."""
    ada = rel["adaptado"]
    linhas = [("para", [(t["pronto"], "texto"), (ada["caminho"], "codigo"), (" " + t["para"].format(imp=ada["impressora"]), "texto")])]
    vals = {m["chave"]: str(m["para"][0] if isinstance(m["para"], list) else m["para"]) for m in rel["mudancas"]}
    if t["decimal"] == ",":
        vals = {k: v.replace("%", " %") for k, v in vals.items()}
    if "sparse_infill_pattern" in vals:
        vals["sparse_infill_pattern"] = t["padrao"].get(vals["sparse_infill_pattern"], vals["sparse_infill_pattern"])
    mud = []
    for m in rel["mudancas"]:
        k = m["chave"]
        if k == "sparse_infill_pattern" and "sparse_infill_density" in vals:
            continue                                  # vai junto com a densidade
        if k == "sparse_infill_density" and "sparse_infill_pattern" in vals:
            mud.append(t["enchimento"].format(d=vals[k], p=vals["sparse_infill_pattern"]))
        elif k in t["mud"]:
            mud.append(t["mud"][k].format(v=vals[k]))
    texto_mud = ", ".join(mud)
    linhas.append(("para", [(t["perfil"].format(p=ada["processo"].split(" @")[0], mud=texto_mud), "texto")]))
    for v in rel["nao_passou"]["velocidades"]:
        m = re.match(r"(\S+) ([\d.]+) > ([\d.]+)", v)
        if m and m.group(1) in t["coisas"]:
            linhas.append(("para", [(t["nao_passou"].format(coisa=t["coisas"][m.group(1)], a=m.group(2), b=m.group(3)), "suave")]))
    linhas.append(("titulo", t["ace"]))
    for f in rel["filamentos"]:
        linhas.append(("cor", (f["cor"], t["ranhura"].format(n=f["n"]), f"{nome_cor(f['cor'], t)} · {f['perfil'].split(' @')[0]} ({f['cor']})")))
    linhas.append(("titulo", t["pratos"]))
    for p in rel["pratos"]:
        trocas = (t["troca"] if p["trocas"] == 1 else t["trocas"]).format(n=p["trocas"]) if p["trocas"] else ""
        objetos = ", ".join(dict.fromkeys(o["nome"] for o in p["objetos"]))
        linhas.append(("prato", (f"{t['prato']} {p['n']} · {objetos}", p["tempo"], f"{num(p['total_g'], t)} g", trocas)))
    c = rel.get("custo")
    if c:
        linhas.append(("para", [(t["custo"].format(t=num(c["total"], t), f=num(c["filamento"], t), m=num(c["maquina"], t)), "texto")]))
    if rel["avisos"]:
        linhas.append(("titulo", t["avisos"]))
        linhas += [("para", [("• " + a, "texto")]) for a in rel["avisos"]]
    else:
        linhas.append(("ok", t["sem_avisos"]))
    return linhas


def conversa(rel, t, comando):
    """SVG de uma conversa no Claude: pedido do utilizador, a skill e o comando (fechados) e a resposta."""
    s, y = [], 40
    conteudo = LARGURA - 2 * MARGEM

    def texto(x, y, runs, tam=15.5, fonte=SERIFA, ancora="start"):
        partes = []
        for txt, estilo in runs:
            cor, fam, peso = {"texto": (TEXTO, fonte, "400"), "suave": (SUAVE, fonte, "400"), "forte": (TEXTO, fonte, "700"),
                              "codigo": (CODIGO, MONO, "400")}[estilo]
            tam_r = tam - 1.5 if estilo == "codigo" else tam
            partes.append(f'<tspan fill="{cor}" font-family="{fam}" font-weight="{peso}" font-size="{tam_r}">'
                          f'{escape(txt).replace("  ", " &#160;")}</tspan>')
        return f'<text x="{x}" y="{y}" text-anchor="{ancora}">' + "".join(partes) + "</text>"

    # pedido do utilizador (bolha a direita)
    y += 34
    larg = int(len(PEDIDO) * 14 * 0.61) + 36
    s.append(f'<rect x="{LARGURA - MARGEM - larg}" y="{y}" width="{larg}" height="44" rx="14" fill="{BOLHA}"/>')
    s.append(texto(LARGURA - MARGEM - 18, y + 27, [(PEDIDO, "codigo")], tam=15.5, ancora="end"))
    y += 44 + 26
    # a skill e o comando, fechados como a app os mostra
    for etiqueta, detalhe in ((t["skill"], "makerworld-to-any"), (t["comando"], comando)):
        s.append(f'<rect x="{MARGEM}" y="{y}" width="{conteudo}" height="34" rx="9" fill="{CAIXA}" stroke="{LINHA}"/>')
        s.append(f'<path d="M{MARGEM + 16} {y + 12} l5 5 l-5 5" fill="none" stroke="{FRACO}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>')
        s.append(f'<text x="{MARGEM + 32}" y="{y + 22}" font-family="{SANS}" font-size="13" fill="{SUAVE}" font-weight="600">{escape(etiqueta)}</text>')
        s.append(f'<text x="{MARGEM + 32 + 9 * len(etiqueta) + 12}" y="{y + 22}" font-family="{MONO}" font-size="12.5" fill="{FRACO}">{escape(detalhe)}</text>')
        y += 34 + 10
    y += 22
    def quebra(runs, largura, tam=15.5):
        """Parte um paragrafo (lista de (texto, estilo)) em linhas que cabem na largura (estimativa larga)."""
        linhas, atual, w = [], [], 0.0
        for txt, estilo in runs:
            for k, palavra in enumerate(re.split(r"(?<= )", txt)):
                if not palavra:
                    continue
                pw = len(palavra) * (tam - 1.5) * 0.61 if estilo == "codigo" else len(palavra) * tam * 0.5
                if atual and w + pw > largura and palavra.strip():
                    linhas.append(atual)
                    atual, w = [], 0.0
                    palavra = palavra.lstrip()
                atual.append((palavra, estilo))
                w += pw
        if atual:
            linhas.append(atual)
        return linhas

    # resposta
    anterior = None
    for tipo, c in resposta(rel, t):
        if tipo == "para":
            y += 38 if anterior == "prato" else 26
            for n, linha in enumerate(quebra(c, conteudo)):
                if n:
                    y += 24
                s.append(texto(MARGEM, y, linha))
            y += 8
        elif tipo == "titulo":
            y += 34
            s.append(texto(MARGEM, y, [(c, "forte")]))
            y += 4
        elif tipo == "cor":
            hexa, ranhura, desc = c
            y += 27
            s.append(f'<circle cx="{MARGEM + 9}" cy="{y - 5}" r="7.5" fill="{hexa[:7]}" stroke="#ffffff33"/>')
            s.append(texto(MARGEM + 26, y, [(ranhura, "forte"), ("  " + desc, "texto")]))
        elif tipo == "prato":
            nome, tempo, gramas, trocas = c
            y += 27
            s.append(texto(MARGEM, y, [(nome, "texto")]))
            s.append(texto(MARGEM + 300, y, [(tempo, "texto")], fonte=SERIFA))
            s.append(texto(MARGEM + 440, y, [(gramas, "texto")]))
            s.append(texto(MARGEM + 540, y, [(trocas, "suave")]))
        elif tipo == "ok":
            y += 34
            s.append(f'<circle cx="{MARGEM + 9}" cy="{y - 5}" r="8" fill="none" stroke="{VERDE}" stroke-width="1.8"/>')
            s.append(f'<path d="M{MARGEM + 5} {y - 5} l3 3 l5 -6" fill="none" stroke="{VERDE}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')
            s.append(texto(MARGEM + 26, y, [(c, "texto")]))
        anterior = tipo
    # caixa de escrever
    y += 40
    s.append(f'<rect x="{MARGEM - 16}" y="{y}" width="{conteudo + 32}" height="52" rx="16" fill="{CAIXA}" stroke="{LINHA}"/>')
    s.append(f'<text x="{MARGEM + 4}" y="{y + 31}" font-family="{SANS}" font-size="14.5" fill="{FRACO}">{escape(t["responder"])}</text>')
    s.append(f'<circle cx="{MARGEM + conteudo - 6}" cy="{y + 26}" r="15" fill="{ACENTO}"/>')
    s.append(f'<path d="M{MARGEM + conteudo - 6} {y + 33} v-14 m-6 6 l6 -6 l6 6" fill="none" stroke="#ffffff" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round"/>')
    altura = y + 52 + 26
    cab = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{altura}" viewBox="0 0 {LARGURA} {altura}" role="img" '
           f'aria-label="{escape(t["alt"], {chr(34): "&quot;"})}">',
           f'<rect x="0.5" y="0.5" width="{LARGURA - 1}" height="{altura - 1}" rx="14" fill="{FUNDO}" stroke="#3b3a36"/>',
           f'<rect x="0.5" y="0.5" width="{LARGURA - 1}" height="40" rx="14" fill="{BARRA}"/>',
           f'<rect x="0.5" y="26" width="{LARGURA - 1}" height="15" fill="{BARRA}"/>',
           f'<line x1="1" y1="40.5" x2="{LARGURA - 1}" y2="40.5" stroke="#34332f"/>',
           '<circle cx="24" cy="20.5" r="6" fill="#ff5f57"/><circle cx="44" cy="20.5" r="6" fill="#febc2e"/><circle cx="64" cy="20.5" r="6" fill="#28c840"/>',
           f'<text x="{LARGURA / 2}" y="25" text-anchor="middle" font-family="{SANS}" font-size="13" fill="{FRACO}">{escape(t["titulo"])}</text>']
    return "\n".join(cab + s + ["</svg>", ""])


def confere(svg):
    """Nenhuma linha passa da largura (estimativa larga: serifa ~0.52 em, mono ~0.61 em)."""
    for m in re.finditer(r'<text x="([\d.]+)"[^>]*text-anchor="start">(.*?)</text>', svg):
        x = float(m.group(1))
        w = 0.0
        for fam, tam, txt in re.findall(r'font-family="([^"]+)"[^>]*font-size="([\d.]+)">([^<]*)</tspan>', m.group(2)):
            txt = txt.replace("&#160;", " ").replace("&amp;", "&")
            w += len(txt) * float(tam) * (0.61 if "monospace" in fam else 0.5)
        if x + w > LARGURA - MARGEM + 20:
            raise SystemExit(f"Linha demasiado comprida para a imagem ({x + w:.0f} px): {re.sub('<[^>]+>', '', m.group(2))}")


def main():
    tmp = tempfile.mkdtemp(prefix="mw2any_docs_")
    try:
        amb = dict(os.environ, MAKERWORLD_TO_ANY_CONFIG=os.path.join(tmp, "dados", "config.json"))
        for v in ("MAKERWORLD_TO_ANY_IMPRESSORA", "MAKERWORLD_TO_ANY_PERFIS"):
            amb.pop(v, None)
        modelos = os.path.join(tmp, "Modelos")
        os.makedirs(modelos)
        corre(amb, "exemplo.py", os.path.join(modelos, "Exemplo.3mf"))
        corre(amb, "perfil.py", "--preco-kg", "PLA=18;*=22", "--preco-hora", "0.40")
        saida = corre(amb, "adaptar.py", os.path.join(modelos, "Exemplo.3mf"), "--impressora", "Kobra X", "--perfis", "sistema", "--json")
        saida = saida.replace(json.dumps(modelos)[1:-1], json.dumps(PASTA_FALSA)[1:-1]).replace(json.dumps(tmp)[1:-1], json.dumps(PASTA_FALSA)[1:-1])
        if re.search(r"[A-Za-z]:\\\\Users\\\\", saida):
            raise SystemExit("O relatorio ainda tem um caminho pessoal")
        rel = json.loads(saida)
        comando = 'python adaptar.py "C:\\Modelos\\Exemplo.3mf" --impressora "Kobra X"'
        os.makedirs(DOCS, exist_ok=True)
        for lingua, nome in (("pt", "demo.svg"), ("en", "demo.en.svg")):
            svg = conversa(rel, TEXTOS[lingua], comando)
            confere(svg)
            with open(os.path.join(DOCS, nome), "w", encoding="utf-8", newline="\n") as f:
                f.write(svg)
        adaptado = os.path.join(modelos, "Exemplo - Kobra X.3mf")
        corre(amb, "medir.py", adaptado, "--fatiar", "--imagem", os.path.join(DOCS, "pratos.png"))
        for lingua in ("pt", "en"):
            print(f"--- {lingua}")
            for tipo, c in resposta(rel, TEXTOS[lingua]):
                print(" ", tipo, c if isinstance(c, (str, tuple)) else "".join(x for x, _ in c))
        print("docs/demo.svg, docs/demo.en.svg e docs/pratos.png")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
