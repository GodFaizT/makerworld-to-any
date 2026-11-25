---
name: any-pratos
description: "Comando /any-pratos: ve e arruma os pratos de um projeto Anycubic ja adaptado - mover objetos entre pratos, um objeto por prato, juntar tudo num prato, afastar pecas encostadas, centrar (MakerWorld to Any, Megatic). Uso: /any-pratos <projeto.3mf> [pedido]. EN: arrange the plates of an adapted Anycubic project."
argument-hint: "<projeto.3mf> [ex.: o corpo num prato e a barra noutro | um por prato | afasta 6 mm]"
disable-model-invocation: true
---

# /any-pratos - pratos e arrumacao

Pedido: `$ARGUMENTS`

1. A skill principal esta na pasta irma desta: `<Base directory desta skill>/../makerworld-to-any`.
   Os scripts estao em `<essa pasta>/scripts/` e correm com `python` (ou `py -3`).
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
