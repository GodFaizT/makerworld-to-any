"""Separa pratos de um projeto da Kobra X: fica so com os pratos pedidos, renumerados 1..n, e com os objetos
deslocados para as novas posicoes de prato (passo 312 na mesa de 260; 307.2 na vista de montagem).

Uso:
    python separar_pratos.py <entrada.3mf> <saida.3mf> <pratos, ex. 3,4>

Exemplo: o Engel+ tinha anjo grande nos pratos 1-2 e pequeno nos 3-4 -> "1,2" e "3,4" dao dois ficheiros.
Fatiar depois com medir.py --fatiar para confirmar.
"""
import math
import re
import sys
import zipfile


def colunas(n):
    v = math.sqrt(n)
    r = round(v)
    return r + 1 if v > r else r


def main():
    src, dst, pratos = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(",")]
    zi = zipfile.ZipFile(src)
    ms = zi.read("Metadata/model_settings.config").decode("utf-8")
    placas = {int(re.search(r'plater_id" value="(\d+)"', p).group(1)): p for p in re.findall(r"  <plate>.*?</plate>\n", ms, re.S)}
    n_orig = len(placas)
    faltam = [p for p in pratos if p not in placas]
    if faltam:
        raise SystemExit(f"O projeto so tem os pratos {sorted(placas)}")

    def slot(i, n):        # coluna, linha (a linha cresce para y negativo)
        c = colunas(n)
        return (i - 1) % c, (i - 1) // c

    obj_prato = {}
    for i, p in placas.items():
        for oid in re.findall(r'object_id" value="(\d+)"', p):
            obj_prato[oid] = i
    novo_id = {old: k + 1 for k, old in enumerate(pratos)}
    manter = {o for o, i in obj_prato.items() if i in pratos}

    def desloc(oid, passo):
        i = obj_prato[oid]
        (c0, l0), (c1, l1) = slot(i, n_orig), slot(novo_id[i], len(pratos))
        return (c1 - c0) * passo, -(l1 - l0) * passo

    print("objetos mantidos:", sorted(manter, key=int))
    m = zi.read("3D/3dmodel.model").decode("utf-8")
    for oid in set(obj_prato) - manter:
        m, n = re.subn(r'\s*<object id="%s" .*?</object>' % oid, "", m, flags=re.S)
        m, n = re.subn(r'\s*<item objectid="%s" [^>]*/>' % oid, "", m)

    def mexe_item(mm):
        oid, t = mm.group(1), mm.group(3).split()
        if oid not in obj_prato:
            return mm.group(0)
        dx, dy = desloc(oid, 312)
        t[9] = format(float(t[9]) + dx, ".9g")
        t[10] = format(float(t[10]) + dy, ".9g")
        return mm.group(0).replace(mm.group(3), " ".join(t))
    m = re.sub(r'<item objectid="(\d+)"( [^>]*)?transform="([^"]+)"', mexe_item, m)
    for oid in set(obj_prato) - manter:
        ms = re.sub(r'\n  <object id="%s">.*?</object>' % oid, "", ms, flags=re.S)
        ms = re.sub(r'\s*<assemble_item object_id="%s" [^>]*/>' % oid, "", ms)
    for i, p in placas.items():
        if i not in pratos:
            ms = ms.replace(p, "")
            continue
        k = novo_id[i]
        q = p.replace(f'plater_id" value="{i}"', f'plater_id" value="{k}"')
        for base in ("plate_", "plate_no_light_", "top_", "pick_"):
            q = q.replace(f"Metadata/{base}{i}.png", f"Metadata/{base}{k}.png")
        ms = ms.replace(p, q)

    def mexe_asm(mm):
        oid, t = mm.group(1), mm.group(2).split()
        if oid not in obj_prato:
            return mm.group(0)
        dx, dy = desloc(oid, 307.2)
        t[9] = repr(float(t[9]) + dx)
        t[10] = repr(float(t[10]) + dy)
        return mm.group(0).replace(mm.group(2), " ".join(t))
    ms = re.sub(r'<assemble_item object_id="(\d+)" instance_id="0" transform="([^"]+)"', mexe_asm, ms)
    ren = {}
    for i in placas:
        for base in ("plate_", "plate_no_light_", "top_", "pick_"):
            for suf in ((".png", "_small.png") if base == "plate_" else (".png",)):
                ren[f"Metadata/{base}{i}{suf}"] = f"Metadata/{base}{novo_id[i]}{suf}" if i in pratos else None
    zo = zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED)
    for it in zi.infolist():
        nome = it.filename
        if nome in ren:
            if ren[nome] is None:
                continue
            it2 = zipfile.ZipInfo(ren[nome], it.date_time)
            it2.compress_type = zipfile.ZIP_DEFLATED
            zo.writestr(it2, zi.read(nome))
            continue
        d = zi.read(nome)
        if nome == "3D/3dmodel.model":
            d = m.encode("utf-8")
        elif nome == "Metadata/model_settings.config":
            d = ms.encode("utf-8")
        elif nome == "Metadata/project_settings.config":   # torre de purga: uma posicao por prato
            import json
            j = json.loads(d)
            for key in ("wipe_tower_x", "wipe_tower_y"):
                if isinstance(j.get(key), list) and len(j[key]) == n_orig:
                    j[key] = [j[key][p - 1] for p in pratos]
            d = json.dumps(j, indent=4, ensure_ascii=False).encode("utf-8")
        zo.writestr(it, d)
    zo.close()
    print("ok", dst)


if __name__ == "__main__":
    main()
