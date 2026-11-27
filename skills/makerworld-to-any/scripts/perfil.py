r"""Preferencias da MakerWorld to Any: perfis e impressora por omissao, pastas e precos.
Feito pela Megatic - https://megatic.pt

Uso:
    python perfil.py                              mostra o que esta escolhido e os perfis que tens no slicer
    python perfil.py meus                         passa a usar sempre os teus perfis (quando existem)
    python perfil.py anycubic                     volta aos perfis de origem da Anycubic (tambem: sistema)
    python perfil.py --impressora "Kobra S1"      impressora por omissao
    python perfil.py --saida "D:\Impressoes\Adaptado {impressora}"   pasta onde ficam os adaptados
    python perfil.py --originais "D:\Impressoes\Originais"           pasta para onde vao os originais
    python perfil.py --preco-kg "PLA=18;PETG=20;*=22" --preco-hora 0.40    para o custo estimado de cada trabalho
    python perfil.py --apagar saida               tira uma preferencia (saida, originais, precos, preco_hora...)

Pastas: com --saida, os adaptados vao sempre para essa pasta ({impressora} e trocado pelo modelo). Com --originais,
um original largado na pasta-mae dessa pasta e movido para la depois de adaptado.
Precos: euros por kg de cada material (procura "PLA Matte", depois "PLA", depois "*") e euros por hora de maquina.

Fica guardado em %APPDATA%/makerworld-to-any/config.json (fora da pasta da skill: nao se perde ao atualizar).
Uma variavel de ambiente MAKERWORLD_TO_ANY_PERFIS / MAKERWORLD_TO_ANY_IMPRESSORA manda sobre isto; e uma opcao no
comando manda sobre tudo.
"""
import argparse
import os
import re
import sys

sys.dont_write_bytecode = True
import anycubic as K

MODOS ={"meus": "meus", "minhas": "meus", "teus": "meus", "user": "meus",
         "anycubic": "sistema", "sistema": "sistema", "oficiais": "sistema", "default": "sistema", "origem": "sistema"}
CHAVES = ("perfis", "impressora", "saida", "originais", "precos", "preco_hora")


def mostra():
    cfg = K.le_config()
    perfis = os.environ.get("MAKERWORLD_TO_ANY_PERFIS") or cfg.get("perfis") or "sistema"
    imp = os.environ.get("MAKERWORLD_TO_ANY_IMPRESSORA") or cfg.get("impressora") or "Kobra X"
    print("MakerWorld to Any (Megatic) - settings")
    print("  default profiles   : " + ("yours (when they exist; otherwise Anycubic's)" if perfis == "meus" else "Anycubic's")
          + ("   [environment variable]" if os.environ.get("MAKERWORLD_TO_ANY_PERFIS") else ""))
    print(f"  printer            : {imp}" + ("   [environment variable]" if os.environ.get("MAKERWORLD_TO_ANY_IMPRESSORA") else ""))
    print(f"  adapted folder     : {cfg.get('saida') or '(next to the original, or the Adaptado <printer> folder if it exists)'}")
    print(f"  originals folder   : {cfg.get('originais') or '(originals stay where they are)'}")
    if cfg.get("precos") or cfg.get("preco_hora"):
        pk = "; ".join(f"{k}={v:g}" for k, v in sorted((cfg.get("precos") or {}).items()))
        print(f"  prices             : filament {pk or '-'} EUR/kg | machine {float(cfg.get('preco_hora') or 0):g} EUR/h")
    else:
        print("  prices             : (no prices: the report shows no cost)")
    print(f"  saved in           : {K.CONFIG}" + ("" if os.path.exists(K.CONFIG) else " (doesn't exist yet: defaults)"))
    try:
        K.usa_impressora(K.encontra_maquina(imp))
        alvo = K.MAQUINA_SISTEMA
    except SystemExit:
        alvo = None
    print("Your profiles in Anycubic Slicer Next:")
    algum = False
    for tipo, titulo in (("machine", "printer"), ("process", "process"), ("filament", "filament")):
        for n, base in K.meus(tipo):
            algum = True
            serve = ""
            if alvo:
                ok = base == alvo if tipo == "machine" else K.meu_compativel(tipo, n)
                serve = "  <- for your printer" if ok else ""
            print(f"  [{titulo}] {n}   (based on {base or '?'}){serve}")
    if not algum:
        print("  none (in Anycubic Slicer Next: change a profile and save it under another name)")


def precos(texto):
    out = {}
    # separados por ";" (ou por "," quando o que vem a seguir e outro material=preco: "20,5" e um preco)
    for par in re.split(r";|,(?=[^,;]*=)", texto):
        par = par.strip()
        if not par:
            continue
        if "=" not in par:
            raise SystemExit(f"I didn't understand '{par}': use material=price (e.g. \"PLA=18;PETG=20;*=22\")")
        mat, v = par.rsplit("=", 1)
        try:
            out[mat.strip().upper() if mat.strip() != "*" else "*"] = float(v.replace(",", ".").replace("€", "").strip())
        except ValueError:
            raise SystemExit(f"Invalid price in '{par}'")
    return out


def main():
    ap = argparse.ArgumentParser(description="MakerWorld to Any settings")
    ap.add_argument("modo", nargs="?", help="meus | anycubic")
    ap.add_argument("--impressora", help='default printer, e.g. "Kobra S1"')
    ap.add_argument("--saida", metavar="FOLDER", help="folder for adapted files ({impressora} = the printer model)")
    ap.add_argument("--originais", metavar="FOLDER", help="folder the originals go to after they are adapted")
    ap.add_argument("--preco-kg", metavar="LIST", help='euros per kg, e.g. "PLA=18;PETG=20;*=22"')
    ap.add_argument("--preco-hora", type=float, metavar="EUR", help="euros per machine hour")
    ap.add_argument("--apagar", metavar="KEY", action="append", help="removes a setting: " + ", ".join(CHAVES))
    a = ap.parse_args()
    mudou = {}
    if a.modo:
        m = MODOS.get(a.modo.strip().lower())
        if not m:
            raise SystemExit(f"I didn't understand '{a.modo}'. Use: meus | anycubic")
        mudou["perfis"] = m
    if a.impressora:
        maq = K.encontra_maquina(a.impressora)          # valida (sai com a lista se nao existir)
        K.usa_impressora(maq)
        mudou["impressora"] = K.nome_curto()
    for chave, v in (("saida", a.saida), ("originais", a.originais)):
        if v:
            mudou[chave] = v if "{impressora}" in v else os.path.abspath(os.path.expandvars(os.path.expanduser(v)))
    if a.preco_kg:
        atuais = dict(K.le_config().get("precos") or {})
        atuais.update(precos(a.preco_kg))
        mudou["precos"] = atuais
    if a.preco_hora is not None:
        mudou["preco_hora"] = a.preco_hora
    for chave in a.apagar or []:
        if chave not in CHAVES:
            raise SystemExit(f"Unknown setting '{chave}'. There are: " + ", ".join(CHAVES))
        mudou[chave] = None
    if mudou:
        K.grava_config(**mudou)
        print("Saved:", ", ".join(f"{k} = {v if v is not None else '(removed)'}" for k, v in mudou.items()))
        print()
    mostra()


if __name__ == "__main__":
    main()
