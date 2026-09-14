const STORAGE_KEY = 'meuFinanceiro.dados';

// Paleta categórica validada para segurança de daltonismo (mesma ordem fixa
// nos dois modos, apenas os tons trocam entre claro/escuro).
const CHART_COLORS_LIGHT = [
  '#2a78d6', '#eb6834', '#1baf7a', '#eda100',
  '#e87ba4', '#008300', '#4a3aa7', '#e34948',
];
const CHART_COLORS_DARK = [
  '#3987e5', '#d95926', '#199e70', '#c98500',
  '#d55181', '#008300', '#9085e9', '#e66767',
];
const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
function currentChartColors() {
  return darkModeQuery.matches ? CHART_COLORS_DARK : CHART_COLORS_LIGHT;
}

// Categoria reservada para as duas pernas de um pagamento de fatura de
// cartão (dinheiro só mudando de lugar entre contas do próprio usuário) —
// nunca entra em despesas/receitas do mês, orçamentos, tendência ou no
// resumo enviado à IA, senão a mesma compra seria contada duas vezes.
const CATEGORIA_TRANSFERENCIA = 'Pagamento de fatura';

// Método Kakeibo: agrupa categorias em 4 grupos fixos para o resumo do
// Relatório. "sem-grupo" (Não classificado) não é um grupo Kakeibo de
// verdade, é o balde para categorias ainda não classificadas.
const KAKEIBO_GRUPOS = [
  { id: 'sobrevivencia', nome: 'Sobrevivência' },
  { id: 'lazer', nome: 'Lazer' },
  { id: 'cultura', nome: 'Cultura' },
  { id: 'extra', nome: 'Extra' },
];

const DEFAULT_CATEGORIA_GRUPOS = {
  'Alimentação': 'sobrevivencia',
  'Transporte': 'sobrevivencia',
  'Moradia': 'sobrevivencia',
  'Saúde': 'sobrevivencia',
  'Lazer': 'lazer',
  'Educação': 'cultura',
  'Outros': 'extra',
};

function contaPadraoUnica() {
  return { id: 'principal', nome: 'Conta principal', tipo: 'conta' };
}

const balanceValue = document.getElementById('balance-value');
const balanceDelta = document.getElementById('balance-delta');
const receitasMesValue = document.getElementById('receitas-mes-value');
const receitasMesDelta = document.getElementById('receitas-mes-delta');
const despesasMesValue = document.getElementById('despesas-mes-value');
const despesasMesDelta = document.getElementById('despesas-mes-delta');
const trendChart = document.getElementById('trend-chart');

const tabs = document.querySelectorAll('.tab');
const views = document.querySelectorAll('.view');

const extratoEmpty = document.getElementById('extrato-empty');
const transacaoList = document.getElementById('transacao-list');
const addBtn = document.getElementById('add-btn');
const emptyAddBtn = document.getElementById('empty-add-btn');

const transacaoDialog = document.getElementById('transacao-dialog');
const transacaoForm = document.getElementById('transacao-form');
const transacaoDialogTitle = document.getElementById('transacao-dialog-title');
const tipoToggle = document.getElementById('tipo-toggle');
const tipoBtns = tipoToggle.querySelectorAll('.tipo-btn');
const valorInput = document.getElementById('valor');
const categoriaInput = document.getElementById('categoria');
const descricaoInput = document.getElementById('descricao');
const dataInput = document.getElementById('data');
const transacaoIdInput = document.getElementById('transacao-id');
const transacaoDeleteBtn = document.getElementById('transacao-delete-btn');
const transacaoCancelBtn = document.getElementById('transacao-cancel-btn');

const extratoContaFilterEl = document.getElementById('extrato-conta-filter');
const transacaoContaSelect = document.getElementById('transacao-conta');

const contasEmpty = document.getElementById('contas-empty');
const contaListEl = document.getElementById('conta-list');
const addContaBtn = document.getElementById('add-conta-btn');
const emptyContaBtn = document.getElementById('empty-conta-btn');

const contaDialog = document.getElementById('conta-dialog');
const contaForm = document.getElementById('conta-form');
const contaDialogTitle = document.getElementById('conta-dialog-title');
const contaNomeInput = document.getElementById('conta-nome');
const contaTipoSelect = document.getElementById('conta-tipo');
const contaIdInput = document.getElementById('conta-id');
const contaDeleteBtn = document.getElementById('conta-delete-btn');
const contaCancelBtn = document.getElementById('conta-cancel-btn');

const pagamentoDialog = document.getElementById('pagamento-dialog');
const pagamentoForm = document.getElementById('pagamento-form');
const pagamentoCartaoNomeEl = document.getElementById('pagamento-cartao-nome');
const pagamentoValorInput = document.getElementById('pagamento-valor');
const pagamentoContaOrigemSelect = document.getElementById('pagamento-conta-origem');
const pagamentoCartaoIdInput = document.getElementById('pagamento-cartao-id');
const pagamentoCancelBtn = document.getElementById('pagamento-cancel-btn');

const importExtratoContaSelect = document.getElementById('import-extrato-conta');
const categoriaGruposListEl = document.getElementById('categoria-grupos-list');

const kakeiboBarEl = document.getElementById('kakeibo-bar');
const kakeiboLegendEl = document.getElementById('kakeibo-legend');

const orcamentosEmpty = document.getElementById('orcamentos-empty');
const orcamentoList = document.getElementById('orcamento-list');
const addOrcamentoBtn = document.getElementById('add-orcamento-btn');
const emptyOrcamentoBtn = document.getElementById('empty-orcamento-btn');

const orcamentoDialog = document.getElementById('orcamento-dialog');
const orcamentoForm = document.getElementById('orcamento-form');
const orcamentoDialogTitle = document.getElementById('orcamento-dialog-title');
const orcamentoCategoriaInput = document.getElementById('orcamento-categoria');
const orcamentoLimiteInput = document.getElementById('orcamento-limite');
const orcamentoOriginalInput = document.getElementById('orcamento-original-categoria');
const orcamentoDeleteBtn = document.getElementById('orcamento-delete-btn');
const orcamentoCancelBtn = document.getElementById('orcamento-cancel-btn');

const prevMonthBtn = document.getElementById('prev-month-btn');
const nextMonthBtn = document.getElementById('next-month-btn');
const monthLabel = document.getElementById('month-label');
const relatorioEmpty = document.getElementById('relatorio-empty');
const relatorioContent = document.getElementById('relatorio-content');
const relatorioChart = document.getElementById('relatorio-chart');
const relatorioLegend = document.getElementById('relatorio-legend');

const settingsBtn = document.getElementById('settings-btn');
const settingsDialog = document.getElementById('settings-dialog');
const settingsCloseBtn = document.getElementById('settings-close-btn');
const exportBtn = document.getElementById('export-btn');
const importInput = document.getElementById('import-input');
const importStatus = document.getElementById('import-status');
const importExtratoInput = document.getElementById('import-extrato-input');
const importExtratoStatus = document.getElementById('import-extrato-status');
const apiKeyInput = document.getElementById('api-key-input');
const apiKeySaveBtn = document.getElementById('api-key-save-btn');
const apiKeyClearBtn = document.getElementById('api-key-clear-btn');
const apiKeyStatus = document.getElementById('api-key-status');
const advisorBtn = document.getElementById('advisor-btn');
const advisorResult = document.getElementById('advisor-result');
const wipeBtn = document.getElementById('wipe-btn');

