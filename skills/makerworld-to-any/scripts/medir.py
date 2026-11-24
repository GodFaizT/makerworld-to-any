"""Mede um projeto 3MF (original Bambu ou adaptado Anycubic): tamanho de cada objeto e, opcionalmente, fatia.

Uso:
    python medir.py <ficheiro.3mf> [--fatiar]

Num projeto Anycubic tambem diz em que prato esta cada objeto, a posicao na mesa da impressora e avisos
(fora da mesa, pecas encostadas, torre de purga em cima de pecas).
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True
import anycubic as K


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ficheiro")
    ap.add_argument("--fatiar", action="store_true")
    a = ap.parse_args()
    z = zipfile.ZipFile(a.ficheiro)
    j = json.loads(z.read("Metadata/project_settings.config"))
    impressora = str(K.primeiro(j.get("printer_settings_id", "")))
    print("impressora:", impressora, "| perfil:", K.primeiro(j.get("print_settings_id", "")),
          "| filamentos:", j.get("filament_settings_id"), j.get("filament_colour"))
    mod = K.Modelo(z)
    kobra = K.impressora_do_projeto(j)
    if kobra:
        print(f"mesa da {K.MODELO}: {K.CAMA_X:g} x {K.CAMA_Y:g} x {K.ALTURA_MAX:g} mm")
        por_prato = K.caixas_por_prato(mod)
        for p, cs in sorted(por_prato.items()):
            for c in cs:
                print(f"prato {p}: {c['nome']}: {c['tam'][0]:.1f} x {c['tam'][1]:.1f} x {c['tam'][2]:.1f} mm "
                      f"(x {c['llo'][0]:.1f}..{c['lhi'][0]:.1f}, y {c['llo'][1]:.1f}..{c['lhi'][1]:.1f})")
        avisos = K.avisos_mesa(por_prato, sobreposicao=True)
    else:
        for c in mod.caixas():
            print(f"{c['nome']}: {c['tam'][0]:.1f} x {c['tam'][1]:.1f} x {c['tam'][2]:.1f} mm")
        avisos = []
    z.close()
    if a.fatiar:
        if not kobra:
            raise SystemExit("--fatiar so para projetos de impressoras Anycubic (adapta primeiro)")
        tmp = tempfile.mkdtemp(prefix="mw2any_med_")
        try:
            res = K.fatia(os.path.abspath(a.ficheiro), os.path.join(tmp, "fatiado"), tmp)
            print("FATIADO:\n  " + K.texto_resumo(res, j.get("filament_colour")).replace("\n", "\n  "))
            avisos += K.colisoes_torre(res, por_prato)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("AVISOS:" if avisos else "AVISOS: nenhum")
    for av in avisos:
        print("  -", av)


if __name__ == "__main__":
    main()
