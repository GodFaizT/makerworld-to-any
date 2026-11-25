"""Pratos de um projeto Anycubic ja adaptado: ver o que esta em cada um, mover objetos para outro prato, por um
objeto por prato, afastar pecas que estao muito juntas e centrar.
MakerWorld to Any - feito pela Megatic (https://megatic.pt).

Uso:
    python pratos.py <projeto.3mf> --listar
    python pratos.py <projeto.3mf> [<saida.3mf>] --mover "body=1;barra=2"     objetos (nome, numero da lista ou "prato 2") -> prato
    python pratos.py <projeto.3mf> [<saida.3mf>] --um-por-prato
    python pratos.py <projeto.3mf> [<saida.3mf>] --juntar                      tudo num prato so
    python pratos.py <projeto.3mf> [<saida.3mf>] --afastar 6 [--prato 1]       folga minima entre pecas (mm)
    python pratos.py <projeto.3mf> [<saida.3mf>] --centrar [--prato 1]
    ... [--fatiar]

Sem <saida.3mf> altera o proprio ficheiro (fica uma copia de seguranca; desfazer.py repoe).
As pecas que mudam de prato mantem a arrumacao que tinham entre si e o grupo fica ao centro da mesa. Pratos que
ficam vazios desaparecem. A torre de purga e posta outra vez num sitio livre.
"""
import argparse
import json
import math
import os
import re
import shutil
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True
import anycubic as K
import distancias

RE_PRATO = re.compile(r"[ \t]*<plate>.*?</plate>\r?\n", re.S)
RE_INST = re.compile(r'[ \t]*<model_instance>\s*<metadata key="object_id" value="(\d+)"/>\s*'
                     r'<metadata key="instance_id" value="(\d+)"/>.*?</model_instance>\r?\n', re.S)
MINIATURAS = re.compile(r'[ \t]*<metadata key="(?:thumbnail_file|thumbnail_no_light_file|top_file|pick_file)" value="[^"]*"/>\r?\n')
ENTRE_GRUPOS = 8.0       # mm entre grupos de pecas que vieram de pratos diferentes


