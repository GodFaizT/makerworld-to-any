"""Preferencias da MakerWorld to Any: que perfis usar por omissao e para que impressora.
Feito pela Megatic - https://megatic.pt

Uso:
    python perfil.py                              mostra o que esta escolhido e os perfis que tens no slicer
    python perfil.py meus                         passa a usar sempre os teus perfis (quando existem)
    python perfil.py anycubic                     volta aos perfis de origem da Anycubic (tambem: sistema)
    python perfil.py --impressora "Kobra S1"      muda a impressora por omissao
    python perfil.py meus --impressora "Kobra X"  as duas coisas de uma vez

Fica guardado em %APPDATA%/makerworld-to-any/config.json. A variavel de ambiente MAKERWORLD_TO_ANY_PERFIS /
MAKERWORLD_TO_ANY_IMPRESSORA, se existir, manda sobre isto; e uma opcao no comando manda sobre tudo.
"""
import argparse
import os
import sys

sys.dont_write_bytecode = True
import anycubic as K

MODOS = {"meus": "meus", "minhas": "meus", "teus": "meus", "user": "meus",
         "anycubic": "sistema", "sistema": "sistema", "oficiais": "sistema", "default": "sistema", "origem": "sistema"}


def mostra():
    cfg = K.le_config()
    perfis = os.environ.get("MAKERWORLD_TO_ANY_PERFIS") or cfg.get("perfis") or "sistema"
    imp = os.environ.get("MAKERWORLD_TO_ANY_IMPRESSORA") or cfg.get("impressora") or "Kobra X"
    print("MakerWorld to Any (Megatic) - preferencias")
    print(f"  perfis por omissao : {'os teus (quando existem; senao os da Anycubic)' if perfis == 'meus' else 'os da Anycubic'}"
          + ("   [variavel de ambiente]" if os.environ.get("MAKERWORLD_TO_ANY_PERFIS") else ""))
    print(f"  impressora         : {imp}" + ("   [variavel de ambiente]" if os.environ.get("MAKERWORLD_TO_ANY_IMPRESSORA") else ""))
    print(f"  guardado em        : {K.CONFIG}" + ("" if os.path.exists(K.CONFIG) else " (ainda nao existe: valores por omissao)"))
    try:
        K.usa_impressora(K.encontra_maquina(imp))
        alvo = K.MAQUINA_SISTEMA
    except SystemExit:
        alvo = None
    print("Perfis teus no Anycubic Slicer Next:")
    algum = False
    for tipo, titulo in (("machine", "impressora"), ("process", "impressao"), ("filament", "filamento")):
        for n, base in K.meus(tipo):
            algum = True
            serve = ""
            if alvo:
                ok = base == alvo if tipo == "machine" else K.meu_compativel(tipo, n)
                serve = "  <- para a tua impressora" if ok else ""
            print(f"  [{titulo}] {n}   (baseado em {base or '?'}){serve}")
    if not algum:
        print("  nenhum (no Anycubic Slicer Next: muda um perfil e guarda-o com outro nome)")


def main():
    ap = argparse.ArgumentParser(description="Preferencias da MakerWorld to Any (perfis e impressora por omissao)")
    ap.add_argument("modo", nargs="?", help="meus | anycubic")
    ap.add_argument("--impressora", help='impressora por omissao, ex. "Kobra S1"')
    a = ap.parse_args()
    mudou = {}
    if a.modo:
        m = MODOS.get(a.modo.strip().lower())
        if not m:
            raise SystemExit(f"Nao percebi '{a.modo}'. Usa: meus | anycubic")
        mudou["perfis"] = m
    if a.impressora:
        maq = K.encontra_maquina(a.impressora)          # valida (sai com a lista se nao existir)
        K.usa_impressora(maq)
        mudou["impressora"] = K.nome_curto()
    if mudou:
        K.grava_config(**mudou)
        print("Guardado:", ", ".join(f"{k} = {v}" for k, v in mudou.items()))
        print()
    mostra()


if __name__ == "__main__":
    main()
