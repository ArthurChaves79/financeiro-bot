const STORAGE_KEY = 'condominioRI.dados';

const DOC_TIPOS = {
  auto_vistoria: 'Auto de vistoria',
  quadro_areas: 'Quadro de áreas',
  especificacao: 'Especificação',
  convencao: 'Convenção',
  plantas: 'Plantas',
  outros: 'Outros',
};

// ==============================================
// Persistência
// ==============================================
function loadData() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return { condominios: Array.isArray(parsed && parsed.condominios) ? parsed.condominios : [] };
  } catch {
    return { condominios: [] };
  }
}

function saveData(d) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(d));
}

let data = loadData();
let currentView = 'lista';
let currentCondoId = null;

function uid() {
  return crypto.randomUUID();
}

function getCondo(id) {
  return data.condominios.find((c) => c.id === id) || null;
}

function novoCondominio() {
  return {
    id: uid(),
    criadoEm: new Date().toISOString(),
    nome: '',
    endereco: { logradouro: '', numero: '', bairro: '', cidade: '', uf: '', cep: '' },
    registro: { tipo: 'matricula', matricula: '', transcricoes: [] },
    pastas: [],
    livros: {
      incorporacao: { livro: '', numero: '', folha: '', data: '' },
      especificacao: { livro: '', numero: '', folha: '', data: '' },
      convencao: { livro: '', numero: '', folha: '', tipo: 'integral', data: '' },
    },
    documentos: [],
    unidades: [],
    observacoes: '',
  };
}

// ==============================================
// Elementos
// ==============================================
const views = document.querySelectorAll('.view');

const buscaInput = document.getElementById('busca-input');
const listaEmpty = document.getElementById('lista-empty');
const condominioList = document.getElementById('condominio-list');
const addBtn = document.getElementById('add-btn');
const emptyAddBtn = document.getElementById('empty-add-btn');
const voltarBtn = document.getElementById('voltar-btn');

const detalheNome = document.getElementById('detalhe-nome');
const detalheEndereco = document.getElementById('detalhe-endereco');
const editarCondominioBtn = document.getElementById('editar-condominio-btn');
const excluirCondominioBtn = document.getElementById('excluir-condominio-btn');

const registroResumo = document.getElementById('registro-resumo');
const editarRegistroBtn = document.getElementById('editar-registro-btn');

const pastaList = document.getElementById('pasta-list');
const pastaEmpty = document.getElementById('pasta-empty');
const addPastaBtn = document.getElementById('add-pasta-btn');

const livrosResumo = document.getElementById('livros-resumo');
const editarLivrosBtn = document.getElementById('editar-livros-btn');

const documentoList = document.getElementById('documento-list');
const documentoEmpty = document.getElementById('documento-empty');
const addDocumentoBtn = document.getElementById('add-documento-btn');

const unidadeList = document.getElementById('unidade-list');
const unidadeEmpty = document.getElementById('unidade-empty');
const addUnidadeBtn = document.getElementById('add-unidade-btn');

const observacoesTexto = document.getElementById('observacoes-texto');
const editarObservacoesBtn = document.getElementById('editar-observacoes-btn');

const exportarHtmlBtn = document.getElementById('exportar-html-btn');

// Dialogs: condomínio
const condominioDialog = document.getElementById('condominio-dialog');
const condominioForm = document.getElementById('condominio-form');
const condominioDialogTitle = document.getElementById('condominio-dialog-title');
const condominioCancelBtn = document.getElementById('condominio-cancel-btn');
const cId = document.getElementById('c-id');
const cNome = document.getElementById('c-nome');
const cLogradouro = document.getElementById('c-logradouro');
const cNumero = document.getElementById('c-numero');
const cBairro = document.getElementById('c-bairro');
const cCidade = document.getElementById('c-cidade');
const cUf = document.getElementById('c-uf');
const cCep = document.getElementById('c-cep');

// Dialog: registro
const registroDialog = document.getElementById('registro-dialog');
const registroForm = document.getElementById('registro-form');
const registroCancelBtn = document.getElementById('registro-cancel-btn');
const registroTipoToggle = document.getElementById('registro-tipo-toggle');
const registroTipoBtns = registroTipoToggle.querySelectorAll('.tipo-btn');
const registroMatriculaCampo = document.getElementById('registro-matricula-campo');
const registroTranscricaoCampo = document.getElementById('registro-transcricao-campo');
const rMatricula = document.getElementById('r-matricula');
const rTranscricoes = document.getElementById('r-transcricoes');

