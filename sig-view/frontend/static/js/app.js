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
  };

  const state = {
    map: null,
    marker: null,
    layerIds: new Set(), // camadas já adicionadas ao mapa
  };

  async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Erro ${res.status} em ${url}`);
    }
    return res.json();
  }

  async function init() {
    const config = await fetchJSON(API.config);
    state.map = createMap(config);
    state.map.on("load", async () => {
      await loadLayersPanel();
    });
    setupSearch();
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

    if (config.bounds) {
      const [west, south, east, north] = config.bounds;
      map.fitBounds([[west, south], [east, north]], { padding: 20, duration: 0 });
    }
    return map;
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
    for (const layer of data.layers) {
      const li = document.createElement("li");
      const checkboxId = `layer-${layer.id}`;
      li.innerHTML = `
        <input type="checkbox" id="${checkboxId}" />
        <label for="${checkboxId}">${escapeHtml(layer.nome)}${
        layer.feature_count != null ? ` <small>(${layer.feature_count})</small>` : ""
      }</label>
      `;
      const checkbox = li.querySelector("input");
      checkbox.addEventListener("change", () => toggleLayer(layer.id, checkbox.checked));
      listEl.appendChild(li);
    }
  }

  async function toggleLayer(layerId, enabled) {
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
      return;
    }

    if (state.layerIds.has(layerId)) return; // já carregada

    let geojson;
    try {
      geojson = await fetchJSON(API.layer(layerId));
    } catch (err) {
      alert(`Não foi possível carregar a camada: ${err.message}`);
      return;
    }

    state.map.addSource(sourceId, { type: "geojson", data: geojson });

    state.map.addLayer({
      id: fillId,
      type: "fill",
      source: sourceId,
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "fill-color": "#3fa9f5", "fill-opacity": 0.15 },
    });
    state.map.addLayer({
      id: lineId,
      type: "line",
      source: sourceId,
      filter: ["any", ["==", ["geometry-type"], "Polygon"], ["==", ["geometry-type"], "LineString"]],
      paint: { "line-color": "#3fa9f5", "line-width": 2 },
    });
    state.map.addLayer({
      id: pointId,
      type: "circle",
      source: sourceId,
      filter: ["==", ["geometry-type"], "Point"],
      paint: { "circle-radius": 5, "circle-color": "#3fa9f5", "circle-stroke-color": "#fff", "circle-stroke-width": 1 },
    });

    state.map.on("click", pointId, (e) => {
      const feature = e.features[0];
      const props = feature.properties || {};
      const html = Object.entries(props)
        .map(([k, v]) => `<p><strong>${escapeHtml(k)}:</strong> ${escapeHtml(String(v))}</p>`)
        .join("");
      new maplibregl.Popup()
        .setLngLat(feature.geometry.coordinates)
        .setHTML(`<div class="sigview-popup"><h3>${escapeHtml(layerId)}</h3>${html}</div>`)
        .addTo(state.map);
    });

    state.layerIds.add(layerId);
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
      state.map.flyTo({ center: [result.lon, result.lat], zoom: 16 });
      if (state.marker) state.marker.remove();
      state.marker = new maplibregl.Marker({ color: "#3fa9f5" })
        .setLngLat([result.lon, result.lat])
        .setPopup(new maplibregl.Popup().setHTML(`<div class="sigview-popup"><h3>${escapeHtml(result.label)}</h3></div>`))
        .addTo(state.map);
    }
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
