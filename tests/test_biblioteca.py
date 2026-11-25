import contextlib
import io
import os
import subprocess
import sys
import unittest
import zipfile

import apoio
from apoio import K, KX, KX6, NEO


class Impressoras(unittest.TestCase):
    def setUp(self):
        K.usa_impressora(KX)

    def test_encontra_pelo_nome_solto(self):
        self.assertEqual(K.encontra_maquina("kobra-x"), KX)
        self.assertEqual(K.encontra_maquina("Anycubic Kobra X"), KX)
        self.assertEqual(K.encontra_maquina("Kobra X 0.6"), KX6)
        self.assertEqual(K.encontra_maquina("Kobra X", "0.6"), KX6)
        self.assertEqual(K.encontra_maquina("kobra 2 neo"), NEO)
        self.assertEqual(K.encontra_maquina(), KX)                       # por omissao

    def test_impressora_desconhecida_ou_sem_esse_bico(self):
        for mau, bico in (("Ender 3", None), ("Kobra", None), ("Kobra 2 Neo", "0.8")):
            with self.assertRaises(SystemExit):
                K.encontra_maquina(mau, bico)

    def test_mesa_e_ace_vem_do_perfil(self):
        self.assertEqual((K.MODELO, K.BICO, K.CAMA_X, K.CAMA_Y, K.ALTURA_MAX), ("Anycubic Kobra X", "0.4", 260.0, 260.0, 260.0))
        self.assertEqual((K.PASSO_X, K.MULTICOR, K.VOLUME_BICO, K.nome_curto()), (312.0, True, 79.0, "Kobra X"))
        K.usa_impressora(NEO)
        self.assertEqual((K.CAMA_X, K.ALTURA_MAX, K.MULTICOR, K.nome_curto()), (220.0, 250.0, False, "Kobra 2 Neo"))
        K.usa_impressora(KX6)
        self.assertEqual(K.nome_curto(), "Kobra X 0.6")

    def test_fim_de_impressao_levanta_o_bico_so_quando_o_de_fabrica_nao_levanta(self):
        fim = K.fim_gcode()
        self.assertIn("G1 Z{max_layer_z + 5}", fim)
        self.assertTrue(fim.rstrip().endswith("M84"))
        K.usa_impressora(NEO)
        self.assertIsNone(K.fim_gcode())

    def test_perfis_compativeis(self):
        self.assertEqual(sorted(K.compativeis("process")), ["0.12mm High Quality", "0.16mm High Quality", "0.20mm Standard", "0.28mm Draft"])
        self.assertIn("Anycubic PLA Silk", K.compativeis("filament"))
        K.usa_impressora(NEO)
        self.assertEqual(sorted(K.compativeis("filament")), ["Anycubic PETG", "Anycubic PLA"])

    def test_perfis_do_utilizador(self):
        base = "0.20mm Standard @" + KX
        self.assertEqual(K.meus("process"), [("O meu 0.20", base)])
        self.assertEqual(K.meu_para("process", base), "O meu 0.20")
        self.assertIsNone(K.meu_para("process", "0.28mm Draft @" + KX))
        self.assertTrue(K.meu_compativel("process", "O meu 0.20"))
        self.assertEqual(K.mudancas_do_utilizador("process", "O meu 0.20"), ["seam_position", "wall_loops"])
        p = K.perfil("process", "O meu 0.20")                              # heranca resolvida
        self.assertEqual((p["seam_position"], p["wall_loops"], p["layer_height"]), ("back", "4", "0.2"))

    def test_grava_perfil_do_utilizador_mantem_a_base(self):
        # sem "inherits" a linha de comandos do Anycubic recusa o perfil ("process not compatible with printer")
        f = os.path.join(apoio.pasta("perfil"), "p.json")
        d = apoio.le_json(K.grava_perfil(f, "process", "O meu 0.20", {"wall_loops": "5"}))
        self.assertEqual((d["inherits"], d["from"], d["wall_loops"]), ("0.20mm Standard @" + KX, "User", "5"))
        d = apoio.le_json(K.grava_perfil(f, "process", "0.20mm Standard @" + KX, {}))
        self.assertEqual((d["inherits"], d["from"]), ("", "system"))

    def test_impressora_do_projeto(self):
        self.assertTrue(K.impressora_do_projeto({"printer_settings_id": NEO}))
        self.assertEqual(K.MODELO, "Anycubic Kobra 2 Neo")
        self.assertFalse(K.impressora_do_projeto({"printer_settings_id": "Bambu Lab A1 0.4 nozzle"}))


