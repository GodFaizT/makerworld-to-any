"""Gera os comandos (/kobrax, /kobras1, ... /any-perfil, /any-pratos, ...) em skills/<comando>/SKILL.md.

Cada comando e uma mini-skill que so o utilizador chama (disable-model-invocation) e que encaminha para a skill
principal. Estao todos aqui para se mudarem num sitio so.

    python tools/gera_comandos.py              escreve os ficheiros
    python tools/gera_comandos.py --verificar  falha se algum ficheiro nao corresponder ao que isto gera
"""
import os
import sys

for _f in (sys.stdout, sys.stderr):      # acentos e travessoes tambem quando a saida vai para um ficheiro ou pipe
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(RAIZ, "skills")
PRINCIPAL = "makerworld-to-any"

IMPRESSORAS = [  # (comando, impressora para --impressora, nome completo)
    ("kobrax", "Kobra X", "Anycubic Kobra X"),
    ("kobra4", "Kobra 4", "Anycubic Kobra 4"),
    ("kobras1", "Kobra S1", "Anycubic Kobra S1"),
    ("kobras1max", "Kobra S1 Max", "Anycubic Kobra S1 Max"),
    ("kobra3", "Kobra 3", "Anycubic Kobra 3"),
    ("kobra3max", "Kobra 3 Max", "Anycubic Kobra 3 Max"),
]

CARREGA = """1. Carrega a skill **makerworld-to-any** com a ferramenta Skill (se vier de um plugin chama-se
   `makerworld-to-any:makerworld-to-any`) e segue as instrucoes dela."""

IRMA = """1. A skill principal esta na pasta irma desta: `<Base directory desta skill>/../makerworld-to-any`.
   Os scripts estao em `<essa pasta>/scripts/` e correm com `python` (ou `py -3`)."""

PEDIDOS = """tamanho ("com 10 cm" -> `escalar.py` depois de adaptar), bico ("bico 0.6" -> `--bico 0.6`), material
   ("em PETG", "em PLA Silk" -> `--material PETG`), cor ("dourado" -> `--cores "#D4AF37"`), cores por peca ("o nome a
   azul e o resto a branco" -> `cores.py --atribuir` depois de adaptar), pratos ("o corpo num prato e a barra noutro"
   -> `pratos.py --mover` depois de adaptar), perfis ("com os meus perfis" -> `--perfis meus`), perfil de impressao
   ("0.16 high quality" -> `--processo`), "guarda o g-code" -> `--gcode <pasta>`, "sem camadas variaveis" ->
   `--sem-camadas-variaveis`."""

FIM_ADAPTAR = """4. Se o caminho for uma **pasta**, adapta um a um todos os `.3mf` dessa pasta (sem subpastas), menos os que ja sao
   adaptados (acabam em ` - <impressora>.3mf`).
5. Se nao houver caminho, ou o ficheiro nao existir, ve so a pasta indicada ou a pasta atual (nunca o disco todo):
   se houver um unico `.3mf` parecido usa-o; senao pergunta qual.
6. No fim responde como a skill manda: onde ficou, tempo e gramas de cada prato, cores, custo (se houver precos) e
   avisos."""


def impressora(cmd, imp, bonito):
    return f"""---
name: {cmd}
description: "Comando /{cmd}: adapta um 3MF do MakerWorld / Bambu Studio para a {bonito} (MakerWorld to Any, Megatic). Uso: /{cmd} <ficheiro.3mf ou pasta> [pedidos extra]. EN: adapt a MakerWorld / Bambu Studio 3MF for the {bonito}."
argument-hint: "<ficheiro.3mf ou pasta> [ex.: com 10 cm, bico 0.6, em PETG, dourado]"
disable-model-invocation: true
---

# /{cmd} - adaptar para a {bonito}

Pedido: `$ARGUMENTS`

{CARREGA}
2. Impressora de destino: **{bonito}** -> `adaptar.py "<ficheiro>" --impressora "{imp}"` (mais as opcoes que os
   pedidos pedirem).
3. O pedido comeca pelo caminho do ficheiro `.3mf` (com ou sem aspas, pode ter espacos); o resto sao pedidos extra:
   {PEDIDOS}
{FIM_ADAPTAR}
"""


