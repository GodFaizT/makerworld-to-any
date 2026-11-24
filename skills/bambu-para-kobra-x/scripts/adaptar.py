"""Adapta um projeto 3MF do Bambu Studio / MakerWorld para a Anycubic Kobra X (bico 0.4).

Uso:
    python adaptar.py "<original.3mf>" [--saida PASTA] [--processo "0.16mm High Quality"]
                      [--filamentos "Anycubic PLA Matte;Anycubic PLA"] [--cores "#FFFFFF;#800020"]
                      [--substituir] [--arquivar-original PASTA] [--sem-fatiar]

O que faz:
  1. Le o projeto: impressora, perfil, filamentos e quais sao mesmo usados, pratos, objetos.
  2. Prepara uma copia: nomes de prato vazios (com nome o Anycubic rebenta) e filamentos usados renumerados 1..n.
  3. Escolhe o perfil da Kobra X com a mesma altura de camada e passa as definicoes do autor (as que ele mudou
     e as de "intencao": paredes, enchimento, suportes, brim, costura, ironing, fuzzy skin...).
  4. O Anycubic cria o projeto (formato dele) a partir do 3MF original: mantem pecas, modificadores, pintura,
     pratos, camadas variaveis e os creditos do autor.
  5. Corrige o que a linha de comandos deixa mal: filamentos a mais, matriz de purga, torre de purga desligada,
     lista de definicoes alteradas.
  6. Confere medidas (iguais ao original), se tudo cabe na mesa de 260 mm, e fatia todos os pratos.
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
import kobrax as K

# definicoes que dizem como a peca deve ser impressa: passam sempre que diferem do perfil da Kobra X
INTENCAO = ["layer_height", "wall_loops", "top_shell_layers", "bottom_shell_layers", "sparse_infill_density",
            "sparse_infill_pattern", "enable_support", "support_type", "support_threshold_angle",
            "support_on_build_plate_only", "brim_type", "raft_layers", "spiral_mode", "ironing_type", "fuzzy_skin",
            "print_sequence", "seam_position"]
# do que o autor mudou, isto e da impressora dele (dinamica, posicao da torre, g-code) e nao passa
IGNORAR = re.compile(r"^(wipe_tower_[xy]|prime_tower_.*|enable_prime_tower|compatible_.*|inherits|.*_settings_id|"
                     r".*gcode.*|timelapse.*|thumbnails.*|filename_format|post_process|machine_.*|printer_.*|"
                     r"nozzle_.*|bed_.*|default_acceleration|.*acceleration.*|.*jerk.*|accel_to_decel.*|"
                     r"initial_layer_print_height|.*_filament)$")


def normaliza(k, v, sis):
    if isinstance(v, list) and not isinstance(sis.get(k), list):
        v = v[0] if v else ""
    elif not isinstance(v, list) and isinstance(sis.get(k), list):
        v = [v]
    if k.endswith("_pattern") and v == "zig-zag":
        v = "zigzag"
    if k == "support_style" and v == "tree_organic":
        return None            # o Anycubic 2.0 nao tem arvore organica: fica o estilo da Kobra X
    return v


TIPOS = {"High Quality": "High Quality", "Optimal": "High Quality", "Fine": "High Quality", "Extra Fine": "High Quality"}


def escolhe_processo(j, pedido=None):
    """Perfil base do autor com o mesmo nome na Kobra X (as mudancas dele sao relativas a esse perfil, e a altura
    de camada dele passa como mudanca); senao o perfil da Kobra X com a altura de camada mais proxima."""
    kx = [n for n in K.nomes("process") if n.endswith(K.SUF)]
    if pedido:
        n = pedido if pedido.endswith(K.SUF) else pedido + K.SUF
        if n not in kx:
            raise SystemExit(f"Perfil '{n}' nao existe. Ha: " + ", ".join(x.replace(K.SUF, "") for x in kx))
        return n
    lh = float(K.primeiro(j.get("layer_height", "0.2")))
    m = re.match(r"\s*(\d+\.\d+)mm ([A-Za-z ]+?)\s*@", str(K.primeiro(j.get("print_settings_id", ""))))
    if m:
        tipo = next((v for c, v in TIPOS.items() if c == m.group(2).strip()), "Standard")
        for c in (f"{float(m.group(1)):.2f}mm {tipo}{K.SUF}", f"{float(m.group(1)):.2f}mm Standard{K.SUF}"):
            if c in kx:
                return c
    std = [n for n in kx if "Standard" in n]
    return min(std, key=lambda n: abs(float(n.split("mm")[0]) - lh))


def mudancas_processo(j, sis):
    diffs = [k for k in str(K.primeiro(j.get("different_settings_to_system", [""])) or "").split(";") if k]
    mud, ignorados = {}, []
    for k in diffs:
        if IGNORAR.match(k) or k not in sis:
            ignorados.append(k)
            continue
        v = normaliza(k, j.get(k), sis)
        if v is None:
            ignorados.append(k)
        elif str(v) != str(sis.get(k)):
            mud[k] = v
    for k in INTENCAO:
        if k in j and k in sis and k not in mud:
            v = normaliza(k, j[k], sis)
            if v is not None and str(v) != str(sis.get(k)):
                mud[k] = v
    return mud, ignorados, diffs


def filamento_kx(nome_b, tipo):
    n, t = (nome_b or "").lower(), (tipo or "PLA").upper()
    if "PETG" in t:
        c = "Anycubic PETG-CF" if "cf" in n else "Anycubic PETG"
    elif t in ("ABS", "ASA", "PVA"):
        c = "Anycubic " + t
    elif "TPU" in t:
        c = "Anycubic TPU 95A"
    elif "PLA" in t or not t:
        c = "Anycubic PLA"
        for chave, kx in (("matte", "Anycubic PLA Matte"), ("silk", "Anycubic PLA Silk"), ("wood", "Anycubic PLA Wood"),
                          ("glow", "Anycubic PLA Glow"), ("transl", "Anycubic PLA Translucent"), ("-cf", "Anycubic PLA-CF"),
                          (" cf", "Anycubic PLA-CF"), ("pla+", "Anycubic PLA+"), ("tough", "Anycubic PLA+"),
                          ("high speed", "Anycubic PLA High Speed")):
            if chave in n:
                c = kx
                break
    else:
        c = "Anycubic PLA"
    nome = c + K.SUF
    return nome if K.existe("filament", nome) else "Anycubic PLA" + K.SUF


def filamentos_usados(z, j, ms):
    """Indices (1..N) dos filamentos usados; pintado=True se ha pintura de cores nas malhas."""
    n = len(j.get("filament_settings_id", [])) or 1
    usados = set()
    for o in re.finditer(r'<object id="\d+">(.*?)</object>', ms, re.S):
        corpo = o.group(1)
        cab = corpo.split("<part", 1)[0]
        mo = re.search(r'key="extruder" value="(\d+)"', cab)
        eo = int(mo.group(1)) if mo and int(mo.group(1)) > 0 else 1
        partes = re.findall(r'<part id="\d+" subtype="(\w+)">(.*?)</part>', corpo, re.S)
        if not partes:
            usados.add(eo)
        for sub, pc in partes:
            mp = re.search(r'key="extruder" value="(\d+)"', pc)
            e = int(mp.group(1)) if mp and int(mp.group(1)) > 0 else eo
            if sub == "normal_part" or (sub == "modifier_part" and mp):
                usados.add(e)
        for k in K.CHAVES_FIL:
            for v in re.findall(r'key="%s" value="(\d+)"' % k, corpo):
                if int(v) > 0:
                    usados.add(int(v))
    # no perfil, wall/sparse/solid_infill_filament valem 1 por omissao (= filamento do objeto): nao contam.
    # So o filamento de suporte conta, e so com suportes ligados.
    if str(K.primeiro(j.get("enable_support", "0"))) == "1":
        for k in ("support_filament", "support_interface_filament"):
            v = K.primeiro(j.get(k))
            if v and str(v).isdigit() and int(v) > 0:
                usados.add(int(v))
    try:
        cg = z.read("Metadata/custom_gcode_per_layer.xml").decode("utf-8")
        usados |= {int(e) for e in re.findall(r'extruder="(\d+)"', cg) if int(e) > 0}
    except KeyError:
        pass
    pintado = fuzzy = suportes = costura = False
    for nome in z.namelist():
        if nome.startswith("3D/") and nome.endswith(".model"):
            t = z.read(nome)
            pintado |= b"paint_color=" in t or b"mmu_segmentation=" in t
            fuzzy |= b"paint_fuzzy_skin=" in t
            suportes |= b"paint_supports=" in t
            costura |= b"paint_seam=" in t
    usados = {u for u in usados if 1 <= u <= n} or {1}
    if pintado:
        usados = set(range(1, n + 1))
    return sorted(usados), n, dict(pintura_cores=pintado, fuzzy_pintado=fuzzy, suportes_pintados=suportes, costura_pintada=costura)


def prepara(orig, dst, mapa):
    def mudar(nome, d):
        if nome == "Metadata/model_settings.config":
            t = d.decode("utf-8")
            t = re.sub(r'(<metadata key="plater_name" value=")[^"]*(")', r"\1\2", t)
            if mapa:
                chaves = "|".join(("extruder",) + K.CHAVES_FIL)
                t = re.sub(r'(<metadata key="(?:%s)" value=")(\d+)(")' % chaves,
                           lambda m: m.group(1) + str(mapa.get(int(m.group(2)), int(m.group(2)))) + m.group(3), t)
            return t.encode("utf-8")
        if nome == "Metadata/custom_gcode_per_layer.xml" and mapa:
            t = d.decode("utf-8")
            return re.sub(r'extruder="(\d+)"', lambda m: f'extruder="{mapa.get(int(m.group(1)), int(m.group(1)))}"', t).encode("utf-8")
        return d
    K.reescreve(orig, dst, mudar)


def corrige(exp, ref, dst, n_orig, idx, proc_diff, torre):
    R = json.loads(zipfile.ZipFile(ref).read("Metadata/project_settings.config"))
    k = len(R["filament_settings_id"])
    relatorio = {"cortadas": [], "sem_regra": []}

    def mudar(nome, d):
        if nome == "Metadata/project_settings.config":
            j = json.loads(d)
            nf = len(j["filament_settings_id"])
            for key, v in list(j.items()):
                if not isinstance(v, list) or key in K.POR_PRATO:
                    continue
                r = R.get(key)
                if key == "different_settings_to_system":
                    continue
                if key == "flush_volumes_matrix":
                    if k == 1 and isinstance(r, list):
                        j[key] = r
                    elif len(v) in (nf * nf, 2 * nf * nf) and isinstance(r, list) and len(r) == k * k:
                        j[key] = [v[a * nf + b] for a in idx for b in idx]
                    elif isinstance(r, list) and len(r) != len(v):
                        j[key] = r
                    continue
                if key == "flush_volumes_vector":
                    if isinstance(r, list) and len(r) != len(v):
                        j[key] = v[:2 * k] if len(v) == 2 * nf and len(r) == 2 * k else r
                    continue
                if nf == k:
                    continue
                if key.endswith("_group") and len(v) == nf + 2:
                    j[key] = [v[0]] + v[1:1 + k] + [v[-1]]
                elif len(v) == nf and (r is None or (isinstance(r, list) and len(r) in (k, 1))):
                    j[key] = v[:k]
                    relatorio["cortadas"].append(key)
                elif isinstance(r, list) and len(r) != len(v):
                    relatorio["sem_regra"].append((key, len(v), len(r)))
            j["different_settings_to_system"] = [proc_diff] + [""] * k + ["machine_end_gcode"]
            if k > 1:
                j["enable_prime_tower"] = "1"
                if torre:
                    j["wipe_tower_x"] = [str(t[0]) for t in torre]
                    j["wipe_tower_y"] = [str(t[1]) for t in torre]
            relatorio["prime_tower"] = j.get("enable_prime_tower")
            return json.dumps(j, indent=4, ensure_ascii=False).encode("utf-8")
        if nome == "Metadata/model_settings.config":
            t = d.decode("utf-8")
            t = re.sub(r'(key="filament_maps" value=")[^"]*', lambda m: m.group(1) + " ".join(["1"] * k), t)
            t = re.sub(r'(key="filament_volume_maps" value=")[^"]*', lambda m: m.group(1) + " ".join(["0"] * k), t)
            return t.encode("utf-8")
        return d
    K.reescreve(exp, dst, mudar)
    return relatorio


def main():
    ap = argparse.ArgumentParser(description="Bambu Lab 3MF -> Anycubic Kobra X")
    ap.add_argument("original")
    ap.add_argument("--saida", help="pasta de saida (por omissao: 'Adaptado Kobra X' ao lado, se existir)")
    ap.add_argument("--nome", help="nome do ficheiro de saida (por omissao '<original> - Kobra X.3mf')")
    ap.add_argument("--processo", help='perfil da Kobra X, ex. "0.16mm High Quality" (por omissao: mesma altura de camada)')
    ap.add_argument("--filamentos", help='perfis Anycubic por ordem, separados por ";" (ex. "Anycubic PLA Matte;Anycubic PLA")')
    ap.add_argument("--cores", help='cores por ordem, separadas por ";" (por omissao as do autor)')
    ap.add_argument("--substituir", action="store_true", help="substitui o ficheiro de saida se ja existir")
    ap.add_argument("--arquivar-original", metavar="PASTA", help="no fim move o original para esta pasta")
    ap.add_argument("--sem-fatiar", action="store_true")
    ap.add_argument("--manter-temp", action="store_true", help="guarda a pasta temporaria (para investigar)")
    a = ap.parse_args()

    orig = os.path.abspath(a.original)
    pasta_o = os.path.dirname(orig)
    saida = a.saida
    if not saida:
        cand = [os.path.join(pasta_o, "Adaptado Kobra X"), os.path.join(os.path.dirname(pasta_o), "Adaptado Kobra X")]
        saida = next((c for c in cand if os.path.isdir(c)), pasta_o)
    nome_saida = a.nome or os.path.splitext(os.path.basename(orig))[0] + " - Kobra X.3mf"
    destino = os.path.join(saida, nome_saida)
    if os.path.exists(destino) and not a.substituir:
        raise SystemExit(f"Ja existe {destino} (usa --substituir ou --nome)")

    z = zipfile.ZipFile(orig)
    if "3D/3dmodel.model" not in z.namelist():
        raise SystemExit("Este ficheiro nao tem modelo 3D (sera um .gcode.3mf ja fatiado?)")
    j = json.loads(z.read("Metadata/project_settings.config"))
    ms = z.read("Metadata/model_settings.config").decode("utf-8") if "Metadata/model_settings.config" in z.namelist() else ""
    nomes_pratos = re.findall(r'<metadata key="plater_name" value="([^"]*)"', ms)
    usados, n_orig, pinturas = filamentos_usados(z, j, ms)
    k = len(usados)
    mapa = {old: i + 1 for i, old in enumerate(usados)} if usados != list(range(1, k + 1)) else {}
    idx = [u - 1 for u in usados]

    processo = escolhe_processo(j, a.processo)
    sis = K.perfil("process", processo)
    mud, ignorados, diffs = mudancas_processo(j, sis)
    for key in ("support_filament", "support_interface_filament"):   # filamento de suporte renumerado
        v = K.primeiro(j.get(key))
        if v and str(v).isdigit() and int(v) > 0 and key in sis:
            novo = K.normaliza_tipo(str(mapa.get(int(v), int(v))), sis[key])
            if str(novo) != str(sis[key]):
                mud[key] = novo
    proc_diff = ";".join(sorted(x for x, v in mud.items() if str(v) != str(sis.get(x))))

    fids, ftipos, fcores = j.get("filament_settings_id", []), j.get("filament_type", []), j.get("filament_colour", [])
    pedidos = [s.strip() for s in a.filamentos.split(";")] if a.filamentos else []
    cores_p = [s.strip() for s in a.cores.split(";")] if a.cores else []
    fils = []
    for i, u in enumerate(usados):
        if i < len(pedidos):
            nome = pedidos[i] if pedidos[i].endswith(K.SUF) else pedidos[i] + K.SUF
            if not K.existe("filament", nome):
                raise SystemExit(f"Filamento '{nome}' nao existe no Anycubic")
        else:
            nome = filamento_kx(fids[u - 1] if u - 1 < len(fids) else "", ftipos[u - 1] if u - 1 < len(ftipos) else "PLA")
        cor = cores_p[i] if i < len(cores_p) else (fcores[u - 1] if u - 1 < len(fcores) else "#FFFFFF")
        fils.append((nome, cor, fids[u - 1] if u - 1 < len(fids) else "?"))

    tmp = tempfile.mkdtemp(prefix="kobrax_")
    try:
        prep = os.path.join(tmp, "entrada.3mf")
        prepara(orig, prep, mapa)
        mj = K.grava_perfil(os.path.join(tmp, "machine.json"), "machine", K.MAQUINA, {"machine_end_gcode": K.FIM_GCODE})
        pj = K.grava_perfil(os.path.join(tmp, "process.json"), "process", processo, mud)
        fj = [K.grava_perfil(os.path.join(tmp, f"fil{i + 1}.json"), "filament", n, {"filament_colour": [c]})
              for i, (n, c, _) in enumerate(fils)]
        exp = os.path.join(tmp, "exportado.3mf")
        K.exporta(prep, exp, mj, pj, fj, tmp)
        ref = os.path.join(tmp, "referencia.3mf")      # projeto do Anycubic com k filamentos: comprimentos certos
        K.exporta(K.cubo_stl(os.path.join(tmp, "cubo.stl")), ref, mj, pj, fj, tmp)

        mod = K.Modelo(zipfile.ZipFile(exp))
        por_prato = K.caixas_por_prato(mod)
        torre = None
        if k > 1:
            largura = float(K.primeiro(sis.get("prime_tower_width", "35")) or 35)
            torre = []
            for p in range(1, mod.n_pratos + 1):
                pos = K.posicao_torre([K.ret(c) for c in por_prato.get(p, []) if c["printable"] != "0"], k, largura)
                torre.append(pos or (int(K.CAMA / 2), int(K.CAMA - 50)))
        final = os.path.join(tmp, "final.3mf")
        rel = corrige(exp, ref, final, n_orig, idx, proc_diff, torre)

        # ---- verificacoes
        mod_f = K.Modelo(zipfile.ZipFile(final))
        por_prato = K.caixas_por_prato(mod_f)
        avisos = K.avisos_mesa(por_prato)
        t_orig = sorted(tuple(round(x, 1) for x in c["tam"]) for c in K.Modelo(z).caixas())
        t_novo = sorted(tuple(round(x, 1) for x in c["tam"]) for c in mod_f.caixas())
        if t_orig != t_novo:
            avisos.append(f"as medidas mudaram! original {t_orig} -> novo {t_novo}")
        if rel["sem_regra"]:
            avisos.append(f"listas com comprimento inesperado (ver no Anycubic): {rel['sem_regra']}")
        if k > 4:
            avisos.append(f"usa {k} cores: uma ACE so tem 4 ranhuras")
        bocal = str(K.primeiro(j.get("nozzle_diameter", "0.4")))
        if bocal not in ("0.4", "0.40"):
            avisos.append(f"o original era para bico {bocal}; o adaptado e para bico 0.4")
        res = None
        if not a.sem_fatiar:
            res = K.fatia(final, os.path.join(tmp, "fatiado"), tmp)
            avisos += K.colisoes_torre(res, por_prato)

        os.makedirs(saida, exist_ok=True)
        shutil.copyfile(final, destino)
        arquivado = None
        if a.arquivar_original:
            os.makedirs(a.arquivar_original, exist_ok=True)
            arquivado = os.path.join(a.arquivar_original, os.path.basename(orig))
            if os.path.abspath(arquivado) != orig:
                if os.path.exists(arquivado):
                    avisos.append(f"nao movi o original: ja existe {arquivado}")
                    arquivado = None
                else:
                    z.close()
                    shutil.move(orig, arquivado)

        # ---- relatorio
        print("=" * 70)
        print("ORIGINAL :", orig)
        print("  impressora:", K.primeiro(j.get("printer_model", "")) or K.primeiro(j.get("printer_settings_id", "")),
              "| perfil:", K.primeiro(j.get("print_settings_id", "")))
        print("  pratos:", mod.n_pratos, ("| nomes: " + "; ".join(f"{i + 1}={n}" for i, n in enumerate(nomes_pratos) if n)) if any(nomes_pratos) else "")
        print(f"  filamentos no projeto: {n_orig} | usados: {usados}" + (" (pintura de cores: ficam todos)" if pinturas["pintura_cores"] else ""))
        extras = [n for n, v in (("fuzzy skin pintado", pinturas["fuzzy_pintado"]), ("suportes pintados", pinturas["suportes_pintados"]),
                                 ("costura pintada", pinturas["costura_pintada"])) if v]
        if "Metadata/layer_heights_profile.txt" in z.namelist():
            extras.append("alturas de camada variaveis (mandam sobre a altura do perfil)")
        if extras:
            print("  tem:", ", ".join(extras))
        print("ADAPTADO :", destino)
        print("  perfil:", processo)
        for key in sorted(mud):
            print(f"    {key}: {sis.get(key)} -> {mud[key]}")
        if ignorados:
            print("  definicoes do autor nao passadas (sao da impressora dele):", ", ".join(ignorados))
        for i, (n, c, b) in enumerate(fils):
            print(f"  filamento {i + 1}: {n.replace(K.SUF, '')} {c}  (era {b})")
        if k > 1:
            print("  torre de purga:", rel["prime_tower"], "| posicao por prato:", torre)
        for p, cs in sorted(por_prato.items()):
            for c in cs:
                print(f"  prato {p}: {c['nome']}: {c['tam'][0]:.1f} x {c['tam'][1]:.1f} x {c['tam'][2]:.1f} mm "
                      f"(x {c['llo'][0]:.1f}..{c['lhi'][0]:.1f}, y {c['llo'][1]:.1f}..{c['lhi'][1]:.1f})")
        if res:
            print("FATIADO:")
            print("  " + K.texto_resumo(res, [c for _, c, _ in fils]).replace("\n", "\n  "))
        if arquivado:
            print("ORIGINAL MOVIDO PARA:", arquivado)
        print("AVISOS:" if avisos else "AVISOS: nenhum")
        for av in avisos:
            print("  -", av)
    finally:
        if a.manter_temp:
            print("pasta temporaria:", tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
