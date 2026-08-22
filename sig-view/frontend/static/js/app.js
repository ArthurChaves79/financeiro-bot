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
  };

  const state = {
    map: null,
    marker: null,
    layerIds: new Set(), // camadas já adicionadas ao mapa
    refreshTimers: new Map(), // layerId -> setInterval id (camadas com atualização periódica, ex: NetworkLink)
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

  async function init() {
    const config = await fetchJSON(API.config);
    state.map = createMap(config);
    state.map.on("load", async () => {
      console.debug(
        "[SIG View] mapa carregado — zoom:", state.map.getZoom(),
        "centro:", state.map.getCenter(),
        "fontes:", Object.keys(state.map.getStyle().sources)
      );
      await loadLayersPanel();
    });
    setupSearch();
    setupSettings();
  }

  function createMap(config) {
    const isVector = config.tile_source.type === "vector";
    const mapOptions = {
      container: "map",
      center: [config.center.lon, config.center.lat],
      zoom: config.zoom,
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

    const cor = corPadrao || "#3fa9f5";
    // Usa a cor definida no próprio KML (_cor_preenchimento/_cor_linha),
    // quando existir; senão cai para a cor padrão desta camada.
    const corPreenchimento = ["coalesce", ["get", "_cor_preenchimento"], cor];
    const opacidadePreenchimento = ["coalesce", ["get", "_opacidade_preenchimento"], 0.25];
    const corLinha = ["coalesce", ["get", "_cor_linha"], cor];
    const larguraLinha = ["coalesce", ["get", "_largura_linha"], 2];
    const corPonto = ["coalesce", ["get", "_cor_ponto"], cor];

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
    // abre um popup com todos os atributos da feature.
    for (const id of [fillId, lineId, pointId]) {
      state.map.on("click", id, (e) => {
        const feature = e.features[0];
        const props = feature.properties || {};
        const entradas = Object.entries(props).filter(([k]) => !k.startsWith("_"));
        const titulo = props.nome || camada.nome || layerId;
        new maplibregl.Popup({ maxWidth: "320px" })
          .setLngLat(e.lngLat)
          .setHTML(buildPopupHtml(titulo, cor, entradas))
          .addTo(state.map);
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

  function setupSearch() {
    const input = document.getElementById("search-input");
    const resultsEl = document.getElementById("search-results");
    let debounceTimer = null;

    input.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      const q = input.value.trim();
      if (q.length < 2) {
        hideResults();
        return;
      }
      debounceTimer = setTimeout(() => runSearch(q), 250);
    });

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

    function selectResult(result) {
      hideResults();
      input.value = result.label;
      state.map.flyTo({ center: [result.lon, result.lat], zoom: 17 });
      if (state.marker) state.marker.remove();
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

      // Resultado veio de uma camada vinculada (ex: um imóvel) — liga a
      // camada automaticamente, senão o polígono não aparece no mapa.
      if (result.layer_id) {
        const checkbox = document.getElementById(`layer-${result.layer_id}`);
        if (checkbox && !checkbox.checked) {
          checkbox.checked = true;
          checkbox.dispatchEvent(new Event("change"));
        }
      }
    }
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
    };

    btn.addEventListener("click", async () => {
      errorEl.hidden = true;
      try {
        const current = await fetchJSON(API.settings);
        for (const [key, el] of Object.entries(fields)) {
          if (current[key] != null) el.value = current[key];
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

  // Popup padrão usado tanto no clique de uma feature quanto num
  // resultado de busca — cabeçalho com a cor da camada + tabela de
  // atributos, combinando com o tema escuro do resto do app.
  function buildPopupHtml(titulo, cor, entradas) {
    const corpo = entradas.length
      ? `<table class="sigview-popup-table">${entradas
          .map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${escapeHtml(String(v))}</td></tr>`)
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