COMANDOS = {c: impressora(c, i, b) for c, i, b in IMPRESSORAS}

COMANDOS["anycubic"] = f"""---
name: anycubic
description: "Comando /anycubic: adapta um 3MF do MakerWorld / Bambu Studio para qualquer impressora Anycubic (MakerWorld to Any, Megatic). Uso: /anycubic <impressora> <ficheiro.3mf ou pasta> [pedidos extra]. EN: adapt a MakerWorld / Bambu Studio 3MF for any Anycubic printer."
argument-hint: "<impressora, ex. Kobra 2 Neo> <ficheiro.3mf ou pasta> [pedidos extra]"
disable-model-invocation: true
---

# /anycubic - adaptar para qualquer impressora Anycubic

Pedido: `$ARGUMENTS`

{CARREGA}
2. O pedido comeca pela impressora (ex. "Kobra 2 Neo", "Kobra 3 V2", "S1 Max", "Kobra X 0.6") e depois o caminho do
   `.3mf` ou de uma pasta. Passa a impressora em `adaptar.py --impressora "..."`. Se nao reconheceres a impressora,
   corre `adaptar.py --listar-impressoras` e pergunta qual.
3. O resto sao pedidos extra:
   {PEDIDOS}
{FIM_ADAPTAR}
"""

COMANDOS["any-perfil"] = f"""---
name: any-perfil
description: "Comando /any-perfil: preferencias da MakerWorld to Any - perfis por omissao (os da Anycubic ou os teus), impressora, pasta dos adaptados e dos originais, precos para o custo de cada trabalho; sem nada mostra o que esta escolhido. Feito pela Megatic. EN: MakerWorld to Any preferences (default profiles, printer, folders, prices)."
argument-hint: "[meus | anycubic] [impressora <nome>] [pasta dos adaptados / originais] [precos]"
disable-model-invocation: true
---

# /any-perfil - preferencias

Pedido: `$ARGUMENTS`

{IRMA}
   Script: `perfil.py`.
2. Traduz o pedido para o script:
   - nada -> `perfil.py` (so mostra);
   - "meus", "os meus", "minhas definicoes", "os meus perfis" -> `perfil.py meus`;
   - "anycubic", "sistema", "oficiais", "default", "de origem" -> `perfil.py anycubic`;
   - "impressora Kobra S1", "kobra 3 max", "S1" -> `--impressora "Kobra S1"` (pode vir junto: `perfil.py meus --impressora "Kobra S1"`);
   - "guarda os adaptados em D:\\Impressoes\\Adaptado" -> `--saida "D:\\Impressoes\\Adaptado"` (com `{{impressora}}` no caminho
     fica uma pasta por impressora);
   - "os originais vao para D:\\Impressoes\\Originais" -> `--originais "D:\\Impressoes\\Originais"`;
   - "PLA a 18 euros o quilo, PETG a 20, a maquina a 40 centimos a hora" -> `--preco-kg "PLA=18;PETG=20" --preco-hora 0.40`
     (`*=22` vale para os materiais sem preco proprio);
   - "esquece os precos / a pasta" -> `--apagar precos --apagar preco_hora` / `--apagar saida`.
3. Mostra o resultado curto: perfis por omissao, impressora, pastas, precos, e os perfis do utilizador que servem para
   essa impressora (os marcados com "<- para a tua impressora").
4. Explica numa frase o que mudou: com "meus", em cada adaptacao usa o perfil do utilizador baseado no perfil
   escolhido, quando existe; com pasta dos adaptados, tudo o que se adapta vai para la; com pasta dos originais, um
   original largado na pasta-mae dessa pasta e movido para la depois de adaptado; com precos, o relatorio traz o
   custo estimado (filamento + horas de maquina). Os comandos `/kobrax`, `/kobras1`... continuam a escolher a
   impressora deles; a impressora por omissao vale para pedidos sem impressora.
5. Se o utilizador nao tem perfis guardados e escolheu "meus": dizer que pode criar um no Anycubic Slicer Next
   (mudar um perfil e guarda-lo com outro nome) e que entretanto usa os da Anycubic.
"""