// Dialog: pasta
const pastaDialog = document.getElementById('pasta-dialog');
const pastaForm = document.getElementById('pasta-form');
const pastaDialogTitle = document.getElementById('pasta-dialog-title');
const pastaCancelBtn = document.getElementById('pasta-cancel-btn');
const pastaDeleteBtn = document.getElementById('pasta-delete-btn');
const pId = document.getElementById('p-id');
const pNumero = document.getElementById('p-numero');
const pDescricao = document.getElementById('p-descricao');

// Dialog: livros
const livrosDialog = document.getElementById('livros-dialog');
const livrosForm = document.getElementById('livros-form');
const livrosCancelBtn = document.getElementById('livros-cancel-btn');
const lIncLivro = document.getElementById('l-inc-livro');
const lIncNumero = document.getElementById('l-inc-numero');
const lIncFolha = document.getElementById('l-inc-folha');
const lIncData = document.getElementById('l-inc-data');
const lEspLivro = document.getElementById('l-esp-livro');
const lEspNumero = document.getElementById('l-esp-numero');
const lEspFolha = document.getElementById('l-esp-folha');
const lEspData = document.getElementById('l-esp-data');
const lConvLivro = document.getElementById('l-conv-livro');
const lConvNumero = document.getElementById('l-conv-numero');
const lConvFolha = document.getElementById('l-conv-folha');
const lConvTipo = document.getElementById('l-conv-tipo');
const lConvData = document.getElementById('l-conv-data');

// Dialog: documento
const documentoDialog = document.getElementById('documento-dialog');
const documentoForm = document.getElementById('documento-form');
const documentoDialogTitle = document.getElementById('documento-dialog-title');
const documentoCancelBtn = document.getElementById('documento-cancel-btn');
const documentoDeleteBtn = document.getElementById('documento-delete-btn');
const dId = document.getElementById('d-id');
const dTipo = document.getElementById('d-tipo');
const dDescricao = document.getElementById('d-descricao');
const dPasta = document.getElementById('d-pasta');
const pastaOptions = document.getElementById('pasta-options');
const dData = document.getElementById('d-data');

// Dialog: unidade
const unidadeDialog = document.getElementById('unidade-dialog');
const unidadeForm = document.getElementById('unidade-form');
const unidadeDialogTitle = document.getElementById('unidade-dialog-title');
const unidadeCancelBtn = document.getElementById('unidade-cancel-btn');
const unidadeDeleteBtn = document.getElementById('unidade-delete-btn');
const unidadeTipoToggle = document.getElementById('unidade-tipo-toggle');
const unidadeTipoBtns = unidadeTipoToggle.querySelectorAll('.tipo-btn');
const uId = document.getElementById('u-id');
const uNumero = document.getElementById('u-numero');
const uRegistro = document.getElementById('u-registro');
const uFracao = document.getElementById('u-fracao');

// Dialog: observações
const observacoesDialog = document.getElementById('observacoes-dialog');
const observacoesForm = document.getElementById('observacoes-form');
const observacoesCancelBtn = document.getElementById('observacoes-cancel-btn');
const oTexto = document.getElementById('o-texto');

// Dialog: configurações
const settingsBtn = document.getElementById('settings-btn');
const settingsDialog = document.getElementById('settings-dialog');
const settingsCloseBtn = document.getElementById('settings-close-btn');
const exportBtn = document.getElementById('export-btn');
const importInput = document.getElementById('import-input');
const importStatus = document.getElementById('import-status');
const wipeBtn = document.getElementById('wipe-btn');

// ==============================================
// Navegação
// ==============================================
function showView(view) {
  currentView = view;
  views.forEach((v) => v.classList.toggle('active', v.id === `view-${view}`));
}

function abrirDetalhe(id) {
  currentCondoId = id;
  showView('detalhe');
  renderDetalhe();
}

voltarBtn.addEventListener('click', () => {
  currentCondoId = null;
  showView('lista');
  renderLista();
});

