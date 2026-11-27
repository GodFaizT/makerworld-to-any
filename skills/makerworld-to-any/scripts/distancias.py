"""Folga real entre as pecas de um prato, vista de cima.

As caixas (bounding boxes) enganam: uma barra na diagonal "ocupa" o prato todo e duas pecas encaixadas parecem
sobrepostas. Aqui desenha-se a pegada de cada peca numa grelha fina (a projecao dos triangulos da malha no plano da
mesa) e mede-se a distancia entre pegadas. Serve para avisar de pecas quase coladas, para as afastar e para por a
torre de purga num sitio mesmo livre. Precisa do numpy; sem ele `disponivel()` da False e usam-se as caixas.
"""
import math

try:
    import numpy as np
except ImportError:
    np = None

import anycubic as K

CELULA = 0.25               # mm; as folgas saem com erro de cerca de +-0.25 mm
MARGEM = 10.0               # a grelha passa da mesa, para pecas que saem fora
MAX_AMOSTRAS = 30_000_000   # acima disto a grelha fica mais grossa (pecas enormes e muito detalhadas)


def disponivel():
    return np is not None


def _subdivisoes(P, F, cel):
    A, B, C = P[F[:, 0]], P[F[:, 1]], P[F[:, 2]]
    e = np.maximum(np.maximum(np.hypot(B[:, 0] - A[:, 0], B[:, 1] - A[:, 1]), np.hypot(C[:, 0] - B[:, 0], C[:, 1] - B[:, 1])),
                   np.hypot(A[:, 0] - C[:, 0], A[:, 1] - C[:, 1]))
    return A, B, C, np.maximum(1, np.ceil(e / (cel * 0.7)).astype(np.int64))


