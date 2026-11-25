"""Adapta um projeto 3MF do Bambu Studio / MakerWorld para uma impressora Anycubic (por omissao a Kobra X).
MakerWorld to Any - feito pela Megatic (https://megatic.pt).

Uso:
    python adaptar.py "<original.3mf>" [--impressora "Kobra S1"] [--bico 0.4] [--saida PASTA]
                      [--processo "0.16mm High Quality"] [--material PETG] [--cores "#FFFFFF;#800020"]
                      [--perfis meus] [--sem-camadas-variaveis] [--gcode PASTA] [--json] [--substituir] ...
    python adaptar.py --listar-impressoras
    python adaptar.py --listar-perfis            (os perfis que o utilizador guardou no Anycubic Slicer Next)

O que faz:
  1. Le o projeto: impressora, perfil, filamentos e quais sao mesmo usados, pratos, objetos.
  2. Prepara uma copia: nomes de prato vazios (com nome o Anycubic rebenta) e filamentos usados renumerados 1..n.
  3. Escolhe o perfil da impressora com o mesmo nome do perfil base do autor (ou a mesma altura de camada) e passa
     as definicoes do autor que dizem respeito ao modelo (paredes, enchimento, suportes, ironing, fuzzy skin...).
     As velocidades do autor nunca passam acima das do perfil da impressora.
  4. O Anycubic cria o projeto (formato dele) a partir do 3MF original: mantem pecas, modificadores, pintura,
     pratos, camadas variaveis e os creditos do autor.
  5. Corrige o que a linha de comandos deixa mal: filamentos a mais, matriz de purga (recalculada para as cores que
     mudaram), torre de purga desligada, lista de definicoes alteradas.
  6. Confere medidas (iguais ao original), se tudo cabe na mesa, a folga real entre pecas, e fatia todos os pratos.

Tambem aceita um projeto Anycubic ja adaptado (para mudar cores, material ou impressora): nesse caso ficam os perfis
que o projeto ja tinha, salvo o que for pedido.
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import types
import zipfile

sys.dont_write_bytecode = True
import anycubic as K
import distancias
import pecas
import purga

# definicoes que dizem como a peca deve ser impressa: passam sempre que diferem do perfil da impressora
INTENCAO = ["layer_height", "wall_loops", "top_shell_layers", "bottom_shell_layers", "sparse_infill_density",
            "sparse_infill_pattern", "enable_support", "support_type", "support_threshold_angle",
            "support_on_build_plate_only", "brim_type", "raft_layers", "spiral_mode", "ironing_type", "fuzzy_skin",
            "print_sequence", "seam_position"]
# do que o autor mudou, isto e da impressora dele (dinamica, g-code) e nao passa
IGNORAR = re.compile(r"^(compatible_.*|inherits|.*_settings_id|.*gcode.*|timelapse.*|thumbnails.*|filename_format|"
                     r"post_process|machine_.*|printer_.*|nozzle_.*|bed_.*|default_acceleration|.*acceleration.*|"
                     r".*jerk.*|accel_to_decel.*|initial_layer_print_height)$")
# e isto e a skill que trata (torre de purga, filamento de cada funcao): nao aparece no relatorio
TRATADAS = re.compile(r"^(wipe_tower_[xy]|prime_tower_.*|enable_prime_tower|.*_filament)$")
# num projeto que ja e desta impressora passa tudo (tambem a largura da torre...) menos o que identifica os perfis
TRATADAS_PROPRIO = re.compile(r"^(wipe_tower_[xy]|enable_prime_tower|.*_filament)$")
NUNCA = re.compile(r"^(compatible_.*|inherits|.*_settings_id|from|name|version)$")
# comandos que um slicer corre no computador depois de fatiar: nunca passam, venha o projeto de onde vier
PERIGOSAS = re.compile(r"^(post_process)$")
# velocidades que fazem parte de uma "receita" do autor (com o fluxo e o espacamento do ironing): passam como estao
VELOCIDADES_LIVRES = {"ironing_speed"}


def normaliza(k, v, sis):
    if isinstance(v, list) and not isinstance(sis.get(k), list):
        v = v[0] if v else ""
    elif not isinstance(v, list) and isinstance(sis.get(k), list):
        v = [v]
    if k.endswith("_pattern") and v == "zig-zag":
        v = "zigzag"
    if k == "support_style" and v == "tree_organic":
        v = "default"          # no Anycubic 2.0 a arvore organica e o estilo "default" dos suportes em arvore
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
    lh = float(K.primeiro(j.get("layer_height", "0.2")) or 0.2)
    m = re.match(r"\s*(\d+\.\d+)mm ([A-Za-z ]+?)\s*@", str(K.primeiro(j.get("print_settings_id", ""))))
    if m:
        tipo = next((v for c, v in TIPOS.items() if c == m.group(2).strip()), "Standard")
        for c in (f"{float(m.group(1)):.2f}mm {tipo}", f"{float(m.group(1)):.2f}mm Standard"):
            if c in comp:
                return comp[c]
    std = [b for b in comp if "Standard" in b and re.match(r"\d", b)] or [b for b in comp if re.match(r"\d", b)] or list(comp)
    return comp[min(std, key=lambda b: abs(float(re.match(r"[\d.]+", b).group(0)) - lh) if re.match(r"[\d.]+", b) else 9)]


def mudancas_processo(j, sis, protegidas=(), sem_altura=False, proprio=False):
    """Mudancas do autor a aplicar sobre o perfil `sis`.
    protegidas: o que o utilizador mudou no perfil dele (ganha aos valores "de intencao" que o autor nao mudou de
    proposito). sem_altura: o utilizador escolheu o perfil, a altura de camada e a dele.
    proprio: o projeto ja e desta impressora e deste perfil (mudar cores ou material de um projeto adaptado): passa
    tudo o que la estava mudado, incluindo o que o utilizador afinou a mao no slicer, sem filtros nem limite de
    velocidade.
    Devolve (mudancas, origem de cada uma: "autor" | "perfil" | "projeto", o que nao passou por categoria, lista
    do autor). Os scripts de pos-processamento (post_process) nunca passam: categoria "seguranca"."""
    diffs = [k for k in str(K.primeiro(j.get("different_settings_to_system", [""])) or "").split(";") if k]
    mud, origem = {}, {}
    nao = {"impressora": [], "sem_equivalente": [], "velocidades": [], "seguranca": []}
    if K.tem_pos_processamento(j):
        nao["seguranca"].append("post_process")
    dependem_da_altura = {"layer_height", "top_shell_layers", "bottom_shell_layers"}
    for k in diffs:
        if (sem_altura and k in dependem_da_altura) or (TRATADAS_PROPRIO if proprio else TRATADAS).match(k) or PERIGOSAS.match(k):
            continue
        if proprio:
            if NUNCA.match(k):
                continue
            if k == "filename_format" and re.search(r"[\\/:]|\.\.", str(K.primeiro(j.get(k)) or "")):
                nao["seguranca"].append(k)        # um nome de ficheiro com pastas la dentro nao e so um nome
                continue
        elif IGNORAR.match(k):
            nao["impressora"].append(k)
            continue
        if k not in sis:
            nao["sem_equivalente"].append(k)
            continue
        v = normaliza(k, j.get(k), sis)
        if v is None:
            nao["sem_equivalente"].append(f"{k}={K.primeiro(j.get(k))}")
        elif str(v) != str(sis.get(k)):
            mud[k], origem[k] = v, "projeto" if proprio else "autor"
    for k in INTENCAO:
        if sem_altura and k in dependem_da_altura or k in protegidas:
            continue
        if k in j and k in sis and k not in mud:
            v = normaliza(k, j[k], sis)
            if v is not None and str(v) != str(sis.get(k)):
                mud[k], origem[k] = v, "perfil"
    # as velocidades do autor (pensadas para a impressora dele) so podem baixar: nunca acima do perfil desta impressora
    for k in [k for k in mud if k.endswith("_speed") and k not in VELOCIDADES_LIVRES and not proprio]:
        try:
            autor, base = float(K.primeiro(mud[k])), float(K.primeiro(sis[k]))
        except (TypeError, ValueError):
            continue                      # percentagens (ex. "50%") ficam como estao
        if autor > base:
            nao["velocidades"].append(f"{k} {autor:g} > {base:g}")
            del mud[k]
            origem.pop(k, None)
    return mud, origem, nao, diffs


# variantes de PLA reconhecidas pelo nome do filamento do autor (Bambu PLA Matte, Silk+, Galaxy...)
VARIANTES_PLA = (("matte", "PLA Matte"), ("silk", "PLA Silk"), ("wood", "PLA Wood"), ("glow", "PLA Glow"),
                 ("transl", "PLA Translucent"), ("clear", "PLA Clear"), ("marble", "PLA Marble"),
                 ("galaxy", "PLA Galaxy"), ("sparkle", "PLA Galaxy"), ("metal", "PLA Metal"),
                 ("pla+", "PLA+"), ("pla plus", "PLA+"), ("tough", "PLA+"), ("high speed", "PLA High Speed"),
                 ("pla se", "PLA SE"))
# material -> perfis Anycubic/Generic por ordem de preferencia (o primeiro que a impressora tiver)
MATERIAIS = {
    "PLA": ["PLA", "PLA+"],
    "PLA-CF": ["PLA-CF", "PLA"],
    "PETG": ["PETG"],
    "PETG-CF": ["PETG-CF", "PETG"],
    "PCTG": ["PETG"],
    "PET-CF": ["PET-CF", "PETG-CF", "PETG"],
    "ABS": ["ABS"],
    "ASA": ["ASA", "ABS"],
    "PC": ["PC", "PC-GF", "PC-CF"],
    "PC-CF": ["PC-CF", "PC"],
    "PC-GF": ["PC-GF", "PC"],
    "PA": ["PA", "PAHT-CF", "PA6-CF"],
    "PA-CF": ["PA6-CF", "PAHT-CF", "PA"],
    "PAHT-CF": ["PAHT-CF", "PA6-CF", "PA"],
    "TPU": ["TPU 95A", "TPU", "TPU for ACE"],
    "TPU-ACE": ["TPU for ACE", "TPU 95A", "TPU"],
    "PEBA": ["PEBA 95A", "PEBA"],
    "PVA": ["PVA"],
}
# notas por material (aparecem no relatorio)
NOTAS = {
    "fibra": "material com fibra (CF/GF): usa um bico endurecido; o de latao gasta-se depressa",
    "fechada": "ABS/ASA/PC/PA: imprime com a impressora fechada (ou numa caixa) e sem correntes de ar, para nao empenar",
    "tpu": "TPU e flexivel: imprime devagar a partir de uma bobine externa; so pela ACE com o perfil 'TPU for ACE'",
    "pva": "PVA dissolve-se em agua: guarda-o bem seco",
    "suporte": "o autor usava um material so para suportes (Support for PLA/PA): ficou o material normal; os suportes saem mais presos",
}


def familia(x):
    """'PA6-CF' -> 'PA', 'PAHT-CF' -> 'PA', 'PLA Matte' -> 'PLA', 'PETG-CF' -> 'PETG' (PET e PETG sao diferentes)."""
    f = re.sub(r"\d", "", x.upper().split()[0].split("-")[0])
    return "PA" if f.startswith("PAHT") else f


def material_de(nome_b, tipo):
    """(material, variante PLA ou None, suporte?) a partir do filamento do autor (tipo da Bambu + nome)."""
    n, t = (nome_b or "").lower(), (tipo or "PLA").upper().replace(" ", "")
    suporte = t in ("PLA-S", "PA-S", "SUPPORT") or "support" in n
    if suporte:
        t = "PA" if t.startswith("PA") else "PLA"
    cf = "-cf" in n or " cf" in n or t.endswith("-CF")
    gf = "-gf" in n or " gf" in n or t.endswith("-GF")
    if t.startswith("PLA"):
        mat = "PLA-CF" if cf else "PLA"
    elif t.startswith("PCTG"):
        mat = "PCTG"
    elif t.startswith("PETG") or t == "PET":
        mat = "PETG-CF" if cf else "PETG"
    elif t.startswith("PET"):
        mat = "PET-CF"
    elif t.startswith("ABS"):
        mat = "ABS"
    elif t.startswith("ASA"):
        mat = "ASA"
    elif t.startswith("PC"):
        mat = "PC-CF" if cf else "PC-GF" if gf else "PC"
    elif t.startswith("PAHT"):
        mat = "PAHT-CF"
    elif t.startswith("PA"):
        mat = "PA-CF" if cf else "PA"
    elif t.startswith("TPU") or t.startswith("TPE"):
        mat = "TPU-ACE" if ("ams" in n or "ace" in n or "AMS" in t) else "TPU"
    elif t.startswith("PEBA"):
        mat = "PEBA"
    elif t.startswith("PVA") or t.startswith("BVOH"):
        mat = "PVA"
    else:
        mat = None                       # HIPS, PP, PE, PPS, PPA... sem perfil Anycubic
    variante = next((v for c, v in VARIANTES_PLA if c in n), None) if mat == "PLA" else None
    return mat, variante, suporte


def notas_de(mat, suporte=False):
    notas = []
    if mat and ("CF" in mat or "GF" in mat):
        notas.append(NOTAS["fibra"])
    if mat in ("ABS", "ASA", "PC", "PC-CF", "PC-GF", "PA", "PA-CF", "PAHT-CF"):
        notas.append(NOTAS["fechada"])
    if mat in ("TPU", "TPU-ACE", "PEBA"):
        notas.append(NOTAS["tpu"])
    if mat == "PVA":
        notas.append(NOTAS["pva"])
    if suporte:
        notas.append(NOTAS["suporte"])
    return notas


def filamento_para(nome_b, tipo):
    """(perfil desta impressora mais parecido com o do autor, aviso ou None, notas)."""
    comp = K.compativeis("filament")
    if not comp:
        raise SystemExit(f"Nao ha perfis de filamento para {K.MAQUINA}")
    mat, variante, suporte = material_de(nome_b, tipo)
    bases = ([variante] if variante else []) + MATERIAIS.get(mat, [])
    notas = notas_de(mat, suporte)
    for b in bases:
        for marca in ("Anycubic ", "Generic "):
            if marca + b in comp:
                aviso = None
                if mat and (familia(b) != familia(mat) or ("CF" in mat and "CF" not in b)) and not b.startswith("TPU"):
                    aviso = f"'{nome_b}' ({mat}): a {K.MODELO} nao tem perfil de {mat}, ficou {marca + b}"
                return comp[marca + b], aviso, notas
    for marca in ("Anycubic ", "Generic "):              # material sem perfil nesta impressora
        if marca + "PLA" in comp:
            return comp[marca + "PLA"], (f"'{nome_b}' ({mat or tipo}): a {K.MODELO} nao tem perfil para este material; "
                                         f"ficou {marca}PLA - confirma o material ou escolhe outro com --material/--filamentos"), notas
    return comp[sorted(comp)[0]], f"'{nome_b}': sem perfil equivalente, ficou {sorted(comp)[0]}", notas


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


def filamentos_usados(z, j, ms, novos=()):
    """Indices (1..N) dos filamentos usados; novos = filamentos acima de N acrescentados por atribuicao de pecas."""
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
    if not ms:
        usados.add(1)
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
    usados = {u for u in usados if 1 <= u <= n or u in novos} or {1}
    if pintado:
        usados |= set(range(1, n + 1))
    return sorted(usados), n, dict(pintura_cores=pintado, fuzzy_pintado=fuzzy, suportes_pintados=suportes, costura_pintada=costura)


def cores_por_objeto(ms, j):
    """[(nome do objeto, [cores do autor])] a partir do filamento de cada objeto/peca."""
    fcores = j.get("filament_colour", [])
    out = []
    for o in pecas.le(ms):
        es = sorted({p["efetivo"] for p in o["pecas"] if p["tipo"] == "normal_part"} or {o["efetivo"]})
        out.append((o["nome"] or "?", [fcores[e - 1] if e - 1 < len(fcores) else "?" for e in es]))
    return out


def remapeia(ms, mapa):
    """Renumera os filamentos no model_settings (extruder e filamento por funcao)."""
    if not mapa or not ms:
        return ms
    chaves = "|".join(("extruder",) + K.CHAVES_FIL)
    return re.sub(r'(<metadata key="(?:%s)" value=")(\d+)(")' % chaves,
                  lambda m: m.group(1) + str(mapa.get(int(m.group(2)), int(m.group(2)))) + m.group(3), ms)


def prepara(orig, dst, ms_novo, mapa, camadas_variaveis=True):
    """Copia do original pronta para a linha de comandos do Anycubic."""
    def mudar(nome, d):
        if nome == "Metadata/model_settings.config":
            return re.sub(r'(<metadata key="plater_name" value=")[^"]*(")', r"\1\2", ms_novo).encode("utf-8")
        if nome == "Metadata/custom_gcode_per_layer.xml" and mapa:
            t = d.decode("utf-8")
            return re.sub(r'extruder="(\d+)"', lambda m: f'extruder="{mapa.get(int(m.group(1)), int(m.group(1)))}"', t).encode("utf-8")
        if nome == "Metadata/layer_heights_profile.txt" and not camadas_variaveis:
            return None
        if nome == "Metadata/project_settings.config":
            # scripts de pos-processamento do projeto: a linha de comandos recusa-os e a skill nunca os passa
            try:
                jj = json.loads(d)
            except ValueError:
                return d
            if isinstance(jj, dict) and K.sem_pos_processamento(jj):
                return json.dumps(jj, indent=4, ensure_ascii=False).encode("utf-8")
        return d
    K.reescreve(orig, dst, mudar)


def corrige(exp, ref, dst, proc_diff, fil_diffs, maq_diff, torre, matriz=None, plano=None):
    """Acerta o projeto exportado pela linha de comandos: listas por filamento, purga, torre, filamento das pecas."""
    R = json.loads(zipfile.ZipFile(ref).read("Metadata/project_settings.config"))
    k = len(R["filament_settings_id"])
    relatorio = {"cortadas": [], "sem_regra": [], "plano_falhou": []}

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
                    if k > 1 and matriz is not None:
                        j[key] = list(matriz)
                    elif isinstance(r, list):
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
            relatorio["flush_multiplier"] = K.primeiro(j.get("flush_multiplier"))
            K.sem_pos_processamento(j)
            return json.dumps(j, indent=4, ensure_ascii=False).encode("utf-8")
        if nome == "Metadata/model_settings.config":
            t = d.decode("utf-8")
            t = re.sub(r'(key="filament_maps" value=")[^"]*', lambda m: m.group(1) + " ".join(["1"] * k), t)
            t = re.sub(r'(key="filament_volume_maps" value=")[^"]*', lambda m: m.group(1) + " ".join(["0"] * k), t)
            if plano:
                # a linha de comandos repoe no filamento 1 tudo o que apontava para um filamento que o projeto de
                # entrada ainda nao tinha: volta-se a escrever o filamento de cada objeto/peca
                agora = {o["id"]: o["nome"] for o in pecas.le(t)}
                bom = {}
                for oid, alvo in plano.items():
                    if agora.get(oid) == alvo.get("nome"):
                        bom[oid] = alvo
                    else:
                        relatorio["plano_falhou"].append(alvo.get("nome") or oid)
                t = pecas.impoe(t, bom)
            return t.encode("utf-8")
        return d
    K.reescreve(exp, dst, mudar)
    return relatorio


def _hex(c, onde="--cores"):
    c2 = str(c).strip()
    if not re.fullmatch(r"#?[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", c2):
        raise SystemExit(f"Cor invalida '{c}' em {onde}: usa #RRGGBB (ex.: #800020)")
    return "#" + c2.lstrip("#").upper()


def preco_material(precos, perfil_filamento):
    """Preco por kg do filamento deste perfil: procura 'PLA Matte', depois a familia 'PLA', depois '*'."""
    if not precos:
        return None
    base = (K.raiz_sistema("filament", perfil_filamento) or perfil_filamento).split(" @")[0]
    nome = re.sub(r"^(Anycubic|Generic)\s+", "", base)
    p = {str(k).lower(): v for k, v in precos.items()}
    for c in (nome.lower(), familia(nome).lower(), "*"):
        if c in p:
            try:
                return float(p[c])
            except (TypeError, ValueError):
                return None
    return None


OMISSAO = dict(original=None, impressora=None, bico=None, perfis=None, saida=None, nome=None, processo=None,
               filamentos=None, cores=None, material=None, atribuir=None, substituir=False, arquivar_original=None,
               fatiar=True, manter_temp=False, camadas_variaveis=True, gcode=None)


def pedido(**kw):
    """Opcoes de adapta(), com os valores por omissao."""
    estranhas = set(kw) - set(OMISSAO)
    if estranhas:
        raise TypeError("opcoes desconhecidas: " + ", ".join(sorted(estranhas)))
    return types.SimpleNamespace(**dict(OMISSAO, **kw))


def adapta(a):
    """Faz a adaptacao e devolve o relatorio (dicionario). `a` vem de pedido(...) ou do argparse."""
    orig = os.path.abspath(a.original)
    if not os.path.isfile(orig):
        raise SystemExit(f"Nao encontro o ficheiro {orig}")
    try:
        z = zipfile.ZipFile(orig)
    except zipfile.BadZipFile:
        raise SystemExit(f"{os.path.basename(orig)} nao e um 3MF valido")
    conteudo = z.namelist()
    if "3D/3dmodel.model" not in conteudo:
        raise SystemExit("Este ficheiro nao tem modelo 3D (sera um .gcode.3mf ja fatiado?)")
    tem_definicoes = "Metadata/project_settings.config" in conteudo
    j = json.loads(z.read("Metadata/project_settings.config")) if tem_definicoes else {}
    ms = z.read("Metadata/model_settings.config").decode("utf-8") if "Metadata/model_settings.config" in conteudo else ""

    # ---- impressora. Bico: o pedido, o do nome ("Kobra X 0.6"), o do original se houver perfil, ou 0.4
    psid = str(K.primeiro(j.get("printer_settings_id", "")) or "")
    e_any = bool(psid) and K.existe("machine", psid)          # ja e um projeto do Anycubic
    perfis = a.perfis or (None if e_any else K.PERFIS_OMISSAO)   # num projeto Anycubic ficam os perfis que ja tinha
    bico_orig = format(float(K.primeiro(j.get("nozzle_diameter", "0.4")) or 0.4), "g")
    imp = a.impressora or K.IMPRESSORA_OMISSAO      # (a guardada pode trazer o bico: "Kobra X 0.6")
    if e_any and not a.impressora and not a.bico:
        maquina = psid
    elif a.bico or re.search(r"\d\.\d+\s*(mm|nozzle|bico)?\s*$", imp):
        maquina = K.encontra_maquina(imp, a.bico)
    else:
        try:
            maquina = K.encontra_maquina(imp, bico_orig)
        except SystemExit:
            maquina = K.encontra_maquina(imp, "0.4")
    if perfis == "meus" and not K.do_utilizador("machine", maquina):
        maquina = K.meu_para("machine", maquina) or maquina
    K.usa_impressora(maquina)
    # o projeto ja e desta maquina (mudar cores, material...): o que la esta mudado e do utilizador e fica tudo
    mesma_maquina = e_any and maquina == psid
    dts = j.get("different_settings_to_system")
    dts = [str(x) for x in dts] if isinstance(dts, list) else []      # [processo, filamento 1..n, maquina]

    # ---- onde gravar
    pasta_o = os.path.dirname(orig)
    saida = a.saida or (None if e_any else K.pasta_config("saida"))
    if not saida:
        nomes_pasta = [f"Adaptado {K.nome_curto()}", f"Adaptado {K.MODELO.replace('Anycubic ', '')}"]
        cand = [os.path.join(b, n) for n in nomes_pasta for b in (pasta_o, os.path.dirname(pasta_o))]
        saida = next((c for c in cand if os.path.isdir(c)), pasta_o)
    base_nome = os.path.splitext(os.path.basename(orig))[0]
    if e_any:
        base_nome = re.sub(r" - Kobra [^-]+$", "", base_nome)       # "Vaso - Kobra X" adaptado para outra impressora
    nome_saida = a.nome or f"{base_nome} - {K.nome_curto()}.3mf"
    destino = os.path.join(saida, nome_saida)
    mesmo = os.path.normcase(os.path.abspath(destino)) == os.path.normcase(orig)
    if os.path.exists(destino) and not a.substituir:
        raise SystemExit(f"Ja existe {destino} (usa --substituir ou --nome)")

    # ---- filamentos usados, com as atribuicoes de pecas pedidas
    regras = pecas.interpreta(a.atribuir) if a.atribuir else []
    ms_trab, feito_cores = pecas.atribui(ms, regras) if regras else (ms, [])
    nomes_pratos = re.findall(r'<metadata key="plater_name" value="([^"]*)"', ms)
    usados, n_orig, pinturas = filamentos_usados(z, j, ms_trab, {f for _, f in regras})
    usados_orig = list(usados)
    k = len(usados)
    cores_obj = []
    if k > 1 and not K.MULTICOR:
        # sem ACE nao ha troca de filamento: tudo no filamento 1 (sem comandos T1 no g-code); o relatorio diz a cor
        # que o autor deu a cada objeto, para trocar o rolo entre pratos
        cores_obj = cores_por_objeto(ms_trab, j)
        mapa = {u: 1 for u in usados}
        usados, k = usados[:1], 1
        regras = []
    else:
        mapa = {old: i + 1 for i, old in enumerate(usados)} if usados != list(range(1, k + 1)) else {}
    idx = [u - 1 if u <= n_orig else None for u in usados]       # filamento do original de cada ranhura (None = novo)
    ms_prep = remapeia(ms_trab, mapa)
    plano = pecas.plano_de(ms_prep) if regras else None

    # ---- perfil de impressao
    comp_p = K.compativeis("process")
    pid_ = str(K.primeiro(j.get("print_settings_id", "")) or "")
    if a.processo:
        processo = escolhe_processo(j, a.processo)
    elif e_any and K.existe("process", pid_) and (pid_ in comp_p.values() or K.meu_compativel("process", pid_)):
        processo = pid_
    else:
        processo = escolhe_processo(j, None)
    if perfis == "meus" and not K.do_utilizador("process", processo):
        processo = K.meu_para("process", processo) or processo
    sis = K.perfil("process", processo)
    mud, origem, nao, diffs = mudancas_processo(j, sis, set(K.mudancas_do_utilizador("process", processo)),
                                                sem_altura=bool(a.processo), proprio=mesma_maquina and processo == pid_)
    for key in ("support_filament", "support_interface_filament"):   # filamento de suporte renumerado
        v = K.primeiro(j.get(key))
        if v and str(v).isdigit() and int(v) > 0 and key in sis:
            novo = K.normaliza_tipo(str(mapa.get(int(v), int(v))), sis[key])
            if str(novo) != str(sis[key]):
                mud[key], origem[key] = novo, "autor"
    # alturas de camada variaveis + suportes em arvore organica: o Anycubic recusa-se a fatiar
    tem_variaveis = "Metadata/layer_heights_profile.txt" in conteudo and a.camadas_variaveis
    notas_proc = []
    if e_any and mapa and len(usados) > 1:
        renum = [f"{de} passou a {para}" for de, para in sorted(mapa.items()) if de != para]
        if renum:
            notas_proc.append("os filamentos que ficaram sem pecas sairam do projeto; numeros novos: filamento " + ", ".join(renum))

    def fica(chave):
        return str(K.primeiro(mud.get(chave, sis.get(chave, ""))))
    if tem_variaveis and fica("enable_support") == "1" and fica("support_type").startswith("tree") and fica("support_style") in ("default", ""):
        mud["support_style"], origem["support_style"] = K.normaliza_tipo("tree_hybrid", sis.get("support_style", "")), "skill"
        notas_proc.append("alturas de camada variaveis nao funcionam com suportes em arvore organica no Anycubic: os suportes "
                          "ficaram em arvore hibrida (tree_hybrid)")
    proc_diff = ";".join(sorted({x for x, v in mud.items() if str(v) != str(sis.get(x))}
                                | set(K.mudancas_do_utilizador("process", processo))))

    # ---- filamentos
    fids, ftipos, fcores = j.get("filament_settings_id", []), j.get("filament_type", []), j.get("filament_colour", [])
    pedidos = [s.strip() for s in a.filamentos.split(";")] if a.filamentos else []
    cores_p = [s.strip() for s in a.cores.split(";")] if a.cores else []
    comp_f = K.compativeis("filament")

    def pedido_de(lista, i, u):
        """O que foi pedido em --cores / --filamentos para o filamento u (ranhura i). Num projeto Anycubic a posicao e o
        numero do filamento (o que se ve em cores.py --listar e se usa em --atribuir); num original e a ordem dos
        filamentos usados (a ranhura em que ficam)."""
        pos = u - 1 if e_any else i
        return lista[pos] if 0 <= pos < len(lista) and lista[pos] else None
    fils, avisos_fil, notas_fil, mudou_cor, fil_extra = [], [], [], [], []
    for i, u in enumerate(usados):
        novo_fil = u > n_orig
        nb = fids[u - 1] if u - 1 < len(fids) else ""
        tb = ftipos[u - 1] if u - 1 < len(ftipos) else "PLA"
        ped = pedido_de(pedidos, i, u)
        if ped:
            base = ped.split(" @")[0].strip()
            if K.existe("filament", ped) and K.meu_compativel("filament", ped):
                nome = ped                              # perfil do utilizador pelo nome
            elif base in comp_f:
                nome = comp_f[base]
            else:
                meus_f = [n for n, _ in K.meus("filament") if K.meu_compativel("filament", n)]
                raise SystemExit(f"Filamento '{base}' nao existe para {K.MAQUINA}. Ha: " + ", ".join(sorted(comp_f) + meus_f))
            notas = notas_de(material_de(base, familia(re.sub(r"^(Anycubic|Generic)\s+", "", base)))[0])
        elif a.material:                                # "em PETG": o material pedido, com as cores do autor
            nome, av, notas = filamento_para(a.material, a.material.split()[0])
            if av:
                avisos_fil.append(av)
        elif novo_fil and fils:
            nome, notas = fils[0][0], []                # filamento acrescentado: o mesmo material do primeiro
        elif e_any and K.existe("filament", nb) and (nb in comp_f.values() or K.meu_compativel("filament", nb)):
            nome = nb                                   # projeto Anycubic: fica o filamento que ja tinha
            notas = notas_de(material_de(nb.split(" @")[0], tb)[0])
        else:
            nome, av, notas = filamento_para(nb, tb)
            if av:
                avisos_fil.append(av)
        notas_fil += [x for x in notas if x not in notas_fil]
        if perfis == "meus" and not K.do_utilizador("filament", nome):
            nome = K.meu_para("filament", nome) or nome
        cor_orig = fcores[u - 1] if u - 1 < len(fcores) and not novo_fil else None
        cor_pedida = pedido_de(cores_p, i, u)
        if cor_pedida:
            cor = _hex(cor_pedida)
        elif cor_orig:
            cor = cor_orig
        elif novo_fil:
            pos = u if e_any else i + 1
            raise SystemExit(f"O filamento {pos} e novo: da-lhe uma cor na posicao {pos} de --cores "
                             f"(ex.: --cores \"{';' * (pos - 1)}#800020\")")
        else:
            cor = "#FFFFFF"
        mudou_cor.append(cor_orig is None or purga.normaliza(cor) != purga.normaliza(cor_orig))
        fils.append((nome, cor, nb or ("novo" if novo_fil else "?")))
        extra = {}
        if mesma_maquina and nome == nb and len(dts) == n_orig + 2:
            # o mesmo filamento na mesma impressora: o que o utilizador afinou neste projeto (temperatura...) fica
            base_f = K.perfil("filament", nome)
            for key in [x for x in dts[u].split(";") if x]:
                val = j.get(key)
                if key in base_f and isinstance(val, list) and len(val) >= u and key != "filament_colour" and not NUNCA.match(key):
                    v = K.normaliza_tipo(val[u - 1], base_f[key])
                    if v != base_f[key]:              # (igual ao perfil: nao ha nada a acrescentar)
                        extra[key] = v
        fil_extra.append(extra)
    # cores ou filamentos pedidos para posicoes que nao sao de nenhum filamento usado: diz-se, nao se ignoram em silencio
    posicoes = {(u - 1 if e_any else i) for i, u in enumerate(usados)}
    for opcao, lista in (("--cores", cores_p), ("--filamentos", pedidos)):
        sobram = [f"{p + 1} ({v})" for p, v in enumerate(lista) if v and p not in posicoes]
        if sobram:
            avisos_fil.append(f"{opcao}: ficou por aplicar o que pediste para a posicao " + ", ".join(sobram) + ": nenhuma peca usa esse filamento "
                              + ("(num projeto ja adaptado a posicao e o numero do filamento, como em cores.py --listar)" if e_any
                                 else "(num original a posicao e a ordem dos filamentos usados)"))

    # ---- purga: a do autor onde as duas cores sao as dele; recalculada onde mudaram (a CLI nao a recalcula)
    matriz, recalculadas = None, []
    if k > 1:
        m_in, n_in = j.get("flush_volumes_matrix"), len(fids)
        valida = isinstance(m_in, list) and n_in > 0 and len(m_in) in (n_in * n_in, 2 * n_in * n_in)
        base = [[0] * k for _ in range(k)]
        manter = [[False] * k for _ in range(k)]
        for x in range(k):
            for y in range(k):
                if x != y and valida and idx[x] is not None and idx[y] is not None and not mudou_cor[x] and not mudou_cor[y]:
                    try:
                        base[x][y] = int(float(m_in[idx[x] * n_in + idx[y]]))
                        manter[x][y] = True
                    except (TypeError, ValueError):
                        pass
        matriz, recalculadas = purga.matriz([c for _, c, _ in fils], K.VOLUME_BICO, base, manter)

    rel = {"versao": K.versao(), "avisos": [], "notas": list(notas_fil) + notas_proc}
    tmp = tempfile.mkdtemp(prefix="mw2any_")
    abertos = []
    try:
        prep = os.path.join(tmp, "entrada.3mf")
        prepara(orig, prep, ms_prep, mapa, a.camadas_variaveis)
        fim = K.fim_gcode()
        maq_extra = {}
        if mesma_maquina and len(dts) == n_orig + 2:
            base_m = K.perfil("machine", K.MAQUINA)
            for key in [x for x in dts[-1].split(";") if x]:
                if key in j and key in base_m and not NUNCA.match(key):
                    v = K.normaliza_tipo(j[key], base_m[key])
                    if v != base_m[key]:              # (igual ao perfil da maquina, p. ex. um perfil teu: ja la esta)
                        maq_extra[key] = v
        if fim and "machine_end_gcode" not in maq_extra:
            maq_extra["machine_end_gcode"] = fim
        mj = K.grava_perfil(os.path.join(tmp, "machine.json"), "machine", K.MAQUINA, maq_extra)
        pj = K.grava_perfil(os.path.join(tmp, "process.json"), "process", processo, mud)
        fj = [K.grava_perfil(os.path.join(tmp, f"fil{i + 1}.json"), "filament", n, dict(fil_extra[i], filament_colour=[c]))
              for i, (n, c, _) in enumerate(fils)]
        exp = os.path.join(tmp, "exportado.3mf")
        K.exporta(prep, exp, mj, pj, fj, tmp)
        ref = os.path.join(tmp, "referencia.3mf")      # projeto do Anycubic com k filamentos: comprimentos certos
        K.exporta(K.cubo_stl(os.path.join(tmp, "cubo.stl")), ref, mj, pj, fj, tmp)

        ze = zipfile.ZipFile(exp)
        abertos.append(ze)
        mod = K.Modelo(ze)
        por_prato = K.caixas_por_prato(mod)
        av_folgas, pegadas = ([], {})
        if distancias.disponivel():
            try:
                av_folgas, pegadas = distancias.avisos_folgas(mod, por_prato)
            except MemoryError:
                av_folgas, pegadas = [], {}
        torre, torre_sem_sitio = None, []
        if k > 1:
            largura = float(K.primeiro(mud.get("prime_tower_width", sis.get("prime_tower_width", "35"))) or 35)
            torre = []
            for p in range(1, mod.n_pratos + 1):
                rects = [K.ret(c) for c in por_prato.get(p, []) if c["printable"] != "0"]
                pos = K.posicao_torre(rects, k, largura, livre=pegadas[p].livre if p in pegadas else None)
                if not pos:
                    torre_sem_sitio.append(p)
                torre.append(pos or (int(K.CAMA_X / 2), int(K.CAMA_Y - 50)))
        final = os.path.join(tmp, "final.3mf")
        fil_diffs = [";".join(sorted(set(K.mudancas_do_utilizador("filament", n)) | set(fil_extra[i]))) for i, (n, _, _) in enumerate(fils)]
        maq_diff = ";".join(sorted(set(K.mudancas_do_utilizador("machine", K.MAQUINA)) | set(maq_extra)))
        corr = corrige(exp, ref, final, proc_diff, fil_diffs, maq_diff, torre, matriz, plano)

        # ---- verificacoes
        zf = zipfile.ZipFile(final)
        abertos.append(zf)
        mod_f = K.Modelo(zf)
        por_prato = K.caixas_por_prato(mod_f)
        avisos = K.avisos_mesa(por_prato, sobreposicao=not distancias.disponivel())
        t_orig = sorted(tuple(round(x, 1) for x in c["tam"]) for c in K.Modelo(z).caixas())
        t_novo = sorted(tuple(round(x, 1) for x in c["tam"]) for c in mod_f.caixas())
        if t_orig != t_novo:
            avisos.append(f"as medidas mudaram! original {t_orig} -> novo {t_novo}")
        avisos += av_folgas
        for p in torre_sem_sitio:
            avisos.append(f"prato {p}: nao ha sitio livre para a torre de purga; ficou em ({torre[p - 1][0]}, {torre[p - 1][1]}), "
                          "provavelmente em cima de pecas: divide as pecas por mais pratos (pratos.py) ou arruma no Anycubic")
        gcode_proprio = sorted({x for x in list(maq_extra) + [y for e in fil_extra for y in e]
                                if "gcode" in x and not (x == "machine_end_gcode" and maq_extra.get(x) == fim)})
        if gcode_proprio:
            avisos.append("o projeto ja trazia g-code proprio (" + ", ".join(gcode_proprio) + ") e ficou como estava, porque ja era desta "
                          "impressora. Se o ficheiro nao e teu, confirma esse g-code no Anycubic ou adapta a partir do original")
        if corr["sem_regra"]:
            avisos.append(f"listas com comprimento inesperado (ver no Anycubic): {corr['sem_regra']}")
        if corr["plano_falhou"]:
            avisos.append("nao consegui por o filamento pedido nestes objetos (confirma no Anycubic): " + ", ".join(corr["plano_falhou"]))
        if cores_obj:
            avisos.append(f"a {K.MODELO} nao tem ACE: ficou tudo num filamento so. Cores do autor por objeto (trocar o "
                          "rolo entre pratos): " + "; ".join(dict.fromkeys(f"{n}: {'+'.join(c)}" for n, c in cores_obj)))
            varias = [n for n, c in cores_obj if len(set(c)) > 1]
            if varias or pinturas["pintura_cores"]:
                avisos.append("estes objetos tinham varias cores e saem numa so: " + (", ".join(varias) or "pintura de cores"))
            if a.atribuir:
                avisos.append("as cores por peca pedidas nao se aplicam: esta impressora so imprime uma cor")
        if k > 4:
            avisos.append(f"usa {k} cores: uma ACE so tem 4 ranhuras")
        if regras and pinturas["pintura_cores"]:
            avisos.append("o modelo tem cores pintadas nas faces: mudar o filamento das pecas nao muda a pintura")
        avisos += avisos_fil
        if NOTAS["tpu"] in notas_fil and k > 1 and K.MULTICOR and not any("TPU for ACE" in n for n, _, _ in fils):
            avisos.append("ha TPU num projeto de varias cores: pela ACE so com o perfil 'TPU for ACE'")
        if bico_orig != K.BICO and tem_definicoes:
            avisos.append(f"o original era para bico {bico_orig}; o adaptado e para bico {K.BICO}")
        if not tem_definicoes:
            avisos.append("o 3MF nao trazia definicoes de impressao (nao veio de um slicer): usei o perfil normal da impressora")
        altura_perfil = float(K.primeiro(mud.get("layer_height", sis.get("layer_height", "0.2"))) or 0.2)
        res = None
        if a.fatiar:
            res = K.fatia(final, os.path.join(tmp, "fatiado"), tmp, avisos)
            avisos += K.colisoes_torre(res, por_prato, pegadas=pegadas)
            if tem_variaveis:
                medias = [r["camada_media"] for r in res.values() if r.get("camada_media")]
                if medias and abs(min(medias) - altura_perfil) / altura_perfil > 0.2:
                    rel["notas"].append(f"alturas de camada variaveis do autor: imprime em media a {min(medias):.2f} mm e nao aos "
                                        f"{altura_perfil:g} mm do perfil (--sem-camadas-variaveis usa a altura do perfil)")

        # ---- gravar
        copia = K.guarda_copia(destino, "adaptar") if os.path.exists(destino) else None
        if mesmo:
            z.close()
        os.makedirs(saida, exist_ok=True)
        shutil.copyfile(final, destino)
        gcodes = []
        if a.gcode and res:
            os.makedirs(a.gcode, exist_ok=True)
            nb = os.path.splitext(nome_saida)[0]
            antigo = re.compile(r"^%s( - prato \d+)?\.gcode$" % re.escape(nb), re.I)
            for f in os.listdir(a.gcode):          # o g-code anterior deste projeto: nao pode ficar um prato antigo esquecido
                if antigo.match(f):
                    os.remove(os.path.join(a.gcode, f))
            for p, r in sorted(res.items()):
                alvo = os.path.join(a.gcode, f"{nb}.gcode" if len(res) == 1 else f"{nb} - prato {p}.gcode")
                shutil.copyfile(r["ficheiro"], alvo)
                gcodes.append(alvo)
        arq = a.arquivar_original
        if arq is None and not e_any:
            o = K.pasta_config("originais")       # so arquiva sozinho o que foi largado ao lado da pasta de originais
            if o and os.path.normcase(pasta_o) == os.path.normcase(os.path.dirname(os.path.abspath(o))):
                arq = o
        arquivado = None
        if arq and not mesmo:
            os.makedirs(arq, exist_ok=True)
            arquivado = os.path.join(arq, os.path.basename(orig))
            if os.path.normcase(os.path.abspath(arquivado)) == os.path.normcase(orig):
                arquivado = None
            elif os.path.exists(arquivado):
                avisos.append(f"nao movi o original: ja existe {arquivado}")
                arquivado = None
            else:
                z.close()
                shutil.move(orig, arquivado)

        # ---- relatorio
        extras = [n for n, v in (("fuzzy skin pintado", pinturas["fuzzy_pintado"]), ("suportes pintados", pinturas["suportes_pintados"]),
                                 ("costura pintada", pinturas["costura_pintada"]), ("cores pintadas", pinturas["pintura_cores"])) if v]
        if "Metadata/layer_heights_profile.txt" in conteudo:
            extras.append("alturas de camada variaveis" + ("" if a.camadas_variaveis else " (ignoradas a pedido)"))
        rel["original"] = {"caminho": orig, "impressora": K.primeiro(j.get("printer_model", "")) or psid or "?",
                           "perfil": pid_ or "?", "pratos": mod.n_pratos, "nomes_pratos": nomes_pratos,
                           "filamentos": n_orig, "usados": usados_orig, "tem": extras, "anycubic": e_any}
        rel["adaptado"] = {"caminho": destino, "impressora": K.MODELO, "bico": K.BICO,
                           "mesa": [K.CAMA_X, K.CAMA_Y, K.ALTURA_MAX], "ace": K.MULTICOR, "fim_levanta_bico": "levanta o bico" in str(maq_extra.get("machine_end_gcode", "")),
                           "maquina": K.MAQUINA, "maquina_base": K.raiz_sistema("machine", K.MAQUINA) if K.do_utilizador("machine", K.MAQUINA) else None,
                           "perfis": perfis or "do projeto", "processo": processo,
                           "processo_base": K.raiz_sistema("process", processo) if K.do_utilizador("process", processo) else None}
        rel["mudancas"] = [{"chave": c, "de": sis.get(c), "para": mud[c], "origem": origem.get(c, "autor")} for c in sorted(mud)]
        rel["nao_passou"] = nao
        rel["filamentos"] = [{"n": i + 1, "perfil": n, "cor": c, "era": b,
                              "base": K.raiz_sistema("filament", n) if K.do_utilizador("filament", n) else None}
                             for i, (n, c, b) in enumerate(fils)]
        rel["pecas"] = feito_cores
        # o que ja estava afinado no projeto (so quando ja era desta impressora) e ficou
        rel["do_projeto"] = {"impressora": sorted(x for x in maq_extra if not (x == "machine_end_gcode" and maq_extra[x] == fim)),
                             "filamentos": {str(i + 1): sorted(e) for i, e in enumerate(fil_extra) if e}}
        rel["purga"] = None
        if k > 1:
            rel["purga"] = {"matriz": [[int(matriz[x * k + y]) for y in range(k)] for x in range(k)],
                            "recalculadas": recalculadas, "multiplicador": corr.get("flush_multiplier")}
        rel["torre"] = {"ligada": corr["prime_tower"], "posicoes": torre} if k > 1 else None
        rel["pratos"] = []
        for p in range(1, mod_f.n_pratos + 1):
            pr = {"n": p, "objetos": [{"nome": c["nome"], "tamanho": [round(v, 1) for v in c["tam"]],
                                       "x": [round(c["llo"][0], 1), round(c["lhi"][0], 1)],
                                       "y": [round(c["llo"][1], 1), round(c["lhi"][1], 1)]} for c in por_prato.get(p, [])]}
            if res and p in res:
                r = res[p]
                pr.update({"tempo": r["tempo"], "segundos": r["segundos"], "g": r["g"], "total_g": r["total_g"],
                           "camadas": r["camadas"], "altura": r["altura"], "camada_media": r["camada_media"], "trocas": r["trocas"]})
            rel["pratos"].append(pr)
        cfg = K.le_config()
        if res and (cfg.get("precos") or cfg.get("preco_hora")):
            cf = cm = 0.0
            for r in res.values():
                for i, g in enumerate(r["g"]):
                    pk = preco_material(cfg.get("precos"), fils[i][0]) if i < len(fils) else None
                    cf += g * pk / 1000.0 if pk else 0.0
                cm += r["segundos"] / 3600.0 * float(cfg.get("preco_hora") or 0)
            rel["custo"] = {"filamento": round(cf, 2), "maquina": round(cm, 2), "total": round(cf + cm, 2)}
        rel["copia"], rel["arquivado"], rel["gcode"] = copia, arquivado, gcodes
        rel["avisos"] = avisos
        return rel
    finally:
        for zz in abertos:
            zz.close()
        if a.manter_temp:
            rel["pasta_temporaria"] = tmp
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def imprime(rel):
    o, d = rel["original"], rel["adaptado"]
    print("=" * 70)
    print("ORIGINAL :", o["caminho"])
    print("  impressora:", o["impressora"], "| perfil:", o["perfil"])
    nomes = [n for n in o["nomes_pratos"] if n]
    print("  pratos:", o["pratos"], ("| nomes: " + "; ".join(f"{i + 1}={n}" for i, n in enumerate(o["nomes_pratos"]) if n)) if nomes else "")
    print(f"  filamentos no projeto: {o['filamentos']} | usados: {o['usados']}")
    if o["tem"]:
        print("  tem:", ", ".join(o["tem"]))
    print("ADAPTADO :", d["caminho"])
    print(f"  impressora: {d['impressora']} (bico {d['bico']}, mesa {d['mesa'][0]:g} x {d['mesa'][1]:g} x {d['mesa'][2]:g} mm"
          f"{', com ACE' if d['ace'] else ', sem ACE'})" + (" | fim de impressao: levanta o bico" if d["fim_levanta_bico"] else "")
          + (f" | maquina: '{d['maquina']}' (perfil teu, baseado em '{d['maquina_base']}')" if d["maquina_base"] else ""))
    print("  perfis:", {"meus": "os teus, quando existem", "sistema": "de origem da Anycubic"}.get(d["perfis"], "os que o projeto ja tinha"))
    print("  perfil:", d["processo"] + (f" (perfil teu, baseado em '{d['processo_base']}')" if d["processo_base"] else ""))
    for m in rel["mudancas"]:
        rotulo = {"autor": "o autor mudou", "perfil": "valor do perfil do autor", "skill": "acerto da skill",
                  "projeto": "ja estava no projeto"}.get(m["origem"], m["origem"])
        print(f"    {m['chave']}: {m['de']} -> {m['para']}   [{rotulo}]")
    n = rel["nao_passou"]
    if n["impressora"]:
        print("  do autor, nao passou (e da impressora dele):", ", ".join(n["impressora"]))
    if n["sem_equivalente"]:
        print("  do autor, nao passou (nao existe no Anycubic):", ", ".join(n["sem_equivalente"]))
    if n["velocidades"]:
        print(f"  do autor, nao passou (velocidade acima do perfil da {d['impressora']}):", ", ".join(n["velocidades"]))
    if n.get("seguranca"):
        print("  nao passou, por seguranca (comandos que correriam no computador depois de fatiar):", ", ".join(n["seguranca"]))
    dp = rel.get("do_projeto") or {}
    if dp.get("impressora"):
        print("  ja estava no projeto e ficou (impressora):", ", ".join(dp["impressora"]))
    for fil, chaves in sorted((dp.get("filamentos") or {}).items()):
        print(f"  ja estava no projeto e ficou (filamento {fil}):", ", ".join(chaves))
    for f in rel["filamentos"]:
        print(f"  filamento {f['n']}: {f['perfil'].split(' @')[0]} {f['cor']}  (era {f['era']})"
              + (f" (perfil teu, baseado em '{f['base']}')" if f["base"] else ""))
    for x in rel["pecas"]:
        print("  peca:", x)
    for x in rel["notas"]:
        print("  nota:", x)
    if rel["purga"]:
        k = len(rel["purga"]["matriz"])
        pares = ", ".join(f"{a + 1}>{b + 1} {rel['purga']['matriz'][a][b]}" + ("*" if [a + 1, b + 1] in [list(r) for r in rel["purga"]["recalculadas"]] else "")
                          for a in range(k) for b in range(k) if a != b)
        print(f"  purga em mm3 (x{rel['purga']['multiplicador']} na impressora): {pares}"
              + ("   (* recalculada para as cores novas)" if rel["purga"]["recalculadas"] else "   (valores do autor)"))
    if rel["torre"]:
        print("  torre de purga:", rel["torre"]["ligada"], "| posicao por prato:", rel["torre"]["posicoes"])
    for pr in rel["pratos"]:
        for c in pr["objetos"]:
            print(f"  prato {pr['n']}: {c['nome']}: {c['tamanho'][0]:.1f} x {c['tamanho'][1]:.1f} x {c['tamanho'][2]:.1f} mm "
                  f"(x {c['x'][0]:.1f}..{c['x'][1]:.1f}, y {c['y'][0]:.1f}..{c['y'][1]:.1f})")
    if any("tempo" in pr for pr in rel["pratos"]):
        print("FATIADO:")
        cores = [f["cor"] for f in rel["filamentos"]]
        for pr in rel["pratos"]:
            if "tempo" not in pr:
                continue
            g = " + ".join(f"{v:.1f} g" + (f" ({cores[i]})" if i < len(cores) else "") for i, v in enumerate(pr["g"]))
            t = f"  prato {pr['n']}: {pr['tempo']}, {pr['total_g']} g" + (f" [{g}]" if len(pr["g"]) > 1 else "")
            t += f", {pr['camadas']} camadas, altura {pr['altura']} mm"
            if pr["trocas"]:
                t += f", {pr['trocas']} troca{'s' if pr['trocas'] > 1 else ''} de cor"
            print(t)
    if rel.get("custo"):
        c = rel["custo"]
        print(f"CUSTO ESTIMADO: {c['total']:.2f} EUR (filamento {c['filamento']:.2f} + maquina {c['maquina']:.2f})")
    if rel.get("gcode"):
        print("G-CODE:", "; ".join(rel["gcode"]))
    if rel.get("copia"):
        print("COPIA DO FICHEIRO ANTERIOR:", rel["copia"], "(desfazer.py repoe)")
    if rel.get("arquivado"):
        print("ORIGINAL MOVIDO PARA:", rel["arquivado"])
    if rel.get("pasta_temporaria"):
        print("pasta temporaria:", rel["pasta_temporaria"])
    print("AVISOS:" if rel["avisos"] else "AVISOS: nenhum")
    for av in rel["avisos"]:
        print("  -", av)


def main():
    ap = argparse.ArgumentParser(description="MakerWorld to Any: Bambu Lab 3MF -> impressora Anycubic (Megatic)")
    ap.add_argument("original", nargs="?")
    ap.add_argument("--impressora", help=f'impressora Anycubic, ex. "Kobra S1", "Kobra 3 Max" (por omissao: {K.IMPRESSORA_OMISSAO})')
    ap.add_argument("--bico", help="diametro do bico (por omissao o do original, se houver perfil; senao 0.4)")
    ap.add_argument("--listar-impressoras", action="store_true", help="mostra as impressoras disponiveis e sai")
    ap.add_argument("--perfis", choices=("sistema", "meus"),
                    help=f"sistema = perfis de origem da Anycubic; meus = os que guardaste no slicer (por omissao: {K.PERFIS_OMISSAO})")
    ap.add_argument("--listar-perfis", action="store_true", help="mostra os perfis que guardaste no slicer e sai")
    ap.add_argument("--saida", help="pasta de saida (por omissao: a de /any-perfil, ou 'Adaptado <impressora>' ao lado)")
    ap.add_argument("--nome", help="nome do ficheiro de saida (por omissao '<original> - <impressora>.3mf')")
    ap.add_argument("--processo", help='perfil da impressora, ex. "0.16mm High Quality" (por omissao: o do autor)')
    ap.add_argument("--filamentos", help='perfis Anycubic por ordem, separados por ";" (ex. "Anycubic PLA Matte;Anycubic PLA")')
    ap.add_argument("--cores", help='cores por ordem, separadas por ";" (vazio = fica a do autor, ex. ";#800020")')
    ap.add_argument("--material", help='muda o material de todos os filamentos, ex. "PETG", "PLA Silk", "ABS", "TPU" '
                                       '(as cores ficam; --filamentos manda sobre isto)')
    ap.add_argument("--atribuir", help='filamento de objetos/pecas, ex. "anel=2;1.3=2" (ver cores.py --listar)')
    ap.add_argument("--sem-camadas-variaveis", dest="camadas_variaveis", action="store_false",
                    help="ignora as alturas de camada variaveis do autor (usa a altura do perfil)")
    ap.add_argument("--gcode", metavar="PASTA", help="guarda tambem o g-code de cada prato nesta pasta")
    ap.add_argument("--substituir", action="store_true", help="substitui o ficheiro de saida se ja existir (fica uma copia)")
    ap.add_argument("--arquivar-original", metavar="PASTA", help="no fim move o original para esta pasta")
    ap.add_argument("--sem-fatiar", dest="fatiar", action="store_false")
    ap.add_argument("--manter-temp", action="store_true", help="guarda a pasta temporaria (para investigar)")
    ap.add_argument("--json", action="store_true", help="relatorio em JSON (para programas)")
    a = ap.parse_args()
    if a.listar_impressoras:
        lista_impressoras()
        return
    if a.listar_perfis:
        lista_perfis()
        return
    if not a.original:
        ap.error("falta o ficheiro 3MF original")
    try:
        rel = adapta(a)
    except SystemExit as e:
        if a.json and e.code not in (0, None):
            print(json.dumps({"erro": str(e.code)}, ensure_ascii=False))
            sys.exit(1)
        raise
    if a.json:
        print(json.dumps(rel, indent=1, ensure_ascii=False))
    else:
        imprime(rel)


if __name__ == "__main__":
    main()