// ==============================================
// Utilidades de formatação
// ==============================================
function formatDateShort(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

function enderecoLinha(endereco) {
  if (!endereco) return '';
  const partes = [];
  if (endereco.logradouro) partes.push(`${endereco.logradouro}${endereco.numero ? ', ' + endereco.numero : ''}`);
  if (endereco.bairro) partes.push(endereco.bairro);
  const cidadeUf = [endereco.cidade, endereco.uf].filter(Boolean).join('/');
  if (cidadeUf) partes.push(cidadeUf);
  return partes.join(' — ');
}

function registroBadge(registro) {
  if (!registro) return '';
  if (registro.tipo === 'matricula') {
    return registro.matricula ? `Matrícula ${registro.matricula}` : 'Matrícula (sem número)';
  }
  const n = (registro.transcricoes || []).length;
  return n > 0 ? `Transcrição (${n})` : 'Transcrição (sem número)';
}

// ==============================================
// Lista de condomínios
// ==============================================
function condominiosFiltrados() {
  const termo = buscaInput.value.trim().toLowerCase();
  const ordenados = [...data.condominios].sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
  if (!termo) return ordenados;
  return ordenados.filter((c) => {
    const alvo = [
      c.nome,
      enderecoLinha(c.endereco),
      c.registro?.matricula,
      ...(c.registro?.transcricoes || []),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    return alvo.includes(termo);
  });
}

function renderLista() {
  const lista = condominiosFiltrados();
  condominioList.innerHTML = '';
  listaEmpty.hidden = data.condominios.length > 0;

  for (const c of lista) {
    const li = document.createElement('li');
    li.className = 'condominio-card';

    const nome = document.createElement('div');
    nome.className = 'condominio-card-nome';
    nome.textContent = c.nome || '(sem nome)';

    const endereco = document.createElement('div');
    endereco.className = 'condominio-card-endereco';
    endereco.textContent = enderecoLinha(c.endereco) || 'Endereço não informado';

    const meta = document.createElement('div');
    meta.className = 'condominio-card-meta';
    const badgeRegistro = document.createElement('span');
    badgeRegistro.className = 'badge';
    badgeRegistro.textContent = registroBadge(c.registro);
    meta.appendChild(badgeRegistro);
    if (c.unidades.length > 0) {
      const badgeUnidades = document.createElement('span');
      badgeUnidades.className = 'badge';
      badgeUnidades.textContent = `${c.unidades.length} unidade${c.unidades.length > 1 ? 's' : ''}`;
      meta.appendChild(badgeUnidades);
    }

    li.append(nome, endereco, meta);
    li.addEventListener('click', () => abrirDetalhe(c.id));
    condominioList.appendChild(li);
  }
}

buscaInput.addEventListener('input', renderLista);

// ==============================================
// Dialog: condomínio (dados gerais)
// ==============================================
function openCondominioDialog(condo) {
  condominioForm.reset();
  if (condo) {
    condominioDialogTitle.textContent = 'Editar condomínio';
    cId.value = condo.id;
    cNome.value = condo.nome;
    cLogradouro.value = condo.endereco.logradouro;
    cNumero.value = condo.endereco.numero;
    cBairro.value = condo.endereco.bairro;
    cCidade.value = condo.endereco.cidade;
    cUf.value = condo.endereco.uf;
    cCep.value = condo.endereco.cep;
  } else {
    condominioDialogTitle.textContent = 'Novo condomínio';
    cId.value = '';
  }
  condominioDialog.showModal();
  cNome.focus();
}

addBtn.addEventListener('click', () => openCondominioDialog(null));
emptyAddBtn.addEventListener('click', () => openCondominioDialog(null));
condominioCancelBtn.addEventListener('click', () => condominioDialog.close());
editarCondominioBtn.addEventListener('click', () => openCondominioDialog(getCondo(currentCondoId)));

condominioForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const nome = cNome.value.trim();
  if (!nome) return;

  const endereco = {
    logradouro: cLogradouro.value.trim(),
    numero: cNumero.value.trim(),
    bairro: cBairro.value.trim(),
    cidade: cCidade.value.trim(),
    uf: cUf.value.trim().toUpperCase(),
    cep: cCep.value.trim(),
  };

  const isNew = !cId.value;

  if (!isNew) {
    const condo = getCondo(cId.value);
    condo.nome = nome;
    condo.endereco = endereco;
  } else {
    const condo = novoCondominio();
    condo.nome = nome;
    condo.endereco = endereco;
    data.condominios.push(condo);
    currentCondoId = condo.id;
  }

  saveData(data);
  condominioDialog.close();

  if (isNew) {
    abrirDetalhe(currentCondoId);
  } else if (currentView === 'detalhe') {
    renderDetalhe();
  } else {
    renderLista();
  }
});

excluirCondominioBtn.addEventListener('click', () => {
  const condo = getCondo(currentCondoId);
  if (!condo) return;
  const ok = window.confirm(`Excluir o condomínio "${condo.nome}"? Essa ação não pode ser desfeita.`);
  if (!ok) return;
  data.condominios = data.condominios.filter((c) => c.id !== currentCondoId);
  saveData(data);
  currentCondoId = null;
  showView('lista');
  renderLista();
});

