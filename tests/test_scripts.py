"""Os scripts corridos como o utilizador os corre (noutro processo), com os perfis falsos e sem slicer."""
import json
import os
import subprocess
import sys
import unittest
import zipfile

import apoio
from apoio import K


def corre(script, *args, **amb):
    """(codigo, saida) de `python <script> args...`; a saida le-se sempre como UTF-8."""
    r = subprocess.run([sys.executable, os.path.join(apoio.SCRIPTS, script)] + list(args), capture_output=True,
                       env=apoio.ambiente_isolado(**amb), cwd=apoio.TMP)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", errors="replace")


class Medir(unittest.TestCase):
    def test_nomes_fora_do_cp1252_nao_rebentam(self):
        # no Windows, com a saida ligada a um pipe, o Python escreve em cp1252: um nome em chines rebentava o script
        p = apoio.projeto_anycubic(os.path.join(apoio.pasta("utf8"), "a.3mf"), nomes_estranhos=True)
        rc, out = corre("medir.py", p, PYTHONIOENCODING="cp1252")
        self.assertEqual(rc, 0, out)
        self.assertIn("prato 2: Tampa \u84cb: 66.0 x 57.2 x 4.0 mm", out)
        self.assertIn("AVISOS: nenhum", out)

    def test_projeto_bambu_so_mede(self):
        p = apoio.projeto_bambu(os.path.join(apoio.pasta("medir"), "b.3mf"))
        rc, out = corre("medir.py", p)
        self.assertEqual(rc, 0, out)
        self.assertIn("nao e um projeto Anycubic", out)
        self.assertIn("Caixa: 60.0 x 52.0 x 48.0 mm", out)
        rc, out = corre("medir.py", p, "--fatiar")
        self.assertNotEqual(rc, 0)
        self.assertIn("adapta primeiro", out)

    @unittest.skipUnless(apoio.TEM_NUMPY, "precisa do numpy")
    def test_folgas_e_avisos(self):
        p = apoio.projeto_anycubic(os.path.join(apoio.pasta("medir2"), "a.3mf"), junto=True)
        rc, out = corre("medir.py", p)
        self.assertEqual(rc, 0, out)
        self.assertIn("folga entre 'Tampa' e 'Tampa': 1.0 mm", out)
        self.assertIn("podem colar na primeira camada", out)