let currentView = 'extrato';
let reportMonth = startOfMonth(new Date());

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function todayISO() {
  const d = new Date();
  const offset = d.getTimezoneOffset();
  return new Date(d.getTime() - offset * 60000).toISOString().slice(0, 10);
}

// Garante que `contas` tenha ao menos uma conta e que toda transação
// aponte para uma conta existente (dados antigos, de antes das contas
// existirem, ou um backup restaurado de uma versão anterior do app).
function migrarContas(transacoes, contasBrutas) {
  const contas = Array.isArray(contasBrutas) && contasBrutas.length > 0 ? contasBrutas : [contaPadraoUnica()];
  const contaPadraoId = contas[0].id;
  for (const t of transacoes) {
    if (!t.contaId || !contas.some((c) => c.id === t.contaId)) {
      t.contaId = contaPadraoId;
    }
  }
  return contas;
}

function migrarCategoriaGrupos(brutos) {
  return { ...DEFAULT_CATEGORIA_GRUPOS, ...(brutos && typeof brutos === 'object' ? brutos : {}) };
}

function loadData() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
    const transacoes = Array.isArray(parsed && parsed.transacoes) ? parsed.transacoes : [];
    return {
      transacoes,
      orcamentos: Array.isArray(parsed && parsed.orcamentos) ? parsed.orcamentos : [],
      contas: migrarContas(transacoes, parsed && parsed.contas),
      categoriaGrupos: migrarCategoriaGrupos(parsed && parsed.categoriaGrupos),
    };
  } catch {
    return {
      transacoes: [],
      orcamentos: [],
      contas: [contaPadraoUnica()],
      categoriaGrupos: migrarCategoriaGrupos(),
    };
  }
}

