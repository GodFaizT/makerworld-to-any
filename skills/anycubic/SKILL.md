---
name: anycubic
description: "Comando /anycubic: adapta um 3MF do MakerWorld / Bambu Studio para qualquer impressora Anycubic (MakerWorld to Any, Megatic). Uso: /anycubic <impressora> <ficheiro.3mf ou pasta> [pedidos extra]"
argument-hint: "<impressora, ex. Kobra 2 Neo> <ficheiro.3mf ou pasta> [pedidos extra]"
disable-model-invocation: true
---

# /anycubic - adaptar para qualquer impressora Anycubic

Pedido: `$ARGUMENTS`

1. Carrega a skill **makerworld-to-any** com a ferramenta Skill (se vier de um plugin chama-se
   `makerworld-to-any:makerworld-to-any`) e segue as instrucoes dela.
2. O pedido comeca pela impressora (ex. "Kobra 2 Neo", "Kobra 3 V2", "S1 Max", "Kobra X 0.6") e depois o caminho do
   `.3mf` ou de uma pasta. Passa a impressora em `adaptar.py --impressora "..."`. Se nao reconheceres a impressora,
   corre `adaptar.py --listar-impressoras` e pergunta qual.
3. O resto sao pedidos extra: tamanho -> `escalar.py` depois de adaptar; bico -> `--bico`; material ("em PETG")
   -> `--material`; cor -> `--cores`; "com os meus perfis" -> `--perfis meus`; perfil de impressao -> `--processo`.
4. Se o caminho for uma **pasta**, adapta um a um todos os `.3mf` dessa pasta (sem subpastas), menos os que ja sao
   adaptados (acabam em ` - <impressora>.3mf`).
5. Se nao houver caminho, ou o ficheiro nao existir, ve so a pasta indicada ou a pasta atual (nunca o disco todo):
   se houver um unico `.3mf` parecido usa-o; senao pergunta qual.
6. No fim responde como a skill manda: onde ficou, tempo e gramas de cada prato, cores e avisos.