class Geometria(unittest.TestCase):
    def setUp(self):
        K.usa_impressora(KX)

    def test_compoe(self):
        t = [2.0, 0, 0, 0, 2.0, 0, 0, 0, 2.0, 10.0, 20.0, 30.0]
        self.assertEqual(K.compoe(K.IDENT, t), t)
        self.assertEqual(K.compoe(t, K.IDENT), t)
        desloca = list(K.IDENT[:9]) + [1.0, 2.0, 3.0]
        self.assertEqual(K.compoe(t, desloca)[9:], [12.0, 24.0, 36.0])     # desloca e depois escala/desloca
        self.assertEqual(K.matriz(K.fmt_matriz(t)), t)

    def test_pratos(self):
        self.assertEqual([K.colunas(n) for n in (1, 2, 3, 4, 5, 9, 10)], [1, 2, 2, 2, 3, 3, 4])
        self.assertEqual(K.origem_prato(1, 4), (0.0, -0.0))
        self.assertEqual(K.origem_prato(2, 2), (312.0, -0.0))
        self.assertEqual(K.origem_prato(3, 4), (0.0, -312.0))
        for n in (1, 2, 4, 7):
            for p in range(1, n + 1):
                ox, oy = K.origem_prato(p, n)
                caixa = {"lo": [ox + 10, oy + 10, 0], "hi": [ox + 250, oy + 250, 5]}
                self.assertEqual(K.prato_de(caixa, n), p)

    def test_objeto_fora_da_grelha_de_pratos_conta_para_o_mais_proximo(self):
        # um numero de prato que nao existe (0, ou 3 num projeto de 2) fazia os outros scripts inventar pratos
        def prato(x, y, n):
            return K.prato_de({"lo": [x - 5, y - 5, 0], "hi": [x + 5, y + 5, 5]}, n)
        self.assertEqual(prato(-400, 130, 2), 1)                 # muito a esquerda do prato 1
        self.assertEqual(prato(2000, 130, 2), 2)                 # muito a direita do ultimo
        self.assertEqual(prato(130, 900, 4), 1)                  # acima da primeira fila
        self.assertEqual(prato(130, -5000, 4), 3)                # abaixo da ultima fila
        self.assertEqual(prato(312 + 130, -312 + 130, 3), 3)     # o sitio onde seria o prato 4 de 3
        self.assertEqual(prato(130, 130, 1), 1)

    def test_nomes_com_caracteres_de_xml(self):
        d = apoio.pasta("xml")
        p = apoio.projeto_anycubic(os.path.join(d, "a.3mf"))

        def mudar(nome, dados):
            if nome == "Metadata/model_settings.config":
                return dados.decode().replace('value="Caixa"', 'value="Caixa &amp; &quot;tampa&quot;"').encode()
            return dados
        K.reescreve(p, p, mudar)
        with zipfile.ZipFile(p) as z:
            self.assertEqual(K.Modelo(z).caixas()[0]["nome"], 'Caixa & "tampa"')

    def test_distancia_entre_caixas(self):
        self.assertEqual(K.sep((0, 0, 10, 10), (5, 5, 20, 20)), 0)
        self.assertEqual(K.sep((0, 0, 10, 10), (13, 0, 20, 10)), 3)
        self.assertEqual(K.sep((0, 0, 10, 10), (13, 14, 20, 20)), 5.0)

    def test_modelo_mede_o_exemplo(self):
        p = apoio.projeto_bambu(os.path.join(apoio.pasta("modelo"), "m.3mf"))
        with zipfile.ZipFile(p) as z:
            mod = K.Modelo(z)
            cx = mod.caixas()
        self.assertEqual(mod.n_pratos, 2)
        self.assertEqual([c["nome"] for c in cx], ["Caixa", "Tampa"])
        self.assertEqual([[round(v, 1) for v in c["tam"]] for c in cx], [[60.0, 52.0, 48.0], [66.0, 57.2, 4.0]])
        self.assertEqual([round(c["lo"][2], 6) for c in cx], [0.0, 0.0])    # assentes na mesa

    def test_modelo_so_conta_pecas_normais(self):
        # um modificador enorme dentro da caixa nao pode contar para o tamanho
        d = apoio.pasta("modificador")
        p = apoio.projeto_bambu(os.path.join(d, "m.3mf"))
        q = os.path.join(d, "mod.3mf")

        def mudar(nome, dados):
            if nome == "Metadata/model_settings.config":
                return dados.decode().replace('<part id="2" subtype="normal_part">', '<part id="2" subtype="modifier_part">').encode()
            return dados
        K.reescreve(p, q, mudar)
        with zipfile.ZipFile(q) as z:
            caixa = K.Modelo(z).caixas()[0]
        self.assertEqual([round(v, 1) for v in caixa["tam"]], [60.0, 52.0, 40.0])   # sem a faixa (que passou a modificador)

    def test_avisos_de_mesa(self):
        p = apoio.projeto_anycubic(os.path.join(apoio.pasta("mesa"), "a.3mf"))
        with zipfile.ZipFile(p) as z:
            por_prato = K.caixas_por_prato(K.Modelo(z))
        self.assertEqual(sorted(por_prato), [1, 2])
        self.assertEqual(K.avisos_mesa(por_prato), [])
        K.usa_impressora(NEO)                                               # numa mesa de 220 ja nao estao centradas...
        self.assertEqual(K.avisos_mesa({1: por_prato[1]}), [])              # ...mas cabem
        por_prato[1][0]["lhi"][0] = 300.0
        self.assertIn("sai da mesa", K.avisos_mesa(por_prato)[0])

    def test_torre_de_purga_num_sitio_livre(self):
        self.assertEqual(K.posicao_torre([], 2), (112, 118))                # mesa vazia: ao centro
        pos = K.posicao_torre([(100, 100, 160, 160)], 2)
        torre = (pos[0] - 8, pos[1] - 8, pos[0] + 35 + 3, pos[1] + 22)
        self.assertGreaterEqual(K.sep(torre, (100, 100, 160, 160)), 10)
        self.assertIsNone(K.posicao_torre([(0, 0, 260, 260)], 2))           # mesa cheia


