"""Muda o tamanho de objetos num projeto Anycubic ja adaptado (MakerWorld to Any, Megatic).

Uso:
    python escalar.py <projeto.3mf> [<saida.3mf>] (--altura MM | --largura MM | --fator F) [--objeto TEXTO] [--fatiar]

  --altura MM   o objeto mais alto (dos escolhidos) fica com esta altura; os outros crescem na mesma proporcao
  --largura MM  idem para a largura (eixo X)
  --fator F     multiplica por F (ex. 0.52 = 52 %)
  --objeto TXT  so os objetos cujo nome contem TXT (sem isto: todos)

Cada objeto cresce a volta do seu centro e fica assente na mesa (mantem a rotacao). Tambem escala as alturas de
camada variaveis, volta a por a torre de purga num sitio livre e avisa se algo sai da mesa ou se as pecas ficam
encostadas (pratos.py --afastar resolve). Sem <saida.3mf> altera o proprio ficheiro e fica uma copia de seguranca
(desfazer.py repoe).
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True
import anycubic as K
import distancias


def main():
    ap = argparse.ArgumentParser(description="Mudar o tamanho num projeto Anycubic (MakerWorld to Any)")
    ap.add_argument("entrada")
    ap.add_argument("saida", nargs="?")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--altura", type=float)
    g.add_argument("--largura", type=float)
    g.add_argument("--fator", type=float)
    ap.add_argument("--objeto")
    ap.add_argument("--fatiar", action="store_true")
    a = ap.parse_args()
    destino = os.path.abspath(a.saida or a.entrada)

    z = zipfile.ZipFile(a.entrada)
    if not K.impressora_do_projeto(json.loads(z.read("Metadata/project_settings.config"))):
        raise SystemExit("Este projeto nao e de uma impressora Anycubic: adapta-o primeiro com adaptar.py")
    mod = K.Modelo(z)
    cx = mod.caixas()
    esc = [i for i, c in enumerate(cx) if not a.objeto or a.objeto.lower() in c["nome"].lower()]
    if not esc:
        raise SystemExit("Nenhum objeto com esse nome. Ha: " + ", ".join(sorted({c["nome"] for c in cx})))
    if a.fator:
        f = a.fator
    elif a.altura:
        f = a.altura / max(cx[i]["tam"][2] for i in esc)
    else:
        f = a.largura / max(cx[i]["tam"][0] for i in esc)
    if not 0.01 <= f <= 100:
        raise SystemExit(f"Fator {f:g} fora do razoavel")

    novos = {}
    for i in esc:
        c, T = cx[i], cx[i]["T"]
        mx, my = (c["lo"][0] + c["hi"][0]) / 2, (c["lo"][1] + c["hi"][1]) / 2
        novos[i] = [v * f for v in T[:9]] + [T[9] * f + mx * (1 - f), T[10] * f + my * (1 - f), T[11] * f - f * c["lo"][2]]
    oids = {cx[i]["oid"] for i in esc}
    cont = {"i": -1}
    # posicao de cada objeto no projeto (1, 2, ...): e assim que o ficheiro das alturas de camada variaveis os conhece
    ordem = list(dict.fromkeys(c["oid"] for c in cx))
    pos_esc = {ordem.index(o) + 1 for o in oids}
    # pratos em que todas as pecas mudam de tamanho (as trocas de cor por camada acompanham) ou so algumas (aviso)
    n_pratos = mod.n_pratos
    por_prato0 = {}
    for i, c in enumerate(cx):
        if c["printable"] != "0":
            por_prato0.setdefault(K.prato_de(c, n_pratos), []).append(i in novos)

    def item(m):
        cont["i"] += 1
        tag = m.group(0)
        if cont["i"] not in novos:
            return tag
        t = K.fmt_matriz(novos[cont["i"]])
        if 'transform="' in tag:
            return re.sub(r'transform="[^"]*"', f'transform="{t}"', tag)
        return tag.replace("<item ", f'<item transform="{t}" ', 1)

    avisos = []

    def mudar(nome, d):
        if nome == "3D/3dmodel.model":
            return re.sub(r"<item\s[^>]*?/?>", item, d.decode("utf-8")).encode("utf-8")
        if nome == "Metadata/model_settings.config":
            t = d.decode("utf-8")

            def asm(m):
                if m.group(1) not in oids:
                    return m.group(0)
                v = [float(x) for x in m.group(2).split()]
                return m.group(0).replace(m.group(2), K.fmt_matriz([x * f for x in v[:9]] + v[9:]))
            return re.sub(r'<assemble_item object_id="(\d+)"[^>]*?transform="([^"]+)"', asm, t).encode("utf-8")
        if nome == "Metadata/layer_heights_profile.txt":
            linhas = []
            for l in d.decode().splitlines():
                mm = re.match(r"object_id=(\d+)\|", l)
                if not mm or int(mm.group(1)) not in pos_esc:      # so os objetos que mudaram de tamanho
                    linhas.append(l)
                    continue
                v = [float(x) for x in l[mm.end():].split(";") if x]
                linhas.append(mm.group(0) + ";".join(f"{x * f:.6f}" if k % 2 == 0 else f"{x:.6f}" for k, x in enumerate(v)))
            return "\n".join(linhas).encode()
        if nome == "Metadata/custom_gcode_per_layer.xml":
            # trocas de cor / pausas a uma certa altura: sobem ou descem com as pecas
            def bloco(mm):
                pid = re.search(r'<plate_info id="(\d+)"', mm.group(0))
                if not pid or "<layer" not in mm.group(0):
                    return mm.group(0)
                mudou = por_prato0.get(int(pid.group(1)), [])
                if mudou and all(mudou):
                    return re.sub(r'(top_z=")([-\d.]+)(")', lambda z: z.group(1) + format(float(z.group(2)) * f, ".6g") + z.group(3), mm.group(0))
                if any(mudou):
                    avisos.append(f"prato {pid.group(1)}: ha trocas de cor ou pausas por camada e so algumas pecas mudaram de tamanho: "
                                  "as alturas das trocas ficaram como estavam, confirma no Anycubic")
                return mm.group(0)
            return re.sub(r"<plate>.*?</plate>", bloco, d.decode("utf-8"), flags=re.S).encode("utf-8")
        return d

    tmp = tempfile.mkdtemp(prefix="mw2any_esc_")
    try:
        meio = os.path.join(tmp, "escalado.3mf")
        K.reescreve(a.entrada, meio, mudar)
        z.close()
        zz = zipfile.ZipFile(meio)
        mod2 = K.Modelo(zz)
        por_prato = K.caixas_por_prato(mod2)
        j = json.loads(zz.read("Metadata/project_settings.config"))
        avisos += K.avisos_mesa(por_prato, sobreposicao=not distancias.disponivel())
        pegadas = {}
        if distancias.disponivel():
            av, pegadas = distancias.avisos_folgas(mod2, por_prato)
            avisos += av
        zz.close()                     # no Windows nao se pode substituir um zip ainda aberto
        nfil = len(j.get("filament_settings_id", [])) or 1
        if nfil > 1 and str(j.get("enable_prime_tower")) == "1":
            largura = float(K.primeiro(j.get("prime_tower_width", "35")) or 35)
            pos = []
            for p in range(1, mod2.n_pratos + 1):
                livre = K.posicao_torre([K.ret(c) for c in por_prato.get(p, []) if c["printable"] != "0"], nfil, largura,
                                        livre=pegadas[p].livre if p in pegadas else None)
                if not livre:
                    livre = (int(K.CAMA_X / 2), int(K.CAMA_Y - 50))
                    avisos.append(f"prato {p}: nao ha sitio livre para a torre de purga; ficou em ({livre[0]}, {livre[1]}), provavelmente em "
                                  "cima de pecas: reduz o tamanho ou divide as pecas por mais pratos (pratos.py)")
                pos.append(livre)

            def torre(nome, d):
                if nome != "Metadata/project_settings.config":
                    return d
                jj = json.loads(d)
                jj["wipe_tower_x"] = [str(p[0]) for p in pos]
                jj["wipe_tower_y"] = [str(p[1]) for p in pos]
                return json.dumps(jj, indent=4, ensure_ascii=False).encode("utf-8")
            K.reescreve(meio, meio, torre)
            print("torre de purga por prato:", pos)
        print(f"fator {f:.5f}")
        antes = {c["i"]: c["tam"] for c in cx}
        for p, cs in sorted(por_prato.items()):
            for c in cs:
                t0 = antes.get(c["i"])
                print(f"prato {p}: {c['nome']}: " + (f"{t0[0]:.1f} x {t0[1]:.1f} x {t0[2]:.1f} -> " if t0 else "")
                      + f"{c['tam'][0]:.1f} x {c['tam'][1]:.1f} x {c['tam'][2]:.1f} mm")
        if a.fatiar:
            res = K.fatia(meio, os.path.join(tmp, "fatiado"), tmp, avisos)
            print("FATIADO:\n  " + K.texto_resumo(res, j.get("filament_colour")).replace("\n", "\n  "))
            avisos += K.colisoes_torre(res, por_prato, pegadas=pegadas)
        copia = K.guarda_copia(destino, "escalar") if os.path.exists(destino) else None
        shutil.copyfile(meio, destino)
        print("gravado:", destino)
        if copia:
            print("COPIA DO FICHEIRO ANTERIOR:", copia, "(desfazer.py repoe)")
        print("AVISOS:" if avisos else "AVISOS: nenhum")
        for av in avisos:
            print("  -", av)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
