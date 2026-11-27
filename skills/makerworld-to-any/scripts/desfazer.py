"""Repoe a versao anterior de um ficheiro que a skill substituiu.
MakerWorld to Any - feito pela Megatic (https://megatic.pt).

Sempre que adaptar.py, escalar.py, pratos.py ou cores.py substituem um ficheiro, guardam antes uma copia (as ultimas
30) na pasta de dados da skill.

Uso:
    python desfazer.py --listar            copias guardadas (a mais recente primeiro)
    python desfazer.py <ficheiro>          repoe a copia mais recente desse ficheiro
    python desfazer.py --copia 3           repoe a copia numero 3 da lista, no sitio de onde veio

O ficheiro que la estava fica tambem guardado como copia, por isso da para desfazer o desfazer.
"""
import argparse
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
import anycubic as K


def main():
    ap = argparse.ArgumentParser(description="Restore the previous version of a file (MakerWorld to Any)")
    ap.add_argument("ficheiro", nargs="?", help="restores the most recent backup of this file")
    ap.add_argument("--listar", action="store_true", help="saved backups (most recent first)")
    ap.add_argument("--copia", type=int, metavar="N", help="restores backup N of the list, where it came from")
    a = ap.parse_args()
    cs = K.copias()
    if a.listar or not (a.ficheiro or a.copia):
        if not cs:
            print("There are no saved backups.")
            return
        print(f"Backups saved in {os.path.join(K.PASTA_DADOS, 'copias')}:")
        for n, c in enumerate(cs, 1):
            print(f"  {n}  {c['quando']}  {os.path.basename(c['original'])}  [{c.get('motivo') or '-'}]  from {os.path.dirname(c['original'])}")
        return
    if a.copia:
        if not 1 <= a.copia <= len(cs):
            raise SystemExit(f"There is no backup {a.copia} (there are {len(cs)})")
        c = cs[a.copia - 1]
    else:
        alvo = os.path.normcase(os.path.abspath(a.ficheiro))
        c = next((c for c in cs if os.path.normcase(c["original"]) == alvo), None)
        if c is None:
            raise SystemExit(f"There are no backups of {a.ficheiro} (see desfazer.py --listar)")
    destino = c["original"]
    tmp = tempfile.mkdtemp(prefix="mw2any_desfazer_")
    try:
        # primeiro poe-se a salvo a copia a repor: com as 30 copias cheias, guardar a versao atual apagava a mais antiga,
        # que pode ser precisamente esta
        a_repor = os.path.join(tmp, "copia")
        shutil.copy2(c["copia"], a_repor)
        atual = K.guarda_copia(destino, "before undo")
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        shutil.copy2(a_repor, destino)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"Restored: {destino}")
    print(f"  it is now the version from {c['quando']} (saved before: {c.get('motivo') or '-'})")
    if atual:
        print(f"  the version that was there was saved in {atual}")


if __name__ == "__main__":
    main()