COMANDOS["any-pratos"] = f"""---
name: any-pratos
description: "Comando /any-pratos: ve e arruma os pratos de um projeto Anycubic ja adaptado - mover objetos entre pratos, um objeto por prato, juntar tudo num prato, afastar pecas encostadas, centrar (MakerWorld to Any, Megatic). Uso: /any-pratos <projeto.3mf> [pedido]. EN: arrange the plates of an adapted Anycubic project."
argument-hint: "<projeto.3mf> [ex.: o corpo num prato e a barra noutro | um por prato | afasta 6 mm]"
disable-model-invocation: true
---

# /any-pratos - pratos e arrumacao

Pedido: `$ARGUMENTS`

{IRMA}
   Script: `pratos.py`.
2. O pedido comeca pelo caminho de um projeto **ja adaptado** para uma Anycubic. Se for um original do Bambu Studio,
   adapta-o primeiro com a skill principal e trabalha no adaptado.
3. Sem mais pedido, ou para saber os nomes: `pratos.py "<projeto>" --listar` (pratos, objetos numerados, folgas entre
   pecas e avisos).
4. Traduz o pedido:
   - "o X num prato e o Y noutro", "poe o X no prato 2" -> `--mover "X=1;Y=2"` (alvo = parte do nome, o numero da
     lista, ou "prato N" para tudo o que esta nesse prato);
   - "um por prato", "cada peca no seu prato" -> `--um-por-prato`;
   - "tudo no mesmo prato", "junta" -> `--juntar`;
   - "afasta as pecas", "estao coladas" -> `--afastar 6` (folga em mm; `--prato N` para um prato so);
   - "centra" -> `--centrar`;
   - "fica so com os pratos 3 e 4" (apagar o resto) -> `separar_pratos.py "<entrada>" "<saida>" 3,4`.
   Junta sempre `--fatiar`, para dar tempo e gramas de cada prato.
5. Sem ficheiro de saida o script altera o proprio projeto e guarda uma copia (`/any-desfazer` repoe). Se o
   utilizador quer manter o que tem, da um segundo caminho como saida.
6. Responde curto: o que ficou em cada prato, tempo e gramas de cada um, e os avisos (pecas fora da mesa, pecas
   encostadas, torre de purga).
"""

