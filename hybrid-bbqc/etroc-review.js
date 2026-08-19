(() => {
  "use strict";

  const DATASET_ID = "ETROC_OI_2608";
  const DATA_BASE = "/data/etroc-optical/ETROC_OI_2608/";
  const EVIDENCE_FIELDS = Object.freeze(["dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "montage_sha256"]);
  const STATES = Object.freeze(["reviewed_no_optical_concern", "reviewed_concern_observed", "follow_up_required"]);
  const EVIDENCE_RESPONSE_FIELDS = Object.freeze([...EVIDENCE_FIELDS, "montage_uri"]);
  const EVENT_FIELDS = Object.freeze(["event_id", ...EVIDENCE_FIELDS, "state", "note", "author", "author_display", "created_at", "mutation_id", "supersedes_event_id"]);
  const CURRENT_FIELDS = Object.freeze(["current_event_id", ...EVIDENCE_FIELDS, "state", "note", "author", "author_display", "created_at", "history_count"]);
  const HASH = /^[0-9a-f]{64}$/;
  const CANDIDATE_COUNT_FIELDS = Object.freeze(["optical_no_ball_candidate_count", "red_candidate_count", "needs_inspection_count", "review_candidate_count"]);

  function scientificCandidateCounts(record) {
    const counts = CANDIDATE_COUNT_FIELDS.map((field) => record?.[field]);
    if (counts.some((count) => !Number.isInteger(count) || count < 0)) throw new Error("invalid scientific candidate counts");
    return counts;
  }

  async function sha256(bytes) {
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
  }

  async function parsePublication(bytes) {
    const publicationSha256 = await sha256(bytes);
    const publication = JSON.parse(new TextDecoder().decode(bytes));
    if (!publication || publication.dataset_id !== DATASET_ID || publication.record_count !== 36 || !Array.isArray(publication.records) || publication.records.length !== 36) throw new Error("invalid ETROC publication");
    const records = publication.records.map((record) => ({ ...record, dataset_id: DATASET_ID }));
    return { publication, records, publicationSha256 };
  }

  function publicationFromEvent(detail) {
    if (!detail || !Array.isArray(detail.records) || detail.records.length !== 36 || !HASH.test(detail.publicationSha256)) throw new Error("invalid ETROC publication event");
    const records = detail.records.map((record) => ({ ...record, dataset_id: DATASET_ID }));
    return { records, publication: { dataset_id: DATASET_ID, records }, publicationSha256: detail.publicationSha256 };
  }

  function evidenceKey(record) { return EVIDENCE_FIELDS.map((field) => record[field]).join("\u0000"); }

  function canonicalMontageUri(record) { return `data/etroc-optical/${DATASET_ID}/montages/sha256/${record.montage_sha256}.jpg`; }

  function isEvidence(record, requireUri) {
    return record && EVIDENCE_FIELDS.every((field) => typeof record[field] === "string" && record[field]) && HASH.test(record.montage_sha256)
      && (!requireUri || record.montage_uri === canonicalMontageUri(record));
  }

  function hasExactFields(value, fields) { return Boolean(value) && typeof value === "object" && Object.keys(value).length === fields.length && fields.every((field) => Object.hasOwn(value, field)); }
  function sameEvidence(left, right) { return evidenceKey(left) === evidenceKey(right); }
  function validCurrent(current, evidence) {
    return hasExactFields(current, CURRENT_FIELDS) && sameEvidence(current, evidence) && STATES.includes(current.state)
      && typeof current.note === "string" && typeof current.author === "string" && typeof current.author_display === "string"
      && Number.isInteger(current.current_event_id) && current.current_event_id > 0 && Number.isInteger(current.created_at)
      && Number.isInteger(current.history_count) && current.history_count > 0;
  }
  function validEvent(event, evidence) {
    return hasExactFields(event, EVENT_FIELDS) && sameEvidence(event, evidence) && STATES.includes(event.state)
      && typeof event.note === "string" && typeof event.author === "string" && typeof event.author_display === "string"
      && typeof event.mutation_id === "string" && Number.isInteger(event.event_id) && event.event_id > 0
      && Number.isInteger(event.created_at) && (event.supersedes_event_id === null || (Number.isInteger(event.supersedes_event_id) && event.supersedes_event_id > 0));
  }

  function reconcileEvidence(publication, summary) {
    if (!publication || !hasExactFields(summary, ["dataset_id", "record_count", "publication_sha256", "viewer", "evidence", "reviews"]) || summary.dataset_id !== DATASET_ID || summary.record_count !== 36 || publication.publication.dataset_id !== DATASET_ID || publication.records.length !== 36 || summary.publication_sha256 !== publication.publicationSha256 || !summary.evidence || typeof summary.evidence !== "object") throw new Error("ETROC review evidence is unavailable");
    const local = new Map();
    publication.records.forEach((record) => {
      if (!isEvidence({ ...record, montage_uri: canonicalMontageUri(record) }, true) || record.montage_uri !== `montages/sha256/${record.montage_sha256}.jpg` || local.has(record.acquisition_id)) throw new Error("invalid local evidence");
      local.set(record.acquisition_id, record);
    });
    const remoteKeys = Object.keys(summary.evidence);
    if (local.size !== 36 || remoteKeys.length !== 36 || remoteKeys.some((key) => !local.has(key))) throw new Error("ETROC evidence keyset mismatch");
    remoteKeys.forEach((key) => {
      const localRecord = local.get(key);
      const remoteRecord = summary.evidence[key];
      if (!hasExactFields(remoteRecord, EVIDENCE_RESPONSE_FIELDS) || !isEvidence(remoteRecord, true) || evidenceKey(localRecord) !== evidenceKey(remoteRecord) || remoteRecord.montage_uri !== canonicalMontageUri(localRecord)) throw new Error("ETROC evidence identity mismatch");
    });
    if (!hasExactFields(summary.viewer, ["identity_display", "can_append_review"]) || typeof summary.viewer.identity_display !== "string" || typeof summary.viewer.can_append_review !== "boolean" || typeof summary.reviews !== "object" || !summary.reviews) throw new Error("ETROC review summary is malformed");
    Object.entries(summary.reviews).forEach(([acquisitionId, review]) => {
      const localRecord = local.get(acquisitionId);
      if (!localRecord || !validCurrent(review, localRecord)) throw new Error("ETROC review provenance mismatch");
    });
    return local;
  }

  function validatedSaveCurrent(summary, acquisitionId, body) {
    const refreshed = summary?.reviews?.[acquisitionId];
    const returned = body?.current;
    if (!refreshed || !returned || evidenceKey(refreshed) !== evidenceKey(returned)
      || refreshed.current_event_id !== returned.current_event_id || refreshed.state !== returned.state
      || refreshed.note !== returned.note) throw new Error("saved review readback mismatch");
    return refreshed;
  }

  function validatedSaveEnvelope(summary, acquisitionId, body, submitted) {
    const refreshed = summary?.reviews?.[acquisitionId];
    const returned = body?.current;
    if (!body || body.ok !== true || typeof body.idempotent_replay !== "boolean" || !validEvent(body.event, submitted)
      || !validCurrent(returned, submitted) || !validCurrent(refreshed, submitted)
      || body.event.state !== submitted.state || body.event.note !== submitted.note || body.event.mutation_id !== submitted.mutation_id
      || body.event.supersedes_event_id !== submitted.expected_current_event_id || returned.current_event_id < body.event.event_id
      || refreshed.current_event_id < returned.current_event_id
      || (returned.current_event_id === body.event.event_id && (returned.state !== submitted.state || returned.note !== submitted.note))) throw new Error("saved review event mismatch");
    return { current: refreshed, saved: body.event, superseded: refreshed.current_event_id !== body.event.event_id };
  }

  function validatedHistory(body, evidence) {
    if (!hasExactFields(body, ["evidence", "current", "history"]) || !hasExactFields(body.evidence, EVIDENCE_RESPONSE_FIELDS)
      || !sameEvidence(body.evidence, evidence) || body.evidence.montage_uri !== canonicalMontageUri(evidence) || !Array.isArray(body.history)) throw new Error("review history is malformed");
    if (body.current === null) {
      if (body.history.length) throw new Error("review history has no current event");
      return body.history;
    }
    if (!validEvent(body.current, evidence) || !body.history.length || !body.history.every((event) => validEvent(event, evidence))) throw new Error("review history event mismatch");
    if (body.current.event_id !== body.history[0].event_id || body.history.some((event, index) => index && event.event_id >= body.history[index - 1].event_id)
      || body.history.some((event, index) => index < body.history.length - 1 ? event.supersedes_event_id !== body.history[index + 1].event_id : event.supersedes_event_id !== null)) throw new Error("review history chain mismatch");
    return body.history;
  }

  function naturalSerial(left, right) { return String(left.etroc_serial).localeCompare(String(right.etroc_serial), undefined, { numeric: true, sensitivity: "base" }); }

  function candidateMatch(record, candidate) {
    if (candidate === "no_ball") return record.optical_no_ball_candidate_count > 0;
    if (candidate === "red") return record.red_candidate_count > 0;
    if (candidate === "needs_inspection") return record.needs_inspection_count > 0;
    if (candidate === "review_candidate" || candidate === "candidate") return record.review_candidate_count > 0;
    if (candidate === "all") return record.optical_no_ball_candidate_count > 0 || record.red_candidate_count > 0
      || record.needs_inspection_count > 0 || record.review_candidate_count > 0;
    return false;
  }

  function canonicalComparator(left, right, reviews = {}) {
    return Number(Boolean(reviews[left.acquisition_id])) - Number(Boolean(reviews[right.acquisition_id]))
      || Number(right.optical_no_ball_candidate_count > 0) - Number(left.optical_no_ball_candidate_count > 0)
      || Number(right.red_candidate_count > 0) - Number(left.red_candidate_count > 0)
      || right.needs_inspection_count - left.needs_inspection_count
      || right.review_candidate_count - left.review_candidate_count
      || naturalSerial(left, right);
  }

  function makeQueue(records, reviews, filters) {
    const matching = records.filter((record) => {
      const review = reviews[record.acquisition_id];
      const current = review?.state || "not_reviewed";
      const stateMatches = !filters.state || (filters.state === "unreviewed" ? current === "not_reviewed" : current === filters.state);
      return stateMatches && (!filters.wafer || record.wafer === filters.wafer) && (!filters.serial || record.etroc_serial.toLowerCase().includes(filters.serial.toLowerCase())) && candidateMatch(record, filters.candidate);
    });
    return matching.sort(filters.order === "wafer_serial" ? (left, right) => String(left.wafer).localeCompare(String(right.wafer)) || naturalSerial(left, right) : (left, right) => canonicalComparator(left, right, reviews));
  }

  function snapshotQueue(records, reviews, filters) { return makeQueue(records, reviews, { ...filters, state: "unreviewed" }); }

  function openQueue(records, reviews, record, filters) {
    const queueFilters = { ...filters };
    if (reviews[record.acquisition_id]) return { mode: "correction", queue: [record], queueIndex: 0, saveNext: false, filters: queueFilters };
    const queue = snapshotQueue(records, reviews, queueFilters);
    const index = queue.findIndex((item) => item.acquisition_id === record.acquisition_id);
    const anchored = index < 0 ? [record] : queue.slice(index);
    return { mode: "queue", queue: anchored, queueIndex: 0, saveNext: anchored.length > 0, filters: queueFilters };
  }
  function refreshQueueAfterSave(queue, reviews, savedAcquisitionId) {
    const savedIndex = queue.findIndex((record) => record.acquisition_id === savedAcquisitionId);
    const forward = savedIndex < 0 ? [] : queue.slice(savedIndex + 1);
    return { queue: forward.filter((record) => !reviews[record.acquisition_id]), queueIndex: 0 };
  }

  function nextQueueIndex(queue, reviews, queueIndex) {
    let index = queueIndex + 1;
    while (index < queue.length && reviews[queue[index].acquisition_id]) index += 1;
    return index;
  }

  class ReviewSessionGate {
    constructor() { this.token = 0; this.acquisitionId = ""; this.verified = ""; }
    begin(acquisitionId) { this.token += 1; this.acquisitionId = acquisitionId; this.verified = ""; return this.token; }
    accept(token, acquisitionId) { return token === this.token && acquisitionId === this.acquisitionId; }
    markVerified(token, acquisitionId, montageHash) { if (this.accept(token, acquisitionId)) this.verified = montageHash; }
    canSave(acquisitionId, montageHash) { return this.acquisitionId === acquisitionId && this.verified === montageHash; }
  }

  const mutationFingerprints = new Map();
  function draftMutation(draft, prior, createId) {
    const fingerprint = JSON.stringify(draft);
    if (prior && prior.fingerprint === fingerprint) return prior.mutationId;
    if (typeof prior === "string" && mutationFingerprints.get(prior) === fingerprint) return prior;
    const mutationId = createId();
    mutationFingerprints.set(mutationId, fingerprint);
    return mutationId;
  }
  function applySaveResult(state, response) { return response.status === 409 ? { ...state, conflict: true } : state; }

  class MontageController {
    constructor(dependencies) { Object.assign(this, dependencies); this.generation = 0; this.abortController = null; this.objectUrl = ""; }
    revoke() { if (this.objectUrl) this.revokeObjectURL(this.objectUrl); this.objectUrl = ""; }
    close() { this.generation += 1; this.abortController?.abort(); this.abortController = null; this.revoke(); }
    async load(record) {
      const generation = ++this.generation;
      this.abortController?.abort();
      this.abortController = new AbortController();
      this.revoke();
      try {
        const response = await this.fetch(`${DATA_BASE}${record.montage_uri}`, { credentials: "same-origin", signal: this.abortController.signal });
        if (!response.ok) throw new Error("montage unavailable");
        const blob = await response.blob();
        if (await this.hash(await blob.arrayBuffer()) !== record.montage_sha256) throw new Error("montage digest mismatch");
        if (generation !== this.generation) return false;
        const objectUrl = this.createObjectURL(blob);
        if (generation !== this.generation) { this.revokeObjectURL(objectUrl); return false; }
        this.objectUrl = objectUrl;
        await this.decode(objectUrl);
        if (generation !== this.generation) { if (this.objectUrl === objectUrl) this.revoke(); else this.revokeObjectURL(objectUrl); return false; }
        this.onReady(objectUrl, blob, record);
        return true;
      } catch (error) {
        if (generation === this.generation) this.revoke();
        if (generation === this.generation && error.name !== "AbortError") this.onError(error);
        return false;
      }
    }
  }

  globalThis.ETROCReviewContract = Object.freeze({ EVIDENCE_FIELDS, STATES, sha256, parsePublication, publicationFromEvent, reconcileEvidence, validatedSaveCurrent, validatedSaveEnvelope, validatedHistory, scientificCandidateCounts, canonicalComparator, makeQueue, snapshotQueue, openQueue, refreshQueueAfterSave, nextQueueIndex, ReviewSessionGate, draftMutation, applySaveResult, MontageController });

  const dialog = document.querySelector("[data-etroc-review-dialog]");
  if (!dialog) return;
  function addControl(parent, tag, attribute, text) {
    let node = parent.querySelector(`[${attribute}]`);
    if (node) return node;
    node = document.createElement(tag);
    node.setAttribute(attribute, "");
    node.textContent = text;
    parent.append(node);
    return node;
  }
  function ensureWorkspaceControls() {
    const evidence = dialog.querySelector(".etroc-review-evidence");
    const wrap = dialog.querySelector(".etroc-review-image-wrap");
    const decision = dialog.querySelector(".etroc-review-decision");
    const actions = dialog.querySelector(".etroc-review-actions");
    if (!evidence || !wrap || !decision || !actions) return;
    const reviewControls = document.querySelector(".etroc-review-controls");
    if (reviewControls && !reviewControls.querySelector("[data-etroc-candidate-filter]")) {
      const label = document.createElement("label"); label.textContent = "Candidate type";
      const select = document.createElement("select"); select.setAttribute("data-etroc-candidate-filter", ""); select.setAttribute("aria-label", "Candidate type");
      [["all", "All candidates"], ["no_ball", "Optical no-ball"], ["red", "Red"], ["needs_inspection", "Needs inspection"], ["review_candidate", "Review candidate"]].forEach(([value, text]) => { const option = document.createElement("option"); option.value = value; option.textContent = text; select.append(option); });
      label.append(select); reviewControls.insertBefore(label, reviewControls.querySelector("[data-etroc-review-filter-order]")?.closest("label") || null);
    }
    const tools = document.createElement("div");
    tools.className = "etroc-review-image-tools";
    wrap.append(tools);
    addControl(tools, "button", "data-etroc-review-zoom-out", "Zoom out");
    addControl(tools, "button", "data-etroc-review-zoom-in", "Zoom in");
    addControl(tools, "button", "data-etroc-review-fit", "Fit");
    const original = addControl(tools, "a", "data-etroc-review-original", "Open verified original");
    original.setAttribute("target", "_blank");
    original.setAttribute("rel", "noopener");
    addControl(evidence, "p", "data-etroc-review-progress", "");
    addControl(evidence, "p", "data-etroc-review-provenance", "");
    if (!evidence.querySelector("[data-etroc-review-scientific-context]")) {
      const context = document.createElement("section");
      context.className = "etroc-review-scientific-context";
      context.setAttribute("data-etroc-review-scientific-context", "");
      const heading = document.createElement("h3");
      heading.textContent = "Algorithmic screening context";
      const counts = document.createElement("dl");
      counts.className = "etroc-review-candidate-counts";
      [["Optical no-ball", "data-etroc-review-no-ball-count"], ["RED", "data-etroc-review-red-count"], ["Needs inspection", "data-etroc-review-needs-inspection-count"], ["Review candidate", "data-etroc-review-candidate-count"]].forEach(([label, attribute]) => {
        const row = document.createElement("div");
        const term = document.createElement("dt");
        const value = document.createElement("dd");
        term.textContent = label;
        value.setAttribute(attribute, "");
        value.textContent = "—";
        row.append(term, value);
        counts.append(row);
      });
      const disclaimer = document.createElement("p");
      disclaimer.className = "etroc-review-scientific-disclaimer";
      disclaimer.textContent = "Algorithmic screening candidates are exploratory and not a confirmed QC disposition.";
      context.append(heading, counts, disclaimer);
      evidence.append(context);
    }
    addControl(decision, "ol", "data-etroc-review-history", "").setAttribute("aria-label", "Review history");
    addControl(decision, "button", "data-etroc-review-reapply", "Reapply draft to intervening version");
    addControl(actions, "button", "data-etroc-review-next", "Next");
    const discard = addControl(dialog, "dialog", "data-etroc-review-discard-dialog", "");
    if (!discard.childElementCount) {
      discard.setAttribute("aria-labelledby", "etroc-review-discard-title");
      const heading = document.createElement("h3"); heading.id = "etroc-review-discard-title"; heading.textContent = "Keep this draft?";
      const message = document.createElement("p"); message.textContent = "Your selected state or note has changed.";
      const discardActions = document.createElement("div"); discardActions.className = "etroc-review-actions";
      addControl(discardActions, "button", "data-etroc-review-keep", "Keep editing");
      addControl(discardActions, "button", "data-etroc-review-discard", "Discard draft");
      discard.append(heading, message, discardActions);
    }
  }
  ensureWorkspaceControls();
  const image = dialog.querySelector("[data-etroc-review-image]");
  const title = dialog.querySelector("#etroc-review-title");
  const status = dialog.querySelector("[data-etroc-review-status]");
  const progress = dialog.querySelector("[data-etroc-review-progress]");
  const provenance = dialog.querySelector("[data-etroc-review-provenance]");
  const scientificCountNodes = ["[data-etroc-review-no-ball-count]", "[data-etroc-review-red-count]", "[data-etroc-review-needs-inspection-count]", "[data-etroc-review-candidate-count]"].map((selector) => dialog.querySelector(selector));
  const history = dialog.querySelector("[data-etroc-review-history]");
  const note = dialog.querySelector("[data-etroc-review-note]");
  const save = dialog.querySelector("[data-etroc-review-save]");
  const saveNext = dialog.querySelector("[data-etroc-review-save-next]");
  const close = dialog.querySelector("[data-etroc-review-close]");
  const previous = dialog.querySelector("[data-etroc-review-previous]");
  const next = dialog.querySelector("[data-etroc-review-next]");
  const reset = dialog.querySelector("[data-etroc-review-reset]");
  const fit = dialog.querySelector("[data-etroc-review-fit]");
  const zoomIn = dialog.querySelector("[data-etroc-review-zoom-in]");
  const zoomOut = dialog.querySelector("[data-etroc-review-zoom-out]");
  const original = dialog.querySelector("[data-etroc-review-original]");
  const confirmDiscard = dialog.querySelector("[data-etroc-review-discard-dialog]");
  const reapply = dialog.querySelector("[data-etroc-review-reapply]");
  reapply.hidden = true;
  const start = document.querySelector("[data-etroc-review-start]");
  const summaryNode = document.querySelector("[data-etroc-review-summary]");
  const stateFilter = document.querySelector("[data-etroc-review-filter-state]");
  const orderFilter = document.querySelector("[data-etroc-review-filter-order]");
  const waferFilter = document.querySelector("[data-etroc-wafer-filter]");
  const serialFilter = document.querySelector("[data-etroc-search]");
  const candidateFilter = document.querySelector("[data-etroc-candidate-filter]");
  const controls = () => [save, saveNext, previous, next, reset, fit, zoomIn, zoomOut, original, ...dialog.querySelectorAll("input[name='etroc-review-state']"), note].filter(Boolean);
  let state = { verified: false, records: [], publication: null, summary: null, evidence: new Map(), queue: [], queueIndex: 0, queueFilters: null, active: null, origin: null, mutation: null, loadedFingerprint: "", mode: "queue", zoom: 1, conflict: null, pendingDestination: null, session: new ReviewSessionGate(), activeMontageVerified: "", saveInFlight: false, verificationInFlight: false };

  function canSaveActive() { return Boolean(state.active && state.verified && state.summary?.viewer?.can_append_review && !state.conflict && !state.saveInFlight && !state.verificationInFlight && state.activeMontageVerified === evidenceKey(state.active) && state.session.canSave(state.active.acquisition_id, evidenceKey(state.active))); }
  function inspectionControlsEnabled(enabled) {
    [reset, fit, zoomIn, zoomOut].filter(Boolean).forEach((control) => { control.disabled = !enabled; });
    const originalEnabled = Boolean(enabled && state.activeMontageVerified && montage.objectUrl);
    if (originalEnabled) {
      original.href = montage.objectUrl;
      original.removeAttribute("aria-disabled");
      original.tabIndex = 0;
    } else {
      original.removeAttribute("href");
      original.setAttribute("aria-disabled", "true");
      original.tabIndex = -1;
    }
  }
  function controlsEnabled(enabled) {
    controls().forEach((control) => { control.disabled = !enabled || Boolean(state.conflict) || (control === saveNext && state.mode === "correction"); });
    inspectionControlsEnabled(Boolean(enabled && !state.conflict));
  }
  function setStatus(message, kind = "") { status.textContent = message; status.className = `etroc-review-status ${kind}`; }
  function filters() { return { wafer: waferFilter?.value || "", serial: serialFilter?.value || "", candidate: candidateFilter?.value || "all", order: orderFilter?.value || "candidate" }; }
  function currentDraft() { const selected = dialog.querySelector("input[name='etroc-review-state']:checked"); return { state: selected?.value || "", note: note.value.trim(), expected_current_event_id: state.summary?.reviews?.[state.active?.acquisition_id]?.current_event_id ?? null }; }
  function fingerprint(draft) { return JSON.stringify(draft); }
  function refreshMutation() { const draft = currentDraft(); const value = fingerprint(draft); state.mutation = { fingerprint: value, id: draftMutation(draft, state.mutation && { fingerprint: state.mutation.fingerprint, mutationId: state.mutation.id }, () => crypto.randomUUID()) }; return { ...draft, mutation_id: state.mutation.id }; }
  function dirty() { return fingerprint(currentDraft()) !== state.loadedFingerprint; }
  function zoom(value) { state.zoom = Math.max(0.5, Math.min(3, value)); image.style.transform = `scale(${state.zoom})`; }
  function reviewedCount() { return state.records.filter((record) => state.summary?.reviews?.[record.acquisition_id]).length; }
  function updateProgress() { progress.textContent = `${reviewedCount()} / 36 reviewed · ${state.queueIndex + 1} / ${state.queue.length}`; previous.disabled = Boolean(state.conflict) || state.saveInFlight || state.verificationInFlight || state.queueIndex === 0; next.disabled = Boolean(state.conflict) || state.saveInFlight || state.verificationInFlight || state.queueIndex >= state.queue.length - 1; save.disabled = !canSaveActive(); saveNext.disabled = !canSaveActive() || state.mode === "correction"; }
  function utcTimestamp(value) { const millis = typeof value === "number" ? value * 1000 : Date.parse(value || ""); return Number.isFinite(millis) ? new Date(millis).toISOString() : "Timestamp unavailable"; }
  function setHistory(items) { history.replaceChildren(); (items || []).forEach((item) => { const row = document.createElement("li"); row.textContent = `${item.state} · ${item.author_display || item.author || "Unknown reviewer"} · ${utcTimestamp(item.created_at ?? item.created_at_utc)} · ${item.note || "No note"}`; history.append(row); }); }
  function updateScientificContext(record) { scientificCandidateCounts(record).forEach((count, index) => { scientificCountNodes[index].textContent = String(count); }); }
  async function fetchSummary() { const response = await fetch(`/api/etroc-reviews?dataset_id=${encodeURIComponent(DATASET_ID)}`, { credentials: "same-origin", headers: { Accept: "application/json" } }); if (!response.ok) throw new Error("review service unavailable"); return response.json(); }
  async function fetchHistory(record) { const response = await fetch(`/api/etroc-reviews/history?acquisition_id=${encodeURIComponent(record.acquisition_id)}`, { credentials: "same-origin" }); if (!response.ok) throw new Error("review history unavailable"); return validatedHistory(await response.json(), record); }
  const montage = new MontageController({ fetch: (...args) => fetch(...args), hash: sha256, createObjectURL: (blob) => URL.createObjectURL(blob), revokeObjectURL: (url) => URL.revokeObjectURL(url), decode: async (url) => { image.src = url; await (image.decode ? image.decode() : new Promise((resolve, reject) => { image.onload = resolve; image.onerror = reject; })); }, onReady: () => {}, onError: (error) => { if (!state.verificationInFlight) return; state.verificationInFlight = false; controlsEnabled(false); setStatus(`Verification failed: ${error.message}`, "failed"); } });

  let preloadAbort = null;
  async function preloadAdjacent() {
    preloadAbort?.abort();
    preloadAbort = new AbortController();
    const adjacent = [state.queue[state.queueIndex - 1], state.queue[state.queueIndex + 1]].filter(Boolean);
    await Promise.all(adjacent.map(async (record) => {
      const response = await fetch(`${DATA_BASE}${record.montage_uri}`, { credentials: "same-origin", signal: preloadAbort.signal });
      if (!response.ok) throw new Error("adjacent montage unavailable");
      const blob = await response.blob();
      if (await sha256(await blob.arrayBuffer()) !== record.montage_sha256) throw new Error("adjacent montage digest mismatch");
    })).catch(() => {});
  }

  function syncDraft(review) { dialog.querySelectorAll("input[name='etroc-review-state']").forEach((control) => { control.checked = control.value === review?.state; }); note.value = review?.note || ""; state.loadedFingerprint = fingerprint(currentDraft()); state.mutation = null; state.conflict = null; reapply.hidden = true; }
  async function updateDialog() {
    const record = state.active;
    if (!record) return;
    const token = state.session.begin(record.acquisition_id);
    state.activeMontageVerified = "";
    state.verificationInFlight = true;
    controlsEnabled(false);
    title.textContent = `Review ${record.etroc_serial}`;
    updateScientificContext(record);
    provenance.textContent = `${record.acquisition_id} · ${record.analysis_run_id} · montage SHA-256 ${record.montage_sha256} · ${record.montage_uri}`;
    setHistory([]);
    syncDraft(state.summary.reviews[record.acquisition_id]);
    zoom(1);
    updateProgress();
    setStatus("Verifying exact montage bytes", "");
    const [historyResult, montageResult] = await Promise.allSettled([fetchHistory(record), montage.load(record)]);
    if (!state.session.accept(token, record.acquisition_id)) return;
    state.verificationInFlight = false;
    if (montageResult.status !== "fulfilled" || !montageResult.value) {
      controlsEnabled(false);
      updateProgress();
      return;
    }
    state.session.markVerified(token, record.acquisition_id, evidenceKey(record));
    state.activeMontageVerified = evidenceKey(record);
    if (historyResult.status !== "fulfilled") {
      const item = document.createElement("li");
      item.textContent = "Review history unavailable.";
      history.replaceChildren(item);
      controlsEnabled(false);
      inspectionControlsEnabled(true);
      updateProgress();
      setStatus("Verified evidence. Review history unavailable; read-only inspection.", "readonly");
      return;
    }
    setHistory(historyResult.value);
    controlsEnabled(Boolean(state.summary?.viewer?.can_append_review));
    updateProgress();
    setStatus(state.summary.viewer.can_append_review ? "Verified evidence and decoded exact montage bytes." : "Verified evidence. Read-only access.", state.summary.viewer.can_append_review ? "verified" : "readonly");
    void preloadAdjacent();
  }
  function applyQueue(record, origin) { const opened = openQueue(state.records, state.summary.reviews, record, filters()); state.mode = opened.mode; state.queue = opened.queue; state.queueIndex = opened.queueIndex; state.queueFilters = opened.filters; state.active = state.queue[0]; state.origin = origin; dialog.hidden = false; updateDialog(); close.focus(); }
  function interactionBusy() { return state.saveInFlight || state.verificationInFlight; }
  function requestDestination(destination) { if (!dirty()) return destination(); state.pendingDestination = destination; confirmDiscard.showModal(); confirmDiscard.querySelector("[data-etroc-review-keep]")?.focus(); }
  function requestClose() { if (interactionBusy()) { setStatus("Wait for the active save or verification before closing.", "failed"); return; } requestDestination(closeDialog); }
  function closeDialog() { if (interactionBusy()) return; state.pendingDestination = null; state.session.begin(""); preloadAbort?.abort(); state.activeMontageVerified = ""; controlsEnabled(false); montage.close(); image.removeAttribute("src"); dialog.hidden = true; state.origin?.focus(); }
  async function navigateForward() {
    state.verificationInFlight = true;
    controlsEnabled(false);
    updateProgress();
    try {
      const summary = await fetchSummary();
      state.evidence = reconcileEvidence(state.publication, summary);
      state.summary = summary;
      updateReviewSurface();
    } catch (error) {
      state.verificationInFlight = false;
      controlsEnabled(canSaveActive());
      updateProgress();
      setStatus(`Review state refresh unavailable: ${error.message}`, "failed");
      return;
    }
    state.verificationInFlight = false;
    const index = nextQueueIndex(state.queue, state.summary.reviews, state.queueIndex);
    if (index >= state.queue.length) {
      controlsEnabled(canSaveActive());
      updateProgress();
      setStatus("Queue complete. No later unreviewed item remains in this snapshot.", "verified");
      return;
    }
    state.queueIndex = index;
    state.active = state.queue[index];
    void updateDialog();
  }
  function navigate(offset) {
    if (interactionBusy()) { setStatus("Wait for the active save or verification before changing items.", "failed"); return; }
    if (offset > 0) { requestDestination(() => { void navigateForward(); }); return; }
    const index = state.queueIndex + offset;
    if (index < 0 || index >= state.queue.length) return;
    requestDestination(() => { state.queueIndex = index; state.active = state.queue[index]; void updateDialog(); });
  }
  async function saveReview(andNext) {
    if (!state.active || !canSaveActive()) return;
    const token = state.session.token; const activeId = state.active.acquisition_id;
    const draft = refreshMutation();
    if (!STATES.includes(draft.state) || (draft.state !== "reviewed_no_optical_concern" && !draft.note)) { setStatus("Choose a review state and provide notes for concern or follow-up.", "failed"); return; }
    const payload = Object.fromEntries(EVIDENCE_FIELDS.map((field) => [field, state.active[field]])); Object.assign(payload, draft); state.saveInFlight = true; controlsEnabled(false);
    try {
      const response = await fetch("/api/etroc-reviews", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const body = await response.json(); if (!state.session.accept(token, activeId)) return;
      if (response.status === 409) {
        const conflict = body.error;
        if (!conflict || typeof conflict.code !== "string") throw new Error("conflict response is malformed");
        if (conflict.code === "evidence_changed") {
          state.conflict = conflict;
          state.verified = false;
          state.activeMontageVerified = "";
          state.saveInFlight = false;
          state.verificationInFlight = false;
          state.session.begin(activeId);
          reapply.hidden = true;
          controlsEnabled(false);
          setStatus("Published evidence changed. Reload and verify the new bytes before reviewing.", "failed");
          return;
        }
        if (conflict.code === "mutation_id_conflict") {
          state.conflict = conflict;
          reapply.hidden = false;
          setStatus("The mutation ID was already used for different content. Draft retained; explicitly reapply with a fresh mutation ID.", "failed");
          return;
        }
        if (conflict.code !== "stale_current" || !validCurrent(conflict.current, state.active)) throw new Error("conflict current review is malformed");
        state.conflict = conflict;
        reapply.hidden = true;
        const summary = await fetchSummary();
        if (!state.session.accept(token, activeId)) return;
        const reconciled = reconcileEvidence(state.publication, summary);
        state.summary = summary;
        state.evidence = reconciled;
        if (!validCurrent(state.summary.reviews[activeId], state.active) || state.summary.reviews[activeId].current_event_id !== conflict.current.current_event_id) throw new Error("conflict current review readback mismatch");
        const items = await fetchHistory(state.active);
        if (!state.session.accept(token, activeId)) return;
        if (items[0]?.event_id !== conflict.current.current_event_id) throw new Error("conflict history readback mismatch");
        setHistory(items);
        state.conflict = conflict;
        reapply.hidden = false;
        setStatus(`${conflict.message || "Conflict"} Intervening current state loaded; draft retained. Reapply uses a fresh mutation ID.`, "failed");
        return;
      }
      if (!response.ok) throw new Error(body.error?.message || "save failed");
      const summary = await fetchSummary();
      if (!state.session.accept(token, activeId)) return;
      const reconciled = reconcileEvidence(state.publication, summary);
      state.summary = summary;
      state.evidence = reconciled;
      const outcome = validatedSaveEnvelope(state.summary, activeId, body, payload);
      const items = await fetchHistory(state.active);
      if (!state.session.accept(token, activeId)) return;
      if (items[0]?.event_id !== outcome.current.current_event_id || !items.some((item) => item.event_id === body.event.event_id)) throw new Error("saved review history readback mismatch");
      setHistory(items);
      updateReviewSurface();
      if (outcome.superseded) {
        state.conflict = { code: "post_save_successor", current: outcome.current };
        reapply.hidden = false;
        setStatus("Review saved, then changed by another reviewer. New current loaded; explicitly reapply the retained draft if needed.", "failed");
        return;
      }
      syncDraft(outcome.current);
      state.loadedFingerprint = fingerprint(currentDraft());
      setStatus("Review saved. Current summary and history validated.", "verified");
      if (andNext && state.mode === "queue") { const refreshed = refreshQueueAfterSave(state.queue, state.summary.reviews, activeId); state.queue = refreshed.queue; state.queueIndex = refreshed.queueIndex; if (state.queue.length) { state.active = state.queue[0]; state.saveInFlight = false; void updateDialog(); return; } setStatus("Queue complete. Review saved; choose Close to return to the pool.", "verified"); }
    } catch (error) { if (state.session.accept(token, activeId)) setStatus(`Save unavailable: ${error.message}. Retry retains this mutation ID.`, "failed"); } finally { if (state.session.accept(token, activeId)) { state.saveInFlight = false; controlsEnabled(canSaveActive()); updateProgress(); } }
  }
  function reapplyConflict() {
    if (!state.conflict) return;
    if (state.conflict.code === "mutation_id_conflict") {
      state.mutation = null;
      state.conflict = null;
      reapply.hidden = true;
      setStatus("Draft is ready to retry with a fresh mutation ID.", "verified");
      controlsEnabled(true);
      updateProgress();
      return;
    }
    const review = state.summary.reviews[state.active.acquisition_id];
    if (!["stale_current", "post_save_successor"].includes(state.conflict.code) || !validCurrent(review, state.active)) { setStatus("Intervening current review is unavailable.", "failed"); return; }
    state.mutation = null;
    state.conflict = null;
    reapply.hidden = true;
    setStatus("Intervening version adopted. Your draft is ready to reapply with a fresh mutation ID.", "verified");
    controlsEnabled(true);
    updateProgress();
  }
  function trapFocus(event) { if (event.key !== "Tab") return; const scope = confirmDiscard.open ? confirmDiscard : dialog; const focusable = [...scope.querySelectorAll("button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled])")].filter((control) => !control.closest("dialog:not([open])")); if (!focusable.length) return; const first = focusable[0]; const last = focusable.at(-1); if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); } }
  function bindRecords(records) { records.forEach((record) => { const card = document.querySelector(`[data-etroc-serial="${record.etroc_serial}"]`); if (!card) return; card.target = ""; card.rel = ""; card.href = "#etroc-review-workspace"; card.dataset.etrocAcquisition = record.acquisition_id; card.addEventListener("click", (event) => { event.preventDefault(); applyQueue(record, card); }); }); }
  function updateCardReview(card, review) { if (!card) return; let detail = card.querySelector("[data-etroc-review-card-state]"); if (!detail) { detail = document.createElement("small"); detail.setAttribute("data-etroc-review-card-state", ""); card.querySelector(".etroc-pool-card-body")?.append(detail); } if (!review) { detail.textContent = "Live review: unreviewed"; return; } const count = Number.isInteger(review.history_count) ? review.history_count : 1; detail.textContent = `Live review: ${review.state} · ${review.author_display || review.author || "Unknown reviewer"} · ${utcTimestamp(review.created_at ?? review.created_at_utc)} · ${count} event${count === 1 ? "" : "s"}`; }
  function updateReviewSurface() { if (!state.summary) return; const totals = { unreviewed: 0, reviewed_no_optical_concern: 0, reviewed_concern_observed: 0, follow_up_required: 0 }; state.records.forEach((record) => { const review = state.summary.reviews[record.acquisition_id]; const stateMatches = !stateFilter?.value || (stateFilter.value === "unreviewed" ? !review : review?.state === stateFilter.value); totals[review?.state || "unreviewed"] += 1; const card = document.querySelector(`[data-etroc-acquisition="${record.acquisition_id}"]`); card?.classList.toggle("review-filter-hidden", !stateMatches || !candidateMatch(record, candidateFilter?.value || "all")); updateCardReview(card, review); }); summaryNode.textContent = `${totals.unreviewed} unreviewed · ${totals.reviewed_no_optical_concern} no concern · ${totals.reviewed_concern_observed} concern · ${totals.follow_up_required} follow-up`; const queue = snapshotQueue(state.records, state.summary.reviews, filters()); start.disabled = !state.verified || !queue.length; }

  globalThis.addEventListener("etroc-optical-publication", async (event) => { try { const detail = event.detail || {}; const parsed = detail.records && detail.publicationSha256 ? publicationFromEvent(detail) : await parsePublication(detail.bytes); const summary = await fetchSummary(); state.evidence = reconcileEvidence(parsed, summary); state.records = parsed.records; state.publication = parsed; state.summary = summary; state.verified = true; bindRecords(state.records); updateReviewSurface(); setStatus("Verified review workspace available.", "verified"); } catch (error) { state.verified = false; controlsEnabled(false); setStatus(`Review unavailable: ${error.message}`, "failed"); } });
  dialog.addEventListener("keydown", (event) => { trapFocus(event); if (confirmDiscard.open) return; if (event.key === "Escape") { event.preventDefault(); requestClose(); return; } if (["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) return; if (event.key === "ArrowRight") navigate(1); if (event.key === "ArrowLeft") navigate(-1); if (event.key === "+") zoom(state.zoom + .25); if (event.key === "-") zoom(state.zoom - .25); });
  dialog.addEventListener("click", (event) => { if (event.target === dialog) requestClose(); });
  dialog.querySelectorAll("input[name='etroc-review-state']").forEach((control) => control.addEventListener("change", refreshMutation)); note.addEventListener("input", refreshMutation); close.addEventListener("click", requestClose); save.addEventListener("click", () => saveReview(false)); saveNext.addEventListener("click", () => saveReview(true)); previous.addEventListener("click", () => navigate(-1)); next.addEventListener("click", () => navigate(1)); reset.addEventListener("click", () => zoom(1)); fit.addEventListener("click", () => zoom(1)); zoomIn.addEventListener("click", () => zoom(state.zoom + .25)); zoomOut.addEventListener("click", () => zoom(state.zoom - .25)); reapply.addEventListener("click", reapplyConflict); confirmDiscard.addEventListener("cancel", () => { state.pendingDestination = null; }); confirmDiscard.querySelector("[data-etroc-review-keep]")?.addEventListener("click", () => { state.pendingDestination = null; confirmDiscard.close(); }); confirmDiscard.querySelector("[data-etroc-review-discard]")?.addEventListener("click", () => { const destination = state.pendingDestination; state.pendingDestination = null; confirmDiscard.close(); destination?.(); }); start.addEventListener("click", async () => { try { const summary = await fetchSummary(); const reconciled = reconcileEvidence(state.publication, summary); state.summary = summary; state.evidence = reconciled; updateReviewSurface(); const queue = snapshotQueue(state.records, state.summary.reviews, filters()); if (queue.length) applyQueue(queue[0], start); } catch (error) { setStatus(`Review unavailable: ${error.message}`, "failed"); } }); [stateFilter, orderFilter, waferFilter, serialFilter, candidateFilter].forEach((control) => control?.addEventListener("change", updateReviewSurface)); globalThis.addEventListener("beforeunload", (event) => { if (dirty()) { event.preventDefault(); event.returnValue = ""; } });
})();