// ==============================================
// Renderização do detalhe
// ==============================================
function renderDetalhe() {
  const condo = getCondo(currentCondoId);
  if (!condo) {
    showView('lista');
    renderLista();
    return;
  }

  detalheNome.textContent = condo.nome || '(sem nome)';
  detalheEndereco.textContent = enderecoLinha(condo.endereco) || 'Endereço não informado';

  renderRegistroResumo(condo);
  renderPastas(condo);
  renderLivrosResumo(condo);
  renderDocumentos(condo);
  renderUnidades(condo);

  observacoesTexto.textContent = condo.observacoes || 'Nenhuma observação registrada.';
}

function renderRegistroResumo(condo) {
  const r = condo.registro;
  registroResumo.innerHTML = '';
  const dl = document.createElement('dl');

  const addRow = (dt, dd) => {
    const t = document.createElement('dt');
    t.textContent = dt;
    const d = document.createElement('dd');
    d.textContent = dd;
    dl.append(t, d);
  };

  if (r.tipo === 'matricula') {
    addRow('Tipo', 'Matrícula (única)');
    addRow('Número', r.matricula || '—');
  } else {
    addRow('Tipo', 'Transcrição');
    addRow('Número(s)', (r.transcricoes || []).length ? r.transcricoes.join(', ') : '—');
  }

  registroResumo.appendChild(dl);
}

editarRegistroBtn.addEventListener('click', () => {
  const condo = getCondo(currentCondoId);
  setRegistroTipo(condo.registro.tipo || 'matricula');
  rMatricula.value = condo.registro.matricula || '';
  rTranscricoes.value = (condo.registro.transcricoes || []).join('\n');
  registroDialog.showModal();
});

function setRegistroTipo(tipo) {
  registroTipoToggle.dataset.value = tipo;
  registroTipoBtns.forEach((b) => b.classList.toggle('active', b.dataset.value === tipo));
  registroMatriculaCampo.hidden = tipo !== 'matricula';
  registroTranscricaoCampo.hidden = tipo !== 'transcricao';
}

registroTipoBtns.forEach((btn) => {
  btn.addEventListener('click', () => setRegistroTipo(btn.dataset.value));
});

registroCancelBtn.addEventListener('click', () => registroDialog.close());

registroForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const condo = getCondo(currentCondoId);
  const tipo = registroTipoToggle.dataset.value;
  if (tipo === 'matricula') {
    condo.registro = { tipo, matricula: rMatricula.value.trim(), transcricoes: [] };
  } else {
    const transcricoes = rTranscricoes.value
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean);
    condo.registro = { tipo, matricula: '', transcricoes };
  }
  saveData(data);
  registroDialog.close();
  renderDetalhe();
});

// ==============================================
// Pastas
// ==============================================
function renderPastas(condo) {
  pastaList.innerHTML = '';
  pastaEmpty.hidden = condo.pastas.length > 0;

  pastaOptions.innerHTML = '';

  for (const p of condo.pastas) {
    const li = document.createElement('li');
    li.className = 'chip';
    const num = document.createElement('span');
    num.className = 'chip-numero';
    num.textContent = p.numero;
    li.appendChild(num);
    if (p.descricao) {
      const desc = document.createElement('span');
      desc.className = 'chip-descricao';
      desc.textContent = `· ${p.descricao}`;
      li.appendChild(desc);
    }
    li.addEventListener('click', () => openPastaDialog(p));
    pastaList.appendChild(li);

    const opt = document.createElement('option');
    opt.value = p.numero;
    pastaOptions.appendChild(opt);
  }
}

function openPastaDialog(pasta) {
  pastaForm.reset();
  if (pasta) {
    pastaDialogTitle.textContent = 'Editar pasta';
    pId.value = pasta.id;
    pNumero.value = pasta.numero;
    pDescricao.value = pasta.descricao || '';
    pastaDeleteBtn.hidden = false;
  } else {
    pastaDialogTitle.textContent = 'Nova pasta';
    pId.value = '';
    pastaDeleteBtn.hidden = true;
  }
  pastaDialog.showModal();
  pNumero.focus();
}

addPastaBtn.addEventListener('click', () => openPastaDialog(null));
pastaCancelBtn.addEventListener('click', () => pastaDialog.close());

