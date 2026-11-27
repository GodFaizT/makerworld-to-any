"""Biblioteca comum da skill makerworld-to-any (MakerWorld to Any, feita pela Megatic - https://megatic.pt).

Converte projetos 3MF do Bambu Studio / MakerWorld para impressoras Anycubic (Kobra X, Kobra S1, Kobra 3, Kobra 4,
...) com a linha de comandos do proprio Anycubic Slicer Next (testado com a 2.0.0.3 e a 2.0.0.7) e verifica o resultado
fatiando. A impressora de destino escolhe-se com usa_impressora(); tamanho da mesa, perfis e filamentos vem dos
perfis de sistema do Anycubic. So precisa da biblioteca padrao do Python (o numpy acelera e permite medir folgas).
"""
import glob
import html
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile

from pecas import limpa_nome

try:
    import numpy as np
except ImportError:  # funciona sem numpy: mais devagar e sem folgas reais entre pecas
    np = None


def saida_utf8():
    """Nomes de objetos fora do cp1252 (chines, emoji...) rebentavam o print no Windows quando a saida e um pipe."""
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


saida_utf8()

AQUI = os.path.dirname(os.path.abspath(__file__))
TESTADO_COM = ("2.0.0.3", "2.0.0.7")       # versoes do Anycubic Slicer Next com que a skill foi testada


def le_json(caminho):
    with open(caminho, encoding="utf-8-sig") as f:      # utf-8-sig: aceita a marca (BOM) que o Bloco de notas pode por
        return json.load(f)


def grava_json(caminho, dados, indent=1):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=indent, ensure_ascii=False)


