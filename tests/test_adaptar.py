import json
import os
import unittest
import zipfile

import apoio
from apoio import K, KX, NEO
import adaptar


class Materiais(unittest.TestCase):
    def setUp(self):
        K.usa_impressora(KX)

    def test_material_do_filamento_do_autor(self):
        casos = {
            ("Bambu PLA Matte @BBL A1", "PLA"): ("PLA", "PLA Matte", False),
            ("Bambu PLA Silk+", "PLA"): ("PLA", "PLA Silk", False),
            ("Bambu PETG HF", "PETG"): ("PETG", None, False),
            ("Bambu PLA-CF", "PLA-CF"): ("PLA-CF", None, False),
            ("Bambu PA6-CF", "PA6-CF"): ("PA-CF", None, False),
            ("Bambu PAHT-CF", "PAHT-CF"): ("PAHT-CF", None, False),
            ("Bambu TPU for AMS", "TPU-AMS"): ("TPU-ACE", None, False),
            ("Bambu TPU 95A", "TPU"): ("TPU", None, False),
            ("Bambu Support For PLA", "PLA-S"): ("PLA", None, True),
            ("Generic HIPS", "HIPS"): (None, None, False),
        }
        for (nome, tipo), esperado in casos.items():
            self.assertEqual(adaptar.material_de(nome, tipo), esperado, nome)

    def test_familia(self):
        self.assertEqual([adaptar.familia(x) for x in ("PA6-CF", "PAHT-CF", "PLA Matte", "PETG-CF", "PET-CF", "TPU 95A")],
                         ["PA", "PA", "PLA", "PETG", "PET", "TPU"])

    def test_escolhe_o_perfil_de_filamento_da_impressora(self):
        self.assertEqual(adaptar.filamento_para("Bambu PLA Matte @BBL A1", "PLA")[:2], ("Anycubic PLA Matte @" + KX, None))
        self.assertEqual(adaptar.filamento_para("Bambu TPU for AMS", "TPU-AMS")[0], "Anycubic TPU for ACE @" + KX)
        K.usa_impressora(NEO)                       # nao tem PLA Matte: fica o PLA normal, sem aviso (e o mesmo material)
        self.assertEqual(adaptar.filamento_para("Bambu PLA Matte @BBL A1", "PLA")[:2], ("Anycubic PLA @" + NEO, None))

    def test_nunca_troca_de_material_em_silencio(self):
        nome, aviso, _ = adaptar.filamento_para("Bambu ASA", "ASA")
        self.assertEqual(nome, "Anycubic ABS @" + KX)
        self.assertIn("nao tem perfil de ASA", aviso)
        nome, aviso, _ = adaptar.filamento_para("Generic HIPS", "HIPS")
        self.assertEqual(nome, "Anycubic PLA @" + KX)
        self.assertIn("nao tem perfil para este material", aviso)

    def test_notas_por_material(self):
        self.assertEqual(adaptar.notas_de("PLA"), [])
        self.assertIn("bico endurecido", " ".join(adaptar.notas_de("PETG-CF")))
        self.assertIn("fechada", " ".join(adaptar.notas_de("ABS")))
        self.assertIn("mais presos", " ".join(adaptar.notas_de("PLA", suporte=True)))

    def test_preco_por_material(self):
        precos = {"PLA": 18, "PLA SILK": 24, "*": 22}
        self.assertEqual(adaptar.preco_material(precos, "Anycubic PLA Silk @" + KX), 24.0)      # o mais especifico
        self.assertEqual(adaptar.preco_material(precos, "Anycubic PLA Matte @" + KX), 18.0)     # a familia
        self.assertEqual(adaptar.preco_material(precos, "Anycubic PETG @" + KX), 22.0)          # o resto
        self.assertEqual(adaptar.preco_material(precos, "O meu PLA"), 18.0)                     # perfil do utilizador: pela base
        self.assertIsNone(adaptar.preco_material({"PETG": 20}, "Anycubic PLA @" + KX))
        self.assertIsNone(adaptar.preco_material(None, "Anycubic PLA @" + KX))


