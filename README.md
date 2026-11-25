<p align="center">
  <img src="docs/banner.svg" alt="MakerWorld to Any — projetos Bambu Lab e MakerWorld prontos para impressoras Anycubic" width="100%">
</p>

<h1 align="center">MakerWorld to Any</h1>

<p align="center">
  <b>Projetos do MakerWorld prontos a imprimir na tua Anycubic, com um comando.</b><br>
  <sub>Skill do Claude Code · feita pela <a href="https://megatic.pt"><b>Megatic</b></a> · <a href="README.en.md">🇬🇧 English</a></sub>
</p>

<p align="center">
  <a href="https://github.com/GodFaizT/makerworld-to-any/releases/latest"><img alt="Versão" src="https://img.shields.io/github/v/release/GodFaizT/makerworld-to-any?label=vers%C3%A3o&color=38BDF8"></a>
  <a href="https://github.com/GodFaizT/makerworld-to-any/actions/workflows/testes.yml"><img alt="Testes" src="https://github.com/GodFaizT/makerworld-to-any/actions/workflows/testes.yml/badge.svg"></a>
  <img alt="Claude Code skill" src="https://img.shields.io/badge/Claude%20Code-skill-D97757?logo=claude&logoColor=white">
  <img alt="Anycubic Slicer Next" src="https://img.shields.io/badge/Anycubic%20Slicer%20Next-2.0-1E88E5">
  <img alt="Windows" src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?logo=windows&logoColor=white">
  <a href="LICENSE"><img alt="Licença MIT" src="https://img.shields.io/badge/licen%C3%A7a-MIT-22c55e"></a>
  <a href="https://megatic.pt"><img alt="Feito pela Megatic" src="https://img.shields.io/badge/feito%20pela-Megatic-0F172A?labelColor=38BDF8"></a>
</p>

<p align="center">
  <a href="#comecar"><b>Começar</b></a> ·
  <a href="#comandos"><b>Comandos</b></a> ·
  <a href="#depois"><b>Pratos e cores</b></a> ·
  <a href="#impressoras"><b>Impressoras</b></a> ·
  <a href="#perfis"><b>Perfis</b></a> ·
  <a href="#filamentos"><b>Filamentos</b></a> ·
  <a href="#preferencias"><b>Pastas e custo</b></a> ·
  <a href="#perguntas"><b>Perguntas</b></a>
</p>