class Projeto:
    def __init__(self, caminho):
        self.caminho = os.path.abspath(caminho)
        self.z = zipfile.ZipFile(self.caminho)
        self.j = json.loads(self.z.read("Metadata/project_settings.config"))
        if not K.impressora_do_projeto(self.j):
            raise SystemExit("Este projeto nao e de uma impressora Anycubic: adapta-o primeiro com adaptar.py")
        self.mod = K.Modelo(self.z)
        self.n = self.mod.n_pratos
        self.itens = self.mod.caixas()
        vezes = {}
        for c in self.itens:
            c["inst"] = vezes.get(c["oid"], 0)
            vezes[c["oid"]] = c["inst"] + 1
            c["prato"] = K.prato_de(c, self.n)
            ox, oy = K.origem_prato(c["prato"], self.n)
            c["llo"] = [c["lo"][0] - ox, c["lo"][1] - oy, c["lo"][2]]
            c["lhi"] = [c["hi"][0] - ox, c["hi"][1] - oy, c["hi"][2]]
            c["novo"] = c["prato"]            # prato de destino
            c["d"] = [0.0, 0.0]              # deslocamento na mesa (mm)
        self.feito = []
        self.avisos = []                      # o que o utilizador deve confirmar depois de gravar

    def fecha(self):
        self.z.close()

    # ------------------------------------------------------------------ escolher
    def escolhe(self, alvo):
        a = alvo.strip().strip('"\'').lower()
        m = re.fullmatch(r"prato\s*(\d+)", a)
        if m:
            return [c for c in self.itens if c["novo"] == int(m.group(1))]
        if a.isdigit():
            n = int(a)
            if not 1 <= n <= len(self.itens):
                raise SystemExit(f"Nao ha objeto {n} (ha {len(self.itens)})")
            return [self.itens[n - 1]]
        if a in ("tudo", "todos", "todas", "*"):
            return list(self.itens)
        achados = [c for c in self.itens if a in c["nome"].lower()]
        if not achados:
            raise SystemExit(f"Nenhum objeto com '{alvo}' no nome. Ha: " + ", ".join(sorted({c['nome'] for c in self.itens})))
        return achados

    def membros(self, p):
        return [c for c in self.itens if c["novo"] == p]

    def caixa_de(self, cs):
        return (min(c["llo"][0] + c["d"][0] for c in cs), min(c["llo"][1] + c["d"][1] for c in cs),
                max(c["lhi"][0] + c["d"][0] for c in cs), max(c["lhi"][1] + c["d"][1] for c in cs))

    # ------------------------------------------------------------------ operacoes
    def move(self, regras):
        """regras: [(alvo, prato)]"""
        for alvo, p in regras:
            if p < 1:
                raise SystemExit("O prato tem de ser 1 ou mais")
            for c in self.escolhe(alvo):
                if c["novo"] != p:
                    c["novo"] = p
                    self.feito.append(f"{c['nome']} -> prato {p}")
        self._arruma_mudados()

    def um_por_prato(self):
        p = 0
        for c in sorted(self.itens, key=lambda c: (c["novo"], c["i"])):
            if c["printable"] == "0":
                continue
            p += 1
            c["novo"] = p
        self.feito.append(f"um objeto por prato ({p} pratos)")
        self._arruma_mudados()

    def junta(self):
        for c in self.itens:
            c["novo"] = 1
        self.feito.append("tudo no prato 1")
        self._arruma_mudados()

    def _arruma_mudados(self):
        for p in sorted({c["novo"] for c in self.itens}):
            cs = self.membros(p)
            antes = {c["i"] for c in self.itens if c["prato"] == p}
            if {c["i"] for c in cs} == antes:
                continue                                  # este prato nao mudou
            grupos = {}
            for c in cs:
                grupos.setdefault(c["prato"], []).append(c)     # o que veio junto fica arrumado como estava
            if len(grupos) > 1:
                self._em_fila(list(grupos.values()))
            self.centra(p, regista=False)

    def _em_fila(self, grupos):
        """Poe grupos lado a lado (pelas caixas), mudando de fila quando nao cabem na largura da mesa."""
        grupos.sort(key=lambda g: -(self.caixa_de(g)[3] - self.caixa_de(g)[1]))
        x = y = fila_alt = 0.0
        for g in grupos:
            x0, y0, x1, y1 = self.caixa_de(g)
            w, h = x1 - x0, y1 - y0
            if x > 0 and x + w > K.CAMA_X - 10:
                x, y, fila_alt = 0.0, y + fila_alt + ENTRE_GRUPOS, 0.0
            for c in g:
                c["d"][0] += x - x0
                c["d"][1] += y - y0
            x += w + ENTRE_GRUPOS
            fila_alt = max(fila_alt, h)

    def centra(self, p=None, regista=True):
        for q in ([p] if p else sorted({c["novo"] for c in self.itens})):
            cs = [c for c in self.membros(q) if c["printable"] != "0"] or self.membros(q)
            if not cs:
                continue
            x0, y0, x1, y1 = self.caixa_de(cs)
            dx, dy = K.CAMA_X / 2 - (x0 + x1) / 2, K.CAMA_Y / 2 - (y0 + y1) / 2
            dx, dy = round(dx / distancias.CELULA) * distancias.CELULA, round(dy / distancias.CELULA) * distancias.CELULA
            for c in self.membros(q):
                c["d"][0] += dx
                c["d"][1] += dy
            if regista:
                self.feito.append(f"prato {q} centrado")

    def pegadas(self, p):
        """Pegadas das pecas do prato p, ja nas posicoes novas (None sem numpy)."""
        if not distancias.disponivel():
            return None
        cs = self.membros(p)
        peg = distancias.Pegadas(self.mod, cs)
        for k, c in enumerate(peg.itens):
            c["d"][0], c["d"][1] = peg.move(k, c["d"][0], c["d"][1])     # arredonda o deslocamento a grelha
        return peg

    def afasta(self, alvo, p=None):
        if not distancias.disponivel():
            raise SystemExit("Afastar pecas precisa do numpy (pip install numpy)")
        for q in ([p] if p else sorted({c["novo"] for c in self.itens})):
            peg = self.pegadas(q)
            if peg is None or len(peg) < 2:
                continue
            antes = min([g for _, _, g in peg.folgas(limite=alvo + 20)] or [alvo + 20])
            if antes >= alvo:
                continue
            ok, mov = distancias.afasta(peg, alvo)
            for k, (dx, dy) in mov.items():
                peg.itens[k]["d"][0] += dx
                peg.itens[k]["d"][1] += dy
            self.centra(q, regista=False)
            depois = min([g for _, _, g in self.pegadas(q).folgas(limite=alvo + 20)] or [alvo + 20])
            self.feito.append(f"prato {q}: pecas afastadas (folga minima {antes:.1f} -> {depois:.1f} mm)"
                              + ("" if ok else " - nao consegui chegar ao pedido, ve no Anycubic"))

    def junta_demasiado(self, minimo=2.0, alvo=5.0):
        """Depois de mover: se pecas de grupos diferentes ficaram em cima umas das outras, afasta-as."""
        if not distancias.disponivel():
            return
        for q in sorted({c["novo"] for c in self.itens}):
            cs = self.membros(q)
            if len({c["prato"] for c in cs}) < 2:
                continue
            peg = self.pegadas(q)
            if any(g < minimo for _, _, g in peg.folgas(limite=minimo + 1)):
                self.afasta(alvo, q)

    # ------------------------------------------------------------------ gravar
    def _trocas_por_camada(self, texto):
        """custom_gcode_per_layer.xml para os pratos novos. As trocas de cor e pausas por camada estao guardadas por
        numero de prato, mas sao das pecas que la estavam: seguem as pecas para o prato onde ficam. Se um prato novo
        junta pecas de pratos diferentes, as trocas passam a valer para todas (o slicer so sabe faze-las por prato):
        fica um aviso."""
        RE_BLOCO = re.compile(r"<plate>.*?</plate>[ \t]*\r?\n?", re.S)
        RE_CAMADA = re.compile(r"[ \t]*<layer\b[^>]*/>[ \t]*\r?\n?")
        primeiro = RE_BLOCO.search(texto)
        if not primeiro:
            return texto
        blocos = {}
        for m in RE_BLOCO.finditer(texto):
            pid = re.search(r'<plate_info id="(\d+)"', m.group(0))
            if pid:
                blocos[int(pid.group(1))] = m.group(0)
        novos = []
        for q in sorted({c["final"] for c in self.itens}):
            cs = [c for c in self.itens if c["final"] == q]
            fontes = sorted({c["prato"] for c in cs if c["printable"] != "0"} or {c["prato"] for c in cs})
            com = [p for p in fontes if p in blocos and RE_CAMADA.search(blocos[p])]
            base = blocos[com[0]] if com else next((blocos[p] for p in fontes if p in blocos), None)
            if base is None:
                continue
            if len(com) > 1:                  # juntam-se as trocas dos varios pratos, por altura
                camadas = {}
                for p in com:
                    for linha in RE_CAMADA.findall(blocos[p]):
                        camadas.setdefault(linha.strip(), linha if linha.endswith("\n") else linha + "\n")

                def altura(linha):
                    z = re.search(r'top_z="([-\d.]+)"', linha)
                    return float(z.group(1)) if z else 0.0
                onde = RE_CAMADA.search(base).start()
                base = RE_CAMADA.sub("", base)
                base = base[:onde] + "".join(camadas[x] for x in sorted(camadas, key=altura)) + base[onde:]
            if com and len(fontes) > 1:
                self.avisos.append(f"prato {q}: as trocas de cor ou pausas por camada vinham do prato {' e '.join(str(p) for p in com)} e passam a "
                                   "valer para todas as pecas deste prato: confirma no Anycubic")
            novos.append(re.sub(r'(<plate_info id=")\d+', lambda m: m.group(1) + str(q), base))
        return texto[:primeiro.start()] + "".join(novos) + RE_BLOCO.sub("", texto[primeiro.start():])

    def _compacta(self):
        usados = sorted({c["novo"] for c in self.itens})
        return {velho: i + 1 for i, velho in enumerate(usados)}

    def grava(self, destino):
        mapa = self._compacta()
        n_novo = len(mapa)
        cel = distancias.CELULA
        for c in self.itens:
            c["final"] = mapa[c["novo"]]
            c["d"] = [round(c["d"][0] / cel) * cel, round(c["d"][1] / cel) * cel]     # na grelha das pegadas
        transf = {}
        for c in self.itens:
            ox0, oy0 = K.origem_prato(c["prato"], self.n)
            ox1, oy1 = K.origem_prato(c["final"], n_novo)
            T = list(c["T"])
            T[9] += ox1 - ox0 + c["d"][0]
            T[10] += oy1 - oy0 + c["d"][1]
            transf[c["i"]] = T

        # pratos do model_settings
        ms = self.mod.ms
        velhos = RE_PRATO.findall(ms)
        cab, inst = {}, {}
        for bloco in velhos:
            pid = int(re.search(r'key="plater_id" value="(\d+)"', bloco).group(1))
            cab[pid] = RE_INST.sub("", bloco)
            for m in RE_INST.finditer(bloco):
                inst[(m.group(1), int(m.group(2)))] = m.group(0)
        molde = cab.get(1) or next(iter(cab.values()))
        ind = re.match(r"[ \t]*", molde).group(0)
        novos, ident = [], 9000
        for velho, q in sorted(mapa.items(), key=lambda kv: kv[1]):
            cs = [c for c in self.itens if c["final"] == q]
            igual = velho in cab and velho == q and {c["i"] for c in cs} == {c["i"] for c in self.itens if c["prato"] == velho}
            b = cab.get(velho, molde)
            if not igual:
                b = MINIATURAS.sub("", b)                  # a miniatura ja nao corresponde ao prato
            b = re.sub(r'(key="plater_id" value=")\d+', rf"\g<1>{q}", b)
            b = re.sub(r'(key="plater_name" value=")[^"]*', r"\g<1>", b)
            blocos = ""
            for c in cs:
                bl = inst.get((c["oid"], c["inst"]))
                if bl is None:
                    ident += 1
                    bl = (f'{ind}  <model_instance>\n{ind}    <metadata key="object_id" value="{c["oid"]}"/>\n'
                          f'{ind}    <metadata key="instance_id" value="{c["inst"]}"/>\n'
                          f'{ind}    <metadata key="identify_id" value="{ident}"/>\n{ind}  </model_instance>\n')
                blocos += bl
            fim = b.rindex("</plate>")
            novos.append(b[:fim].rstrip(" \t") + blocos + ind + b[fim:])
        primeiro = RE_PRATO.search(ms)
        ms_novo = ms[:primeiro.start()] + "".join(novos) + RE_PRATO.sub("", ms[primeiro.start():])

        # torre de purga: uma posicao por prato
        j = dict(self.j)
        nfil = len(j.get("filament_settings_id", [])) or 1
        torre = None
        if nfil > 1 and str(j.get("enable_prime_tower")) == "1":
            largura = float(K.primeiro(j.get("prime_tower_width", "35")) or 35)
            torre = []
            for velho, q in sorted(mapa.items(), key=lambda kv: kv[1]):
                peg = self.pegadas(velho)
                cs = [c for c in self.membros(velho) if c["printable"] != "0"]
                rects = [(c["llo"][0] + c["d"][0], c["llo"][1] + c["d"][1], c["lhi"][0] + c["d"][0], c["lhi"][1] + c["d"][1]) for c in cs]
                pos = K.posicao_torre(rects, nfil, largura, livre=peg.livre if peg is not None else None)
                if not pos:
                    pos = (int(K.CAMA_X / 2), int(K.CAMA_Y - 50))
                    self.avisos.append(f"prato {q}: nao ha sitio livre para a torre de purga; ficou em ({pos[0]}, {pos[1]}), provavelmente "
                                       "em cima de pecas: poe menos pecas neste prato")
                torre.append(pos)
            j["wipe_tower_x"] = [str(t[0]) for t in torre]
            j["wipe_tower_y"] = [str(t[1]) for t in torre]
        else:
            for key in K.POR_PRATO:
                if isinstance(j.get(key), list) and j[key]:
                    j[key] = (j[key] * n_novo)[:n_novo]

        cont = {"i": -1}

        def item(m):
            cont["i"] += 1
            t = K.fmt_matriz(transf[cont["i"]])
            tag = m.group(0)
            if 'transform="' in tag:
                return re.sub(r'transform="[^"]*"', f'transform="{t}"', tag)
            return tag.replace("<item ", f'<item transform="{t}" ', 1)

        def mudar(nome, d):
            if nome == "3D/3dmodel.model":
                return re.sub(r"<item\s[^>]*?/?>", item, d.decode("utf-8")).encode("utf-8")
            if nome == "Metadata/model_settings.config":
                return ms_novo.encode("utf-8")
            if nome == "Metadata/project_settings.config":
                return json.dumps(j, indent=4, ensure_ascii=False).encode("utf-8")
            if nome == "Metadata/custom_gcode_per_layer.xml":
                return self._trocas_por_camada(d.decode("utf-8")).encode("utf-8")
            return d

        tmp = destino + ".novo"
        K.reescreve(self.caminho, tmp, mudar)
        self.fecha()
        os.replace(tmp, destino)
        return n_novo, torre