class Processo(unittest.TestCase):
    def setUp(self):
        K.usa_impressora(KX)
        self.sis = K.perfil("process", "0.20mm Standard @" + KX)

    def test_escolhe_o_perfil_com_o_mesmo_nome(self):
        self.assertEqual(adaptar.escolhe_processo({"print_settings_id": "0.20mm Standard @BBL A1"}), "0.20mm Standard @" + KX)
        self.assertEqual(adaptar.escolhe_processo({"print_settings_id": "0.16mm Optimal @BBL X1C"}), "0.16mm High Quality @" + KX)
        self.assertEqual(adaptar.escolhe_processo({"print_settings_id": "0.12mm Fine @BBL A1"}), "0.12mm High Quality @" + KX)

    def test_sem_nome_conhecido_vai_pela_altura_de_camada(self):
        self.assertEqual(adaptar.escolhe_processo({"layer_height": "0.24"}), "0.20mm Standard @" + KX)
        self.assertEqual(adaptar.escolhe_processo({"print_settings_id": "0.08mm Extra Fine @BBL A1", "layer_height": "0.08"}),
                         "0.20mm Standard @" + KX)   # nao ha 0.08: o Standard mais proximo (a altura passa como mudanca)

    def test_perfil_pedido(self):
        self.assertEqual(adaptar.escolhe_processo({}, "0.28mm Draft"), "0.28mm Draft @" + KX)
        self.assertEqual(adaptar.escolhe_processo({}, "O meu 0.20"), "O meu 0.20")
        with self.assertRaises(SystemExit):
            adaptar.escolhe_processo({}, "0.50mm Enorme")

    def projeto(self, **kw):
        j = {"different_settings_to_system": [";".join(kw.pop("mudou", []))], "layer_height": "0.2", "wall_loops": "2"}
        j.update(kw)
        return j

    def test_passa_o_que_o_autor_mudou(self):
        j = self.projeto(mudou=["sparse_infill_density", "enable_support"], sparse_infill_density="10%", enable_support="1")
        mud, origem, nao, _ = adaptar.mudancas_processo(j, self.sis)
        self.assertEqual(mud, {"sparse_infill_density": "10%", "enable_support": "1"})
        self.assertEqual(set(origem.values()), {"autor"})
        self.assertEqual(nao, {"impressora": [], "sem_equivalente": [], "velocidades": [], "seguranca": []})

    def test_valores_de_intencao_do_perfil_do_autor_tambem_passam(self):
        mud, origem, _, _ = adaptar.mudancas_processo(self.projeto(wall_loops="3"), self.sis)
        self.assertEqual((mud, origem), ({"wall_loops": "3"}, {"wall_loops": "perfil"}))

    def test_o_que_e_da_impressora_do_autor_nao_passa(self):
        j = self.projeto(mudou=["outer_wall_acceleration", "machine_start_gcode", "wipe_tower_x", "skin_infill_density"],
                         outer_wall_acceleration="12000", machine_start_gcode="G28", wipe_tower_x="15", skin_infill_density="20%")
        mud, _, nao, _ = adaptar.mudancas_processo(j, self.sis)
        self.assertEqual(mud, {})
        self.assertEqual(nao["impressora"], ["outer_wall_acceleration", "machine_start_gcode"])
        self.assertEqual(nao["sem_equivalente"], ["skin_infill_density"])          # a torre de purga nem aparece: trata a skill

    def test_velocidades_do_autor_so_baixam(self):
        j = self.projeto(mudou=["outer_wall_speed", "inner_wall_speed"], outer_wall_speed=["350"], inner_wall_speed=["150"])
        mud, _, nao, _ = adaptar.mudancas_processo(j, self.sis)
        self.assertEqual(mud, {"inner_wall_speed": ["150"]})                       # mais devagar que o perfil: passa
        self.assertEqual(nao["velocidades"], ["outer_wall_speed 350 > 200"])       # mais depressa: fica a do perfil

    def test_a_velocidade_do_ironing_faz_parte_da_receita_do_autor(self):
        j = self.projeto(mudou=["ironing_speed", "ironing_type"], ironing_speed="150", ironing_type="top")
        mud, _, nao, _ = adaptar.mudancas_processo(j, self.sis)
        self.assertEqual(mud, {"ironing_speed": "150", "ironing_type": "top"})
        self.assertEqual(nao["velocidades"], [])

    def test_o_perfil_do_utilizador_ganha_a_intencao_mas_nao_ao_que_o_autor_mudou(self):
        j = self.projeto(mudou=["sparse_infill_density"], sparse_infill_density="10%", wall_loops="3", seam_position="random")
        meu = K.perfil("process", "O meu 0.20")
        mud, _, _, _ = adaptar.mudancas_processo(j, meu, protegidas={"wall_loops", "seam_position"})
        self.assertEqual(mud, {"sparse_infill_density": "10%"})

    def test_perfil_escolhido_a_mao_manda_na_altura(self):
        j = self.projeto(mudou=["layer_height", "top_shell_layers"], layer_height="0.12", top_shell_layers="7")
        mud, _, _, _ = adaptar.mudancas_processo(j, self.sis, sem_altura=True)
        self.assertEqual(mud, {})
        mud, _, _, _ = adaptar.mudancas_processo(j, self.sis)
        self.assertEqual(mud, {"layer_height": "0.12", "top_shell_layers": "7"})

    def test_projeto_que_ja_e_desta_impressora_passa_tudo(self):
        # mudar as cores de um projeto adaptado nao pode deitar fora o que o utilizador afinou a mao no slicer
        j = self.projeto(mudou=["outer_wall_acceleration", "outer_wall_speed", "prime_tower_width", "wipe_tower_x", "print_settings_id"],
                         outer_wall_acceleration="12000", outer_wall_speed=["350"], prime_tower_width="45", wipe_tower_x="15",
                         print_settings_id="x")
        sis = dict(self.sis, outer_wall_acceleration="6000")
        mud, origem, nao, _ = adaptar.mudancas_processo(j, sis, proprio=True)
        self.assertEqual(mud, {"outer_wall_acceleration": "12000", "outer_wall_speed": ["350"], "prime_tower_width": "45"})
        self.assertEqual(set(origem.values()), {"projeto"})
        self.assertEqual(nao, {"impressora": [], "sem_equivalente": [], "velocidades": [], "seguranca": []})
        mud, _, nao, _ = adaptar.mudancas_processo(j, sis)                           # o mesmo, vindo de outra impressora
        self.assertEqual(mud, {})
        self.assertEqual((nao["impressora"], nao["velocidades"]), (["outer_wall_acceleration", "print_settings_id"], ["outer_wall_speed 350 > 200"]))

    def test_scripts_de_pos_processamento_nunca_passam(self):
        # post_process sao comandos que um slicer corre no computador depois de fatiar: nem de um original, nem de um
        # projeto que ja e desta impressora
        j = self.projeto(mudou=["post_process", "sparse_infill_density"], post_process=["cmd.exe /c qualquer coisa"],
                         sparse_infill_density="10%")
        sis = dict(self.sis, post_process=[])
        for proprio in (False, True):
            mud, _, nao, _ = adaptar.mudancas_processo(j, sis, proprio=proprio)
            self.assertEqual(mud, {"sparse_infill_density": "10%"}, proprio)
            self.assertEqual(nao["seguranca"], ["post_process"], proprio)
        # mesmo sem estar na lista de alteracoes do projeto, fica dito
        j = self.projeto(post_process=["script.bat"])
        self.assertEqual(adaptar.mudancas_processo(j, sis)[2]["seguranca"], ["post_process"])
        self.assertEqual(adaptar.mudancas_processo(self.projeto(post_process=[""]), sis)[2]["seguranca"], [])

    def test_formato_do_nome_do_ficheiro_so_passa_se_for_um_nome(self):
        sis = dict(self.sis, filename_format="{input_filename_base}.gcode")
        bom = self.projeto(mudou=["filename_format"], filename_format="{input_filename_base}_{print_time}.gcode")
        mud, _, nao, _ = adaptar.mudancas_processo(bom, sis, proprio=True)
        self.assertEqual((mud, nao["seguranca"]), ({"filename_format": "{input_filename_base}_{print_time}.gcode"}, []))
        for mau in ("..\\..\\x.gcode", "C:/Windows/x.gcode", "pasta\\x.gcode"):
            mud, _, nao, _ = adaptar.mudancas_processo(self.projeto(mudou=["filename_format"], filename_format=mau), sis, proprio=True)
            self.assertEqual((mud, nao["seguranca"]), ({}, ["filename_format"]), mau)

    def test_nomes_que_mudam_entre_slicers(self):
        self.assertEqual(adaptar.normaliza("sparse_infill_pattern", "zig-zag", self.sis), "zigzag")
        self.assertEqual(adaptar.normaliza("support_style", "tree_organic", self.sis), "default")
        self.assertEqual(adaptar.normaliza("outer_wall_speed", "150", self.sis), ["150"])   # lista como no perfil
        self.assertEqual(adaptar.normaliza("wall_loops", ["3"], self.sis), "3")


