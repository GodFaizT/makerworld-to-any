---
name: makerworld-update
description: "Comando /makerworld-update: atualiza a MakerWorld to Any (skill e comandos /kobrax, /kobras1, ...) para a ultima versao publicada no GitHub. Feito pela Megatic."
argument-hint: "[--verificar]"
disable-model-invocation: true
---

# /makerworld-update - atualizar a MakerWorld to Any

Pedido: `$ARGUMENTS`

1. A skill principal esta na pasta irma desta: `<Base directory desta skill>/../makerworld-to-any`.
   Corre: `python "<essa pasta>/scripts/atualizar.py" $ARGUMENTS` (ou `py -3`).
   - Instalada como plugin: o script usa `claude plugin update`; se o `claude` nao estiver no PATH, diz ao
     utilizador para correr `/plugin marketplace update makerworld-to-any` e
     `/plugin update makerworld-to-any@makerworld-to-any`.
   - Instalada como skill: o script descarrega o ZIP da ultima release do GitHub (GodFaizT/makerworld-to-any) e
     substitui so as pastas da skill e dos comandos.
2. Responde curto: versao que tinha -> versao nova e as novidades principais (ou que ja tem a ultima).
3. Se atualizou: lembrar de abrir uma sessao nova do Claude Code (as skills carregam no arranque).
4. Se falhar (sem internet, GitHub em baixo): dizer o erro e sugerir `npx github:GodFaizT/makerworld-to-any`.
