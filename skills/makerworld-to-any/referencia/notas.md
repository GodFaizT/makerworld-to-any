# Notas tecnicas (Anycubic Slicer Next 2.0.0.3, linha de comandos)

MakerWorld to Any - Megatic (https://megatic.pt).

Os scripts ja tratam tudo o que esta marcado com (auto). Depois de uma atualizacao do Anycubic Slicer Next, correr
`diagnostico.py --teste`: se passar, estas notas continuam validas.

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
- Um STL solto so e carregado se estiver mais ou menos entre 60 e 125 mm, seja qual for a mesa (na origem, ou a
  partir de ~150 mm, da "Loading of a model file failed") -> o cubo de referencia fica sempre a 100 mm (auto).
- Centra os pratos na mesa da impressora de destino (Kobra X: +2,+2 de uma mesa de 256; +40 da A1 mini de 180).
  Pratos separados por mesa x 1.2 (Kobra X 312, S1 300, Kobra 3 306, 3 Max 511.2 x 504); colunas = arredondar para
  cima de raiz(n); as filas crescem para y negativo. A vista de montagem (assemble) e so visual.
- Escreve mal `different_settings_to_system`; tem de ser `[processo, "" por filamento..., "machine_end_gcode"]` (auto).
- Com menos ficheiros de filamento do que o projeto tinha, so substitui os primeiros e deixa os restantes como
  perfis Bambu (temperaturas erradas, High Flow a 220 C...) -> cortar todas as listas por filamento (auto). Listas
  `*_group` sao [processo, filamentos..., impressora].
- Com **mais** ficheiros de filamento do que o projeto tinha, alarga todas as listas (bom), mas tudo o que apontava
  para um filamento que a entrada ainda nao tinha volta ao filamento 1 -> o filamento de cada objeto/peca e escrito
  outra vez depois de exportar (auto). No `model_settings` o filamento do objeto esta sempre escrito e o da peca so
  quando e diferente.
- No Bambu 2.x, `wall_filament`/`sparse_infill_filament`/`solid_infill_filament` do perfil valem 1 por omissao (=
  filamento do objeto): nao contam como "usados" (auto).
- Desliga a torre de purga (`enable_prime_tower` 0) mesmo com 2 cores; os perfis com ACE tem 1 (auto, e posicao
  livre por prato). Pegada medida numa Kobra X: x de X-6 a X+largura+1, y de Y-7.5 a Y+20 com 2 cores.
- A matriz `matrix` das pecas no `model_settings` sai "dobrada" (escala 1.21 para 1.1): inofensivo, o g-code sai certo.
- Diferencas de normalizacao que aparecem sempre (internal_solid_infill_pattern rectilinear, wall_direction ccw,
  ironing_angle 0) sao do proprio Anycubic.
- Erros conhecidos tem uma dica no fim da mensagem (`anycubic.DICAS_CLI`); as linhas `calc_exclude_triangles` do
  registo sao ruido.
- **Recusa** qualquer projeto com `post_process` nao vazio ("normative_check: postprocess not supported"), tanto a
  exportar como a fatiar: ou seja, a linha de comandos nunca corre esses scripts. O `adaptar.py` tira-os da copia
  de entrada e do projeto final (auto) e o relatorio diz que nao passaram; o `fatia()` fatia uma copia sem eles
  quando um projeto ja adaptado os tem. A skill nunca escreve `post_process` num projeto.

## Purga entre cores

- A linha de comandos **nunca recalcula** `flush_volumes_matrix`: herda a do original (um projeto de 1 filamento
  fica com 16 valores "280" mesmo depois de passar a ter 2). Escreve-se sempre uma matriz k x k (auto): os valores do
  autor onde as duas cores nao mudaram, e recalculados onde mudaram ou onde o filamento e novo.
- Calculo em `purga.py`: e a formula do Bambu Studio (diferenca de cor em HSV + luminancia) mais `nozzle_volume` do
  perfil da impressora (Kobra X 79, Bambu A1 92). Conferida com um projeto real: reproduz ao mm3 os valores
  guardados pelo Bambu Studio. Para uma cor mais clara purga-se muito mais (branco -> azul escuro 204, o contrario
  604 na Kobra X). Maximo 800.
- A impressora multiplica por `flush_multiplier` (0.7 na Kobra X): o relatorio mostra os mm3 antes de multiplicar.

## Pratos, folgas e torre

- `model_settings.config`: um bloco `<plate>` por prato com `plater_id`, `plater_name`, miniaturas e um
  `<model_instance>` (object_id, instance_id, identify_id) por objeto. `pratos.py` reescreve os blocos, tira as
  miniaturas dos pratos que mudaram e apaga os que ficam vazios.
- `custom_gcode_per_layer.xml`: um bloco `<plate>` por prato (`<plate_info id="N"/>`) com as trocas de cor e pausas
  por camada (`<layer top_z="..." .../>`). Valem para o prato inteiro. `pratos.py` leva-as com as pecas (e avisa
  quando um prato passa a juntar pecas de pratos diferentes), `separar_pratos.py` fica so com as dos pratos que
  ficam, e `escalar.py` multiplica o `top_z` quando todas as pecas do prato mudam de tamanho.
- O prato de um objeto e so a posicao dele (o centro da caixa dividido pelo passo entre pratos); o slicer confirma
  pelo bloco `<plate>`.
- Folga real: `distancias.py` desenha a pegada de cada peca (projecao dos triangulos, celulas de 0.25 mm) e mede a
  distancia entre pegadas. As caixas enganam (uma barra na diagonal "ocupa" o prato todo). Avisa abaixo de 2 mm.
  Precisa do numpy; sem ele ha so o aviso de caixas sobrepostas.
- A torre de purga e posta no sitio livre mais perto do centro (com as pegadas reais) e conferida no g-code.

## Impressoras

- Maquinas: `%APPDATA%\AnycubicSlicerNext\system\Anycubic\machine\*.json`, nome `Anycubic <modelo> <bico> nozzle`;
  processos e filamentos chamam-se `<nome> @<maquina>` (ou tem a maquina em `compatible_printers`) (auto).
- Mesa: `printable_area` + `printable_height` (Kobra 1/2/2 Neo/2 Pro 220; Kobra 3 255; S1 250; Kobra X e 4 260;
  1 Plus 300; 2 Plus 320; S1 Max 350; 1 Max 400; 2 Max 426; 3 Max 426 x 420 x 501).
- ACE (varias cores): as maquinas com `change_filament_gcode` (Kobra X, 4, 3, 3 V2, 3 Max, S1, S1 Max). As Kobra 1
  e 2 nao tem: o projeto fica num filamento so e o relatorio diz as cores do autor por objeto.
- Fim de impressao de fabrica sem levantar o bico: Kobra X, Kobra 4, S1 Max -> junta-se o levantamento (auto).
  S1, Kobra 3 e Kobra 1/2 ja levantam e ficam como estao.
- Velocidades: as do autor foram pensadas para a impressora dele; em qualquer impressora so passam as que sao mais
  baixas que as do perfil (auto). Excecao: `ironing_speed`, que faz parte da receita de ironing do autor (com o fluxo
  e o espacamento) e passa como esta.
- Filamentos por impressora variam muito (Kobra 1 so tem Generic PLA/PETG/ABS; Kobra 2 Neo so Anycubic PLA/PETG):
  usa-se o mais proximo, Anycubic primeiro, depois Generic (auto).
- Versao do slicer: `%APPDATA%\AnycubicSlicerNext\AnycubicSlicerNext.conf`, chave `app.version` (o diagnostico so le
  essa chave; o resto do ficheiro tem dados da conta).

## Perfis do utilizador

- Ficam em `%APPDATA%\AnycubicSlicerNext\user\<conta>\{machine,process,filament}\*.json` (mais um `.info`): so as
  diferencas, com `"inherits": "<perfil de sistema>"` e `"from": "User"`.
- Ao passar um perfil do utilizador a linha de comandos, o JSON (ja resolvido) tem de manter `inherits` = o perfil de
  sistema base; com `inherits` vazio a CLI recusa com "process not compatible with printer" (so na exportacao de um
  STL, o cubo de referencia) (auto).
- `different_settings_to_system` inclui as mudancas do utilizador em relacao ao perfil de sistema (auto).
- Projeto que ja e desta impressora (mudar cores ou material de um adaptado): o que esta em
  `different_settings_to_system` ([processo, filamento 1..n, impressora]) e do utilizador e passa tudo, sem os
  filtros dos originais (aceleracoes, velocidades acima do perfil, temperaturas) - menos `post_process`, que nunca
  passa, e o g-code e os `machine_max_*`, que correm na impressora e so passam com `--manter-gcode` (qualquer ficheiro
  pode dizer que e "desta impressora"). O fim de impressao que a propria skill poe nao conta: volta a ser posto.

## Perfis

- Perfis de sistema: `%APPDATA%\AnycubicSlicerNext\system\Anycubic\{machine,process,filament}\*.json` com heranca
  por `inherits` (auto).
- Kobra X 0.20mm Standard ~ Bambu A1 0.20mm Standard (2 paredes, 15 % grelha, tree(auto) a 30 graus). Os perfis
  Anycubic vem com suportes desligados e so na mesa.
- O autor muda definicoes em relacao ao perfil base dele -> usar o perfil da impressora com o **mesmo nome do perfil
  base** e a altura de camada dele como mudanca (auto). Ex.: um perfil "optimised" a 0.12 feito sobre o 0.20 Standard.
- O relatorio separa: `[o autor mudou]` (esta na lista de alteracoes do projeto), `[valor do perfil do autor]`
  (definicao "de intencao" que difere do perfil da Anycubic) e `[acerto da skill]`; e o que nao passou: por ser da
  impressora do autor, por nao existir no Anycubic, ou por ser uma velocidade acima do perfil.
- Estilos de suporte em arvore: default, tree_slim, tree_strong, tree_hybrid. O valor `tree_organic` do Bambu nao
  existe, mas com suportes em arvore o `default` **e** a arvore organica (e o que o slicer diz ao validar) -> o
  `tree_organic` do autor passa a `default` (auto). `zig-zag` do Bambu -> `zigzag` (auto). Fuzzy skin pintado
  (`paint_fuzzy_skin`) e suportado.
- Fim de impressao: onde o de fabrica desliga com o bico pousado na peca (fio/bolinha no topo) -> levanta 5 mm e vai
  para o canto (mesa - 10 mm) (auto).

## Alturas de camada variaveis

- `Metadata/layer_heights_profile.txt`: uma linha por objeto, `object_id=N|z;altura;z;altura;...`. O N e a **posicao**
  do objeto no projeto (1, 2, ...) e nao o id dele no 3MF. Mandam sobre `layer_height` (tambem no Bambu): um perfil
  "0.12" com o perfil variavel do autor a 0.2 imprime a 0.2.
- A primeira camada do perfil variavel tem de ter a altura da primeira camada do perfil de impressao; senao o slicer
  deita o perfil variavel fora sem avisar.
- O relatorio diz a altura media real (altura / numero de camadas do g-code) quando difere mais de 20 % da do perfil.
  `--sem-camadas-variaveis` tira o ficheiro (auto) e passa a valer a altura do perfil.
- Com suportes em arvore organica o Anycubic recusa-se a fatiar ("Variable layer height is not supported with
  Organic supports") -> os suportes passam a arvore hibrida e o relatorio diz (auto).
- `escalar.py` multiplica os z do perfil variavel (as alturas ficam) dos objetos que mudam de tamanho;
  `separar_pratos.py` renumera as linhas (a posicao muda quando saem objetos).

## Preferencias e copias de seguranca

- `%APPDATA%\makerworld-to-any\config.json` (outro sitio: `MAKERWORLD_TO_ANY_CONFIG`): `perfis`, `impressora`,
  `saida`, `originais`, `precos` ({material: EUR/kg}), `preco_hora`. Fora da pasta da skill, para sobreviver as
  atualizacoes. Le-se com ou sem BOM (o Bloco de notas pode po-lo). Se estiver estragado ha um aviso e, antes de se
  escrever por cima, fica uma copia `config.json.estragado`.
- Antes de substituir um ficheiro, os scripts guardam-no em `%APPDATA%\makerworld-to-any\copias\` (as ultimas 30,
  com `indice.json`). `desfazer.py` repoe; o ficheiro reposto tambem fica guardado.

## Pecas com texto (trabalho a mao)

- **Pendentes/enfeites OpenSCAD** (MakerLab ou OpenSCAD do autor): o texto e uma extrusao plana. Para trocar o nome:
  cortar a malha em 2D (ex. manifold3d), descobrir a fonte e o tamanho do texto original, gerar o novo texto com a
  mesma fonte e o mesmo `offset`, extrudir e substituir a malha da peca do texto no 3MF original, e so depois correr
  o `adaptar.py`.
- Pontos dos i/j e acentos ficam muitas vezes soltos (pecas flutuantes): ligar a propria haste com um "pescoco" de
  ~1 mm (e confirmar que nao liga a letra do lado), ou baixar o acento ate tocar na letra.
- Pecas que rodam (anel dentro de um aro): confirmar em varias alturas que o anel com o texto e uma peca e o aro
  outra, para continuar a rodar.
- Nomes escritos sem acento: perguntar se levam (Ines ou Inês).
