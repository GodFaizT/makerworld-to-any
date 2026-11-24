"""Muda o tamanho de objetos num projeto Anycubic ja adaptado (MakerWorld to Any, Megatic).

Uso:
    python escalar.py <entrada.3mf> <saida.3mf> (--altura MM | --largura MM | --fator F) [--objeto TEXTO] [--fatiar]

  --altura MM   o objeto mais alto (dos escolhidos) fica com esta altura; os outros crescem na mesma proporcao
  --largura MM  idem para a largura (eixo X)
  --fator F     multiplica por F (ex. 0.52 = 52 %)
  --objeto TXT  so os objetos cujo nome contem TXT (sem isto: todos)

Cada objeto cresce a volta do seu centro e fica assente na mesa (mantem a rotacao). Tambem escala as alturas de
camada variaveis, volta a por a torre de purga num sitio livre e avisa se algo sai da mesa ou se as pecas se
encostam. Pode-se usar a mesma entrada e saida (substitui).
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada")
    ap.add_argument("saida")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--altura", type=float)
    g.add_argument("--largura", type=float)
    g.add_argument("--fator", type=float)
    ap.add_argument("--objeto")
    ap.add_argument("--fatiar", action="store_true")
    a = ap.parse_args()

    z = zipfile.ZipFile(a.entrada)
    K.impressora_do_projeto(json.loads(z.read("Metadata/project_settings.config")))   # mesa e passo entre pratos
    mod = K.Modelo(z)
    cx = mod.caixas()
    esc = [i for i, c in enumerate(cx) if not a.objeto or a.objeto.lower() in c["nome"].lower()]
    if not esc:
        raise SystemExit("Nenhum objeto com esse nome. Ha: " + ", ".join(c["nome"] for c in cx))
    if a.fator:
        f = a.fator
    elif a.altura:
        f = a.altura / max(cx[i]["tam"][2] for i in esc)
    else:
        f = a.largura / max(cx[i]["tam"][0] for i in esc)

    novos = {}
    for i in esc:
        c, T = cx[i], cx[i]["T"]
        mx, my = (c["lo"][0] + c["hi"][0]) / 2, (c["lo"][1] + c["hi"][1]) / 2
        novos[i] = [v * f for v in T[:9]] + [T[9] * f + mx * (1 - f), T[10] * f + my * (1 - f), T[11] * f - f * c["lo"][2]]
    oids = {cx[i]["oid"] for i in esc}
    todos = len(esc) == len(cx)
    cont = {"i": -1}

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
            if not todos:
                avisos.append("ha alturas de camada variaveis e so alguns objetos mudaram: confirma no Anycubic")
                return d
            linhas = []
            for l in d.decode().splitlines():
                if "|" not in l:
                    linhas.append(l)
                    continue
                cab, vals = l.split("|", 1)
                v = [float(x) for x in vals.split(";") if x]
                linhas.append(cab + "|" + ";".join(f"{x * f:.6f}" if k % 2 == 0 else f"{x:.6f}" for k, x in enumerate(v)))
            return "\n".join(linhas).encode()
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
        zz.close()                     # no Windows nao se pode substituir um zip ainda aberto
        nfil = len(j.get("filament_settings_id", [])) or 1
        if nfil > 1 and str(j.get("enable_prime_tower")) == "1":
            largura = float(K.primeiro(j.get("prime_tower_width", "35")) or 35)
            pos = [K.posicao_torre([K.ret(c) for c in por_prato.get(p, []) if c["printable"] != "0"], nfil, largura)
                   or (int(K.CAMA_X / 2), int(K.CAMA_Y - 50)) for p in range(1, mod2.n_pratos + 1)]

            def torre(nome, d):
                if nome != "Metadata/project_settings.config":
                    return d
                jj = json.loads(d)
                jj["wipe_tower_x"] = [str(p[0]) for p in pos]
                jj["wipe_tower_y"] = [str(p[1]) for p in pos]
                return json.dumps(jj, indent=4, ensure_ascii=False).encode("utf-8")
            K.reescreve(meio, meio, torre)
            print("torre de purga por prato:", pos)
        avisos += K.avisos_mesa(por_prato, sobreposicao=True)
        print(f"fator {f:.5f}")
        for p, cs in sorted(por_prato.items()):
            for c in cs:
                antes = next((x["tam"] for x in cx if x["oid"] == c["oid"]), None)
                print(f"prato {p}: {c['nome']}: " + (f"{antes[0]:.1f} x {antes[1]:.1f} x {antes[2]:.1f} -> " if antes else "")
                      + f"{c['tam'][0]:.1f} x {c['tam'][1]:.1f} x {c['tam'][2]:.1f} mm")
        if a.fatiar:
            res = K.fatia(meio, os.path.join(tmp, "fatiado"), tmp)
            print("FATIADO:\n  " + K.texto_resumo(res, j.get("filament_colour")).replace("\n", "\n  "))
            avisos += K.colisoes_torre(res, por_prato)
        shutil.copyfile(meio, a.saida)
        print("gravado:", os.path.abspath(a.saida))
        print("AVISOS:" if avisos else "AVISOS: nenhum")
        for av in avisos:
            print("  -", av)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
