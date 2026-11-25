# Novidades

## 2.0.0 - 2026-11-25 · pratos, cores por peça, desfazer e diagnóstico

Projetos já adaptados passam a poder ser trabalhados sem voltar ao original, e a skill ficou testada de ponta a ponta.

**Comandos novos**
- `/any-pratos` — ver o que está em cada prato, mover objetos entre pratos, um objeto por prato, juntar tudo,
  afastar peças encostadas e centrar.
- `/any-cores` — ver o filamento de cada objeto e de cada peça, pôr peças noutra cor, juntar uma cor nova, mudar
  cores ou o material. A purga é recalculada para as cores novas.
- `/any-desfazer` — repor a versão anterior de um ficheiro. Os scripts guardam sempre uma cópia antes de
  substituírem um ficheiro (as últimas 30).
- `/any-diagnostico` — verifica Python, Anycubic Slicer Next (e a versão), perfis e preferências; com `teste` adapta,
  muda cores, arruma pratos, muda o tamanho e fatia um projeto de exemplo em menos de um minuto.

**Melhor**
- Folga real entre peças, pela forma das peças e não pelas caixas: avisa de peças a menos de 2 mm e a torre de
  purga vai para um sítio mesmo livre.
- Purga entre cores recalculada quando as cores mudam (a linha de comandos do Anycubic não o faz); fica a do autor
  onde as cores são as dele.
- Relatório mais claro: o que o autor mudou de propósito, o que vinha do perfil dele, e o que não passou e porquê.
- As velocidades do autor nunca passam acima das do perfil da impressora, em todas as impressoras.
- Alturas de camada variáveis: o relatório diz a altura média real; `--sem-camadas-variaveis` ignora-as. Com
  suportes em árvore orgânica (que o Anycubic recusa com camadas variáveis) os suportes passam a árvore híbrida.
- `/any-perfil` guarda também a pasta dos adaptados, a pasta dos originais e os preços (por kg de cada material e
  por hora de máquina): o relatório passa a trazer o custo estimado de cada trabalho.
- `--gcode PASTA` guarda o g-code já fatiado de cada prato; `--json` dá o relatório para programas.
- `medir.py --imagem` desenha os pratos vistos de cima.
- Nomes de objetos em chinês, com emoji, etc. já não rebentam os scripts no Windows.
- Os erros conhecidos do Anycubic vêm com uma dica do que fazer.
- Ao mudar as cores ou o material de um projeto já adaptado, o que afinaste à mão no Anycubic (acelerações,
  temperaturas, g-code…) fica como estava.
- Scripts de pós-processamento que venham dentro de um projeto nunca passam para o adaptado nem são executados.
- Trocas de cor por camada e alturas de camada variáveis acompanham as peças quando mudam de prato ou de tamanho.

**Para quem mexe no código**
- Testes automáticos (`python -m unittest discover -s tests -t tests`) com perfis falsos, sem precisar do slicer;
  os testes de ponta a ponta correm quando o Anycubic Slicer Next está instalado.
- Tudo o que é preciso para publicar está no repositório: `tools/publica.py` (versão num sítio só, ZIPs, release),
  `tools/gera_comandos.py`, `tools/verifica.py`, `instalador/`.
- README em inglês (`README.en.md`) e imagens geradas a partir de uma adaptação real (`tools/gera_docs.py`).

## 1.6.0 - 2026-11-24
- Cada material com o seu perfil (PLA e variantes, PETG, ABS, ASA, PC, PA, TPU, fibras...) e `--material`.
- Guia de perfis no README.

## 1.5.0 - 2026-11-24
- Comando `/any-perfil`: perfis e impressora por omissão.

## 1.4.0 a 1.4.2 - 2026-11-24
- Perfis do utilizador (`--perfis meus`) e comando de atualização, que passou a chamar-se `/any-update`.

## 1.3.0 - 2026-11-24
- Comandos `/kobrax`, `/kobra4`, `/kobras1`, `/kobras1max`, `/kobra3`, `/kobra3max` e `/anycubic`.

## 1.2.0 - 2026-11-24
- Várias impressoras Anycubic (todas as que o Anycubic Slicer Next traz).

## 1.1.0 - 2026-11-24
- Novo nome: MakerWorld to Any.

## 1.0.0 - 2026-11-24
- Primeira versão: projetos Bambu Lab / MakerWorld para a Anycubic Kobra X.