function saveData(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

let data = loadData();
// A migração (contas/categoriaGrupos) acontece em memória em loadData(); persiste
// já na primeira carga para não depender da primeira ação do usuário.
saveData(data);
let extratoContaFiltro = null; // null = todas as contas
let ultimaContaUsada = data.contas[0].id;

function formatCurrency(value) {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function formatDateShort(iso) {
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

const MONTH_NAMES = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
];

function colorFor(categoria) {
  const colors = currentChartColors();
  let hash = 0;
  for (let i = 0; i < categoria.length; i++) {
    hash = (hash * 31 + categoria.charCodeAt(i)) >>> 0;
  }
  return colors[hash % colors.length];
}

function contaPorId(contaId) {
  return data.contas.find((c) => c.id === contaId);
}

// Saldo em dinheiro: soma só as contas do tipo "conta" (corrente/poupança).
// Cartões de crédito não entram aqui — eles têm uma dívida, não um saldo
// (ver computeDividaCartao).
function computeSaldo() {
  return data.transacoes.reduce((sum, t) => {
    const conta = contaPorId(t.contaId);
    if (conta && conta.tipo === 'cartao') return sum;
    return sum + (t.tipo === 'entrada' ? t.valor : -t.valor);
  }, 0);
}

// Dívida atual de um cartão: compras (saída) menos pagamentos de fatura já
// registrados nele (entrada). Nunca fica negativa na exibição — um valor
// negativo aqui significaria fatura paga a mais.
function computeDividaCartao(contaId) {
  return data.transacoes
    .filter((t) => t.contaId === contaId)
    .reduce((sum, t) => sum + (t.tipo === 'saida' ? t.valor : -t.valor), 0);
}

function saldoDaConta(contaId) {
  return data.transacoes
    .filter((t) => t.contaId === contaId)
    .reduce((sum, t) => sum + (t.tipo === 'entrada' ? t.valor : -t.valor), 0);
}

function gastosPorCategoriaNoMes(monthDate) {
  const y = monthDate.getFullYear();
  const m = monthDate.getMonth();
  const totals = {};
  for (const t of data.transacoes) {
    if (t.tipo !== 'saida') continue;
    if (t.categoria === CATEGORIA_TRANSFERENCIA) continue;
    const d = new Date(`${t.data}T00:00:00`);
    if (d.getFullYear() !== y || d.getMonth() !== m) continue;
    totals[t.categoria] = (totals[t.categoria] || 0) + t.valor;
  }
  return totals;
}

function totaisDoMes(monthDate) {
  const y = monthDate.getFullYear();
  const m = monthDate.getMonth();
  let receitas = 0;
  let despesas = 0;
  for (const t of data.transacoes) {
    if (t.categoria === CATEGORIA_TRANSFERENCIA) continue;
    const d = new Date(`${t.data}T00:00:00`);
    if (d.getFullYear() !== y || d.getMonth() !== m) continue;
    if (t.tipo === 'entrada') receitas += t.valor;
    else despesas += t.valor;
  }
  return { receitas, despesas };
}

function formatSignedCurrency(value) {
  const sinal = value >= 0 ? '+' : '−';
  return `${sinal} ${formatCurrency(Math.abs(value))}`;
}

// Retorna a variação percentual de curr sobre prev, ou null quando não há
// base de comparação (mês anterior sem nenhum valor).
function pctChange(curr, prev) {
  if (prev === 0) return null;
  return ((curr - prev) / prev) * 100;
}

// ==============================================
// Navegação entre abas
// ==============================================
tabs.forEach((tab) => {
  tab.addEventListener('click', () => {
    tabs.forEach((t) => {
      t.classList.remove('active');
      t.setAttribute('aria-selected', 'false');
    });
    tab.classList.add('active');
    tab.setAttribute('aria-selected', 'true');
    currentView = tab.dataset.view;
    views.forEach((v) => v.classList.toggle('active', v.id === `view-${currentView}`));
    render();
  });
});

// ==============================================
// Extrato / Transações
// ==============================================
// Preenche um <select> com as contas cadastradas. Cartões aparecem com um
// sufixo "(cartão)" para ficar claro que uma despesa ali vira dívida, não
// saída de caixa imediata.
function populateContaSelect(selectEl, selectedId) {
  selectEl.innerHTML = '';
  for (const c of data.contas) {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.tipo === 'cartao' ? `${c.nome} (cartão)` : c.nome;
    selectEl.appendChild(opt);
  }
  if (selectedId && data.contas.some((c) => c.id === selectedId)) {
    selectEl.value = selectedId;
  }
}

function openTransacaoDialog(transacao) {
  transacaoForm.reset();
  setTipo('saida');
  populateContaSelect(transacaoContaSelect, transacao ? transacao.contaId : ultimaContaUsada);

  if (transacao) {
    transacaoDialogTitle.textContent = 'Editar transação';
    transacaoIdInput.value = transacao.id;
    setTipo(transacao.tipo);
    valorInput.value = transacao.valor;
    categoriaInput.value = transacao.categoria;
    descricaoInput.value = transacao.descricao || '';
    dataInput.value = transacao.data;
    transacaoDeleteBtn.hidden = false;
  } else {
    transacaoDialogTitle.textContent = 'Nova transação';
    transacaoIdInput.value = '';
    dataInput.value = todayISO();
    transacaoDeleteBtn.hidden = true;
  }

  transacaoDialog.showModal();
  valorInput.focus();
}

function setTipo(value) {
  tipoToggle.dataset.value = value;
  tipoBtns.forEach((btn) => btn.classList.toggle('active', btn.dataset.value === value));
}

tipoBtns.forEach((btn) => {
  btn.addEventListener('click', () => setTipo(btn.dataset.value));
});

addBtn.addEventListener('click', () => openTransacaoDialog(null));
emptyAddBtn.addEventListener('click', () => openTransacaoDialog(null));
transacaoCancelBtn.addEventListener('click', () => transacaoDialog.close());

transacaoDeleteBtn.addEventListener('click', () => {
  const id = transacaoIdInput.value;
  if (!id) return;
  data.transacoes = data.transacoes.filter((t) => t.id !== id);
  saveData(data);
  transacaoDialog.close();
  render();
});

transacaoForm.addEventListener('submit', (event) => {
  event.preventDefault();

  const valor = parseFloat(valorInput.value);
  const categoria = categoriaInput.value.trim();
  if (!valor || valor <= 0 || !categoria || !dataInput.value) return;

  const id = transacaoIdInput.value;
  const payload = {
    tipo: tipoToggle.dataset.value,
    valor,
    categoria,
    descricao: descricaoInput.value.trim(),
    data: dataInput.value,
    contaId: transacaoContaSelect.value,
  };
  ultimaContaUsada = payload.contaId;

  if (id) {
    const existing = data.transacoes.find((t) => t.id === id);
    Object.assign(existing, payload);
  } else {
    data.transacoes.push({
      id: crypto.randomUUID(),
      criadoEm: new Date().toISOString(),
      ...payload,
    });
  }

  saveData(data);
  transacaoDialog.close();
  render();
});

function renderExtratoContaFilter() {
  extratoContaFilterEl.innerHTML = '';

  const criarChip = (label, ativo, onClick) => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = `conta-chip${ativo ? ' active' : ''}`;
    chip.textContent = label;
    chip.addEventListener('click', onClick);
    extratoContaFilterEl.appendChild(chip);
  };

  criarChip('Todas', extratoContaFiltro === null, () => {
    extratoContaFiltro = null;
    renderExtrato();
  });

  for (const conta of data.contas) {
    criarChip(conta.nome, extratoContaFiltro === conta.id, () => {
      extratoContaFiltro = conta.id;
      renderExtrato();
    });
  }
}

function renderExtrato() {
  renderExtratoContaFilter();

  const transacoes = [...data.transacoes]
    .filter((t) => extratoContaFiltro === null || t.contaId === extratoContaFiltro)
    .sort((a, b) => {
      if (a.data !== b.data) return b.data.localeCompare(a.data);
      return (b.criadoEm || '').localeCompare(a.criadoEm || '');
    });

  transacaoList.innerHTML = '';
  extratoEmpty.hidden = transacoes.length > 0;

  let lastMonthKey = null;
  for (const t of transacoes) {
    const monthKey = t.data.slice(0, 7);
    if (monthKey !== lastMonthKey) {
      lastMonthKey = monthKey;
      const [y, m] = monthKey.split('-').map(Number);
      const header = document.createElement('li');
      header.className = 'month-header';
      header.textContent = `${MONTH_NAMES[m - 1]} ${y}`;
      transacaoList.appendChild(header);
    }

    const li = document.createElement('li');
    li.className = 'transacao-card';

    const dot = document.createElement('span');
    dot.className = 'categoria-dot';
    dot.style.background = colorFor(t.categoria);

    const textos = document.createElement('div');
    textos.className = 'transacao-textos';
    const cat = document.createElement('div');
    cat.className = 'transacao-categoria';
    if (t.categoria === 'A categorizar') cat.classList.add('pendente');
    cat.textContent = t.categoria;
    textos.appendChild(cat);
    if (t.descricao) {
      const desc = document.createElement('div');
      desc.className = 'transacao-descricao';
      desc.textContent = t.descricao;
      textos.appendChild(desc);
    }
    const date = document.createElement('div');
    date.className = 'transacao-data';
    const contaNome = contaPorId(t.contaId)?.nome || '';
    date.textContent = contaNome ? `${formatDateShort(t.data)} · ${contaNome}` : formatDateShort(t.data);
    textos.appendChild(date);

    const info = document.createElement('div');
    info.className = 'transacao-info';
    info.append(dot, textos);

    const valor = document.createElement('div');
    valor.className = `transacao-valor ${t.tipo}`;
    valor.textContent = `${t.tipo === 'entrada' ? '+' : '-'} ${formatCurrency(t.valor)}`;

    li.append(info, valor);
    li.addEventListener('click', () => openTransacaoDialog(t));
    transacaoList.appendChild(li);
  }
}

// ==============================================
// Contas (bancos e cartões)
// ==============================================
function openContaDialog(conta) {
  contaForm.reset();

  if (conta) {
    contaDialogTitle.textContent = 'Editar conta';
    contaIdInput.value = conta.id;
    contaNomeInput.value = conta.nome;
    contaTipoSelect.value = conta.tipo;
    contaDeleteBtn.hidden = false;
  } else {
    contaDialogTitle.textContent = 'Nova conta';
    contaIdInput.value = '';
    contaTipoSelect.value = 'conta';
    contaDeleteBtn.hidden = true;
  }

  contaDialog.showModal();
  contaNomeInput.focus();
}

addContaBtn.addEventListener('click', () => openContaDialog(null));
emptyContaBtn.addEventListener('click', () => openContaDialog(null));
contaCancelBtn.addEventListener('click', () => contaDialog.close());

contaDeleteBtn.addEventListener('click', () => {
  const id = contaIdInput.value;
  if (!id) return;
  if (data.contas.length <= 1) {
    window.alert('Você precisa ter pelo menos uma conta.');
    return;
  }
  const temTransacoes = data.transacoes.some((t) => t.contaId === id);
  if (temTransacoes) {
    const confirmado = window.confirm(
      'Essa conta tem transações lançadas nela. Excluí-la também vai excluir todas as transações associadas. Continuar?'
    );
    if (!confirmado) return;
    data.transacoes = data.transacoes.filter((t) => t.contaId !== id);
  }
  data.contas = data.contas.filter((c) => c.id !== id);
  if (extratoContaFiltro === id) extratoContaFiltro = null;
  if (ultimaContaUsada === id) ultimaContaUsada = data.contas[0].id;
  saveData(data);
  contaDialog.close();
  render();
});

contaForm.addEventListener('submit', (event) => {
  event.preventDefault();

  const nome = contaNomeInput.value.trim();
  const tipo = contaTipoSelect.value;
  if (!nome) return;

  const id = contaIdInput.value;
  if (id) {
    const existing = data.contas.find((c) => c.id === id);
    Object.assign(existing, { nome, tipo });
  } else {
    data.contas.push({ id: crypto.randomUUID(), nome, tipo });
  }

  saveData(data);
  contaDialog.close();
  render();
});

function openPagamentoDialog(cartaoConta) {
  pagamentoForm.reset();
  pagamentoCartaoIdInput.value = cartaoConta.id;
  pagamentoCartaoNomeEl.textContent = `Cartão: ${cartaoConta.nome}`;

  const divida = computeDividaCartao(cartaoConta.id);
  pagamentoValorInput.value = divida > 0 ? divida.toFixed(2) : '';

  pagamentoContaOrigemSelect.innerHTML = '';
  const optNenhuma = document.createElement('option');
  optNenhuma.value = '';
  optNenhuma.textContent = 'Não registrar saída em outra conta';
  pagamentoContaOrigemSelect.appendChild(optNenhuma);
  for (const c of data.contas) {
    if (c.tipo === 'cartao') continue;
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.nome;
    pagamentoContaOrigemSelect.appendChild(opt);
  }

  pagamentoDialog.showModal();
  pagamentoValorInput.focus();
}

pagamentoCancelBtn.addEventListener('click', () => pagamentoDialog.close());

pagamentoForm.addEventListener('submit', (event) => {
  event.preventDefault();

  const cartaoId = pagamentoCartaoIdInput.value;
  const valor = parseFloat(pagamentoValorInput.value);
  const contaOrigemId = pagamentoContaOrigemSelect.value;
  if (!cartaoId || !valor || valor <= 0) return;

  const criadoEm = new Date().toISOString();
  const hoje = todayISO();

  data.transacoes.push({
    id: crypto.randomUUID(),
    criadoEm,
    tipo: 'entrada',
    valor,
    categoria: CATEGORIA_TRANSFERENCIA,
    descricao: 'Pagamento de fatura',
    data: hoje,
    contaId: cartaoId,
  });

  if (contaOrigemId) {
    data.transacoes.push({
      id: crypto.randomUUID(),
      criadoEm,
      tipo: 'saida',
      valor,
      categoria: CATEGORIA_TRANSFERENCIA,
      descricao: 'Pagamento de fatura',
      data: hoje,
      contaId: contaOrigemId,
    });
  }

  saveData(data);
  pagamentoDialog.close();
  render();
});

function renderContas() {
  contaListEl.innerHTML = '';
  contasEmpty.hidden = data.contas.length > 0;

  for (const conta of data.contas) {
    const li = document.createElement('li');
    li.className = 'conta-card';

    const header = document.createElement('div');
    header.className = 'conta-header';
    const nome = document.createElement('span');
    nome.className = 'conta-nome';
    nome.textContent = conta.nome;
    const badge = document.createElement('span');
    badge.className = 'conta-tipo-badge';
    badge.textContent = conta.tipo === 'cartao' ? 'Cartão' : 'Conta';
    header.append(nome, badge);

    const valorEl = document.createElement('div');
    if (conta.tipo === 'cartao') {
      const divida = computeDividaCartao(conta.id);
      valorEl.className = `conta-valor${divida > 0 ? ' divida' : ''}`;
      valorEl.textContent = divida > 0 ? `Dívida atual: ${formatCurrency(divida)}` : 'Sem dívida';
    } else {
      const saldoConta = saldoDaConta(conta.id);
      valorEl.className = `conta-valor${saldoConta < 0 ? ' divida' : ''}`;
      valorEl.textContent = `Saldo: ${formatCurrency(saldoConta)}`;
    }

    li.append(header, valorEl);

    if (conta.tipo === 'cartao' && computeDividaCartao(conta.id) > 0) {
      const pagarBtn = document.createElement('button');
      pagarBtn.type = 'button';
      pagarBtn.className = 'secondary-btn full-width';
      pagarBtn.textContent = 'Registrar pagamento da fatura';
      pagarBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        openPagamentoDialog(conta);
      });
      li.appendChild(pagarBtn);
    }

    li.addEventListener('click', () => openContaDialog(conta));
    contaListEl.appendChild(li);
  }
}

