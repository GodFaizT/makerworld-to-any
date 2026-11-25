"""Testes de ponta a ponta: so correm onde o Anycubic Slicer Next esta instalado (demoram 1-2 minutos).

Os scripts correm noutro processo com os perfis e o slicer verdadeiros, numa pasta temporaria e com as preferencias
e as copias de seguranca isoladas - nao tocam em nada de quem os corre.
"""
import json
import os
import subprocess
import sys
import unittest
import zipfile

import apoio


def corre(script, *args, **amb):
    r = subprocess.run([sys.executable, os.path.join(apoio.SCRIPTS, script)] + list(args), capture_output=True,
                       env=apoio.ambiente_real(**amb), cwd=apoio.TMP)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", errors="replace")


@unittest.skipUnless(apoio.TEM_SLICER, "precisa do Anycubic Slicer Next instalado")
class PontaAPonta(unittest.TestCase):
    def test_o_teste_do_diagnostico_passa(self):
        rc, out = corre("diagnostico.py", "--teste", "--impressora", "Kobra X", "--json")
        d = json.loads(out)
        falhas = [v["texto"] for v in d["verificacoes"] if v["estado"] == "falha"]
        self.assertEqual((rc, falhas), (0, []))
        self.assertGreaterEqual(len([v for v in d["verificacoes"] if v["texto"].startswith("teste:")]), 12)

    def test_impressora_sem_ace_fica_com_um_filamento(self):
        d = apoio.pasta("e2e_neo")
        orig = apoio.projeto_bambu(os.path.join(d, "Exemplo.3mf"))
        rc, out = corre("adaptar.py", orig, "--impressora", "Kobra 2 Neo", "--json")
        self.assertEqual(rc, 0, out)
        rel = json.loads(out)
        self.assertEqual((rel["adaptado"]["ace"], len(rel["filamentos"]), rel["original"]["usados"]), (False, 1, [2, 4]))
        self.assertTrue(any("nao tem ACE" in a for a in rel["avisos"]))
        self.assertTrue(os.path.isfile(os.path.join(d, "Exemplo - Kobra 2 Neo.3mf")))
        self.assertEqual([p["trocas"] for p in rel["pratos"]], [0, 0])

    def test_camadas_variaveis_com_suportes_organicos_e_gcode(self):
        d = apoio.pasta("e2e_var")
        orig = apoio.projeto_bambu(os.path.join(d, "Variavel.3mf"), camadas_variaveis=True, nomes_estranhos=True)
        gcode = os.path.join(d, "gcode")
        os.makedirs(gcode)
        apoio.escreve(os.path.join(gcode, "Variavel - Kobra X - prato 9.gcode"), "; de uma vez anterior, com mais pratos\n")
        apoio.escreve(os.path.join(gcode, "Outro projeto.gcode"), "; nao e deste projeto\n")
        rc, out = corre("adaptar.py", orig, "--impressora", "Kobra X", "--gcode", gcode, "--json")
        self.assertEqual(rc, 0, out)
        rel = json.loads(out)
        estilo = next(m for m in rel["mudancas"] if m["chave"] == "support_style")
        self.assertEqual((estilo["para"], estilo["origem"]), ("tree_hybrid", "skill"))       # senao o slicer recusa-se a fatiar
        self.assertTrue(any("arvore hibrida" in n for n in rel["notas"]))
        self.assertTrue(any("imprime em media a 0.10 mm" in n for n in rel["notas"]))        # a caixa tem camadas de 0.1
        self.assertEqual(rel["pratos"][0]["camadas"], 479)
        # o g-code antigo deste projeto sai (um "prato 9" esquecido imprimia-se por engano); o de outros projetos fica
        self.assertEqual(sorted(os.listdir(gcode)), ["Outro projeto.gcode", "Variavel - Kobra X - prato 1.gcode",
                                                     "Variavel - Kobra X - prato 2.gcode"])
        # sem as camadas variaveis volta a altura do perfil (0.2) e aos suportes do autor
        rc, out = corre("adaptar.py", orig, "--impressora", "Kobra X", "--sem-camadas-variaveis", "--substituir", "--json")
        self.assertEqual(rc, 0, out)
        rel = json.loads(out)
        self.assertEqual(rel["pratos"][0]["camadas"], 240)
        self.assertFalse([m for m in rel["mudancas"] if m["chave"] == "support_style"])
        self.assertTrue(rel["copia"] and os.path.isfile(rel["copia"]))                       # o adaptado anterior ficou guardado

    def test_pratos_e_medir_com_imagem(self):
        d = apoio.pasta("e2e_pratos")
        orig = apoio.projeto_bambu(os.path.join(d, "Juntas.3mf"), junto=True)
        rc, out = corre("adaptar.py", orig, "--impressora", "Kobra X", "--sem-fatiar")
        self.assertEqual(rc, 0, out)
        if apoio.TEM_NUMPY:
            self.assertIn("estao a 1.0 mm uma da outra", out)                               # as duas tampas do exemplo
        ada = os.path.join(d, "Juntas - Kobra X.3mf")
        rc, out = corre("pratos.py", ada, "--um-por-prato", "--fatiar")
        self.assertEqual(rc, 0, out)
        self.assertIn("3 prato(s)", out)
        self.assertIn("AVISOS: nenhum", out)
        with zipfile.ZipFile(ada) as z:
            j = json.loads(z.read("Metadata/project_settings.config"))
        self.assertEqual(len(j["wipe_tower_x"]), 3)
        png = os.path.join(d, "pratos.png")
        rc, out = corre("medir.py", ada, "--fatiar", "--imagem", png)
        if "precisa do matplotlib" in out:
            self.skipTest("sem matplotlib")
        self.assertEqual(rc, 0, out)
        self.assertGreater(os.path.getsize(png), 5000)

    def test_afinacoes_feitas_a_mao_sobrevivem_a_mudar_cores(self):
        # o utilizador abriu o adaptado no slicer, afinou definicoes e gravou; depois pede outra cor a skill
        d = apoio.pasta("e2e_afinado")
        orig = apoio.projeto_bambu(os.path.join(d, "Exemplo.3mf"))
        rc, out = corre("adaptar.py", orig, "--impressora", "Kobra X", "--sem-fatiar")
        self.assertEqual(rc, 0, out)
        ada = os.path.join(d, "Exemplo - Kobra X.3mf")

        def afina(nome, dados):
            if nome != "Metadata/project_settings.config":
                return dados
            j = json.loads(dados)
            lista = lambda v, modelo: [v] if isinstance(modelo, list) else v           # noqa: E731
            j["default_acceleration"] = lista("4321", j["default_acceleration"])       # (seria "da impressora do autor")
            j["outer_wall_speed"] = lista("260", j["outer_wall_speed"])                # (acima do perfil)
            j["nozzle_temperature"] = ["217", j["nozzle_temperature"][1]]              # so o filamento 1
            j["retraction_length"] = lista("1.23", j["retraction_length"])             # definicao da impressora
            dts = j["different_settings_to_system"]
            dts[0] = ";".join(sorted(set(dts[0].split(";")) | {"default_acceleration", "outer_wall_speed"}))
            dts[1] = "nozzle_temperature"
            dts[-1] = ";".join(sorted(set(dts[-1].split(";")) | {"retraction_length"}))
            return json.dumps(j, indent=4).encode("utf-8")
        apoio.K.reescreve(ada, ada, afina)
        rc, out = corre("cores.py", ada, "--cores", ";#232C7C", "--json")
        self.assertEqual(rc, 0, out)
        rel = json.loads(out)
        self.assertEqual({m["origem"] for m in rel["mudancas"]}, {"projeto"})
        self.assertEqual(rel["nao_passou"], {"impressora": [], "sem_equivalente": [], "velocidades": [], "seguranca": []})
        self.assertEqual(rel["do_projeto"], {"impressora": ["retraction_length"], "filamentos": {"1": ["nozzle_temperature"]}})
        self.assertEqual(rel["purga"]["recalculadas"], [[1, 2], [2, 1]])
        with zipfile.ZipFile(ada) as z:
            j = json.loads(z.read("Metadata/project_settings.config"))
        primeiro = lambda v: v[0] if isinstance(v, list) else v                         # noqa: E731
        self.assertEqual((primeiro(j["default_acceleration"]), primeiro(j["outer_wall_speed"]), j["nozzle_temperature"][0],
                          primeiro(j["retraction_length"]), j["filament_colour"]),
                         ("4321", "260", "217", "1.23", ["#F2C94C", "#232C7C"]))
        dts = j["different_settings_to_system"]
        self.assertIn("default_acceleration", dts[0])
        self.assertEqual(dts[1], "nozzle_temperature")
        self.assertIn("retraction_length", dts[-1])
        self.assertIn("levanta o bico", j["machine_end_gcode"])

    def test_cores_pedem_se_pelo_numero_do_filamento(self):
        d = apoio.pasta("e2e_cores")
        orig = apoio.projeto_bambu(os.path.join(d, "Exemplo.3mf"))
        rc, out = corre("adaptar.py", orig, "--impressora", "Kobra X", "--sem-fatiar")
        self.assertEqual(rc, 0, out)
        ada = os.path.join(d, "Exemplo - Kobra X.3mf")
        # a faixa era a unica peca do filamento 2: ao passa-la para um filamento novo (o 3), o 2 deixa de existir
        rc, out = corre("cores.py", ada, os.path.join(d, "a.3mf"), "--atribuir", "faixa=3", "--cores", ";;#232C7C", "--sem-fatiar", "--json")
        self.assertEqual(rc, 0, out)
        rel = json.loads(out)
        self.assertEqual([f["cor"] for f in rel["filamentos"]], ["#F2C94C", "#232C7C"])
        self.assertTrue(any("3 passou a 2" in n for n in rel["notas"]), rel["notas"])
        self.assertFalse([a for a in rel["avisos"] if "--cores" in a])
        import pecas
        caixa = pecas.le(apoio.le_zip(os.path.join(d, "a.3mf"), "Metadata/model_settings.config"))[0]
        self.assertEqual([(p["nome"], p["efetivo"]) for p in caixa["pecas"]], [("Corpo", 1), ("Faixa", 2)])
        # uma cor dada para um filamento que fica sem pecas nao se aplica a outro, e isso e dito
        rc, out = corre("cores.py", ada, os.path.join(d, "b.3mf"), "--atribuir", "faixa=3", "--cores", "#FFFFFF;#00FF00;#232C7C",
                        "--sem-fatiar", "--json")
        self.assertEqual(rc, 0, out)
        rel = json.loads(out)
        self.assertEqual([f["cor"] for f in rel["filamentos"]], ["#FFFFFF", "#232C7C"])
        self.assertTrue(any("--cores" in a and "2 (#00FF00)" in a for a in rel["avisos"]), rel["avisos"])
        # filamento novo sem cor: o erro diz a posicao certa
        rc, out = corre("cores.py", ada, os.path.join(d, "c.3mf"), "--atribuir", "faixa=3", "--cores", ";#232C7C", "--sem-fatiar")
        self.assertNotEqual(rc, 0)
        self.assertIn("O filamento 3 e novo: da-lhe uma cor na posicao 3 de --cores", out)
        # num original a posicao e a ordem dos filamentos usados (os filamentos 2 e 4 ficam nas posicoes 1 e 2), como sempre
        rc, out = corre("adaptar.py", orig, "--impressora", "Kobra X", "--cores", "#FFFFFF;#800020", "--nome", "d.3mf", "--sem-fatiar", "--json")
        self.assertEqual(rc, 0, out)
        self.assertEqual([f["cor"] for f in json.loads(out)["filamentos"]], ["#FFFFFF", "#800020"])

    def test_impressora_guardada_com_bico(self):
        # "Kobra X 0.6" como impressora por omissao: o bico 0.4 do original nao pode ganhar ao que o utilizador guardou
        d = apoio.pasta("e2e_bico")
        orig = apoio.projeto_bambu(os.path.join(d, "Exemplo.3mf"))
        rc, out = corre("adaptar.py", orig, "--sem-fatiar", "--json", MAKERWORLD_TO_ANY_IMPRESSORA="Kobra X 0.6")
        self.assertEqual(rc, 0, out)
        rel = json.loads(out)
        self.assertEqual((rel["adaptado"]["bico"], rel["adaptado"]["maquina"]), ("0.6", "Anycubic Kobra X 0.6 nozzle"))
        self.assertTrue(any("bico 0.4" in a and "bico 0.6" in a for a in rel["avisos"]), rel["avisos"])

    def test_scripts_de_pos_processamento_nao_passam_nem_correm(self):
        d = apoio.pasta("e2e_pp")
        marcador = os.path.join(d, "marcador.txt")
        # inofensivo: se algum slicer o corresse, so criava este ficheiro (e o teste falhava)
        comando = r'C:\Windows\System32\cmd.exe /c echo executado > "%s"' % marcador
        orig = apoio.projeto_bambu(os.path.join(d, "Exemplo.3mf"))

        def poe(j):
            j["post_process"] = [comando]
            dts = j["different_settings_to_system"]
            dts[0] = ";".join(sorted({x for x in dts[0].split(";") if x} | {"post_process"}))
        apoio.muda_definicoes(orig, poe)
        rc, out = corre("adaptar.py", orig, "--impressora", "Kobra X", "--json")
        self.assertEqual(rc, 0, out)              # (com o script la dentro, a linha de comandos do Anycubic recusava o projeto)
        rel = json.loads(out)
        self.assertEqual(rel["nao_passou"]["seguranca"], ["post_process"])
        ada = rel["adaptado"]["caminho"]
        self.assertFalse(apoio.K.tem_pos_processamento(json.loads(apoio.le_zip(ada, "Metadata/project_settings.config"))))
        # um projeto ja adaptado a que alguem juntou um script: mede-se e fatia-se sem ele, e avisa-se
        apoio.muda_definicoes(ada, poe)
        rc, out = corre("medir.py", ada, "--fatiar")
        self.assertEqual(rc, 0, out)
        self.assertIn("FATIADO", out)
        self.assertIn("scripts de pos-processamento", out)
        # e ao mudar as cores (projeto "da mesma impressora", onde quase tudo passa) tambem fica de fora
        rc, out = corre("cores.py", ada, os.path.join(d, "cores.3mf"), "--cores", ";#232C7C", "--sem-fatiar", "--json")
        self.assertEqual(rc, 0, out)
        rel = json.loads(out)
        self.assertEqual(rel["nao_passou"]["seguranca"], ["post_process"])
        self.assertFalse(apoio.K.tem_pos_processamento(json.loads(apoio.le_zip(os.path.join(d, "cores.3mf"), "Metadata/project_settings.config"))))
        self.assertFalse(os.path.exists(marcador))

    def test_gcode_que_vem_no_projeto_so_passa_com_manter_gcode(self):
        d = apoio.pasta("e2e_gcode")
        orig = apoio.projeto_bambu(os.path.join(d, "Exemplo.3mf"))
        rc, out = corre("adaptar.py", orig, "--impressora", "Kobra X", "--sem-fatiar")
        self.assertEqual(rc, 0, out)
        ada = os.path.join(d, "Exemplo - Kobra X.3mf")
        MARCA = "; g-code que veio no ficheiro (teste)"

        def poe(j):           # como um ficheiro "da Kobra X" partilhado por outra pessoa, com g-code proprio
            j["machine_start_gcode"] = MARCA + "\n" + j["machine_start_gcode"]
            j["filament_start_gcode"] = [MARCA, j["filament_start_gcode"][1]]
            j["machine_max_speed_x"] = ["9000"] * len(j["machine_max_speed_x"])
            dts = j["different_settings_to_system"]
            dts[1] = "filament_start_gcode"
            dts[-1] = ";".join(sorted({x for x in dts[-1].split(";") if x} | {"machine_start_gcode", "machine_max_speed_x"}))
        apoio.muda_definicoes(ada, poe)
        sem = os.path.join(d, "sem.3mf")
        rc, out = corre("cores.py", ada, sem, "--cores", ";#232C7C", "--sem-fatiar", "--json")
        self.assertEqual(rc, 0, out)
        rel = json.loads(out)
        self.assertEqual(sorted(rel["nao_passou"]["seguranca"]), ["filament_start_gcode (filamento 1)", "machine_max_speed_x",
                                                                 "machine_start_gcode"])
        self.assertTrue(any("--manter-gcode" in a for a in rel["avisos"]), rel["avisos"])
        j = json.loads(apoio.le_zip(sem, "Metadata/project_settings.config"))
        self.assertNotIn(MARCA, j["machine_start_gcode"])
        self.assertNotIn(MARCA, json.dumps(j["filament_start_gcode"]))
        self.assertNotEqual(apoio.K.primeiro(j["machine_max_speed_x"]), "9000")
        self.assertIn("levanta o bico", j["machine_end_gcode"])                     # o fim de impressao da skill fica
        # com autorizacao explicita (o utilizador diz que o g-code e dele) passa
        com = os.path.join(d, "com.3mf")
        rc, out = corre("cores.py", ada, com, "--cores", ";#232C7C", "--manter-gcode", "--sem-fatiar", "--json")
        self.assertEqual(rc, 0, out)
        rel = json.loads(out)
        self.assertEqual(rel["nao_passou"]["seguranca"], [])
        j = json.loads(apoio.le_zip(com, "Metadata/project_settings.config"))
        self.assertIn(MARCA, j["machine_start_gcode"])
        self.assertIn(MARCA, json.dumps(j["filament_start_gcode"]))

    def test_custo_com_precos_guardados(self):
        d = apoio.pasta("e2e_custo")
        rc, out = corre("perfil.py", "--preco-kg", "PLA=20;*=30", "--preco-hora", "1")
        self.assertEqual(rc, 0, out)
        try:
            orig = apoio.projeto_bambu(os.path.join(d, "Exemplo.3mf"))
            rc, out = corre("adaptar.py", orig, "--impressora", "Kobra X", "--json")
            self.assertEqual(rc, 0, out)
            rel = json.loads(out)
            gramas = sum(sum(p["g"]) for p in rel["pratos"])
            horas = sum(p["segundos"] for p in rel["pratos"]) / 3600
            self.assertAlmostEqual(rel["custo"]["filamento"], gramas * 20 / 1000, delta=0.02)   # PLA Matte e PLA Silk: familia PLA
            self.assertAlmostEqual(rel["custo"]["maquina"], horas * 1, delta=0.02)
            self.assertAlmostEqual(rel["custo"]["total"], rel["custo"]["filamento"] + rel["custo"]["maquina"], delta=0.011)
        finally:
            corre("perfil.py", "--apagar", "precos", "--apagar", "preco_hora")


if __name__ == "__main__":
    unittest.main()
