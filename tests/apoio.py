"""Apoio dos testes: prepara um ambiente isolado ANTES de importar os scripts da skill.

- perfis de sistema e do utilizador falsos (minimos) numa pasta temporaria: os testes nao dependem do Anycubic
  Slicer Next estar instalado nem dos perfis de quem os corre;
- preferencias e copias de seguranca noutra pasta temporaria: nunca tocam nas do utilizador.

Os testes que precisam mesmo do slicer (test_e2e.py) correm os scripts noutro processo, com o ambiente real.
"""
import atexit
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(RAIZ, "skills", "makerworld-to-any", "scripts")
AMBIENTE_REAL = dict(os.environ)           # como estava antes de isolar (para os testes com o slicer)
TMP = tempfile.mkdtemp(prefix="mw2any_testes_")
atexit.register(shutil.rmtree, TMP, True)

KX = "Anycubic Kobra X 0.4 nozzle"
KX6 = "Anycubic Kobra X 0.6 nozzle"
NEO = "Anycubic Kobra 2 Neo 0.4 nozzle"
TROCA = "; troca de filamento pela ACE\nM400\nT[next_extruder]\nG1 E10 F300\n"


def _grava(pasta, d):
    os.makedirs(pasta, exist_ok=True)
    nome = d["name"].replace("/", "_").replace("@", "_")
    with open(os.path.join(pasta, nome + ".json"), "w", encoding="utf-8") as f:
        json.dump(d, f)


def _maquina(nome, modelo, mesa, altura, bico, ace, fim):
    return {"name": nome, "type": "machine", "from": "system", "instantiation": "true", "printer_model": modelo,
            "printable_area": ["0x0", f"{mesa}x0", f"{mesa}x{mesa}", f"0x{mesa}"], "printable_height": str(altura),
            "nozzle_diameter": [bico], "nozzle_volume": ["79"], "change_filament_gcode": TROCA if ace else "",
            "machine_end_gcode": fim}


def _processo(nome, maquina, altura, velocidade="200"):
    return {"name": f"{nome} @{maquina}", "type": "process", "from": "system", "instantiation": "true",
            "compatible_printers": [maquina], "layer_height": altura, "wall_loops": "2", "top_shell_layers": "5",
            "bottom_shell_layers": "3", "sparse_infill_density": "15%", "sparse_infill_pattern": "grid",
            "enable_support": "0", "support_type": "tree(auto)", "support_style": "default",
            "support_threshold_angle": "30", "support_on_build_plate_only": "0", "brim_type": "auto_brim",
            "raft_layers": "0", "spiral_mode": "0", "ironing_type": "no ironing", "ironing_speed": "30",
            "fuzzy_skin": "none", "print_sequence": "by layer", "seam_position": "aligned",
            "outer_wall_speed": [velocidade], "inner_wall_speed": ["300"], "prime_tower_width": "35",
            "support_filament": "0", "support_interface_filament": "0"}


def _filamento(nome, maquina, tipo):
    return {"name": f"{nome} @{maquina}", "type": "filament", "from": "system", "instantiation": "true",
            "compatible_printers": [maquina], "filament_type": [tipo], "filament_colour": ["#FFFFFF"]}


def _cria_perfis():
    sis = os.path.join(TMP, "perfis")
    _grava(os.path.join(sis, "machine"), _maquina(KX, "Anycubic Kobra X", 260, 260, "0.4", True, "M104 S0\nM140 S0\nM84\n"))
    _grava(os.path.join(sis, "machine"), _maquina(KX6, "Anycubic Kobra X", 260, 260, "0.6", True, "M104 S0\nM140 S0\nM84\n"))
    _grava(os.path.join(sis, "machine"), _maquina(NEO, "Anycubic Kobra 2 Neo", 220, 250, "0.4", False,
                                                  "G91\nG1 Z5 F900\nG90\nM104 S0\nM84\n"))
    for maq in (KX, NEO):
        for nome, altura in (("0.12mm High Quality", "0.12"), ("0.16mm High Quality", "0.16"), ("0.20mm Standard", "0.2"),
                             ("0.28mm Draft", "0.28")):
            _grava(os.path.join(sis, "process"), _processo(nome, maq, altura, "200" if maq == KX else "120"))
    _grava(os.path.join(sis, "process"), _processo("0.30mm Standard", KX6, "0.3"))
    for nome, tipo in (("Anycubic PLA", "PLA"), ("Anycubic PLA Matte", "PLA"), ("Anycubic PLA Silk", "PLA"),
                       ("Anycubic PETG", "PETG"), ("Anycubic ABS", "ABS"), ("Anycubic TPU for ACE", "TPU"),
                       ("Generic TPU 95A", "TPU")):
        _grava(os.path.join(sis, "filament"), _filamento(nome, KX, tipo))
    for nome, tipo in (("Anycubic PLA", "PLA"), ("Anycubic PETG", "PETG")):
        _grava(os.path.join(sis, "filament"), _filamento(nome, NEO, tipo))
    _grava(os.path.join(sis, "filament"), _filamento("Anycubic PLA", KX6, "PLA"))
    # perfis do utilizador (so as diferencas + inherits), como o Anycubic Slicer Next os guarda
    meu = os.path.join(TMP, "utilizador", "default")
    _grava(os.path.join(meu, "process"), {"name": "O meu 0.20", "inherits": f"0.20mm Standard @{KX}", "from": "User",
                                          "seam_position": "back", "wall_loops": "4"})
    _grava(os.path.join(meu, "filament"), {"name": "O meu PLA", "inherits": f"Anycubic PLA @{KX}", "from": "User",
                                           "nozzle_temperature": ["215"]})
    return sis, os.path.join(TMP, "utilizador")


