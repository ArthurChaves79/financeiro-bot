# Meu Financeiro

Aplicativo web (PWA) de controle financeiro pessoal — instale na tela inicial do celular e use offline, sem precisar de conta ou servidor.

Substitui o antigo bot de WhatsApp por um app que funciona direto no navegador do celular.

## Funcionalidades

- Registrar receitas e despesas com categoria, descrição e data
- Ver o saldo atual, o extrato agrupado por mês e um resumo de receitas x despesas do mês, com comparação percentual em relação ao mês anterior
- Definir orçamentos mensais por categoria, com aviso quando o limite é ultrapassado
- Relatório com gráfico de barras da evolução dos gastos nos últimos 6 meses e gráfico de pizza dos gastos por categoria, navegável por mês
- Funciona offline (Service Worker) e pode ser instalado como app no celular
- Os dados ficam salvos localmente no navegador (localStorage) — não saem do seu aparelho
- Backup: exportar todos os dados em um arquivo `.json` e importá-los depois (útil ao trocar de celular ou por segurança)
- Importar extrato bancário (`.ofx`/`.qfx` do internet banking, ou `.csv`) para trazer as entradas e saídas automaticamente, sem digitar uma por uma
- Consultor com IA (opcional): um botão "Analisar com IA" no Relatório que dá um diagnóstico do mês e sugestões de economia com base nos seus dados

## Como usar

Basta abrir `index.html` num navegador (ou hospedar os arquivos estáticos, ex. GitHub Pages). No celular, use a opção "Adicionar à tela inicial" do navegador para instalar como app.

### Rodando localmente

```
python3 -m http.server 8000
```

Depois acesse `http://localhost:8000` no navegador.

### Backup

No menu de configurações (ícone de engrenagem):

- **Exportar backup**: baixa um arquivo `financeiro-backup-AAAA-MM-DD.json` com todas as transações e orçamentos.
- **Importar backup**: escolhe um arquivo `.json` exportado anteriormente e substitui os dados atuais por ele.
- **Apagar todos os dados**: limpa tudo o que está salvo neste celular.

### Importar extrato do banco

No menu de configurações, em "Importar extrato bancário", escolha o arquivo baixado do internet banking:

- **`.ofx`/`.qfx`**: formato padrão exportado pela maioria dos bancos (ex. Bradesco).
- **`.csv`**: planilha com colunas de data, valor e descrição (ex. exportação do Nubank). O separador (`,` ou `;`) e os nomes das colunas são detectados automaticamente.

As transações importadas entram com a categoria "A categorizar" — toque em cada uma para ajustar a categoria depois. Reimportar o mesmo período não duplica lançamentos: o app identifica transações já importadas (pelo identificador do OFX, ou por data + valor + descrição) e ignora as repetidas.

> Isso não é sincronização automática via Open Finance — cada banco tem sua própria forma de exportar o extrato (app ou internet banking), então é preciso baixar o arquivo manualmente sempre que quiser atualizar.

### Consultor com IA

Na aba **Relatório**, o botão "Analisar com IA" envia um resumo do seu mês (saldo, receitas, despesas por categoria, orçamentos e a evolução dos últimos 6 meses — nunca a lista de transações inteira) para a API da Anthropic (Claude) e mostra um diagnóstico curto com pontos de atenção e sugestões de economia.

Como configurar:

1. Gere sua própria chave em [console.anthropic.com](https://console.anthropic.com) (é uma conta separada do app, cobra por uso — uma análise custa uma fração de centavo).
2. Cole a chave em Configurações ⚙ → "Chave da API (Anthropic)" → Salvar chave.

Detalhes importantes:

- A chave fica salva só neste celular (`localStorage`), **nunca** é incluída no backup `.json`.
- Nada é enviado automaticamente — só quando você toca em "Analisar com IA".
- O app chama a API da Anthropic diretamente do navegador (sem servidor próprio). Isso expõe a chave a quem tiver acesso ao seu celular/navegador — mesmo risco de uma senha salva no navegador. Não compartilhe seu celular com essa chave configurada, nem reuse uma chave "cara" de produção aqui.

## Estrutura

- `index.html` — estrutura da página
- `styles.css` — estilos
- `app.js` — lógica do app (transações, orçamentos, relatório, backup)
- `sw.js` — Service Worker (cache offline)
- `manifest.webmanifest` — metadados de instalação do PWA
- `icons/` — ícones do app
