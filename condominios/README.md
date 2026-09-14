# SIG Condomínios

Aplicativo para cadastro de condomínios voltado ao **Registro de Imóveis** — não a uma administradora de condomínios. Roda como programa desktop (junto com o SIG Editor e o SIG View), sem precisar de servidor nem internet.

Cada condomínio registrado no RI tem suas particularidades (não seguem um padrão fixo), então o cadastro foi pensado para ser flexível: todos os campos de registro (livro, número, folha, data) são opcionais e podem ficar em branco quando não se aplicam a um condomínio específico.

## Funcionalidades

- **Cadastro do condomínio**: nome, endereço e número.
- **Registro do condomínio**: Matrícula (sempre única) ou Transcrição (pode conter várias, uma por linha).
- **Pastas de arquivamento**: número da(s) pasta(s) onde estão arquivados os documentos que deram origem ao condomínio.
- **Incorporação, especificação e convenção**: registro de livro/número/folha/data para cada um. Contempla tanto o padrão antigo (registro no Livro 8, quando o condomínio é transcrito) quanto o padrão atual, mais comum, de resumo da convenção no Livro 3.
- **Documentos**: classificação por tipo (auto de vistoria, quadro de áreas, especificação, convenção, plantas, outros), com referência à pasta onde está arquivado.
- **Unidades autônomas**: número da unidade e número do seu próprio registro (matrícula ou transcrição), além de fração ideal.
- **Observações** livres por condomínio.
- **Busca** por nome, endereço ou número de registro na lista de condomínios.
- **Gerar HTML do condomínio**: exporta uma página HTML autocontida com o resumo do condomínio (pastas, livros, documentos, unidades) e os dados estruturados em JSON (`<script type="application/json" id="condominio-data">`), pronta para alimentar os lotes que são condomínios no SIG view.
- **Arquivos digitalizados**: campos de "Arquivo digitalizado (rede)" nos livros e documentos, com botão 📂 para escolher o arquivo direto pelo seletor do Windows (versão desktop).
- **Backup**: exportar/importar todos os condomínios em um arquivo `.json`.

## Como usar

Este app não precisa funcionar no celular — ele sempre roda como programa desktop, junto com o SIG Editor e o SIG View. Veja `desktop/README.md` para gerar/rodar o `.exe`. (Também é possível abrir `index.html` direto num navegador para testes rápidos, mas nesse modo os dados ficam isolados no navegador daquele computador, sem o arquivo compartilhado em rede.)

### Rodando localmente

```
python3 -m http.server 8000
```

Depois acesse `http://localhost:8000` no navegador.

### Versão desktop (.exe para Windows)

Para gerar um executável Windows (janela própria, sem depender de
navegador), veja `desktop/README.md`.

## Estrutura

- `index.html` — estrutura da página (lista, detalhe do condomínio, diálogos de cadastro)
- `styles.css` — estilos
- `app.js` — lógica do app (condomínios, registro, pastas, livros, documentos, unidades, exportação HTML, backup)
- `icons/` — ícones do app
- `desktop/` — lançador Python (pywebview), API que lê/grava o `condominios-dados.json` compartilhado, e instruções para gerar o `.exe` Windows

## Modelo de dados

Cada condomínio é salvo como:

```json
{
  "id": "...",
  "nome": "Edifício Exemplo",
  "endereco": { "logradouro": "", "numero": "", "bairro": "", "cidade": "", "uf": "", "cep": "" },
  "registro": { "tipo": "matricula|transcricao", "matricula": "", "transcricoes": [] },
  "pastas": [{ "id": "...", "numero": "", "descricao": "" }],
  "livros": {
    "incorporacao": { "livro": "", "numero": "", "folha": "", "data": "", "caminho": "" },
    "especificacao": { "livro": "", "numero": "", "folha": "", "data": "", "caminho": "" },
    "convencao": { "livro": "", "numero": "", "folha": "", "tipo": "integral|resumo", "data": "", "caminho": "" }
  },
  "documentos": [{ "id": "...", "tipo": "auto_vistoria|quadro_areas|especificacao|convencao|plantas|outros", "descricao": "", "pasta": "", "data": "", "caminho": "" }],
  "unidades": [{ "id": "...", "numero": "", "registroTipo": "matricula|transcricao", "registro": "", "fracao": "" }],
  "observacoes": ""
}
```

O HTML gerado pelo botão "Gerar HTML deste condomínio" embute exatamente este objeto como JSON, para que o SIG view possa ler os dados do condomínio ao alimentar os lotes correspondentes.