_sis, _util = _cria_perfis()
os.environ["ANYCUBIC_PERFIS"] = _sis
os.environ["ANYCUBIC_PERFIS_UTILIZADOR"] = _util
os.environ["MAKERWORLD_TO_ANY_CONFIG"] = os.path.join(TMP, "dados", "config.json")
os.environ["ANYCUBIC_SLICER"] = os.path.join(TMP, "nao-existe", "AnycubicSlicerNext.exe")
for _v in ("MAKERWORLD_TO_ANY_IMPRESSORA", "MAKERWORLD_TO_ANY_PERFIS"):
    os.environ.pop(_v, None)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
sys.dont_write_bytecode = True

import anycubic as K      # noqa: E402  (so depois de preparar o ambiente)
import exemplo            # noqa: E402

try:
    import numpy          # noqa: F401,E402
    TEM_NUMPY = True
except ImportError:
    TEM_NUMPY = False

SLICER_REAL = AMBIENTE_REAL.get("ANYCUBIC_SLICER", r"C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe")
TEM_SLICER = os.path.exists(SLICER_REAL)


def escreve(caminho, texto):
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)
    return caminho


def le(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def le_bytes(caminho):
    with open(caminho, "rb") as f:
        return f.read()


def le_json(caminho):
    return json.loads(le(caminho))


def pasta(nome):
    """Pasta nova e vazia dentro da pasta temporaria dos testes."""
    p = os.path.join(TMP, nome)
    shutil.rmtree(p, ignore_errors=True)
    os.makedirs(p)
    return p


def projeto_bambu(caminho, **kw):
    """Projeto de exemplo como vem do Bambu Studio / MakerWorld."""
    return exemplo.cria(caminho, **kw)


def projeto_anycubic(caminho, **kw):
    """O mesmo exemplo, a fingir que ja foi adaptado para a Kobra X (sem precisar do slicer)."""
    return exemplo.cria(caminho, mesa=260.0, impressora=KX, **kw)


def le_zip(caminho, nome):
    """Texto de um ficheiro dentro do 3MF (None se nao existir)."""
    with zipfile.ZipFile(caminho) as z:
        return z.read(nome).decode("utf-8") if nome in z.namelist() else None


def muda_definicoes(caminho, mudar):
    """Altera o project_settings de um projeto: mudar(dicionario) mexe nele no sitio."""
    def f(nome, dados):
        if nome != "Metadata/project_settings.config":
            return dados
        j = json.loads(dados)
        mudar(j)
        return json.dumps(j, indent=4, ensure_ascii=False).encode("utf-8")
    K.reescreve(caminho, caminho, f)


def poe_trocas(caminho, por_prato):
    """Junta trocas de cor por camada (as que se poem no slicer a uma certa altura): {prato: [alturas]}."""
    blocos = "".join('<plate>\n<plate_info id="%d"/>\n' % p
                     + "".join('<layer top_z="%g" type="2" extruder="2" color="#C0392B" extra="" gcode="tool_change"/>\n' % z for z in zs)
                     + '<mode value="MultiAsSingle"/>\n</plate>\n' for p, zs in sorted(por_prato.items()))
    with zipfile.ZipFile(caminho, "a", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Metadata/custom_gcode_per_layer.xml",
                   '<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_layer>\n' + blocos + '</custom_gcodes_per_layer>\n')


def trocas(caminho):
    """{prato: [alturas das trocas por camada]} de um projeto."""
    t = le_zip(caminho, "Metadata/custom_gcode_per_layer.xml") or ""
    out = {}
    for b in re.findall(r"<plate>.*?</plate>", t, re.S):
        out[int(re.search(r'<plate_info id="(\d+)"', b).group(1))] = [float(x) for x in re.findall(r'top_z="([-\d.]+)"', b)]
    return out


def ambiente_isolado(**extra):
    """Ambiente para correr um script noutro processo com os perfis falsos."""
    return dict(os.environ, **extra)


def ambiente_real(**extra):
    """Ambiente real (perfis e slicer de quem corre os testes), mas com preferencias e copias isoladas."""
    amb = dict(AMBIENTE_REAL, MAKERWORLD_TO_ANY_CONFIG=os.path.join(TMP, "dados_real", "config.json"))
    for v in ("MAKERWORLD_TO_ANY_IMPRESSORA", "MAKERWORLD_TO_ANY_PERFIS"):
        amb.pop(v, None)
    amb.update(extra)
    return amb
