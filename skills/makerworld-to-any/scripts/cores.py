"""Cores e filamentos de um projeto Anycubic ja adaptado: ver que filamento tem cada objeto e cada peca, por pecas
noutro filamento ("o nome a azul e o resto a branco"), juntar uma cor nova, mudar cores ou o material.
MakerWorld to Any - feito pela Megatic (https://megatic.pt).

Uso:
    python cores.py <projeto.3mf> --listar
    python cores.py <projeto.3mf> [<saida.3mf>] --atribuir "anel=2;1.3=2" --cores "#FFFFFF;#800020"
    python cores.py <projeto.3mf> [<saida.3mf>] --cores ";#232C7C"            muda so a cor do filamento 2
    python cores.py <projeto.3mf> [<saida.3mf>] --material PETG

  --atribuir  alvo=filamento, separados por ";". Alvo: "tudo", o numero de um objeto da lista ("2"), de uma peca
              ("1.3"), ou um texto do nome (objetos com esse nome; se nao houver, pecas com esse nome).
              Um numero de filamento que ainda nao existe cria um filamento novo (da-lhe a cor em --cores).
  --cores     cor de cada filamento pela posicao: a posicao e o numero do filamento que aparece em --listar e que se
              usa em --atribuir (vazio = fica a que estava; a cor do filamento novo 3 vai na posicao 3: ";;#232C7C").

Um filamento que fique sem nenhuma peca sai do projeto e os seguintes descem um numero: o relatorio diz os numeros
novos (e a ranhura da ACE de cada cor).

Sem <saida.3mf> altera o proprio ficheiro (fica uma copia de seguranca; desfazer.py repoe). O projeto volta a passar
pelo Anycubic com os perfis que ja tinha: a purga e recalculada para as cores novas, a torre de purga e posta num
sitio livre e os pratos sao fatiados outra vez.
"""
import argparse
import json
import os
import sys
import zipfile

sys.dont_write_bytecode = True
import anycubic as K
import adaptar
import pecas


def main():
    ap = argparse.ArgumentParser(description="Cores por peca num projeto Anycubic (MakerWorld to Any)")
    ap.add_argument("projeto")
    ap.add_argument("saida", nargs="?")
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--atribuir", help='ex.: "anel=2;1.3=2;tudo=1"')
    ap.add_argument("--cores", help='ex.: "#FFFFFF;#800020" (vazio = fica a que estava)')
    ap.add_argument("--filamentos", help='perfis por ordem, ex.: "Anycubic PLA;Anycubic PLA Silk"')
    ap.add_argument("--material", help='muda o material de todos, ex.: "PETG"')
    ap.add_argument("--sem-fatiar", dest="fatiar", action="store_false")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    z = zipfile.ZipFile(a.projeto)
    j = json.loads(z.read("Metadata/project_settings.config"))
    ms = z.read("Metadata/model_settings.config").decode("utf-8")
    z.close()
    if not K.impressora_do_projeto(j):
        raise SystemExit("Este projeto nao e de uma impressora Anycubic: adapta-o primeiro com adaptar.py")
    if a.listar or not (a.atribuir or a.cores or a.filamentos or a.material):
        print(f"{K.MODELO}" + (" (com ACE)" if K.MULTICOR else " (sem ACE: uma cor)"))
        print("Filamentos:")
        for i, (n, c) in enumerate(zip(j.get("filament_settings_id", []), j.get("filament_colour", [])), 1):
            print(f"  {i}  {n.split(' @')[0]}  {c}")
        print("Objetos e pecas (o numero da esquerda serve para --atribuir):")
        print("  " + pecas.texto_lista(pecas.le(ms), j.get("filament_colour")).replace("\n", "\n  "))
        return

    destino = os.path.abspath(a.saida or a.projeto)
    rel = adaptar.adapta(adaptar.pedido(original=a.projeto, saida=os.path.dirname(destino), nome=os.path.basename(destino),
                                        substituir=True, atribuir=a.atribuir, cores=a.cores, filamentos=a.filamentos,
                                        material=a.material, fatiar=a.fatiar))
    if a.json:
        print(json.dumps(rel, indent=1, ensure_ascii=False))
    else:
        adaptar.imprime(rel)


if __name__ == "__main__":
    main()
