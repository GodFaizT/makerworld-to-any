r"""Gera as imagens do README a partir de uma adaptacao REAL do projeto de exemplo (precisa do Anycubic Slicer Next).

    python tools/gera_docs.py

    docs/demo.svg     o relatorio verdadeiro do adaptar.py, desenhado como uma janela de terminal
    docs/pratos.png   os pratos vistos de cima (medir.py --fatiar --imagem), com a torre de purga

Corre tudo numa pasta temporaria, com preferencias isoladas (so com precos de exemplo, para aparecer o custo). Os
caminhos da pasta temporaria sao trocados por C:\Modelos, para as imagens nao levarem caminhos de quem as gera.
"""
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

FUNDO, BARRA, TEXTO, APAGADO, VERDE, AZUL, AMARELO = "#0f1419", "#1c2430", "#d8dee6", "#7d8a99", "#3fb950", "#58a6ff", "#e3b341"
FONTE = "'Cascadia Code', Consolas, 'SF Mono', Menlo, 'DejaVu Sans Mono', monospace"
TAM, LINHA, MARGEM, LARGURA = 12.5, 19, 26, 900


def corre(amb, script, *args):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)] + list(args), capture_output=True, env=amb)
    saida = (r.stdout + r.stderr).decode("utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"{script} falhou:\n{saida}")
    return saida


def pedacos(linha):
    """[(texto, cor, negrito)] de uma linha do relatorio."""
    if set(linha.strip()) == {"="}:
        return [(linha, "#30363d", False)]
    m = re.match(r"(ORIGINAL|ADAPTADO|FATIADO|CUSTO ESTIMADO|AVISOS|G-CODE)\s*:", linha)
    if m:
        resto = linha[m.end():]
        return [(m.group(0), AZUL, True), (resto, VERDE if m.group(1) == "AVISOS" and "nenhum" in resto else TEXTO, False)]
    out, pos = [], 0
    # etiquetas entre [ ] no fim, cores #RRGGBB na propria cor, tempos a verde
    for t in re.finditer(r"#[0-9A-Fa-f]{6}\b|\[(?:o autor mudou|valor do perfil do autor|acerto da skill)\]|\d+h \d+m \d+s|\b\d+m \d+s", linha):
        if t.start() > pos:
            out.append((linha[pos:t.start()], TEXTO, False))
        s = t.group(0)
        out.append((s, s if s.startswith("#") else APAGADO if s.startswith("[") else VERDE, s.startswith("#")))
        pos = t.end()
    if pos < len(linha):
        out.append((linha[pos:], TEXTO, False))
    if linha.lstrip().startswith(("do autor, nao passou", "nota:")):
        out = [(t, AMARELO if c == TEXTO else c, n) for t, c, n in out]
    return out


def terminal(comando, linhas, titulo):
    altura = 40 + 22 + LINHA * (len(linhas) + 2) + 14
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{altura}" viewBox="0 0 {LARGURA} {altura}" role="img" '
         f'aria-label="{escape(titulo)}">',
         f'  <rect x="0.5" y="0.5" width="{LARGURA - 1}" height="{altura - 1}" rx="12" fill="{FUNDO}" stroke="#2a3442"/>',
         f'  <rect x="0.5" y="0.5" width="{LARGURA - 1}" height="38" rx="12" fill="{BARRA}"/>',
         f'  <rect x="0.5" y="24" width="{LARGURA - 1}" height="15" fill="{BARRA}"/>',
         '  <circle cx="24" cy="20" r="6" fill="#ff5f57"/><circle cx="44" cy="20" r="6" fill="#febc2e"/><circle cx="64" cy="20" r="6" fill="#28c840"/>',
         f'  <text x="{LARGURA / 2}" y="25" text-anchor="middle" font-family="\'Segoe UI\', Helvetica, Arial, sans-serif" font-size="13" '
         f'fill="{APAGADO}">{escape(titulo)}</text>',
         f'  <g font-family="{FONTE}" font-size="{TAM}" xml:space="preserve">']
    y = 40 + 26
    s.append(f'    <text x="{MARGEM}" y="{y}"><tspan fill="{VERDE}">&gt; </tspan><tspan fill="#ffffff" font-weight="bold">{escape(comando)}</tspan></text>')
    y += LINHA
    for linha in linhas:
        y += LINHA
        # espacos que nao se juntam (&#160;): os browsers colapsam os espacos normais no texto de um SVG
        spans = "".join(f'<tspan fill="{c}"' + (' font-weight="bold"' if n else "") + f'>{escape(t).replace(" ", "&#160;")}</tspan>'
                        for t, c, n in pedacos(linha))
        s.append(f'    <text x="{MARGEM}" y="{y}">{spans}</text>')
    s += ["  </g>", "</svg>", ""]
    return "\n".join(s)


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
        rel = corre(amb, "adaptar.py", os.path.join(modelos, "Exemplo.3mf"), "--impressora", "Kobra X", "--perfis", "sistema")
        rel = rel.replace(modelos, PASTA_FALSA).replace(tmp, PASTA_FALSA)
        if re.search(r"[A-Za-z]:\\Users\\", rel):
            raise SystemExit("O relatorio ainda tem um caminho pessoal:\n" + rel)
        linhas = [l.rstrip() for l in rel.strip().splitlines()]
        maior = max(len(l) for l in linhas)
        if maior * TAM * 0.6 > LARGURA - 2 * MARGEM:
            raise SystemExit(f"Ha linhas com {maior} caracteres: nao cabem na imagem")
        os.makedirs(DOCS, exist_ok=True)
        with open(os.path.join(DOCS, "demo.svg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(terminal(r'python adaptar.py "C:\Modelos\Exemplo.3mf"', linhas,
                             "Relatorio real do adaptar.py com o projeto de exemplo (2 pratos, 2 cores) para a Anycubic Kobra X"))
        adaptado = os.path.join(modelos, "Exemplo - Kobra X.3mf")
        corre(amb, "medir.py", adaptado, "--fatiar", "--imagem", os.path.join(DOCS, "pratos.png"))
        print(rel)
        print(f"docs/demo.svg ({len(linhas)} linhas, a maior com {maior} caracteres) e docs/pratos.png")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
