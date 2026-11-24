---
name: any-perfil
description: "Comando /any-perfil: escolhe os perfis por omissao da MakerWorld to Any (os da Anycubic ou os teus do Anycubic Slicer Next) e a impressora por omissao; sem nada mostra o que esta escolhido e os teus perfis. Feito pela Megatic."
argument-hint: "[meus | anycubic] [impressora <nome>]"
disable-model-invocation: true
---

# /any-perfil - perfis e impressora por omissao

Pedido: `$ARGUMENTS`

1. A skill principal esta na pasta irma desta: `<Base directory desta skill>/../makerworld-to-any`.
   O script e `python "<essa pasta>/scripts/perfil.py"` (ou `py -3`).
2. Traduz o pedido para o script:
   - nada -> `perfil.py` (so mostra);
   - "meus", "os meus", "minhas definicoes", "os meus perfis" -> `perfil.py meus`;
   - "anycubic", "sistema", "oficiais", "default", "de origem" -> `perfil.py anycubic`;
   - "impressora Kobra S1", "kobra 3 max", "S1" -> `--impressora "Kobra S1"` (pode vir junto: `perfil.py meus --impressora "Kobra S1"`).
3. Mostra o resultado curto: que perfis ficam por omissao, qual e a impressora, e os perfis do utilizador que servem
   para essa impressora (os marcados com "<- para a tua impressora").
4. Explica numa frase: com "meus", em cada adaptacao usa o perfil do utilizador baseado no perfil escolhido, quando
   existe; senao o da Anycubic. Os comandos `/kobrax`, `/kobras1`... continuam a escolher a impressora deles; esta
   impressora por omissao vale para pedidos sem impressora ("adapta este ficheiro").
5. Se o utilizador nao tem perfis guardados e escolheu "meus": dizer que pode criar um no Anycubic Slicer Next
   (mudar um perfil e guarda-lo com outro nome) e que entretanto usa os da Anycubic.