// ==============================================
// Orçamentos
// ==============================================
function openOrcamentoDialog(orcamento) {
  orcamentoForm.reset();

  if (orcamento) {
    orcamentoDialogTitle.textContent = 'Editar orçamento';
    orcamentoCategoriaInput.value = orcamento.categoria;
    orcamentoLimiteInput.value = orcamento.limite;
    orcamentoOriginalInput.value = orcamento.categoria;
    orcamentoDeleteBtn.hidden = false;
  } else {
    orcamentoDialogTitle.textContent = 'Novo orçamento';
    orcamentoOriginalInput.value = '';
    orcamentoDeleteBtn.hidden = true;
  }

  orcamentoDialog.showModal();
  orcamentoCategoriaInput.focus();
}

addOrcamentoBtn.addEventListener('click', () => openOrcamentoDialog(null));
emptyOrcamentoBtn.addEventListener('click', () => openOrcamentoDialog(null));
orcamentoCancelBtn.addEventListener('click', () => orcamentoDialog.close());

orcamentoDeleteBtn.addEventListener('click', () => {
  const original = orcamentoOriginalInput.value;
  if (!original) return;
  data.orcamentos = data.orcamentos.filter((o) => o.categoria !== original);
  saveData(data);
  orcamentoDialog.close();
  render();
});

orcamentoForm.addEventListener('submit', (event) => {
  event.preventDefault();

  const categoria = orcamentoCategoriaInput.value.trim();
  const limite = parseFloat(orcamentoLimiteInput.value);
  if (!categoria || !limite || limite <= 0) return;

  const original = orcamentoOriginalInput.value;
  if (original) {
    data.orcamentos = data.orcamentos.filter((o) => o.categoria !== original);
  }
  data.orcamentos = data.orcamentos.filter((o) => o.categoria !== categoria);
  data.orcamentos.push({ categoria, limite });

  saveData(data);
  orcamentoDialog.close();
  render();
});

function renderOrcamentos() {
  const gastos = gastosPorCategoriaNoMes(new Date());

  orcamentoList.innerHTML = '';
  orcamentosEmpty.hidden = data.orcamentos.length > 0;

  const ordenados = [...data.orcamentos].sort((a, b) =>
    a.categoria.localeCompare(b.categoria, 'pt-BR')
  );

  for (const o of ordenados) {
    const gasto = gastos[o.categoria] || 0;
    const pct = Math.min(100, (gasto / o.limite) * 100);
    let status = 'ok';
    if (gasto > o.limite) status = 'over';
    else if (pct >= 80) status = 'warn';

    const li = document.createElement('li');
    li.className = 'orcamento-card';

    const header = document.createElement('div');
    header.className = 'orcamento-header';
    const dot = document.createElement('span');
    dot.className = 'categoria-dot';
    dot.style.background = colorFor(o.categoria);
    const cat = document.createElement('span');
    cat.className = 'orcamento-nome';
    cat.textContent = o.categoria;
    const valores = document.createElement('span');
    valores.className = `orcamento-valores ${status}`;
    valores.textContent = `${formatCurrency(gasto)} / ${formatCurrency(o.limite)}`;
    header.append(dot, cat, valores);

    const bar = document.createElement('div');
    bar.className = 'progress-bar';
    const fill = document.createElement('div');
    fill.className = `progress-fill ${status}`;
    fill.style.width = `${pct}%`;
    bar.appendChild(fill);

    li.append(header, bar);
    li.addEventListener('click', () => openOrcamentoDialog(o));
    orcamentoList.appendChild(li);
  }
}

