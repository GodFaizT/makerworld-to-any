# Notas tecnicas (Anycubic Slicer Next 2.0.0.3, linha de comandos)

MakerWorld to Any - Megatic (https://megatic.pt).

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
- Centra os pratos na mesa da impressora de destino (Kobra X: +2,+2 de uma mesa de 256; +40 da A1 mini de 180).
  Pratos separados por mesa x 1.2 (Kobra X 312, S1 300, Kobra 3 306, 3 Max 511.2 x 504); colunas = arredondar para
  cima de raiz(n). A vista de montagem (assemble) e so visual.
- Escreve mal `different_settings_to_system`; tem de ser `[processo, "" por filamento..., "machine_end_gcode"]` (auto).
- Com menos ficheiros de filamento do que o projeto tinha, so substitui os primeiros e deixa os restantes como
  perfis Bambu (temperaturas erradas, High Flow a 220 C...) -> cortar todas as listas por filamento (auto). Listas
  `*_group` sao [processo, filamentos..., impressora]. A matriz de purga nao e recalculada: e a do original na ordem
  original -> sub-matriz dos filamentos usados (auto).
- No Bambu 2.x, `wall_filament`/`sparse_infill_filament`/`solid_infill_filament` do perfil valem 1 por omissao (=
  filamento do objeto): nao contam como "usados" (auto).
- Desliga a torre de purga (`enable_prime_tower` 0) mesmo com 2 cores; os perfis com ACE tem 1 (auto, e posicao
  livre por prato). Pegada medida numa Kobra X: x de X-6 a X+largura+1, y de Y-7.5 a Y+20 com 2 cores.
- A matriz `matrix` das pecas no `model_settings` sai "dobrada" (escala 1.21 para 1.1): inofensivo, o g-code sai certo.
- Diferencas de normalizacao que aparecem sempre (internal_solid_infill_pattern rectilinear, wall_direction ccw,
  ironing_angle 0) sao do proprio Anycubic.

## Impressoras

- Maquinas: `%APPDATA%\AnycubicSlicerNext\system\Anycubic\machine\*.json`, nome `Anycubic <modelo> <bico> nozzle`;
  processos e filamentos chamam-se `<nome> @<maquina>` (ou tem a maquina em `compatible_printers`) (auto).
- Mesa: `printable_area` + `printable_height` (Kobra 1/2/2 Neo/2 Pro 220; Kobra 3 255; S1 250; Kobra X e 4 260;
  1 Plus 300; 2 Plus 320; S1 Max 350; 1 Max 400; 2 Max 426; 3 Max 426 x 420 x 501).
- ACE (varias cores): as maquinas com `change_filament_gcode` (Kobra X, 4, 3, 3 V2, 3 Max, S1, S1 Max). As Kobra 1
  e 2 nao tem (aviso se o projeto tem varias cores).
- Fim de impressao de fabrica sem levantar o bico: Kobra X, Kobra 4, S1 Max -> junta-se o levantamento (auto).
  S1, Kobra 3 e Kobra 1/2 ja levantam e ficam como estao.
- Velocidades: impressoras com `machine_max_speed_x` >= 450 aceitam as do autor; nas lentas (Kobra 1/1 Plus/1 Max,
  Kobra 2/2 Neo) so passam as mais baixas que as do perfil (auto).
- Filamentos por impressora variam muito (Kobra 1 so tem Generic PLA/PETG/ABS; Kobra 2 Neo so Anycubic PLA/PETG):
  usa-se o mais proximo, Anycubic primeiro, depois Generic (auto).

## Perfis

- Perfis de sistema: `%APPDATA%\AnycubicSlicerNext\system\Anycubic\{machine,process,filament}\*.json` com heranca
  por `inherits` (auto).
- Kobra X 0.20mm Standard ~ Bambu A1 0.20mm Standard (2 paredes, 15 % grelha, tree(auto) a 30 graus). Os perfis
  Anycubic vem com suportes desligados e so na mesa.
- O autor muda definicoes em relacao ao perfil base dele -> usar o perfil da impressora com o **mesmo nome do perfil
  base** e a altura de camada dele como mudanca (auto). Ex.: um perfil "optimised" a 0.12 feito sobre o 0.20 Standard.
- Alturas de camada variaveis (`Metadata/layer_heights_profile.txt`) mandam sobre `layer_height` (tambem no Bambu).
  Um perfil "0.12" com o perfil variavel do autor a 0.2 imprime a 0.2. Um 0.12 a serio precisa do perfil limitado a
  0.12.
- Anycubic 2.0.0.3: estilos de suporte default/tree_slim/tree_strong/tree_hybrid (sem tree_organic) (auto).
  `zig-zag` do Bambu -> `zigzag` (auto). Fuzzy skin pintado (`paint_fuzzy_skin`) e suportado.
- Fim de impressao: onde o de fabrica desliga com o bico pousado na peca (fio/bolinha no topo) -> levanta 5 mm e vai
  para o canto (mesa - 10 mm) (auto).

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
