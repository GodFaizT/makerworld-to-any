import os
import unittest
import zipfile

import apoio
from apoio import K
import distancias


@unittest.skipUnless(apoio.TEM_NUMPY, "precisa do numpy")
class Folgas(unittest.TestCase):
    def pegadas(self, **kw):
        p = apoio.projeto_anycubic(os.path.join(apoio.pasta("folgas"), "f.3mf"), **kw)
        with zipfile.ZipFile(p) as z:
            mod = K.Modelo(z)
            por_prato = K.caixas_por_prato(mod)
            return distancias.avisos_folgas(mod, por_prato)

    def test_pecas_a_1_mm_dao_aviso(self):
        avisos, peg = self.pegadas(junto=True)
        self.assertEqual(len(avisos), 1)
        self.assertIn("'Tampa' e 'Tampa' estao a 1.0 mm", avisos[0])
        self.assertAlmostEqual(peg[2].folga(0, 1), 1.0, delta=distancias.CELULA)

    def test_sem_pecas_juntas_nao_ha_aviso(self):
        avisos, peg = self.pegadas()
        self.assertEqual(avisos, [])
        self.assertEqual(sorted(peg), [1, 2])

    def test_pegada_e_a_forma_real_e_nao_a_caixa(self):
        _, peg = self.pegadas()
        tampa = peg[2]
        # hexagono de raio 33: area 2829 mm2 (a caixa teria 66 x 57.2 = 3775)
        self.assertAlmostEqual(tampa.area(0), 2829, delta=60)
        cx, cy = tampa.centro(0)
        self.assertAlmostEqual(cx, 130, delta=0.3)
        self.assertAlmostEqual(cy, 130, delta=0.3)
        x0, y0, x1, y1 = tampa.caixa(0)
        self.assertAlmostEqual(x1 - x0, 66, delta=1)
        self.assertTrue(tampa.livre(0, 0, 20, 20))
        self.assertFalse(tampa.livre(120, 120, 140, 140))
        # o canto da caixa esta livre: o hexagono nao chega la (uma caixa diria que esta ocupado)
        self.assertTrue(tampa.livre(97.5, 101.5, 105, 106))

    def test_afastar(self):
        _, peg = self.pegadas(junto=True)
        ok, mov = distancias.afasta(peg[2], 6.0)
        self.assertTrue(ok)
        self.assertGreaterEqual(peg[2].folga(0, 1, limite=20), 6.0 - distancias.CELULA)
        mexidas = [k for k, (dx, dy) in mov.items() if dx or dy]
        self.assertEqual(len(mexidas), 1)                           # so uma das duas se mexe

    def test_sobrepostas(self):
        _, peg = self.pegadas(junto=True)
        peg[2].move(1, 0, -30)                                      # puxa a segunda tampa para cima da primeira
        self.assertTrue(peg[2].sobrepoem(0, 1))
        self.assertEqual(peg[2].folga(0, 1), 0.0)


if __name__ == "__main__":
    unittest.main()