def lista(caminho, titulo=None):
    """Imprime o que esta em cada prato e devolve (modelo aberto, por_prato, avisos)."""
    z = zipfile.ZipFile(caminho)
    j = json.loads(z.read("Metadata/project_settings.config"))
    if not K.impressora_do_projeto(j):
        raise SystemExit("Este projeto nao e de uma impressora Anycubic: adapta-o primeiro com adaptar.py")
    mod = K.Modelo(z)
    por_prato = K.caixas_por_prato(mod)
    if titulo:
        print(titulo)
    print(f"{K.MODELO}: mesa {K.CAMA_X:g} x {K.CAMA_Y:g} mm, {mod.n_pratos} prato(s)")
    for p in range(1, mod.n_pratos + 1):
        cs = por_prato.get(p, [])
        print(f"prato {p}:" + ("" if cs else " (vazio)"))
        for c in cs:
            print(f"  {c['i'] + 1}  {c['nome']}  {c['tam'][0]:.1f} x {c['tam'][1]:.1f} x {c['tam'][2]:.1f} mm  "
                  f"(x {c['llo'][0]:.1f}..{c['lhi'][0]:.1f}, y {c['llo'][1]:.1f}..{c['lhi'][1]:.1f})"
                  + ("  [nao imprime]" if c["printable"] == "0" else ""))
    avisos = K.avisos_mesa(por_prato, sobreposicao=not distancias.disponivel())
    pegadas = {}
    if distancias.disponivel():
        av, pegadas = distancias.avisos_folgas(mod, por_prato)
        avisos += av
    return z, j, por_prato, pegadas, avisos