class Fatiado(unittest.TestCase):
    def test_tempo(self):
        self.assertEqual(K.tempo_segundos("1d 2h 3m 4s"), 93784)
        self.assertEqual(K.tempo_segundos("17m 8s"), 1028)
        self.assertEqual(K.tempo_segundos(None), 0)

    def test_resumo_do_gcode(self):
        g = os.path.join(apoio.pasta("gcode"), "plate_1.gcode")
        apoio.escreve(g, (
            "; estimated printing time (normal mode) = 1h 2m 3s\n; filament used [g] = 10.50, 2.25\n"
            "; total filament used [g] = 12.75\n; total layers count = 100\n; total filament change = 3\n; max_z_height: 20.00\n"
            ";TYPE:Outer wall\nG1 X100 Y100 E1\nG1 X150 Y120 E2\n;TYPE:Prime tower\nG1 X20 Y30 E1\nG1 X50 Y45 E1\n"
            ";TYPE:Custom\nG1 X0 Y0 E5\n"))
        r = K.resumo_gcode(g)
        self.assertEqual((r["tempo"], r["segundos"], r["g"], r["total_g"], r["camadas"], r["trocas"], r["altura"], r["camada_media"]),
                         ("1h 2m 3s", 3723, [10.5, 2.25], 12.75, 100, 3, 20.0, 0.2))
        self.assertEqual((r["pecas"], r["torre"]), ([100.0, 100.0, 150.0, 120.0], [20.0, 30.0, 50.0, 45.0]))
        t = K.texto_resumo({1: r}, ["#FFFFFF", "#800020"])
        self.assertIn("prato 1: 1h 2m 3s, 12.75 g [10.5 g (#FFFFFF) + 2.2 g (#800020)], 100 camadas", t)
        self.assertIn("3 trocas de cor", t)
        caixas = {1: [{"nome": "peca", "llo": [40, 40, 0], "lhi": [80, 80, 5]}]}
        self.assertEqual(len(K.colisoes_torre({1: r}, caixas)), 1)          # a torre (20..50, 30..45) toca na peca
        caixas[1][0]["llo"] = [60, 60, 0]
        self.assertEqual(K.colisoes_torre({1: r}, caixas), [])

    def test_scripts_de_pos_processamento(self):
        self.assertFalse(K.tem_pos_processamento({}))
        self.assertFalse(K.tem_pos_processamento({"post_process": []}))
        self.assertFalse(K.tem_pos_processamento({"post_process": ["", "  "]}))
        j = {"post_process": ["cmd.exe /c x"], "outra": 1}
        self.assertTrue(K.tem_pos_processamento(j))
        self.assertTrue(K.sem_pos_processamento(j))
        self.assertEqual(j, {"post_process": [], "outra": 1})
        self.assertFalse(K.sem_pos_processamento(j))
        self.assertIn("pos-processamento", K.explica_rc(4294967277, "[error] normative_check: postprocess not supported, array size 1"))

    def test_erros_do_slicer_com_dica(self):
        t = K.explica_rc(4294967245, "[error] plate 1's got error when validate: Variable layer height is not supported with Organic supports.")
        self.assertIn("--sem-camadas-variaveis", t)
        self.assertIn("rebentou", K.explica_rc(3221225477, ""))