pastaDeleteBtn.addEventListener('click', () => {
  const condo = getCondo(currentCondoId);
  condo.pastas = condo.pastas.filter((p) => p.id !== pId.value);
  saveData(data);
  pastaDialog.close();
  renderDetalhe();
});

pastaForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const numero = pNumero.value.trim();
  if (!numero) return;
  const condo = getCondo(currentCondoId);
  const descricao = pDescricao.value.trim();

  if (pId.value) {
    const pasta = condo.pastas.find((p) => p.id === pId.value);
    pasta.numero = numero;
    pasta.descricao = descricao;
  } else {
    condo.pastas.push({ id: uid(), numero, descricao });
  }

  saveData(data);
  pastaDialog.close();
  renderDetalhe();
});

// ==============================================
// Livros (incorporação / especificação / convenção)
// ==============================================
function renderLivrosResumo(condo) {
  const l = condo.livros;
  livrosResumo.innerHTML = '';

  const blocos = [
    { titulo: 'Incorporação', v: l.incorporacao },
    { titulo: 'Especificação', v: l.especificacao },
    {
      titulo: `Convenção${l.convencao.tipo === 'resumo' ? ' (resumo)' : ''}`,
      v: l.convencao,
    },
  ];

  const algum = blocos.some((b) => b.v.livro || b.v.numero || b.v.folha || b.v.data);
  if (!algum) {
    const p = document.createElement('p');
    p.className = 'empty-inline';
    p.textContent = 'Nenhum registro de livro informado.';
    livrosResumo.appendChild(p);
    return;
  }

  for (const b of blocos) {
    if (!b.v.livro && !b.v.numero && !b.v.folha && !b.v.data) continue;
    const div = document.createElement('div');
    div.className = 'livro-bloco';

    const titulo = document.createElement('div');
    titulo.className = 'livro-bloco-titulo';
    titulo.textContent = b.titulo;

    const dl = document.createElement('dl');
    const addRow = (dt, dd) => {
      if (!dd) return;
      const t = document.createElement('dt');
      t.textContent = dt;
      const d = document.createElement('dd');
      d.textContent = dd;
      dl.append(t, d);
    };
    addRow('Livro', b.v.livro);
    addRow('Número', b.v.numero);
    addRow('Folha', b.v.folha);
    addRow('Data', formatDateShort(b.v.data));

    div.append(titulo, dl);
    livrosResumo.appendChild(div);
  }
}

editarLivrosBtn.addEventListener('click', () => {
  const condo = getCondo(currentCondoId);
  const l = condo.livros;
  lIncLivro.value = l.incorporacao.livro || '';
  lIncNumero.value = l.incorporacao.numero || '';
  lIncFolha.value = l.incorporacao.folha || '';
  lIncData.value = l.incorporacao.data || '';
  lEspLivro.value = l.especificacao.livro || '';
  lEspNumero.value = l.especificacao.numero || '';
  lEspFolha.value = l.especificacao.folha || '';
  lEspData.value = l.especificacao.data || '';
  lConvLivro.value = l.convencao.livro || '';
  lConvNumero.value = l.convencao.numero || '';
  lConvFolha.value = l.convencao.folha || '';
  lConvTipo.value = l.convencao.tipo || 'integral';
  lConvData.value = l.convencao.data || '';
  livrosDialog.showModal();
});

livrosCancelBtn.addEventListener('click', () => livrosDialog.close());

livrosForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const condo = getCondo(currentCondoId);
  condo.livros = {
    incorporacao: {
      livro: lIncLivro.value.trim(),
      numero: lIncNumero.value.trim(),
      folha: lIncFolha.value.trim(),
      data: lIncData.value,
    },
    especificacao: {
      livro: lEspLivro.value.trim(),
      numero: lEspNumero.value.trim(),
      folha: lEspFolha.value.trim(),
      data: lEspData.value,
    },
    convencao: {
      livro: lConvLivro.value.trim(),
      numero: lConvNumero.value.trim(),
      folha: lConvFolha.value.trim(),
      tipo: lConvTipo.value,
      data: lConvData.value,
    },
  };
  saveData(data);
  livrosDialog.close();
  renderDetalhe();
});

