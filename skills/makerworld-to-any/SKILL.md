---
name: makerworld-to-any
description: Adapta projetos 3MF do Bambu Studio / MakerWorld (Bambu Lab A1, A1 mini, P1S, X1C...) para impressoras Anycubic (Kobra X, Kobra S1, S1 Max, Kobra 3, 3 Max, Kobra 4, Kobra 2, Kobra 1...) no Anycubic Slicer Next, e muda o tamanho, separa pratos ou mede/fatia projetos Anycubic. Usar quando o utilizador pede "adapta para a kobra x / s1 / kobra 3", "converte este 3mf para a anycubic", "mete com X cm", "faz um ficheiro so com o prato N", "quanto tempo demora", ou da um .3mf do MakerWorld/Bambu Studio para imprimir numa Anycubic. Also for "convert this Bambu/MakerWorld 3MF to my Anycubic printer".
---

# MakerWorld to Any

Projetos Bambu Lab / MakerWorld -> impressoras Anycubic. Feito pela Megatic (https://megatic.pt).

Converte projetos 3MF feitos no Bambu Studio (a maioria dos modelos do MakerWorld) em projetos do **Anycubic Slicer
Next** (testado com a 2.0.0.3) para qualquer impressora Anycubic que o slicer traga: Kobra X, Kobra S1 / S1 Max,
Kobra 3 / 3 V2 / 3 Max, Kobra 4, Kobra 2 (Neo, Pro, Plus, Max), Kobra 1. Mesa, perfis e filamentos vem dos perfis de
cada impressora. Confirma o resultado fatiando. Responder na lingua do utilizador (PT-PT se escreve em portugues).

Os scripts estao em `scripts/` dentro da pasta desta skill (a "Base directory" indicada ao carregar a skill).
Precisam de Python 3 (`python` ou `py -3`; o numpy acelera mas e opcional) e do Anycubic Slicer Next instalado em
`C:\Program Files\AnycubicSlicerNext` (outro sitio: variavel de ambiente `ANYCUBIC_SLICER`). Cada adaptacao demora
1-3 minutos porque exporta e fatia todos os pratos.

Se o Anycubic Slicer Next nao existir neste ambiente (ex.: chat do claude.ai ou da app Claude, que correm num
servidor Linux), nao tentar instalar nem simular: explicar que a adaptacao tem de ser feita no Claude Code no
computador Windows onde esta o Anycubic (na app Claude: separador "Code"), e ajudar so com conselhos.

## Que impressora?

- `--impressora "Kobra S1"` (basta o modelo; aceita "kobra-s1", "Kobra 3 Max", "Kobra X 0.6"...). Sem a opcao usa
  a variavel de ambiente `MAKERWORLD_TO_ANY_IMPRESSORA`, ou a Kobra X.
- Se o utilizador nunca disse qual e a impressora dele e o pedido nao a indica, perguntar uma vez e sugerir definir
  `MAKERWORLD_TO_ANY_IMPRESSORA` (ou guardar na memoria) para nao perguntar outra vez.
- `python "<skill>/scripts/adaptar.py" --listar-impressoras` mostra todas, com mesa, bicos e se tem ACE.
- Bico: `--bico 0.6`; sem a opcao usa o bico do original se a impressora tiver perfis para ele, senao 0.4.
- **Cores**: so as impressoras com ACE (Kobra X, S1, S1 Max, Kobra 3, 3 V2, 3 Max, Kobra 4) trocam de filamento
  sozinhas. Nas Kobra 1 e 2 um projeto com varias cores da aviso: imprimir numa cor (`--filamentos` com um so) ou
  trocar a mao.

## Regras

- O Anycubic escreve certificados e chaves privadas da impressora (ficheiros com nome hexadecimal) na pasta onde corre.
  Os scripts correm-no numa pasta temporaria; se aparecerem ficheiros assim noutra pasta, **nao os abrir nem mostrar**.
- Nao procurar ficheiros pelo disco todo: perguntar onde esta o 3MF se nao for obvio.
- Nao descarregar do MakerWorld sem autorizacao explicita do utilizador.
- Antes de substituir um ficheiro adaptado que ja existe, guardar uma copia e dizer onde ficou.

## 1. Adaptar

```
python "<skill>/scripts/adaptar.py" "<original.3mf>" [--impressora "Kobra S1"] [opcoes]
```

Saida por omissao: `<original> - <impressora>.3mf` (ex. `Vaso - Kobra S1.3mf`) numa pasta `Adaptado <impressora>` ao
lado do original (ou na pasta-mae), se existir; senao ao lado do original.

| opcao | para que |
|---|---|
| `--impressora "Kobra S1"`, `--bico 0.6` | impressora e bico de destino |
| `--saida PASTA`, `--nome FICHEIRO`, `--substituir` | onde/como gravar |
| `--arquivar-original PASTA` | no fim move o original para essa pasta (ex.: uma pasta de originais) |
| `--processo "0.16mm High Quality"` | forcar outro perfil da impressora |
| `--filamentos "Anycubic PLA Matte;Anycubic PLA"` | perfis de filamento por ordem (so o nome, sem ` @Anycubic ...`) |
| `--cores "#FFFFFF;#800020"` | cores por ordem (o utilizador diz nomes: traduzir para hex) |
| `--sem-fatiar` | so exportar (rapido, para ver definicoes) |
| `--manter-temp` | guardar a pasta temporaria para investigar |

O que o script faz:
1. Le impressora, perfil, pratos, objetos e filamentos, e descobre quais filamentos sao **mesmo usados** (pecas,
   modificadores, filamento de suporte, trocas de cor por camada; com pintura de cores ficam todos).
2. Copia o original com os nomes de prato vazios (com nome, a linha de comandos do Anycubic rebenta) e os
   filamentos usados renumerados 1..n.
3. Perfil: o da impressora com o mesmo nome do perfil base do autor ("0.20mm Standard @BBL A1" -> "0.20mm Standard";
   Optimal/Fine -> High Quality); senao a altura de camada mais proxima. Passa as definicoes que o autor mudou e as
   de "intencao" (paredes, enchimento, suportes, brim, costura, ironing, fuzzy skin, modo vaso...), mas nao as da
   impressora dele (aceleracoes, posicao da torre, g-code). `zig-zag` -> `zigzag`; `tree_organic` sai (o Anycubic
   2.0 nao tem).
4. Filamentos: Bambu PLA Matte -> Anycubic PLA Matte, Silk -> PLA Silk, PETG -> PETG, TPU -> TPU 95A... (so os que a
   impressora tem; senao o Anycubic/Generic mais proximo) com as cores do autor.
5. O Anycubic cria o projeto a partir do 3MF original (mantem pecas, modificadores, pintura de cores, fuzzy skin
   pintado, pratos, alturas de camada variaveis e os creditos do autor) e centra tudo na mesa da impressora.
6. Corrige o que a linha de comandos deixa mal: listas com filamentos a mais (compara com um projeto de referencia
   feito pelo Anycubic com o mesmo numero de filamentos), matriz de purga, torre de purga desligada (liga e poe num
   sitio livre de cada prato), lista de definicoes alteradas. Nas impressoras cujo fim de impressao deixa o bico
   pousado na peca (Kobra X, Kobra 4, S1 Max) junta um levantamento de 5 mm antes de desligar.
7. Confere que as medidas sao iguais ao original e que tudo cabe na mesa, e fatia todos os pratos.

**Ler o relatorio todo**, sobretudo `AVISOS`, e responder curto:
- onde ficou o ficheiro e para que impressora;
- perfil e o que o autor tinha mudado que passou (so o que interessa: suportes, enchimento, ironing...);
- filamentos e cores (com 2+ cores: que cor vai em que ranhura da ACE);
- por prato: o que tem, tempo, gramas (e trocas de cor);
- avisos e o que fazer (nao cabe na mesa, cores sem ACE, bico diferente...).

## 2. Mudar tamanho

Quando o utilizador da um tamanho em cm sem dizer a dimensao, e a **altura** ("mete com 10 cm"). "Do tamanho do X" =
mesma altura que o X (medir com `medir.py`); dizer tambem a largura que fica.

```
python "<skill>/scripts/escalar.py" "<adaptado.3mf>" "<saida.3mf>" --altura 100 [--objeto TEXTO] --fatiar
```

Tambem `--fator 0.52` ou `--largura 197`. Entrada e saida podem ser o mesmo ficheiro. Cada objeto cresce a volta do
seu centro e fica assente na mesa; as alturas de camada variaveis acompanham; a torre de purga e reposicionada. A
mesa e a da impressora do projeto. Com varios objetos no mesmo prato, ver os avisos de pecas encostadas.

## 3. Separar pratos e medir

- Ficar so com alguns pratos (ex.: tamanho grande nos pratos 1-2 e pequeno nos 3-4):
  `python "<skill>/scripts/separar_pratos.py" "<in.3mf>" "<out.3mf>" 3,4`, depois `medir.py --fatiar`.
- Tamanhos, posicoes, tempo e gramas: `python "<skill>/scripts/medir.py" "<ficheiro.3mf>" [--fatiar]`.

## Quando e preciso trabalho a mao

- **Objeto nao cabe na mesa** (Kobra 1/2 de 220 mm, originais da H2D...): propor reduzir com `escalar.py`, outra
  impressora maior, ou arrumar no Anycubic.
- **Mudar nomes/texto** de pecas personalizaveis: ver `referencia/notas.md`.
- **Mais de 4 cores**: uma ACE so tem 4 ranhuras; avisar.
- **`.gcode.3mf`** (ja fatiado, sem modelo): nao da para adaptar; pedir o projeto 3MF.
- **Alturas de camada variaveis** do autor mandam sobre o perfil: se o utilizador pede uma altura de camada, avisar.
- Se o Anycubic falhar, correr com `--manter-temp`, ver `entrada.3mf` e ler `referencia/notas.md`.

## Verificacao

Nunca dizer que esta pronto sem o relatorio do fatiamento (tempo e gramas de cada prato). Se ja existe um adaptado
anterior do mesmo modelo, comparar tempo/gramas e explicar diferencas.