class Preferencias(unittest.TestCase):
    def tearDown(self):
        K.grava_config(saida=None, originais=None, precos=None, preco_hora=None)

    def test_guardar_e_apagar(self):
        K.grava_config(saida=r"D:\Impressoes\Adaptado {impressora}", preco_hora=0.5)
        self.assertEqual(K.le_config()["preco_hora"], 0.5)
        K.usa_impressora(KX6)
        self.assertEqual(K.pasta_config("saida"), r"D:\Impressoes\Adaptado Kobra X 0.6")
        K.grava_config(saida=None)
        self.assertIsNone(K.pasta_config("saida"))
        self.assertNotIn("saida", K.le_config())

    def test_config_estragada_nao_rebenta_nem_se_perde(self):
        os.makedirs(K.PASTA_DADOS, exist_ok=True)
        apoio.escreve(K.CONFIG, "{isto nao e json")
        erros, K._AVISOU_CONFIG = io.StringIO(), False
        with contextlib.redirect_stderr(erros):
            self.assertEqual(K.le_config(), {})
            self.assertEqual(K.le_config(), {})
        self.assertEqual(erros.getvalue().count("nao consegui ler as preferencias"), 1)      # avisa, e so uma vez
        with contextlib.redirect_stderr(io.StringIO()):
            K.grava_config(preco_hora=1)
        self.assertEqual(K.le_config(), {"preco_hora": 1})
        self.assertEqual(apoio.le(K.CONFIG + ".estragado"), "{isto nao e json")              # o que la estava fica guardado
        os.remove(K.CONFIG + ".estragado")

    def test_config_gravada_pelo_bloco_de_notas(self):
        # o Bloco de notas pode gravar UTF-8 com uma marca (BOM) no inicio: tem de se ler na mesma
        os.makedirs(K.PASTA_DADOS, exist_ok=True)
        with open(K.CONFIG, "w", encoding="utf-8-sig") as f:
            f.write('{"impressora": "Kobra S1"}')
        self.assertEqual(K.le_config(), {"impressora": "Kobra S1"})
        K.grava_config(impressora=None)


class Copias(unittest.TestCase):
    def test_copia_antes_de_substituir(self):
        d = apoio.pasta("copias")
        f = os.path.join(d, "Vaso - Kobra X.3mf")
        self.assertIsNone(K.guarda_copia(f, "adaptar"))                     # ainda nao existe: nada a guardar
        apoio.escreve(f, "versao 1")
        c1 = K.guarda_copia(f, "adaptar")
        apoio.escreve(f, "versao 2")
        c2 = K.guarda_copia(f, "escalar")
        self.assertNotEqual(c1, c2)
        self.assertEqual(apoio.le(c1), "versao 1")
        mais_recente = K.copias()[0]
        self.assertEqual((mais_recente["copia"], mais_recente["motivo"], mais_recente["original"]), (c2, "escalar", os.path.abspath(f)))

    def test_repor_a_copia_mais_antiga_com_as_copias_cheias(self):
        # guardar "a versao que la estava" apagava a copia mais antiga... que era a que se ia repor
        d = apoio.pasta("copias3")
        alvo = os.path.join(d, "importante.3mf")
        apoio.escreve(alvo, "versao boa")
        K.guarda_copia(alvo, "escalar")
        apoio.escreve(alvo, "versao estragada")
        outro = apoio.escreve(os.path.join(d, "outro.3mf"), "x")
        for n in range(K.MAX_COPIAS - 1):                          # enche: a copia do alvo passa a ser a mais antiga
            K.guarda_copia(outro, "pratos")
        self.assertEqual(len(K.copias()), K.MAX_COPIAS)
        self.assertEqual(K.copias()[-1]["original"], os.path.abspath(alvo))
        r = subprocess.run([sys.executable, os.path.join(apoio.SCRIPTS, "desfazer.py"), alvo], capture_output=True,
                           env=apoio.ambiente_isolado())
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        self.assertEqual(apoio.le(alvo), "versao boa")
        self.assertIn("versao estragada", [apoio.le(c["copia"]) for c in K.copias()])        # e da para desfazer o desfazer

    def test_so_ficam_as_ultimas(self):
        d = apoio.pasta("copias2")
        f = os.path.join(d, "x.3mf")
        antigo, K.MAX_COPIAS = K.MAX_COPIAS, 3
        try:
            for n in range(5):
                apoio.escreve(f, str(n))
                K.guarda_copia(f, f"n{n}")
            guardadas = K.copias()
            self.assertEqual([c["motivo"] for c in guardadas], ["n4", "n3", "n2"])
            self.assertEqual([apoio.le(c["copia"]) for c in guardadas], ["4", "3", "2"])
            pasta = os.path.dirname(guardadas[0]["copia"])
            self.assertEqual(len([x for x in os.listdir(pasta) if x != "indice.json"]), 3)     # as mais antigas foram apagadas
        finally:
            K.MAX_COPIAS = antigo


if __name__ == "__main__":
    unittest.main()
