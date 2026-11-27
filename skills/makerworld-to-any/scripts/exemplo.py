"""Creates an example project in the Bambu Studio format, for the tests, the diagnostics and demos.
MakerWorld to Any - made by Megatic (https://megatic.pt).

Usage:
    python exemplo.py <output.3mf>

The example deliberately puts together the things that make a MakerWorld project hard work:
  - 2 plates with names ("Caixa" and "Tampa"; with names, Anycubic's command line crashes);
  - 4 filaments in the project but only 2 in use (2 and 4), one of them on a part inside an object;
  - settings changed by the designer: infill, organic tree supports (which don't exist in Anycubic) and a
    speed above what the Anycubic profiles use.
The geometry (hexagonal box with a band, lid) is generated here: it doesn't come from anyone else's model.
"""
import json
import math
import os
import sys
import zipfile

sys.dont_write_bytecode = True

CORES = ["#FFFFFF", "#F2C94C", "#0086D6", "#C0392B"]
FILAMENTOS = ["Bambu PLA Basic @BBL A1", "Bambu PLA Matte @BBL A1", "Bambu PETG HF @BBL A1", "Bambu PLA Silk @BBL A1"]
TIPOS = ["PLA", "PLA", "PETG", "PLA"]


def prisma(lados, raio, altura):
    """Prisma regular centrado na origem (z de -h/2 a h/2): (vertices, triangulos virados para fora)."""
    v = [(raio * math.cos(2 * math.pi * i / lados), raio * math.sin(2 * math.pi * i / lados), z)
         for z in (-altura / 2, altura / 2) for i in range(lados)]
    v += [(0.0, 0.0, -altura / 2), (0.0, 0.0, altura / 2)]
    cb, ct, t = 2 * lados, 2 * lados + 1, []
    for i in range(lados):
        k = (i + 1) % lados
        t += [(i, k, lados + k), (i, lados + k, lados + i), (cb, k, i), (ct, lados + i, lados + k)]
    return v, t


def _malha(oid, v, t):
    vs = "\n".join(f'     <vertex x="{x:.6g}" y="{y:.6g}" z="{z:.6g}"/>' for x, y, z in v)
    ts = "\n".join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in t)
    return (f'  <object id="{oid}" p:UUID="0000{oid:04d}-81cb-4c03-9d28-80fed5dfa1dc" type="model">\n   <mesh>\n    <vertices>\n{vs}\n'
            f'    </vertices>\n    <triangles>\n{ts}\n    </triangles>\n   </mesh>\n  </object>\n')


CAB_MODELO = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
              'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
              'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
              'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">\n')