Os modelos do [MakerWorld](https://makerworld.com) são feitos no Bambu Studio para impressoras Bambu Lab. Abertos
no **Anycubic Slicer Next** perdem perfis, ficam com filamentos da Bambu com temperaturas erradas, desligam a torre
de purga e às vezes até rebentam o programa. A **MakerWorld to Any** trata disso tudo com a linha de comandos do
próprio Anycubic e confirma o resultado fatiando: dás-lhe um `.3mf` e recebes um projeto pronto a imprimir, com o
tempo e as gramas de cada prato.

<p align="center">
  <img src="docs/demo.svg" alt="Conversa no Claude: /kobrax com o projeto de exemplo e a resposta, com o perfil, as cores na ACE, o tempo, as gramas e o custo de cada prato" width="860">
  <br><sub>Assim fica no Claude. Os números são de uma adaptação verdadeira do projeto de exemplo que vem com a skill (2 pratos, 2 cores).</sub>
</p>

<a id="comecar"></a>

## 🚀 Começar em 1 minuto

> **Precisas de:** [Claude Code](https://claude.com/claude-code) · [Anycubic Slicer Next](https://www.anycubic.com) (Windows) · [Python 3](https://www.python.org/downloads/)

**1. Instala** — dentro do Claude Code:

```text
/plugin marketplace add GodFaizT/makerworld-to-any
/plugin install makerworld-to-any@makerworld-to-any
```

**2. Abre uma sessão nova** do Claude Code.

**3. Adapta** — o comando da tua impressora e o caminho do ficheiro:

```text
/kobrax "C:\Downloads\Vaso.3mf"
```

Pronto: fica `Vaso - Kobra X.3mf` ao lado do original, já verificado, com tempo e gramas de cada prato. 🎉

Para confirmar que está tudo no sítio: `/any-diagnostico teste` (adapta e fatia um projeto de exemplo em menos de um
minuto).

<details>
<summary><b>Outras formas de instalar</b> (npx, ZIP, app do Claude)</summary>

<br>

| Como | Comando / passos |
|---|---|
| **npx** (sem plugin) | `npx github:GodFaizT/makerworld-to-any` — instala em `~/.claude/skills` (`--projeto` só no projeto atual, `--desinstalar` para remover) |
| **npx skills** | `npx skills add GodFaizT/makerworld-to-any` |
| **ZIP** | Descarrega `makerworld-to-any-v….zip` das [releases](https://github.com/GodFaizT/makerworld-to-any/releases/latest), descompacta e dá duplo clique em `instalar.bat` |
| **App Claude (separador _Code_)** | É o Claude Code dentro da app: instala o plugin como acima. Funciona tudo. |
| **Chat do claude.ai / da app** | Carrega `makerworld-to-any-skill.zip` em **Definições → Capacidades → Skills**. O chat corre num servidor sem o Anycubic Slicer Next: o Claude explica e aconselha, mas não adapta nem fatia. |

O `numpy` é opcional (`pip install numpy`): com ele a skill mede a folga real entre peças e consegue afastá-las.

</details>

<a id="comandos"></a>

## ⚡ Comandos

Escreve o comando, o caminho do `.3mf` (ou de uma **pasta**, para adaptar todos os que lá estão) e, se quiseres,
o que mais queres em português normal.

| Comando | Para |
|---|---|
| `/kobrax <ficheiro>` | adaptar para a Anycubic **Kobra X** |
| `/kobra4` · `/kobras1` · `/kobras1max` · `/kobra3` · `/kobra3max` | o mesmo para a **Kobra 4**, **S1**, **S1 Max**, **Kobra 3** e **3 Max** |
| `/anycubic <impressora> <ficheiro>` | qualquer outra: Kobra 2 Neo, Kobra 3 V2, Kobra 1… |
| `/any-pratos <adaptado>` | arrumar pratos: mover objetos, um por prato, juntar, afastar peças |
| `/any-cores <adaptado>` | cores por peça, juntar uma cor, mudar cores ou o material |
| `/any-desfazer [ficheiro]` | repor a versão anterior de um ficheiro |
| `/any-perfil` | os teus perfis, a tua impressora, pastas e preços |
| `/any-diagnostico [teste]` | ver se está tudo a funcionar |
| `/any-update` | atualizar a skill e os comandos |

```text
/kobrax "C:\Downloads\Vaso.3mf"
/kobras1 "C:\Downloads\Vaso.3mf" com 12 cm, em PLA Silk dourado
/kobrax "C:\Downloads\Vaso.3mf" com os meus perfis
/kobrax "C:\Downloads\Vaso.3mf" em PETG e guarda o g-code
/kobra3max "C:\Downloads\MakerWorld"                  ← todos os .3mf da pasta
/anycubic Kobra 2 Neo "C:\Downloads\Vaso.3mf" bico 0.6
```

Também podes simplesmente pedir: *"adapta este ficheiro para a kobra x"*, *"mete o vaso com 10 cm"*,
*"põe o corpo num prato e a tampa noutro"*, *"o nome a azul e o resto a branco"*, *"quanto tempo demora este?"*.

<a id="depois"></a>

## 🧰 Depois de adaptar: pratos, cores, tamanho

Um projeto já adaptado pode ser trabalhado sem voltar ao original. Cada alteração é fatiada outra vez, para saberes
o tempo e as gramas, e fica sempre uma cópia do ficheiro anterior.

<p align="center">
  <img src="docs/pratos.png" alt="Os dois pratos do projeto de exemplo vistos de cima, com a peça na cor do filamento e a torre de purga" width="760">
  <br><sub>O que a skill vê: a forma real de cada peça (não a caixa à volta), a torre de purga, o tempo e as gramas de cada prato.</sub>
</p>

**Pratos** — `/any-pratos`

```text
/any-pratos "C:\…\Vaso - Kobra X.3mf"                                 ← mostra o que está em cada prato
/any-pratos "C:\…\Vaso - Kobra X.3mf" o corpo num prato e a tampa noutro
/any-pratos "C:\…\Vaso - Kobra X.3mf" um por prato
/any-pratos "C:\…\Vaso - Kobra X.3mf" junta tudo e afasta as peças 6 mm
```

A skill mede a **folga real** entre as peças, pela forma delas. Avisa quando duas peças estão a menos de 2 mm (podem
colar na primeira camada) e sabe afastá-las. A torre de purga vai sempre para um sítio livre.

**Cores por peça** — `/any-cores`

```text
/any-cores "C:\…\Placa - Kobra X.3mf"                                 ← filamento de cada objeto e de cada peça
/any-cores "C:\…\Placa - Kobra X.3mf" o nome a azul escuro e o resto a branco
/any-cores "C:\…\Placa - Kobra X.3mf" o filamento 2 em bordô
/any-cores "C:\…\Placa - Kobra X.3mf" em PETG
```

Podes pôr uma peça noutro filamento, juntar uma cor que o projeto não tinha, ou mudar só as cores. A **purga entre
cores é recalculada** para as cores novas (de azul escuro para branco purga-se três vezes mais do que ao contrário):
a linha de comandos do Anycubic não o faz e ficava a purga das cores antigas.

**Tamanho** — pede no comando ou depois: *"mete com 10 cm"*, *"do tamanho do outro"*, *"metade"*. Cada objeto cresce
à volta do seu centro e fica assente na mesa.

**Voltar atrás** — `/any-desfazer`

```text
/any-desfazer                                 ← mostra as cópias guardadas
/any-desfazer "C:\…\Vaso - Kobra X.3mf"       ← repõe a versão anterior
```

Antes de substituir um ficheiro, a skill guarda-o (ficam as últimas 30 cópias, em `%APPDATA%\makerworld-to-any\copias`).
Os teus originais nunca são alterados.

<a id="impressoras"></a>

## 🖨 Impressoras

| Impressora | Mesa (mm) | Bicos | Cores |
|---|---|---|---|
| **Kobra X** | 260 × 260 × 260 | 0.25 · 0.4 · 0.6 · 0.8 | 🌈 ACE |
| **Kobra 4** | 260 × 260 × 260 | 0.25 · 0.4 · 0.6 · 0.8 | 🌈 ACE |
| **Kobra S1** | 250 × 250 × 250 | 0.25 · 0.4 · 0.6 · 0.8 | 🌈 ACE |
| **Kobra S1 Max** | 350 × 350 × 350 | 0.25 · 0.4 · 0.6 · 0.8 | 🌈 ACE |
| **Kobra 3** · 3 V2 | 255 × 255 × 260 | 0.2 · 0.4 · 0.6 · 0.8 | 🌈 ACE |
| **Kobra 3 Max** · 3 Max V2 | 426 × 420 × 501 | 0.4 · 0.6 · 0.8 | 🌈 ACE |
| Kobra 2 · 2 Neo · 2 Pro | 220 × 220 × 250 | 0.4 | uma cor |
| Kobra 2 Plus · 2 Max | 320³ · 426³ | 0.4 | uma cor |
| Kobra 1 · 1 Plus · 1 Max | 220 · 300 · 400 | 0.4 | uma cor |

A lista vem do Anycubic Slicer Next que tens instalado. Sem ACE, um modelo de várias cores fica num só filamento e
a skill diz-te que cor vai em cada objeto, para trocares o rolo entre pratos.

<a id="perfis"></a>

## 🎛 Perfis: os da Anycubic ou os teus

Cada adaptação usa **três perfis** do Anycubic Slicer Next:

| Perfil | O que define | Exemplo |
|---|---|---|
| 🖨 **Impressora** | mesa, bico, início e fim de impressão, trocas de cor | `Anycubic Kobra X 0.4 nozzle` |
| 🧱 **Impressão** | altura de camada, paredes, enchimento, velocidades, suportes, costura | `0.20mm Standard @Anycubic Kobra X 0.4 nozzle` |
| 🧵 **Filamento** | temperaturas, ventilação, retração, fluxo, velocidade máxima | `Anycubic PLA Matte @Anycubic Kobra X 0.4 nozzle` |

### Duas maneiras de trabalhar

<table>
<tr>
<th width="50%">🏭 Perfis da Anycubic <i>(por omissão)</i></th>
<th width="50%">🙋 Os teus perfis</th>
</tr>
<tr valign="top">
<td>

Os perfis oficiais que vêm com o Anycubic Slicer Next, afinados pela Anycubic para cada impressora, bico e
filamento. Não tens de fazer nada: é o que a skill usa se não disseres o contrário.

</td>
<td>

Os perfis que tu afinaste e guardaste no Anycubic Slicer Next (costura atrás, mais paredes, o teu PLA com outra
temperatura…). A skill usa-os sempre que tens um baseado no perfil que ela escolheu; nos outros casos usa o da
Anycubic.

</td>
</tr>
</table>

### Usar os teus perfis, passo a passo

1. **Cria o teu perfil no Anycubic Slicer Next.** Escolhe a impressora e o perfil que queres afinar (ex.
   `0.20mm Standard`), muda o que quiseres e carrega no ícone de **guardar**. Dá-lhe um nome teu
   (ex. *"0.20 Os meus"*).
   Para filamentos é igual: abre por exemplo o `Anycubic PLA Matte`, afina a temperatura e guarda com outro nome.
2. **Confirma que a skill o vê:**
   ```text
   /any-perfil
   ```
   Lista os teus perfis e marca com *"← para a tua impressora"* os que servem.
3. **Escolhe usá-los:**
   ```text
   /any-perfil meus                         ← sempre, a partir de agora
   /kobrax "C:\…\Vaso.3mf" com os meus perfis   ← só desta vez
   ```
4. **Adapta como sempre.** O relatório diz que perfis foram usados e marca os teus com
   *"(perfil teu, baseado em …)"*.

Para voltar aos da Anycubic: `/any-perfil anycubic`.

> 💡 **Dica:** os modelos do MakerWorld são quase todos a **0.20 mm**. Se quiseres as tuas definições em quase
> tudo, cria o teu perfil a partir do `0.20mm Standard` da tua impressora.

### Como a skill escolhe

```mermaid
flowchart LR
    A["Perfil do autor<br/>0.20mm Standard @BBL A1"] --> B["Perfil equivalente da Anycubic<br/>0.20mm Standard @Kobra X"]
    B --> C{"Tens um perfil teu<br/>baseado neste?"}
    C -- "sim, e /any-perfil meus" --> D["🙋 Usa o teu<br/>(o mais recente)"]
    C -- "não" --> E["🏭 Usa o da Anycubic"]
```

### Quem manda em quê

| Definições | De onde vêm |
|---|---|
| Velocidades, acelerações, temperaturas, retração, ventilação | do perfil escolhido (Anycubic ou teu) — nunca da Bambu |
| Suportes, enchimento, paredes, ironing, fuzzy skin, modo vaso | do **autor do modelo**, porque o modelo foi pensado assim |
| O que mudaste no teu perfil (costura, arachne…) | **teu**: ganha aos valores que o autor só tinha por omissão |
| Altura de camada | a do autor; se escolheres o perfil à mão ("com 0.12"), a desse perfil |
| Velocidades que o autor mudou | só passam se forem **mais baixas** que as do perfil da tua impressora |
| Alturas de camada variáveis do autor | mantêm-se (o relatório diz a altura média real); *"sem camadas variáveis"* ignora-as |

O relatório separa o que o autor **mudou de propósito**, o que vinha do **perfil dele**, e o que **não passou** e
porquê (é da impressora dele, não existe no Anycubic, ou é uma velocidade acima do teu perfil).

### Prioridades

O que pedes no comando ganha a tudo: depois vêm as variáveis de ambiente, depois o `/any-perfil`, e por fim a Kobra X
com os perfis da Anycubic.

```text
/kobrax "C:\…\Vaso.3mf"                          ← usa o que está no /any-perfil
/kobrax "C:\…\Vaso.3mf" com os meus perfis       ← os teus, só desta vez
/kobrax "C:\…\Vaso.3mf" com 0.16 high quality    ← outro perfil de impressão
```

A escolha do `/any-perfil` fica guardada fora da pasta da skill, por isso não se perde com o `/any-update`. Os teus
perfis só são lidos: a skill nunca escreve na pasta do Anycubic.

<a id="filamentos"></a>

## 🧵 Filamentos: cada material com o seu perfil

A skill vê o material de cada filamento do autor e escolhe o perfil **desse material** para a tua impressora, com
as temperaturas, a ventilação, a retração e a velocidade máxima certas. As cores do autor mantêm-se.

| Material do autor (Bambu) | Fica (se a impressora tiver) | Notas |
|---|---|---|
| PLA Basic, Generic PLA | Anycubic PLA | |
| PLA Matte · Silk · Wood · Glow · Translucent · Marble · Galaxy/Sparkle · Metal | a variante igual da Anycubic | se a impressora não a tiver, fica PLA |
| PLA Tough / PLA+ | Anycubic PLA+ | |
| PLA-CF | Anycubic PLA-CF | 🔩 bico endurecido |
| PETG (Basic, HF, Translucent) | Anycubic PETG | |
| PETG-CF · PET-CF | Anycubic PETG-CF · PET-CF | 🔩 bico endurecido |
| PCTG | Anycubic PETG | ⚠️ avisa |
| ABS · ASA | Anycubic ABS · ASA | 📦 impressora fechada |
| PC · PC-CF · PC-GF | Anycubic PC · PC-CF · PC-GF | 📦 impressora fechada |
| PA · PA6-CF · PAHT-CF | Anycubic PA · PA6-CF · PAHT-CF | 📦 fechada · 🔩 bico endurecido |
| TPU 95A | Anycubic TPU 95A / TPU | 🌀 bobine externa |
| TPU for AMS | Anycubic TPU for ACE | 🌀 pode ir pela ACE |
| PVA | Anycubic PVA | 💧 guardar seco |
| Support for PLA | Anycubic PLA | ⚠️ avisa (era material só para suportes) |

**Se a tua impressora não tiver perfil para o material** (por exemplo PC na Kobra X ou ASA na Kobra 1), a skill usa o
mais próximo e **avisa sempre**. Nunca troca de material em silêncio. Os materiais disponíveis variam muito: a S1
Max tem PA, PC e fibras, e a Kobra 1 só tem Generic PLA, PETG e ABS.

**Mudar o material** — pede no comando e as cores ficam:

```text
/kobrax "C:\…\Vaso.3mf" em PETG
/kobras1 "C:\…\Vaso.3mf" em PLA Silk
/kobras1max "C:\…\Suporte.3mf" em PA6-CF
```

**Usar o teu perfil de filamento:** guarda-o no Anycubic Slicer Next a partir do perfil da Anycubic desse material
(ex. o teu *"PETG preto"* a partir do `Anycubic PETG`) e usa `/any-perfil meus`. A skill usa-o sempre que o material
for esse.

<a id="preferencias"></a>

## 📁 Pastas e custo de cada trabalho

O `/any-perfil` também guarda onde queres os ficheiros e quanto te custa imprimir:

```text
/any-perfil guarda os adaptados em D:\Impressões\Adaptado e os originais em D:\Impressões\Originais
/any-perfil PLA a 18 euros o quilo, PETG a 20, a máquina a 40 cêntimos a hora
```

- **Pasta dos adaptados** — tudo o que adaptas vai para lá (com `{impressora}` no caminho, uma pasta por impressora).
- **Pasta dos originais** — um original que largues na pasta acima dessa é arrumado lá depois de adaptado.
- **Preços** — por quilo de cada material e por hora de máquina. O relatório passa a trazer o **custo estimado** de
  cada trabalho (filamento + horas), como na imagem lá em cima.

Sem nada disto a skill funciona como sempre: o adaptado fica ao lado do original (ou numa pasta
`Adaptado <impressora>`, se existir) e não há custo no relatório.

## ✨ O que faz por ti

| | |
|---|---|
| 🎯 **Perfil certo** | O perfil da tua impressora com o mesmo nome do do autor (`0.20mm Standard @BBL A1` → `0.20mm Standard @Anycubic Kobra X`) |
| 🎨 **Filamentos e cores** | Descobre que filamentos o modelo usa *mesmo* e escolhe o perfil de cada material (PLA, PETG, ABS, TPU, CF…) para a tua impressora, com as cores do autor; avisa se a impressora não tiver o material |
| 🗼 **Torre e purga** | Liga a torre de purga quando há cores, põe-na num sítio livre de cada prato e recalcula a purga quando as cores mudam |
| 🧩 **Tudo intacto** | Pratos, peças, modificadores, pintura de cores, fuzzy skin, alturas de camada variáveis e os créditos do autor |
| 🩹 **Bugs do Anycubic** | Contorna os crashes e erros conhecidos da linha de comandos do Anycubic |
| 📏 **Tamanhos, pratos e cores** | "Mete com 10 cm", "um por prato", "o nome a azul e o resto a branco" |
| 📐 **Folgas reais** | Mede a distância entre peças pela forma delas e avisa das que podem colar |
| ✅ **Verificado** | Medidas iguais ao original, tudo dentro da mesa, e fatiado prato a prato |
| ↩️ **Sem medo** | Guarda uma cópia antes de substituir um ficheiro; `/any-desfazer` repõe |
| 💶 **Custo** | Com os teus preços, o custo estimado de cada trabalho |
| 🧷 **Fim de impressão** | Onde o g-code de fábrica deixa o bico pousado na peça (Kobra X, 4, S1 Max), levanta-o 5 mm |

```mermaid
flowchart LR
    A["📦 3MF do MakerWorld"] --> B["🔍 Analisa o projeto"]
    B --> C["🖨 Anycubic exporta<br/>com os perfis da tua impressora"]
    C --> D["🩹 Corrige e verifica"]
    D --> E["✅ Pronto a imprimir"]
    E -.-> F["🧰 pratos · cores · tamanho"]
    F -.-> D
```

<a id="atualizar"></a>

## 🔄 Atualizar e diagnosticar

```text
/any-update              ← última versão do GitHub (skill e comandos)
/any-diagnostico         ← Python, Anycubic Slicer Next, perfis e preferências
/any-diagnostico teste   ← adapta, muda cores, arruma pratos e fatia um projeto de exemplo
```

Se instalaste como plugin, também podes atualizar com `/plugin update makerworld-to-any@makerworld-to-any`. No fim,
abre uma sessão nova do Claude Code. Depois de atualizares o **Anycubic Slicer Next**, corre `/any-diagnostico teste`:
a skill foi testada com a versão 2.0.0.3 e o teste diz-te se continua tudo a funcionar com a tua. As novidades de
cada versão estão no [CHANGELOG](CHANGELOG.md).

<a id="perguntas"></a>

## ❓ Perguntas frequentes

<details>
<summary><b>Funciona no chat do claude.ai ou só no Claude Code?</b></summary>

<br>Precisa de correr o Anycubic Slicer Next no teu computador, por isso adapta no **Claude Code** (terminal, VS Code
ou separador *Code* da app Claude para Windows). No chat do claude.ai a skill só explica e aconselha.
</details>

<details>
<summary><b>A minha impressora não tem ACE e o modelo tem várias cores</b></summary>

<br>Nas Kobra 1 e 2 o projeto fica com um só filamento (sem comandos de troca que a impressora não sabe fazer) e a
skill diz-te a cor que o autor deu a cada objeto, para trocares o rolo entre pratos.
</details>

<details>
<summary><b>O modelo não cabe na minha mesa</b></summary>

<br>A skill avisa. Pede para reduzir (*"mete com 18 cm"*), divide por pratos (`/any-pratos`), ou escolhe uma
impressora maior.
</details>

<details>
<summary><b>Mexe nos meus perfis ou nos meus ficheiros?</b></summary>

<br>Os teus perfis só são lidos: a skill nunca escreve na pasta do Anycubic. Os originais nunca são alterados (só
mudam de pasta se guardaste uma pasta de originais). Quando um adaptado é substituído, fica uma cópia que o
`/any-desfazer` repõe.
</details>

<details>
<summary><b>Posso imprimir diretamente o g-code que a skill guarda?</b></summary>

<br>Com *"guarda o g-code"* ficas com o g-code de cada prato tal como o Anycubic Slicer Next o fatiou. O caminho
recomendado continua a ser abrir o `.3mf` no Anycubic Slicer Next e enviar dali: vês a pré-visualização e a ACE fica
mapeada. O g-code direto é para quem sabe o que está a fazer.
</details>

<details>
<summary><b>O custo estimado inclui o quê?</b></summary>

<br>As gramas de cada filamento ao preço por quilo que guardaste, mais as horas de impressão ao teu preço por hora.
Falhas, eletricidade ou o teu tempo só entram se os puseres no preço por hora.
</details>

<details>
<summary><b>E os créditos e licenças dos modelos?</b></summary>

<br>A skill mantém no projeto os créditos do autor original. Os modelos continuam a ser dos seus autores: respeita
a licença de cada um (muitos são só para uso pessoal).
</details>

<details>
<summary><b>Posso usar sem o Claude?</b></summary>

<br>Sim, os scripts são Python simples (o `numpy` e o `matplotlib` são opcionais):

```bash
cd skills/makerworld-to-any/scripts
python adaptar.py --listar-impressoras
python adaptar.py "Modelo.3mf"                                   # → Modelo - Kobra X.3mf
python adaptar.py "Modelo.3mf" --impressora "Kobra S1" --perfis meus --gcode gcode
python escalar.py "Modelo - Kobra X.3mf" --altura 120 --fatiar   # altera o ficheiro e guarda uma cópia
python pratos.py "Modelo - Kobra X.3mf" --mover "corpo=1;tampa=2" --fatiar
python pratos.py "Modelo - Kobra X.3mf" --afastar 6 --fatiar
python cores.py "Modelo - Kobra X.3mf" --atribuir "tampa=2" --cores ";#232C7C"
python medir.py "Modelo - Kobra X.3mf" --fatiar --imagem pratos.png
python desfazer.py "Modelo - Kobra X.3mf"
python perfil.py meus --impressora "Kobra X" --preco-kg "PLA=18;*=22" --preco-hora 0.40
python diagnostico.py --teste
python exemplo.py Exemplo.3mf                                    # o projeto de exemplo das imagens deste README
```

| opção do `adaptar.py` | para que |
|---|---|
| `--impressora "Kobra S1"` · `--bico 0.6` | impressora e bico de destino |
| `--perfis sistema\|meus` | perfis da Anycubic ou os teus |
| `--processo "0.16mm High Quality"` | outro perfil de impressão (também um teu, pelo nome) |
| `--material PETG` | muda o material de todos os filamentos (as cores ficam) |
| `--filamentos "Anycubic PLA Matte;Anycubic PLA"` · `--cores "#FFFFFF;#800020"` | filamentos e cores por ordem |
| `--atribuir "tampa=2;1.3=2"` | filamento de objetos e peças |
| `--sem-camadas-variaveis` | ignora as alturas de camada variáveis do autor |
| `--gcode PASTA` | guarda o g-code de cada prato |
| `--saida PASTA` · `--nome FICHEIRO` · `--substituir` | onde gravar |
| `--arquivar-original PASTA` | move o original no fim |
| `--sem-fatiar` · `--json` · `--manter-temp` | só exportar · relatório em JSON · guardar a pasta temporária |

Preferências (`/any-perfil` ou `perfil.py`) ficam em `%APPDATA%\makerworld-to-any\config.json`. Variáveis de
ambiente (mandam sobre as preferências): `MAKERWORLD_TO_ANY_IMPRESSORA`, `MAKERWORLD_TO_ANY_PERFIS` (`sistema` ou
`meus`), `ANYCUBIC_SLICER` (caminho do executável).
</details>

<details>
<summary><b>Com que projetos foi testada?</b></summary>

<br>Projetos para Bambu Lab **A1**, **A1 mini** e **P1S/X1C**, com 1 a 4 pratos, até 5 filamentos, pintura de fuzzy
skin, alturas de camada variáveis e peças cortadas, adaptados para a **Kobra X** (resultados iguais a adaptações
feitas à mão), com os perfis da Anycubic e com perfis do utilizador. O teste de ponta a ponta
(`/any-diagnostico teste`) passa na **Kobra X** (bicos 0.4 e 0.6), **Kobra 4**, **S1**, **S1 Max**, **Kobra 3**,
**3 Max**, **Kobra 2 Neo**, **2 Max** e **Kobra 1**. Esse teste é feito no slicer (o projeto abre e fatia sem
erros); a impressora em que a Megatic imprime é a Kobra X.
</details>

<details>
<summary><b>Quero mexer no código</b></summary>

<br>

```bash
python -m unittest discover -s tests -t tests   # testes (com perfis falsos; os de ponta a ponta precisam do slicer)
python tools/verifica.py                        # versão, comandos gerados, sintaxe, dados pessoais
python tools/gera_comandos.py                   # os comandos /kobrax, /any-… saem todos daqui
python tools/gera_docs.py                       # as imagens deste README, a partir de uma adaptação real
python tools/publica.py 2.1.0                   # prepara uma versão: versão num sítio só, testes e ZIPs
```

As notas técnicas sobre a linha de comandos do Anycubic estão em
[`skills/makerworld-to-any/referencia/notas.md`](skills/makerworld-to-any/referencia/notas.md).
</details>

---

<p align="center">
  <br>
  <a href="https://megatic.pt"><img alt="Megatic" src="https://img.shields.io/badge/Megatic-megatic.pt-0F172A?style=for-the-badge&labelColor=38BDF8"></a>
  <br><br>
  Feito com ❤️ em Portugal pela <a href="https://megatic.pt"><b>Megatic</b></a><br>
  <sub>Projeto independente, sem ligação à Bambu Lab, à Anycubic nem ao MakerWorld · Licença MIT</sub>
</p>