def _custo(P, F, cel):
    if len(F) == 0:
        return 0
    n = _subdivisoes(P, F, cel)[3]
    return int(((n + 1) * (n + 2) // 2).sum())


def _raster(P, F, cel, x0, y0, nx, ny):
    """Mascara (ny, nx) das celulas tocadas pela projecao dos triangulos. P em mm, origem da grelha em (x0, y0)."""
    m = np.zeros((ny, nx), bool)
    if len(F) == 0:
        return m
    A, B, C, n = _subdivisoes(P, F, cel)
    for nv in np.unique(n):
        g = np.nonzero(n == nv)[0]
        i, j = np.meshgrid(np.arange(nv + 1), np.arange(nv + 1), indexing="ij")
        ok = (i + j) <= nv
        u, v = i[ok] / nv, j[ok] / nv                      # pontos baricentricos que cobrem o triangulo
        lote = max(1, 2_000_000 // len(u))
        for s in range(0, len(g), lote):
            gi = g[s:s + lote]
            a, ab, ac = A[gi], B[gi] - A[gi], C[gi] - A[gi]
            px = a[:, 0:1] + ab[:, 0:1] * u[None, :] + ac[:, 0:1] * v[None, :]
            py = a[:, 1:2] + ab[:, 1:2] * u[None, :] + ac[:, 1:2] * v[None, :]
            ix = np.floor((px - x0) / cel).astype(np.int64).ravel()
            iy = np.floor((py - y0) / cel).astype(np.int64).ravel()
            dentro = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
            m[iy[dentro], ix[dentro]] = True
    return m


def _borda(m):
    """Celulas cheias com pelo menos um vizinho vazio (ou na orla da janela)."""
    dentro = np.zeros_like(m)
    dentro[1:-1, 1:-1] = m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:]
    return m & ~dentro


class Pegadas:
    """Pegadas das pecas imprimiveis de um prato. Cada peca tem a sua janela (mascara) e uma posicao em celulas,
    por isso mover uma peca e so mudar a posicao."""

    def __init__(self, modelo, caixas, cel=CELULA):
        """caixas: as de um prato, como vem de K.caixas_por_prato (com 'i', 'prato', 'llo', 'lhi')."""
        self.itens = [c for c in caixas if c.get("printable") != "0"]
        self.cel = cel
        malhas = []
        for c in self.itens:
            ox, oy = K.origem_prato(c["prato"], modelo.n_pratos)
            W, F = modelo.malha_item(c["i"])
            malhas.append((W[:, :2] - np.array([ox, oy]) if len(W) else np.zeros((0, 2)), F))
        while self.cel < 2.0 and any(_custo(P, F, self.cel) > MAX_AMOSTRAS for P, F in malhas):
            self.cel *= 2
        cel = self.cel
        self.x0 = self.y0 = -MARGEM
        self.pos, self.m, self.borda = [], [], []
        for c, (P, F) in zip(self.itens, malhas):
            if len(P) == 0:
                self.pos.append([0, 0])
                self.m.append(np.zeros((1, 1), bool))
                self.borda.append(np.zeros((0, 2), np.int64))
                continue
            lo, hi = P.min(0), P.max(0)
            ix0 = int(math.floor((lo[0] - self.x0) / cel)) - 1
            iy0 = int(math.floor((lo[1] - self.y0) / cel)) - 1
            nx = int(math.ceil((hi[0] - lo[0]) / cel)) + 3
            ny = int(math.ceil((hi[1] - lo[1]) / cel)) + 3
            m = _raster(P, F, cel, self.x0 + ix0 * cel, self.y0 + iy0 * cel, nx, ny)
            self.pos.append([ix0, iy0])
            self.m.append(m)
            self.borda.append(np.argwhere(_borda(m))[:, ::-1])       # (x, y) em celulas, na janela

    def __len__(self):
        return len(self.itens)

    # ---- medidas de uma peca
    def area(self, k):
        return float(self.m[k].sum()) * self.cel ** 2

    def centro(self, k):
        ys, xs = np.nonzero(self.m[k])
        if len(xs) == 0:
            return 0.0, 0.0
        return (self.x0 + (self.pos[k][0] + xs.mean() + 0.5) * self.cel, self.y0 + (self.pos[k][1] + ys.mean() + 0.5) * self.cel)

    def caixa(self, k):
        """(x0, y0, x1, y1) em mm, na mesa."""
        ys, xs = np.nonzero(self.m[k])
        if len(xs) == 0:
            return 0.0, 0.0, 0.0, 0.0
        return (self.x0 + (self.pos[k][0] + xs.min()) * self.cel, self.y0 + (self.pos[k][1] + ys.min()) * self.cel,
                self.x0 + (self.pos[k][0] + xs.max() + 1) * self.cel, self.y0 + (self.pos[k][1] + ys.max() + 1) * self.cel)

    def move(self, k, dx, dy):
        """Desloca a peca k (mm); devolve o deslocamento real, arredondado a celula."""
        cx, cy = int(round(dx / self.cel)), int(round(dy / self.cel))
        self.pos[k][0] += cx
        self.pos[k][1] += cy
        return cx * self.cel, cy * self.cel

    # ---- relacoes entre pecas
    def _intersecao(self, a, b):
        ax, ay = self.pos[a]
        bx, by = self.pos[b]
        x0, y0 = max(ax, bx), max(ay, by)
        x1 = min(ax + self.m[a].shape[1], bx + self.m[b].shape[1])
        y1 = min(ay + self.m[a].shape[0], by + self.m[b].shape[0])
        if x1 <= x0 or y1 <= y0:
            return None
        return self.m[a][y0 - ay:y1 - ay, x0 - ax:x1 - ax], self.m[b][y0 - by:y1 - by, x0 - bx:x1 - bx]

    def sobrepoem(self, a, b):
        par = self._intersecao(a, b)
        return bool(par is not None and (par[0] & par[1]).any())

    def folga(self, a, b, limite=6.0):
        """Distancia (mm) entre as pegadas a e b; 0 se se tocam ou sobrepoem; `limite` se estao mais longe que isso."""
        cel = self.cel
        lim = int(math.ceil(limite / cel)) + 2
        ax, ay = self.pos[a]
        bx, by = self.pos[b]
        ah, aw = self.m[a].shape
        bh, bw = self.m[b].shape
        if ax - lim > bx + bw or bx - lim > ax + aw or ay - lim > by + bh or by - lim > ay + ah:
            return limite
        if self.sobrepoem(a, b):
            return 0.0
        pa = self.borda[a] + np.array([ax, ay])
        pb = self.borda[b] + np.array([bx, by])
        pa = pa[(pa[:, 0] >= bx - lim) & (pa[:, 0] <= bx + bw + lim) & (pa[:, 1] >= by - lim) & (pa[:, 1] <= by + bh + lim)]
        pb = pb[(pb[:, 0] >= ax - lim) & (pb[:, 0] <= ax + aw + lim) & (pb[:, 1] >= ay - lim) & (pb[:, 1] <= ay + ah + lim)]
        if len(pa) == 0 or len(pb) == 0:
            return limite
        if len(pa) > len(pb):
            pa, pb = pb, pa
        melhor = None
        lote = max(1, 4_000_000 // len(pb))
        for s in range(0, len(pa), lote):
            d = pa[s:s + lote, None, :] - pb[None, :, :]
            d2 = int((d[..., 0] ** 2 + d[..., 1] ** 2).min())
            melhor = d2 if melhor is None else min(melhor, d2)
        # as mascaras engordam as pecas cerca de meia celula de cada lado, o que compensa a distancia entre centros
        return min(limite, math.sqrt(melhor) * cel)

    def folgas(self, limite=6.0):
        """[(a, b, folga)] dos pares de pecas mais perto que `limite` mm."""
        out = []
        for a in range(len(self)):
            for b in range(a + 1, len(self)):
                g = self.folga(a, b, limite)
                if g < limite:
                    out.append((a, b, g))
        return out

    def livre(self, x0, y0, x1, y1):
        """True se nenhuma peca toca no retangulo (mm, na mesa)."""
        cel = self.cel
        rx0, ry0 = int(math.floor((x0 - self.x0) / cel)), int(math.floor((y0 - self.y0) / cel))
        rx1, ry1 = int(math.ceil((x1 - self.x0) / cel)), int(math.ceil((y1 - self.y0) / cel))
        for k in range(len(self)):
            px, py = self.pos[k]
            h, w = self.m[k].shape
            a0, b0 = max(rx0, px), max(ry0, py)
            a1, b1 = min(rx1, px + w), min(ry1, py + h)
            if a1 > a0 and b1 > b0 and self.m[k][b0 - py:b1 - py, a0 - px:a1 - px].any():
                return False
        return True


def avisos_folgas(modelo, por_prato, minimo=2.0):
    """(avisos, {prato: Pegadas}) - pecas que se tocam ou que estao a menos de `minimo` mm (podem colar)."""
    av, pegadas = [], {}
    if np is None:
        return av, pegadas
    for p, cs in sorted(por_prato.items()):
        peg = Pegadas(modelo, cs)
        pegadas[p] = peg
        for a, b, g in peg.folgas(limite=minimo + 1.0):
            na, nb = peg.itens[a]["nome"], peg.itens[b]["nome"]
            if g <= 0:
                av.append(f"plate {p}: '{na}' and '{nb}' touch or overlap (seen from above)")
            elif g < minimo:
                av.append(f"plate {p}: '{na}' and '{nb}' are {g:.1f} mm apart - they may stick together on the first layer "
                          f"(pratos.py --afastar)")
    return av, pegadas


def afasta(peg, alvo=6.0, iteracoes=80, fixos=()):
    """Afasta as pecas ate todas terem pelo menos `alvo` mm de folga. Em cada par a mais pequena foge da maior, na
    direcao que une os centros. Devolve (ok, {k: (dx, dy)}) com o deslocamento total de cada peca (mm)."""
    n = len(peg)
    total = {k: [0.0, 0.0] for k in range(n)}
    areas = [peg.area(k) for k in range(n)]
    for _ in range(iteracoes):
        perto = [(a, b, g) for a, b, g in peg.folgas(limite=alvo + peg.cel) if g < alvo]
        if not perto:
            return True, {k: tuple(v) for k, v in total.items()}
        empurra = {}
        for a, b, g in perto:
            fica, foge = (a, b) if (areas[a] >= areas[b] and b not in fixos) or a in fixos else (b, a)
            if foge in fixos:
                continue
            cf, cm = peg.centro(fica), peg.centro(foge)
            dx, dy = cm[0] - cf[0], cm[1] - cf[1]
            d = math.hypot(dx, dy)
            if d < 1e-6:
                dx, dy, d = 1.0, 0.0, 1.0
            passo = (alvo - g) + peg.cel * 2 if g > 0 else max(2.0, alvo / 2)
            e = empurra.setdefault(foge, [0.0, 0.0])
            e[0] += dx / d * passo
            e[1] += dy / d * passo
        if not empurra:
            break
        for k, (dx, dy) in empurra.items():
            rx, ry = peg.move(k, dx, dy)
            if rx == 0 and ry == 0:               # empurrao menor que uma celula: da um passo minimo
                rx, ry = peg.move(k, math.copysign(peg.cel, dx or 1), math.copysign(peg.cel, dy) if dy else 0)
            total[k][0] += rx
            total[k][1] += ry
    ok = not [1 for a, b, g in peg.folgas(limite=alvo + peg.cel) if g < alvo - peg.cel]
    return ok, {k: tuple(v) for k, v in total.items()}