// ==============================================
// Documentos
// ==============================================
function renderDocumentos(condo) {
  documentoList.innerHTML = '';
  documentoEmpty.hidden = condo.documentos.length > 0;

  const ordenados = [...condo.documentos].sort((a, b) =>
    DOC_TIPOS[a.tipo].localeCompare(DOC_TIPOS[b.tipo], 'pt-BR')
  );

  for (const doc of ordenados) {
    const li = document.createElement('li');
    li.className = 'registro-item';

    const info = document.createElement('div');
    info.className = 'registro-item-info';
    const titulo = document.createElement('div');
    titulo.className = 'registro-item-titulo';
    titulo.textContent = DOC_TIPOS[doc.tipo] || doc.tipo;
    info.appendChild(titulo);

    const subPartes = [];
    if (doc.descricao) subPartes.push(doc.descricao);
    if (doc.pasta) subPartes.push(`Pasta ${doc.pasta}`);
    if (doc.data) subPartes.push(formatDateShort(doc.data));
    if (subPartes.length) {
      const sub = document.createElement('div');
      sub.className = 'registro-item-sub';
      sub.textContent = subPartes.join(' · ');
      info.appendChild(sub);
    }

    li.appendChild(info);
    li.addEventListener('click', () => openDocumentoDialog(doc));
    documentoList.appendChild(li);
  }
}

function openDocumentoDialog(doc) {
  documentoForm.reset();
  if (doc) {
    documentoDialogTitle.textContent = 'Editar documento';
    dId.value = doc.id;
    dTipo.value = doc.tipo;
    dDescricao.value = doc.descricao || '';
    dPasta.value = doc.pasta || '';
    dData.value = doc.data || '';
    documentoDeleteBtn.hidden = false;
  } else {
    documentoDialogTitle.textContent = 'Novo documento';
    dId.value = '';
    documentoDeleteBtn.hidden = true;
  }
  documentoDialog.showModal();
}

addDocumentoBtn.addEventListener('click', () => openDocumentoDialog(null));
documentoCancelBtn.addEventListener('click', () => documentoDialog.close());

documentoDeleteBtn.addEventListener('click', () => {
  const condo = getCondo(currentCondoId);
  condo.documentos = condo.documentos.filter((d) => d.id !== dId.value);
  saveData(data);
  documentoDialog.close();
  renderDetalhe();
});

documentoForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const condo = getCondo(currentCondoId);
  const payload = {
    tipo: dTipo.value,
    descricao: dDescricao.value.trim(),
    pasta: dPasta.value.trim(),
    data: dData.value,
  };

  if (dId.value) {
    const doc = condo.documentos.find((d) => d.id === dId.value);
    Object.assign(doc, payload);
  } else {
    condo.documentos.push({ id: uid(), ...payload });
  }

  saveData(data);
  documentoDialog.close();
  renderDetalhe();
});

// ==============================================
// Unidades
// ==============================================
function renderUnidades(condo) {
  unidadeList.innerHTML = '';
  unidadeEmpty.hidden = condo.unidades.length > 0;

  const ordenadas = [...condo.unidades].sort((a, b) =>
    a.numero.localeCompare(b.numero, 'pt-BR', { numeric: true })
  );

  for (const u of ordenadas) {
    const li = document.createElement('li');
    li.className = 'registro-item';

    const info = document.createElement('div');
    info.className = 'registro-item-info';
    const titulo = document.createElement('div');
    titulo.className = 'registro-item-titulo';
    titulo.textContent = u.numero;
    info.appendChild(titulo);

    const subPartes = [];
    subPartes.push(u.registroTipo === 'transcricao' ? 'Transcrição' : 'Matrícula');
    if (u.registro) subPartes.push(u.registro);
    if (u.fracao) subPartes.push(`Fração ideal: ${u.fracao}`);
    const sub = document.createElement('div');
    sub.className = 'registro-item-sub';
    sub.textContent = subPartes.join(' · ');
    info.appendChild(sub);

    li.appendChild(info);
    li.addEventListener('click', () => openUnidadeDialog(u));
    unidadeList.appendChild(li);
  }
}

function setUnidadeTipo(tipo) {
  unidadeTipoToggle.dataset.value = tipo;
  unidadeTipoBtns.forEach((b) => b.classList.toggle('active', b.dataset.value === tipo));
}

unidadeTipoBtns.forEach((btn) => {
  btn.addEventListener('click', () => setUnidadeTipo(btn.dataset.value));
});

