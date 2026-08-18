(() => {
  "use strict";

  const DATA_URL = "/data/etroc-optical/ETROC_OI_2608/chips.json";
  const DATA_BASE = "/data/etroc-optical/ETROC_OI_2608/";
  const EXPECTED_WAFERS = new Map([["W02G4", 18], ["W03F7", 9], ["W05E5", 9]]);
  const APPROVED_SERIALS = new Set([
    "W02G4-44", "W02G4-45", "W02G4-49", "W02G4-50", "W02G4-51", "W02G4-55", "W02G4-60", "W02G4-63", "W02G4-64", "W02G4-66", "W02G4-67", "W02G4-68", "W02G4-70", "W02G4-78", "W02G4-79", "W02G4-80", "W02G4-81", "W02G4-82",
    "W03F7-75", "W03F7-76", "W03F7-77", "W03F7-78", "W03F7-79", "W03F7-80", "W03F7-81", "W03F7-83", "W03F7-85",
    "W05E5-24", "W05E5-30", "W05E5-36", "W05E5-38", "W05E5-39", "W05E5-41", "W05E5-64", "W05E5-68", "W05E5-75",
  ]);
  const root = document.querySelector("[data-etroc-optical-pool]");
  const status = document.querySelector("[data-etroc-optical-status]");
  globalThis.ETROCOpticalContract = Object.freeze({ validate });
  if (!root || !status) return;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }

  function safeAssetUri(uri, role) {
    const pattern = role === "montage"
      ? /^montages\/[A-Z0-9]+-[0-9]+\.jpg$/
      : /^previews\/[A-Z0-9]+-[0-9]+\.jpg$/;
    if (typeof uri !== "string" || !pattern.test(uri)) {
      throw new Error(`invalid ${role} URI`);
    }
    return DATA_BASE + uri;
  }

  function validate(payload) {
    if (!payload || payload.schema_version !== "1.0" || payload.dataset_id !== "ETROC_OI_2608" || payload.publication_status !== "exploratory_review_pending") {
      throw new Error("unexpected dataset identity, schema, or status");
    }
    if (payload.record_count !== 36 || payload.position_record_count !== 9216 || payload.expected_positions_per_chip !== 256) {
      throw new Error("unexpected top-level cardinality");
    }
    if (!Array.isArray(payload.records) || payload.records.length !== 36) {
      throw new Error("expected exactly 36 ETROC records");
    }
    const seen = new Set();
    const counts = new Map();
    const countFields = ["green_count", "blue_count", "yellow_count", "red_candidate_count", "needs_inspection_count", "review_candidate_count", "optical_no_ball_candidate_count"];
    payload.records.forEach((record) => {
      const identity = /^(W02G4|W03F7|W05E5)-([0-9]+)$/.exec(record.etroc_serial);
      if (!identity || !APPROVED_SERIALS.has(record.etroc_serial) || identity[1] !== record.wafer || identity[2] !== String(record.chip)) throw new Error("invalid or inconsistent ETROC identity");
      if (seen.has(record.etroc_serial)) throw new Error("duplicate ETROC serial");
      seen.add(record.etroc_serial);
      if (record.image_count !== 256 || record.height_count !== 256 || record.position_count !== 256) {
        throw new Error("incomplete ETROC acquisition");
      }
      if (record.publication_status !== "exploratory_review_pending" || record.review_state !== "not_reviewed") {
        throw new Error("unexpected review state");
      }
      countFields.forEach((field) => {
        if (!Number.isSafeInteger(record[field]) || record[field] < 0 || record[field] > 256) throw new Error(`invalid ${field}`);
      });
      if (record.green_count + record.blue_count + record.yellow_count + record.red_candidate_count + record.needs_inspection_count !== 256) {
        throw new Error("candidate category partition does not total 256");
      }
      if (record.optical_no_ball_candidate_count > record.red_candidate_count) throw new Error("invalid no-ball/red relationship");
      if (record.montage_uri !== `montages/${record.etroc_serial}.jpg` || record.preview_uri !== `previews/${record.etroc_serial}.jpg`) {
        throw new Error("asset identity mismatch");
      }
      if (typeof record.acquisition_id !== "string" || !record.acquisition_id.startsWith(`ETROC_OI_2608:${record.etroc_serial}:`)) {
        throw new Error("acquisition identity mismatch");
      }
      safeAssetUri(record.montage_uri, "montage");
      safeAssetUri(record.preview_uri, "preview");
      counts.set(record.wafer, (counts.get(record.wafer) || 0) + 1);
    });
    EXPECTED_WAFERS.forEach((expected, wafer) => {
      if (counts.get(wafer) !== expected || payload.wafer_counts?.[wafer] !== expected) throw new Error(`unexpected ${wafer} count`);
    });
    return payload.records;
  }

  function renderSummary(records) {
    const summary = element("section", "etroc-pool-summary");
    summary.setAttribute("aria-label", "ETROC_OI_2608 dataset summary");
    [
      ["ETROCs", records.length],
      ["Positions", records.reduce((total, record) => total + record.position_count, 0).toLocaleString()],
      ["Coverage", "256 / 256 each"],
      ["Review state", "Pending"],
    ].forEach(([label, value]) => {
      const metric = element("div", "etroc-pool-metric");
      metric.append(element("span", "", label), element("strong", "", value));
      summary.append(metric);
    });
    return summary;
  }

  function renderCard(record) {
    const card = element("a", "etroc-pool-card");
    card.href = safeAssetUri(record.montage_uri, "montage");
    card.target = "_blank";
    card.rel = "noopener";
    card.dataset.etrocSerial = record.etroc_serial;

    const image = document.createElement("img");
    image.loading = "lazy";
    image.src = safeAssetUri(record.preview_uri, "preview");
    image.alt = `${record.etroc_serial} pre-bonding optical inspection montage preview`;
    image.width = 720;
    image.height = 653;

    const body = element("div", "etroc-pool-card-body");
    const heading = element("div", "etroc-pool-card-heading");
    heading.append(
      element("strong", "", record.etroc_serial),
      element("span", "etroc-pool-badge", "Exploratory")
    );
    const coverage = element("span", "", `${record.position_count}/256 positions · review pending`);
    const candidates = element(
      "em",
      "",
      `${record.red_candidate_count} red candidate · ${record.needs_inspection_count} needs inspection · ${record.optical_no_ball_candidate_count} optical no-ball candidate`
    );
    const warning = element("small", "", "Algorithmic screening only — not a confirmed QC disposition");
    body.append(heading, coverage, candidates, warning);
    card.append(image, body);
    return card;
  }

  function render(records) {
    const fragment = document.createDocumentFragment();
    fragment.append(renderSummary(records));
    EXPECTED_WAFERS.forEach((expected, wafer) => {
      const group = element("section", "etroc-pool-group");
      const heading = element("div", "wafer");
      heading.append(
        element("h3", "", wafer),
        element("span", "", `${expected} ETROCs · ETROC_OI_2608 exploratory montages`)
      );
      const grid = element("div", "etroc-pool-grid");
      records.filter((record) => record.wafer === wafer).forEach((record) => grid.append(renderCard(record)));
      group.append(heading, grid);
      fragment.append(group);
    });
    root.replaceChildren(fragment);
    root.setAttribute("aria-busy", "false");
    status.textContent = "ETROC_OI_2608 loaded: 36 ETROCs · 9,216 positions · review pending";
    status.classList.add("loaded");
  }

  fetch(DATA_URL, { credentials: "same-origin", headers: { Accept: "application/json" } })
    .then((response) => {
      if (!response.ok) throw new Error(`dataset request failed: ${response.status}`);
      return response.json();
    })
    .then(validate)
    .then(render)
    .catch((error) => {
      root.replaceChildren();
      root.setAttribute("aria-busy", "false");
      const message = element("p", "etroc-pool-error", "ETROC optical dataset unavailable");
      message.setAttribute("role", "alert");
      root.append(message);
      status.textContent = "ETROC optical dataset unavailable";
      status.classList.add("failed");
      console.error("ETROC optical pool load failed", error);
    });
})();