def cria(caminho, mesa=256.0, impressora=None, junto=False, camadas_variaveis=False, nomes_estranhos=False):
    """Escreve o projeto de exemplo.
    mesa: tamanho da mesa do "autor" (256 = Bambu A1). impressora: nome de uma maquina Anycubic para fingir um
    projeto ja adaptado (usado nos testes sem slicer). junto: poe uma segunda tampa a 1 mm da primeira (para o aviso
    de pecas encostadas). nomes_estranhos: nomes com caracteres fora do cp1252."""
    passo = mesa * 1.2
    c = mesa / 2
    caixa, faixa, tampa = prisma(6, 30.0, 40.0), prisma(6, 30.0, 8.0), prisma(6, 33.0, 4.0)
    n_tampa = "Tampa 蓋" if nomes_estranhos else "Tampa"
    objetos = [   # (id, nome, filamento, [(id da malha, nome da peca, malha, z da peca, filamento da peca)], (x, y, z))
        (3, "Caixa", 2, [(1, "Corpo", caixa, 0.0, None), (2, "Faixa", faixa, 24.0, 4)], (c, c, 20.0)),
        (5, n_tampa, 2, [(4, "Tampa", tampa, 0.0, None)], (passo + c, c, 2.0)),
    ]
    pratos = [("Caixa", [3]), ("Tampa", [5])]
    if junto:      # hexagono de raio 33: de lado a lado mede 57.16 mm -> 58.16 entre centros da 1 mm de folga
        objetos.append((7, "Tampa", 2, [(6, "Tampa", tampa, 0.0, None)], (passo + c, c + 58.16, 2.0)))
        pratos[1][1].append(7)

    fich = {}
    fich["[Content_Types].xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                                   ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
                                   ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
                                   ' <Default Extension="png" ContentType="image/png"/>\n'
                                   ' <Default Extension="gcode" ContentType="text/x.gcode"/>\n</Types>\n')
    fich["_rels/.rels"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                           ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
                           '</Relationships>\n')
    rels, recursos, itens, ms_obj, asm = "", "", "", "", ""
    for n, (oid, nome, fil, partes, (x, y, z)) in enumerate(objetos, 1):
        fich[f"3D/Objects/object_{n}.model"] = (CAB_MODELO + ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n'
                                                + "".join(_malha(pid, *malha) for pid, _, malha, _, _ in partes)
                                                + " </resources>\n <build/>\n</model>\n")
        rels += f' <Relationship Target="/3D/Objects/object_{n}.model" Id="rel-{n}" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        comps = "".join(f'    <component p:path="/3D/Objects/object_{n}.model" objectid="{pid}" p:UUID="000{n}{pid:04d}-b206-40ff-9872-83e8017abed1" '
                        f'transform="1 0 0 0 1 0 0 0 1 0 0 {pz:g}"/>\n' for pid, _, _, pz, _ in partes)
        recursos += f'  <object id="{oid}" p:UUID="0000{oid:04d}-61cb-4c03-9d28-80fed5dfa1dc" type="model">\n   <components>\n{comps}   </components>\n  </object>\n'
        itens += f'  <item objectid="{oid}" p:UUID="0000{oid:04d}-b1ec-4553-aec9-835e5b724bb4" transform="1 0 0 0 1 0 0 0 1 {x:.6g} {y:.6g} {z:g}" printable="1"/>\n'
        ps = ""
        for pid, pnome, malha, pz, pfil in partes:
            ps += (f'    <part id="{pid}" subtype="normal_part">\n      <metadata key="name" value="{pnome}"/>\n'
                   f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 {pz:g} 0 0 0 1"/>\n'
                   + (f'      <metadata key="extruder" value="{pfil}"/>\n' if pfil else "")
                   + f'      <mesh_stat face_count="{len(malha[1])}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n'
                   '    </part>\n')
        ms_obj += f'  <object id="{oid}">\n    <metadata key="name" value="{nome}"/>\n    <metadata key="extruder" value="{fil}"/>\n{ps}  </object>\n'
        asm += f'   <assemble_item object_id="{oid}" instance_id="0" transform="1 0 0 0 1 0 0 0 1 {x:.6g} {y:.6g} {z:g}" offset="0 0 0" />\n'
    fich["3D/_rels/3dmodel.model.rels"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                                           + rels + '</Relationships>\n')
    app = "AnycubicSlicerNext-2.0.0.3" if impressora else "BambuStudio-02.02.02.56"
    fich["3D/3dmodel.model"] = (CAB_MODELO + f' <metadata name="Application">{app}</metadata>\n <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
                                ' <metadata name="Designer">Megatic</metadata>\n <metadata name="License">MIT</metadata>\n'
                                ' <metadata name="Title">Exemplo MakerWorld to Any</metadata>\n <resources>\n' + recursos
                                + ' </resources>\n <build p:UUID="2c7c17d8-22b5-4d84-8835-1976022ea369">\n' + itens + ' </build>\n</model>\n')
    ms_pratos = ""
    for n, (nome, oids) in enumerate(pratos, 1):
        inst = "".join(f'    <model_instance>\n      <metadata key="object_id" value="{o}"/>\n      <metadata key="instance_id" value="0"/>\n'
                       f'      <metadata key="identify_id" value="{100 + o}"/>\n    </model_instance>\n' for o in oids)
        ms_pratos += (f'  <plate>\n    <metadata key="plater_id" value="{n}"/>\n    <metadata key="plater_name" value="{"" if impressora else nome}"/>\n'
                      '    <metadata key="locked" value="false"/>\n' + inst + '  </plate>\n')
    fich["Metadata/model_settings.config"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>\n' + ms_obj + ms_pratos
                                              + '  <assemble>\n' + asm + '  </assemble>\n</config>\n')
    try:
        import purga
        matriz = [str(0 if a == b else purga.volume(CORES[a], CORES[b], 92)) for a in range(4) for b in range(4)]
    except ImportError:
        matriz = ["0" if a == b else "280" for a in range(4) for b in range(4)]
    j = {
        "version": "02.02.02.56", "from": "project", "name": "project_settings",
        "printer_model": "Bambu Lab A1", "printer_settings_id": "Bambu Lab A1 0.4 nozzle",
        "print_settings_id": "0.20mm Standard @BBL A1", "default_print_profile": "0.20mm Standard @BBL A1",
        "printable_area": ["0x0", f"{mesa:g}x0", f"{mesa:g}x{mesa:g}", f"0x{mesa:g}"], "printable_height": "256",
        "nozzle_diameter": ["0.4"], "nozzle_volume": ["92"],
        "filament_settings_id": list(FILAMENTOS), "filament_type": list(TIPOS), "filament_colour": list(CORES),
        "filament_ids": ["GFA00", "GFA01", "GFG02", "GFA05"], "filament_vendor": ["Bambu Lab"] * 4,
        "flush_volumes_matrix": matriz, "flush_volumes_vector": ["140"] * 8, "flush_multiplier": ["1"],
        "layer_height": "0.2", "wall_loops": "3", "sparse_infill_density": "10%", "sparse_infill_pattern": "gyroid",
        "enable_support": "1", "support_type": "tree(auto)", "support_style": "tree_organic", "outer_wall_speed": ["350"],
        "enable_prime_tower": "1", "wipe_tower_x": ["15", "15"], "wipe_tower_y": ["220", "220"],
        "different_settings_to_system": ["enable_support;outer_wall_speed;sparse_infill_density;sparse_infill_pattern;support_style;wipe_tower_x",
                                         "", "", "", "", ""],
    }
    if impressora:        # fingir um projeto ja adaptado para uma Anycubic (testes sem slicer)
        j.update({"printer_model": impressora.rsplit(" ", 2)[0], "printer_settings_id": impressora,
                  "print_settings_id": "0.20mm Standard @" + impressora, "support_style": "default", "outer_wall_speed": ["200"],
                  "filament_settings_id": ["Anycubic PLA Matte @" + impressora, "Anycubic PLA Silk @" + impressora],
                  "filament_type": ["PLA", "PLA"], "filament_colour": [CORES[1], CORES[3]],
                  "flush_volumes_matrix": [matriz[1 * 4 + 1], matriz[1 * 4 + 3], matriz[3 * 4 + 1], matriz[3 * 4 + 3]],
                  "flush_volumes_vector": ["140"] * 4, "flush_multiplier": "0.7",
                  "different_settings_to_system": ["enable_support;sparse_infill_density;sparse_infill_pattern", "", "", ""]})
        fich["Metadata/model_settings.config"] = (fich["Metadata/model_settings.config"]
                                                  .replace('key="extruder" value="2"', 'key="extruder" value="1"')
                                                  .replace('key="extruder" value="4"', 'key="extruder" value="2"'))
    fich["Metadata/project_settings.config"] = json.dumps(j, indent=4, ensure_ascii=False)
    if camadas_variaveis:     # a caixa a 0.1 mm em toda a altura (o perfil diz 0.2); object_id = posicao do objeto (1, 2...)
        # a primeira camada tem de ter a altura da primeira camada do perfil (0.2), senao o slicer deita o perfil fora
        fich["Metadata/layer_heights_profile.txt"] = "object_id=1|0.000000;0.200000;0.200000;0.200000;0.200000;0.100000;48.000000;0.100000\n"
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, texto in fich.items():
            z.writestr(nome, texto)
    return caminho


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1].startswith("-"):
        raise SystemExit(__doc__)
    print("created:", os.path.abspath(cria(sys.argv[1])))
