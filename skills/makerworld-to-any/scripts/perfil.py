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
    print("MakerWorld to Any (Megatic) - preferencias")
    print(f"  perfis por omissao : {'os teus (quando existem; senao os da Anycubic)' if perfis == 'meus' else 'os da Anycubic'}"
          + ("   [variavel de ambiente]" if os.environ.get("MAKERWORLD_TO_ANY_PERFIS") else ""))
    print(f"  impressora         : {imp}" + ("   [variavel de ambiente]" if os.environ.get("MAKERWORLD_TO_ANY_IMPRESSORA") else ""))
    print(f"  pasta dos adaptados: {cfg.get('saida') or '(ao lado do original, ou a pasta Adaptado <impressora> se existir)'}")
    print(f"  pasta dos originais: {cfg.get('originais') or '(os originais ficam onde estao)'}")
    if cfg.get("precos") or cfg.get("preco_hora"):
        pk = "; ".join(f"{k}={v:g}" for k, v in sorted((cfg.get("precos") or {}).items()))
        print(f"  precos             : filamento {pk or '-'} EUR/kg | maquina {float(cfg.get('preco_hora') or 0):g} EUR/h")
    else:
        print("  precos             : (sem precos: o relatorio nao mostra custo)")
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


def precos(texto):
    out = {}
    # separados por ";" (ou por "," quando o que vem a seguir e outro material=preco: "20,5" e um preco)
    for par in re.split(r";|,(?=[^,;]*=)", texto):
        par = par.strip()
        if not par:
            continue
        if "=" not in par:
            raise SystemExit(f"Nao percebi '{par}': usa material=preco (ex.: \"PLA=18;PETG=20;*=22\")")
        mat, v = par.rsplit("=", 1)
        try:
            out[mat.strip().upper() if mat.strip() != "*" else "*"] = float(v.replace(",", ".").replace("€", "").strip())
        except ValueError:
            raise SystemExit(f"Preco invalido em '{par}'")
    return out


def main():
    ap = argparse.ArgumentParser(description="Preferencias da MakerWorld to Any")
    ap.add_argument("modo", nargs="?", help="meus | anycubic")
    ap.add_argument("--impressora", help='impressora por omissao, ex. "Kobra S1"')
    ap.add_argument("--saida", metavar="PASTA", help="pasta dos adaptados ({impressora} = modelo)")
    ap.add_argument("--originais", metavar="PASTA", help="pasta para onde vao os originais depois de adaptados")
    ap.add_argument("--preco-kg", metavar="LISTA", help='euros por kg, ex. "PLA=18;PETG=20;*=22"')
    ap.add_argument("--preco-hora", type=float, metavar="EUR", help="euros por hora de maquina")
    ap.add_argument("--apagar", metavar="CHAVE", action="append", help="tira uma preferencia: " + ", ".join(CHAVES))
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
            raise SystemExit(f"Nao conheco '{chave}'. Ha: " + ", ".join(CHAVES))
        mudou[chave] = None
    if mudou:
        K.grava_config(**mudou)
        print("Guardado:", ", ".join(f"{k} = {v if v is not None else '(apagado)'}" for k, v in mudou.items()))
        print()
    mostra()


if __name__ == "__main__":
    main()
