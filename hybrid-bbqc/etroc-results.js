(() => {
  "use strict";
  const DATASET = "ETROC_OI_2608";
  const BASE = `/data/etroc-optical/${DATASET}/`;
  const LABELS = Object.freeze(["GREEN", "BLUE", "YELLOW", "RED", "PENDING"]);
  const ALGORITHM = ["GREEN", "BLUE", "YELLOW", "RED", "NEED_INSPECT"];
  const FIELDS = ["green_count", "blue_count", "yellow_count", "red_candidate_count", "needs_inspection_count"];
  const COLORS = {GREEN: "#44db93", BLUE: "#70baff", YELLOW: "#ffda69", RED: "#ff7d89", PENDING: "#e5e7eb"};
  const exact = (object, fields) => object && typeof object === "object" && !Array.isArray(object)
    && Object.keys(object).length === fields.length && fields.every(key => Object.hasOwn(object, key));
  const counts = () => Object.fromEntries(LABELS.map(label => [label, 0]));

  function reconcile(records, payload, publicationSha256) {
    if (!exact(payload, ["dataset_id", "publication_sha256", "record_count", "position_count", "target_count", "reviewed_target_count", "results"])
      || payload.dataset_id !== DATASET || !/^[0-9a-f]{64}$/.test(publicationSha256) || payload.publication_sha256 !== publicationSha256
      || payload.record_count !== records.length || !exact(payload.results, records.map(record => record.acquisition_id))) {
      throw new Error("Current results publication is unavailable or mismatched");
    }
    const models = records.map(record => {
      const item = payload.results[record.acquisition_id];
      if (!exact(item, ["acquisition_id", "etroc_serial", "target_count", "reviewed_target_count", "status", "analysis_run_id", "labelled_montage_sha256", "clean_montage_sha256", "position_publication_sha256", "geometry_version", "algorithm_labels", "human_labels"])
        || item.acquisition_id !== record.acquisition_id || item.etroc_serial !== record.etroc_serial || item.analysis_run_id !== record.analysis_run_id
        || item.labelled_montage_sha256 !== record.montage_sha256 || item.clean_montage_sha256 !== record.clean_montage_sha256
        || item.position_publication_sha256 !== record.position_publication_sha256 || item.geometry_version !== record.position_geometry_version
        || item.target_count !== record.position_review_target_count || !Array.isArray(item.algorithm_labels) || item.algorithm_labels.length !== record.position_count
        || !item.human_labels || typeof item.human_labels !== "object" || Array.isArray(item.human_labels)) throw new Error("Current acquisition results are malformed");
      const algorithmCounts = Object.fromEntries(ALGORITHM.map(label => [label, 0]));
      item.algorithm_labels.forEach(label => {
        if (!ALGORITHM.includes(label)) throw new Error("Unknown algorithm label");
        algorithmCounts[label]++;
      });
      if (ALGORITHM.some((label, index) => algorithmCounts[label] !== record[FIELDS[index]])) throw new Error("Algorithm partition mismatch");
      Object.entries(item.human_labels).forEach(([key, review]) => {
        if (!/^(0|[1-9][0-9]{0,2})$/.test(key) || item.algorithm_labels[Number(key)] !== "NEED_INSPECT"
          || !exact(review, ["label", "current_event_id"]) || !LABELS.slice(0, 4).includes(review.label)
          || !Number.isSafeInteger(review.current_event_id) || review.current_event_id <= 0) throw new Error("Invalid current human label");
      });
      const reviewed = Object.keys(item.human_labels).length;
      const status = item.target_count === 0 ? "not_applicable" : reviewed === item.target_count ? "review_complete" : "review_pending";
      if (item.reviewed_target_count !== reviewed || item.status !== status) throw new Error("Review completion mismatch");
      const categories = counts();
      const positions = item.algorithm_labels.map((algorithm, position) => {
        const human = item.human_labels[String(position)];
        const label = algorithm === "NEED_INSPECT" ? human?.label || "PENDING" : algorithm;
        const source = algorithm !== "NEED_INSPECT" ? "algorithm" : human ? "human" : "pending";
        categories[label]++;
        return {position, label, source, event_id: human?.current_event_id || null};
      });
      return {...record, target_count: item.target_count, reviewed_target_count: reviewed, status, categories, positions};
    });
    const totals = summarize(models);
    if (payload.position_count !== totals.positions || payload.target_count !== totals.targets || payload.reviewed_target_count !== totals.human) throw new Error("Current result aggregate mismatch");
    return models;
  }

  function summarize(models) {
    const summary = {records: models.length, positions: 0, targets: 0, human: 0, algorithm: 0, pending: 0, noTargets: 0, complete: 0, categories: counts()};
    models.forEach(model => {
      summary.positions += model.positions.length;
      summary.targets += model.target_count;
      summary.human += model.reviewed_target_count;
      summary.algorithm += model.positions.length - model.target_count;
      summary.pending += model.categories.PENDING;
      summary.noTargets += Number(model.target_count === 0);
      summary.complete += Number(model.status === "review_complete");
      LABELS.forEach(label => { summary.categories[label] += model.categories[label]; });
    });
    return summary;
  }

  function select(models, filters = {}) {
    const needle = (filters.serial || "").trim().toLowerCase();
    return models.filter(model => (!filters.wafer || model.wafer === filters.wafer)
      && (!needle || model.etroc_serial.toLowerCase().includes(needle))
      && (!filters.category || model.categories[filters.category] > 0)
      && (!filters.status || filters.status === "all" || (filters.status === "pending" ? model.status === "review_pending"
        : filters.status === "complete" ? model.status === "review_complete" : model.target_count === 0)));
  }

  function node(tag, className = "", text) {
    const result = document.createElement(tag);
    if (className) result.className = className;
    if (text !== undefined) result.textContent = String(text);
    return result;
  }
  function svgNode(tag, attrs = {}) {
    const result = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs).forEach(([key, value]) => result.setAttribute(key, String(value)));
    return result;
  }
  function renderOverlay(model) {
    const svg = svgNode("svg", {viewBox: "0 0 2400 2176", "aria-label": `${model.etroc_serial}: effective labels on all 256 positions`, role: "img"});
    svg.classList.add("etroc-effective-overlay");
    model.positions.forEach(position => {
      const x = position.position % 16 * 150, y = Math.floor(position.position / 16) * 136;
      const group = svgNode("g", {"data-position": position.position, "data-label": position.label, "data-source": position.source});
      const title = svgNode("title");
      title.textContent = `Position ${position.position}: ${position.label} · ${position.source}${position.event_id ? ` · event ${position.event_id}` : ""}`;
      const rect = svgNode("rect", {x: x + 2, y: y + 2, width: 146, height: 132, fill: "none", stroke: COLORS[position.label], "stroke-width": 4});
      if (position.label === "PENDING") rect.setAttribute("stroke-dasharray", "9 5");
      // Keep the central evidence clear: identity and classification share the upper edge only.
      const badge = svgNode("rect", {x: x + 4, y: y + 1, width: 142, height: 39, fill: "#111", "data-etroc-location-badge": ""});
      const number = svgNode("text", {x: x + 7, y: y + 32, fill: "#fff", "font-size": 32, "font-weight": 800, class: "etroc-location-number", "data-etroc-location-number": position.position});
      number.textContent = String(position.position);
      const text = svgNode("text", {x: x + 69, y: y + 18, fill: COLORS[position.label], "font-size": 13, "font-weight": 700});
      text.textContent = `${position.label === "PENDING" ? "?" : position.label} ${position.source === "human" ? "H" : position.source === "algorithm" ? "A" : ""}`;
      group.append(title, rect, badge, number, text); svg.append(group);
    });
    return svg;
  }

  function categoryStrip(categories) {
    const strip = node("div", "etroc-result-categories");
    LABELS.forEach(label => {
      const metric = node("span", `etroc-result-category ${label.toLowerCase()}`, `${label} ${categories[label]}`);
      metric.dataset.category = label;
      strip.append(metric);
    });
    return strip;
  }

  // A separate, read-only surface; only reconciled models enter this viewer.
  function createViewer() {
    const dialog = node("dialog", "etroc-result-viewer");
    dialog.setAttribute("data-etroc-result-viewer", "");
    dialog.setAttribute("aria-labelledby", "etroc-result-viewer-title");
    const heading = node("h2"); heading.id = "etroc-result-viewer-title";
    const closeButton = node("button", "optical-table-link", "Close reviewed montage");
    closeButton.type = "button";
    closeButton.setAttribute("data-etroc-result-viewer-close", "");
    const header = node("div", "etroc-result-viewer-header"); header.append(heading, closeButton);
    const status = node("p"); status.setAttribute("role", "status");
    status.setAttribute("data-etroc-result-viewer-status", "");
    const content = node("div");
    dialog.append(header, status, content); document.body.append(dialog);
    let generation = 0, controller = null, trigger = null;
    const urls = new Set();
    const release = url => { if (urls.delete(url)) URL.revokeObjectURL(url); };
    function cleanup() {
      ++generation; controller?.abort(); controller = null;
      urls.forEach(release); content.replaceChildren();
      const previous = trigger; trigger = null;
      if (previous?.isConnected) previous.focus();
    }
    function close() {
      const previous = trigger;
      cleanup();
      if (dialog.open) dialog.close();
      // The opener is inert until the native modal has actually closed.
      if (previous?.isConnected) previous.focus();
    }
    closeButton.addEventListener("click", close);
    // Invalidate synchronously, rather than waiting for the queued close event.
    dialog.addEventListener("cancel", event => { event.preventDefault(); close(); });
    dialog.addEventListener("close", () => { if (!dialog.open) cleanup(); });
    dialog.addEventListener("click", event => {
      if (event.target !== dialog) return;
      const box = dialog.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) close();
    });
    async function open(model, opener) {
      close(); trigger = opener;
      const token = ++generation;
      controller = new AbortController();
      const current = () => token === generation && dialog.open;
      heading.textContent = `${model.etroc_serial} · Current reviewed montage`;
      status.textContent = "Verifying clean optical evidence…";
      dialog.showModal(); closeButton.focus();
      let url = null, displayed = false;
      try {
        const response = await fetch(BASE + model.clean_montage_uri, {method: "GET", credentials: "same-origin", cache: "no-store", signal: controller.signal});
        if (!current()) return;
        if (!response.ok) throw new Error("Clean montage request failed");
        const bytes = await response.arrayBuffer();
        if (!current()) return;
        const digest = await crypto.subtle.digest("SHA-256", bytes);
        if (!current()) return;
        const hash = [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, "0")).join("");
        if (hash !== model.clean_montage_sha256) throw new Error("Clean montage integrity mismatch");
        url = URL.createObjectURL(new Blob([bytes], {type: "image/jpeg"})); urls.add(url);
        const image = node("img"); image.src = url; image.width = 2400; image.height = 2176;
        image.alt = `${model.etroc_serial}: verified clean evidence with current effective labels`;
        await image.decode();
        if (!current()) return;
        image.setAttribute("data-etroc-result-viewer-image", "");
        const montage = node("div", "etroc-result-montage"); montage.append(image, renderOverlay(model));
        const scroller = node("div", "etroc-result-viewer-scroll");
        scroller.setAttribute("data-etroc-result-viewer-scroll", "");
        scroller.setAttribute("tabindex", "0");
        scroller.setAttribute("role", "region");
        scroller.setAttribute("aria-label", "Numbered montage, positions 0–255. Scroll to inspect all cells.");
        scroller.append(montage);
        content.replaceChildren(categoryStrip(model.categories),
          node("p", "", `${model.reviewed_target_count} human · ${model.positions.length - model.target_count} algorithm · ${model.categories.PENDING} unreviewed. H = human; A = algorithm; ? = pending. Positions 0–255. Scroll montage to inspect. Read-only.`), scroller);
        displayed = true;
        status.textContent = "Verified clean montage · current effective labels on all 256 positions";
      } catch (error) {
        if (current()) {
          content.replaceChildren();
          status.textContent = "Reviewed montage unavailable — clean evidence could not be verified or decoded. Close and reopen to retry; no original-image fallback.";
        }
      } finally {
        if (url && !displayed) release(url);
      }
    }
    return {open, close};
  }
  let resultViewer = null;
  function openResultViewer(model, trigger) {
    resultViewer ||= createViewer();
    void resultViewer.open(model, trigger);
  }

  function renderCard(model, onOpen = openResultViewer) {
    const card = node("article", "etroc-pool-card etroc-result-card");
    card.dataset.etrocSerial = model.etroc_serial;
    card.dataset.etrocAcquisition = model.acquisition_id;
    const body = node("div", "etroc-pool-card-body");
    body.append(node("h3", "", model.etroc_serial));
    const figure = node("button", "etroc-result-montage");
    figure.type = "button";
    figure.setAttribute("aria-label", `${model.etroc_serial}: open current reviewed montage`);
    figure.setAttribute("aria-haspopup", "dialog");
    figure.addEventListener("click", () => onOpen(model, figure));
    card.addEventListener("click", event => {
      if (event.defaultPrevented || event.button !== 0 || String(globalThis.getSelection?.() || "").trim()
        || event.target.closest("button, a, details, summary, input, select, textarea, [role='button'], [contenteditable]")) return;
      onOpen(model, figure);
    });
    const image = node("img");
    image.src = BASE + model.clean_montage_uri; image.loading = "lazy"; image.width = 2400; image.height = 2176;
    image.alt = `${model.etroc_serial} clean optical evidence; effective labels in overlay`;
    image.addEventListener("error", () => {
      figure.replaceChildren(node("p", "etroc-pool-error", "Clean montage unavailable. Open verified details to retry; no original-image fallback."));
    });
    figure.append(image, renderOverlay(model));
    body.append(categoryStrip(model.categories));
    body.append(node("p", "", `${model.reviewed_target_count} human · ${model.positions.length - model.target_count} algorithm · ${model.categories.PENDING} unreviewed`));
    body.append(node("p", "etroc-result-coverage", model.target_count === 0 ? "No review targets · algorithm classifications retained"
      : `${model.reviewed_target_count}/${model.target_count} target labels · ${model.status === "review_complete" ? "Review complete" : "Review pending"}`));
    const inspect = node("button", "optical-table-link", "Inspect / correct labels & history");
    inspect.type = "button"; inspect.dataset.etrocInspect = model.acquisition_id;
    inspect.setAttribute("aria-label", `${model.etroc_serial}: inspect evidence, height measurements, correct labels and view history`);
    body.append(inspect);
    const original = node("details", "etroc-original-evidence");
    original.append(node("summary", "", "Original evidence"));
    const link = node("a", "", "Open original algorithm-labelled montage");
    link.href = BASE + model.montage_uri; link.target = "_blank"; link.rel = "noopener";
    original.append(link, node("p", "", `Original algorithm: GREEN ${model.green_count} · BLUE ${model.blue_count} · YELLOW ${model.yellow_count} · RED ${model.red_candidate_count} · NEED_INSPECT ${model.needs_inspection_count}.`),
      node("p", "", `Analysis run: ${model.analysis_run_id}. Acquisition: ${model.acquisition_id}.`));
    body.append(original); card.append(figure, body);
    return card;
  }

  globalThis.ETROCResultsContract = Object.freeze({reconcile, summarize, select, renderOverlay, renderCard, createViewer});
  const root = document.querySelector("[data-etroc-results]");
  if (!root) return;
  const pool = document.querySelector("[data-etroc-optical-pool]");
  const status = root.querySelector("[data-etroc-results-status]");
  const metrics = root.querySelector("[data-etroc-result-metrics]");
  const categories = root.querySelector("[data-etroc-result-categories]");
  const filterState = root.querySelector("[data-etroc-results-filter-state]");
  const wafer = root.querySelector("[data-etroc-wafer-filter]");
  const serial = root.querySelector("[data-etroc-search]");
  const category = root.querySelector("[data-etroc-result-category]");
  const completion = root.querySelector("[data-etroc-result-completion]");
  let publication = null, models = null, generation = 0;

  function clear(message, failed = false) {
    resultViewer?.close();
    models = null; pool.replaceChildren(); metrics.replaceChildren(); categories.replaceChildren();
    status.textContent = message; status.classList.toggle("failed", failed);
    root.setAttribute("aria-busy", String(!failed)); pool.setAttribute("aria-busy", String(!failed));
    filterState.textContent = "Current results unavailable until validated";
  }
  function apply() {
    if (!models) return;
    const visible = select(models, {wafer: wafer.value, serial: serial.value, category: category.value, status: completion.value});
    const totals = summarize(visible);
    metrics.replaceChildren();
    [["ETROCs shown", `${totals.records} / ${models.length}`], ["Positions", totals.positions.toLocaleString("en-US")],
      ["Human target labels", `${totals.human} / ${totals.targets}`], ["Algorithm labels retained", totals.algorithm.toLocaleString("en-US")],
      ["Pending review positions", totals.pending], ["ETROCs without targets", totals.noTargets]].forEach(([label, value]) => {
      const metric = node("div", "optical-analytics-kpi"); metric.append(node("span", "", label), node("strong", "", value)); metrics.append(metric);
    });
    categories.replaceChildren(categoryStrip(totals.categories));
    filterState.textContent = `${totals.records} / ${models.length} ETROCs · ${totals.positions.toLocaleString("en-US")} positions · filters apply to cards and counts`;
    pool.replaceChildren();
    [...new Set(visible.map(model => model.wafer))].forEach(waferName => {
      const subset = visible.filter(model => model.wafer === waferName);
      const group = node("section", "etroc-pool-group");
      const heading = node("div", "wafer"); heading.append(node("h3", "", waferName), node("span", "", `${subset.length} ETROCs`));
      const grid = node("div", "etroc-pool-grid"); subset.forEach(model => grid.append(renderCard(model)));
      group.append(heading, grid); pool.append(group);
    });
    if (!visible.length) pool.append(node("p", "optical-chart-empty", "No ETROCs match these filters. Select All review states to see the full result cohort."));
  }
  async function refresh() {
    resultViewer?.close();
    if (!publication) return;
    const token = ++generation;
    clear("Loading current reviewed results…");
    try {
      const response = await fetch(`/api/etroc-position-reviews/results?dataset_id=${DATASET}`, {credentials: "same-origin", cache: "no-store", headers: {Accept: "application/json"}});
      if (!response.ok) throw new Error(`Result service HTTP ${response.status}`);
      const next = reconcile(publication.records, await response.json(), publication.publicationSha256);
      if (token !== generation) return;
      models = next; apply();
      const totals = summarize(models);
      status.textContent = `${totals.records} ETROCs · ${totals.human}/${totals.targets} human target labels · ${totals.pending} unreviewed · ${totals.noTargets} without targets`;
      root.setAttribute("aria-busy", "false"); pool.setAttribute("aria-busy", "false");
    } catch (error) {
      if (token !== generation) return;
      clear("Current reviewed results unavailable — no final counts or montage fallback. Retry when the review service is available.", true);
      console.error("ETROC results unavailable", error);
    }
  }
  [wafer, serial, category, completion].forEach(control => control.addEventListener(control === serial ? "input" : "change", apply));
  root.querySelector("[data-etroc-results-refresh]").addEventListener("click", refresh);
  globalThis.addEventListener("etroc-optical-publication", event => { publication = event.detail; void refresh(); });
  globalThis.addEventListener("etroc-position-review-updated", () => { void refresh(); });
  globalThis.addEventListener("etroc-optical-unavailable", () => { ++generation; clear("ETROC publication unavailable — current reviewed results cannot be verified.", true); });
})();
