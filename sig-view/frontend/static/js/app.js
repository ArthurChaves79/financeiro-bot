/**
 * SIG View — frontend.
 * Fala apenas com o backend local (mesma origem), que por sua vez lê a
 * rede local (servidor de tiles, pasta de camadas, banco de geocoding).
 */
(() => {
  const API = {
    config: "/api/config",
    search: (q) => `/api/search?q=${encodeURIComponent(q)}`,
    layers: "/api/layers",
    layer: (id) => `/api/layers/${encodeURIComponent(id)}`,
    settings: "/api/settings",
    version: "/api/version",
    manutencaoTarefas: "/api/manutencao/tarefas",
    manutencaoExecutar: "/api/manutencao/executar",
    manutencaoStatus: (id) => `/api/manutencao/status/${encodeURIComponent(id)}`,
    manutencaoAgendamentos: "/api/manutencao/agendamentos",
    manutencaoAgendamento: (id) => `/api/manutencao/agendamentos/${encodeURIComponent(id)}`,
  };

  const state = {
    map: null,
    marker: null,
    layerIds: new Set(), // camadas já adicionadas ao mapa
    refreshTimers: new Map(), // layerId -> setInterval id (camadas com atualização periódica, ex: NetworkLink)
    medindo: false, // true enquanto a ferramenta "📏 Medir" está ativa
    pontosMedicao: [], // [[lon, lat], ...] marcados enquanto mede
    buscandoVizinhos: false, // true enquanto a ferramenta "🎯 Vizinhos" está ativa
    geojsonPorCamada: new Map(), // layerId -> {geojson, titulo, cor} das camadas ligadas — pra buscar vizinhos sem rebuscar no servidor
    camadasPorId: new Map(), // layerId -> objeto "camada" (do painel de Camadas) — pra ligar uma camada a partir de um resultado de busca, sem depender do checkbox
  };

  async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Erro ${res.status} em ${url}`);
    }
    return res.json();
  }

  // Limita quantas buscas de camada acontecem ao mesmo tempo. Sem isso,
  // marcar uma pasta com centenas de subcamadas (ex: um KML com muitas
  // pastas) dispara todas as requisições de uma vez, o que pode
  // sobrecarregar a conexão local e derrubar algumas delas ("Failed to
  // fetch") — mesmo tudo estando certo do lado do servidor.
  const LIMITE_BUSCAS_SIMULTANEAS = 4;
  let _buscasAtivas = 0;
  const _filaDeBuscas = [];

  function comLimiteDeConcorrencia(tarefa) {
    return new Promise((resolve, reject) => {
      const executar = () => {
        _buscasAtivas++;
        tarefa()
          .then(resolve, reject)
          .finally(() => {
            _buscasAtivas--;
            const proxima = _filaDeBuscas.shift();
            if (proxima) proxima();
          });
      };
      if (_buscasAtivas < LIMITE_BUSCAS_SIMULTANEAS) {
        executar();
      } else {
        _filaDeBuscas.push(executar);
      }
    });
  }

  // Monta uma expressão MapLibre que usa a primeira propriedade da
  // feature (dentre `nomes`) que exista e não esteja vazia, na ordem
  // dada, e só cai pro `padrao` se nenhuma servir — diferente de um
  // "coalesce" puro, que aceitaria "" (string vazia) como valor válido.
  function corComFallback(nomes, padrao) {
    let expr = padrao;
    for (let i = nomes.length - 1; i >= 0; i--) {
      const nome = nomes[i];
      expr = ["case", ["all", ["has", nome], ["!=", ["get", nome], ""]], ["get", nome], expr];
    }
    return expr;
  }

  async function init() {
    const config = await fetchJSON(API.config);
    state.map = createMap(config);
    state.map.on("load", async () => {
      console.debug(
        "[SIG View] mapa carregado — zoom:", state.map.getZoom(),
        "centro:", state.map.getCenter(),
        "fontes:", Object.keys(state.map.getStyle().sources)
      );
      criarCamadasDeMedicao();
      criarCamadaDeDestaqueConfrontantes();
      criarCamadaDeDestaqueBusca();
      await loadLayersPanel();
    });
    setupSearch();
    setupSettings();
    setupFeaturePanel();
    setupMeasure();
    setupExportarImagem();
    setupImprimirLayout();
    setupVizinhos();
    setupManutencao();
    checarVersaoNova();
  }

  // Verificação de versão nova (opcional, ⚙ Configurações > "Verificar
  // versão nova em") — só avisa, nunca baixa/instala nada sozinho. Se
  // não estiver configurado, ou a rede estiver fora do ar, o backend
  // sempre devolve atualizacao_disponivel: false (ver app/versao.py),
  // então isso não precisa de nenhum try/catch extra além do já
  // existente em fetchJSON pra não travar o carregamento do mapa.
  const VERSAO_DISPENSADA_CHAVE = "sigview_versao_dispensada";

  async function checarVersaoNova() {
    let info;
    try {
      info = await fetchJSON(API.version);
    } catch {
      return; // nunca deixa isso atrapalhar o resto do programa
    }
    if (!info.atualizacao_disponivel) return;

    let dispensada = "";
    try {
      dispensada = localStorage.getItem(VERSAO_DISPENSADA_CHAVE) || "";
    } catch {
      // localStorage indisponível (ex: modo privado) — só não lembra a dispensa
    }
    if (dispensada === info.versao_disponivel) return;

    mostrarBannerVersaoNova(info.versao_disponivel);
  }

  function mostrarBannerVersaoNova(versaoDisponivel) {
    const banner = document.createElement("div");
    banner.id = "version-banner";
    banner.innerHTML = `
      <span>🆕 Versão ${versaoDisponivel} disponível — fale com quem administra o programa pra atualizar.</span>
      <button type="button" id="version-banner-fechar" aria-label="Dispensar" title="Dispensar">×</button>
    `;
    document.body.appendChild(banner);
    banner.querySelector("#version-banner-fechar").addEventListener("click", () => {
      try {
        localStorage.setItem(VERSAO_DISPENSADA_CHAVE, versaoDisponivel);
      } catch {
        // sem localStorage, só fecha por essa sessão mesmo
      }
      banner.remove();
    });
  }

  function createMap(config) {
    const isVector = config.tile_source.type === "vector";
    const mapOptions = {
      container: "map",
      center: [config.center.lon, config.center.lat],
      zoom: config.zoom,
      // Sem isso, o navegador pode limpar o canvas WebGL logo depois de
      // desenhar cada quadro — capturar como imagem (toDataURL, botão
      // "Salvar imagem") sairia em branco/preto na maior parte das vezes.
      preserveDrawingBuffer: true,
      style: isVector
        ? config.tile_source.url
        : {
            version: 8,
            sources: {
              base: {
                type: "raster",
                tiles: [config.tile_source.url],
                tileSize: 256,
                attribution: "SIG View — servidor de tiles local",
              },
            },
            layers: [{ id: "base", type: "raster", source: "base" }],
          },
    };

    const map = new maplibregl.Map(mapOptions);
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

    // Em algumas janelas embutidas (ex: pywebview), o mapa às vezes é
    // criado antes do container ter o tamanho final, e fica com um
    // canvas de tamanho errado/zero até algo forçar um resize. Isso
    // força de qualquer forma, mais de uma vez, pra cobrir esse caso.
    window.addEventListener("resize", () => map.resize());
    for (const atraso of [100, 500, 1500]) {
      setTimeout(() => map.resize(), atraso);
    }

    if (config.bounds) {
      const [west, south, east, north] = config.bounds;
      map.fitBounds([[west, south], [east, north]], { padding: 20, duration: 0 });
    }

    // Se o mapa de fundo não carregar (ex: nenhum .mbtiles configurado
    // ainda), avisa em vez de deixar a tela em branco sem explicação.
    map.on("error", (e) => {
      // Sempre registra no Console, mesmo quando também mostramos um
      // aviso na tela — sem isso, erros que não sejam "mapa não
      // configurado" ficavam invisíveis (nem no Console apareciam).
      console.error("[SIG View] Erro do MapLibre:", e?.error || e);
      const status = e?.error?.status;
      if (status === 404) mostrarAvisoMapa();
    });

    map.on("sourcedataloading", (e) => {
      console.debug("[SIG View] carregando fonte:", e.sourceId, e.tile ? `tile ${e.tile.tileID?.canonical?.z}/${e.tile.tileID?.canonical?.x}/${e.tile.tileID?.canonical?.y}` : "");
    });

    return map;
  }

  function mostrarAvisoMapa() {
    if (document.getElementById("map-warning")) return; // já mostrado
    const aviso = document.createElement("div");
    aviso.id = "map-warning";
    aviso.innerHTML = `
      Mapa de ruas não configurado ainda.
      Gere um <code>.mbtiles</code> (veja <code>gerar_e_subir_mapa.bat</code>) ou aponte
      pra um servidor de tiles em <strong>⚙ Configurações</strong>.
    `;
    document.getElementById("map").appendChild(aviso);
  }

  // ---- Camadas ---------------------------------------------------------

  async function loadLayersPanel() {
    const listEl = document.getElementById("layers-list");
    let data;
    try {
      data = await fetchJSON(API.layers);
    } catch (err) {
      listEl.innerHTML = `<li class="empty">Erro ao carregar camadas: ${escapeHtml(err.message)}</li>`;
      return;
    }

    if (!data.layers.length) {
      listEl.innerHTML = `<li class="empty">Nenhuma camada encontrada na pasta configurada.</li>`;
      return;
    }

    listEl.innerHTML = "";
    for (const no of data.layers) {
      listEl.appendChild(renderLayerNode(no));
    }
  }

  let _folderIdSeq = 0;

  // A API devolve uma árvore (igual ao painel "Locais" do Google Earth):
  // cada nó pode ter uma camada própria (checkbox) e/ou subpastas
  // (seta de expandir/recolher) — os dois ao mesmo tempo, se o KML
  // tiver placemarks soltos dentro de uma pasta que também tem subpastas.
  //
  // Pastas também têm checkbox: marcar liga TODAS as camadas daquela
  // pasta (e subpastas) de uma vez, igual ao Google Earth. O estado da
  // pasta (marcada / desmarcada / parcial) é recalculado a partir das
  // camadas-folha reais sempre que uma muda, subindo pela árvore.
  function renderLayerNode(no) {
    const li = document.createElement("li");
    li.className = "layer-node";

    const linha = document.createElement("div");
    linha.className = "layer-row";

    const temFilhos = Array.isArray(no.criancas) && no.criancas.length > 0;
    let subLista = null;

    if (temFilhos) {
      const seta = document.createElement("button");
      seta.type = "button";
      seta.className = "layer-toggle-arrow";
      seta.textContent = "▶";
      seta.setAttribute("aria-expanded", "false");
      seta.title = "Expandir/recolher";
      linha.appendChild(seta);

      subLista = document.createElement("ul");
      subLista.className = "layer-children";
      subLista.hidden = true;

      seta.addEventListener("click", () => {
        const vaiAbrir = subLista.hidden;
        subLista.hidden = !vaiAbrir;
        seta.setAttribute("aria-expanded", String(vaiAbrir));
      });
    } else {
      const espaco = document.createElement("span");
      espaco.className = "layer-toggle-arrow layer-toggle-arrow--vazio";
      linha.appendChild(espaco);
    }

    if (no.erro) {
      // Ex: NetworkLink pra um arquivo que não existe, ou link circular.
      const aviso = document.createElement("span");
      aviso.className = "layer-link-erro";
      aviso.title = no.erro;
      aviso.textContent = `⚠ ${no.nome}`;
      linha.appendChild(aviso);
      li.appendChild(linha);
      return li;
    }

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "layer-checkbox";

    if (no.camada) {
      const camada = no.camada;
      state.camadasPorId.set(camada.id, camada);
      checkbox.dataset.leaf = "true";
      checkbox.id = `layer-${camada.id}`;

      const swatch = document.createElement("span");
      swatch.className = "layer-swatch";
      swatch.style.background = camada.cor_padrao || "#3fa9f5";
      linha.appendChild(swatch);
      linha.appendChild(checkbox);

      const label = document.createElement("label");
      label.setAttribute("for", checkbox.id);
      label.textContent = no.nome;
      linha.appendChild(label);

      if (camada.intervalo_atualizacao_segundos) {
        const icone = document.createElement("span");
        icone.className = "layer-refresh-icon";
        icone.textContent = "🔄";
        icone.title = `Atualiza sozinha a cada ${camada.intervalo_atualizacao_segundos}s (link de rede)`;
        linha.appendChild(icone);
      }

      if (camada.feature_count != null) {
        const badge = document.createElement("span");
        badge.className = "layer-feature-count";
        badge.textContent = camada.feature_count;
        linha.appendChild(badge);
      }

      checkbox.addEventListener("change", (ev) => {
        // Clique direto numa camada (não veio de um checkbox de pasta
        // marcando várias de uma vez) -> pode voar até ela se estiver
        // fora da área visível. Num toggle em massa (pasta), isso é
        // desligado pra não ficar "pulando" de camada em camada.
        const autoFit = !(ev.detail && ev.detail.emLote);
        toggleLayer(camada, checkbox.checked, autoFit);
        atualizarAncestrais(li);
      });
    } else {
      // Pasta pura (sem camada própria nesse nível) — o checkbox liga
      // tudo que está dentro dela.
      checkbox.dataset.folder = "true";
      checkbox.id = `layer-folder-${++_folderIdSeq}`;
      linha.appendChild(checkbox);

      const label = document.createElement("label");
      label.setAttribute("for", checkbox.id);
      label.className = no.de_network_link ? "layer-folder-name layer-folder-name--link" : "layer-folder-name";
      label.textContent = no.de_network_link ? `🔗 ${no.nome}` : no.nome;
      linha.appendChild(label);

      checkbox.addEventListener("change", () => {
        const marcar = checkbox.checked;
        checkbox.indeterminate = false;
        for (const folha of li.querySelectorAll('input.layer-checkbox[data-leaf="true"]')) {
          if (folha.checked !== marcar) {
            folha.checked = marcar;
            folha.dispatchEvent(new CustomEvent("change", { detail: { emLote: true } }));
          }
        }
      });
    }

    li.appendChild(linha);

    if (temFilhos) {
      for (const filho of no.criancas) {
        subLista.appendChild(renderLayerNode(filho));
      }
      li.appendChild(subLista);
      if (no.camada) {
        // Pasta que TAMBÉM é camada (placemarks soltos + subpastas): o
        // checkbox dela some do cálculo de "pasta" pra não conflitar com
        // o dela própria como folha — o de cima já cobre o caso comum.
      } else {
        recalcularCheckboxPasta(li); // pastas recém-montadas começam desmarcadas/vazias
      }
    }

    return li;
  }

  function recalcularCheckboxPasta(li) {
    const checkbox = li.querySelector(':scope > .layer-row > input.layer-checkbox[data-folder="true"]');
    if (!checkbox) return;
    const folhas = li.querySelectorAll('input.layer-checkbox[data-leaf="true"]');
    const marcadas = Array.from(folhas).filter((cb) => cb.checked).length;
    checkbox.checked = folhas.length > 0 && marcadas === folhas.length;
    checkbox.indeterminate = marcadas > 0 && marcadas < folhas.length;
  }

  function atualizarAncestrais(li) {
    let atual = li.parentElement && li.parentElement.closest("li.layer-node");
    while (atual) {
      recalcularCheckboxPasta(atual);
      atual = atual.parentElement && atual.parentElement.closest("li.layer-node");
    }
  }

  // Calcula a caixa envolvente (bounding box) de todas as geometrias de
  // um GeoJSON — usado só pra decidir se precisa mover o mapa até a
  // camada recém-carregada.
  function bboxDoGeoJSON(geojson) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

    function considerar(lon, lat) {
      if (lon < minX) minX = lon;
      if (lon > maxX) maxX = lon;
      if (lat < minY) minY = lat;
      if (lat > maxY) maxY = lat;
    }

    function percorrer(coords, tipo) {
      if (tipo === "Point") {
        considerar(coords[0], coords[1]);
      } else if (tipo === "LineString" || tipo === "MultiPoint") {
        for (const p of coords) considerar(p[0], p[1]);
      } else if (tipo === "Polygon" || tipo === "MultiLineString") {
        for (const parte of coords) for (const p of parte) considerar(p[0], p[1]);
      } else if (tipo === "MultiPolygon") {
        for (const poligono of coords) for (const anel of poligono) for (const p of anel) considerar(p[0], p[1]);
      }
    }

    for (const feature of geojson.features || []) {
      const g = feature.geometry;
      if (g && g.coordinates) percorrer(g.coordinates, g.type);
    }

    return minX === Infinity ? null : [minX, minY, maxX, maxY];
  }

  // Só move o mapa se a camada realmente não estiver visível na área
  // atual — evita ficar "pulando" toda vez que uma camada é ligada.
  function voarParaSeNecessario(bbox) {
    const [minX, minY, maxX, maxY] = bbox;
    const visivel = state.map.getBounds();
    const sobrepoe =
      visivel.getWest() < maxX &&
      visivel.getEast() > minX &&
      visivel.getSouth() < maxY &&
      visivel.getNorth() > minY;
    if (sobrepoe) return;

    state.map.fitBounds(
      [
        [minX, minY],
        [maxX, maxY],
      ],
      { padding: 60, maxZoom: 16, duration: 600 }
    );
  }

  async function toggleLayer(camada, enabled, autoFit = true) {
    const layerId = camada.id;
    const corPadrao = camada.cor_padrao;
    const sourceId = `layer-src-${layerId}`;
    const fillId = `layer-fill-${layerId}`;
    const lineId = `layer-line-${layerId}`;
    const pointId = `layer-point-${layerId}`;

    if (!enabled) {
      for (const id of [fillId, lineId, pointId]) {
        if (state.map.getLayer(id)) state.map.removeLayer(id);
      }
      if (state.map.getSource(sourceId)) state.map.removeSource(sourceId);
      state.layerIds.delete(layerId);
      state.geojsonPorCamada.delete(layerId);
      pararAtualizacaoPeriodica(layerId);
      return;
    }

    if (state.layerIds.has(layerId)) return; // já carregada

    let geojson;
    try {
      geojson = await comLimiteDeConcorrencia(() => fetchJSON(API.layer(layerId)));
    } catch (err) {
      alert(`Não foi possível carregar a camada: ${err.message}`);
      return;
    }

    state.map.addSource(sourceId, { type: "geojson", data: geojson });
    state.geojsonPorCamada.set(layerId, { geojson, titulo: camada.nome || layerId, cor: corPadrao || "#3fa9f5" });

    const cor = corPadrao || "#3fa9f5";
    // Usa a cor definida no próprio polígono/feature, quando existir —
    // seja do <Style> do KML (_cor_preenchimento/_cor_linha, já
    // resolvido pelo nosso parser), do padrão "simplestyle" comum em
    // GeoJSON exportado por outras ferramentas (fill/stroke), ou de um
    // campo "cor" cru (comum em exports de banco de dados). Só cai pra
    // cor padrão da camada (palheta) quando a feature não traz nenhuma
    // dessas informações — inclusive quando o campo existe mas vem em
    // branco ("" — comum em exports de banco com valor nulo), que um
    // "coalesce" simples aceitaria como cor válida e quebraria o mapa.
    const corPreenchimento = corComFallback(["_cor_preenchimento", "fill", "cor", "Cor", "COR"], cor);
    const opacidadePreenchimento = corComFallback(["_opacidade_preenchimento", "fill-opacity"], 0.25);
    const corLinha = corComFallback(["_cor_linha", "stroke", "cor", "Cor", "COR"], cor);
    const larguraLinha = corComFallback(["_largura_linha", "stroke-width"], 2);
    const corPonto = corComFallback(["_cor_ponto", "marker-color", "cor", "Cor", "COR"], cor);

    state.map.addLayer({
      id: fillId,
      type: "fill",
      source: sourceId,
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "fill-color": corPreenchimento, "fill-opacity": opacidadePreenchimento },
    });
    state.map.addLayer({
      id: lineId,
      type: "line",
      source: sourceId,
      filter: ["any", ["==", ["geometry-type"], "Polygon"], ["==", ["geometry-type"], "LineString"]],
      paint: { "line-color": corLinha, "line-width": larguraLinha },
    });
    state.map.addLayer({
      id: pointId,
      type: "circle",
      source: sourceId,
      filter: ["==", ["geometry-type"], "Point"],
      paint: { "circle-radius": 6, "circle-color": corPonto, "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 },
    });

    // Clique em qualquer tipo de geometria (ponto, linha ou polígono)
    // abre a barra lateral de detalhes com todos os atributos da feature.
    for (const id of [fillId, lineId, pointId]) {
      state.map.on("click", id, (e) => {
        if (state.medindo) return; // com a régua ativa, o clique é pra marcar ponto, não abrir a feature
        const feature = e.features[0];
        if (state.buscandoVizinhos) {
          state.selecionarConfrontantes?.(feature, { titulo: camada.nome || layerId, cor });
          return;
        }
        const props = feature.properties || {};
        const titulo = props.nome || camada.nome || layerId;
        abrirPainelFeature(titulo, cor, props, feature.geometry);
      });
      state.map.on("mouseenter", id, () => { state.map.getCanvas().style.cursor = "pointer"; });
      state.map.on("mouseleave", id, () => { state.map.getCanvas().style.cursor = ""; });
    }

    state.layerIds.add(layerId);

    // Se a camada carregou mas está fora da área que a tela mostra
    // agora, "voa" até ela — sem isso, ligar o checkbox parece não ter
    // feito nada (a camada existe, só não está visível).
    if (autoFit) {
      const bbox = bboxDoGeoJSON(geojson);
      if (bbox) voarParaSeNecessario(bbox);
    }

    // Camadas vindas de <NetworkLink> com refreshMode=onInterval se
    // atualizam sozinhas, igual ao Google Earth — busca de novo no
    // backend (que relê o arquivo de rede) e atualiza só os dados da
    // fonte no mapa, sem precisar recarregar a página.
    if (camada.intervalo_atualizacao_segundos) {
      iniciarAtualizacaoPeriodica(layerId, sourceId, camada.intervalo_atualizacao_segundos);
    }
  }

  function iniciarAtualizacaoPeriodica(layerId, sourceId, intervaloSegundos) {
    pararAtualizacaoPeriodica(layerId);
    const timerId = setInterval(async () => {
      const source = state.map.getSource(sourceId);
      if (!source) {
        pararAtualizacaoPeriodica(layerId); // camada foi desligada nesse meio tempo
        return;
      }
      try {
        const geojson = await comLimiteDeConcorrencia(() => fetchJSON(API.layer(layerId)));
        source.setData(geojson);
        const info = state.geojsonPorCamada.get(layerId);
        if (info) info.geojson = geojson; // mantém a busca por vizinhos com o dado mais recente
      } catch (err) {
        console.warn(`Falha ao atualizar a camada ${layerId}:`, err.message);
      }
    }, Math.max(intervaloSegundos, 5) * 1000); // nunca mais rápido que a cada 5s, por segurança
    state.refreshTimers.set(layerId, timerId);
  }

  function pararAtualizacaoPeriodica(layerId) {
    const timerId = state.refreshTimers.get(layerId);
    if (timerId != null) {
      clearInterval(timerId);
      state.refreshTimers.delete(layerId);
    }
  }

  // ---- Busca -------------------------------------------------------------

  // Histórico de buscas recentes — guardado só no navegador local (não
  // é dado sensível de verdade, mas mesmo assim não faz sentido
  // compartilhar entre usuários/instalações). Guarda o resultado
  // inteiro selecionado (não só o texto digitado), pra poder voar
  // direto pro lugar de novo sem rebuscar.
  const HISTORICO_CHAVE = "sigview_busca_recente";
  const HISTORICO_MAX = 8;

  function lerHistorico() {
    try {
      const bruto = localStorage.getItem(HISTORICO_CHAVE);
      return bruto ? JSON.parse(bruto) : [];
    } catch {
      return [];
    }
  }

  function salvarNoHistorico(result) {
    try {
      const atual = lerHistorico().filter((r) => r.label !== result.label);
      atual.unshift(result);
      localStorage.setItem(HISTORICO_CHAVE, JSON.stringify(atual.slice(0, HISTORICO_MAX)));
    } catch {
      // localStorage indisponível (ex: modo privado) — sem histórico, sem problema
    }
  }

  function setupSearch() {
    const input = document.getElementById("search-input");
    const resultsEl = document.getElementById("search-results");
    let debounceTimer = null;

    input.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      const q = input.value.trim();
      if (q.length < 2) {
        mostrarHistorico();
        return;
      }
      debounceTimer = setTimeout(() => runSearch(q), 250);
    });

    input.addEventListener("focus", () => {
      if (input.value.trim().length < 2) mostrarHistorico();
    });

    function mostrarHistorico() {
      const historico = lerHistorico();
      if (!historico.length) {
        hideResults();
        return;
      }
      resultsEl.innerHTML = "";
      const titulo = document.createElement("li");
      titulo.className = "empty";
      titulo.textContent = "Buscas recentes";
      resultsEl.appendChild(titulo);
      for (const r of historico) {
        const li = document.createElement("li");
        li.textContent = `🕑 ${r.label}`;
        li.addEventListener("click", () => selectResult(r));
        resultsEl.appendChild(li);
      }
      resultsEl.hidden = false;
    }

    document.addEventListener("click", (e) => {
      if (!resultsEl.contains(e.target) && e.target !== input) hideResults();
    });

    async function runSearch(q) {
      let data;
      try {
        data = await fetchJSON(API.search(q));
      } catch (err) {
        showResultsMessage(`Erro na busca: ${err.message}`, "error");
        return;
      }
      if (!data.results.length) {
        showResultsMessage("Nenhum resultado encontrado.", "empty");
        return;
      }
      renderResults(data.results);
    }

    function renderResults(results) {
      resultsEl.innerHTML = "";
      for (const r of results) {
        const li = document.createElement("li");
        li.textContent = r.label;
        li.addEventListener("click", () => selectResult(r));
        resultsEl.appendChild(li);
      }
      resultsEl.hidden = false;
    }

    function showResultsMessage(msg, cls) {
      resultsEl.innerHTML = `<li class="${cls}">${escapeHtml(msg)}</li>`;
      resultsEl.hidden = false;
    }

    function hideResults() {
      resultsEl.hidden = true;
    }

    async function selectResult(result) {
      hideResults();
      salvarNoHistorico(result);
      input.value = result.label;
      limparDestaqueDeBusca();
      if (state.marker) {
        state.marker.remove();
        state.marker = null;
      }

      // Resultado veio de uma camada vinculada (ex: um imóvel indexado
      // por número de contribuinte, matrícula, setor-quadra-lote etc.)
      // — em vez de só deixar um marcador solto no centro aproximado,
      // mostra o próprio lote: liga a camada (se ainda não estiver),
      // acha a feature de verdade e abre a barra de detalhes dela.
      if (result.layer_id) {
        const mostrou = await mostrarFeatureDeResultado(result);
        if (mostrou) return;
        // Não achou a feature exata (índice desatualizado, camada sem
        // esse registro etc.) — cai pro marcador simples abaixo, pra
        // pelo menos mostrar onde é.
      }

      state.map.flyTo({ center: [result.lon, result.lat], zoom: 17 });
      const entradasResultado = [
        ["Tipo", result.tipo],
        ["Logradouro", result.logradouro],
        ["Bairro", result.bairro],
        ["Cidade", result.cidade],
        ["CEP", result.cep],
        ["Detalhes", result.rotulo],
      ].filter(([, v]) => v);
      state.marker = new maplibregl.Marker({ color: "#3fa9f5" })
        .setLngLat([result.lon, result.lat])
        .setPopup(new maplibregl.Popup({ maxWidth: "320px" }).setHTML(buildPopupHtml(result.label, "#3fa9f5", entradasResultado)))
        .addTo(state.map);
    }

    // Liga a camada do resultado (se preciso) e localiza a feature
    // exata dentro dela (por centroide — ver encontrarFeaturePorCentroide)
    // pra destacar o contorno, enquadrar o mapa nela e abrir a barra de
    // detalhes com os atributos de verdade (não só os campos indexados
    // na busca). Devolve false se não achou (chamador cai pro marcador
    // simples nesse caso).
    async function mostrarFeatureDeResultado(result) {
      const layerId = result.layer_id;
      if (!state.geojsonPorCamada.has(layerId)) {
        const camada = state.camadasPorId.get(layerId);
        if (!camada) return false; // painel de Camadas ainda não carregou — nada a fazer
        const checkbox = document.getElementById(`layer-${layerId}`);
        // autoFit=false: enquadra na feature específica logo abaixo,
        // não faz sentido "pular" pra bbox da camada inteira primeiro.
        await toggleLayer(camada, true, false);
        if (checkbox) checkbox.checked = true; // reflete no painel sem disparar 'change' de novo (toggleLayer já foi chamado)
      }

      const info = state.geojsonPorCamada.get(layerId);
      if (!info) return false;
      const feature = encontrarFeaturePorCentroide(info.geojson, result.lon, result.lat);
      if (!feature) return false;

      destacarResultadoDeBusca(feature.geometry);
      const bbox = bboxDoGeoJSON({ type: "FeatureCollection", features: [feature] });
      if (bbox) {
        state.map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], { padding: 100, maxZoom: 19, duration: 600 });
      } else {
        state.map.flyTo({ center: [result.lon, result.lat], zoom: 18 });
      }

      const props = feature.properties || {};
      abrirPainelFeature(props.nome || result.label, info.cor, props, feature.geometry);
      return true;
    }
  }

  // ---- Medir distância -----------------------------------------------------
  //
  // Ferramenta simples: ativa, clica pontos no mapa, mostra a distância
  // total acumulada (linha reta entre os pontos, ponto a ponto — não
  // segue rua). "Limpar" reseta; desativar o botão também limpa.

  const MEASURE_SOURCE_ID = "sigview-medicao";
  const MEASURE_LINE_ID = "sigview-medicao-linha";
  const MEASURE_PONTOS_ID = "sigview-medicao-pontos";

  function criarCamadasDeMedicao() {
    state.map.addSource(MEASURE_SOURCE_ID, {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
    state.map.addLayer({
      id: MEASURE_LINE_ID,
      type: "line",
      source: MEASURE_SOURCE_ID,
      filter: ["==", ["geometry-type"], "LineString"],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#e0605f", "line-width": 2, "line-dasharray": [2, 1] },
    });
    state.map.addLayer({
      id: MEASURE_PONTOS_ID,
      type: "circle",
      source: MEASURE_SOURCE_ID,
      filter: ["==", ["geometry-type"], "Point"],
      paint: { "circle-radius": 4, "circle-color": "#e0605f", "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 },
    });
  }

  // Haversine — distância em metros entre dois pontos [lon, lat].
  function _distanciaMetros([lon1, lat1], [lon2, lat2]) {
    const R = 6371000;
    const rad = Math.PI / 180;
    const dLat = (lat2 - lat1) * rad;
    const dLon = (lon2 - lon1) * rad;
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  function formatarDistancia(m) {
    if (m >= 1000) return `${(m / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} km`;
    return `${m.toLocaleString("pt-BR", { maximumFractionDigits: 0 })} m`;
  }

  function setupMeasure() {
    const btn = document.getElementById("measure-btn");
    const box = document.getElementById("measure-box");
    const totalEl = document.getElementById("measure-total");
    const clearBtn = document.getElementById("measure-clear");

    function atualizarDesenho() {
      const pontos = state.pontosMedicao;
      const features = pontos.map((p) => ({ type: "Feature", geometry: { type: "Point", coordinates: p }, properties: {} }));
      if (pontos.length >= 2) {
        features.push({ type: "Feature", geometry: { type: "LineString", coordinates: pontos }, properties: {} });
      }
      state.map.getSource(MEASURE_SOURCE_ID)?.setData({ type: "FeatureCollection", features });

      let total = 0;
      for (let i = 1; i < pontos.length; i++) total += _distanciaMetros(pontos[i - 1], pontos[i]);
      totalEl.textContent = formatarDistancia(total);
    }

    function limpar() {
      state.pontosMedicao = [];
      atualizarDesenho();
    }

    function ativar() {
      state.medindo = true;
      btn.classList.add("active");
      box.hidden = false;
      state.map.getCanvas().style.cursor = "crosshair";
      limpar();
    }

    function desativar() {
      state.medindo = false;
      btn.classList.remove("active");
      box.hidden = true;
      state.map.getCanvas().style.cursor = "";
      limpar();
    }

    btn.addEventListener("click", () => {
      if (state.medindo) {
        desativar();
      } else {
        state.desativarVizinhos?.(); // só uma ferramenta de clique-no-mapa ativa por vez
        ativar();
      }
    });
    clearBtn.addEventListener("click", limpar);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && state.medindo) desativar();
    });

    state.map.on("click", (e) => {
      if (!state.medindo) return;
      state.pontosMedicao.push([e.lngLat.lng, e.lngLat.lat]);
      atualizarDesenho();
    });

    state.desativarMedicao = desativar;
  }

  // ---- Salvar mapa como imagem --------------------------------------------
  //
  // Captura o canvas do MapLibre (precisa de preserveDrawingBuffer:true
  // na criação do mapa, senão sai em branco) e baixa como PNG. Só pega
  // o que é desenhado NO mapa (tiles, camadas, a linha de medição) —
  // marcador de busca e a barra lateral são elementos HTML por cima do
  // mapa, não entram na imagem.

  function setupExportarImagem() {
    const btn = document.getElementById("export-btn");
    btn.addEventListener("click", () => {
      // Espera o navegador terminar de pintar o quadro atual antes de
      // capturar — evita pegar um instante intermediário do desenho.
      requestAnimationFrame(async () => {
        let dataUrl;
        try {
          dataUrl = state.map.getCanvas().toDataURL("image/png");
        } catch (err) {
          alert(`Não foi possível gerar a imagem: ${err.message}`);
          return;
        }

        const agora = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const nomeArquivo =
          `sigview-mapa-${agora.getFullYear()}-${pad(agora.getMonth() + 1)}-${pad(agora.getDate())}` +
          `-${pad(agora.getHours())}${pad(agora.getMinutes())}.png`;

        // Na janela própria (pywebview), o download comum de navegador
        // é inconsistente — às vezes cai direto na pasta Downloads sem
        // avisar nada, sem dar pra escolher onde. Quando dá pra usar a
        // ponte pro Python (window.pywebview.api), abre a janela
        // "Salvar como" de verdade do Windows em vez disso.
        if (window.pywebview?.api?.salvar_imagem_png) {
          let resultado;
          try {
            resultado = await window.pywebview.api.salvar_imagem_png(dataUrl, nomeArquivo);
          } catch (err) {
            alert(`Não foi possível salvar a imagem: ${err.message}`);
            return;
          }
          if (resultado.cancelado) return; // usuário fechou a janela "Salvar como" — nada a avisar
          if (!resultado.ok) {
            alert(`Não foi possível salvar a imagem: ${resultado.erro || "erro desconhecido"}`);
            return;
          }
          alert(`Imagem salva em:\n${resultado.caminho}`);
          return;
        }

        // Fallback pra quando o programa abre no navegador comum (sem
        // pywebview) — aí o download padrão do navegador funciona bem.
        const link = document.createElement("a");
        link.href = dataUrl;
        link.download = nomeArquivo;
        document.body.appendChild(link);
        link.click();
        link.remove();
      });
    });
  }

  // ---- Layout de impressão "oficial" (🖨) ----------------------------------
  //
  // Diferente de "📷 Salvar imagem" (que só baixa o canvas puro), monta
  // uma segunda imagem — título, data, barra de escala, seta do norte e
  // legenda das camadas visíveis — por cima de uma cópia do mapa, tudo
  // desenhado num <canvas> à parte (offscreen), pronta pra anexar num
  // relatório ou imprimir. Não depende de nenhuma biblioteca nova: tudo
  // aqui é Canvas 2D (texto, linhas, triângulo) puro.

  // Arredonda uma distância "crua" (metros por N pixels da barra) pro
  // número mais próximo da série 1-2-5-10 (mesma lógica usada em régua
  // de mapa/atlas) — assim a barra sempre mostra um valor redondo tipo
  // "50 m" ou "2 km", nunca "37 m".
  function _numeroBonitoDeEscala(metros) {
    if (!Number.isFinite(metros) || metros <= 0) return 100;
    const expoente = Math.floor(Math.log10(metros));
    const base = 10 ** expoente;
    const fracao = metros / base;
    let escolhido;
    if (fracao < 1.5) escolhido = 1;
    else if (fracao < 3.5) escolhido = 2;
    else if (fracao < 7.5) escolhido = 5;
    else escolhido = 10;
    return escolhido * base;
  }

  function _formatarEscalaLabel(metros) {
    if (metros >= 1000) return `${(metros / 1000).toLocaleString("pt-BR")} km`;
    return `${metros.toLocaleString("pt-BR")} m`;
  }

  // Metros por pixel "cru" (pixel de verdade do canvas, já multiplicado
  // pelo devicePixelRatio) medindo 100px na horizontal a partir do
  // centro do mapa — suficiente pra uma barra de escala aproximada
  // (não precisa ser exata a ponto de considerar a curvatura dentro da
  // própria tela).
  function _metrosPorPixelCru() {
    const dpr = window.devicePixelRatio || 1;
    const centro = state.map.getCenter();
    const pxCentro = state.map.project(centro);
    const pxDeslocado = state.map.unproject({ x: pxCentro.x + 100, y: pxCentro.y });
    const metros100px = _distanciaMetros([centro.lng, centro.lat], [pxDeslocado.lng, pxDeslocado.lat]);
    return metros100px / 100 / dpr;
  }

  function setupImprimirLayout() {
    const btn = document.getElementById("print-btn");

    btn.addEventListener("click", () => {
      requestAnimationFrame(async () => {
        const dpr = window.devicePixelRatio || 1;
        const mapaCanvas = state.map.getCanvas();

        const margem = Math.round(20 * dpr);
        const alturaCabecalho = Math.round(64 * dpr);
        const itensLegenda = Array.from(state.geojsonPorCamada.values()).map((info) => ({
          titulo: info.titulo,
          cor: info.cor,
        }));
        const alturaLinhaLegenda = Math.round(22 * dpr);
        const alturaLegenda = itensLegenda.length
          ? Math.round(30 * dpr) + itensLegenda.length * alturaLinhaLegenda
          : 0;

        const largura = mapaCanvas.width;
        const altura = alturaCabecalho + mapaCanvas.height + alturaLegenda;

        const saida = document.createElement("canvas");
        saida.width = largura;
        saida.height = altura;
        const ctx = saida.getContext("2d");

        // Fundo branco (papel) — a área do mapa em si vem colada por
        // cima logo abaixo, isso só cobre cabeçalho/legenda.
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, largura, altura);

        // Cabeçalho: título + data/hora de geração.
        ctx.fillStyle = "#1a1a1a";
        ctx.font = `bold ${Math.round(22 * dpr)}px -apple-system, "Segoe UI", Arial, sans-serif`;
        ctx.textBaseline = "alphabetic";
        ctx.fillText("SIG View", margem, Math.round(30 * dpr));

        const agora = new Date();
        ctx.fillStyle = "#555555";
        ctx.font = `${Math.round(12 * dpr)}px -apple-system, "Segoe UI", Arial, sans-serif`;
        ctx.fillText(`Gerado em ${agora.toLocaleString("pt-BR")}`, margem, Math.round(50 * dpr));

        ctx.strokeStyle = "#cccccc";
        ctx.lineWidth = Math.max(1, Math.round(1 * dpr));
        ctx.beginPath();
        ctx.moveTo(0, alturaCabecalho - 1);
        ctx.lineTo(largura, alturaCabecalho - 1);
        ctx.stroke();

        // O mapa em si — cola direto do canvas do MapLibre, sem passar
        // por toDataURL/Image (evita um round-trip assíncrono à toa).
        ctx.drawImage(mapaCanvas, 0, alturaCabecalho);

        // Seta do norte — ver a explicação do sinal de "-bearing" no
        // comentário da função.
        _desenharSetaNorte(ctx, largura - margem - Math.round(18 * dpr), alturaCabecalho + margem + Math.round(18 * dpr), dpr);

        // Barra de escala.
        const metrosPorPixel = _metrosPorPixelCru();
        const metrosAlvo = _numeroBonitoDeEscala(metrosPorPixel * 120 * dpr);
        const larguraBarra = metrosAlvo / metrosPorPixel;
        _desenharBarraDeEscala(
          ctx,
          margem,
          alturaCabecalho + mapaCanvas.height - margem,
          larguraBarra,
          _formatarEscalaLabel(metrosAlvo),
          dpr
        );

        // Legenda das camadas visíveis (uma por linha, com uma
        // quadradinho colorido igual ao usado no painel de Camadas).
        if (itensLegenda.length) {
          let y = alturaCabecalho + mapaCanvas.height + Math.round(24 * dpr);
          ctx.font = `${Math.round(13 * dpr)}px -apple-system, "Segoe UI", Arial, sans-serif`;
          for (const item of itensLegenda) {
            const ladoQuadrado = Math.round(12 * dpr);
            ctx.fillStyle = item.cor;
            ctx.fillRect(margem, y - ladoQuadrado, ladoQuadrado, ladoQuadrado);
            ctx.strokeStyle = "#999999";
            ctx.lineWidth = 1;
            ctx.strokeRect(margem, y - ladoQuadrado, ladoQuadrado, ladoQuadrado);

            ctx.fillStyle = "#1a1a1a";
            ctx.fillText(item.titulo, margem + ladoQuadrado + Math.round(8 * dpr), y);
            y += alturaLinhaLegenda;
          }
        }

        let dataUrl;
        try {
          dataUrl = saida.toDataURL("image/png");
        } catch (err) {
          alert(`Não foi possível gerar o layout de impressão: ${err.message}`);
          return;
        }

        const pad = (n) => String(n).padStart(2, "0");
        const nomeArquivo =
          `sigview-impressao-${agora.getFullYear()}-${pad(agora.getMonth() + 1)}-${pad(agora.getDate())}` +
          `-${pad(agora.getHours())}${pad(agora.getMinutes())}.png`;

        if (window.pywebview?.api?.salvar_imagem_png) {
          let resultado;
          try {
            resultado = await window.pywebview.api.salvar_imagem_png(dataUrl, nomeArquivo);
          } catch (err) {
            alert(`Não foi possível salvar a imagem: ${err.message}`);
            return;
          }
          if (resultado.cancelado) return;
          if (!resultado.ok) {
            alert(`Não foi possível salvar a imagem: ${resultado.erro || "erro desconhecido"}`);
            return;
          }
          alert(`Imagem salva em:\n${resultado.caminho}`);
          return;
        }

        const link = document.createElement("a");
        link.href = dataUrl;
        link.download = nomeArquivo;
        document.body.appendChild(link);
        link.click();
        link.remove();
      });
    });
  }

  // Seta apontando pro norte verdadeiro, considerando a rotação atual
  // do mapa (bearing). bearing=0 -> mapa "sem rotação", norte é pra
  // cima, seta não gira. Girar o mapa bearing° no sentido horário faz
  // uma direção fixa (como o norte) girar bearing° no sentido
  // ANTI-horário na tela — por isso o sinal trocado (-bearing).
  function _desenharSetaNorte(ctx, cx, cy, dpr) {
    const bearing = state.map.getBearing();
    const raio = Math.round(14 * dpr);

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate((-bearing * Math.PI) / 180);

    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.beginPath();
    ctx.arc(0, 0, raio + Math.round(6 * dpr), 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#999999";
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.fillStyle = "#c0392b";
    ctx.beginPath();
    ctx.moveTo(0, -raio);
    ctx.lineTo(raio * 0.55, raio * 0.6);
    ctx.lineTo(0, raio * 0.25);
    ctx.lineTo(-raio * 0.55, raio * 0.6);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = "#1a1a1a";
    ctx.font = `bold ${Math.round(11 * dpr)}px -apple-system, "Segoe UI", Arial, sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText("N", 0, -raio - Math.round(4 * dpr));
    ctx.textAlign = "start";

    ctx.restore();
  }

  // Barra de escala com traços nas pontas e o rótulo (ex: "50 m") acima
  // — desenhada com um fundo branco semi-transparente por baixo, pra
  // ficar legível em cima de qualquer cor de mapa.
  function _desenharBarraDeEscala(ctx, x, yBase, largura, rotulo, dpr) {
    const alturaTraco = Math.round(6 * dpr);
    const padding = Math.round(6 * dpr);

    ctx.font = `${Math.round(11 * dpr)}px -apple-system, "Segoe UI", Arial, sans-serif`;
    const larguraTexto = ctx.measureText(rotulo).width;
    const larguraFundo = Math.max(largura, larguraTexto) + padding * 2;
    const alturaFundo = Math.round(28 * dpr) + padding;

    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.fillRect(x - padding, yBase - alturaFundo, larguraFundo, alturaFundo);
    ctx.strokeStyle = "#999999";
    ctx.lineWidth = 1;
    ctx.strokeRect(x - padding, yBase - alturaFundo, larguraFundo, alturaFundo);

    ctx.fillStyle = "#1a1a1a";
    ctx.fillText(rotulo, x, yBase - alturaTraco - Math.round(6 * dpr));

    ctx.strokeStyle = "#1a1a1a";
    ctx.lineWidth = Math.max(1, Math.round(1.5 * dpr));
    ctx.beginPath();
    ctx.moveTo(x, yBase - alturaTraco);
    ctx.lineTo(x, yBase);
    ctx.lineTo(x + largura, yBase);
    ctx.lineTo(x + largura, yBase - alturaTraco);
    ctx.stroke();
  }

  // ---- Confrontantes (🧭) --------------------------------------------------
  //
  // Clica um lote (polígono) e lista os OUTROS polígonos — em qualquer
  // camada ligada — cuja linha divisória toca a dele diretamente (não
  // é busca por raio: é "faz divisa", com uma tolerância pequena em
  // metros pra absorver folgas comuns de digitalização entre bases
  // diferentes). Mostra endereço + matrícula/transcrição de cada um.

  const CONFRONTANTES_DESTAQUE_SOURCE_ID = "sigview-confrontantes-destaque";
  const CONFRONTANTES_DESTAQUE_LAYER_ID = "sigview-confrontantes-destaque-linha";

  function criarCamadaDeDestaqueConfrontantes() {
    state.map.addSource(CONFRONTANTES_DESTAQUE_SOURCE_ID, {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
    state.map.addLayer({
      id: CONFRONTANTES_DESTAQUE_LAYER_ID,
      type: "line",
      source: CONFRONTANTES_DESTAQUE_SOURCE_ID,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        // azul = o lote selecionado; laranja = quem faz divisa com ele
        "line-color": ["case", ["==", ["get", "papel"], "selecionado"], "#3fa9f5", "#f5a93f"],
        "line-width": 3,
      },
    });
  }

  // ---- Destaque do resultado de busca --------------------------------------
  //
  // Quando a busca acha um registro vinculado a uma camada (ex: um
  // imóvel, via numero_contribuinte/matrícula/etc.), em vez de só
  // deixar um marcador solto no centro aproximado, mostra o polígono
  // (ou linha/ponto) encontrado de verdade — contorno destacado, mapa
  // enquadrado nele e a barra de detalhes já aberta. Ver selectResult().

  const BUSCA_DESTAQUE_SOURCE_ID = "sigview-busca-destaque";
  const BUSCA_DESTAQUE_LAYER_ID = "sigview-busca-destaque-linha";

  function criarCamadaDeDestaqueBusca() {
    state.map.addSource(BUSCA_DESTAQUE_SOURCE_ID, {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
    state.map.addLayer({
      id: BUSCA_DESTAQUE_LAYER_ID,
      type: "line",
      source: BUSCA_DESTAQUE_SOURCE_ID,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#3fa9f5", "line-width": 4 },
    });
  }

  function destacarResultadoDeBusca(geometry) {
    state.map.getSource(BUSCA_DESTAQUE_SOURCE_ID)?.setData({
      type: "FeatureCollection",
      features: [{ type: "Feature", properties: {}, geometry }],
    });
  }

  function limparDestaqueDeBusca() {
    state.map.getSource(BUSCA_DESTAQUE_SOURCE_ID)?.setData({ type: "FeatureCollection", features: [] });
  }

  // Acha, dentro do GeoJSON de uma camada já carregada, a feature cujo
  // centroide (mesmo cálculo — média dos vértices — usado tanto aqui
  // quanto em app/geoutil.py na hora de indexar) mais se aproxima do
  // ponto salvo no índice de busca. Uma pequena tolerância absorve a
  // perda de precisão da compactação de coordenadas (compactar_
  // camadas.py) — sem ela, o mesmo lote comparado com ele mesmo já não
  // bateria exatamente. Sempre devolve a feature mais próxima dentro
  // da tolerância (nunca a mais próxima "custe o que custar"), pra não
  // arriscar destacar o lote errado se o índice estiver desatualizado.
  function encontrarFeaturePorCentroide(geojson, lon, lat) {
    const TOLERANCIA_GRAUS = 0.001; // ~90-100m em São Paulo — folga generosa pra compactação, nunca pra "adivinhar"
    let melhor = null;
    let melhorDist = Infinity;
    for (const feature of geojson.features || []) {
      const centro = centroideAproximado(feature.geometry);
      if (!centro) continue;
      const dist = Math.hypot(centro[0] - lon, centro[1] - lat);
      if (dist < melhorDist) {
        melhorDist = dist;
        melhor = feature;
      }
    }
    return melhorDist <= TOLERANCIA_GRAUS ? melhor : null;
  }

  // Só os anéis externos importam pra "faz divisa" (buracos internos
  // não são fronteira com o lote vizinho).
  function _aneisExternos(geometry) {
    if (geometry.type === "Polygon") return [geometry.coordinates[0]];
    if (geometry.type === "MultiPolygon") return geometry.coordinates.map((p) => p[0]);
    return [];
  }

  function _orientacao(p, q, r) {
    const val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1]);
    if (Math.abs(val) < 1e-9) return 0;
    return val > 0 ? 1 : 2;
  }

  function _noSegmento(p, q, r) {
    return (
      Math.min(p[0], r[0]) - 1e-9 <= q[0] && q[0] <= Math.max(p[0], r[0]) + 1e-9 &&
      Math.min(p[1], r[1]) - 1e-9 <= q[1] && q[1] <= Math.max(p[1], r[1]) + 1e-9
    );
  }

  // Teste clássico de interseção de segmentos (orientação + casos
  // colineares) — sem isso, dois segmentos que se cruzam no meio (não
  // nas pontas) passariam despercebidos só olhando ponto-a-segmento.
  function _segmentosSeCruzam(p1, q1, p2, q2) {
    const o1 = _orientacao(p1, q1, p2), o2 = _orientacao(p1, q1, q2);
    const o3 = _orientacao(p2, q2, p1), o4 = _orientacao(p2, q2, q1);
    if (o1 !== o2 && o3 !== o4) return true;
    if (o1 === 0 && _noSegmento(p1, p2, q1)) return true;
    if (o2 === 0 && _noSegmento(p1, q2, q1)) return true;
    if (o3 === 0 && _noSegmento(p2, p1, q2)) return true;
    if (o4 === 0 && _noSegmento(p2, q1, q2)) return true;
    return false;
  }

  function _distanciaSegmentoSegmento(a1, a2, b1, b2) {
    if (_segmentosSeCruzam(a1, a2, b1, b2)) return 0;
    return Math.min(
      _distanciaPontoSegmento(a1, b1, b2),
      _distanciaPontoSegmento(a2, b1, b2),
      _distanciaPontoSegmento(b1, a1, a2),
      _distanciaPontoSegmento(b2, a1, a2)
    );
  }

  // Distância mínima entre as BORDAS de dois polígonos (0 quando as
  // linhas se tocam ou se cruzam) — projeta os dois num referencial
  // local comum (metros) antes de comparar segmento a segmento.
  function distanciaEntrePoligonos(geomA, geomB) {
    const aneisA = _aneisExternos(geomA);
    const aneisB = _aneisExternos(geomB);
    if (!aneisA.length || !aneisB.length) return Infinity;
    const origem = aneisA[0][0];
    const proj = (pt) => _projetarLocal(pt, origem);

    let min = Infinity;
    for (const anelA of aneisA) {
      for (let i = 0; i < anelA.length - 1; i++) {
        const a1 = proj(anelA[i]), a2 = proj(anelA[i + 1]);
        for (const anelB of aneisB) {
          for (let j = 0; j < anelB.length - 1; j++) {
            const d = _distanciaSegmentoSegmento(a1, a2, proj(anelB[j]), proj(anelB[j + 1]));
            if (d < min) min = d;
            if (min === 0) return 0;
          }
        }
      }
    }
    return min;
  }

  // Endereço e número de registro resumidos — mesmos campos
  // reconhecidos usados na barra lateral de detalhes (CAMPOS_CONHECIDOS),
  // só que soltos aqui (sem "consumir" nada de um índice compartilhado),
  // pra montar uma linha curta de listagem.
  function _enderecoResumo(props) {
    const indice = indexarPropriedades(props);
    const descartar = new Set();
    const tipo = pegarPropriedade(props, indice, descartar, CAMPOS_CONHECIDOS.tipoLogradouro);
    const logradouro = pegarPropriedade(props, indice, descartar, CAMPOS_CONHECIDOS.logradouro);
    const numero = pegarPropriedade(props, indice, descartar, CAMPOS_CONHECIDOS.numeroEndereco);
    const endereco = [tipo, logradouro].filter(Boolean).join(" ").trim() + (numero ? `, ${numero}` : "");
    return endereco.trim() || null;
  }

  function _registroResumo(props) {
    const indice = indexarPropriedades(props);
    const descartar = new Set();
    const matricula = pegarPropriedade(props, indice, descartar, CAMPOS_CONHECIDOS.matricula);
    if (matricula) return `Matrícula ${matricula}`;
    const transcricao = pegarPropriedade(props, indice, descartar, CAMPOS_CONHECIDOS.transcricao);
    if (transcricao) return `Transcrição ${transcricao}`;
    return null;
  }

  function setupVizinhos() {
    const btn = document.getElementById("neighbors-btn");
    const panel = document.getElementById("neighbors-panel");
    const closeBtn = document.getElementById("neighbors-panel-close");
    const toleranciaInput = document.getElementById("neighbors-raio");
    const buscarBtn = document.getElementById("neighbors-buscar");
    const hintEl = document.getElementById("neighbors-hint");
    const listEl = document.getElementById("neighbors-list");
    const exportarBtn = document.getElementById("neighbors-exportar");

    let poligonoSelecionado = null; // { feature, info } — o lote clicado, base da comparação
    let ultimosEncontrados = []; // guardado pra "Exportar CSV" sem precisar buscar de novo

    function renderLista(encontrados) {
      ultimosEncontrados = encontrados;
      exportarBtn.disabled = encontrados.length === 0;

      listEl.innerHTML = "";
      if (!encontrados.length) {
        listEl.innerHTML = `<li class="neighbors-item" style="cursor:default">Nenhum confrontante encontrado com essa tolerância.</li>`;
        return;
      }
      for (const { info, feature } of encontrados) {
        const props = feature.properties || {};
        const endereco = _enderecoResumo(props) || props.nome || info.titulo;
        const registro = _registroResumo(props);

        const li = document.createElement("li");
        li.className = "neighbors-item";
        li.innerHTML = `<span class="layer-swatch" style="background:${escapeHtml(info.cor)}"></span><span class="neighbors-item-label"></span>`;
        li.querySelector(".neighbors-item-label").textContent = registro ? `${endereco} — ${registro}` : endereco;
        li.addEventListener("click", () => {
          const centro = centroideAproximado(feature.geometry);
          if (centro) state.map.flyTo({ center: centro, zoom: 18 });
          abrirPainelFeature(endereco, info.cor, props, feature.geometry);
        });
        listEl.appendChild(li);
      }
    }

    // CSV com ";" (não ",") — é o separador de lista que o Excel em
    // português usa por padrão (já que "," é o separador decimal aqui).
    function _campoCsv(valor) {
      const texto = String(valor ?? "");
      return /[;"\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
    }

    function exportarCsv() {
      if (!ultimosEncontrados.length) return;
      const linhas = [["Endereço", "Registro", "Distância (m)", "Camada", "Latitude", "Longitude"].map(_campoCsv).join(";")];
      for (const { info, feature, distancia } of ultimosEncontrados) {
        const props = feature.properties || {};
        const endereco = _enderecoResumo(props) || props.nome || info.titulo;
        const registro = _registroResumo(props) || "";
        const centro = centroideAproximado(feature.geometry) || ["", ""];
        linhas.push(
          [endereco, registro, distancia.toFixed(1), info.titulo, centro[1], centro[0]].map(_campoCsv).join(";")
        );
      }
      const csv = linhas.join("\r\n") + "\r\n";
      const nomeArquivo = `confrontantes-${new Date().toISOString().slice(0, 10)}.csv`;

      if (window.pywebview?.api?.salvar_texto) {
        window.pywebview.api.salvar_texto(csv, nomeArquivo).then((resultado) => {
          if (resultado.cancelado) return;
          if (!resultado.ok) {
            alert(`Não foi possível salvar o CSV: ${resultado.erro || "erro desconhecido"}`);
            return;
          }
          alert(`CSV salvo em:\n${resultado.caminho}`);
        });
        return;
      }

      // Fallback pro modo navegador comum (sem pywebview) — precisa do
      // BOM (﻿) na frente pro Excel também abrir os acentos certo.
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
      link.download = nomeArquivo;
      document.body.appendChild(link);
      link.click();
      link.remove();
    }

    function executarBusca() {
      if (!poligonoSelecionado) return;
      const tolerancia = Math.max(0, Number(toleranciaInput.value) || 0);

      const encontrados = [];
      for (const [, info] of state.geojsonPorCamada) {
        for (const feature of info.geojson.features || []) {
          if (feature === poligonoSelecionado.feature) continue; // não compara o lote com ele mesmo
          if (feature.geometry?.type !== "Polygon" && feature.geometry?.type !== "MultiPolygon") continue;
          const distancia = distanciaEntrePoligonos(poligonoSelecionado.feature.geometry, feature.geometry);
          if (distancia <= tolerancia) encontrados.push({ info, feature, distancia });
        }
      }
      encontrados.sort((a, b) => a.distancia - b.distancia);

      state.map.getSource(CONFRONTANTES_DESTAQUE_SOURCE_ID)?.setData({
        type: "FeatureCollection",
        features: [
          { type: "Feature", properties: { papel: "selecionado" }, geometry: poligonoSelecionado.feature.geometry },
          ...encontrados.map((e) => ({ type: "Feature", properties: { papel: "confrontante" }, geometry: e.feature.geometry })),
        ],
      });

      hintEl.hidden = true;
      renderLista(encontrados);
    }

    function selecionar(feature, info) {
      if (feature.geometry?.type !== "Polygon" && feature.geometry?.type !== "MultiPolygon") {
        alert("Clique num polígono (lote) — a busca de confrontantes não funciona em ponto/linha.");
        return;
      }
      poligonoSelecionado = { feature, info };
      executarBusca();
    }

    function ativar() {
      state.buscandoVizinhos = true;
      btn.classList.add("active");
      panel.classList.add("open");
      state.map.getCanvas().style.cursor = "crosshair";
    }

    function desativar() {
      state.buscandoVizinhos = false;
      btn.classList.remove("active");
      panel.classList.remove("open");
      state.map.getCanvas().style.cursor = "";
      state.map.getSource(CONFRONTANTES_DESTAQUE_SOURCE_ID)?.setData({ type: "FeatureCollection", features: [] });
      poligonoSelecionado = null;
      ultimosEncontrados = [];
      exportarBtn.disabled = true;
      hintEl.hidden = false;
      listEl.innerHTML = "";
    }

    btn.addEventListener("click", () => {
      if (state.buscandoVizinhos) {
        desativar();
      } else {
        state.desativarMedicao?.();
        ativar();
      }
    });
    closeBtn.addEventListener("click", desativar);
    buscarBtn.addEventListener("click", executarBusca);
    exportarBtn.addEventListener("click", exportarCsv);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && state.buscandoVizinhos) desativar();
    });

    state.desativarVizinhos = desativar;
    state.selecionarConfrontantes = selecionar; // chamado pelo clique normal de feature, quando o modo está ativo
  }

  // Centroide aproximado — mesma lógica usada no backend
  // (app/geoutil.py), reimplementada aqui em JS pra "voar até" um
  // resultado da busca por vizinhos sem precisar de outra chamada ao
  // servidor.
  function centroideAproximado(geometry) {
    function* pontos(coords, tipo) {
      if (tipo === "Point") yield coords;
      else if (tipo === "LineString" || tipo === "MultiPoint") yield* coords;
      else if (tipo === "Polygon" || tipo === "MultiLineString") for (const parte of coords) yield* parte;
      else if (tipo === "MultiPolygon") for (const poligono of coords) for (const anel of poligono) yield* anel;
    }
    if (!geometry) return null;
    let xs = 0, ys = 0, n = 0;
    for (const p of pontos(geometry.coordinates, geometry.type)) {
      xs += p[0];
      ys += p[1];
      n++;
    }
    return n ? [xs / n, ys / n] : null;
  }

  // ---- Configurações -----------------------------------------------------

  function setupSettings() {
    const btn = document.getElementById("settings-btn");
    const overlay = document.getElementById("settings-overlay");
    const cancelBtn = document.getElementById("settings-cancel");
    const saveBtn = document.getElementById("settings-save");
    const errorEl = document.getElementById("settings-error");

    const fields = {
      layers_dir: document.getElementById("cfg-layers-dir"),
      geocoder_db: document.getElementById("cfg-geocoder-db"),
      mbtiles_path: document.getElementById("cfg-mbtiles"),
      tile_source_url: document.getElementById("cfg-tile-url"),
      tile_source_type: document.getElementById("cfg-tile-type"),
      map_style: document.getElementById("cfg-map-style"),
      versao_check_path: document.getElementById("cfg-versao-check"),
    };

    const mapaSelect = document.getElementById("cfg-mapa-select");
    const mbtilesLabel = document.getElementById("cfg-mbtiles-label");
    const mbtilesInput = fields.mbtiles_path;
    const VALOR_PERSONALIZADO = "__personalizado__";

    // O <select> é só um jeito mais fácil de escolher entre os
    // .mbtiles de data/maps/ — quem realmente é salvo continua sendo
    // o input de texto escondido (cfg-mbtiles), pra não duplicar a
    // lógica de salvar/validar que já existe pros outros campos.
    function mostrarCampoPersonalizado(mostrar) {
      mbtilesLabel.hidden = !mostrar;
      mbtilesInput.hidden = !mostrar;
    }

    mapaSelect.addEventListener("change", () => {
      if (mapaSelect.value === VALOR_PERSONALIZADO) {
        mostrarCampoPersonalizado(true);
      } else {
        mostrarCampoPersonalizado(false);
        mbtilesInput.value = mapaSelect.value;
      }
    });

    btn.addEventListener("click", async () => {
      errorEl.hidden = true;
      try {
        const [current, mapasResp, estilosResp] = await Promise.all([
          fetchJSON(API.settings),
          fetchJSON("/api/maps").catch(() => ({ maps: [] })),
          fetchJSON("/api/map-styles").catch(() => ({ styles: [] })),
        ]);

        // Popula os <select> dinâmicos ANTES de aplicar os valores
        // atuais — senão "fields.map_style.value = current.map_style"
        // não acharia nenhuma <option> ainda pra selecionar.
        fields.map_style.innerHTML = "";
        for (const estilo of estilosResp.styles || []) {
          const opt = document.createElement("option");
          opt.value = estilo.id;
          opt.textContent = estilo.nome;
          fields.map_style.appendChild(opt);
        }

        for (const [key, el] of Object.entries(fields)) {
          if (current[key] != null) el.value = current[key];
        }

        mapaSelect.innerHTML = "";
        for (const mapa of mapasResp.maps || []) {
          const opt = document.createElement("option");
          opt.value = mapa.caminho;
          opt.textContent = mapa.nome;
          mapaSelect.appendChild(opt);
        }
        const optPersonalizado = document.createElement("option");
        optPersonalizado.value = VALOR_PERSONALIZADO;
        optPersonalizado.textContent = "Personalizado (digitar caminho)...";
        mapaSelect.appendChild(optPersonalizado);

        const atual = mbtilesInput.value;
        const existeNaLista = Array.from(mapaSelect.options).some((o) => o.value === atual);
        if (existeNaLista) {
          mapaSelect.value = atual;
          mostrarCampoPersonalizado(false);
        } else {
          mapaSelect.value = VALOR_PERSONALIZADO;
          mostrarCampoPersonalizado(true);
        }
      } catch (err) {
        showError(`Não foi possível carregar as configurações atuais: ${err.message}`);
      }
      overlay.hidden = false;
    });

    cancelBtn.addEventListener("click", () => {
      overlay.hidden = true;
    });

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) overlay.hidden = true;
    });

    saveBtn.addEventListener("click", async () => {
      errorEl.hidden = true;
      const payload = {};
      for (const [key, el] of Object.entries(fields)) {
        payload[key] = el.value.trim();
      }

      saveBtn.disabled = true;
      saveBtn.textContent = "Salvando...";
      try {
        const res = await fetch(API.settings, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || `Erro ${res.status}`);
        }
        location.reload();
      } catch (err) {
        showError(err.message);
        saveBtn.disabled = false;
        saveBtn.textContent = "Salvar";
      }
    });

    function showError(msg) {
      errorEl.textContent = msg;
      errorEl.hidden = false;
    }
  }

  // Painel de manutenção (🔧) — roda de dentro do programa os scripts
  // que antes só davam pra rodar via terminal (reindexar camadas,
  // reconstruir o índice de busca, vincular polígonos a um banco
  // existente). O catálogo de tarefas/campos vem do backend (ver
  // app/manutencao.py) pra não duplicar aqui os nomes/padrões de cada
  // parâmetro; o formulário é montado dinamicamente a partir dele.
  function setupManutencao() {
    const btn = document.getElementById("maintenance-btn");
    const overlay = document.getElementById("maintenance-overlay");
    const closeBtn = document.getElementById("maintenance-close");
    const runBtn = document.getElementById("maintenance-run");
    const tarefaSelect = document.getElementById("maint-tarefa-select");
    const descricaoEl = document.getElementById("maint-tarefa-descricao");
    const camposEl = document.getElementById("maint-campos");
    const errorEl = document.getElementById("maintenance-error");
    const logWrap = document.getElementById("maintenance-log-wrap");
    const logEl = document.getElementById("maintenance-log");
    const statusEl = document.getElementById("maintenance-status");
    const agendaAtivoEl = document.getElementById("maint-agenda-ativo");
    const agendaDetalhesEl = document.getElementById("maint-agenda-detalhes");
    const agendaIntervaloEl = document.getElementById("maint-agenda-intervalo");
    const agendaInfoEl = document.getElementById("maint-agenda-info");
    const agendaSalvarBtn = document.getElementById("maint-agenda-salvar");

    let tarefas = [];
    let agendamentos = []; // agendamentos já salvos (ver app/agendamento.py), um por tarefa_id
    let pollTimer = null;

    function showError(msg) {
      errorEl.textContent = msg;
      errorEl.hidden = false;
    }

    function pararPoll() {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    }

    // Cada tarefa declara seus próprios campos (nome, rótulo, se é
    // obrigatório, valor padrão, texto de ajuda, se aceita lista) — só
    // precisamos de um <input> de texto genérico por campo, sem
    // conhecer os detalhes de cada tarefa aqui.
    function renderCampos(tarefa) {
      camposEl.innerHTML = "";
      for (const campo of tarefa.campos || []) {
        const label = document.createElement("label");
        label.setAttribute("for", `maint-campo-${campo.nome}`);
        label.textContent = campo.rotulo + (campo.obrigatorio ? "" : " (opcional)");
        camposEl.appendChild(label);

        const input = document.createElement("input");
        input.type = "text";
        input.id = `maint-campo-${campo.nome}`;
        input.dataset.campo = campo.nome;
        input.value = campo.padrao || "";
        camposEl.appendChild(input);

        if (campo.ajuda) {
          const ajuda = document.createElement("p");
          ajuda.className = "maint-campo-ajuda";
          ajuda.textContent = campo.ajuda;
          camposEl.appendChild(ajuda);
        }
      }
    }

    function tarefaSelecionada() {
      return tarefas.find((t) => t.id === tarefaSelect.value);
    }

    // Lê os valores atuais do formulário e devolve {parametros, faltando}
    // — usado tanto por "Rodar" quanto por "Salvar agendamento", já que
    // os dois precisam dos mesmos campos preenchidos.
    function coletarParametros(tarefa) {
      const parametros = {};
      for (const input of camposEl.querySelectorAll("input[data-campo]")) {
        parametros[input.dataset.campo] = input.value.trim();
      }
      const faltando = (tarefa.campos || []).filter(
        (campo) => campo.obrigatorio && !parametros[campo.nome]
      );
      return { parametros, faltando };
    }

    function formatarDataHora(isoUtc) {
      if (!isoUtc) return null;
      const data = new Date(isoUtc);
      if (Number.isNaN(data.getTime())) return null;
      return data.toLocaleString("pt-BR");
    }

    // Preenche o bloco "Repetir automaticamente" com o que já estiver
    // salvo pra essa tarefa (se houver) — cada tarefa tem seu próprio
    // agendamento independente.
    function atualizarAgendaUI(tarefa) {
      const agendamento = agendamentos.find((a) => a.tarefa_id === tarefa.id);
      agendaAtivoEl.checked = !!(agendamento && agendamento.ativo);
      agendaIntervaloEl.value = (agendamento && agendamento.intervalo_horas) || 24;
      agendaDetalhesEl.hidden = !agendaAtivoEl.checked;

      const partesInfo = [];
      const ultima = formatarDataHora(agendamento && agendamento.ultima_execucao);
      if (ultima) partesInfo.push(`Último disparo: ${ultima}`);
      if (agendamento && agendamento.ativo) {
        partesInfo.push(`repete a cada ${agendamento.intervalo_horas}h enquanto o programa estiver aberto`);
      }
      agendaInfoEl.textContent = partesInfo.join(" — ");
    }

    agendaAtivoEl.addEventListener("change", () => {
      agendaDetalhesEl.hidden = !agendaAtivoEl.checked;
    });

    agendaSalvarBtn.addEventListener("click", async () => {
      const tarefa = tarefaSelecionada();
      if (!tarefa) return;
      errorEl.hidden = true;

      const { parametros, faltando } = coletarParametros(tarefa);
      const ativo = agendaAtivoEl.checked;
      const intervaloHoras = Number(agendaIntervaloEl.value);

      if (ativo && faltando.length) {
        showError(`Preencha antes de agendar: ${faltando.map((c) => c.rotulo).join(", ")}`);
        return;
      }
      if (ativo && (!intervaloHoras || intervaloHoras <= 0)) {
        showError("Informe um intervalo (em horas) maior que zero.");
        return;
      }

      agendaSalvarBtn.disabled = true;
      try {
        const resp = await fetch(API.manutencaoAgendamento(tarefa.id), {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ativo, intervalo_horas: intervaloHoras, parametros }),
        });
        const body = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(body.detail || `Erro ${resp.status}`);

        agendamentos = agendamentos.filter((a) => a.tarefa_id !== tarefa.id);
        agendamentos.push({ tarefa_id: tarefa.id, nome: tarefa.nome, ...body });
        atualizarAgendaUI(tarefa);
      } catch (err) {
        showError(`Não foi possível salvar o agendamento: ${err.message}`);
      } finally {
        agendaSalvarBtn.disabled = false;
      }
    });

    tarefaSelect.addEventListener("change", () => {
      const tarefa = tarefaSelecionada();
      if (!tarefa) return;
      descricaoEl.textContent = tarefa.descricao;
      renderCampos(tarefa);
      atualizarAgendaUI(tarefa);
    });

    btn.addEventListener("click", async () => {
      errorEl.hidden = true;
      logWrap.hidden = true;
      logEl.textContent = "";
      statusEl.textContent = "";
      statusEl.className = "hint";
      runBtn.disabled = false;
      runBtn.textContent = "Rodar";
      tarefaSelect.disabled = false;
      pararPoll();

      try {
        const [tarefasResp, agendamentosResp] = await Promise.all([
          fetchJSON(API.manutencaoTarefas),
          fetchJSON(API.manutencaoAgendamentos).catch(() => ({ agendamentos: [] })),
        ]);
        tarefas = tarefasResp.tarefas || [];
        agendamentos = agendamentosResp.agendamentos || [];
        tarefaSelect.innerHTML = "";
        for (const tarefa of tarefas) {
          const opt = document.createElement("option");
          opt.value = tarefa.id;
          opt.textContent = tarefa.nome;
          tarefaSelect.appendChild(opt);
        }
        if (tarefas.length) {
          tarefaSelect.value = tarefas[0].id;
          descricaoEl.textContent = tarefas[0].descricao;
          renderCampos(tarefas[0]);
          atualizarAgendaUI(tarefas[0]);
        }
      } catch (err) {
        showError(`Não foi possível carregar as tarefas: ${err.message}`);
      }
      overlay.hidden = false;
    });

    closeBtn.addEventListener("click", () => {
      // A tarefa continua rodando no servidor mesmo fechando o painel
      // (só para de acompanhar o log aqui) — reabrir e escolher a
      // mesma tarefa de novo não retoma o acompanhamento, mas rodar
      // outra tarefa antes dela terminar é bloqueado pelo backend.
      pararPoll();
      overlay.hidden = true;
    });

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        pararPoll();
        overlay.hidden = true;
      }
    });

    runBtn.addEventListener("click", async () => {
      const tarefa = tarefaSelecionada();
      if (!tarefa) return;
      errorEl.hidden = true;

      const { parametros, faltando } = coletarParametros(tarefa);
      if (faltando.length) {
        showError(`Preencha: ${faltando.map((c) => c.rotulo).join(", ")}`);
        return;
      }

      runBtn.disabled = true;
      runBtn.textContent = "Rodando...";
      tarefaSelect.disabled = true;
      logWrap.hidden = false;
      logEl.textContent = "";
      statusEl.textContent = "Rodando...";
      statusEl.className = "hint";

      let execucaoId;
      try {
        const resp = await fetch(API.manutencaoExecutar, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tarefa_id: tarefa.id, parametros }),
        });
        const body = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(body.detail || `Erro ${resp.status}`);
        execucaoId = body.execucao_id;
      } catch (err) {
        showError(err.message);
        runBtn.disabled = false;
        runBtn.textContent = "Rodar";
        tarefaSelect.disabled = false;
        return;
      }

      pollTimer = setInterval(async () => {
        let status;
        try {
          status = await fetchJSON(API.manutencaoStatus(execucaoId));
        } catch {
          return; // tenta de novo no próximo tick — não desiste por uma falha isolada
        }
        logEl.textContent = status.log.join("\n");
        logEl.scrollTop = logEl.scrollHeight;

        if (status.status === "executando") return;

        pararPoll();
        runBtn.disabled = false;
        runBtn.textContent = "Rodar";
        tarefaSelect.disabled = false;

        if (status.status === "concluido") {
          statusEl.textContent = "✅ Concluído.";
          statusEl.className = "hint concluido";
        } else {
          statusEl.textContent = `❌ Erro: ${status.erro || "desconhecido"}`;
          statusEl.className = "hint erro";
        }
      }, 1000);
    });
  }

  // Popup pequeno usado só pro marcador de um resultado de busca (não
  // é sobre um polígono do mapa, então continua sendo um popup simples
  // de "balão", não a barra lateral).
  function buildPopupHtml(titulo, cor, entradas) {
    const corpo = entradas.length
      ? `<table class="sigview-popup-table">${entradas
          .map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${escapeHtml(formatarValorPropriedade(v))}</td></tr>`)
          .join("")}</table>`
      : `<div class="sigview-popup-empty">Sem atributos</div>`;
    return `
      <div class="sigview-popup">
        <div class="sigview-popup-header">
          <span class="layer-swatch" style="background:${escapeHtml(cor || "#3fa9f5")}"></span>
          <h3 title="${escapeHtml(titulo)}">${escapeHtml(titulo)}</h3>
        </div>
        <div class="sigview-popup-body">${corpo}</div>
      </div>
    `;
  }

  // ---- Barra lateral de detalhes do polígono/feature ----------------------
  //
  // Ao clicar num polígono/linha/ponto do mapa, mostra TODAS as
  // informações que a feature tiver, só organizando um conjunto de
  // campos "conhecidos" (contribuinte, matrícula/transcrição, endereço,
  // loteamento, documentos, observações) numa ordem fixa e com rótulo
  // amigável — o resto das propriedades continua aparecendo depois,
  // igual antes. Campos sem valor simplesmente não aparecem.

  function setupFeaturePanel() {
    const closeBtn = document.getElementById("feature-panel-close");
    closeBtn.addEventListener("click", fecharPainelFeature);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") fecharPainelFeature();
    });
  }

  function fecharPainelFeature() {
    document.getElementById("feature-panel").classList.remove("open");
  }

  function abrirPainelFeature(titulo, cor, props, geometry) {
    const painel = document.getElementById("feature-panel");
    document.getElementById("feature-panel-title").textContent = titulo;
    document.getElementById("feature-panel-title").title = titulo;
    document.getElementById("feature-panel-swatch").style.background = cor || "#3fa9f5";

    const linhas = montarLinhasPainel(props || {}, geometry);
    document.getElementById("feature-panel-body").innerHTML = linhas.length
      ? linhas.map(renderLinhaPainel).join("")
      : `<div class="feature-panel-empty">Sem atributos</div>`;

    painel.classList.add("open");
  }

  function renderLinhaPainel(linha) {
    const valorHtml = linha.documentos
      ? `<div class="feature-panel-docs">${linha.documentos
          .map((doc) => `<a href="${escapeHtml(doc)}" target="_blank" rel="noopener">📎 ${escapeHtml(nomeArquivoDoCaminho(doc))}</a>`)
          .join("")}</div>`
      : escapeHtml(linha.valor);
    return `
      <div class="feature-panel-row">
        <span class="feature-panel-label">${escapeHtml(linha.label)}</span>
        <div class="feature-panel-value">${valorHtml}</div>
      </div>
    `;
  }

  // Nomes de propriedade "conhecidos" pra cada campo do painel, já
  // normalizados (sem acento/maiúscula/separador) — aceita variações
  // comuns de nome vindas de KML/SQL/GeoJSON de terceiros, sem precisar
  // bater exatamente com um nome fixo de coluna.
  const CAMPOS_CONHECIDOS = {
    setor: ["setor"],
    quadra: ["quadra"],
    lote: ["lote"],
    contribuinte: ["contribuinte", "numerocontribuinte", "numcontribuinte", "inscricaoimobiliaria", "inscricao"],
    matricula: ["matricula", "nmatricula", "numeromatricula"],
    transcricao: ["transcricao", "ntranscricao", "numerotranscricao"],
    tipoLogradouro: ["tipologradouro", "tipoendereco", "tipo"],
    logradouro: ["logradouro", "endereco", "rua", "enderecocompleto"],
    numeroEndereco: ["numeroendereco", "nendereco", "numero", "num"],
    loteamento: ["loteamento", "nomeloteamento"],
    documentos: ["documentos", "documento", "anexos", "anexo", "linkdocumentos", "urldocumentos", "arquivos", "arquivo"],
    observacoes: ["observacoes", "observacao", "obs"],
  };

  function normalizarChave(k) {
    return k
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "");
  }

  // Converte qualquer valor de propriedade pra texto legível — inclusive
  // array/objeto (que antes viravam "[object Object]" no popup, o
  // "aparece entre colchetes" que causava confusão).
  function formatarValorPropriedade(v) {
    if (v === null || v === undefined) return "";
    if (Array.isArray(v)) {
      return v.map(formatarValorPropriedade).filter(Boolean).join(", ");
    }
    if (typeof v === "object") {
      return Object.values(v).map(formatarValorPropriedade).filter(Boolean).join(", ");
    }
    return String(v).trim();
  }

  function indexarPropriedades(props) {
    const porNomeNormalizado = new Map(); // nome normalizado -> nome original
    for (const chave of Object.keys(props)) {
      if (chave.startsWith("_")) continue; // uso interno (ex: cor vinda do KML)
      if (formatarValorPropriedade(props[chave]) === "") continue; // vazio não conta como presente
      const norm = normalizarChave(chave);
      if (!porNomeNormalizado.has(norm)) porNomeNormalizado.set(norm, chave);
    }
    return porNomeNormalizado;
  }

  function pegarPropriedade(props, indice, consumidas, candidatos) {
    for (const candidato of candidatos) {
      const chaveOriginal = indice.get(candidato);
      if (chaveOriginal !== undefined) {
        consumidas.add(chaveOriginal);
        return formatarValorPropriedade(props[chaveOriginal]);
      }
    }
    return "";
  }

  // Um campo de "documentos" pode ter mais de um caminho/link, separados
  // por vírgula/ponto-e-vírgula/quebra de linha.
  function extrairDocumentos(bruto) {
    const partes = bruto.split(/[;\n]+/).map((s) => s.trim()).filter(Boolean);
    return partes.length ? partes : [bruto];
  }

  function nomeArquivoDoCaminho(caminho) {
    const semBarra = caminho.split(/[\\/]/).pop();
    return semBarra || caminho;
  }

  function rotuloAmigavel(chave) {
    const espacado = chave.replace(/[_-]+/g, " ").trim();
    return espacado.charAt(0).toUpperCase() + espacado.slice(1);
  }

  // Área aproximada de um Polygon/MultiPolygon, em m² — projeta cada
  // anel localmente (achatando a longitude pelo cosseno da latitude
  // média, aproximação boa o bastante pra um lote/terreno, que é
  // pequeno perto do raio da Terra) e aplica a fórmula do shoelace.
  // Buracos (anéis internos) são subtraídos, como o GeoJSON já prevê
  // (primeiro anel = contorno externo, os demais = buracos).
  const _RAIO_TERRA_M = 6371000;

  function _areaDoAnel(anel) {
    if (anel.length < 3) return 0;
    const latMedia = anel.reduce((soma, p) => soma + p[1], 0) / anel.length;
    const metrosPorGrauLat = (Math.PI / 180) * _RAIO_TERRA_M;
    const metrosPorGrauLon = metrosPorGrauLat * Math.cos((latMedia * Math.PI) / 180);
    let soma = 0;
    for (let i = 0; i < anel.length; i++) {
      const [lon1, lat1] = anel[i];
      const [lon2, lat2] = anel[(i + 1) % anel.length];
      const x1 = lon1 * metrosPorGrauLon, y1 = lat1 * metrosPorGrauLat;
      const x2 = lon2 * metrosPorGrauLon, y2 = lat2 * metrosPorGrauLat;
      soma += x1 * y2 - x2 * y1;
    }
    return Math.abs(soma) / 2;
  }

  function areaAproximadaM2(geometry) {
    if (!geometry) return null;
    if (geometry.type === "Polygon") {
      const [externo, ...buracos] = geometry.coordinates;
      return _areaDoAnel(externo) - buracos.reduce((soma, b) => soma + _areaDoAnel(b), 0);
    }
    if (geometry.type === "MultiPolygon") {
      return geometry.coordinates.reduce((soma, poligono) => {
        const [externo, ...buracos] = poligono;
        return soma + _areaDoAnel(externo) - buracos.reduce((s, b) => s + _areaDoAnel(b), 0);
      }, 0);
    }
    return null;
  }

  function formatarArea(m2) {
    if (m2 >= 1_000_000) return `${(m2 / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} km²`;
    if (m2 >= 10_000) return `${(m2 / 10_000).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} ha`;
    return `${m2.toLocaleString("pt-BR", { maximumFractionDigits: 0 })} m²`;
  }

  // ---- Geometria compartilhada (projeção local + distância ponto-segmento) --
  //
  // Base usada pela busca de confrontantes (distância entre bordas de
  // dois polígonos). Mesma técnica de projeção local usada em
  // areaAproximadaM2: converte tudo pra metros num referencial local
  // antes de medir, boa o bastante pra distâncias de lote/quarteirão.

  function _projetarLocal([lon, lat], origem) {
    const mLat = (Math.PI / 180) * _RAIO_TERRA_M;
    const mLon = mLat * Math.cos((origem[1] * Math.PI) / 180);
    return [(lon - origem[0]) * mLon, (lat - origem[1]) * mLat];
  }

  function _distanciaPontoSegmento(p, a, b) {
    const [px, py] = p, [ax, ay] = a, [bx, by] = b;
    const dx = bx - ax, dy = by - ay;
    const lenSq = dx * dx + dy * dy;
    let t = lenSq === 0 ? 0 : ((px - ax) * dx + (py - ay) * dy) / lenSq;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
  }

  function montarLinhasPainel(props, geometry) {
    const indice = indexarPropriedades(props);
    const consumidas = new Set();
    const linhas = [];

    // Contribuinte = Setor + Quadra + Lote (ou já vem pronto num campo
    // próprio, ex: vindo direto do SQL) — mostrado como um só valor.
    const setor = pegarPropriedade(props, indice, consumidas, CAMPOS_CONHECIDOS.setor);
    const quadra = pegarPropriedade(props, indice, consumidas, CAMPOS_CONHECIDOS.quadra);
    const lote = pegarPropriedade(props, indice, consumidas, CAMPOS_CONHECIDOS.lote);
    const contribuinteDireto = pegarPropriedade(props, indice, consumidas, CAMPOS_CONHECIDOS.contribuinte);
    const contribuinte = contribuinteDireto || [setor, quadra, lote].filter(Boolean).join(".");
    if (contribuinte) linhas.push({ label: "Contribuinte", valor: contribuinte });

    // Área calculada na hora, a partir da própria geometria — não
    // depende de nenhum campo/atributo do banco (só entra pra
    // Polygon/MultiPolygon; ponto e linha não têm área).
    const areaM2 = areaAproximadaM2(geometry);
    if (areaM2 !== null && areaM2 > 0) {
      linhas.push({ label: "Área (aprox.)", valor: formatarArea(areaM2) });
    }

    // Número do Registro: Matrícula (prioridade) ou Transcrição.
    const matricula = pegarPropriedade(props, indice, consumidas, CAMPOS_CONHECIDOS.matricula);
    const transcricao = matricula ? "" : pegarPropriedade(props, indice, consumidas, CAMPOS_CONHECIDOS.transcricao);
    if (matricula) linhas.push({ label: "Matrícula", valor: matricula });
    else if (transcricao) linhas.push({ label: "Transcrição", valor: transcricao });

    // Endereço: Tipo + Logradouro + nº (ex: "Rua Exemplo, 123").
    const tipo = pegarPropriedade(props, indice, consumidas, CAMPOS_CONHECIDOS.tipoLogradouro);
    const logradouro = pegarPropriedade(props, indice, consumidas, CAMPOS_CONHECIDOS.logradouro);
    const numeroEndereco = pegarPropriedade(props, indice, consumidas, CAMPOS_CONHECIDOS.numeroEndereco);
    const endereco = [tipo, logradouro].filter(Boolean).join(" ").trim() + (numeroEndereco ? `, ${numeroEndereco}` : "");
    if (endereco.trim()) linhas.push({ label: "Endereço", valor: endereco.trim() });

    const loteamento = pegarPropriedade(props, indice, consumidas, CAMPOS_CONHECIDOS.loteamento);
    if (loteamento) linhas.push({ label: "Loteamento", valor: loteamento });

    // Documentos anexados ao loteamento — vira link clicável, não texto.
    const documentosBruto = pegarPropriedade(props, indice, consumidas, CAMPOS_CONHECIDOS.documentos);
    if (documentosBruto) {
      linhas.push({ label: "Documentos", documentos: extrairDocumentos(documentosBruto) });
    }

    const observacoes = pegarPropriedade(props, indice, consumidas, CAMPOS_CONHECIDOS.observacoes);
    if (observacoes) linhas.push({ label: "Observações", valor: observacoes });

    // Qualquer outra propriedade que a feature tiver, não coberta pelos
    // campos conhecidos acima, ainda aparece — só depois, no final.
    for (const [chave, valorOriginal] of Object.entries(props)) {
      if (chave.startsWith("_") || consumidas.has(chave)) continue;
      const valor = formatarValorPropriedade(valorOriginal);
      if (!valor) continue;
      linhas.push({ label: rotuloAmigavel(chave), valor });
    }

    return linhas;
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c]));
  }

  init().catch((err) => {
    console.error(err);
    document.getElementById("map").innerHTML =
      `<p style="padding:24px;color:#f66">Erro ao iniciar o mapa: ${escapeHtml(err.message)}</p>`;
  });
})();
