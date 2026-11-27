"""Objetos, pecas e o filamento de cada uma (Metadata/model_settings.config de um projeto Bambu/Anycubic).

O slicer guarda o filamento do objeto em <metadata key="extruder"> e, nas pecas, so quando e diferente do do objeto.
"""
import html
import re

RE_OBJ = re.compile(r'(<object id="(\d+)">)(.*?)(</object>)', re.S)
RE_PECA = re.compile(r'(<part id="(\d+)" subtype="(\w+)">)(.*?)(</part>)', re.S)
RE_EXT = re.compile(r'[ \t]*<metadata key="extruder" value="(\d+)"/>\r?\n?')
RE_NOME = re.compile(r'<metadata key="name" value="([^"]*)"/>')
# caracteres de controlo, quebras de linha e marcas invisiveis/de direcao do texto
_INVISIVEIS = re.compile("[\x00-\x1f\x7f​-‏  ‪-‮⁠-⁤⁦-⁩﻿]")


def limpa_nome(nome, maximo=80):
    """Nome escrito pelo autor de um 3MF (objeto, peca): sem quebras de linha nem caracteres invisiveis, e curto.
    Nos relatorios e so um rotulo, nunca uma instrucao."""
    s = re.sub(r"\s+", " ", _INVISIVEIS.sub(" ", html.unescape(nome or ""))).strip()
    return s if len(s) <= maximo else s[:maximo - 3].rstrip() + "..."


def _ext(texto):
    m = re.search(r'key="extruder" value="(\d+)"', texto)
    return int(m.group(1)) if m else None


def le(ms):
    """Objetos por ordem de id: [{n, id, nome, extrusor, pecas: [{n, id, tipo, nome, extrusor, efetivo}]}].
    extrusor = o que esta escrito (None se nao esta); efetivo = o filamento com que a peca sai."""
    objs = []
    for m in RE_OBJ.finditer(ms):
        corpo = m.group(3)
        cab = corpo.split("<part", 1)[0]
        nome = RE_NOME.search(cab)
        eo = _ext(cab)
        base = eo if eo and eo > 0 else 1
        pecas = []
        for p in RE_PECA.finditer(corpo):
            pn = RE_NOME.search(p.group(4))
            pe = _ext(p.group(4))
            pecas.append({"id": p.group(2), "tipo": p.group(3), "nome": limpa_nome(pn.group(1)) if pn else "", "extrusor": pe,
                          "efetivo": pe if pe and pe > 0 else base})
        objs.append({"id": m.group(2), "nome": limpa_nome(nome.group(1)) if nome else "", "extrusor": eo, "efetivo": base, "pecas": pecas})
    objs.sort(key=lambda o: int(o["id"]))
    for n, o in enumerate(objs, 1):
        o["n"] = n
        for k, p in enumerate(o["pecas"], 1):
            p["n"] = k
    return objs


def _poe_extrusor(bloco, valor, antes_de=None):
    """Bloco de metadados (cabecalho de objeto ou interior de peca) com o filamento `valor` (None = tirar)."""
    atual = _ext(bloco)
    if atual == valor or (valor is None and atual is None):
        return bloco                                   # ja esta como se quer: nao mexe no texto
    bloco = RE_EXT.sub("", bloco)
    if valor is None:
        return bloco
    m = RE_NOME.search(bloco)
    if not m:
        return bloco
    ind = re.search(r"([ \t]*)<metadata key=\"name\"", bloco)
    ind = ind.group(1) if ind else "    "
    return bloco[:m.end()] + f'\n{ind}<metadata key="extruder" value="{valor}"/>' + bloco[m.end():]


def impoe(ms, plano):
    """Escreve o filamento de cada objeto/peca. plano = {id do objeto: {"obj": filamento, "pecas": {id: filamento}}}.
    Nas pecas so fica escrito quando difere do objeto (como o slicer faz)."""
    def no_objeto(m):
        oid = m.group(2)
        if oid not in plano:
            return m.group(0)
        alvo = plano[oid]
        corpo = m.group(3)
        partes = corpo.split("<part", 1)
        atual = _ext(partes[0])
        cab = partes[0] if (atual if atual and atual > 0 else 1) == alvo["obj"] else _poe_extrusor(partes[0], alvo["obj"])

        def na_peca(pm):
            pid = pm.group(2)
            if pid not in alvo.get("pecas", {}):
                return pm.group(0)
            v = alvo["pecas"][pid]
            return pm.group(1) + _poe_extrusor(pm.group(4), None if v == alvo["obj"] else v) + pm.group(5)
        resto = RE_PECA.sub(na_peca, "<part" + partes[1]) if len(partes) > 1 else ""
        return m.group(1) + cab + resto + m.group(4)
    return RE_OBJ.sub(no_objeto, ms)


