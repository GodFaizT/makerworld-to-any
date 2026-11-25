import os
import unittest
import zipfile

import apoio
import pecas


def model_settings(**kw):
    p = apoio.projeto_bambu(os.path.join(apoio.pasta("pecas"), "p.3mf"), **kw)
    with zipfile.ZipFile(p) as z:
        return z.read("Metadata/model_settings.config").decode("utf-8")


class Pecas(unittest.TestCase):
    def setUp(self):
        self.ms = model_settings()

    def test_le(self):
        objs = pecas.le(self.ms)
        self.assertEqual([(o["n"], o["nome"], o["extrusor"]) for o in objs], [(1, "Caixa", 2), (2, "Tampa", 2)])
        caixa = objs[0]
        self.assertEqual([(p["n"], p["nome"], p["extrusor"], p["efetivo"]) for p in caixa["pecas"]],
                         [(1, "Corpo", None, 2), (2, "Faixa", 4, 4)])         # a peca sem filamento herda o do objeto

    def test_interpreta(self):
        self.assertEqual(pecas.interpreta('anel=2; 1.3=2;"tudo"=1'), [("anel", 2), ("1.3", 2), ("tudo", 1)])
        for mau in ("anel", "anel=azul", "anel=0"):
            with self.assertRaises(SystemExit):
                pecas.interpreta(mau)

    def test_reescrever_sem_mudar_nao_toca_no_texto(self):
        self.assertEqual(pecas.impoe(self.ms, pecas.plano_de(self.ms)), self.ms)

    def test_atribui_peca_pelo_nome(self):
        ms, feito = pecas.atribui(self.ms, [("faixa", 1)])
        faixa = pecas.le(ms)[0]["pecas"][1]
        self.assertEqual((faixa["extrusor"], faixa["efetivo"]), (1, 1))
        self.assertEqual(feito, ["1.2 Caixa / Faixa -> filamento 1"])
        self.assertEqual(pecas.le(ms)[1]["efetivo"], 2)                        # a tampa nao mudou

    def test_atribui_objeto_inteiro_tira_o_filamento_das_pecas(self):
        ms, _ = pecas.atribui(self.ms, [("1", 3)])
        caixa = pecas.le(ms)[0]
        self.assertEqual(caixa["extrusor"], 3)
        self.assertEqual([(p["extrusor"], p["efetivo"]) for p in caixa["pecas"]], [(None, 3), (None, 3)])

    def test_atribui_por_numero_e_tudo(self):
        ms, _ = pecas.atribui(self.ms, [("tudo", 1), ("1.2", 2)])
        objs = pecas.le(ms)
        self.assertEqual([o["efetivo"] for o in objs], [1, 1])
        self.assertEqual([p["efetivo"] for p in objs[0]["pecas"]], [1, 2])

    def test_alvo_que_nao_existe(self):
        for mau in ("7", "1.9", "parafuso"):
            with self.assertRaises(SystemExit):
                pecas.atribui(self.ms, [(mau, 2)])

    def test_lista_para_o_utilizador(self):
        t = pecas.texto_lista(pecas.le(self.ms), ["#FFFFFF", "#F2C94C", "#0086D6", "#C0392B"])
        self.assertIn("1  Caixa  [filamento 2 #F2C94C, 4 #C0392B]", t)
        self.assertIn("1.2  Faixa  [filamento 4 #C0392B]", t)
        self.assertIn("2  Tampa  [filamento 2 #F2C94C]", t)


if __name__ == "__main__":
    unittest.main()
