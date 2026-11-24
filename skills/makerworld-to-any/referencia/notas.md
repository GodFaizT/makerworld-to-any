# Notas tecnicas (Anycubic Slicer Next 2.0.0.3, linha de comandos)

O `adaptar.py` ja trata tudo o que esta marcado com (auto).

## Linha de comandos do Anycubic

- Exportar projeto: `AnycubicSlicerNext.exe --arrange 0 --load-settings "maquina.json;processo.json"
  --load-filaments "f1.json;f2.json" --export-3mf saida.3mf --outputdir <pasta> <entrada.3mf|.stl>`.
  Fatiar: `--slice 0 --outputdir <pasta> <projeto.3mf>` (todos os pratos -> `plate_N.gcode`).
- Os caminhos tem de ser do Windows (`C:\...`); em bash, `cygpath -w`. Um `/c/...` dentro da lista com `;` da
  "can not find setting file" (codigo 127).
- Escreve certificados/chaves da impressora (ficheiros com nome hexadecimal) na pasta de trabalho -> correr numa
  pasta temporaria (auto).
- **Rebenta** (segfault) com nomes de prato (`plater_name`) nao vazios, mesmo ASCII (auto: ficam vazios).
- **Rebenta** com uma malha a meio abaixo de z=0. O Bambu guarda malhas centradas (z -h/2..h/2): so importa se se
  extrair a malha para STL; a partir do 3MF original nao acontece.
- Recusa ("Loading of a model file failed") um STL encostado a origem; no meio da mesa aceita (auto).
- Passa os pratos para a mesa de 260: +2,+2 de uma mesa de 256; +40 da A1 mini (180). Pratos de 312 em 312
  (colunas = arredondar para cima de raiz(n)); na vista de montagem o passo e 307.2.
- Escreve mal `different_settings_to_system`; tem de ser `[processo, "" por filamento..., "machine_end_gcode"]` (auto).
- Com menos ficheiros de filamento do que o projeto tinha, so substitui os primeiros e deixa os restantes como
  perfis Bambu (temperaturas erradas, High Flow a 220 C...) -> cortar todas as listas por filamento (auto). Listas
  `*_group` sao [processo, filamentos..., impressora]. A matriz de purga nao e recalculada: e a do original na ordem
  original -> sub-matriz dos filamentos usados (auto).
- No Bambu 2.x, `wall_filament`/`sparse_infill_filament`/`solid_infill_filament` do perfil valem 1 por omissao (=
  filamento do objeto): nao contam como "usados" (auto).
- Desliga a torre de purga (`enable_prime_tower` 0) mesmo com 2 cores; o perfil da Kobra X tem 1 (auto, e posicao
  livre por prato). Pegada medida: x de X-6 a X+largura+1, y de Y-7.5 a Y+20 com 2 cores.
- A matriz `matrix` das pecas no `model_settings` sai "dobrada" (escala 1.21 para 1.1): inofensivo, o g-code sai certo.
- Diferencas de normalizacao que aparecem sempre (internal_solid_infill_pattern rectilinear, wall_direction ccw,
  ironing_angle 0) sao do proprio Anycubic.

## Perfis

- Perfis de sistema: `%APPDATA%\AnycubicSlicerNext\system\Anycubic\{machine,process,filament}\*.json` com heranca
  por `inherits` (auto).
- Kobra X 0.20mm Standard ~ Bambu A1 0.20mm Standard (2 paredes, 15 % grelha, tree(auto) a 30 graus). A Kobra X vem
  com suportes desligados e so na mesa.
- O autor muda definicoes em relacao ao perfil base dele -> usar o perfil da Kobra X com o **mesmo nome do perfil
  base** e a altura de camada dele como mudanca (auto). Ex.: um perfil "optimised" a 0.12 feito sobre o 0.20 Standard.
- Alturas de camada variaveis (`Metadata/layer_heights_profile.txt`) mandam sobre `layer_height` (tambem no Bambu).
  Um perfil "0.12" com o perfil variavel do autor a 0.2 imprime a 0.2. Um 0.12 a serio precisa do perfil limitado a
  0.12.
- Anycubic 2.0.0.3: estilos de suporte default/tree_slim/tree_strong/tree_hybrid (sem tree_organic) (auto).
  `zig-zag` do Bambu -> `zigzag` (auto). Fuzzy skin pintado (`paint_fuzzy_skin`) e suportado.
- Fim de impressao: o de fabrica desliga com o bico pousado na peca (fio/bolinha no topo) -> levanta 5 mm e vai a
  X250 Y250 (auto).

## Pecas com texto (trabalho a mao)

- **Pendentes/enfeites OpenSCAD** (MakerLab ou OpenSCAD do autor): o texto e uma extrusao plana. Para trocar o nome:
  cortar a malha em 2D (ex. manifold3d), descobrir a fonte e o tamanho do texto original, gerar o novo texto com a
  mesma fonte e o mesmo `offset`, extrudir e substituir a malha da peca do texto no 3MF original, e so depois correr
  o `adaptar.py`.
- Pontos dos i/j e acentos ficam muitas vezes soltos (pecas flutuantes): ligar a propria haste com um "pescoco" de
  ~1 mm (e confirmar que nao liga a letra do lado), ou baixar o acento ate tocar na letra.
- Pecas que rodam (anel dentro de um aro): confirmar em varias alturas que o anel com o texto e uma peca e o aro
  outra, para continuar a rodar.
- Nomes escritos sem acento: perguntar se levam (Celia vs Célia).
