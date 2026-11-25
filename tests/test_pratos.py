import json
import os
import re
import unittest
import zipfile

import apoio
from apoio import K
import distancias
import pratos


def le(caminho):
    """(caixas por prato, project_settings, model_settings) de um projeto."""
    with zipfile.ZipFile(caminho) as z:
        j = json.loads(z.read("Metadata/project_settings.config"))
        K.impressora_do_projeto(j)
        mod = K.Modelo(z)
        return K.caixas_por_prato(mod), j, mod.ms


class Pratos(unittest.TestCase):
    def setUp(self):
        self.d = apoio.pasta("pratos")
        self.orig = apoio.projeto_anycubic(os.path.join(self.d, "a.3mf"))
        self.dst = os.path.join(self.d, "saida.3mf")

    def test_juntar_tudo_num_prato(self):
        pr = pratos.Projeto(self.orig)
        pr.junta()
        pr.junta_demasiado()
        n, torre = pr.grava(self.dst)
        self.assertEqual(n, 1)
        por_prato, j, ms = le(self.dst)
        self.assertEqual(sorted(por_prato), [1])
        self.assertEqual(sorted(c["nome"] for c in por_prato[1]), ["Caixa", "Tampa"])
        self.assertEqual(K.avisos_mesa(por_prato), [])                              # tudo dentro da mesa
        self.assertEqual(len(re.findall("<plate>", ms)), 1)
        self.assertEqual(len(re.findall("<model_instance>", ms)), 2)
        self.assertEqual((len(j["wipe_tower_x"]), len(j["wipe_tower_y"])), (1, 1))  # uma posicao de torre por prato
        a, b = (K.ret(c) for c in por_prato[1])
        self.assertGreaterEqual(K.sep(a, b), 5)                                     # nao ficaram em cima uma da outra
        self.assertEqual([round(v, 1) for c in por_prato[1] for v in c["tam"]], [60.0, 52.0, 48.0, 66.0, 57.2, 4.0])

    def test_um_por_prato_desfaz_o_juntar(self):
        pr = pratos.Projeto(self.orig)
        pr.junta()
        pr.grava(self.dst)
        pr = pratos.Projeto(self.dst)
        pr.um_por_prato()
        n, _ = pr.grava(self.dst)
        self.assertEqual(n, 2)
        por_prato, j, ms = le(self.dst)
        self.assertEqual({p: [c["nome"] for c in cs] for p, cs in por_prato.items()}, {1: ["Caixa"], 2: ["Tampa"]})
        self.assertEqual(re.findall(r'key="plater_id" value="(\d+)"', ms), ["1", "2"])
        self.assertEqual(len(j["wipe_tower_x"]), 2)
        for cs in por_prato.values():                                               # cada um ao centro da sua mesa
            c = cs[0]
            self.assertAlmostEqual((c["llo"][0] + c["lhi"][0]) / 2, 130, delta=0.3)
            self.assertAlmostEqual((c["llo"][1] + c["lhi"][1]) / 2, 130, delta=0.3)

    def test_mover_por_nome_e_pratos_vazios_desaparecem(self):
        pr = pratos.Projeto(self.orig)
        pr.move(pratos.interpreta("tampa=1"))
        n, _ = pr.grava(self.dst)
        self.assertEqual(n, 1)
        self.assertEqual(pr.feito, ["Tampa -> prato 1"])
        pr = pratos.Projeto(self.dst)
        pr.move([("2", 3)])                                # o objeto 2 para um prato que nao existe: passa a ser o 2
        n, _ = pr.grava(self.dst)
        self.assertEqual(n, 2)
        por_prato, _, _ = le(self.dst)
        self.assertEqual({p: [c["nome"] for c in cs] for p, cs in por_prato.items()}, {1: ["Caixa"], 2: ["Tampa"]})

    def test_escolher_objetos(self):
        pr = pratos.Projeto(self.orig)
        self.assertEqual([c["nome"] for c in pr.escolhe("prato 2")], ["Tampa"])
        self.assertEqual([c["nome"] for c in pr.escolhe("1")], ["Caixa"])
        self.assertEqual(len(pr.escolhe("tudo")), 2)
        for mau in ("9", "parafuso"):
            with self.assertRaises(SystemExit):
                pr.escolhe(mau)
        pr.fecha()

    def test_regras(self):
        self.assertEqual(pratos.interpreta("body=1; barra=2"), [("body", 1), ("barra", 2)])
        for mau in ("body", "body=dois"):
            with self.assertRaises(SystemExit):
                pratos.interpreta(mau)

    def test_so_projetos_anycubic(self):
        bambu = apoio.projeto_bambu(os.path.join(self.d, "b.3mf"))
        with self.assertRaises(SystemExit) as e:
            pratos.Projeto(bambu)
        self.assertIn("adapta-o primeiro", str(e.exception))

    def test_trocas_de_cor_por_camada_seguem_as_pecas(self):
        # estao guardadas por numero de prato, mas sao das pecas: ao trocar os pratos, a troca aos 10 mm vai com a caixa
        apoio.poe_trocas(self.orig, {1: [10]})
        pr = pratos.Projeto(self.orig)
        pr.move(pratos.interpreta("caixa=2;tampa=1"))
        pr.grava(self.dst)
        self.assertEqual(apoio.trocas(self.dst), {2: [10.0]})
        self.assertEqual(pr.avisos, [])

    def test_um_por_prato_leva_as_trocas_para_cada_prato_novo(self):
        juntas = apoio.projeto_anycubic(os.path.join(self.d, "juntas.3mf"), junto=True)       # prato 2: duas tampas
        apoio.poe_trocas(juntas, {2: [2]})
        pr = pratos.Projeto(juntas)
        pr.um_por_prato()
        pr.grava(self.dst)
        self.assertEqual(apoio.trocas(self.dst), {2: [2.0], 3: [2.0]})
        self.assertEqual(pr.avisos, [])

    def test_juntar_pratos_com_trocas_avisa(self):
        # o slicer so sabe fazer trocas por camada no prato inteiro: ao juntar, passam a valer para todas as pecas
        apoio.poe_trocas(self.orig, {1: [10], 2: [2]})
        pr = pratos.Projeto(self.orig)
        pr.junta()
        pr.grava(self.dst)
        self.assertEqual(apoio.trocas(self.dst), {1: [2.0, 10.0]})                           # as duas, por altura
        self.assertEqual(len(pr.avisos), 1)
        self.assertIn("passam a valer para todas as pecas deste prato", pr.avisos[0])
        # so um dos pratos tinha trocas: tambem avisa, porque a outra peca passa a te-las
        outro = apoio.projeto_anycubic(os.path.join(self.d, "outro.3mf"))
        apoio.poe_trocas(outro, {1: [10]})
        pr = pratos.Projeto(outro)
        pr.junta()
        pr.grava(self.dst)
        self.assertEqual(apoio.trocas(self.dst), {1: [10.0]})
        self.assertEqual(len(pr.avisos), 1)

    def test_projeto_sem_trocas_fica_sem_trocas(self):
        pr = pratos.Projeto(self.orig)
        pr.junta()
        pr.grava(self.dst)
        self.assertEqual(apoio.trocas(self.dst), {})
        self.assertEqual(pr.avisos, [])

    @unittest.skipUnless(apoio.TEM_NUMPY, "precisa do numpy")
    def test_afastar_pecas_encostadas(self):
        juntas = apoio.projeto_anycubic(os.path.join(self.d, "juntas.3mf"), junto=True)
        pr = pratos.Projeto(juntas)
        pr.afasta(6.0)
        pr.grava(self.dst)
        self.assertRegex(pr.feito[0], r"prato 2: pecas afastadas \(folga minima 1\.0 -> \d+\.\d mm\)")
        with zipfile.ZipFile(self.dst) as z:
            mod = K.Modelo(z)
            por_prato = K.caixas_por_prato(mod)
            avisos, peg = distancias.avisos_folgas(mod, por_prato)
        self.assertEqual(avisos, [])
        self.assertGreaterEqual(peg[2].folgas(30)[0][2], 6.0 - distancias.CELULA)
        self.assertEqual(K.avisos_mesa(por_prato), [])
        self.assertEqual(sorted(len(cs) for cs in por_prato.values()), [1, 2])     # o prato 1 nao mudou


if __name__ == "__main__":
    unittest.main()