class Escalar(unittest.TestCase):
    def setUp(self):
        self.d = apoio.pasta("escalar")
        self.p = apoio.projeto_anycubic(os.path.join(self.d, "a.3mf"))

    def tamanhos(self, caminho):
        with zipfile.ZipFile(caminho) as z:
            return {c["nome"]: [round(v, 1) for v in c["tam"]] + [round(c["lo"][2], 3)] for c in K.Modelo(z).caixas()}

    def test_fator_para_outro_ficheiro(self):
        dst = os.path.join(self.d, "metade.3mf")
        rc, out = corre("escalar.py", self.p, dst, "--fator", "0.5")
        self.assertEqual(rc, 0, out)
        self.assertIn("Caixa: 60.0 x 52.0 x 48.0 -> 30.0 x 26.0 x 24.0 mm", out)
        self.assertEqual(self.tamanhos(dst), {"Caixa": [30.0, 26.0, 24.0, 0.0], "Tampa": [33.0, 28.6, 2.0, 0.0]})   # assentes na mesa
        self.assertEqual(self.tamanhos(self.p)["Caixa"][:3], [60.0, 52.0, 48.0])                                    # o original fica

    def test_altura_de_um_objeto_e_no_proprio_ficheiro_fica_copia(self):
        antes = apoio.le_bytes(self.p)
        rc, out = corre("escalar.py", self.p, "--altura", "96", "--objeto", "caixa")
        self.assertEqual(rc, 0, out)
        self.assertIn("COPIA DO FICHEIRO ANTERIOR", out)
        self.assertEqual(self.tamanhos(self.p), {"Caixa": [120.0, 103.9, 96.0, 0.0], "Tampa": [66.0, 57.2, 4.0, 0.0]})
        rc, out = corre("desfazer.py", self.p)                    # e da para voltar atras
        self.assertEqual(rc, 0, out)
        self.assertIn("Reposto", out)
        self.assertEqual(apoio.le_bytes(self.p), antes)

    def test_pedidos_maus(self):
        rc, out = corre("escalar.py", self.p, "--fator", "0.5", "--objeto", "parafuso")
        self.assertNotEqual(rc, 0)
        self.assertIn("Nenhum objeto com esse nome", out)
        rc, out = corre("escalar.py", self.p, "--altura", "100000")
        self.assertNotEqual(rc, 0)
        self.assertIn("fora do razoavel", out)
        bambu = apoio.projeto_bambu(os.path.join(self.d, "b.3mf"))
        rc, out = corre("escalar.py", bambu, "--fator", "0.5")
        self.assertNotEqual(rc, 0)
        self.assertIn("adapta-o primeiro", out)

    def test_alturas_variaveis_e_trocas_por_camada_acompanham_o_tamanho(self):
        p = apoio.projeto_anycubic(os.path.join(self.d, "v.3mf"), camadas_variaveis=True)      # a caixa (objeto 1) a 0.1 mm
        apoio.poe_trocas(p, {1: [10], 2: [2]})
        so_caixa = os.path.join(self.d, "caixa.3mf")
        rc, out = corre("escalar.py", p, so_caixa, "--fator", "0.5", "--objeto", "caixa")
        self.assertEqual(rc, 0, out)
        alturas = apoio.le_zip(so_caixa, "Metadata/layer_heights_profile.txt")
        self.assertTrue(alturas.startswith("object_id=1|0.000000;0.200000;0.100000;0.200000;0.100000;0.100000;24.000000;0.100000"), alturas)
        self.assertEqual(apoio.trocas(so_caixa), {1: [5.0], 2: [2.0]})                         # so o prato da caixa mudou
        tudo = os.path.join(self.d, "tudo.3mf")
        rc, out = corre("escalar.py", p, tudo, "--fator", "2")
        self.assertEqual(rc, 0, out)
        self.assertEqual(apoio.trocas(tudo), {1: [20.0], 2: [4.0]})

    def test_trocas_por_camada_com_so_algumas_pecas_a_mudar_avisa(self):
        p = apoio.projeto_anycubic(os.path.join(self.d, "j.3mf"), junto=True)                 # prato 2: duas tampas
        apoio.poe_trocas(p, {2: [2]})

        def renomeia(nome, dados):
            if nome == "Metadata/model_settings.config":
                t = dados.decode("utf-8")
                i = t.rindex('<metadata key="name" value="Tampa"/>\n    <metadata key="extruder"')
                return (t[:i] + t[i:].replace('value="Tampa"', 'value="Tampa grande"', 1)).encode("utf-8")
            return dados
        K.reescreve(p, p, renomeia)
        dst = os.path.join(self.d, "j2.3mf")
        rc, out = corre("escalar.py", p, dst, "--fator", "1.2", "--objeto", "tampa grande")
        self.assertEqual(rc, 0, out)
        self.assertIn("so algumas pecas mudaram de tamanho", out)
        self.assertEqual(apoio.trocas(dst), {2: [2.0]})

    def test_nao_cabe_na_mesa_da_aviso(self):
        rc, out = corre("escalar.py", self.p, os.path.join(self.d, "grande.3mf"), "--fator", "5")
        self.assertEqual(rc, 0, out)
        self.assertIn("sai da mesa de 260 x 260 mm", out)


