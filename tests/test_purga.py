import unittest

import apoio  # noqa: F401  (prepara o ambiente)
import purga


class Purga(unittest.TestCase):
    def test_valores_conhecidos(self):
        # Kobra X (nozzle_volume 79): branco -> azul escuro e o contrario (para claro purga muito mais)
        self.assertEqual(purga.volume("#FFFFFF", "#232C7C", 79), 204)
        self.assertEqual(purga.volume("#232C7C", "#FFFFFF", 79), 604)
        # as cores do projeto de exemplo, com o bico de uma Bambu A1 (92)
        self.assertEqual(purga.volume("#F2C94C", "#C0392B", 92), 208)
        self.assertEqual(purga.volume("#C0392B", "#F2C94C", 92), 448)

    def test_extremos(self):
        self.assertEqual(purga.volume("#000000", "#000000", 79), 60 + 79)       # mesma cor: o minimo mais o bico
        self.assertEqual(purga.volume("#000000", "#FFFFFF", 0), 559)
        self.assertEqual(purga.volume("#FFFFFF", "#000000", 0), 79)
        self.assertEqual(purga.volume("#000", "#FFFFFFFF", 500), 800)           # nunca passa do limite do slicer

    def test_formatos_de_cor(self):
        self.assertEqual(purga.normaliza("abc"), "#AABBCC")
        self.assertEqual(purga.normaliza("#aabbccff"), "#AABBCC")
        self.assertEqual(purga.volume("fff", "232c7c", 79), purga.volume("#FFFFFF", "#232C7C", 79))
        self.assertEqual(purga.volume("#00000000", "#232C7C", 79), 204)          # transparente conta como branco
        with self.assertRaises(ValueError):
            purga.volume("vermelho", "#FFFFFF")

    def test_matriz_recalcula_so_o_que_mudou(self):
        cores = ["#FFFFFF", "#232C7C", "#800020"]
        m, rec = purga.matriz(cores, 79)
        self.assertEqual(len(m), 9)
        self.assertEqual([m[0], m[4], m[8]], ["0", "0", "0"])
        self.assertEqual(m[1], "204")
        self.assertEqual(len(rec), 6)
        base = [[0, 111, 0], [222, 0, 0], [0, 0, 0]]
        manter = [[False, True, False], [True, False, False], [False, False, False]]
        m2, rec2 = purga.matriz(cores, 79, base, manter)
        self.assertEqual((m2[1], m2[3]), ("111", "222"))                        # os valores do autor ficam
        self.assertEqual(m2[2], m[2])                                           # o resto e calculado
        self.assertEqual(sorted(rec2), [(1, 3), (2, 3), (3, 1), (3, 2)])


if __name__ == "__main__":
    unittest.main()