class Filamentos(unittest.TestCase):
    def test_descobre_os_usados(self):
        p = apoio.projeto_bambu(os.path.join(apoio.pasta("usados"), "u.3mf"))
        with zipfile.ZipFile(p) as z:
            j = json.loads(z.read("Metadata/project_settings.config"))
            ms = z.read("Metadata/model_settings.config").decode("utf-8")
            usados, n, pinturas = adaptar.filamentos_usados(z, j, ms)
            self.assertEqual((usados, n, pinturas["pintura_cores"]), ([2, 4], 4, False))
            # filamento de suporte so conta com suportes ligados
            j2 = dict(j, support_filament="3")
            self.assertEqual(adaptar.filamentos_usados(z, j2, ms)[0], [2, 3, 4])
            self.assertEqual(adaptar.filamentos_usados(z, dict(j2, enable_support="0"), ms)[0], [2, 4])
            # um filamento novo pedido para uma peca (acima dos do projeto) conta
            ms5 = ms.replace('key="extruder" value="4"', 'key="extruder" value="5"')
            self.assertEqual(adaptar.filamentos_usados(z, j, ms5)[0], [2])
            self.assertEqual(adaptar.filamentos_usados(z, j, ms5, {5})[0], [2, 5])

    def test_renumera(self):
        ms = '<metadata key="extruder" value="2"/><metadata key="support_filament" value="4"/><metadata key="name" value="4"/>'
        self.assertEqual(adaptar.remapeia(ms, {2: 1, 4: 2}),
                         '<metadata key="extruder" value="1"/><metadata key="support_filament" value="2"/><metadata key="name" value="4"/>')
        self.assertEqual(adaptar.remapeia(ms, {}), ms)

    def test_cores(self):
        self.assertEqual(adaptar._hex("800020"), "#800020")
        self.assertEqual(adaptar._hex(" #abcdef "), "#ABCDEF")
        for mau in ("bordo", "#12345", "#GGGGGG"):
            with self.assertRaises(SystemExit):
                adaptar._hex(mau)