function openUnidadeDialog(unidade) {
  unidadeForm.reset();
  setUnidadeTipo('matricula');
  if (unidade) {
    unidadeDialogTitle.textContent = 'Editar unidade';
    uId.value = unidade.id;
    uNumero.value = unidade.numero;
    setUnidadeTipo(unidade.registroTipo || 'matricula');
    uRegistro.value = unidade.registro || '';
    uFracao.value = unidade.fracao || '';
    unidadeDeleteBtn.hidden = false;
  } else {
    unidadeDialogTitle.textContent = 'Nova unidade';
    uId.value = '';
    unidadeDeleteBtn.hidden = true;
  }
  unidadeDialog.showModal();
  uNumero.focus();
}

addUnidadeBtn.addEventListener('click', () => openUnidadeDialog(null));
unidadeCancelBtn.addEventListener('click', () => unidadeDialog.close());

unidadeDeleteBtn.addEventListener('click', () => {
  const condo = getCondo(currentCondoId);
  condo.unidades = condo.unidades.filter((u) => u.id !== uId.value);
  saveData(data);
  unidadeDialog.close();
  renderDetalhe();
});

unidadeForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const numero = uNumero.value.trim();
  if (!numero) return;
  const condo = getCondo(currentCondoId);
  const payload = {
    numero,
    registroTipo: unidadeTipoToggle.dataset.value,
    registro: uRegistro.value.trim(),
    fracao: uFracao.value.trim(),
  };

  if (uId.value) {
    const unidade = condo.unidades.find((u) => u.id === uId.value);
    Object.assign(unidade, payload);
  } else {
    condo.unidades.push({ id: uid(), ...payload });
  }

  saveData(data);
  unidadeDialog.close();
  renderDetalhe();
});

// ==============================================
// Observações
// ==============================================
editarObservacoesBtn.addEventListener('click', () => {
  const condo = getCondo(currentCondoId);
  oTexto.value = condo.observacoes || '';
  observacoesDialog.showModal();
  oTexto.focus();
});

observacoesCancelBtn.addEventListener('click', () => observacoesDialog.close());

observacoesForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const condo = getCondo(currentCondoId);
  condo.observacoes = oTexto.value.trim();
  saveData(data);
  observacoesDialog.close();
  renderDetalhe();
});

// ==============================================
// Exportar HTML do condomínio (para alimentar o SIG view)
// ==============================================
function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function livroLinha(v) {
  const partes = [];
  if (v.livro) partes.push(`Livro ${v.livro}`);
  if (v.numero) partes.push(`nº ${v.numero}`);
  if (v.folha) partes.push(`fl. ${v.folha}`);
  if (v.data) partes.push(formatDateShort(v.data));
  return partes.join(', ');
}