// ==============================================
// Relatório
// ==============================================
prevMonthBtn.addEventListener('click', () => {
  reportMonth = new Date(reportMonth.getFullYear(), reportMonth.getMonth() - 1, 1);
  renderRelatorio();
});

nextMonthBtn.addEventListener('click', () => {
  reportMonth = new Date(reportMonth.getFullYear(), reportMonth.getMonth() + 1, 1);
  renderRelatorio();
});

function renderRelatorio() {
  renderTrend();
  monthLabel.textContent = `${MONTH_NAMES[reportMonth.getMonth()]} ${reportMonth.getFullYear()}`;

  const totals = gastosPorCategoriaNoMes(reportMonth);
  const entries = Object.entries(totals).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);

  relatorioEmpty.hidden = entries.length > 0;
  relatorioContent.hidden = entries.length === 0;
  if (entries.length === 0) return;

  renderKakeiboBar(entries, total);

  const ctx = relatorioChart.getContext('2d');
  const size = relatorioChart.width;
  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 8;

  ctx.clearRect(0, 0, size, size);
  let startAngle = -Math.PI / 2;
  for (const [categoria, valor] of entries) {
    const slice = (valor / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, radius, startAngle, startAngle + slice);
    ctx.closePath();
    ctx.fillStyle = colorFor(categoria);
    ctx.fill();
    startAngle += slice;
  }

  relatorioLegend.innerHTML = '';
  const totalLi = document.createElement('li');
  totalLi.className = 'legend-total';
  totalLi.textContent = `Total gasto: ${formatCurrency(total)}`;
  relatorioLegend.appendChild(totalLi);

  for (const [categoria, valor] of entries) {
    const li = document.createElement('li');
    li.className = 'legend-item';
    const dot = document.createElement('span');
    dot.className = 'legend-dot';
    dot.style.background = colorFor(categoria);
    const label = document.createElement('span');
    label.className = 'legend-label';
    label.textContent = categoria;
    const pct = document.createElement('span');
    pct.className = 'legend-pct';
    pct.textContent = `${formatCurrency(valor)} (${((valor / total) * 100).toFixed(0)}%)`;
    li.append(dot, label, pct);
    relatorioLegend.appendChild(li);
  }
}

// Resumo do mês agrupado no método Kakeibo (Sobrevivência / Lazer / Cultura
// / Extra), a partir das mesmas entradas por categoria já calculadas para a
// pizza — categorias sem grupo definido caem em "Não classificado".
function renderKakeiboBar(entries, total) {
  const porGrupo = {};
  for (const [categoria, valor] of entries) {
    const grupoId = data.categoriaGrupos[categoria] || 'sem-grupo';
    porGrupo[grupoId] = (porGrupo[grupoId] || 0) + valor;
  }

  const colors = currentChartColors();
  const corPorGrupo = {
    sobrevivencia: colors[0],
    lazer: colors[1],
    cultura: colors[2],
    extra: colors[3],
    'sem-grupo': 'var(--text-faint)',
  };
  const gruposExibidos = [...KAKEIBO_GRUPOS, { id: 'sem-grupo', nome: 'Não classificado' }];

  kakeiboBarEl.innerHTML = '';
  kakeiboLegendEl.innerHTML = '';

  for (const grupo of gruposExibidos) {
    const valor = porGrupo[grupo.id] || 0;
    if (valor <= 0) continue;
    const pct = (valor / total) * 100;

    const seg = document.createElement('div');
    seg.className = 'kakeibo-segment';
    seg.style.width = `${pct}%`;
    seg.style.background = corPorGrupo[grupo.id];
    kakeiboBarEl.appendChild(seg);

    const li = document.createElement('li');
    li.className = 'legend-item';
    const dot = document.createElement('span');
    dot.className = 'legend-dot';
    dot.style.background = corPorGrupo[grupo.id];
    const label = document.createElement('span');
    label.className = 'legend-label';
    label.textContent = grupo.nome;
    const pctEl = document.createElement('span');
    pctEl.className = 'legend-pct';
    pctEl.textContent = `${formatCurrency(valor)} (${pct.toFixed(0)}%)`;
    li.append(dot, label, pctEl);
    kakeiboLegendEl.appendChild(li);
  }
}

// ==============================================
// Categorias e grupos (método Kakeibo)
// ==============================================
function getAllCategoriasConhecidas() {
  const set = new Set(Object.keys(DEFAULT_CATEGORIA_GRUPOS));
  for (const t of data.transacoes) {
    if (t.categoria && t.categoria !== 'A categorizar' && t.categoria !== CATEGORIA_TRANSFERENCIA) {
      set.add(t.categoria);
    }
  }
  for (const o of data.orcamentos) {
    if (o.categoria) set.add(o.categoria);
  }
  return [...set].sort((a, b) => a.localeCompare(b, 'pt-BR'));
}

function renderCategoriaGrupos() {
  categoriaGruposListEl.innerHTML = '';
  const categorias = getAllCategoriasConhecidas();

  if (categorias.length === 0) {
    const p = document.createElement('p');
    p.className = 'settings-hint';
    p.textContent = 'Nenhuma categoria ainda.';
    categoriaGruposListEl.appendChild(p);
    return;
  }

  for (const categoria of categorias) {
    const row = document.createElement('div');
    row.className = 'categoria-grupo-row';

    const dot = document.createElement('span');
    dot.className = 'categoria-dot';
    dot.style.background = colorFor(categoria);

    const nome = document.createElement('span');
    nome.className = 'categoria-grupo-nome';
    nome.textContent = categoria;

    const select = document.createElement('select');
    select.className = 'categoria-grupo-select';
    const optSem = document.createElement('option');
    optSem.value = '';
    optSem.textContent = 'Sem grupo';
    select.appendChild(optSem);
    for (const grupo of KAKEIBO_GRUPOS) {
      const opt = document.createElement('option');
      opt.value = grupo.id;
      opt.textContent = grupo.nome;
      select.appendChild(opt);
    }
    select.value = data.categoriaGrupos[categoria] || '';

    select.addEventListener('change', () => {
      if (select.value) {
        data.categoriaGrupos[categoria] = select.value;
      } else {
        delete data.categoriaGrupos[categoria];
      }
      saveData(data);
      renderRelatorio();
    });

    row.append(dot, nome, select);
    categoriaGruposListEl.appendChild(row);
  }
}

// ==============================================
// Backup: exportar / importar / apagar
// ==============================================
settingsBtn.addEventListener('click', () => {
  importStatus.hidden = true;
  importInput.value = '';
  importExtratoStatus.hidden = true;
  importExtratoInput.value = '';
  populateContaSelect(importExtratoContaSelect, ultimaContaUsada);
  renderCategoriaGrupos();
  apiKeyInput.value = '';
  apiKeyStatus.hidden = false;
  apiKeyStatus.classList.remove('error');
  apiKeyStatus.textContent = getApiKey()
    ? 'Chave configurada neste celular.'
    : 'Nenhuma chave configurada — o consultor com IA fica indisponível até você adicionar uma.';
  settingsDialog.showModal();
});
settingsCloseBtn.addEventListener('click', () => settingsDialog.close());

