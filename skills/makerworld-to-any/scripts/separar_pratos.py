"""Separa pratos de um projeto Anycubic: fica so com os pratos pedidos, renumerados 1..n, e com os objetos
deslocados para as novas posicoes de prato (passo = mesa x 1.2: 312 mm na Kobra X).

Uso:
    python separar_pratos.py <entrada.3mf> <saida.3mf> <pratos, ex. 3,4>

Exemplo: um projeto com o tamanho grande nos pratos 1-2 e o pequeno nos 3-4 -> "1,2" e "3,4" dao dois ficheiros.
Fatiar depois com medir.py --fatiar para confirmar. Para mudar objetos de prato sem apagar nada: pratos.py.
Se <saida.3mf> ja existir fica uma copia de seguranca (desfazer.py repoe).
"""
import json
import math
import os
import re
import sys
import zipfile

sys.dont_write_bytecode = True
import anycubic as K


def colunas(n):
    v = math.sqrt(n)
    r = round(v)
    return r + 1 if v > r else r


def main():
    if len(sys.argv) != 4 or not re.fullmatch(r"\d+(\s*,\s*\d+)*", sys.argv[3].strip()):
        raise SystemExit(__doc__)
    src, dst, pratos = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(",")]
    zi = zipfile.ZipFile(src)
    ms = zi.read("Metadata/model_settings.config").decode("utf-8")
    if not K.impressora_do_projeto(json.loads(zi.read("Metadata/project_settings.config"))):
        raise SystemExit("Este projeto nao e de uma impressora Anycubic: adapta-o primeiro com adaptar.py")
    placas = {int(re.search(r'plater_id" value="(\d+)"', p).group(1)): p for p in re.findall(r"  <plate>.*?</plate>\n", ms, re.S)}
    n_orig = len(placas)
    faltam = [p for p in pratos if p not in placas]
    if faltam:
        raise SystemExit(f"O projeto so tem os pratos {sorted(placas)}")
    if len(set(pratos)) != len(pratos):
        raise SystemExit("Ha pratos repetidos na lista")

    def slot(i, n):        # coluna, linha (a linha cresce para y negativo)
        c = colunas(n)
        return (i - 1) % c, (i - 1) // c

    obj_prato = {}
    for i, p in placas.items():
        for oid in re.findall(r'object_id" value="(\d+)"', p):
            if oid in obj_prato:
                # copias do mesmo objeto (instancias) em mais de um sitio: aqui cada objeto so pode ter um prato
                raise SystemExit("Este projeto tem copias do mesmo objeto (instancias): usa pratos.py --mover para as arrumar, "
                                 "ou separa os pratos no Anycubic")
            obj_prato[oid] = i
    novo_id = {old: k + 1 for k, old in enumerate(pratos)}
    manter = {o for o, i in obj_prato.items() if i in pratos}

    def desloc(oid):
        i = obj_prato[oid]
        (c0, l0), (c1, l1) = slot(i, n_orig), slot(novo_id[i], len(pratos))
        return (c1 - c0) * K.PASSO_X, -(l1 - l0) * K.PASSO_Y

    print("objetos mantidos:", sorted(manter, key=int))
    m = zi.read("3D/3dmodel.model").decode("utf-8")
    # posicao de cada objeto no projeto (1, 2, ...): e por ela que o ficheiro das alturas de camada variaveis os conhece
    ordem = list(dict.fromkeys(re.findall(r'<item\s[^>]*?objectid="(\d+)"', m)))
    ficam = [o for o in ordem if o not in obj_prato or o in manter]
    nova_pos = {ordem.index(o) + 1: ficam.index(o) + 1 for o in ficam}
    for oid in set(obj_prato) - manter:
        m, n = re.subn(r'\s*<object id="%s" .*?</object>' % oid, "", m, flags=re.S)
        m, n = re.subn(r'\s*<item objectid="%s" [^>]*/>' % oid, "", m)

    def mexe_item(mm):
        oid, t = mm.group(1), mm.group(3).split()
        if oid not in obj_prato:
            return mm.group(0)
        dx, dy = desloc(oid)
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
        dx, dy = desloc(oid)
        t[9] = repr(float(t[9]) + dx)
        t[10] = repr(float(t[10]) + dy)
        return mm.group(0).replace(mm.group(2), " ".join(t))
    ms = re.sub(r'<assemble_item object_id="(\d+)" instance_id="0" transform="([^"]+)"', mexe_asm, ms)
    ren = {}
    for i in placas:
        for base in ("plate_", "plate_no_light_", "top_", "pick_"):
            for suf in ((".png", "_small.png") if base == "plate_" else (".png",)):
                ren[f"Metadata/{base}{i}{suf}"] = f"Metadata/{base}{novo_id[i]}{suf}" if i in pratos else None
    copia = K.guarda_copia(dst, "separar pratos")
    tmp = dst + ".novo"
    zo = zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED)
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
        elif nome == "Metadata/custom_gcode_per_layer.xml":   # trocas de cor / pausas por camada: so as dos pratos que ficam
            def bloco(mm):
                pid = re.search(r'<plate_info id="(\d+)"', mm.group(0))
                if not pid or int(pid.group(1)) not in novo_id:
                    return ""
                return mm.group(0).replace(pid.group(0), f'<plate_info id="{novo_id[int(pid.group(1))]}"')
            d = re.sub(r"<plate>.*?</plate>[ \t]*\r?\n?", bloco, d.decode("utf-8"), flags=re.S).encode("utf-8")
        elif nome == "Metadata/layer_heights_profile.txt":    # alturas de camada variaveis: so as dos objetos que ficam
            linhas = []
            for l in d.decode("utf-8").splitlines():
                mm = re.match(r"object_id=(\d+)\|", l)
                if not mm:
                    linhas.append(l)
                elif int(mm.group(1)) in nova_pos:
                    linhas.append(f"object_id={nova_pos[int(mm.group(1))]}|" + l[mm.end():])
            d = ("\n".join(linhas) + "\n").encode("utf-8") if linhas else b""
        elif nome == "Metadata/project_settings.config":   # torre de purga: uma posicao por prato
            j = json.loads(d)
            for key in ("wipe_tower_x", "wipe_tower_y"):
                if isinstance(j.get(key), list) and len(j[key]) == n_orig:
                    j[key] = [j[key][p - 1] for p in pratos]
            d = json.dumps(j, indent=4, ensure_ascii=False).encode("utf-8")
        if nome == "Metadata/layer_heights_profile.txt" and not d:
            continue                                      # nenhum dos objetos que ficam tinha alturas variaveis
        zo.writestr(it, d)
    zo.close()
    zi.close()
    os.replace(tmp, dst)
    print("ok", dst)
    if copia:
        print("COPIA DO FICHEIRO ANTERIOR:", copia, "(desfazer.py repoe)")


if __name__ == "__main__":
    main()