COMANDOS["any-cores"] = f"""---
name: any-cores
description: "Comando /any-cores: cores e filamentos de um projeto Anycubic ja adaptado - que filamento tem cada objeto e cada peca, por pecas noutra cor, juntar uma cor nova, mudar cores ou o material (MakerWorld to Any, Megatic). Uso: /any-cores <projeto.3mf> [pedido]. EN: per-part colours and filaments of an adapted Anycubic project."
argument-hint: "<projeto.3mf> [ex.: o nome a azul e o resto a branco | filamento 2 em bordo | em PETG]"
disable-model-invocation: true
---

# /any-cores - cores por peca

Pedido: `$ARGUMENTS`

{IRMA}
   Script: `cores.py`.
2. O pedido comeca pelo caminho de um projeto **ja adaptado** para uma Anycubic. Se for um original do Bambu Studio,
   adapta-o primeiro com a skill principal (as cores tambem se podem pedir logo ai, com `--atribuir` e `--cores`).
3. Comeca por `cores.py "<projeto>" --listar`: mostra os filamentos (numero, perfil, cor) e os objetos e pecas com o
   numero que serve de alvo (`2` = objeto 2, `1.3` = peca 3 do objeto 1).
4. Traduz o pedido:
   - "o X a azul", "a peca Y no filamento 2" -> `--atribuir "X=2"` (alvo = `tudo`, numero do objeto, `objeto.peca`, ou
     parte do nome). Um numero de filamento que ainda nao existe cria um filamento novo: da-lhe a cor em `--cores`;
   - cores -> `--cores "#FFFFFF;#232C7C"`: a posicao e o numero do filamento da lista (vazio = fica a que estava:
     `";#800020"` muda so o 2; a cor de um filamento novo 3 vai na posicao 3: `";;#232C7C"`). O utilizador diz nomes
     de cores: traduz para hexadecimal (branco #FFFFFF, preto #000000, bordo #800020, azul escuro #232C7C, dourado
     #D4AF37...);
   - "em PETG", "em PLA Silk" -> `--material PETG`; perfis exatos -> `--filamentos "Anycubic PLA;Anycubic PLA Silk"`.
5. Sem ficheiro de saida altera o proprio projeto e guarda uma copia (`/any-desfazer` repoe). O projeto volta a
   passar pelo Anycubic com os perfis que ja tinha: a purga e recalculada para as cores novas, a torre de purga e
   posta num sitio livre e os pratos sao fatiados outra vez. Se o relatorio avisar que g-code ou limites da maquina
   do projeto nao passaram, pergunta ao utilizador se foi ele que os afinou; so entao repete com `--manter-gcode`.
6. Responde curto: que cor vai em que ranhura da ACE (os numeros finais, das linhas `filamento N:` do relatorio: um
   filamento que fique sem pecas sai e os seguintes descem um numero), o que mudou de filamento, tempo e gramas por
   prato (com as gramas de cada cor) e avisos. Mais de 4 cores nao cabem numa ACE; impressoras sem ACE so imprimem
   uma cor.
"""

COMANDOS["any-desfazer"] = f"""---
name: any-desfazer
description: "Comando /any-desfazer: repoe a versao anterior de um ficheiro que a MakerWorld to Any substituiu (ha sempre uma copia de seguranca das ultimas 30 alteracoes). Uso: /any-desfazer [ficheiro.3mf]. Feito pela Megatic. EN: undo - restore the previous version of a file the skill replaced."
argument-hint: "[ficheiro.3mf] (sem nada: mostra as copias guardadas)"
disable-model-invocation: true
---

# /any-desfazer - voltar atras

Pedido: `$ARGUMENTS`

{IRMA}
   Script: `desfazer.py`.
2. Sem ficheiro: `desfazer.py --listar` e mostra as copias (numero, data, ficheiro, o que se ia fazer quando foi
   guardada). Pergunta qual repor se houver duvida.
3. Com um ficheiro: `desfazer.py "<ficheiro>"` repoe a copia mais recente desse ficheiro. "A copia 3" ->
   `desfazer.py --copia 3` (o numero da lista).
4. O ficheiro que la estava fica tambem guardado, por isso da para desfazer o desfazer (correr outra vez).
5. Responde numa frase: que ficheiro foi reposto e de quando era a versao.
"""