exportBtn.addEventListener('click', () => {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `financeiro-backup-${todayISO()}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

importInput.addEventListener('change', () => {
  const file = importInput.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = () => {
    try {
      const parsed = JSON.parse(String(reader.result));
      if (!Array.isArray(parsed.transacoes) || !Array.isArray(parsed.orcamentos)) {
        throw new Error('formato inválido');
      }
      const confirmado = window.confirm(
        'Importar este backup vai substituir todos os dados atuais neste celular. Continuar?'
      );
      if (!confirmado) {
        importInput.value = '';
        return;
      }
      data = {
        transacoes: parsed.transacoes,
        orcamentos: parsed.orcamentos,
        contas: migrarContas(parsed.transacoes, parsed.contas),
        categoriaGrupos: migrarCategoriaGrupos(parsed.categoriaGrupos),
      };
      extratoContaFiltro = null;
      ultimaContaUsada = data.contas[0].id;
      saveData(data);
      render();
      importStatus.hidden = false;
      importStatus.textContent = 'Backup importado com sucesso.';
      importStatus.classList.remove('error');
    } catch {
      importStatus.hidden = false;
      importStatus.textContent = 'Não foi possível ler este arquivo. Verifique se é um backup válido.';
      importStatus.classList.add('error');
    } finally {
      importInput.value = '';
    }
  };
  reader.readAsText(file);
});

// ------------------------------------------------
// Importar extrato bancário (.ofx/.qfx ou .csv)
// ------------------------------------------------
function normalizeText(s) {
  return String(s || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim();
}

function ofxDateToISO(raw) {
  const m = String(raw || '').match(/^(\d{4})(\d{2})(\d{2})/);
  return m ? `${m[1]}-${m[2]}-${m[3]}` : null;
}

function csvDateToISO(raw) {
  const s = String(raw || '').trim();
  let m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[1]}-${m[2]}-${m[3]}`;
  m = s.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
  if (m) return `${m[3]}-${m[2]}-${m[1]}`;
  return null;
}

function parseLocaleNumber(raw) {
  let s = String(raw || '').trim();
  if (!s) return 0;
  const hasComma = s.includes(',');
  const hasDot = s.includes('.');
  if (hasComma && hasDot) {
    s = s.replace(/\./g, '').replace(',', '.');
  } else if (hasComma && !hasDot) {
    s = s.replace(',', '.');
  }
  const n = parseFloat(s);
  return Number.isFinite(n) ? n : 0;
}

function parseOFX(text) {
  const blocks = text.match(/<STMTTRN>[\s\S]*?<\/STMTTRN>/gi) || [];
  const field = (block, tag) => {
    const m = block.match(new RegExp(`<${tag}>([^<\r\n]*)`, 'i'));
    return m ? m[1].trim() : '';
  };
  return blocks
    .map((block) => {
      const dataISO = ofxDateToISO(field(block, 'DTPOSTED'));
      const valor = parseFloat(field(block, 'TRNAMT'));
      const descricao = field(block, 'MEMO') || field(block, 'NAME');
      const fitid = field(block, 'FITID') || null;
      return {
        data: dataISO,
        valor: Math.abs(valor),
        tipo: valor < 0 ? 'saida' : 'entrada',
        descricao,
        fitid,
      };
    })
    .filter((t) => t.data && Number.isFinite(t.valor) && t.valor > 0);
}

function splitCSVLine(line, delimiter) {
  const result = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inQuotes) {
      if (c === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        cur += c;
      }
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === delimiter) {
      result.push(cur);
      cur = '';
    } else {
      cur += c;
    }
  }
  result.push(cur);
  return result;
}

// Detecta se uma linha é um cabeçalho de tabela (precisa de coluna de data e
// de valor — seja uma coluna "valor" única, seja um par crédito/débito) e,
// se for, devolve o mapeamento de colunas; senão devolve null. Extratos
// bancários reais costumam ter o cabeçalho fora da primeira linha (título
// antes) e mais de uma seção/tabela no mesmo arquivo, cada uma com seu
// próprio cabeçalho — por isso o parser reavalia isso linha a linha.
function detectCsvHeader(cols) {
  const norm = cols.map(normalizeText);
  const dateIdx = norm.findIndex((h) => h === 'data' || h === 'date' || h.startsWith('data '));
  if (dateIdx === -1) return null;

  const valueIdx = norm.findIndex((h) => ['valor', 'value', 'amount', 'montante'].includes(h));
  const creditIdx = norm.findIndex(
    (h) => h.includes('credito') || h.includes('credit') || h.includes('entrada') || h.includes('receita')
  );
  const debitIdx = norm.findIndex(
    (h) => h.includes('debito') || h.includes('debit') || h.includes('saida') || h.includes('despesa')
  );
  if (valueIdx === -1 && creditIdx === -1 && debitIdx === -1) return null;

  const descIdx = norm.findIndex((h) =>
    ['descricao', 'description', 'title', 'memo', 'historico', 'lancamento', 'categoria'].includes(h)
  );
  const docIdx = norm.findIndex(
    (h) => h.includes('docto') || h.includes('documento') || h === 'doc' || h.includes('referencia')
  );

  return { dateIdx, valueIdx, creditIdx, debitIdx, descIdx, docIdx };
}

function parseCSV(text) {
  // Remove BOM (comum em CSV exportado de internet banking/Excel).
  const semLinhas = text.replace(/^﻿/, '').split(/\r\n|\n|\r/);

  const semiCount = (text.match(/;/g) || []).length;
  const commaCount = (text.match(/,/g) || []).length;
  const delimiter = semiCount > commaCount ? ';' : ',';

  const resultado = [];
  let mapping = null;

  for (const linha of semLinhas) {
    if (!linha.trim()) continue;
    const cols = splitCSVLine(linha, delimiter);

    const possivelCabecalho = detectCsvHeader(cols);
    if (possivelCabecalho) {
      mapping = possivelCabecalho;
      continue;
    }
    if (!mapping) continue;

    const dataISO = csvDateToISO(cols[mapping.dateIdx]);
    if (!dataISO) continue;

    let valor;
    let tipo;
    if (mapping.valueIdx !== -1) {
      const bruto = parseLocaleNumber(cols[mapping.valueIdx]);
      valor = Math.abs(bruto);
      tipo = bruto < 0 ? 'saida' : 'entrada';
    } else {
      const credito = mapping.creditIdx !== -1 ? parseLocaleNumber(cols[mapping.creditIdx]) : 0;
      const debito = mapping.debitIdx !== -1 ? parseLocaleNumber(cols[mapping.debitIdx]) : 0;
      if (credito > 0) {
        valor = credito;
        tipo = 'entrada';
      } else {
        valor = debito;
        tipo = 'saida';
      }
    }
    if (!Number.isFinite(valor) || valor <= 0) continue;

    const descricao = mapping.descIdx !== -1 ? String(cols[mapping.descIdx] || '').trim() : '';
    const doc = mapping.docIdx !== -1 ? String(cols[mapping.docIdx] || '').trim() : '';

    resultado.push({
      data: dataISO,
      valor,
      tipo,
      descricao,
      // Combina data + nº do documento: identifica bem a transação mesmo
      // quando o número em si se repete em datas diferentes, e evita tratar
      // como duplicatas transações distintas com mesmo valor/descrição no
      // mesmo dia (ex. duas compras de R$ 4,60 no cartão no mesmo dia).
      fitid: doc ? `${dataISO}:${doc}` : null,
    });
  }

  return resultado;
}