function gerarHtmlCondominio(condo) {
  const registroTexto =
    condo.registro.tipo === 'matricula'
      ? `Matrícula ${condo.registro.matricula || '(sem número)'}`
      : `Transcrição ${(condo.registro.transcricoes || []).join(', ') || '(sem número)'}`;

  const pastasHtml = condo.pastas.length
    ? `<ul>${condo.pastas.map((p) => `<li><strong>${escapeHtml(p.numero)}</strong>${p.descricao ? ' — ' + escapeHtml(p.descricao) : ''}</li>`).join('')}</ul>`
    : '<p><em>Nenhuma pasta cadastrada.</em></p>';

  const livrosLinhas = [
    condo.livros.incorporacao.livro || condo.livros.incorporacao.numero ? `<li><strong>Incorporação:</strong> ${escapeHtml(livroLinha(condo.livros.incorporacao))}</li>` : '',
    condo.livros.especificacao.livro || condo.livros.especificacao.numero ? `<li><strong>Especificação:</strong> ${escapeHtml(livroLinha(condo.livros.especificacao))}</li>` : '',
    condo.livros.convencao.livro || condo.livros.convencao.numero
      ? `<li><strong>Convenção${condo.livros.convencao.tipo === 'resumo' ? ' (resumo)' : ''}:</strong> ${escapeHtml(livroLinha(condo.livros.convencao))}</li>`
      : '',
  ].filter(Boolean);
  const livrosHtml = livrosLinhas.length ? `<ul>${livrosLinhas.join('')}</ul>` : '<p><em>Nenhum registro de livro informado.</em></p>';

  const documentosHtml = condo.documentos.length
    ? `<table><thead><tr><th>Tipo</th><th>Descrição</th><th>Pasta</th><th>Data</th></tr></thead><tbody>${condo.documentos
        .map(
          (d) =>
            `<tr><td>${escapeHtml(DOC_TIPOS[d.tipo] || d.tipo)}</td><td>${escapeHtml(d.descricao)}</td><td>${escapeHtml(d.pasta)}</td><td>${escapeHtml(formatDateShort(d.data))}</td></tr>`
        )
        .join('')}</tbody></table>`
    : '<p><em>Nenhum documento cadastrado.</em></p>';

  const unidadesHtml = condo.unidades.length
    ? `<table><thead><tr><th>Unidade</th><th>Registro</th><th>Fração ideal</th></tr></thead><tbody>${[...condo.unidades]
        .sort((a, b) => a.numero.localeCompare(b.numero, 'pt-BR', { numeric: true }))
        .map(
          (u) =>
            `<tr><td>${escapeHtml(u.numero)}</td><td>${u.registroTipo === 'transcricao' ? 'Transcrição' : 'Matrícula'} ${escapeHtml(u.registro)}</td><td>${escapeHtml(u.fracao)}</td></tr>`
        )
        .join('')}</tbody></table>`
    : '<p><em>Nenhuma unidade cadastrada.</em></p>';

  const dadosJson = JSON.stringify(condo, null, 2);

  return `<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<title>${escapeHtml(condo.nome)} — Condomínio RI</title>
<meta name="description" content="Ficha do condomínio para alimentar o SIG view (lotes-condomínio)" />
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1.25rem; color: #1c2620; line-height: 1.5; }
  h1 { font-size: 1.5rem; margin-bottom: 0.1rem; }
  h2 { font-size: 1.05rem; margin-top: 2rem; border-bottom: 1px solid #d8d0b8; padding-bottom: 0.3rem; }
  .endereco { color: #5a6b60; margin-top: 0; }
  table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
  th, td { text-align: left; padding: 0.4rem 0.5rem; border-bottom: 1px solid #e5dfc9; }
  th { color: #5a6b60; font-weight: 600; }
  ul { padding-left: 1.2rem; }
  .meta { color: #5a6b60; font-size: 0.85rem; }
  pre { background: #f4f1e8; border: 1px solid #d8d0b8; border-radius: 8px; padding: 0.9rem; overflow-x: auto; font-size: 0.78rem; }
</style>
</head>
<body data-sig-tipo="condominio" data-sig-condominio-id="${escapeHtml(condo.id)}">
<h1>${escapeHtml(condo.nome)}</h1>
<p class="endereco">${escapeHtml(enderecoLinha(condo.endereco))}</p>
<p class="meta">Registro do condomínio: ${escapeHtml(registroTexto)}</p>

<h2>Pastas de arquivamento</h2>
${pastasHtml}

<h2>Incorporação, especificação e convenção</h2>
${livrosHtml}

<h2>Documentos</h2>
${documentosHtml}

<h2>Unidades autônomas (${condo.unidades.length})</h2>
${unidadesHtml}

<h2>Observações</h2>
<p>${escapeHtml(condo.observacoes) || '<em>Nenhuma observação registrada.</em>'}</p>

<h2>Dados estruturados (uso pelo SIG view)</h2>
<script type="application/json" id="condominio-data">${dadosJson}<\/script>
<pre>${escapeHtml(dadosJson)}</pre>
</body>
</html>
`;
}

function slugify(str) {
  return String(str)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '') || 'condominio';
}
exportarHtmlBtn.addEventListener('click', () => {
  const condo = getCondo(currentCondoId);
  if (!condo) return;
  const html = gerarHtmlCondominio(condo);
  const blob = new Blob([html], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `condominio-${slugify(condo.nome)}.html`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

// ==============================================
// Backup: exportar / importar / apagar
// ==============================================
function todayISO() {
  const d = new Date();
  const offset = d.getTimezoneOffset();
  return new Date(d.getTime() - offset * 60000).toISOString().slice(0, 10);
}

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
  a.download = `condominios-backup-${todayISO()}.json`;
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
      if (!Array.isArray(parsed.condominios)) {
        throw new Error('formato inválido');
      }
      const confirmado = window.confirm(
        'Importar este backup vai substituir todos os dados atuais neste dispositivo. Continuar?'
      );
      if (!confirmado) {
        importInput.value = '';
        return;
      }
      data = { condominios: parsed.condominios };
      saveData(data);
      currentCondoId = null;
      showView('lista');
      renderLista();
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
    'Tem certeza? Isso vai apagar todos os condomínios cadastrados neste dispositivo. Essa ação não pode ser desfeita.'
  );
  if (!confirmado) return;
  data = { condominios: [] };
  saveData(data);
  currentCondoId = null;
  showView('lista');
  renderLista();
  settingsDialog.close();
});

// ==============================================
// Início
// ==============================================
renderLista();

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  });
}