def interpreta(texto):
    """'body=1; barra=2' -> [("body", 1), ("barra", 2)]"""
    out = []
    for r in re.split(r"[;\n]+", texto or ""):
        r = r.strip()
        if not r:
            continue
        if "=" not in r or not r.rsplit("=", 1)[1].strip().isdigit():
            raise SystemExit(f"Nao percebi '{r}': usa objeto=prato (ex.: 'body=1;barra=2')")
        alvo, p = r.rsplit("=", 1)
        out.append((alvo.strip(), int(p)))
    return out


def main():
    ap = argparse.ArgumentParser(description="Pratos de um projeto Anycubic (MakerWorld to Any)")
    ap.add_argument("projeto")
    ap.add_argument("saida", nargs="?")
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--mover", help='ex.: "body=1;barra=2" (nome, numero da lista ou "prato 2")')
    ap.add_argument("--um-por-prato", action="store_true")
    ap.add_argument("--juntar", action="store_true", help="tudo num prato so")
    ap.add_argument("--afastar", type=float, metavar="MM", help="folga minima entre pecas")
    ap.add_argument("--centrar", action="store_true")
    ap.add_argument("--prato", type=int, help="so este prato (para --afastar e --centrar)")
    ap.add_argument("--fatiar", action="store_true")
    a = ap.parse_args()

    if a.listar or not (a.mover or a.um_por_prato or a.juntar or a.afastar or a.centrar):
        z, j, por_prato, pegadas, avisos = lista(a.projeto)
        z.close()
        print("AVISOS:" if avisos else "AVISOS: nenhum")
        for av in avisos:
            print("  -", av)
        return

    pr = Projeto(a.projeto)
    if a.mover:
        pr.move(interpreta(a.mover))
    if a.um_por_prato:
        pr.um_por_prato()
    if a.juntar:
        pr.junta()
    if a.mover or a.um_por_prato or a.juntar:
        pr.junta_demasiado()
    if a.afastar:
        pr.afasta(a.afastar, a.prato)
    if a.centrar:
        pr.centra(a.prato)
    destino = os.path.abspath(a.saida or a.projeto)
    copia = K.guarda_copia(destino, "pratos") if os.path.exists(destino) else None
    feito = list(pr.feito)
    pr.grava(destino)

    for f in feito:
        print("-", f)
    z, j, por_prato, pegadas, avisos = lista(destino, "RESULTADO: " + destino)
    avisos = list(pr.avisos) + avisos
    if a.fatiar:
        tmp = tempfile.mkdtemp(prefix="mw2any_pratos_")
        try:
            res = K.fatia(destino, os.path.join(tmp, "fatiado"), tmp, avisos)
            print("FATIADO:\n  " + K.texto_resumo(res, j.get("filament_colour")).replace("\n", "\n  "))
            avisos += K.colisoes_torre(res, por_prato, pegadas=pegadas)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    z.close()
    if copia:
        print("COPIA DO FICHEIRO ANTERIOR:", copia, "(desfazer.py repoe)")
    print("AVISOS:" if avisos else "AVISOS: nenhum")
    for av in avisos:
        print("  -", av)


if __name__ == "__main__":
    main()
