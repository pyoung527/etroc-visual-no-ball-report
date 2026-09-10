(() => {
  "use strict";

  const DATA_URL = "/data/etroc-optical/ETROC_OI_2608/chips.json";
  const DATA_BASE = "/data/etroc-optical/ETROC_OI_2608/";
  const EXPECTED_WAFERS = new Map([["W02G4", 18], ["W03F7", 9], ["W05E5", 9]]);
  const EXPECTED_ANALYSIS_RUNS = new Map([
    ["ETROC_OI_2608:common-baseline-v0:pack1", { count: 9, batch: "pack1" }],
    ["ETROC_OI_2608:common-baseline-v0:pack1_original", { count: 8, batch: "pack1_original" }],
    ["ETROC_OI_2608:common-baseline-v0:pack2", { count: 17, batch: "pack2" }],
    ["ETROC_OI_2608:common-baseline-v0:re_chip24", { count: 1, batch: "re_chip24" }],
    ["ETROC_OI_2608:common-baseline-v0:re_chip51", { count: 1, batch: "re_chip51" }],
  ]);
  const SHA256_PATTERN = /^[0-9a-f]{64}$/;
  const EXPECTED_PIPELINE_FILES = new Set([
    "etroc_inspection/__init__.py",
    "etroc_inspection/classify.py",
    "etroc_inspection/cli.py",
    "etroc_inspection/config.py",
    "etroc_inspection/detector.py",
    "etroc_inspection/golden.py",
    "etroc_inspection/io.py",
    "etroc_inspection/visualize.py",
  ]);
  const SUPPLEMENT_SERIALS = new Set(["W02G4-51", "W05E5-24"]);
  const APPROVED_SERIALS = new Set([
    "W02G4-44", "W02G4-45", "W02G4-49", "W02G4-50", "W02G4-51", "W02G4-55", "W02G4-60", "W02G4-63", "W02G4-64", "W02G4-66", "W02G4-67", "W02G4-68", "W02G4-70", "W02G4-78", "W02G4-79", "W02G4-80", "W02G4-81", "W02G4-82",
    "W03F7-75", "W03F7-76", "W03F7-77", "W03F7-78", "W03F7-79", "W03F7-80", "W03F7-81", "W03F7-83", "W03F7-85",
    "W05E5-24", "W05E5-30", "W05E5-36", "W05E5-38", "W05E5-39", "W05E5-41", "W05E5-64", "W05E5-68", "W05E5-75",
  ]);
  const root = document.querySelector("[data-etroc-optical-pool]");
  const status = document.querySelector("[data-etroc-optical-status]");
  const statsRoot = document.querySelector("#etroc-optical-analytics");
  const statsStatus = document.querySelector("[data-etroc-analytics-state]");
  async function parseVerifiedPublication(bytes) {
    const publicationSha256 = await crypto.subtle.digest("SHA-256", bytes).then((digest) => [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join(""));
    const payload = JSON.parse(new TextDecoder().decode(bytes));
    return { payload, records: validate(payload), publicationSha256 };
  }

  globalThis.ETROCOpticalContract = Object.freeze({ validate, summarize, selectRecords, summarizeProvenance, parseVerifiedPublication });
  if (!root || !status) return;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }

  function safeAssetUri(uri, role) {
    const pattern = role === "montage"
      ? /^montages\/sha256\/[0-9a-f]{64}\.jpg$/
      : role === "clean montage"
        ? /^clean-montages\/sha256\/[0-9a-f]{64}\.jpg$/
        : role === "position publication"
          ? /^positions\/sha256\/[0-9a-f]{64}\.json$/
          : role === "height publication"
            ? /^heights\/sha256\/[0-9a-f]{64}\.json$/
          : /^previews\/[A-Z0-9]+-[0-9]+\.jpg$/;
    if (typeof uri !== "string" || !pattern.test(uri)) {
      throw new Error(`invalid ${role} URI`);
    }
    return DATA_BASE + uri;
  }

  function isSha256(value) {
    return typeof value === "string" && SHA256_PATTERN.test(value) && !/^0{64}$/.test(value);
  }

  function validate(payload) {
    if (!payload || payload.schema_version !== "1.0" || payload.dataset_id !== "ETROC_OI_2608" || payload.publication_status !== "exploratory_review_pending") {
      throw new Error("unexpected dataset identity, schema, or status");
    }
    const topLevelHashes = [
      payload.analysis_config_sha256,
      payload.base_archive_sha256,
      payload.position_results_sha256,
      payload.source_complete_manifest_sha256,
      payload.supplement_archive_sha256,
    ];
    if (topLevelHashes.some((value) => !isSha256(value))) throw new Error("invalid top-level provenance hash");
    if (typeof payload.analysis_created_at_utc !== "string" || !/(?:Z|[+]00:00)$/.test(payload.analysis_created_at_utc) || !Number.isFinite(Date.parse(payload.analysis_created_at_utc))) {
      throw new Error("invalid analysis timestamp");
    }
    const pipelineHashes = payload.pipeline_files_sha256;
    const pipelineFiles = pipelineHashes && typeof pipelineHashes === "object" && !Array.isArray(pipelineHashes) ? Object.keys(pipelineHashes) : [];
    if (pipelineFiles.length !== EXPECTED_PIPELINE_FILES.size || pipelineFiles.some((file) => !EXPECTED_PIPELINE_FILES.has(file)) || Object.values(pipelineHashes || {}).some((value) => !isSha256(value))) {
      throw new Error("invalid pipeline provenance files or hashes");
    }
    if (payload.encoder?.pillow !== "12.2.0" || payload.encoder?.libjpeg !== "6.2") throw new Error("unexpected encoder provenance");
    if (payload.record_count !== 36 || payload.position_record_count !== 9216 || payload.expected_positions_per_chip !== 256
      || payload.position_geometry_version !== "etroc-grid-16x16-v1" || payload.position_review_target_count !== 82) {
      throw new Error("unexpected top-level cardinality");
    }
    if (!Array.isArray(payload.records) || payload.records.length !== 36) {
      throw new Error("expected exactly 36 ETROC records");
    }
    const seen = new Set();
    const counts = new Map();
    const runCounts = new Map();
    const countFields = ["green_count", "blue_count", "yellow_count", "red_candidate_count", "needs_inspection_count", "review_candidate_count", "optical_no_ball_candidate_count", "position_review_target_count"];
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
      const expectedRun = EXPECTED_ANALYSIS_RUNS.get(record.analysis_run_id);
      if (!expectedRun || record.analysis_batch !== expectedRun.batch) throw new Error("unexpected analysis run or batch");
      runCounts.set(record.analysis_run_id, (runCounts.get(record.analysis_run_id) || 0) + 1);
      if (record.height_unit !== "mm" || record.source_width_px !== 2400 || record.source_height_px !== 2176) {
        throw new Error("unexpected source geometry or unit");
      }
      const assetHashes = [record.montage_sha256, record.preview_sha256, record.source_montage_sha256, record.clean_montage_sha256, record.position_publication_sha256, record.height_publication_sha256];
      const assetSizes = [record.montage_size_bytes, record.preview_size_bytes, record.source_montage_size_bytes, record.clean_montage_size_bytes, record.height_publication_size_bytes];
      if (assetHashes.some((value) => !isSha256(value))) throw new Error("invalid record asset hash");
      if (assetSizes.some((value) => !Number.isSafeInteger(value) || value <= 0)) throw new Error("invalid record asset size");
      countFields.forEach((field) => {
        if (!Number.isSafeInteger(record[field]) || record[field] < 0 || record[field] > 256) throw new Error(`invalid ${field}`);
      });
      if (record.green_count + record.blue_count + record.yellow_count + record.red_candidate_count + record.needs_inspection_count !== 256) {
        throw new Error("candidate category partition does not total 256");
      }
      if (record.optical_no_ball_candidate_count > record.red_candidate_count || record.position_review_target_count !== record.needs_inspection_count) throw new Error("invalid candidate relationship");
      if (!record.montage_uri.startsWith("montages/sha256/") || record.preview_uri !== `previews/${record.etroc_serial}.jpg`
        || record.clean_montage_uri !== `clean-montages/sha256/${record.clean_montage_sha256}.jpg`
        || record.position_publication_uri !== `positions/sha256/${record.position_publication_sha256}.json`
        || record.height_publication_uri !== `heights/sha256/${record.height_publication_sha256}.json`
        || record.position_geometry_version !== "etroc-grid-16x16-v1") {
        throw new Error("asset identity mismatch");
      }
      const expectedSourceRevision = SUPPLEMENT_SERIALS.has(record.etroc_serial) ? "supplement-re" : "base";
      if (record.source_revision !== expectedSourceRevision || record.acquisition_id !== `ETROC_OI_2608:${record.etroc_serial}:${expectedSourceRevision}`) {
        throw new Error("acquisition identity or source lineage mismatch");
      }
      safeAssetUri(record.montage_uri, "montage");
      safeAssetUri(record.preview_uri, "preview");
      safeAssetUri(record.clean_montage_uri, "clean montage");
      safeAssetUri(record.position_publication_uri, "position publication");
      safeAssetUri(record.height_publication_uri, "height publication");
      counts.set(record.wafer, (counts.get(record.wafer) || 0) + 1);
    });
    EXPECTED_WAFERS.forEach((expected, wafer) => {
      if (counts.get(wafer) !== expected || payload.wafer_counts?.[wafer] !== expected) throw new Error(`unexpected ${wafer} count`);
    });
    EXPECTED_ANALYSIS_RUNS.forEach((expected, analysisRunId) => {
      if (runCounts.get(analysisRunId) !== expected.count) throw new Error(`unexpected count for ${analysisRunId}`);
    });
    if (runCounts.size !== EXPECTED_ANALYSIS_RUNS.size) throw new Error("unexpected analysis run set");
    return payload.records;
  }

  function summarize(records) {
    if (!Array.isArray(records)) throw new Error("records must be an array");
    const categoryTotals = {
      green: 0,
      blue: 0,
      yellow: 0,
      redCandidate: 0,
      needsInspection: 0,
    };
    let positionCount = 0;
    let reviewCandidateCount = 0;
    let noBallCandidateCount = 0;
    let redCandidateRecordCount = 0;
    let needsInspectionRecordCount = 0;
    let noBallCandidateRecordCount = 0;
    records.forEach((record) => {
      const values = [
        record.position_count,
        record.green_count,
        record.blue_count,
        record.yellow_count,
        record.red_candidate_count,
        record.needs_inspection_count,
        record.review_candidate_count,
        record.optical_no_ball_candidate_count,
      ];
      if (values.some((value) => !Number.isSafeInteger(value) || value < 0)) {
        throw new Error("invalid statistics record");
      }
      const partition = record.green_count + record.blue_count + record.yellow_count + record.red_candidate_count + record.needs_inspection_count;
      if (partition !== record.position_count) throw new Error("statistics partition mismatch");
      positionCount += record.position_count;
      categoryTotals.green += record.green_count;
      categoryTotals.blue += record.blue_count;
      categoryTotals.yellow += record.yellow_count;
      categoryTotals.redCandidate += record.red_candidate_count;
      categoryTotals.needsInspection += record.needs_inspection_count;
      reviewCandidateCount += record.review_candidate_count;
      noBallCandidateCount += record.optical_no_ball_candidate_count;
      redCandidateRecordCount += Number(record.red_candidate_count > 0);
      needsInspectionRecordCount += Number(record.needs_inspection_count > 0);
      noBallCandidateRecordCount += Number(record.optical_no_ball_candidate_count > 0);
    });
    const categoryTotal = Object.values(categoryTotals).reduce((total, value) => total + value, 0);
    if (categoryTotal !== positionCount) throw new Error("statistics totals do not reconcile");
    return {
      recordCount: records.length,
      positionCount,
      categoryTotals,
      reviewCandidateCount,
      noBallCandidateCount,
      redCandidateRecordCount,
      needsInspectionRecordCount,
      noBallCandidateRecordCount,
    };
  }

  function selectRecords(records, wafer = "", query = "") {
    if (!Array.isArray(records)) throw new Error("records must be an array");
    if (typeof wafer !== "string" || (wafer && !EXPECTED_WAFERS.has(wafer))) throw new Error("invalid wafer filter");
    if (typeof query !== "string") throw new Error("invalid serial filter");
    const needle = query.trim().toLowerCase();
    return records.filter((record) => (!wafer || record.wafer === wafer) && (!needle || record.etroc_serial.toLowerCase().includes(needle)));
  }

  function summarizeProvenance(records) {
    if (!Array.isArray(records)) throw new Error("records must be an array");
    const counts = new Map();
    records.forEach((record) => {
      if (!EXPECTED_ANALYSIS_RUNS.has(record.analysis_run_id)) throw new Error("unexpected analysis run");
      counts.set(record.analysis_run_id, (counts.get(record.analysis_run_id) || 0) + 1);
    });
    const runs = [...counts.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([analysisRunId, recordCount]) => ({ analysisRunId, recordCount }));
    return { runCount: runs.length, runs };
  }

  const CATEGORY_SPECS = [
    ["green", "Green", "green"],
    ["blue", "Blue", "blue"],
    ["yellow", "Yellow", "yellow"],
    ["redCandidate", "Red candidate", "red"],
    ["needsInspection", "Needs inspection", "inspect"],
  ];
  const TABLE_SORT_TYPES = Object.freeze({
    etroc_serial: "text", wafer: "text", green_count: "number", blue_count: "number", yellow_count: "number",
    red_candidate_count: "number", needs_inspection_count: "number", review_candidate_count: "number", optical_no_ball_candidate_count: "number",
  });
  let tableSort = { key: "etroc_serial", direction: 1 };

  function ratioLabel(numerator, denominator) {
    const percentage = denominator ? (100 * numerator / denominator) : 0;
    const decimals = percentage > 0 && percentage < 1 ? 2 : 1;
    return `${numerator.toLocaleString("en-US")} / ${denominator.toLocaleString("en-US")} (${percentage.toFixed(decimals)}%)`;
  }

  function setStatistic(selector, value) {
    const node = statsRoot?.querySelector(selector);
    if (node) node.textContent = String(value);
  }

  function renderCategoryRows(target, summary) {
    const fragment = document.createDocumentFragment();
    CATEGORY_SPECS.forEach(([key, label, color]) => {
      const count = summary.categoryTotals[key];
      const row = element("div", "optical-stat-row");
      const heading = element("div", "optical-stat-row-heading");
      heading.append(element("span", `optical-stat-key ${color}`, label), element("strong", "", ratioLabel(count, summary.positionCount)));
      const track = element("div", "optical-stat-track");
      track.setAttribute("role", "img");
      track.setAttribute("aria-label", `${label}: ${ratioLabel(count, summary.positionCount)}`);
      const fill = element("span", `optical-stat-fill ${color}`);
      if (count > 0) fill.classList.add("nonzero");
      fill.style.width = `${summary.positionCount ? (100 * count / summary.positionCount) : 0}%`;
      track.append(fill);
      row.append(heading, track);
      fragment.append(row);
    });
    target.replaceChildren(fragment);
  }

  function renderWaferRows(target, records) {
    const fragment = document.createDocumentFragment();
    EXPECTED_WAFERS.forEach((_expected, wafer) => {
      const subset = records.filter((record) => record.wafer === wafer);
      if (!subset.length) return;
      const summary = summarize(subset);
      const row = element("div", "optical-wafer-row");
      const heading = element("div", "optical-stat-row-heading");
      heading.append(
        element("strong", "", wafer),
        element("span", "", `${summary.recordCount} ETROCs · ${summary.positionCount.toLocaleString("en-US")} positions`)
      );
      const categoryLabels = CATEGORY_SPECS.map(([key, label]) => `${label} ${ratioLabel(summary.categoryTotals[key], summary.positionCount)}`);
      const stack = element("div", "optical-stack");
      stack.setAttribute("role", "img");
      stack.setAttribute("aria-label", `${wafer}: ${categoryLabels.join(", ")}`);
      CATEGORY_SPECS.forEach(([key, label, color]) => {
        const count = summary.categoryTotals[key];
        const segment = element("span", `optical-stack-segment ${color}`);
        if (count > 0) segment.classList.add("nonzero");
        segment.style.width = `${100 * count / summary.positionCount}%`;
        segment.title = `${label}: ${ratioLabel(count, summary.positionCount)}`;
        stack.append(segment);
      });
      const details = element("p", "optical-wafer-details");
      details.textContent = categoryLabels.join(" · ");
      row.append(heading, stack, details);
      fragment.append(row);
    });
    target.replaceChildren(fragment);
  }

  function renderWorkload(target, records) {
    const fragment = document.createDocumentFragment();
    [...records]
      .sort((a, b) => b.review_candidate_count - a.review_candidate_count || a.etroc_serial.localeCompare(b.etroc_serial, undefined, { numeric: true }))
      .forEach((record) => {
        const row = element("div", "optical-workload-row");
        const heading = element("div", "optical-stat-row-heading");
        heading.append(
          element("strong", "", record.etroc_serial),
          element("span", "", `${record.review_candidate_count}/256 review · ${record.red_candidate_count} red · ${record.optical_no_ball_candidate_count} no-ball`)
        );
        const track = element("div", "optical-stat-track");
        track.setAttribute("role", "img");
        track.setAttribute("aria-label", `${record.etroc_serial}: ${record.review_candidate_count} of 256 positions in the review-candidate workload`);
        const fill = element("span", "optical-stat-fill workload");
        if (record.review_candidate_count > 0) fill.classList.add("nonzero");
        fill.style.width = `${100 * record.review_candidate_count / 256}%`;
        track.append(fill);
        row.append(heading, track);
        fragment.append(row);
      });
    target.replaceChildren(fragment || element("p", "optical-chart-empty", "No ETROCs match the current filter"));
  }

  function appendCell(row, value) {
    row.append(element("td", "", value));
  }

  function sortedStatisticsRecords(records) {
    const { key, direction } = tableSort;
    const type = TABLE_SORT_TYPES[key];
    if (!type) throw new Error("invalid ETROC table sort key");
    return [...records].sort((left, right) => {
      const comparison = type === "number"
        ? left[key] - right[key]
        : String(left[key]).localeCompare(String(right[key]), undefined, { numeric: true });
      return direction * (comparison || left.etroc_serial.localeCompare(right.etroc_serial, undefined, { numeric: true }));
    });
  }

  function renderStatisticsTable(records) {
    const body = statsRoot?.querySelector("[data-etroc-stats-table] tbody");
    if (!body) throw new Error("ETROC statistics table is unavailable");
    const fragment = document.createDocumentFragment();
    sortedStatisticsRecords(records)
      .forEach((record) => {
        const row = document.createElement("tr");
        appendCell(row, record.etroc_serial);
        appendCell(row, record.wafer);
        appendCell(row, record.green_count);
        appendCell(row, record.blue_count);
        appendCell(row, record.yellow_count);
        appendCell(row, record.red_candidate_count);
        appendCell(row, record.needs_inspection_count);
        appendCell(row, record.review_candidate_count);
        appendCell(row, record.optical_no_ball_candidate_count);
        const linkCell = document.createElement("td");
        const link = element("a", "optical-table-link", "Open montage");
        link.href = safeAssetUri(record.montage_uri, "montage");
        link.target = "_blank";
        link.rel = "noopener";
        link.setAttribute("aria-label", `Open ${record.etroc_serial} full optical montage`);
        linkCell.append(link);
        row.append(linkCell);
        fragment.append(row);
      });
    body.replaceChildren(fragment);
  }

  function renderStatistics(records) {
    if (!statsRoot) return;
    const summary = summarize(records);
    setStatistic('[data-etroc-kpi="records"]', summary.recordCount.toLocaleString("en-US"));
    setStatistic('[data-etroc-kpi="positions"]', summary.positionCount.toLocaleString("en-US"));
    setStatistic('[data-etroc-kpi="red"]', summary.categoryTotals.redCandidate.toLocaleString("en-US"));
    setStatistic('[data-etroc-kpi="inspect"]', summary.categoryTotals.needsInspection.toLocaleString("en-US"));
    setStatistic('[data-etroc-kpi="noball"]', summary.noBallCandidateCount.toLocaleString("en-US"));
    setStatistic('[data-etroc-kpi-detail="red"]', ratioLabel(summary.categoryTotals.redCandidate, summary.positionCount));
    setStatistic('[data-etroc-kpi-detail="inspect"]', ratioLabel(summary.categoryTotals.needsInspection, summary.positionCount));
    setStatistic('[data-etroc-kpi-detail="noball"]', ratioLabel(summary.noBallCandidateCount, summary.positionCount));

    const categoryBody = statsRoot.querySelector("[data-etroc-category-body]");
    const waferBody = statsRoot.querySelector("[data-etroc-wafer-body]");
    const workloadBody = statsRoot.querySelector("[data-etroc-workload-body]");
    if (!categoryBody || !waferBody || !workloadBody) throw new Error("ETROC statistics chart body is unavailable");
    if (!records.length) {
      const emptyText = "No ETROCs match the current filter";
      categoryBody.replaceChildren(element("p", "optical-chart-empty", emptyText));
      waferBody.replaceChildren(element("p", "optical-chart-empty", emptyText));
      workloadBody.replaceChildren(element("p", "optical-chart-empty", emptyText));
    } else {
      renderCategoryRows(categoryBody, summary);
      renderWaferRows(waferBody, records);
      renderWorkload(workloadBody, records);
    }
    renderStatisticsTable(records);
    return summary;
  }

  function initStatisticsTableSorting(apply) {
    const headers = [...statsRoot.querySelectorAll("[data-etroc-sort]")];
    if (headers.length !== Object.keys(TABLE_SORT_TYPES).length) throw new Error("ETROC sortable table headers are incomplete");

    function reflectSortState() {
      headers.forEach((header) => {
        header.setAttribute("aria-sort", "none");
        if (header.dataset.etrocSort === tableSort.key) {
          header.setAttribute("aria-sort", tableSort.direction === 1 ? "ascending" : "descending");
        }
      });
    }

    function activate(header) {
      const key = header.dataset.etrocSort;
      if (!TABLE_SORT_TYPES[key]) throw new Error("invalid ETROC table sort header");
      tableSort = tableSort.key === key ? { key, direction: -tableSort.direction } : { key, direction: 1 };
      reflectSortState();
      apply();
    }

    headers.forEach((header) => {
      header.tabIndex = 0;
      header.setAttribute("aria-sort", "none");
      header.addEventListener("click", () => activate(header));
      header.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate(header);
        }
      });
    });
    reflectSortState();
  }

  function initStatistics(records, payload) {
    if (!statsRoot || !statsStatus) return;
    const waferFilter = statsRoot.querySelector("[data-etroc-original-wafer-filter]");
    const search = statsRoot.querySelector("[data-etroc-original-search]");
    const filterState = statsRoot.querySelector("[data-etroc-filter-state]");
    const provenanceNode = statsRoot.querySelector("[data-etroc-provenance]");
    if (!waferFilter || !search || !filterState || !provenanceNode) throw new Error("ETROC statistics controls or provenance region are unavailable");

    function apply() {
      const visible = selectRecords(records, waferFilter.value, search.value);
      const summary = renderStatistics(visible);
      filterState.textContent = `${visible.length} / ${records.length} ETROCs · ${summary.positionCount.toLocaleString("en-US")} positions`;

    }

    initStatisticsTableSorting(apply);
    waferFilter.addEventListener("change", apply);
    search.addEventListener("input", apply);
    apply();
    statsRoot.setAttribute("aria-busy", "false");
    const provenance = summarizeProvenance(records);
    const config = payload.analysis_config_sha256.slice(0, 12);
    const runLabels = provenance.runs.map(({ analysisRunId, recordCount }) => `${analysisRunId.split(":").at(-1)} ${recordCount}`);
    statsStatus.textContent = `ETROC_OI_2608 · ${provenance.runCount} immutable analysis runs · config ${config}… · original algorithm snapshot`;
    provenanceNode.textContent = `Immutable analysis-run distribution: ${runLabels.join(" · ")}. Created ${payload.analysis_created_at_utc}; config SHA-256 ${payload.analysis_config_sha256}.`;
    statsStatus.classList.add("loaded");
  }

  function renderStatisticsFailure() {
    if (!statsRoot || !statsStatus) return;
    statsRoot.setAttribute("aria-busy", "false");
    statsStatus.textContent = "ETROC statistics unavailable";
    statsStatus.classList.add("failed");
    statsRoot.querySelectorAll("[data-etroc-category-body], [data-etroc-wafer-body], [data-etroc-workload-body]").forEach((target) => {
      const message = element("p", "optical-chart-empty", "ETROC statistics unavailable");
      message.setAttribute("role", "alert");
      target.replaceChildren(message);
    });
    const tableBody = statsRoot.querySelector("[data-etroc-stats-table] tbody");
    tableBody?.replaceChildren();
  }

  fetch(DATA_URL, { credentials: "same-origin", headers: { Accept: "application/json" } })
    .then((response) => {
      if (!response.ok) throw new Error(`dataset request failed: ${response.status}`);
      return response.arrayBuffer();
    })
    .then(async (bytes) => {
      const { payload, records, publicationSha256 } = await parseVerifiedPublication(bytes);
      initStatistics(records, payload);
      globalThis.dispatchEvent(new CustomEvent("etroc-optical-publication", { detail: { bytes, records, publicationSha256 } }));
    })
    .catch((error) => {
      root.replaceChildren();
      root.setAttribute("aria-busy", "false");
      const message = element("p", "etroc-pool-error", "ETROC optical dataset unavailable");
      message.setAttribute("role", "alert");
      root.append(message);
      status.textContent = "ETROC optical dataset unavailable";
      status.classList.add("failed");
      renderStatisticsFailure();
      globalThis.dispatchEvent(new CustomEvent("etroc-optical-unavailable"));
      console.error("ETROC optical pool load failed", error);
    });
})();
