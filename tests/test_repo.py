"""O repositorio esta pronto a publicar? (as mesmas verificacoes de tools/verifica.py, mais os ZIPs)"""
import os
import sys
import unittest
import zipfile

import apoio

sys.path.insert(0, os.path.join(apoio.RAIZ, "tools"))
import gera_comandos  # noqa: E402
import publica  # noqa: E402
import verifica  # noqa: E402


class Repositorio(unittest.TestCase):
    def test_verificacoes(self):
        self.assertEqual(verifica.problemas(), [])

    def test_a_versao_e_a_mesma_em_todo_o_lado(self):
        vs = verifica.versoes()
        self.assertEqual(len(set(vs.values())), 1, vs)
        self.assertEqual(apoio.K.versao(), vs["skills/makerworld-to-any/VERSION"])

    def test_comandos_gerados(self):
        self.assertEqual(gera_comandos.diferencas(), ([], []))
        for cmd, texto in gera_comandos.COMANDOS.items():
            self.assertIn(f"name: {cmd}\n", texto)
            self.assertIn("disable-model-invocation: true", texto)      # so o utilizador os chama
            self.assertIn("$ARGUMENTS", texto)

    def test_cada_comando_any_tem_o_seu_script(self):
        for cmd, script in (("any-pratos", "pratos.py"), ("any-cores", "cores.py"), ("any-desfazer", "desfazer.py"),
                            ("any-perfil", "perfil.py"), ("any-diagnostico", "diagnostico.py"), ("any-update", "atualizar.py")):
            self.assertIn(script, gera_comandos.COMANDOS[cmd])
            self.assertTrue(os.path.isfile(os.path.join(apoio.SCRIPTS, script)), script)

    def test_deteta_dados_pessoais(self):
        # (os exemplos sao montados aqui para este ficheiro nao ter, ele proprio, um caminho pessoal nem um email)
        caminho = "C:" + "\\Users\\" + "Maria\\Desktop\\vaso.3mf"
        email = "maria.silva" + "@" + "gmail.com"
        achou = verifica.dados_pessoais("x.md", f"ver {caminho}\nfalar com {email}\n", verifica.GENERICOS)
        self.assertEqual(len(achou), 2)
        limpo = "instala em %USERPROFILE%\\.claude\\skills ou C:\\Users\\<tu>\\.claude\nactions/checkout@v4\nperfil @Anycubic Kobra X\n"
        self.assertEqual(verifica.dados_pessoais("x.md", limpo, verifica.GENERICOS), [])

    @unittest.skipIf(sys.version_info < (3, 12), "num Python mais antigo estes f-strings ja sao erro de sintaxe")
    def test_deteta_fstrings_que_so_dao_no_python_novo(self):
        # a skill corre com o Python de quem a instala: nada de sintaxe que so exista do 3.12 para cima
        mau = 'd = {"a": 1}\nx = f"{d["a"]}"\ny = f"{chr(10).join(["a"])}"\n'
        self.assertEqual(verifica.fstrings_novos(mau), [2, 3])
        bom = "d = {'a': 1}\nx = f\"{d['a']} {d!r}\"\ny = f'''{d[\"a\"]}'''\n"
        self.assertEqual(verifica.fstrings_novos(bom), [])

    def test_zips_da_release(self):
        antigo = publica.DIST
        publica.DIST = apoio.pasta("dist")
        try:
            completo, so_skill = publica.constroi(mostra=False)
        finally:
            publica.DIST = antigo
        v = publica.versao()
        self.assertEqual(os.path.basename(completo), f"makerworld-to-any-v{v}.zip")      # o nome que o /any-update procura
        with zipfile.ZipFile(completo) as z:
            nomes = z.namelist()
            self.assertIn("instalar.bat", nomes)
            self.assertIn("makerworld-to-any/scripts/adaptar.py", nomes)
            for cmd in gera_comandos.COMANDOS:
                self.assertIn(f"{cmd}/SKILL.md", nomes)
            self.assertFalse([n for n in nomes if "__pycache__" in n or n.endswith(".pyc")])
            self.assertNotIn(b"\r\n", z.read("makerworld-to-any/scripts/adaptar.py"))
        with zipfile.ZipFile(so_skill) as z:
            self.assertTrue(all(n.startswith("makerworld-to-any/") for n in z.namelist()))

    def test_texto_da_release_vem_do_changelog(self):
        v = publica.versao()
        self.assertTrue(publica.notas(v).strip())
        self.assertTrue(publica.titulo(v).startswith(f"v{v}"))


if __name__ == "__main__":
    unittest.main()