function showImportExtratoStatus(text, isError) {
  importExtratoStatus.hidden = false;
  importExtratoStatus.textContent = text;
  importExtratoStatus.classList.toggle('error', !!isError);
}

// A conta faz parte da identidade da transação: importar o mesmo extrato em
// duas contas diferentes (por engano ou de propósito) não deve ser tratado
// como duplicata de si mesmo.
function transacaoFingerprint(t) {
  return t.fitid
    ? `fit:${t.contaId}:${t.fitid}`
    : `fp:${t.contaId}:${t.data}|${t.valor.toFixed(2)}|${t.tipo}|${(t.descricao || '').trim()}`;
}

importExtratoInput.addEventListener('change', () => {
  const file = importExtratoInput.files[0];
  if (!file) return;

  const contaId = importExtratoContaSelect.value;
  if (!contaId) {
    showImportExtratoStatus('Cadastre uma conta em "Contas" antes de importar um extrato.', true);
    importExtratoInput.value = '';
    return;
  }

  const reader = new FileReader();
  reader.onload = () => {
    const text = String(reader.result);
    const isOFX = /\.(ofx|qfx)$/i.test(file.name) || /<OFX>/i.test(text);
    const parsed = isOFX ? parseOFX(text) : parseCSV(text);

    if (!parsed.length) {
      showImportExtratoStatus(
        'Não foi possível encontrar transações neste arquivo. Verifique se é um .ofx/.qfx do internet banking ou um .csv com colunas de data, valor e descrição.',
        true
      );
      importExtratoInput.value = '';
      return;
    }

    const existingFingerprints = new Set(data.transacoes.map(transacaoFingerprint));
    const seenInBatch = new Set();
    let added = 0;
    let skipped = 0;

    for (const t of parsed) {
      const key = transacaoFingerprint({ ...t, contaId });
      if (existingFingerprints.has(key) || seenInBatch.has(key)) {
        skipped++;
        continue;
      }
      seenInBatch.add(key);
      data.transacoes.push({
        id: crypto.randomUUID(),
        criadoEm: new Date().toISOString(),
        tipo: t.tipo,
        valor: t.valor,
        categoria: 'A categorizar',
        descricao: t.descricao || '',
        data: t.data,
        contaId,
        fitid: t.fitid || undefined,
      });
      added++;
    }

    ultimaContaUsada = contaId;
    saveData(data);
    render();
    const addedText =
      added === 1 ? '1 transação importada.' : `${added} transações importadas.`;
    const skippedText =
      skipped === 0
        ? ''
        : skipped === 1
        ? ' 1 já existia e foi ignorada.'
        : ` ${skipped} já existiam e foram ignoradas.`;
    showImportExtratoStatus(
      added > 0
        ? addedText + skippedText
        : `Nenhuma transação nova: todas as ${skipped} já tinham sido importadas antes.`,
      false
    );
    importExtratoInput.value = '';
  };
  reader.readAsText(file);
});

// ==============================================
// Consultor com IA (Anthropic API, chave própria do usuário)
// ==============================================
const API_KEY_STORAGE = 'meuFinanceiro.apiKey';

function getApiKey() {
  return localStorage.getItem(API_KEY_STORAGE) || '';
}

apiKeySaveBtn.addEventListener('click', () => {
  const key = apiKeyInput.value.trim();
  if (!key) return;
  localStorage.setItem(API_KEY_STORAGE, key);
  apiKeyInput.value = '';
  apiKeyStatus.hidden = false;
  apiKeyStatus.classList.remove('error');
  apiKeyStatus.textContent = 'Chave salva neste celular.';
});

apiKeyClearBtn.addEventListener('click', () => {
  localStorage.removeItem(API_KEY_STORAGE);
  apiKeyInput.value = '';
  apiKeyStatus.hidden = false;
  apiKeyStatus.classList.remove('error');
  apiKeyStatus.textContent = 'Chave removida.';
});

function buildResumoParaIA() {
  const now = new Date();
  const mesAtual = totaisDoMes(now);
  const mesAnterior = totaisDoMes(new Date(now.getFullYear(), now.getMonth() - 1, 1));
  const gastosPorCategoria = gastosPorCategoriaNoMes(now);
  const entradasCategoria = Object.entries(gastosPorCategoria).sort((a, b) => b[1] - a[1]);

  const linhas = [];
  linhas.push(`Saldo atual: ${formatCurrency(computeSaldo())}`);
  linhas.push('');
  linhas.push(`Mês atual (${MONTH_NAMES[now.getMonth()]}/${now.getFullYear()}):`);
  linhas.push(`- Receitas: ${formatCurrency(mesAtual.receitas)}`);
  linhas.push(`- Despesas: ${formatCurrency(mesAtual.despesas)}`);
  linhas.push(
    `Mês anterior: receitas ${formatCurrency(mesAnterior.receitas)}, despesas ${formatCurrency(mesAnterior.despesas)}`
  );
  linhas.push('');
  linhas.push('Despesas do mês atual por categoria:');
  if (entradasCategoria.length === 0) linhas.push('(nenhuma despesa registrada este mês)');
  for (const [categoria, valor] of entradasCategoria) {
    linhas.push(`- ${categoria}: ${formatCurrency(valor)}`);
  }

  if (data.orcamentos.length > 0) {
    linhas.push('');
    linhas.push('Orçamentos mensais definidos:');
    for (const o of data.orcamentos) {
      const gasto = gastosPorCategoria[o.categoria] || 0;
      linhas.push(`- ${o.categoria}: gastou ${formatCurrency(gasto)} de um limite de ${formatCurrency(o.limite)}`);
    }
  }

  if (data.contas.length > 1) {
    linhas.push('');
    linhas.push('Contas e cartões:');
    for (const c of data.contas) {
      if (c.tipo === 'cartao') {
        linhas.push(`- ${c.nome} (cartão de crédito): dívida atual ${formatCurrency(computeDividaCartao(c.id))}`);
      } else {
        linhas.push(`- ${c.nome} (conta): saldo ${formatCurrency(saldoDaConta(c.id))}`);
      }
    }
  }

  linhas.push('');
  linhas.push('Despesas totais dos últimos 6 meses:');
  for (let i = 5; i >= 0; i--) {
    const m = new Date(now.getFullYear(), now.getMonth() - i, 1);
    linhas.push(`- ${MONTH_NAMES[m.getMonth()]}/${m.getFullYear()}: ${formatCurrency(totaisDoMes(m).despesas)}`);
  }

  return linhas.join('\n');
}