class PratosCoresDesfazer(unittest.TestCase):
    def setUp(self):
        self.d = apoio.pasta("cli")
        self.p = apoio.projeto_anycubic(os.path.join(self.d, "a.3mf"))

    def test_pratos_listar_e_juntar(self):
        rc, out = corre("pratos.py", self.p)
        self.assertEqual(rc, 0, out)
        self.assertIn("Anycubic Kobra X: mesa 260 x 260 mm, 2 prato(s)", out)
        self.assertIn("  2  Tampa  66.0 x 57.2 x 4.0 mm", out)
        rc, out = corre("pratos.py", self.p, "--juntar")
        self.assertEqual(rc, 0, out)
        self.assertIn("- tudo no prato 1", out)
        self.assertIn("1 prato(s)", out)
        self.assertIn("COPIA DO FICHEIRO ANTERIOR", out)

    def test_cores_listar(self):
        rc, out = corre("cores.py", self.p)
        self.assertEqual(rc, 0, out)
        self.assertIn("Anycubic Kobra X (com ACE)", out)
        self.assertIn("  2  Anycubic PLA Silk  #C0392B", out)
        self.assertIn("1.2  Faixa  [filamento 2 #C0392B]", out)

    def test_separar_pratos(self):
        dst = os.path.join(self.d, "so2.3mf")
        rc, out = corre("separar_pratos.py", self.p, dst, "2")
        self.assertEqual(rc, 0, out)
        with zipfile.ZipFile(dst) as z:
            mod = K.Modelo(z)
            j = json.loads(z.read("Metadata/project_settings.config"))
            por_prato = K.caixas_por_prato(mod)
        self.assertEqual(mod.n_pratos, 1)
        self.assertEqual({p: [c["nome"] for c in cs] for p, cs in por_prato.items()}, {1: ["Tampa"]})
        self.assertEqual(K.avisos_mesa(por_prato), [])
        self.assertEqual(len(j["wipe_tower_x"]), 1)
        rc, out = corre("separar_pratos.py", self.p, dst, "7")
        self.assertNotEqual(rc, 0)
        self.assertIn("so tem os pratos [1, 2]", out)

    def test_separar_pratos_leva_so_o_que_e_dos_pratos_que_ficam(self):
        # trocas de cor por camada (por prato) e alturas de camada variaveis (por posicao do objeto)
        p = apoio.projeto_anycubic(os.path.join(self.d, "v.3mf"), camadas_variaveis=True)      # objeto 1 = caixa, no prato 1
        apoio.poe_trocas(p, {1: [10]})
        so2 = os.path.join(self.d, "v2.3mf")
        rc, out = corre("separar_pratos.py", p, so2, "2")
        self.assertEqual(rc, 0, out)
        self.assertEqual(apoio.trocas(so2), {})                                                # eram da caixa, que saiu
        self.assertIsNone(apoio.le_zip(so2, "Metadata/layer_heights_profile.txt"))
        so1 = os.path.join(self.d, "v1.3mf")
        rc, out = corre("separar_pratos.py", p, so1, "1")
        self.assertEqual(rc, 0, out)
        self.assertEqual(apoio.trocas(so1), {1: [10.0]})
        self.assertTrue(apoio.le_zip(so1, "Metadata/layer_heights_profile.txt").startswith("object_id=1|"))
        # o contrario: o que e do prato 2 passa a ser do prato 1, e o objeto 2 passa a ser o 1
        q = apoio.projeto_anycubic(os.path.join(self.d, "w.3mf"))
        apoio.poe_trocas(q, {1: [10], 2: [2]})
        with zipfile.ZipFile(q, "a", zipfile.ZIP_DEFLATED) as z:
            z.writestr("Metadata/layer_heights_profile.txt", "object_id=2|0.000000;0.200000;4.000000;0.200000\n")
        w2 = os.path.join(self.d, "w2.3mf")
        rc, out = corre("separar_pratos.py", q, w2, "2")
        self.assertEqual(rc, 0, out)
        self.assertEqual(apoio.trocas(w2), {1: [2.0]})
        self.assertEqual(apoio.le_zip(w2, "Metadata/layer_heights_profile.txt"), "object_id=1|0.000000;0.200000;4.000000;0.200000\n")

    def test_separar_pratos_recusa_copias_do_mesmo_objeto(self):
        # o mesmo objeto em dois pratos (instancias): aqui cada objeto so pode ter um prato, por isso nao se arrisca
        def duplica(nome, dados):
            if nome == "Metadata/model_settings.config":
                return dados.decode("utf-8").replace('key="object_id" value="5"', 'key="object_id" value="3"').encode("utf-8")
            return dados
        K.reescreve(self.p, self.p, duplica)
        rc, out = corre("separar_pratos.py", self.p, os.path.join(self.d, "x.3mf"), "1")
        self.assertNotEqual(rc, 0)
        self.assertIn("copias do mesmo objeto", out)
        self.assertFalse(os.path.exists(os.path.join(self.d, "x.3mf")))

    def test_desfazer_sem_copias(self):
        rc, out = corre("desfazer.py", os.path.join(self.d, "nunca mexido.3mf"))
        self.assertNotEqual(rc, 0)
        self.assertIn("Nao ha copias de", out)


