const STORAGE_KEY = 'meuFinanceiro.dados';

const CHART_COLORS = [
  '#c9a227', '#3d7a5c', '#7c2d3a', '#2c5c8a',
  '#8a5a2b', '#5c3a5c', '#3d5c52', '#a4342c',
];

const balanceValue = document.getElementById('balance-value');

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

function loadData() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return {
      transacoes: Array.isArray(parsed && parsed.transacoes) ? parsed.transacoes : [],
      orcamentos: Array.isArray(parsed && parsed.orcamentos) ? parsed.orcamentos : [],
    };
  } catch {
    return { transacoes: [], orcamentos: [] };
  }
}

function saveData(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

let data = loadData();

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
  let hash = 0;
  for (let i = 0; i < categoria.length; i++) {
    hash = (hash * 31 + categoria.charCodeAt(i)) >>> 0;
  }
  return CHART_COLORS[hash % CHART_COLORS.length];
}

function computeSaldo() {
  return data.transacoes.reduce(
    (sum, t) => sum + (t.tipo === 'entrada' ? t.valor : -t.valor),
    0
  );
}

function gastosPorCategoriaNoMes(monthDate) {
  const y = monthDate.getFullYear();
  const m = monthDate.getMonth();
  const totals = {};
  for (const t of data.transacoes) {
    if (t.tipo !== 'saida') continue;
    const d = new Date(`${t.data}T00:00:00`);
    if (d.getFullYear() !== y || d.getMonth() !== m) continue;
    totals[t.categoria] = (totals[t.categoria] || 0) + t.valor;
  }
  return totals;
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
function openTransacaoDialog(transacao) {
  transacaoForm.reset();
  setTipo('saida');

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
  };

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

function renderExtrato() {
  const transacoes = [...data.transacoes].sort((a, b) => {
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

    const info = document.createElement('div');
    info.className = 'transacao-info';
    const cat = document.createElement('div');
    cat.className = 'transacao-categoria';
    cat.textContent = t.categoria;
    info.appendChild(cat);
    if (t.descricao) {
      const desc = document.createElement('div');
      desc.className = 'transacao-descricao';
      desc.textContent = t.descricao;
      info.appendChild(desc);
    }
    const date = document.createElement('div');
    date.className = 'transacao-data';
    date.textContent = formatDateShort(t.data);
    info.appendChild(date);

    const valor = document.createElement('div');
    valor.className = `transacao-valor ${t.tipo}`;
    valor.textContent = `${t.tipo === 'entrada' ? '+' : '-'} ${formatCurrency(t.valor)}`;

    li.append(info, valor);
    li.addEventListener('click', () => openTransacaoDialog(t));
    transacaoList.appendChild(li);
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
    const cat = document.createElement('span');
    cat.textContent = o.categoria;
    const valores = document.createElement('span');
    valores.className = `orcamento-valores ${status}`;
    valores.textContent = `${formatCurrency(gasto)} / ${formatCurrency(o.limite)}`;
    header.append(cat, valores);

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
  monthLabel.textContent = `${MONTH_NAMES[reportMonth.getMonth()]} ${reportMonth.getFullYear()}`;

  const totals = gastosPorCategoriaNoMes(reportMonth);
  const entries = Object.entries(totals).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);

  relatorioEmpty.hidden = entries.length > 0;
  relatorioContent.hidden = entries.length === 0;
  if (entries.length === 0) return;

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

// ==============================================
// Backup: exportar / importar / apagar
// ==============================================
settingsBtn.addEventListener('click', () => {
  importStatus.hidden = true;
  importInput.value = '';
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
      data = { transacoes: parsed.transacoes, orcamentos: parsed.orcamentos };
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

wipeBtn.addEventListener('click', () => {
  const confirmado = window.confirm(
    'Tem certeza? Isso vai apagar todas as transações e orçamentos deste celular. Essa ação não pode ser desfeita.'
  );
  if (!confirmado) return;
  data = { transacoes: [], orcamentos: [] };
  saveData(data);
  render();
  settingsDialog.close();
});

// ==============================================
// Render geral
// ==============================================
function render() {
  balanceValue.textContent = formatCurrency(computeSaldo());
  balanceValue.classList.toggle('negative', computeSaldo() < 0);
  renderExtrato();
  renderOrcamentos();
  renderRelatorio();
}

render();

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  });
}
