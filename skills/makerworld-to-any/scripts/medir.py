"""Mede um projeto 3MF (original Bambu ou adaptado Anycubic): tamanho de cada objeto, folgas e, se pedido, fatia.
MakerWorld to Any - feito pela Megatic (https://megatic.pt).

Uso:
    python medir.py <ficheiro.3mf> [--fatiar] [--imagem prato.png]

Num projeto Anycubic tambem diz em que prato esta cada objeto, a posicao na mesa e avisos (fora da mesa, pecas
encostadas, torre de purga em cima de pecas). --imagem desenha os pratos vistos de cima (precisa do matplotlib).
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
import distancias
import pecas


def desenha(caminho, pegadas, por_prato, cores, res=None):
    """PNG com os pratos vistos de cima: a pegada real de cada peca, na cor do filamento do objeto.
    cores = {id do objeto: "#RRGGBB"}; res = resumo do fatiamento (para a torre de purga, o tempo e as gramas)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        raise SystemExit("--imagem needs matplotlib and numpy (pip install matplotlib numpy)")
    pratos = sorted(por_prato)
    col = min(len(pratos), 3)
    lin = -(-len(pratos) // col)
    fig, eixos = plt.subplots(lin, col, figsize=(5.2 * col, 5.4 * lin), squeeze=False)
    paleta = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#17becf"]
    for n, p in enumerate(pratos):
        ax = eixos[n // col][n % col]
        ax.add_patch(plt.Rectangle((0, 0), K.CAMA_X, K.CAMA_Y, fc="#eef0f3", ec="#888888", lw=1.2, zorder=0))
        peg = pegadas.get(p)
        for k, c in enumerate(peg.itens if peg is not None else []):
            m = peg.m[k]
            x0 = peg.x0 + peg.pos[k][0] * peg.cel
            y0 = peg.y0 + peg.pos[k][1] * peg.cel
            cor = str((cores or {}).get(c["oid"]) or paleta[k % len(paleta)])[:7]
            try:
                rgba = matplotlib.colors.to_rgba(cor, 0.92)
            except ValueError:
                rgba = matplotlib.colors.to_rgba(paleta[k % len(paleta)], 0.92)
            img = np.zeros(m.shape + (4,))
            img[m] = rgba
            ax.imshow(img, origin="lower", extent=(x0, x0 + m.shape[1] * peg.cel, y0, y0 + m.shape[0] * peg.cel),
                      interpolation="nearest", zorder=2)
            if m.shape[0] > 1 and m.shape[1] > 1:          # contorno: uma peca branca tambem se tem de ver
                ax.contour(x0 + (np.arange(m.shape[1]) + 0.5) * peg.cel, y0 + (np.arange(m.shape[0]) + 0.5) * peg.cel,
                           m.astype(float), levels=[0.5], colors=["#2b3138"], linewidths=0.8, zorder=3)
            cx, cy = peg.centro(k)
            ax.annotate(c["nome"][:22], (cx, cy), fontsize=7, ha="center", va="center", color="black", zorder=5,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))
        if res and res.get(p, {}).get("torre"):
            t = res[p]["torre"]
            ax.add_patch(plt.Rectangle((t[0], t[1]), t[2] - t[0], t[3] - t[1], fc="#c9ccd1", ec="#555555", hatch="//", alpha=0.8, zorder=1))
            ax.annotate("prime tower", ((t[0] + t[2]) / 2, (t[1] + t[3]) / 2), fontsize=7, ha="center", va="center", zorder=5)
        titulo = f"plate {p}"
        if res and p in res:
            titulo += f" - {res[p]['tempo']}, {res[p]['total_g']} g"
        ax.set_title(titulo, fontsize=10)
        ax.set_xlim(-8, K.CAMA_X + 8)
        ax.set_ylim(-8, K.CAMA_Y + 8)
        ax.set_aspect("equal")
        ax.grid(alpha=0.2)
    for n in range(len(pratos), lin * col):
        eixos[n // col][n % col].axis("off")
    fig.suptitle(f"{K.MODELO} - bed {K.CAMA_X:g} x {K.CAMA_Y:g} mm", fontsize=11)
    fig.tight_layout()
    fig.savefig(caminho, dpi=90)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="Measure a 3MF project (MakerWorld to Any)")
    ap.add_argument("ficheiro")
    ap.add_argument("--fatiar", action="store_true", help="slice every plate (time and grams)")
    ap.add_argument("--imagem", metavar="PNG", help="draws the plates seen from above")
    a = ap.parse_args()
    z = zipfile.ZipFile(a.ficheiro)
    j = json.loads(z.read("Metadata/project_settings.config")) if "Metadata/project_settings.config" in z.namelist() else {}
    impressora = str(K.primeiro(j.get("printer_settings_id", "")) or "?")
    print("printer:", impressora, "| profile:", K.primeiro(j.get("print_settings_id", "")) or "?")
    for i, (n, c) in enumerate(zip(j.get("filament_settings_id", []), j.get("filament_colour", [])), 1):
        print(f"filament {i}: {str(n).split(' @')[0]} {c}")
    mod = K.Modelo(z)
    anycubic = K.impressora_do_projeto(j)
    por_prato, pegadas, avisos = {}, {}, []
    if anycubic:
        print(f"{K.MODELO} bed: {K.CAMA_X:g} x {K.CAMA_Y:g} x {K.ALTURA_MAX:g} mm")
        por_prato = K.caixas_por_prato(mod)
        for p, cs in sorted(por_prato.items()):
            for c in cs:
                print(f"plate {p}: {c['nome']}: {c['tam'][0]:.1f} x {c['tam'][1]:.1f} x {c['tam'][2]:.1f} mm "
                      f"(x {c['llo'][0]:.1f}..{c['lhi'][0]:.1f}, y {c['llo'][1]:.1f}..{c['lhi'][1]:.1f})")
        avisos = K.avisos_mesa(por_prato, sobreposicao=not distancias.disponivel())
        if distancias.disponivel():
            av, pegadas = distancias.avisos_folgas(mod, por_prato)
            avisos += av
            for p, peg in sorted(pegadas.items()):
                for x, y, g in peg.folgas(limite=10.0):
                    print(f"plate {p}: gap between '{peg.itens[x]['nome']}' and '{peg.itens[y]['nome']}': {g:.1f} mm")
    else:
        print("(not an Anycubic project: sizes only)")
        for c in mod.caixas():
            print(f"{c['nome']}: {c['tam'][0]:.1f} x {c['tam'][1]:.1f} x {c['tam'][2]:.1f} mm")
    z.close()
    res = None
    if a.fatiar:
        if not anycubic:
            raise SystemExit("--fatiar is only for Anycubic printer projects (adapt it first)")
        tmp = tempfile.mkdtemp(prefix="mw2any_med_")
        try:
            res = K.fatia(os.path.abspath(a.ficheiro), os.path.join(tmp, "fatiado"), tmp, avisos)
            print("SLICED:\n  " + K.texto_resumo(res, j.get("filament_colour")).replace("\n", "\n  "))
            avisos += K.colisoes_torre(res, por_prato, pegadas=pegadas)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if a.imagem:
        if not anycubic or not pegadas:
            raise SystemExit("--imagem is only for Anycubic printer projects, with numpy installed")
        fc = j.get("filament_colour") or []
        cores = {o["id"]: fc[o["efetivo"] - 1] for o in pecas.le(mod.ms) if 0 < o["efetivo"] <= len(fc)}
        desenha(a.imagem, pegadas, por_prato, cores, res)
        print("image:", os.path.abspath(a.imagem))
    print("WARNINGS:" if avisos else "WARNINGS: none")
    for av in avisos:
        print("  -", av)


if __name__ == "__main__":
    main()