class Preferencias(unittest.TestCase):
    def amb(self):
        return {"MAKERWORLD_TO_ANY_CONFIG": os.path.join(apoio.pasta("prefs"), "config.json")}

    def test_guardar_mostrar_apagar(self):
        amb = self.amb()
        rc, out = corre("perfil.py", **amb)
        self.assertEqual(rc, 0, out)
        self.assertIn("perfis por omissao : os da Anycubic", out)
        self.assertIn("[impressao] O meu 0.20", out)
        self.assertIn("<- para a tua impressora", out)
        rc, out = corre("perfil.py", "meus", "--impressora", "kobra 2 neo", "--preco-kg", "pla=18; petg=20,5 ;*=22", "--preco-hora", "0.4",
                        "--saida", r"D:\Impressoes\Adaptado {impressora}", **amb)
        self.assertEqual(rc, 0, out)
        cfg = apoio.le_json(amb["MAKERWORLD_TO_ANY_CONFIG"])
        self.assertEqual(cfg, {"perfis": "meus", "impressora": "Kobra 2 Neo", "saida": r"D:\Impressoes\Adaptado {impressora}",
                               "precos": {"PLA": 18.0, "PETG": 20.5, "*": 22.0}, "preco_hora": 0.4})
        self.assertIn("impressora         : Kobra 2 Neo", out)
        rc, out = corre("perfil.py", "--apagar", "precos", "--apagar", "saida", **amb)
        self.assertEqual(rc, 0, out)
        cfg = apoio.le_json(amb["MAKERWORLD_TO_ANY_CONFIG"])
        self.assertEqual(sorted(cfg), ["impressora", "perfis", "preco_hora"])

    def test_pedidos_maus(self):
        amb = self.amb()
        for args, texto in ((["talvez"], "Nao percebi"), (["--impressora", "Ender 3"], "desconhecida"),
                            (["--preco-kg", "PLA"], "material=preco"), (["--apagar", "tudo"], "Nao conheco")):
            rc, out = corre("perfil.py", *args, **amb)
            self.assertNotEqual(rc, 0, args)
            self.assertIn(texto, out)
        self.assertFalse(os.path.exists(amb["MAKERWORLD_TO_ANY_CONFIG"]))


class Diagnostico(unittest.TestCase):
    def test_sem_slicer_diz_o_que_falta(self):
        rc, out = corre("diagnostico.py", "--json")
        d = json.loads(out)
        self.assertEqual(rc, 1)
        self.assertFalse(d["ok"])
        falhas = [v["texto"] for v in d["verificacoes"] if v["estado"] == "falha"]
        self.assertEqual(len(falhas), 1)
        self.assertIn("nao encontro o Anycubic Slicer Next", falhas[0])
        textos = " | ".join(v["texto"] for v in d["verificacoes"])
        self.assertIn("perfis da Anycubic: 2 impressoras, 3 maquinas", textos)
        self.assertIn("Anycubic Kobra X bico 0.4, mesa 260 x 260 x 260 mm, com ACE", textos)


if __name__ == "__main__":
    unittest.main()
