r"""Diagnostico da MakerWorld to Any: ve se esta tudo no sitio e, se pedido, faz um teste completo.
Feito pela Megatic - https://megatic.pt

Uso:
    python diagnostico.py                  verificacoes rapidas (Python, Anycubic Slicer Next, perfis, preferencias)
    python diagnostico.py --teste          + teste de ponta a ponta com um projeto de exemplo (menos de 1 minuto)
    python diagnostico.py --teste --impressora "Kobra S1"
    python diagnostico.py --json

O teste cria um projeto de exemplo no formato do Bambu Studio (2 pratos com nome, 4 filamentos com 2 em uso,
definicoes mudadas pelo "autor"), adapta-o, muda cores, junta e afasta pratos, muda o tamanho e fatia - tudo numa
pasta temporaria, sem tocar nos teus ficheiros nem nas tuas copias de seguranca. Serve para confirmar que a skill
funciona depois de uma atualizacao do Anycubic Slicer Next.
Sai com codigo 1 se alguma verificacao falhar (os avisos nao contam).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True
import anycubic as K

RES = []      # (estado, texto): estado = ok | aviso | falha


def diz(estado, texto):
    RES.append((estado, texto))


def versao_slicer():
    """Versao do Anycubic Slicer Next instalado (do ficheiro de configuracao dele; so se le a versao)."""
    conf = os.path.join(os.environ.get("APPDATA", ""), "AnycubicSlicerNext", "AnycubicSlicerNext.conf")
    try:
        with open(conf, encoding="utf-8", errors="ignore") as f:
            t = f.read()
        m = re.search(r'"app"\s*:\s*\{.*?"version"\s*:\s*"([^"]+)"', t, re.S)
        return m.group(1) if m else None
    except OSError:
        return None


def tupla(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or ""))


def rapido(impressora=None):
    v = sys.version_info
    diz("ok" if v >= (3, 8) else "falha", f"Python {v.major}.{v.minor}.{v.micro}" + ("" if v >= (3, 8) else " (precisa do 3.8 ou mais novo)"))
    try:
        import numpy
        diz("ok", f"numpy {numpy.__version__} (folgas reais entre pecas, afastar pecas)")
    except ImportError:
        diz("aviso", "sem numpy: funciona, mas mais devagar e sem medir a folga real entre pecas (pip install numpy)")
    try:
        import matplotlib
        diz("ok", f"matplotlib {matplotlib.__version__} (medir.py --imagem)")
    except ImportError:
        diz("aviso", "sem matplotlib: medir.py --imagem nao desenha os pratos (pip install matplotlib)")

    base = os.path.dirname(os.path.dirname(K.AQUI))
    irmas = sorted(d for d in os.listdir(base) if os.path.isfile(os.path.join(base, d, "SKILL.md")) and d != "makerworld-to-any") \
        if os.path.isdir(base) else []
    diz("ok", f"MakerWorld to Any {K.versao()} em {os.path.dirname(K.AQUI)}")
    cmds = [d for d in irmas if d.startswith(("kobra", "any"))]
    if cmds:
        diz("ok", "comandos: " + " ".join("/" + c for c in cmds))
    else:
        diz("aviso", "nao encontrei os comandos (/kobrax, /any-perfil...) ao lado da skill: reinstala para os teres")

    if os.path.exists(K.ANY):
        vs = versao_slicer()
        if not vs:
            diz("aviso", f"Anycubic Slicer Next em {K.ANY} (nao consegui ver a versao; testada com a {K.TESTADO_COM})")
        elif tupla(vs) == tupla(K.TESTADO_COM):
            diz("ok", f"Anycubic Slicer Next {vs} em {K.ANY}")
        else:
            diz("aviso", f"Anycubic Slicer Next {vs}: a skill foi testada com a {K.TESTADO_COM}. Corre 'diagnostico.py --teste' "
                         "para confirmar que continua tudo a funcionar")
    else:
        diz("falha", f"nao encontro o Anycubic Slicer Next em {K.ANY} (instala-o, ou define ANYCUBIC_SLICER com o caminho)")

    try:
        ms = K.maquinas()
        np_, nf = len(K.nomes("process")), len(K.nomes("filament"))
        diz("ok", f"perfis da Anycubic: {len(ms)} impressoras, {sum(len(b) for b in ms.values())} maquinas, {np_} de impressao, {nf} de filamento")
    except SystemExit as e:
        diz("falha", f"{e} (abre o Anycubic Slicer Next uma vez para ele criar os perfis)")
        return
    meus = {t: len(K.meus(t)) for t in ("machine", "process", "filament")}
    if sum(meus.values()):
        diz("ok", f"perfis teus: {meus['machine']} de impressora, {meus['process']} de impressao, {meus['filament']} de filamento")
    else:
        diz("ok", "perfis teus: nenhum (usa os da Anycubic)")

    cfg = K.le_config()
    alvo = impressora or K.IMPRESSORA_OMISSAO
    try:
        K.usa_impressora(K.encontra_maquina(alvo))
        np_, nf = len(K.compativeis("process")), len(K.compativeis("filament"))
        estado = "ok" if np_ and nf else "falha"
        diz(estado, f"impressora{'' if impressora else ' por omissao'}: {K.MODELO} bico {K.BICO}, mesa {K.CAMA_X:g} x {K.CAMA_Y:g} x "
                    f"{K.ALTURA_MAX:g} mm, {'com ACE' if K.MULTICOR else 'sem ACE'}, {np_} perfis de impressao, {nf} filamentos")
    except SystemExit as e:
        diz("falha", f"impressora '{alvo}': {e}")
    diz("ok", "perfis por omissao: " + ("os teus, quando existem" if K.PERFIS_OMISSAO == "meus" else "os da Anycubic"))
    for chave, titulo in (("saida", "pasta dos adaptados"), ("originais", "pasta dos originais")):
        p = K.pasta_config(chave)
        if p:
            diz("ok" if os.path.isdir(p) else "aviso", f"{titulo}: {p}" + ("" if os.path.isdir(p) else " (ainda nao existe: e criada quando for precisa)"))
    if cfg.get("precos") or cfg.get("preco_hora"):
        diz("ok", "precos: " + "; ".join(f"{k}={v:g}" for k, v in sorted((cfg.get("precos") or {}).items()))
            + f" EUR/kg | maquina {float(cfg.get('preco_hora') or 0):g} EUR/h")
    cs = K.copias()
    if cs:
        tam = sum(os.path.getsize(c["copia"]) for c in cs) / 1e6
        diz("ok", f"copias de seguranca: {len(cs)} ({tam:.0f} MB) em {os.path.join(K.PASTA_DADOS, 'copias')}")
    try:
        d = tempfile.mkdtemp(prefix="mw2any_diag_")
        shutil.rmtree(d, ignore_errors=True)
    except OSError as e:
        diz("falha", f"nao consigo criar pastas temporarias: {e}")


def confere(cond, certo, errado=None):
    diz("ok" if cond else "falha", certo if cond else (errado or certo + " - FALHOU"))
    return bool(cond)


def teste(impressora=None, manter=False):
    """Teste de ponta a ponta numa pasta temporaria."""
    import adaptar
    import exemplo
    import pratos
    if not os.path.exists(K.ANY):
        diz("falha", "teste: precisa do Anycubic Slicer Next instalado")
        return
    tmp = tempfile.mkdtemp(prefix="mw2any_teste_")
    try:
        orig = exemplo.cria(os.path.join(tmp, "Exemplo.3mf"))
        # 1. adaptar
        try:
            rel = adaptar.adapta(adaptar.pedido(original=orig, impressora=impressora, perfis="sistema", saida=tmp,
                                                nome="adaptado.3mf", arquivar_original=""))
        except SystemExit as e:
            diz("falha", f"teste: adaptar falhou: {e}")
            return
        ada = rel["adaptado"]["caminho"]
        ace = rel["adaptado"]["ace"]
        confere(rel["original"]["usados"] == [2, 4], "teste: descobriu os 2 filamentos usados de 4", f"teste: filamentos usados {rel['original']['usados']} (esperava [2, 4])")
        if ace:
            confere([f["cor"] for f in rel["filamentos"]] == ["#F2C94C", "#C0392B"], "teste: 2 filamentos com as cores do autor",
                    f"teste: filamentos {[(f['perfil'], f['cor']) for f in rel['filamentos']]}")
            confere(rel["torre"] and str(rel["torre"]["ligada"]) == "1" and len(rel["torre"]["posicoes"]) == 2,
                    "teste: torre de purga ligada, uma posicao por prato")
            confere(rel["purga"] and len(rel["purga"]["matriz"]) == 2 and rel["purga"]["matriz"][0][1] > 0, "teste: matriz de purga 2 x 2")
        else:
            confere(len(rel["filamentos"]) == 1 and any("nao tem ACE" in a for a in rel["avisos"]),
                    "teste: impressora sem ACE -> um filamento e aviso das cores")
        ms = {m["chave"]: m for m in rel["mudancas"]}
        confere(str(K.primeiro(ms.get("sparse_infill_density", {}).get("para"))) == "10%" and "wall_loops" in ms,
                "teste: passaram as definicoes do autor (enchimento 10 %, 3 paredes)", f"teste: mudancas {sorted(ms)}")
        confere(any("outer_wall_speed" in x for x in rel["nao_passou"]["velocidades"]), "teste: a velocidade do autor acima do perfil nao passou")
        with zipfile.ZipFile(ada) as z:
            nomes = re.findall(r'key="plater_name" value="([^"]*)"', z.read("Metadata/model_settings.config").decode("utf-8"))
            j = json.loads(z.read("Metadata/project_settings.config"))
        confere(nomes == ["", ""], "teste: 2 pratos, sem nome", f"teste: nomes dos pratos {nomes}")
        confere(str(K.primeiro(j.get("printer_settings_id"))) == K.MAQUINA, f"teste: projeto para {K.MAQUINA}")
        medidas = [o["tamanho"] for p in rel["pratos"] for o in p["objetos"]]
        confere(medidas == [[60.0, 52.0, 48.0], [66.0, 57.2, 4.0]] and not any("medidas mudaram" in a for a in rel["avisos"]),
                "teste: medidas iguais as do original", f"teste: medidas {medidas}")
        fat = [p for p in rel["pratos"] if p.get("segundos")]
        confere(len(fat) == 2 and all(p["total_g"] > 0 for p in fat),
                "teste: fatiou os 2 pratos (" + "; ".join(f"{p['tempo']}, {p['total_g']} g" for p in fat) + ")", "teste: nao fatiou os 2 pratos")
        if ace:
            confere(fat and fat[0]["trocas"] >= 1 and len(fat[0]["g"]) == 2 and min(fat[0]["g"]) > 0, "teste: o prato 1 usa as 2 cores")
        for a in rel["avisos"]:
            if not ("nao tem ACE" in a or "varias cores" in a):
                diz("aviso", "teste: " + a)

        # 2. cores: a tampa noutro filamento (novo) e a faixa a branco
        if ace:
            try:
                r2 = adaptar.adapta(adaptar.pedido(original=ada, saida=tmp, nome="cores.3mf", atribuir="Tampa=3", cores=";#FFFFFF;#232C7C"))
                cores = [f["cor"] for f in r2["filamentos"]]
                p2 = next((p for p in r2["pratos"] if p["n"] == 2), {})
                confere(cores == ["#F2C94C", "#FFFFFF", "#232C7C"] and len(p2.get("g", [])) == 3 and p2["g"][2] > 0 and p2["g"][0] == 0,
                        "teste: cores por peca (filamento novo para a tampa, purga recalculada)", f"teste: cores {cores}, prato 2 {p2.get('g')}")
                confere(len(r2["purga"]["recalculadas"]) == 6, "teste: purga recalculada para as cores novas")
            except SystemExit as e:
                diz("falha", f"teste: mudar cores falhou: {e}")

        # 3. pratos: juntar tudo num so e afastar
        try:
            junto = os.path.join(tmp, "junto.3mf")
            pr = pratos.Projeto(ada)
            pr.junta()
            pr.junta_demasiado()
            n, _ = pr.grava(junto)
            res = K.fatia(junto, os.path.join(tmp, "f_junto"), tmp)
            confere(n == 1 and list(res) == [1] and res[1]["total_g"] > 0, f"teste: juntar pratos (1 prato, {res[1]['tempo']}, {res[1]['total_g']} g)")
        except SystemExit as e:
            diz("falha", f"teste: juntar pratos falhou: {e}")

        # 4. tamanho: metade
        r = subprocess.run([sys.executable, os.path.join(K.AQUI, "escalar.py"), ada, os.path.join(tmp, "metade.3mf"), "--fator", "0.5", "--fatiar"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        confere(r.returncode == 0 and "-> 30.0 x 26.0 x 24.0 mm" in r.stdout and "FATIADO" in r.stdout, "teste: mudar o tamanho (metade: 30 x 26 x 24 mm)",
                "teste: mudar o tamanho falhou: " + (r.stdout + r.stderr).strip()[-300:])
    finally:
        if manter:
            diz("ok", f"pasta do teste: {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Diagnostico da MakerWorld to Any")
    ap.add_argument("--teste", action="store_true", help="teste de ponta a ponta com um projeto de exemplo")
    ap.add_argument("--impressora", help="impressora do teste (por omissao: a tua)")
    ap.add_argument("--manter", action="store_true", help="nao apaga a pasta do teste")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rapido(a.impressora)
    if a.teste and not any(e == "falha" for e, _ in RES):
        teste(a.impressora, a.manter)
    falhas = sum(1 for e, _ in RES if e == "falha")
    avisos = sum(1 for e, _ in RES if e == "aviso")
    if a.json:
        print(json.dumps({"versao": K.versao(), "ok": not falhas, "falhas": falhas, "avisos": avisos,
                          "verificacoes": [{"estado": e, "texto": t} for e, t in RES]}, indent=1, ensure_ascii=False))
    else:
        print(f"MakerWorld to Any {K.versao()} (Megatic) - diagnostico")
        for e, t in RES:
            print(f"  [{ {'ok': 'ok', 'aviso': 'AVISO', 'falha': 'FALHA'}[e] }] {t}")
        fim = "tudo bem" if not falhas else f"{falhas} problema(s)"
        print(f"RESULTADO: {fim}" + (f", {avisos} aviso(s)" if avisos else "") + ("" if a.teste or falhas else "  (--teste faz um teste completo)"))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
