---
name: any-desfazer
description: "Comando /any-desfazer: repoe a versao anterior de um ficheiro que a MakerWorld to Any substituiu (ha sempre uma copia de seguranca das ultimas 30 alteracoes). Uso: /any-desfazer [ficheiro.3mf]. Feito pela Megatic. EN: undo - restore the previous version of a file the skill replaced."
argument-hint: "[ficheiro.3mf] (sem nada: mostra as copias guardadas)"
disable-model-invocation: true
---

# /any-desfazer - voltar atras

Pedido: `$ARGUMENTS`

1. A skill principal esta na pasta irma desta: `<Base directory desta skill>/../makerworld-to-any`.
   Os scripts estao em `<essa pasta>/scripts/` e correm com `python` (ou `py -3`).
   Script: `desfazer.py`.
2. Sem ficheiro: `desfazer.py --listar` e mostra as copias (numero, data, ficheiro, o que se ia fazer quando foi
   guardada). Pergunta qual repor se houver duvida.
3. Com um ficheiro: `desfazer.py "<ficheiro>"` repoe a copia mais recente desse ficheiro. "A copia 3" ->
   `desfazer.py --copia 3` (o numero da lista).
4. O ficheiro que la estava fica tambem guardado, por isso da para desfazer o desfazer (correr outra vez).
5. Responde numa frase: que ficheiro foi reposto e de quando era a versao.