class Pedido(unittest.TestCase):
    def test_opcoes(self):
        a = adaptar.pedido(original="x.3mf", material="PETG")
        self.assertEqual((a.original, a.material, a.fatiar, a.camadas_variaveis, a.substituir), ("x.3mf", "PETG", True, True, False))
        with self.assertRaises(TypeError):
            adaptar.pedido(original="x.3mf", impresora="Kobra X")              # gralha no nome da opcao

    def test_ficheiros_que_nao_servem(self):
        d = apoio.pasta("maus")
        with self.assertRaises(SystemExit) as e:
            adaptar.adapta(adaptar.pedido(original=os.path.join(d, "nao existe.3mf")))
        self.assertIn("Nao encontro", str(e.exception))
        mau = os.path.join(d, "texto.3mf")
        apoio.escreve(mau, "isto nao e um zip")
        with self.assertRaises(SystemExit) as e:
            adaptar.adapta(adaptar.pedido(original=mau))
        self.assertIn("nao e um 3MF valido", str(e.exception))
        fatiado = os.path.join(d, "ja fatiado.gcode.3mf")
        with zipfile.ZipFile(fatiado, "w") as z:
            z.writestr("Metadata/plate_1.gcode", "G28\n")
        with self.assertRaises(SystemExit) as e:
            adaptar.adapta(adaptar.pedido(original=fatiado))
        self.assertIn("nao tem modelo 3D", str(e.exception))

    def test_nao_substitui_sem_pedir(self):
        d = apoio.pasta("existe")
        orig = apoio.projeto_bambu(os.path.join(d, "Vaso.3mf"))
        apoio.escreve(os.path.join(d, "Vaso - Kobra X.3mf"), "adaptado antigo")
        with self.assertRaises(SystemExit) as e:
            adaptar.adapta(adaptar.pedido(original=orig))
        self.assertIn("--substituir", str(e.exception))
        self.assertEqual(apoio.le(os.path.join(d, "Vaso - Kobra X.3mf")), "adaptado antigo")


if __name__ == "__main__":
    unittest.main()