def plano_de(ms):
    """O filamento efetivo de tudo, no formato de impoe()."""
    return {o["id"]: {"obj": o["efetivo"], "nome": o["nome"],
                      "pecas": {p["id"]: p["efetivo"] for p in o["pecas"] if p["tipo"] in ("normal_part", "modifier_part")}}
            for o in le(ms)}


def interpreta(regras):
    """'anel=2; 1.3=2;tudo=1' -> [("anel", 2), ("1.3", 2), ("tudo", 1)]"""
    out = []
    for r in re.split(r"[;\n]+", regras or ""):
        r = r.strip()
        if not r:
            continue
        if "=" not in r:
            raise SystemExit(f"I didn't understand '{r}': use target=filament (e.g. 'anel=2' or '1.3=2')")
        alvo, fil = r.rsplit("=", 1)
        if not fil.strip().isdigit() or int(fil) < 1:
            raise SystemExit(f"'{r}': the filament must be a number (1, 2, ...)")
        out.append((alvo.strip().strip('"\''), int(fil)))
    return out


def atribui(ms, regras):
    """Aplica regras (de interpreta) ao model_settings. Alvos: 'tudo'; 'N' (objeto N da lista); 'N.M' (peca M do
    objeto N); ou um texto que apareca no nome de objetos (objeto inteiro) ou, se nenhum objeto o tiver, de pecas.
    Devolve (texto novo, [descricao do que mudou])."""
    feito = []
    for alvo, fil in regras:
        objs = le(ms)
        plano = plano_de(ms)
        escolhidos = []          # (objeto, peca ou None)
        a = alvo.lower()
        m = re.fullmatch(r"(\d+)(?:\.(\d+))?", alvo)
        if a in ("tudo", "todos", "todas", "*"):
            escolhidos = [(o, None) for o in objs]
        elif m:
            o = next((o for o in objs if o["n"] == int(m.group(1))), None)
            if o is None:
                raise SystemExit(f"There is no object {m.group(1)} (there are {len(objs)})")
            if m.group(2):
                p = next((p for p in o["pecas"] if p["n"] == int(m.group(2))), None)
                if p is None:
                    raise SystemExit(f"Object {o['n']} ({o['nome']}) has no part {m.group(2)} (it has {len(o['pecas'])})")
                escolhidos = [(o, p)]
            else:
                escolhidos = [(o, None)]
        else:
            escolhidos = [(o, None) for o in objs if a in o["nome"].lower()]
            if not escolhidos:
                escolhidos = [(o, p) for o in objs for p in o["pecas"] if a in p["nome"].lower()]
            if not escolhidos:
                nomes = sorted({o["nome"] for o in objs} | {p["nome"] for o in objs for p in o["pecas"]})
                raise SystemExit(f"No object or part with '{alvo}' in its name. There are: " + ", ".join(nomes))
        for o, p in escolhidos:
            if p is None:
                plano[o["id"]]["obj"] = fil
                plano[o["id"]]["pecas"] = {pid: fil for pid in plano[o["id"]]["pecas"]}
                feito.append(f"{o['n']} {o['nome']} -> filament {fil}")
            else:
                plano[o["id"]]["pecas"][p["id"]] = fil
                feito.append(f"{o['n']}.{p['n']} {o['nome']} / {p['nome']} -> filament {fil}")
        ms = impoe(ms, plano)
    return ms, feito


def texto_lista(objs, cores=None):
    """Lista para mostrar ao utilizador (e para escolher alvos de atribui)."""
    def cor(f):
        return f" {cores[f - 1]}" if cores and 0 < f <= len(cores) else ""
    linhas = []
    for o in objs:
        normais = [p for p in o["pecas"] if p["tipo"] == "normal_part"]
        fs = sorted({p["efetivo"] for p in normais} or {o["efetivo"]})
        linhas.append(f"{o['n']}  {o['nome']}  [filament {', '.join(str(f) + cor(f) for f in fs)}]")
        if len(o["pecas"]) > 1:
            for p in o["pecas"]:
                tipo = "" if p["tipo"] == "normal_part" else f"  ({p['tipo'].replace('_part', '').replace('_', ' ')})"
                linhas.append(f"   {o['n']}.{p['n']}  {p['nome']}  [filament {p['efetivo']}{cor(p['efetivo'])}]{tipo}")
    return "\n".join(linhas)
