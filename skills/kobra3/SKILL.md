---
name: kobra3
description: "Comando /kobra3: adapta um 3MF do MakerWorld / Bambu Studio para a Anycubic Kobra 3 (MakerWorld to Any, Megatic). Uso: /kobra3 <ficheiro.3mf ou pasta> [pedidos extra]"
argument-hint: "<ficheiro.3mf ou pasta> [ex.: com 10 cm, bico 0.6, PLA Silk dourado]"
disable-model-invocation: true
---

# /kobra3 - adaptar para a Anycubic Kobra 3

Pedido: `$ARGUMENTS`

1. Carrega a skill **makerworld-to-any** com a ferramenta Skill (se vier de um plugin chama-se
   `makerworld-to-any:makerworld-to-any`) e segue as instrucoes dela.
2. Impressora de destino: **Anycubic Kobra 3** -> `adaptar.py "<ficheiro>" --impressora "Kobra 3"` (mais as opcoes que os
   pedidos pedirem).
3. O pedido comeca pelo caminho do ficheiro `.3mf` (com ou sem aspas, pode ter espacos); o resto sao pedidos extra:
   tamanho ("com 10 cm" -> `escalar.py` depois de adaptar), bico ("bico 0.6" -> `--bico 0.6`), material
   ("em PETG", "em PLA Silk" -> `--material PETG`), cor ("dourado" -> `--cores "#D4AF37"`), perfis ("com os meus
   perfis" -> `--perfis meus`), perfil de impressao ("0.16 high quality" -> `--processo`), etc.
4. Se o caminho for uma **pasta**, adapta um a um todos os `.3mf` dessa pasta (sem subpastas), menos os que ja sao
   adaptados (acabam em ` - <impressora>.3mf`).
5. Se nao houver caminho, ou o ficheiro nao existir, ve so a pasta indicada ou a pasta atual (nunca o disco todo):
   se houver um unico `.3mf` parecido usa-o; senao pergunta qual.
6. No fim responde como a skill manda: onde ficou, tempo e gramas de cada prato, cores e avisos.
