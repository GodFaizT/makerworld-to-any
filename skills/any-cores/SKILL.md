---
name: any-cores
description: "Comando /any-cores: cores e filamentos de um projeto Anycubic ja adaptado - que filamento tem cada objeto e cada peca, por pecas noutra cor, juntar uma cor nova, mudar cores ou o material (MakerWorld to Any, Megatic). Uso: /any-cores <projeto.3mf> [pedido]. EN: per-part colours and filaments of an adapted Anycubic project."
argument-hint: "<projeto.3mf> [ex.: o nome a azul e o resto a branco | filamento 2 em bordo | em PETG]"
disable-model-invocation: true
---

# /any-cores - cores por peca

Pedido: `$ARGUMENTS`

1. A skill principal esta na pasta irma desta: `<Base directory desta skill>/../makerworld-to-any`.
   Os scripts estao em `<essa pasta>/scripts/` e correm com `python` (ou `py -3`).
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
   posta num sitio livre e os pratos sao fatiados outra vez.
6. Responde curto: que cor vai em que ranhura da ACE (os numeros finais, das linhas `filamento N:` do relatorio: um
   filamento que fique sem pecas sai e os seguintes descem um numero), o que mudou de filamento, tempo e gramas por
   prato (com as gramas de cada cor) e avisos. Mais de 4 cores nao cabem numa ACE; impressoras sem ACE so imprimem
   uma cor.
