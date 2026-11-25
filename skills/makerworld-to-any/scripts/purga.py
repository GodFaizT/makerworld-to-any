"""Volume de purga numa troca de cor (mm3), como o slicer o calcula quando se escolhe uma cor.

E a formula do Bambu Studio (o Anycubic Slicer Next e um derivado): diferenca de cor em HSV e de luminancia, mais
uma parte fixa que depende do bico (nozzle_volume do perfil da impressora). Conferida com um projeto real: com
nozzle_volume 92 reproduz ao mm3 os valores que o Bambu Studio tinha guardado.

A linha de comandos do Anycubic nao recalcula a matriz de purga: herda a do projeto original, que esta certa para
as cores do autor. Quando as cores mudam (ou se junta um filamento) recalcula-se aqui.
"""
import colorsys
import math

MAXIMO = 800      # limite do slicer
MINIMO_COR = 60.0


def _rgba(cor):
    c = str(cor or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(x * 2 for x in c)
    if len(c) not in (6, 8):
        raise ValueError(f"cor invalida: {cor!r} (usa #RRGGBB)")
    r, g, b = (int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    a = int(c[6:8], 16) if len(c) == 8 else 255
    if a == 0:                      # transparente conta como branco
        r = g = b = 1.0
    return r, g, b


def normaliza(cor):
    """'#abc', 'ABCDEF', '#AABBCCFF' -> '#AABBCC' (para comparar cores)."""
    c = str(cor or "").strip().lstrip("#").upper()
    if len(c) == 3:
        c = "".join(x * 2 for x in c)
    return "#" + c[:6]


def volume(de, para, extra=0.0, maximo=MAXIMO):
    """mm3 a purgar ao passar da cor `de` para a cor `para`. extra = nozzle_volume da impressora."""
    r1, g1, b1 = _rgba(de)
    r2, g2, b2 = _rgba(para)
    h1, s1, v1 = colorsys.rgb_to_hsv(r1, g1, b1)
    h2, s2, v2 = colorsys.rgb_to_hsv(r2, g2, b2)
    a1, a2 = math.radians(h1 * 360.0), math.radians(h2 * 360.0)
    dx = math.cos(a1) * s1 * v1 - math.cos(a2) * s2 * v2
    dy = math.sin(a1) * s1 * v1 - math.sin(a2) * s2 * v2
    hs = min(1.2, math.hypot(dx, dy))
    l1 = r1 * 0.3 + g1 * 0.59 + b1 * 0.11
    l2 = r2 * 0.3 + g2 * 0.59 + b2 * 0.11
    if l2 >= l1:                    # para uma cor mais clara: e o caso que mais purga pede
        lumi = (l2 - l1) ** 0.7 * 560.0
    else:
        lumi = (l1 - l2) * 80.0
        hs = min(0.67 * v2 + 0.33 * v1, hs)
    hsf = 230.0 * hs
    vol = math.sqrt(hsf * hsf + lumi * lumi - 2.0 * hsf * lumi * math.cos(math.radians(120.0)))
    return min(int(max(vol, MINIMO_COR) + extra), maximo)


def matriz(cores, extra=0.0, base=None, manter=None):
    """Matriz k x k (lista de strings, linha = cor de saida, coluna = cor de entrada), como no project_settings.
    base[a][b] e manter[a][b]=True deixam um valor que ja existia (o do autor, quando as duas cores nao mudaram)."""
    k = len(cores)
    out, recalculadas = [], []
    for a in range(k):
        for b in range(k):
            if a == b:
                out.append("0")
            elif base is not None and manter is not None and manter[a][b]:
                out.append(str(base[a][b]))
            else:
                out.append(str(volume(cores[a], cores[b], extra)))
                recalculadas.append((a + 1, b + 1))
    return out, recalculadas