COMANDOS["any-diagnostico"] = f"""---
name: any-diagnostico
description: "Comando /any-diagnostico: verifica a instalacao da MakerWorld to Any (Python, Anycubic Slicer Next e a sua versao, perfis, preferencias) e, com 'teste', faz um teste completo com um projeto de exemplo. Feito pela Megatic. EN: check the installation and run an end-to-end self-test."
argument-hint: "[teste] [impressora <nome>]"
disable-model-invocation: true
---

# /any-diagnostico - esta tudo a funcionar?

Pedido: `$ARGUMENTS`

{IRMA}
   Script: `diagnostico.py`.
2. Sem nada: `diagnostico.py` (verificacoes rapidas). Com "teste", "testa tudo", "completo": `diagnostico.py --teste`
   (adapta, muda cores, junta pratos, muda o tamanho e fatia um projeto de exemplo numa pasta temporaria; demora
   menos de um minuto e nao toca nos ficheiros do utilizador). Com uma impressora: `--impressora "Kobra S1"`.
3. Responde curto: o que esta bem numa linha, e cada AVISO ou FALHA com o que fazer:
   - sem Anycubic Slicer Next -> instalar, ou definir `ANYCUBIC_SLICER` com o caminho do executavel;
   - versao do slicer diferente da testada -> correr o teste; se o teste passa esta tudo bem;
   - sem numpy -> `pip install numpy` (folgas reais entre pecas e afastar pecas); sem matplotlib -> so faz falta para
     `medir.py --imagem`;
   - sem os comandos ao lado da skill -> reinstalar (`npx github:GodFaizT/makerworld-to-any`) ou `/any-update`.
4. Se o teste falhar: mostra as linhas FALHA tal como sairam e sugere `/any-update`; se continuar, abrir um pedido
   em https://github.com/GodFaizT/makerworld-to-any/issues com essas linhas.
"""

COMANDOS["any-update"] = f"""---
name: any-update
description: "Comando /any-update: atualiza a MakerWorld to Any (skill e comandos /kobrax, /kobras1, ...) para a ultima versao publicada no GitHub. Feito pela Megatic. EN: update the skill and its commands to the latest release."
argument-hint: "[--verificar]"
disable-model-invocation: true
---

# /any-update - atualizar a MakerWorld to Any

Pedido: `$ARGUMENTS`

{IRMA}
   Corre: `atualizar.py $ARGUMENTS`.
   - Instalada como plugin: o script usa `claude plugin update`; se o `claude` nao estiver no PATH, diz ao
     utilizador para correr `/plugin marketplace update makerworld-to-any` e
     `/plugin update makerworld-to-any@makerworld-to-any`.
   - Instalada como skill: o script descarrega o ZIP da ultima release do GitHub (GodFaizT/makerworld-to-any) e
     substitui so as pastas da skill e dos comandos.
2. Responde curto: versao que tinha -> versao nova e as novidades principais (ou que ja tem a ultima).
3. Se atualizou: lembrar de abrir uma sessao nova do Claude Code (as skills carregam no arranque) e sugerir
   `/any-diagnostico teste` para confirmar que ficou tudo a funcionar.
4. Se falhar (sem internet, GitHub em baixo): dizer o erro e sugerir `npx github:GodFaizT/makerworld-to-any`.
"""


def caminho(cmd):
    return os.path.join(SKILLS, cmd, "SKILL.md")


def atual(cmd):
    try:
        with open(caminho(cmd), encoding="utf-8", newline="") as f:
            return f.read()
    except OSError:
        return None


def diferencas():
    """Comandos cujo ficheiro nao corresponde ao gerado, e pastas de skills/ que isto nao conhece."""
    mudados = [c for c, t in COMANDOS.items() if atual(c) != t]
    estranhos = [d for d in sorted(os.listdir(SKILLS))
                 if os.path.isdir(os.path.join(SKILLS, d)) and d != PRINCIPAL and d not in COMANDOS]
    return mudados, estranhos


def main():
    mudados, estranhos = diferencas()
    if "--verificar" in sys.argv:
        for c in mudados:
            print(f"desatualizado: skills/{c}/SKILL.md (corre python tools/gera_comandos.py)")
        for d in estranhos:
            print(f"pasta desconhecida: skills/{d} (falta em tools/gera_comandos.py?)")
        return 1 if mudados or estranhos else 0
    for c in mudados:
        os.makedirs(os.path.dirname(caminho(c)), exist_ok=True)
        with open(caminho(c), "w", encoding="utf-8", newline="\n") as f:
            f.write(COMANDOS[c])
    print(f"{len(COMANDOS)} comandos: " + " ".join("/" + c for c in COMANDOS))
    print("escritos: " + (", ".join(mudados) if mudados else "nenhum (ja estavam atualizados)"))
    for d in estranhos:
        print(f"AVISO: pasta desconhecida skills/{d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