function escapeHTML(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// Renderização mínima e segura de markdown simples (parágrafos, listas com
// "-", **negrito**) devolvido pela IA: o texto é sempre escapado antes de
// qualquer tag ser inserida, então não há risco de HTML vindo da resposta.
function renderAdvisorText(texto) {
  const container = document.createElement('div');
  container.className = 'advisor-text';

  const negrito = (s) => escapeHTML(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  for (const bloco of texto.split(/\n{2,}/)) {
    const linhasBloco = bloco.split('\n').filter((l) => l.trim() !== '');
    const éLista = linhasBloco.length > 0 && linhasBloco.every((l) => /^[-*•]\s+/.test(l.trim()));

    if (éLista) {
      const ul = document.createElement('ul');
      for (const linha of linhasBloco) {
        const li = document.createElement('li');
        li.innerHTML = negrito(linha.trim().replace(/^[-*•]\s+/, ''));
        ul.appendChild(li);
      }
      container.appendChild(ul);
    } else if (bloco.trim()) {
      const p = document.createElement('p');
      p.innerHTML = negrito(bloco.trim());
      container.appendChild(p);
    }
  }

  return container;
}

async function runAdvisor() {
  const apiKey = getApiKey();
  if (!apiKey) {
    advisorResult.hidden = false;
    advisorResult.innerHTML = '<p class="advisor-empty">Configure sua chave da API da Anthropic em Configurações ⚙ para usar o consultor com IA.</p>';
    return;
  }

  advisorBtn.disabled = true;
  advisorBtn.textContent = 'Analisando…';
  advisorResult.hidden = false;
  advisorResult.innerHTML = '<p class="advisor-loading">Analisando seus dados…</p>';

  try {
    const resposta = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true',
      },
      body: JSON.stringify({
        model: 'claude-sonnet-5',
        max_tokens: 1024,
        output_config: { effort: 'medium' },
        system:
          'Você é um consultor financeiro pessoal, direto e prático, falando em português do Brasil. ' +
          'Analise o resumo financeiro do usuário e responda em 2-4 parágrafos ou tópicos curtos com: ' +
          '1) um diagnóstico rápido do mês; 2) pontos de atenção específicos (orçamentos estourados, ' +
          'categorias que cresceram); 3) 2-3 sugestões concretas e realistas de economia. Seja objetivo, ' +
          'sem disclaimers genéricos nem recomendações vagas.',
        messages: [{ role: 'user', content: buildResumoParaIA() }],
      }),
    });

    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => null);
      throw new Error(erro?.error?.message || `Erro ${resposta.status}`);
    }

    const json = await resposta.json();
    const texto = (json.content || [])
      .filter((b) => b.type === 'text')
      .map((b) => b.text)
      .join('\n');

    advisorResult.innerHTML = '';
    advisorResult.appendChild(renderAdvisorText(texto || 'Não foi possível gerar uma análise.'));
  } catch (err) {
    const p = document.createElement('p');
    p.className = 'advisor-error';
    p.textContent = `Não foi possível consultar a IA: ${err.message || err}`;
    advisorResult.innerHTML = '';
    advisorResult.appendChild(p);
  } finally {
    advisorBtn.disabled = false;
    advisorBtn.textContent = '🤖 Analisar com IA';
  }
}

advisorBtn.addEventListener('click', runAdvisor);

wipeBtn.addEventListener('click', () => {
  const confirmado = window.confirm(
    'Tem certeza? Isso vai apagar todas as transações e orçamentos deste celular. Essa ação não pode ser desfeita.'
  );
  if (!confirmado) return;
  data = {
    transacoes: [],
    orcamentos: [],
    contas: [contaPadraoUnica()],
    categoriaGrupos: migrarCategoriaGrupos(),
  };
  extratoContaFiltro = null;
  ultimaContaUsada = data.contas[0].id;
  saveData(data);
  render();
  settingsDialog.close();
});

// ==============================================
// Estatísticas (saldo, receitas/despesas do mês e comparação)
// ==============================================
function setDeltaText(el, pct, upIsGood) {
  if (pct === null) {
    el.textContent = '';
    el.className = 'stat-delta';
    return;
  }
  if (pct === 0) {
    el.textContent = 'Igual ao mês passado';
    el.className = 'stat-delta';
    return;
  }
  const isUp = pct > 0;
  const isGood = isUp === upIsGood;
  const arrow = isUp ? '▲' : '▼';
  el.textContent = `${arrow} ${Math.abs(pct).toFixed(0)}% vs. mês passado`;
  el.className = `stat-delta ${isGood ? 'up' : 'down'}`;
}

function renderStats() {
  const saldo = computeSaldo();
  balanceValue.textContent = formatCurrency(saldo);
  balanceValue.classList.toggle('negative', saldo < 0);

  const now = new Date();
  const mesAtual = totaisDoMes(now);
  const mesAnterior = totaisDoMes(new Date(now.getFullYear(), now.getMonth() - 1, 1));
  const netMes = mesAtual.receitas - mesAtual.despesas;

  balanceDelta.textContent = `${formatSignedCurrency(netMes)} este mês`;
  balanceDelta.className = `stat-delta${netMes > 0 ? ' up' : netMes < 0 ? ' down' : ''}`;

  receitasMesValue.textContent = formatCurrency(mesAtual.receitas);
  setDeltaText(receitasMesDelta, pctChange(mesAtual.receitas, mesAnterior.receitas), true);

  despesasMesValue.textContent = formatCurrency(mesAtual.despesas);
  setDeltaText(despesasMesDelta, pctChange(mesAtual.despesas, mesAnterior.despesas), false);
}

// ==============================================
// Tendência: despesas nos últimos 6 meses
// ==============================================
function renderTrend() {
  const now = new Date();
  const meses = [];
  for (let i = 5; i >= 0; i--) {
    meses.push(new Date(now.getFullYear(), now.getMonth() - i, 1));
  }
  const totais = meses.map((m) => totaisDoMes(m).despesas);
  const max = Math.max(...totais, 1);

  trendChart.innerHTML = '';
  meses.forEach((m, i) => {
    const despesas = totais[i];
    const isCurrent = i === meses.length - 1;

    const col = document.createElement('div');
    col.className = 'trend-col';

    const value = document.createElement('span');
    value.className = 'trend-value';
    value.textContent = despesas.toLocaleString('pt-BR', {
      style: 'currency',
      currency: 'BRL',
      maximumFractionDigits: 0,
    });

    const bar = document.createElement('div');
    bar.className = `trend-bar${isCurrent ? ' current' : ''}`;
    bar.style.height = `${(despesas / max) * 100}%`;

    const label = document.createElement('span');
    label.className = 'trend-label';
    label.textContent = MONTH_NAMES[m.getMonth()].slice(0, 3);

    col.append(value, bar, label);
    trendChart.appendChild(col);
  });
}

// ==============================================
// Render geral
// ==============================================
function render() {
  renderStats();
  renderExtrato();
  renderContas();
  renderOrcamentos();
  renderRelatorio();
}

darkModeQuery.addEventListener('change', render);

render();

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  });
}
