"""Adapta um projeto 3MF do Bambu Studio / MakerWorld para uma impressora Anycubic (por omissao a Kobra X).
MakerWorld to Any - feito pela Megatic (https://megatic.pt).

Uso:
    python adaptar.py "<original.3mf>" [--impressora "Kobra S1"] [--bico 0.4] [--saida PASTA]
                      [--processo "0.16mm High Quality"] [--filamentos "Anycubic PLA Matte;Anycubic PLA"]
                      [--cores "#FFFFFF;#800020"] [--substituir] [--arquivar-original PASTA] [--sem-fatiar]
    python adaptar.py --listar-impressoras
    python adaptar.py --listar-perfis            (os perfis que o utilizador guardou no Anycubic Slicer Next)

Perfis: --perfis sistema (por omissao) usa os perfis de origem da Anycubic; --perfis meus usa, para cada perfil
escolhido, a versao que o utilizador guardou no slicer (se tiver uma baseada nele). Tambem se pode dar o nome de um
perfil do utilizador em --impressora, --processo ou --filamentos.

O que faz:
  1. Le o projeto: impressora, perfil, filamentos e quais sao mesmo usados, pratos, objetos.
  2. Prepara uma copia: nomes de prato vazios (com nome o Anycubic rebenta) e filamentos usados renumerados 1..n.
  3. Escolhe o perfil da impressora com o mesmo nome do perfil base do autor (ou a mesma altura de camada) e passa
     as definicoes do autor (as que ele mudou e as de "intencao": paredes, enchimento, suportes, brim, costura,
     ironing, fuzzy skin...).
  4. O Anycubic cria o projeto (formato dele) a partir do 3MF original: mantem pecas, modificadores, pintura,
     pratos, camadas variaveis e os creditos do autor.
  5. Corrige o que a linha de comandos deixa mal: filamentos a mais, matriz de purga, torre de purga desligada,
     lista de definicoes alteradas.
  6. Confere medidas (iguais ao original), se tudo cabe na mesa da impressora, e fatia todos os pratos.
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

# definicoes que dizem como a peca deve ser impressa: passam sempre que diferem do perfil da impressora
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
        return None            # o Anycubic 2.0 nao tem arvore organica: fica o estilo da impressora
    return v


TIPOS = {"High Quality": "High Quality", "Optimal": "High Quality", "Fine": "High Quality", "Extra Fine": "High Quality"}


def escolhe_processo(j, pedido=None):
    """Perfil base do autor com o mesmo nome nesta impressora (as mudancas dele sao relativas a esse perfil, e a
    altura de camada dele passa como mudanca); senao o perfil com a altura de camada mais proxima."""
    comp = K.compativeis("process")
    if not comp:
        raise SystemExit(f"Nao ha perfis de processo para {K.MAQUINA}")
    if pedido:
        if K.existe("process", pedido) and (K.meu_compativel("process", pedido) or pedido in comp.values()):
            return pedido
        base = pedido.split(" @")[0].strip()
        if base not in comp:
            raise SystemExit(f"Perfil '{base}' nao existe para {K.MAQUINA}. Ha: " + ", ".join(sorted(comp)))
        return comp[base]
    lh = float(K.primeiro(j.get("layer_height", "0.2")))
    m = re.match(r"\s*(\d+\.\d+)mm ([A-Za-z ]+?)\s*@", str(K.primeiro(j.get("print_settings_id", ""))))
    if m:
        tipo = next((v for c, v in TIPOS.items() if c == m.group(2).strip()), "Standard")
        for c in (f"{float(m.group(1)):.2f}mm {tipo}", f"{float(m.group(1)):.2f}mm Standard"):
            if c in comp:
                return comp[c]
    std = [b for b in comp if "Standard" in b and re.match(r"\d", b)] or [b for b in comp if re.match(r"\d", b)] or list(comp)
    return comp[min(std, key=lambda b: abs(float(re.match(r"[\d.]+", b).group(0)) - lh) if re.match(r"[\d.]+", b) else 9)]


def mudancas_processo(j, sis, protegidas=(), sem_altura=False):
    """Mudancas do autor a aplicar sobre o perfil `sis`. protegidas: o que o utilizador mudou no perfil dele (ganha aos
    valores "de intencao" que o autor nao mudou de proposito). sem_altura: o utilizador escolheu o perfil, a altura de
    camada e a dele."""
    diffs = [k for k in str(K.primeiro(j.get("different_settings_to_system", [""])) or "").split(";") if k]
    mud, ignorados = {}, []
    dependem_da_altura = {"layer_height", "top_shell_layers", "bottom_shell_layers"}
    for k in diffs:
        if sem_altura and k in dependem_da_altura:
            continue
        if IGNORAR.match(k) or k not in sis:
            ignorados.append(k)
            continue
        v = normaliza(k, j.get(k), sis)
        if v is None:
            ignorados.append(k)
        elif str(v) != str(sis.get(k)):
            mud[k] = v
    for k in INTENCAO:
        if sem_altura and k in dependem_da_altura or k in protegidas:
            continue
        if k in j and k in sis and k not in mud:
            v = normaliza(k, j[k], sis)
            if v is not None and str(v) != str(sis.get(k)):
                mud[k] = v
    # impressoras lentas (Kobra 1/2): as velocidades do autor (pensadas para uma Bambu) so podem baixar
    limitadas = []
    if not K.RAPIDA:
        for k in [k for k in mud if k.endswith("_speed")]:
            try:
                autor, base = float(K.primeiro(mud[k])), float(K.primeiro(sis[k]))
            except (TypeError, ValueError):
                continue                      # percentagens (ex. "50%") ficam como estao
            if autor > base:
                limitadas.append(f"{k} {autor:g} > {base:g}")
                del mud[k]
    return mud, ignorados, diffs, limitadas


VARIANTES_PLA = (("matte", "PLA Matte"), ("silk", "PLA Silk"), ("wood", "PLA Wood"), ("glow", "PLA Glow"),
                 ("transl", "PLA Translucent"), ("clear", "PLA Clear"), ("marble", "PLA Marble"), ("galaxy", "PLA Galaxy"),
                 ("metal", "PLA Metal"), ("-cf", "PLA-CF"), (" cf", "PLA-CF"), ("pla+", "PLA+"), ("tough", "PLA+"),
                 ("high speed", "PLA High Speed"))


def filamento_para(nome_b, tipo):
    """Perfil de filamento desta impressora mais parecido com o do autor (Anycubic primeiro, depois Generic)."""
    comp = K.compativeis("filament")
    n, t = (nome_b or "").lower(), (tipo or "PLA").upper()
    if "PETG" in t:
        bases = (["PETG-CF"] if "cf" in n else []) + ["PETG"]
    elif "TPU" in t:
        bases = ["TPU 95A", "TPU", "TPU for ACE"]
    elif t in ("ABS", "ASA", "PVA", "PC", "PA", "PEBA"):
        bases = [t]
    else:
        bases = [v for c, v in VARIANTES_PLA if c in n][:1]
    for b in bases + ["PLA"]:
        for marca in ("Anycubic ", "Generic "):
            if marca + b in comp:
                return comp[marca + b]
    if not comp:
        raise SystemExit(f"Nao ha perfis de filamento para {K.MAQUINA}")
    return comp[sorted(comp)[0]]


def lista_perfis():
    print("Perfis guardados no Anycubic Slicer Next (usar com --perfis meus, ou pelo nome):")
    for tipo, titulo in (("machine", "impressoras"), ("process", "processo"), ("filament", "filamentos")):
        ms = K.meus(tipo)
        print(f"  {titulo}:" + ("" if ms else " nenhum"))
        for n, b in ms:
            print(f"    {n}   (baseado em {b or '?'})")


def lista_impressoras():
    print("Impressoras Anycubic no Anycubic Slicer Next (usar com --impressora):")
    for modelo, bicos in sorted(K.maquinas().items()):
        maq = bicos.get("0.4") or next(iter(bicos.values()))
        K.usa_impressora(maq)
        print(f"  {modelo.replace('Anycubic ', ''):18s} mesa {K.CAMA_X:g} x {K.CAMA_Y:g} x {K.ALTURA_MAX:g} mm | "
              f"bicos {', '.join(sorted(bicos, key=float))} | {'ACE (varias cores)' if K.MULTICOR else 'uma cor'}")


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


def cores_por_objeto(ms, j):
    """[(nome do objeto, [cores do autor])] a partir do filamento de cada objeto/peca."""
    fcores = j.get("filament_colour", [])
    out = []
    for o in re.finditer(r'<object id="\d+">(.*?)</object>', ms, re.S):
        corpo = o.group(1)
        cab = corpo.split("<part", 1)[0]
        mn = re.search(r'key="name" value="([^"]*)"', cab)
        mo = re.search(r'key="extruder" value="(\d+)"', cab)
        eo = int(mo.group(1)) if mo and int(mo.group(1)) > 0 else 1
        es = set()
        for sub, pc in re.findall(r'<part id="\d+" subtype="(\w+)">(.*?)</part>', corpo, re.S):
            if sub == "normal_part":
                mp = re.search(r'key="extruder" value="(\d+)"', pc)
                es.add(int(mp.group(1)) if mp and int(mp.group(1)) > 0 else eo)
        out.append((mn.group(1) if mn else "?", [fcores[e - 1] if e - 1 < len(fcores) else "?" for e in sorted(es or {eo})]))
    return out


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


def corrige(exp, ref, dst, n_orig, idx, proc_diff, fil_diffs, maq_diff, torre):
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
            j["different_settings_to_system"] = [proc_diff] + (list(fil_diffs) + [""] * k)[:k] + [maq_diff]
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
    ap = argparse.ArgumentParser(description="MakerWorld to Any: Bambu Lab 3MF -> impressora Anycubic (Megatic)")
    ap.add_argument("original", nargs="?")
    ap.add_argument("--impressora", help=f'impressora Anycubic, ex. "Kobra S1", "Kobra 3 Max" (por omissao: {K.IMPRESSORA_OMISSAO})')
    ap.add_argument("--bico", help="diametro do bico (por omissao o do original, se houver perfil; senao 0.4)")
    ap.add_argument("--listar-impressoras", action="store_true", help="mostra as impressoras disponiveis e sai")
    ap.add_argument("--perfis", choices=("sistema", "meus"), default=K.PERFIS_OMISSAO,
                    help="sistema = perfis de origem da Anycubic; meus = os que guardaste no slicer, quando existem")
    ap.add_argument("--listar-perfis", action="store_true", help="mostra os perfis que guardaste no slicer e sai")
    ap.add_argument("--saida", help="pasta de saida (por omissao: 'Adaptado <impressora>' ao lado, se existir)")
    ap.add_argument("--nome", help="nome do ficheiro de saida (por omissao '<original> - <impressora>.3mf')")
    ap.add_argument("--processo", help='perfil da impressora, ex. "0.16mm High Quality" (por omissao: o do autor)')
    ap.add_argument("--filamentos", help='perfis Anycubic por ordem, separados por ";" (ex. "Anycubic PLA Matte;Anycubic PLA")')
    ap.add_argument("--cores", help='cores por ordem, separadas por ";" (por omissao as do autor)')
    ap.add_argument("--substituir", action="store_true", help="substitui o ficheiro de saida se ja existir")
    ap.add_argument("--arquivar-original", metavar="PASTA", help="no fim move o original para esta pasta")
    ap.add_argument("--sem-fatiar", action="store_true")
    ap.add_argument("--manter-temp", action="store_true", help="guarda a pasta temporaria (para investigar)")
    a = ap.parse_args()
    if a.listar_impressoras:
        lista_impressoras()
        return
    if a.listar_perfis:
        lista_perfis()
        return
    if not a.original:
        ap.error("falta o ficheiro 3MF original")

    orig = os.path.abspath(a.original)
    z = zipfile.ZipFile(orig)
    if "3D/3dmodel.model" not in z.namelist():
        raise SystemExit("Este ficheiro nao tem modelo 3D (sera um .gcode.3mf ja fatiado?)")
    j = json.loads(z.read("Metadata/project_settings.config"))

    # impressora de destino; bico: o pedido, o do nome ("Kobra X 0.6"), o do original se houver perfil, ou 0.4
    bico_orig = format(float(K.primeiro(j.get("nozzle_diameter", "0.4")) or 0.4), "g")
    if a.bico or re.search(r"\d\.\d+\s*(mm|nozzle|bico)?\s*$", a.impressora or ""):
        maquina = K.encontra_maquina(a.impressora, a.bico)
    else:
        try:
            maquina = K.encontra_maquina(a.impressora, bico_orig)
        except SystemExit:
            maquina = K.encontra_maquina(a.impressora, "0.4")
    if a.perfis == "meus" and not K.do_utilizador("machine", maquina):
        maquina = K.meu_para("machine", maquina) or maquina
    K.usa_impressora(maquina)

    pasta_o = os.path.dirname(orig)
    saida = a.saida
    if not saida:
        nomes_pasta = [f"Adaptado {K.nome_curto()}", f"Adaptado {K.MODELO.replace('Anycubic ', '')}"]
        cand = [os.path.join(b, n) for n in nomes_pasta for b in (pasta_o, os.path.dirname(pasta_o))]
        saida = next((c for c in cand if os.path.isdir(c)), pasta_o)
    nome_saida = a.nome or os.path.splitext(os.path.basename(orig))[0] + f" - {K.nome_curto()}.3mf"
    destino = os.path.join(saida, nome_saida)
    if os.path.exists(destino) and not a.substituir:
        raise SystemExit(f"Ja existe {destino} (usa --substituir ou --nome)")
    ms = z.read("Metadata/model_settings.config").decode("utf-8") if "Metadata/model_settings.config" in z.namelist() else ""
    nomes_pratos = re.findall(r'<metadata key="plater_name" value="([^"]*)"', ms)
    usados, n_orig, pinturas = filamentos_usados(z, j, ms)
    k = len(usados)
    cores_obj = []
    if k > 1 and not K.MULTICOR:
        # sem ACE nao ha troca de filamento: tudo no filamento 1 (sem comandos T1 no g-code); o relatorio diz a cor
        # que o autor deu a cada objeto, para trocar o rolo entre pratos
        cores_obj = cores_por_objeto(ms, j)
        mapa = {u: 1 for u in usados}
        usados, k = usados[:1], 1
    else:
        mapa = {old: i + 1 for i, old in enumerate(usados)} if usados != list(range(1, k + 1)) else {}
    idx = [u - 1 for u in usados]

    processo = escolhe_processo(j, a.processo)
    if a.perfis == "meus" and not K.do_utilizador("process", processo):
        processo = K.meu_para("process", processo) or processo
    sis = K.perfil("process", processo)
    mud, ignorados, diffs, limitadas = mudancas_processo(j, sis, set(K.mudancas_do_utilizador("process", processo)),
                                                         sem_altura=bool(a.processo))
    for key in ("support_filament", "support_interface_filament"):   # filamento de suporte renumerado
        v = K.primeiro(j.get(key))
        if v and str(v).isdigit() and int(v) > 0 and key in sis:
            novo = K.normaliza_tipo(str(mapa.get(int(v), int(v))), sis[key])
            if str(novo) != str(sis[key]):
                mud[key] = novo
    proc_diff = ";".join(sorted({x for x, v in mud.items() if str(v) != str(sis.get(x))}
                                | set(K.mudancas_do_utilizador("process", processo))))

    fids, ftipos, fcores = j.get("filament_settings_id", []), j.get("filament_type", []), j.get("filament_colour", [])
    pedidos = [s.strip() for s in a.filamentos.split(";")] if a.filamentos else []
    cores_p = [s.strip() for s in a.cores.split(";")] if a.cores else []
    fils = []
    for i, u in enumerate(usados):
        if i < len(pedidos):
            comp = K.compativeis("filament")
            base = pedidos[i].split(" @")[0].strip()
            if K.existe("filament", pedidos[i]) and K.meu_compativel("filament", pedidos[i]):
                nome = pedidos[i]                       # perfil do utilizador pelo nome
            elif base in comp:
                nome = comp[base]
            else:
                meus_f = [n for n, _ in K.meus("filament") if K.meu_compativel("filament", n)]
                raise SystemExit(f"Filamento '{base}' nao existe para {K.MAQUINA}. Ha: " + ", ".join(sorted(comp) + meus_f))
        else:
            nome = filamento_para(fids[u - 1] if u - 1 < len(fids) else "", ftipos[u - 1] if u - 1 < len(ftipos) else "PLA")
        if a.perfis == "meus" and not K.do_utilizador("filament", nome):
            nome = K.meu_para("filament", nome) or nome
        cor = cores_p[i] if i < len(cores_p) else (fcores[u - 1] if u - 1 < len(fcores) else "#FFFFFF")
        fils.append((nome, cor, fids[u - 1] if u - 1 < len(fids) else "?"))

    tmp = tempfile.mkdtemp(prefix="mw2any_")
    try:
        prep = os.path.join(tmp, "entrada.3mf")
        prepara(orig, prep, mapa)
        fim = K.fim_gcode()
        mj = K.grava_perfil(os.path.join(tmp, "machine.json"), "machine", K.MAQUINA, {"machine_end_gcode": fim} if fim else {})
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
                torre.append(pos or (int(K.CAMA_X / 2), int(K.CAMA_Y - 50)))
        final = os.path.join(tmp, "final.3mf")
        fil_diffs = [";".join(K.mudancas_do_utilizador("filament", n)) for n, _, _ in fils]
        maq_diff = ";".join(sorted(set(K.mudancas_do_utilizador("machine", K.MAQUINA)) | ({"machine_end_gcode"} if fim else set())))
        rel = corrige(exp, ref, final, n_orig, idx, proc_diff, fil_diffs, maq_diff, torre)

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
        if cores_obj:
            avisos.append(f"a {K.MODELO} nao tem ACE: ficou tudo num filamento so. Cores do autor por objeto (trocar o "
                          "rolo entre pratos): " + "; ".join(dict.fromkeys(f"{n}: {'+'.join(c)}" for n, c in cores_obj)))
            varias = [n for n, c in cores_obj if len(set(c)) > 1]
            if varias or pinturas["pintura_cores"]:
                avisos.append("estes objetos tinham varias cores e saem numa so: " + (", ".join(varias) or "pintura de cores"))
        if k > 4:
            avisos.append(f"usa {k} cores: uma ACE so tem 4 ranhuras")
        if bico_orig != K.BICO:
            avisos.append(f"o original era para bico {bico_orig}; o adaptado e para bico {K.BICO}")
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
        teu = lambda t, n: f" (perfil teu, baseado em '{K.raiz_sistema(t, n)}')" if K.do_utilizador(t, n) else ""
        print(f"  impressora: {K.MODELO} (bico {K.BICO}, mesa {K.CAMA_X:g} x {K.CAMA_Y:g} x {K.ALTURA_MAX:g} mm"
              f"{', com ACE' if K.MULTICOR else ', sem ACE'})" + (" | fim de impressao: levanta o bico" if fim else "")
              + (f" | maquina: '{K.MAQUINA}'" + teu("machine", K.MAQUINA) if K.do_utilizador("machine", K.MAQUINA) else ""))
        print(f"  perfis: {'os teus, quando existem' if a.perfis == 'meus' else 'de origem da Anycubic'}")
        print("  perfil:", processo + teu("process", processo))
        for key in sorted(mud):
            print(f"    {key}: {sis.get(key)} -> {mud[key]}")
        if ignorados:
            print("  definicoes do autor nao passadas (sao da impressora dele):", ", ".join(ignorados))
        if limitadas:
            print(f"  velocidades do autor acima das da {K.MODELO} (ficam as da impressora):", ", ".join(limitadas))
        for i, (n, c, b) in enumerate(fils):
            print(f"  filamento {i + 1}: {n.replace(K.SUF, '')} {c}  (era {b})" + teu("filament", n))
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