def versao():
    try:
        with open(os.path.join(os.path.dirname(AQUI), "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "?"


ANY = os.environ.get("ANYCUBIC_SLICER", r"C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe")
PERFIS = os.environ.get("ANYCUBIC_PERFIS", os.path.join(os.environ.get("APPDATA", ""), "AnycubicSlicerNext", "system", "Anycubic"))
# preferencias guardadas com /any-settings (fora da pasta da skill, para nao se perderem ao atualizar)
CONFIG = os.environ.get("MAKERWORLD_TO_ANY_CONFIG") or os.path.join(
    os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config"), "makerworld-to-any", "config.json")
PASTA_DADOS = os.path.dirname(CONFIG)


_AVISOU_CONFIG = False


def _config_estragada():
    """True se o ficheiro de preferencias existe mas nao se consegue ler (editado a mao com um erro)."""
    if not os.path.isfile(CONFIG):
        return False
    try:
        return not isinstance(le_json(CONFIG), dict)
    except ValueError:
        return True
    except OSError:
        return False


def le_config():
    global _AVISOU_CONFIG
    try:
        d = le_json(CONFIG)
        if isinstance(d, dict):
            return d
    except OSError:
        return {}
    except ValueError:
        pass
    if not _AVISOU_CONFIG:                # preferencias ilegiveis: diz-se, em vez de as ignorar em silencio
        _AVISOU_CONFIG = True
        print(f"WARNING: couldn't read the settings in {CONFIG} (broken file): using the defaults",
              file=sys.stderr)
    return {}


def grava_config(**valores):
    """Guarda preferencias; um valor None apaga essa chave."""
    if _config_estragada():               # nao se escreve por cima do que la estava sem ficar uma copia
        shutil.copy2(CONFIG, CONFIG + ".estragado")
    d = le_config()
    for k, v in valores.items():
        if v is None:
            d.pop(k, None)
        else:
            d[k] = v
    os.makedirs(PASTA_DADOS, exist_ok=True)
    grava_json(CONFIG, d, 2)
    return d


_CFG = le_config()
# ordem: opcao na linha de comandos > variavel de ambiente > /any-settings > Kobra X / perfis da Anycubic
IMPRESSORA_OMISSAO = os.environ.get("MAKERWORLD_TO_ANY_IMPRESSORA") or _CFG.get("impressora") or "Kobra X"
# perfis do utilizador (guardados no Anycubic Slicer Next): user/<conta>/{machine,process,filament}/*.json
PERFIS_UTILIZADOR = os.environ.get("ANYCUBIC_PERFIS_UTILIZADOR",
                                   os.path.join(os.environ.get("APPDATA", ""), "AnycubicSlicerNext", "user"))
# "sistema" = perfis de origem da Anycubic; "meus" = os do utilizador quando tem um baseado no perfil escolhido
PERFIS_OMISSAO = os.environ.get("MAKERWORLD_TO_ANY_PERFIS") or _CFG.get("perfis") or "sistema"
if PERFIS_OMISSAO not in ("sistema", "meus"):
    PERFIS_OMISSAO = "sistema"

# impressora de destino: usa_impressora() preenche isto a partir do perfil da maquina
MAQUINA = "Anycubic Kobra X 0.4 nozzle"
MAQUINA_SISTEMA = MAQUINA    # perfil de sistema em que a maquina se baseia (igual a MAQUINA se nao for do utilizador)
MODELO = "Anycubic Kobra X"
SUF = " @" + MAQUINA
BICO = "0.4"
CAMA_X = CAMA_Y = 260.0      # mesa (mm)
ALTURA_MAX = 260.0
PASSO_X = PASSO_Y = 312.0    # distancia entre pratos num projeto do Anycubic (mesa x 1.2)
MULTICOR = True              # tem ACE (troca de filamento automatica)
VOLUME_BICO = 79.0           # nozzle_volume do perfil: parte fixa da purga numa troca de cor

# filamento por funcao (Bambu 2.x): tambem contam como "usados" e tem de ser renumerados
CHAVES_FIL = ("support_filament", "support_interface_filament", "wall_filament", "sparse_infill_filament",
              "solid_infill_filament")
# listas que sao uma por prato (nao por filamento)
POR_PRATO = {"wipe_tower_x", "wipe_tower_y"}


def pasta_config(chave):
    """Pasta guardada nas preferencias ('saida', 'originais'), com {impressora} trocado pelo modelo. None se nao ha."""
    v = le_config().get(chave)
    if not v:
        return None
    return os.path.expandvars(os.path.expanduser(str(v))).replace("{impressora}", nome_curto())


# ----------------------------------------------------------------------------------------- perfis

_IDX = None
_ORIGEM = {}      # (tipo, nome) -> "sistema" | "utilizador"
_DATA = {}        # (tipo, nome) -> data do ficheiro (para escolher o mais recente)
META = {"name", "inherits", "from", "type", "setting_id", "filament_id", "instantiation", "is_custom_defined", "version",
        "print_settings_id", "printer_settings_id", "filament_settings_id", "print_timestamp", "printer_timestamp",
        "filament_timestamp", "updated_time", "base_id", "user_id", "compatible_printers", "compatible_prints"}


def _indice():
    idx = {}
    for f in glob.glob(os.path.join(PERFIS, "*", "*.json")):
        try:
            d = le_json(f)
        except (ValueError, OSError):
            continue
        if isinstance(d, dict) and "name" in d:
            k = (os.path.basename(os.path.dirname(f)), d["name"])
            idx[k], _ORIGEM[k] = d, "sistema"
    if not idx:
        raise SystemExit(f"Can't find the Anycubic Slicer Next profiles in {PERFIS}")
    for f in glob.glob(os.path.join(PERFIS_UTILIZADOR, "*", "*", "*.json")):
        tipo = os.path.basename(os.path.dirname(f))
        if tipo not in ("machine", "process", "filament"):
            continue
        try:
            d = le_json(f)
        except (ValueError, OSError):
            continue
        if not isinstance(d, dict) or "name" not in d or (tipo, d["name"]) in idx and _ORIGEM[(tipo, d["name"])] == "sistema":
            continue
        k, t = (tipo, d["name"]), os.path.getmtime(f)
        if k not in idx or t > _DATA.get(k, 0):     # o mesmo nome em duas contas: fica o mais recente
            idx[k], _ORIGEM[k], _DATA[k] = d, "utilizador", t
    return idx


def _idx():
    global _IDX
    _IDX = _IDX or _indice()
    return _IDX


def existe(tipo, nome):
    return (tipo, nome) in _idx()


def nomes(tipo):
    return sorted(n for t, n in _idx() if t == tipo)


def do_utilizador(tipo, nome):
    _idx()
    return _ORIGEM.get((tipo, nome)) == "utilizador"


def perfil(tipo, nome):
    """Perfil do Anycubic (de sistema ou do utilizador) com a heranca ('inherits') resolvida."""
    d = _idx()[(tipo, nome)]
    out = dict(perfil(tipo, d["inherits"])) if d.get("inherits") and existe(tipo, d["inherits"]) else {}
    out.update(d)
    return out


def raiz_sistema(tipo, nome):
    """Perfil de sistema em que um perfil (do utilizador) se baseia."""
    vistos = set()
    while do_utilizador(tipo, nome) and nome not in vistos:
        vistos.add(nome)
        pai = _idx()[(tipo, nome)].get("inherits")
        if not pai or not existe(tipo, pai):
            return None
        nome = pai
    return nome if existe(tipo, nome) else None


def meus(tipo):
    """[(nome, perfil de sistema base)] dos perfis do utilizador deste tipo, os mais recentes primeiro."""
    out = [(n, raiz_sistema(t, n)) for (t, n) in _idx() if t == tipo and do_utilizador(t, n)]
    return sorted(out, key=lambda x: -_DATA.get((tipo, x[0]), 0))


def meu_para(tipo, nome_sistema):
    """O perfil do utilizador mais recente baseado neste perfil de sistema (ou None)."""
    return next((n for n, b in meus(tipo) if b == nome_sistema), None)


def mudancas_do_utilizador(tipo, nome):
    """Definicoes que o utilizador mudou em relacao ao perfil de sistema base (para different_settings_to_system)."""
    base = raiz_sistema(tipo, nome)
    if not do_utilizador(tipo, nome) or not base:
        return []
    final, sis = perfil(tipo, nome), perfil(tipo, base)
    return sorted(k for k, v in final.items() if k not in META and not k.endswith("_settings_id") and sis.get(k) != v)


def grava_perfil(caminho, tipo, nome, mudancas):
    d = perfil(tipo, nome)
    d.update(mudancas)
    if do_utilizador(tipo, nome):
        # perfil do utilizador: tem de continuar a dizer em que perfil de sistema se baseia, senao a linha de
        # comandos do Anycubic recusa-o ("process not compatible with printer")
        d.update({"inherits": raiz_sistema(tipo, nome) or "", "from": "User", "type": tipo})
    else:
        d.update({"inherits": "", "from": "system", "type": tipo})
    cp = d.get("compatible_printers")
    if tipo != "machine" and isinstance(cp, list) and cp and MAQUINA not in cp:
        d["compatible_printers"] = cp + [MAQUINA]    # maquina do utilizador: senao "process not compatible with printer"
    grava_json(caminho, d)
    return caminho


def normaliza_tipo(v, modelo):
    """Mesmo formato (lista ou valor) que o perfil do Anycubic."""
    if isinstance(modelo, list) and not isinstance(v, list):
        return [v]
    if not isinstance(modelo, list) and isinstance(v, list):
        return v[0] if v else ""
    return v


def primeiro(v):
    return v[0] if isinstance(v, list) and v else v


# ------------------------------------------------------------------------------------- impressoras

def _instanciavel(d):
    return str(d.get("instantiation", "true")).lower() == "true"


def maquinas():
    """{modelo: {bico: nome da maquina}} de todas as impressoras Anycubic do slicer."""
    out = {}
    for (t, n), d in _idx().items():
        m = re.match(r"(.+?) (\d+(?:\.\d+)?) nozzle$", n)
        if t == "machine" and m and _instanciavel(d) and not do_utilizador(t, n):
            modelo = perfil("machine", n).get("printer_model") or m.group(1)
            out.setdefault(modelo, {})[format(float(m.group(2)), "g")] = n
    return out


def _norm(s):
    return re.sub(r"[^a-z0-9.]+", " ", s.lower().replace("anycubic", "")).strip()


def encontra_maquina(consulta=None, bico=None):
    """'Kobra S1', 'kobra-3-max', 'Kobra X 0.6', 'Anycubic Kobra X 0.4 nozzle'... -> nome da maquina no Anycubic."""
    consulta = (consulta or IMPRESSORA_OMISSAO).strip()
    if existe("machine", consulta):
        return consulta
    mb = re.search(r"\s(\d\.\d+)\s*(?:mm)?\s*(?:nozzle|bico)?\s*$", " " + consulta)
    if mb:
        bico = bico or mb.group(1)
        consulta = (" " + consulta)[:mb.start()].strip()
    ms = maquinas()
    q = _norm(consulta)
    exatos = [m for m in ms if _norm(m) == q]
    cands = exatos or [m for m in ms if q and q in _norm(m)]
    if len(cands) != 1:
        lista = ", ".join(sorted(m.replace("Anycubic ", "") for m in ms))
        raise SystemExit(f"Printer '{consulta}' is " + ("ambiguous" if cands else "unknown") + f". Available: {lista}")
    bicos = ms[cands[0]]
    b = format(float(bico), "g") if bico else "0.4"
    if b not in bicos:
        raise SystemExit(f"The {cands[0]} has no profiles for a {b} nozzle (available: {', '.join(sorted(bicos))})")
    return bicos[b]


def usa_impressora(maquina):
    """Passa a trabalhar para esta maquina: mesa, altura, passo entre pratos, ACE, sufixo dos perfis."""
    global MAQUINA, MAQUINA_SISTEMA, MODELO, SUF, BICO, CAMA_X, CAMA_Y, ALTURA_MAX, PASSO_X, PASSO_Y, MULTICOR, VOLUME_BICO
    d = perfil("machine", maquina)
    MAQUINA_SISTEMA = raiz_sistema("machine", maquina) or maquina
    pts = [tuple(float(v) for v in p.split("x")) for p in d.get("printable_area", ["0x0", "260x0", "260x260", "0x260"])]
    CAMA_X = max(p[0] for p in pts) - min(p[0] for p in pts)
    CAMA_Y = max(p[1] for p in pts) - min(p[1] for p in pts)
    ALTURA_MAX = float(primeiro(d.get("printable_height", "250")))
    PASSO_X, PASSO_Y = CAMA_X * 1.2, CAMA_Y * 1.2
    MULTICOR = len(str(d.get("change_filament_gcode", "")).strip()) > 20
    try:
        VOLUME_BICO = float(primeiro(d.get("nozzle_volume", "0")) or 0)
    except (TypeError, ValueError):
        VOLUME_BICO = 0.0
    MAQUINA, SUF = maquina, " @" + MAQUINA_SISTEMA
    MODELO = d.get("printer_model") or re.sub(r" \d+(\.\d+)? nozzle$", "", MAQUINA_SISTEMA)
    BICO = format(float(primeiro(d.get("nozzle_diameter", "0.4"))), "g")
    return d


def nome_curto():
    """'Kobra X', 'Kobra S1 0.6'..."""
    return MODELO.replace("Anycubic ", "") + ("" if BICO == "0.4" else f" {BICO}")


def impressora_do_projeto(j):
    """Num projeto do Anycubic, passa a usar a impressora dele. False se nao for uma Anycubic conhecida."""
    n = str(primeiro(j.get("printer_settings_id", "")))
    if existe("machine", n):
        usa_impressora(n)
        return True
    return False


def compativeis(tipo):
    """{nome base: nome completo} dos perfis de SISTEMA de processo/filamento desta maquina."""
    out = {}
    for (t, n), d in _idx().items():
        if t == tipo and _instanciavel(d) and not do_utilizador(t, n) and (
                n.endswith(SUF) or MAQUINA_SISTEMA in perfil(t, n).get("compatible_printers", [])):
            out[n.split(" @")[0]] = n
    return out


def meu_compativel(tipo, nome):
    """True se for um perfil do utilizador baseado num perfil de sistema desta maquina."""
    return do_utilizador(tipo, nome) and raiz_sistema(tipo, nome) in compativeis(tipo).values()


def fim_gcode():
    """Fim de impressao. O de fabrica da Kobra X, Kobra 4 e S1 Max desliga com o bico pousado em cima da peca (fio e
    bolinha no topo): junta-se antes um levantamento de 5 mm e afasta-se a cabeca. None = o de fabrica ja levanta."""
    fim = str(perfil("machine", MAQUINA).get("machine_end_gcode", ""))     # (o do utilizador, se for perfil dele)
    if re.search(r"G1\s+Z|max_layer_z|G91", fim):
        return None
    return ("M400\nG92 E0\n{if max_layer_z < max_print_height - 5}G1 Z{max_layer_z + 5} F900 ; lift the nozzle off the part{endif}\n"
            f"G1 X{CAMA_X - 10:g} Y{CAMA_Y - 10:g} F12000 ; move the head away before switching off\n" + fim.rstrip("\n") + "\n")


# ------------------------------------------------------------------------------- linha de comandos

def corre_cli(args, cwd, timeout=3600):
    """Corre o Anycubic Slicer Next. cwd = pasta temporaria: ele escreve certificados da impressora na pasta
    de trabalho e nao os queremos nas pastas do utilizador."""
    if not os.path.exists(ANY):
        raise SystemExit(f"Can't find Anycubic Slicer Next in {ANY} (set the ANYCUBIC_SLICER variable if it is elsewhere)")
    r = subprocess.run([ANY] + args, cwd=cwd, capture_output=True, text=True, errors="ignore", timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


DICAS_CLI = {
    "Variable layer height is not supported with Organic supports":
        "variable layer heights don't work with organic tree supports: use --sem-camadas-variaveis, or another support style",
    "process not compatible with printer": "the print profile is not for this printer (see --listar-perfis)",
    "Loading of a model file failed": "Anycubic couldn't read the model (broken file or a format it doesn't know)",
    "is too close to exclusion area": "some parts are on the bed's exclusion area: move them with pratos.py --centrar or --afastar",
    "is laid over the boundary of plate": "some parts are off the bed: scale down with escalar.py or arrange them with pratos.py",
    "postprocess not supported": "the project has post-processing scripts (post_process): Anycubic's command line doesn't accept them",
}


def explica_rc(rc, log):
    dica = ""
    if rc in (139, -11, 3221225477, -1073741819):
        dica = (" (Anycubic crashed: known causes = plate names that are not empty [already handled], a mesh in the"
                " middle of the bed below z=0, or a profile file with a wrong path)")
    linhas = [l for l in log.splitlines() if ("error" in l.lower() or "fail" in l.lower()) and "calc_exclude_triangles" not in l][-8:]
    for sinal, ajuda in DICAS_CLI.items():
        if sinal in log:
            dica += "\n  -> " + ajuda
    return f"code {rc}{dica}\n" + "\n".join(linhas)


def exporta(entrada, saida, maquina_json, processo_json, filamentos_json, cwd):
    args = ["--arrange", "0", "--load-settings", f"{maquina_json};{processo_json}",
            "--load-filaments", ";".join(filamentos_json), "--export-3mf", os.path.basename(saida),
            "--outputdir", os.path.dirname(saida), entrada]
    rc, log = corre_cli(args, cwd)
    if rc != 0 or not os.path.exists(saida):
        raise SystemExit("Anycubic failed to export: " + explica_rc(rc, log))


def cubo_stl(caminho, lado=10.0):
    """Cubo para o projeto de referencia (so servem as definicoes). O Anycubic so carrega um STL solto se estiver mais
    ou menos entre 60 e 125 mm, seja qual for a mesa (na origem ou a partir de ~150 mm da "Loading of a model file
    failed"), por isso fica sempre a 100 mm."""
    cx = cy = 100.0
    v = [(x + cx, y + cy, z) for z in (0, lado) for y in (0, lado) for x in (0, lado)]
    f = [(0, 2, 3), (0, 3, 1), (4, 5, 7), (4, 7, 6), (0, 1, 5), (0, 5, 4),
         (2, 6, 7), (2, 7, 3), (0, 4, 6), (0, 6, 2), (1, 3, 7), (1, 7, 5)]
    with open(caminho, "wb") as fh:
        fh.write(b"\0" * 80 + struct.pack("<I", len(f)))
        for a, b, c in f:
            fh.write(struct.pack("<3f", 0, 0, 0))
            for i in (a, b, c):
                fh.write(struct.pack("<3f", *v[i]))
            fh.write(b"\0\0")
    return caminho


# --------------------------------------------------------------------------------------- geometria

IDENT = [1.0, 0, 0, 0, 1.0, 0, 0, 0, 1.0, 0, 0, 0]


def atributos(tag):
    return dict(re.findall(r'([\w:]+)="([^"]*)"', tag))


def matriz(s):
    return [float(x) for x in s.split()] if s else list(IDENT)


def compoe(a, b):
    """3MF (vetor-linha, 3x4): aplica b e depois a."""
    out = [sum(b[i * 3 + k] * a[k * 3 + j] for k in range(3)) for i in range(3) for j in range(3)]
    tx, ty, tz = b[9:12]
    return out + [tx * a[0] + ty * a[3] + tz * a[6] + a[9], tx * a[1] + ty * a[4] + tz * a[7] + a[10],
                  tx * a[2] + ty * a[5] + tz * a[8] + a[11]]


def fmt_matriz(m):
    return " ".join(format(v, ".9g") for v in m)


class Modelo:
    """Le a estrutura de um 3MF (objetos, componentes, itens) e mede caixas no mundo.
    So contam as pecas normais: modificadores, pecas negativas e bloqueadores de suportes nao se imprimem."""

    def __init__(self, z):
        self.z = z
        self.root = z.read("3D/3dmodel.model").decode("utf-8")
        self.objs = {}
        for m in re.finditer(r'<object\s([^>]*)>(.*?)</object>', self.root, re.S):
            a = atributos(m.group(1))
            comps = []
            for c in re.finditer(r'<component\s([^>]*?)/?>', m.group(2)):
                ca = atributos(c.group(1))
                comps.append(((ca.get("p:path") or "/3D/3dmodel.model").lstrip("/"), ca["objectid"], matriz(ca.get("transform"))))
            if not comps and "<mesh" in m.group(2):
                comps = [("3D/3dmodel.model", a["id"], list(IDENT))]
            self.objs[a["id"]] = comps
        self.itens = []
        for it in re.finditer(r'<item\s([^>]*?)/?>', self.root):
            ia = atributos(it.group(1))
            self.itens.append({"oid": ia["objectid"], "T": matriz(ia.get("transform")), "printable": ia.get("printable", "1")})
        self._cache = {}
        self._cache_f = {}
        try:
            ms = z.read("Metadata/model_settings.config").decode("utf-8")
        except KeyError:
            ms = ""
        self.ms = ms
        self.nomes = {i: limpa_nome(n) for i, n in re.findall(r'<object id="(\d+)">\s*<metadata key="name" value="([^"]*)"', ms)}
        self.n_pratos = max(1, len(re.findall(r"<plate>", ms)))
        self.tipos = {}      # (objeto, peca) -> normal_part | modifier_part | negative_part | support_blocker...
        for o in re.finditer(r'<object id="(\d+)">(.*?)</object>', ms, re.S):
            for p in re.finditer(r'<part id="(\d+)" subtype="(\w+)"', o.group(2)):
                self.tipos[(o.group(1), p.group(1))] = p.group(2)

    def _vertices(self, path, oid):
        if path not in self._cache:
            t = self.z.read(path).decode("utf-8")
            d = {}
            for m in re.finditer(r'<object\s([^>]*)>(.*?)</object>', t, re.S):
                vm = re.search(r"<vertices>(.*?)</vertices>", m.group(2), re.S)
                if vm:
                    xs = re.findall(r'<vertex\s+x="([^"]+)"\s+y="([^"]+)"\s+z="([^"]+)"', vm.group(1))
                    d[atributos(m.group(1))["id"]] = np.array(xs, float) if np is not None else [tuple(map(float, p)) for p in xs]
            self._cache[path] = d
        return self._cache[path].get(oid)

    def _triangulos(self, path, oid):
        if path not in self._cache_f:
            t = self.z.read(path).decode("utf-8")
            d = {}
            for m in re.finditer(r'<object\s([^>]*)>(.*?)</object>', t, re.S):
                tm = re.search(r"<triangles>(.*?)</triangles>", m.group(2), re.S)
                if tm:
                    fs = re.findall(r'<triangle\s+v1="(\d+)"\s+v2="(\d+)"\s+v3="(\d+)"', tm.group(1))
                    d[atributos(m.group(1))["id"]] = np.array(fs, np.int64).reshape(-1, 3)
            self._cache_f[path] = d
        return self._cache_f[path].get(oid)

    def _folhas(self, oid, T, raiz=None, prof=0):
        """(path, id da malha, transformacao, tipo da peca) de cada malha do objeto."""
        raiz = raiz or oid
        for path, sid, C in self.objs.get(oid, []):
            M = compoe(T, C)
            if path == "3D/3dmodel.model" and sid in self.objs and sid != oid and prof < 5 and self._vertices(path, sid) is None:
                yield from self._folhas(sid, M, raiz, prof + 1)
            else:
                yield path, sid, M, self.tipos.get((raiz, sid), "normal_part")

    def _caixa(self, oid, T):
        folhas = list(self._folhas(oid, T))
        normais = [f for f in folhas if f[3] == "normal_part"] or folhas
        lo, hi = [math.inf] * 3, [-math.inf] * 3
        for path, sid, M, _ in normais:
            V = self._vertices(path, sid)
            if V is None or len(V) == 0:
                continue
            if np is not None:
                W = V @ np.array(M[:9]).reshape(3, 3) + np.array(M[9:])
                l2, h2 = W.min(0).tolist(), W.max(0).tolist()
            else:
                W = [(x * M[0] + y * M[3] + z * M[6] + M[9], x * M[1] + y * M[4] + z * M[7] + M[10],
                      x * M[2] + y * M[5] + z * M[8] + M[11]) for x, y, z in V]
                l2 = [min(p[i] for p in W) for i in range(3)]
                h2 = [max(p[i] for p in W) for i in range(3)]
            lo = [min(a, b) for a, b in zip(lo, l2)]
            hi = [max(a, b) for a, b in zip(hi, h2)]
        if math.inf in lo:
            lo = hi = [0.0, 0.0, 0.0]
        return lo, hi

    def caixas(self):
        out = []
        for i, it in enumerate(self.itens):
            lo, hi = self._caixa(it["oid"], it["T"])
            out.append(dict(it, i=i, nome=self.nomes.get(it["oid"], "object " + it["oid"]), lo=lo, hi=hi,
                            tam=[h - l for l, h in zip(lo, hi)]))
        return out

    def malha_item(self, i, T=None):
        """(vertices no mundo, triangulos) das pecas normais do item i. Precisa do numpy."""
        it = self.itens[i]
        folhas = list(self._folhas(it["oid"], T or it["T"]))
        normais = [f for f in folhas if f[3] == "normal_part"] or folhas
        Vs, Fs, base = [], [], 0
        for path, sid, M, _ in normais:
            V, F = self._vertices(path, sid), self._triangulos(path, sid)
            if V is None or F is None or len(V) == 0 or len(F) == 0:
                continue
            Vs.append(V @ np.array(M[:9]).reshape(3, 3) + np.array(M[9:]))
            Fs.append(F + base)
            base += len(V)
        if not Vs:
            return np.zeros((0, 3)), np.zeros((0, 3), np.int64)
        return np.vstack(Vs), np.vstack(Fs)


def colunas(n):
    r = round(math.sqrt(n))
    return r + 1 if math.sqrt(n) > r else r


def origem_prato(i, n):
    """Canto do prato i (1..n) nas coordenadas do projeto do Anycubic."""
    c = colunas(n)
    return ((i - 1) % c) * PASSO_X, -((i - 1) // c) * PASSO_Y


def prato_de(caixa, n):
    """Prato (1..n) em que esta o centro da caixa. Um objeto fora da grelha de pratos conta para o prato mais proximo
    (e aparece depois no aviso de pecas fora da mesa), em vez de dar um numero de prato que nao existe."""
    cx = (caixa["lo"][0] + caixa["hi"][0]) / 2
    cy = (caixa["lo"][1] + caixa["hi"][1]) / 2
    c = colunas(n)
    col = math.floor((cx + (PASSO_X - CAMA_X) / 2) / PASSO_X)
    lin = math.floor((CAMA_Y + (PASSO_Y - CAMA_Y) / 2 - cy) / PASSO_Y)
    col = min(max(col, 0), c - 1)
    lin = min(max(lin, 0), math.ceil(n / c) - 1)
    return min(lin * c + col + 1, n)


def caixas_por_prato(modelo):
    """{prato: [caixa com 'llo'/'lhi' em coordenadas locais da mesa]}"""
    out = {}
    for c in modelo.caixas():
        p = prato_de(c, modelo.n_pratos)
        ox, oy = origem_prato(p, modelo.n_pratos)
        c["prato"] = p
        c["llo"] = [c["lo"][0] - ox, c["lo"][1] - oy, c["lo"][2]]
        c["lhi"] = [c["hi"][0] - ox, c["hi"][1] - oy, c["hi"][2]]
        out.setdefault(p, []).append(c)
    return out


def avisos_mesa(por_prato, folga=0.5, sobreposicao=False):
    """Pecas fora da mesa / abaixo de z=0. Com sobreposicao=True tambem caixas que se cruzam (so quando nao ha numpy
    para medir a folga real com distancias.avisos_folgas)."""
    av = []
    for p, cs in sorted(por_prato.items()):
        for c in cs:
            if c["printable"] == "0":
                continue
            if min(c["llo"][:2]) < -folga or c["lhi"][0] > CAMA_X + folga or c["lhi"][1] > CAMA_Y + folga:
                av.append(f"plate {p}: '{c['nome']}' goes off the {CAMA_X:.0f} x {CAMA_Y:.0f} mm bed "
                          f"(x {c['llo'][0]:.1f}..{c['lhi'][0]:.1f}, y {c['llo'][1]:.1f}..{c['lhi'][1]:.1f})")
            if c["lhi"][2] > ALTURA_MAX:
                av.append(f"plate {p}: '{c['nome']}' is {c['lhi'][2]:.1f} mm tall (maximum {ALTURA_MAX:.0f})")
            if c["llo"][2] < -0.05:
                av.append(f"plate {p}: '{c['nome']}' is {-c['llo'][2]:.2f} mm below the bed")
        for i, a in enumerate(cs if sobreposicao else []):
            for b in cs[i + 1:]:
                if sep(ret(a), ret(b)) == 0 and a["oid"] != b["oid"]:
                    ix = min(a["lhi"][0], b["lhi"][0]) - max(a["llo"][0], b["llo"][0])
                    iy = min(a["lhi"][1], b["lhi"][1]) - max(a["llo"][1], b["llo"][1])
                    if ix > 1 and iy > 1:
                        av.append(f"plate {p}: the boxes of '{a['nome']}' and '{b['nome']}' overlap "
                                  f"({ix:.1f} x {iy:.1f} mm) - check whether the parts touch")
    return av


def ret(c):
    return (c["llo"][0], c["llo"][1], c["lhi"][0], c["lhi"][1])


def sep(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0)
    dy = max(b[1] - a[3], a[1] - b[3], 0)
    return max(dx, dy) if dx == 0 or dy == 0 else math.hypot(dx, dy)


def posicao_torre(rects, n_fil, largura=35.0, folga=10.0, livre=None):
    """Canto (wipe_tower_x, wipe_tower_y) da torre de purga, livre das pecas e o mais perto do centro.
    Pegada medida numa Kobra X: x de X-6 a X+largura+1, y de Y-7.5 a Y+20 com 2 cores (cresce com mais cores).
    livre(x0, y0, x1, y1) -> bool testa as pegadas reais (distancias.Pegadas.livre); sem isso usam-se as caixas."""
    fundo = 22 + 10 * max(0, n_fil - 2)
    melhor = None
    for X in range(12, int(CAMA_X - largura - 6), 2):
        for Y in range(12, int(CAMA_Y - fundo - 4), 2):
            tr = (X - 8, Y - 8, X + largura + 3, Y + fundo)
            if livre is not None:
                ok = livre(tr[0] - folga, tr[1] - folga, tr[2] + folga, tr[3] + folga)
            else:
                ok = all(sep(tr, r) >= folga for r in rects)
            if ok:
                d = math.hypot(X + largura / 2 - CAMA_X / 2, Y + fundo / 2 - CAMA_Y / 2)
                if melhor is None or d < melhor[0]:
                    melhor = (d, X, Y)
    return (melhor[1], melhor[2]) if melhor else None


# ---------------------------------------------------------------------------------------- fatiar

def tempo_segundos(texto):
    """'1d 2h 3m 4s' -> segundos."""
    s = 0
    for n, u in re.findall(r"(\d+)\s*([dhms])", texto or ""):
        s += int(n) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[u]
    return s


def tem_pos_processamento(j):
    """True se o projeto traz scripts de pos-processamento (post_process): comandos que um slicer corre no computador
    depois de fatiar. A skill nunca os passa nem os executa."""
    v = j.get("post_process")
    return bool([x for x in (v if isinstance(v, list) else [v]) if str(x or "").strip()])


def sem_pos_processamento(j):
    """Tira os scripts de pos-processamento de um project_settings (devolve True se tirou algum)."""
    if not tem_pos_processamento(j):
        return False
    j["post_process"] = [] if isinstance(j.get("post_process"), list) else ""
    return True


def fatia(projeto, pasta, cwd, avisos=None):
    """Fatia todos os pratos e devolve um resumo por prato (os .gcode ficam em `pasta`).
    Se o projeto tiver scripts de pos-processamento fatia-se uma copia sem eles (a linha de comandos do Anycubic
    recusa-os, e a skill nao corre comandos que venham dentro de um projeto); fica um aviso em `avisos`."""
    try:
        with zipfile.ZipFile(projeto) as z:
            jp = json.loads(z.read("Metadata/project_settings.config"))
    except KeyError:
        jp = {}                                # 3MF sem definicoes: nao ha nada para tirar
    except (ValueError, OSError, zipfile.BadZipFile):
        jp = None
    if not isinstance(jp, dict):               # nao se fatia o que nao se conseguiu verificar
        raise SystemExit(f"Couldn't read the settings of {os.path.basename(projeto)} (broken file): not slicing")
    limpar = tem_pos_processamento(jp)
    os.makedirs(pasta, exist_ok=True)
    if limpar:
        copia = os.path.join(pasta, "sem_pos_processamento.3mf")

        def mudar(nome, d):
            if nome != "Metadata/project_settings.config":
                return d
            j = json.loads(d)
            sem_pos_processamento(j)
            return json.dumps(j, indent=4, ensure_ascii=False).encode("utf-8")
        reescreve(projeto, copia, mudar)
        projeto = copia
        if avisos is not None:
            avisos.append("the project has post-processing scripts (post_process): time and grams were calculated without them "
                          "(the skill never runs commands that come inside a project)")
    rc, log = corre_cli(["--slice", "0", "--outputdir", pasta, projeto], cwd)
    gs = sorted(glob.glob(os.path.join(pasta, "plate_*.gcode")), key=lambda f: int(re.findall(r"\d+", os.path.basename(f))[0]))
    if rc != 0 or not gs:
        raise SystemExit("Anycubic failed to slice: " + explica_rc(rc, log))
    out = {}
    for g in gs:
        r = resumo_gcode(g)
        r["ficheiro"] = g
        out[int(re.findall(r"\d+", os.path.basename(g))[0])] = r
    return out


def _numeros(texto):
    try:
        return [float(x) for x in texto.replace(";", ",").split(",") if x.strip()]
    except ValueError:
        return []


def gramas_por_ferramenta(g, total, mm, densidades, diametros):
    """O Anycubic Slicer Next 2.0.0.7 poe no resumo do fim do g-code o peso todo no ultimo filamento usado
    ("; filament used [g] = 0.00, 34.07" num prato a duas cores; o g-code em si esta certo). Quando o resumo nao bate
    com o que cada ferramenta extrude de facto (mm = E liquido por ferramenta, extrusao relativa), divide-se o total
    (que esta certo) pela massa extrudida por cada uma."""
    if len(g) < 2 or not total or not mm:
        return g
    massa = []
    for i in range(len(g)):
        d = diametros[i] if i < len(diametros) and diametros[i] > 0 else 1.75
        p = densidades[i] if i < len(densidades) and densidades[i] > 0 else 1.24
        massa.append(max(mm.get(i, 0.0), 0.0) * math.pi * (d / 2) ** 2 * p)
    soma, lido = sum(massa), sum(g)
    if soma <= 0:
        return g
    certo = [m / soma for m in massa]
    parte = [x / lido if lido > 0 else 0.0 for x in g]
    if all((parte[i] > 0) == (certo[i] >= 0.005) and abs(parte[i] - certo[i]) <= 0.1 for i in range(len(g))):
        return g
    return [round(total * c, 2) for c in certo]


def resumo_gcode(caminho):
    r = {"tempo": None, "g": [], "total_g": None, "camadas": None, "trocas": 0, "altura": None, "torre": None, "pecas": None}
    tipo = None
    caixas = {}
    ferramenta, relativo, absoluto, mm, dens, diam = None, False, False, {}, [], []
    with open(caminho, encoding="utf-8", errors="ignore") as f:
        for l in f:
            if l.startswith(";"):
                if l.startswith(";TYPE:"):
                    tipo = l[6:].strip()
                elif l.startswith("; estimated printing time (normal mode) = "):
                    r["tempo"] = l.split("= ", 1)[1].strip()
                elif l.startswith("; filament used [g] = "):
                    r["g"] = [float(x) for x in l.split("= ", 1)[1].split(",") if x.strip()]
                elif l.startswith("; total filament used [g] = "):
                    r["total_g"] = float(l.split("= ", 1)[1])
                elif l.startswith("; total layers count = "):
                    r["camadas"] = int(l.split("= ", 1)[1])
                elif l.startswith("; total filament change = "):
                    r["trocas"] = int(l.split("= ", 1)[1])
                elif l.startswith("; max_z_height:"):
                    r["altura"] = float(l.split(":", 1)[1])
                elif l.startswith("; filament_density:"):
                    dens = _numeros(l.split(":", 1)[1])
                elif l.startswith("; filament_diameter:"):
                    diam = _numeros(l.split(":", 1)[1])
                continue
            # o que cada ferramenta extrude (para conferir o resumo do fim; ver gramas_por_ferramenta)
            if l[:1] == "T" and l[1:2].isdigit():
                m = re.match(r"T(\d+)\s*(?:;|$)", l)
                if m:
                    ferramenta = int(m.group(1))
                continue
            if l.startswith("M83"):
                relativo = True
            elif l.startswith("M82"):
                absoluto = True
            elif ferramenta is not None and relativo and l[:3] in ("G1 ", "G0 ", "G2 ", "G3 ") and "E" in l:
                me = re.search(r" E(-?[\d.]+)", l.split(";", 1)[0])
                if me:
                    mm[ferramenta] = mm.get(ferramenta, 0.0) + float(me.group(1))
            if tipo and tipo != "Custom" and l.startswith("G1 ") and " E" in l:
                mx = re.search(r" X([-\d.]+)", l)
                my = re.search(r" Y([-\d.]+)", l)
                if mx and my:
                    k = "torre" if "tower" in tipo.lower() else "pecas"
                    x, y = float(mx.group(1)), float(my.group(1))
                    e = caixas.setdefault(k, [x, y, x, y])
                    e[0], e[1], e[2], e[3] = min(e[0], x), min(e[1], y), max(e[2], x), max(e[3], y)
    r.update(caixas)
    if not absoluto:
        r["g"] = gramas_por_ferramenta(r["g"], r["total_g"], mm, dens, diam)
    r["segundos"] = tempo_segundos(r["tempo"])
    r["camada_media"] = round(r["altura"] / r["camadas"], 3) if r["altura"] and r["camadas"] else None
    return r


def texto_resumo(res, cores=None):
    linhas = []
    for p, r in sorted(res.items()):
        g = " + ".join(f"{v:.1f} g" + (f" ({cores[i]})" if cores and i < len(cores) else "") for i, v in enumerate(r["g"]))
        t = f"plate {p}: {r['tempo']}, {r['total_g']} g" + (f" [{g}]" if len(r["g"]) > 1 else "")
        t += f", {r['camadas']} layers, height {r['altura']} mm"
        if r["trocas"]:
            t += f", {r['trocas']} color change{'s' if r['trocas'] > 1 else ''}"
        linhas.append(t)
    return "\n".join(linhas)


def colisoes_torre(res, por_prato, folga=2.0, pegadas=None):
    """A torre de purga (medida no g-code) em cima ou encostada a pecas. pegadas = {prato: distancias.Pegadas} testa
    a forma real das pecas; sem isso usam-se as caixas."""
    av = []
    for p, r in res.items():
        if not r.get("torre"):
            continue
        t = r["torre"]
        if pegadas and pegadas.get(p) is not None:
            if not pegadas[p].livre(t[0] - folga, t[1] - folga, t[2] + folga, t[3] + folga):
                av.append(f"plate {p}: the prime tower (x {t[0]:.0f}..{t[2]:.0f}, y {t[1]:.0f}..{t[3]:.0f}) "
                          f"is touching or on top of a part")
            continue
        for c in por_prato.get(p, []):
            if sep(tuple(t), ret(c)) < folga:
                av.append(f"plate {p}: the prime tower (x {t[0]:.0f}..{t[2]:.0f}, y {t[1]:.0f}..{t[3]:.0f}) "
                          f"is touching or on top of '{c['nome']}'")
    return av


# --------------------------------------------------------------------------------- reescrever zip

def reescreve(src, dst, mudar):
    """Copia um 3MF mudando ficheiros: mudar(nome, bytes) -> bytes | None (None = apagar)."""
    tmp = dst + ".tmp"
    try:
        with zipfile.ZipFile(src) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
            for it in zi.infolist():
                d = mudar(it.filename, zi.read(it.filename))
                if d is not None:
                    zo.writestr(it, d)
    except BaseException:                      # (incluindo SystemExit de uma verificacao): nao fica meio ficheiro
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    os.replace(tmp, dst)


# ------------------------------------------------------------------------------ copias de seguranca

MAX_COPIAS = 30


def _indice_copias():
    try:
        d = le_json(os.path.join(PASTA_DADOS, "copias", "indice.json"))
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def copias():
    """Copias de seguranca guardadas (a mais recente primeiro): [{quando, original, copia, motivo}]."""
    return [c for c in reversed(_indice_copias()) if os.path.exists(c.get("copia", ""))]


def guarda_copia(caminho, motivo=""):
    """Antes de substituir um ficheiro: guarda-o em <dados>/copias (as ultimas 30) e devolve o caminho da copia.
    None se o ficheiro ainda nao existia."""
    if not caminho or not os.path.isfile(caminho):
        return None
    pasta = os.path.join(PASTA_DADOS, "copias")
    os.makedirs(pasta, exist_ok=True)
    quando = time.strftime("%Y-%m-%d %H:%M:%S")
    base = time.strftime("%Y%m%d-%H%M%S") + "__" + os.path.basename(caminho)
    destino, n = os.path.join(pasta, base), 1
    while os.path.exists(destino):
        n += 1
        destino = os.path.join(pasta, f"{n}_{base}")
    shutil.copy2(caminho, destino)
    idx = _indice_copias()
    idx.append({"quando": quando, "original": os.path.abspath(caminho), "copia": destino, "motivo": motivo})
    for velho in idx[:-MAX_COPIAS]:
        try:
            os.remove(velho["copia"])
        except OSError:
            pass
    idx = idx[-MAX_COPIAS:]
    grava_json(os.path.join(pasta, "indice.json"), idx)
    return destino
