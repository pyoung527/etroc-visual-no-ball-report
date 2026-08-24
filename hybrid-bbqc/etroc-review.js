(() => {
  "use strict";

  const DATASET_ID = "ETROC_OI_2608";
  const DATA_BASE = "/data/etroc-optical/ETROC_OI_2608/";
  const EVIDENCE_DATA_BASE = "data/etroc-optical/ETROC_OI_2608/";
  const EVIDENCE_FIELDS = Object.freeze(["dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "montage_sha256"]);
  const STATES = Object.freeze(["reviewed_no_optical_concern", "reviewed_concern_observed", "follow_up_required"]);
  const EVIDENCE_RESPONSE_FIELDS = Object.freeze([...EVIDENCE_FIELDS, "montage_uri"]);
  const POSITION_KEY_FIELDS = Object.freeze(["dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "labelled_montage_sha256", "clean_montage_sha256", "position_publication_sha256", "position", "source_image_sha256", "geometry_version"]);
  const POSITION_EVIDENCE_FIELDS = Object.freeze([...POSITION_KEY_FIELDS, "row", "column", "algorithm_category", "algorithm_reason", "review_target", "cell"]);
  const POSITION_CATEGORIES = Object.freeze(["GREEN", "BLUE", "YELLOW", "RED", "NEED_INSPECT"]);
  const HUMAN_LABELS = Object.freeze(["GREEN", "BLUE", "YELLOW", "RED"]);
  const POSITION_GEOMETRY_VERSION = "etroc-grid-16x16-v1";
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

  async function parsePositionPublication(bytes, record) {
    const positionPublicationSha256 = await sha256(bytes);
    if (!record || positionPublicationSha256 !== record.position_publication_sha256 || record.position_geometry_version !== POSITION_GEOMETRY_VERSION
      || !HASH.test(record.montage_sha256) || !HASH.test(record.clean_montage_sha256)) throw new Error("invalid ETROC position publication identity");
    const document = JSON.parse(new TextDecoder().decode(bytes));
    const expectedDocumentFields = ["schema_version", "geometry_version", "dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "labelled_montage_sha256", "clean_montage_sha256", "review_target_count", "positions"];
    if (!hasExactFields(document, expectedDocumentFields) || document.schema_version !== "1.0" || document.geometry_version !== POSITION_GEOMETRY_VERSION
      || document.dataset_id !== DATASET_ID || document.etroc_serial !== record.etroc_serial || document.acquisition_id !== record.acquisition_id
      || document.analysis_run_id !== record.analysis_run_id || document.labelled_montage_sha256 !== record.montage_sha256
      || document.clean_montage_sha256 !== record.clean_montage_sha256 || !Array.isArray(document.positions) || document.positions.length !== 256) throw new Error("invalid ETROC position publication");
    let targetCount = 0;
    const positions = document.positions.map((raw, expectedPosition) => {
      const row = Math.floor(expectedPosition / 16); const column = expectedPosition % 16;
      const expectedCell = { x: column * 150, y: row * 136, width: 150, height: 136, image_y: 16, image_height: 120 };
      if (!hasExactFields(raw, ["position", "row", "column", "algorithm_category", "algorithm_reason", "source_image_sha256", "review_target", "cell"])
        || raw.position !== expectedPosition || raw.row !== row || raw.column !== column || !POSITION_CATEGORIES.includes(raw.algorithm_category)
        || typeof raw.algorithm_reason !== "string" || !raw.algorithm_reason || !HASH.test(raw.source_image_sha256)
        || typeof raw.review_target !== "boolean" || raw.review_target !== (raw.algorithm_category === "NEED_INSPECT")
        || !hasExactFields(raw.cell, Object.keys(expectedCell)) || Object.keys(expectedCell).some((field) => raw.cell[field] !== expectedCell[field])) throw new Error("invalid ETROC position record");
      targetCount += Number(raw.review_target);
      return { dataset_id: DATASET_ID, etroc_serial: record.etroc_serial, acquisition_id: record.acquisition_id, analysis_run_id: record.analysis_run_id,
        labelled_montage_sha256: record.montage_sha256, clean_montage_sha256: record.clean_montage_sha256, position_publication_sha256: positionPublicationSha256,
        position: expectedPosition, source_image_sha256: raw.source_image_sha256, geometry_version: POSITION_GEOMETRY_VERSION,
        row, column, algorithm_category: raw.algorithm_category, algorithm_reason: raw.algorithm_reason, review_target: raw.review_target, cell: { ...raw.cell } };
    });
    if (targetCount !== document.review_target_count || targetCount !== record.position_review_target_count) throw new Error("ETROC position target count mismatch");
    return { positions, targetCount, positionPublicationSha256 };
  }

  async function parseHeightPublication(bytes, record) {
    const heightPublicationSha256 = await sha256(bytes);
    if (!record || heightPublicationSha256 !== record.height_publication_sha256 || record.height_publication_uri !== `heights/sha256/${heightPublicationSha256}.json`) throw new Error("invalid ETROC height publication identity");
    const document = JSON.parse(new TextDecoder().decode(bytes));
    if (!hasExactFields(document, ["schema_version", "dataset_id", "etroc_serial", "acquisition_id", "analysis_run_id", "height_contract", "measurements"])
      || document.schema_version !== "1.0" || document.dataset_id !== DATASET_ID || document.etroc_serial !== record.etroc_serial
      || document.acquisition_id !== record.acquisition_id || document.analysis_run_id !== record.analysis_run_id
      || !hasExactFields(document.height_contract, ["unit", "no_ball_lte", "in_spec_min", "in_spec_max_exclusive", "algorithm_config_sha256"])
      || document.height_contract.unit !== "mm" || !HASH.test(document.height_contract.algorithm_config_sha256)
      || ![document.height_contract.no_ball_lte, document.height_contract.in_spec_min, document.height_contract.in_spec_max_exclusive].every(Number.isFinite)
      || !(0 <= document.height_contract.no_ball_lte && document.height_contract.no_ball_lte < document.height_contract.in_spec_min && document.height_contract.in_spec_min < document.height_contract.in_spec_max_exclusive)
      || !Array.isArray(document.measurements) || document.measurements.length !== 256) throw new Error("invalid ETROC height publication");
    const measurements = document.measurements.map((measurement, position) => {
      if (!hasExactFields(measurement, ["position", "status", "value"]) || measurement.position !== position || !Number.isFinite(measurement.value)
        || !["HEIGHT_NO_BALL", "IN_SPEC", "OUT_OF_SPEC"].includes(measurement.status)) throw new Error("invalid ETROC height measurement");
      const expectedStatus = measurement.value <= document.height_contract.no_ball_lte ? "HEIGHT_NO_BALL" : measurement.value >= document.height_contract.in_spec_min && measurement.value < document.height_contract.in_spec_max_exclusive ? "IN_SPEC" : "OUT_OF_SPEC";
      if (measurement.status !== expectedStatus) throw new Error("ETROC height classification mismatch");
      return { ...measurement };
    });
    return { contract: { ...document.height_contract }, measurements, heightPublicationSha256 };
  }

  function reconcileHeightEvidence(record, parsed, summary) {
    if (summary.height_publication_sha256 !== parsed.heightPublicationSha256 || summary.height_publication_sha256 !== record.height_publication_sha256
      || summary.height_publication_uri !== `${EVIDENCE_DATA_BASE}${record.height_publication_uri}` || !hasExactFields(summary.height_contract, Object.keys(parsed.contract))
      || Object.keys(parsed.contract).some((field) => summary.height_contract[field] !== parsed.contract[field]) || !summary.height_evidence || typeof summary.height_evidence !== "object"
      || Object.keys(summary.height_evidence).length !== 256) throw new Error("ETROC height evidence is unavailable");
    parsed.measurements.forEach((measurement, position) => {
      const remote = summary.height_evidence[String(position)];
      if (!hasExactFields(remote, ["position", "status", "value"]) || remote.position !== position || remote.status !== measurement.status || remote.value !== measurement.value) throw new Error("ETROC height evidence mismatch");
    });
    return parsed;
  }

  function samePositionEvidence(left, right) {
    return POSITION_KEY_FIELDS.every((field) => left?.[field] === right?.[field])
      && left?.row === right?.row && left?.column === right?.column && left?.algorithm_category === right?.algorithm_category
      && left?.algorithm_reason === right?.algorithm_reason && left?.review_target === right?.review_target
      && ["x", "y", "width", "height", "image_y", "image_height"].every((field) => left?.cell?.[field] === right?.cell?.[field]);
  }

  function reconcilePositionEvidence(record, parsed, summary, expectedPublicationSha256) {
    const expectedSummaryFields = ["dataset_id", "publication_sha256", "acquisition_id", "etroc_serial", "analysis_run_id", "labelled_montage_sha256", "clean_montage_sha256", "clean_montage_uri", "position_publication_sha256", "position_publication_uri", "height_publication_sha256", "height_publication_uri", "height_contract", "height_evidence", "geometry_version", "position_count", "target_count", "reviewed_target_count", "completion_status", "viewer", "evidence", "reviews"];
    if (!hasExactFields(summary, expectedSummaryFields) || summary.dataset_id !== DATASET_ID || !HASH.test(expectedPublicationSha256) || summary.publication_sha256 !== expectedPublicationSha256 || summary.acquisition_id !== record.acquisition_id
      || summary.etroc_serial !== record.etroc_serial || summary.analysis_run_id !== record.analysis_run_id
      || summary.labelled_montage_sha256 !== record.montage_sha256 || summary.clean_montage_sha256 !== record.clean_montage_sha256
      || summary.clean_montage_uri !== `${EVIDENCE_DATA_BASE}${record.clean_montage_uri}` || summary.position_publication_sha256 !== parsed.positionPublicationSha256
      || summary.position_publication_uri !== `${EVIDENCE_DATA_BASE}${record.position_publication_uri}` || summary.geometry_version !== POSITION_GEOMETRY_VERSION
      || summary.position_count !== 256 || summary.target_count !== parsed.targetCount || !hasExactFields(summary.viewer, ["identity_display", "can_append_review"])
      || typeof summary.viewer.identity_display !== "string" || typeof summary.viewer.can_append_review !== "boolean"
      || !summary.evidence || typeof summary.evidence !== "object" || !summary.reviews || typeof summary.reviews !== "object") throw new Error("ETROC position evidence is unavailable");
    const keys = Object.keys(summary.evidence);
    if (keys.length !== 256 || keys.some((key, index) => key !== String(index))) throw new Error("ETROC position evidence keyset mismatch");
    const result = new Map();
    parsed.positions.forEach((position) => {
      const remote = summary.evidence[String(position.position)];
      if (!hasExactFields(remote, POSITION_EVIDENCE_FIELDS) || !samePositionEvidence(position, remote)) throw new Error("ETROC position evidence identity mismatch");
      result.set(position.position, position);
    });
    let reviewedTargetCount = 0;
    Object.entries(summary.reviews).forEach(([key, review]) => {
      const position = Number(key); const evidence = result.get(position);
      if (!evidence || !evidence.review_target || !review || POSITION_KEY_FIELDS.some((field) => review[field] !== evidence[field]) || !HUMAN_LABELS.includes(review.label)
        || !Number.isInteger(review.current_event_id) || review.current_event_id <= 0) throw new Error("ETROC position review provenance mismatch");
      reviewedTargetCount += 1;
    });
    const expectedCompletion = parsed.targetCount === 0 ? "not_applicable" : reviewedTargetCount === parsed.targetCount ? "review_complete" : "review_pending";
    if (summary.reviewed_target_count !== reviewedTargetCount || summary.completion_status !== expectedCompletion) throw new Error("ETROC position completion mismatch");
    return result;
  }

  function reconcileCompletion(records, payload, expectedPublicationSha256) {
    const expectedFields = ["dataset_id", "publication_sha256", "record_count", "target_count", "reviewed_target_count", "completion"];
    if (!hasExactFields(payload, expectedFields) || payload.dataset_id !== DATASET_ID || payload.publication_sha256 !== expectedPublicationSha256
      || !HASH.test(expectedPublicationSha256) || payload.record_count !== records.length || payload.record_count !== 36
      || !Number.isInteger(payload.target_count) || payload.target_count < 0 || !Number.isInteger(payload.reviewed_target_count)
      || payload.reviewed_target_count < 0 || payload.reviewed_target_count > payload.target_count || !payload.completion || typeof payload.completion !== "object") throw new Error("ETROC completion summary is unavailable");
    const result = new Map(); let targetTotal = 0; let reviewedTotal = 0;
    records.forEach((record) => {
      const item = payload.completion[record.acquisition_id];
      const targetCount = record.position_review_target_count;
      if (!Number.isInteger(targetCount) || targetCount < 0 || !hasExactFields(item, ["acquisition_id", "etroc_serial", "target_count", "reviewed_target_count", "status"])
        || item.acquisition_id !== record.acquisition_id || item.etroc_serial !== record.etroc_serial || item.target_count !== targetCount
        || !Number.isInteger(item.reviewed_target_count) || item.reviewed_target_count < 0 || item.reviewed_target_count > targetCount) throw new Error("ETROC completion identity mismatch");
      const expectedStatus = targetCount === 0 ? "not_applicable" : item.reviewed_target_count === targetCount ? "review_complete" : "review_pending";
      if (item.status !== expectedStatus) throw new Error("ETROC completion state mismatch");
      targetTotal += targetCount; reviewedTotal += item.reviewed_target_count; result.set(record.acquisition_id, item);
    });
    if (Object.keys(payload.completion).length !== records.length || targetTotal !== payload.target_count || reviewedTotal !== payload.reviewed_target_count) throw new Error("ETROC completion aggregate mismatch");
    return result;
  }

  function completionMatch(filter, item) {
    if (filter === "all") return true;
    if (filter === "complete") return item?.status === "review_complete";
    if (filter === "pending") return item?.status === "review_pending";
    return false;
  }

  function makeCompletionQueue(records, completion, filters) {
    return makeQueue(records.filter((record) => completion?.get(record.acquisition_id)?.status === "review_pending"), {}, { ...filters, state: "" });
  }

  function makePositionQueue(positions, reviews, targetsOnly = true) {
    return positions.filter((position) => (!targetsOnly || position.review_target) && !reviews?.[String(position.position)])
      .slice().sort((left, right) => left.position - right.position);
  }

  function validatePositionDraft(draft) {
    if (!draft || !HUMAN_LABELS.includes(draft.label) || typeof draft.note !== "string" || draft.note.length > 2000
      || (draft.expected_current_event_id !== null && (!Number.isInteger(draft.expected_current_event_id) || draft.expected_current_event_id <= 0))) throw new Error("invalid human position label draft");
    return { label: draft.label, note: draft.note, expected_current_event_id: draft.expected_current_event_id };
  }

  function positionOpenMode(position, review) {
    if (!position?.review_target) return "inspection";
    return review ? "correction" : "queue";
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
    if (candidate === "all") return true;
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

  globalThis.ETROCReviewContract = Object.freeze({ EVIDENCE_FIELDS, POSITION_KEY_FIELDS, POSITION_EVIDENCE_FIELDS, STATES, HUMAN_LABELS, sha256, parsePublication, publicationFromEvent, parsePositionPublication, parseHeightPublication, reconcilePositionEvidence, reconcileHeightEvidence, reconcileCompletion, completionMatch, makeCompletionQueue, makePositionQueue, validatePositionDraft, positionOpenMode, reconcileEvidence, validatedSaveCurrent, validatedSaveEnvelope, validatedHistory, scientificCandidateCounts, canonicalComparator, makeQueue, snapshotQueue, openQueue, refreshQueueAfterSave, nextQueueIndex, ReviewSessionGate, draftMutation, applySaveResult, MontageController });

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
    if (!evidence || !wrap) return;
    const reviewControls = document.querySelector(".etroc-review-controls");
    if (reviewControls && !reviewControls.querySelector("[data-etroc-candidate-filter]")) {
      const label = document.createElement("label"); label.textContent = "Candidate type";
      const select = document.createElement("select"); select.setAttribute("data-etroc-candidate-filter", ""); select.setAttribute("aria-label", "Candidate type");
      [["needs_inspection", "Has NEED_INSPECT targets"], ["all", "All ETROCs"], ["no_ball", "Optical no-ball"], ["red", "Red"], ["review_candidate", "Review candidate"]].forEach(([value, text]) => { const option = document.createElement("option"); option.value = value; option.textContent = text; select.append(option); });
      label.append(select); reviewControls.insertBefore(label, reviewControls.querySelector("[data-etroc-review-filter-order]")?.closest("label") || null);
    }
    if (reviewControls && !reviewControls.querySelector("[data-etroc-review-completion-filter]")) {
      const label = document.createElement("label"); label.textContent = "Review status";
      const select = document.createElement("select"); select.setAttribute("data-etroc-review-completion-filter", ""); select.setAttribute("aria-label", "Review completion status");
      [["pending", "Review pending"], ["complete", "Review complete"], ["all", "All review states"]].forEach(([value, text]) => { const option = document.createElement("option"); option.value = value; option.textContent = text; select.append(option); });
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
    const discard = addControl(dialog, "dialog", "data-etroc-review-discard-dialog", "");
    if (!discard.childElementCount) {
      discard.setAttribute("aria-labelledby", "etroc-review-discard-title");
      const heading = document.createElement("h3"); heading.id = "etroc-review-discard-title"; heading.textContent = "Keep this draft?";
      const message = document.createElement("p"); message.textContent = "Your selected position label or note has changed.";
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
  const positionGrid = dialog.querySelector("[data-etroc-position-grid]");
  const positionCanvas = dialog.querySelector(".etroc-position-canvas");
  const positionStart = dialog.querySelector("[data-etroc-position-start]");
  const positionProgress = dialog.querySelector("[data-etroc-position-progress]");
  const positionContext = dialog.querySelector("[data-etroc-position-context]");
  const positionNote = dialog.querySelector("[data-etroc-position-note]");
  const positionHistory = dialog.querySelector("[data-etroc-position-history]");
  const positionSave = dialog.querySelector("[data-etroc-position-save]");
  const positionSaveNext = dialog.querySelector("[data-etroc-position-save-next]");
  const positionPrevious = dialog.querySelector("[data-etroc-position-previous]");
  const positionReapply = dialog.querySelector("[data-etroc-position-reapply]");
  const positionAlgorithmOverlay = dialog.querySelector("[data-etroc-position-algorithm-overlay]");
  const positionHumanOverlay = dialog.querySelector("[data-etroc-position-human-overlay]");
  const positionModeControls = [...dialog.querySelectorAll("[data-etroc-position-mode]")];
  if (reapply) reapply.hidden = true;
  const start = document.querySelector("[data-etroc-review-start]");
  const summaryNode = document.querySelector("[data-etroc-review-summary]");
  const stateFilter = document.querySelector("[data-etroc-review-filter-state]");
  const orderFilter = document.querySelector("[data-etroc-review-filter-order]");
  const waferFilter = document.querySelector("[data-etroc-wafer-filter]");
  const serialFilter = document.querySelector("[data-etroc-search]");
  const candidateFilter = document.querySelector("[data-etroc-candidate-filter]");
  const completionFilter = document.querySelector("[data-etroc-review-completion-filter]");
  const controls = () => [save, saveNext, previous, next, reset, fit, zoomIn, zoomOut, original, ...dialog.querySelectorAll("input[name='etroc-review-state']"), note].filter(Boolean);
  let state = { verified: false, records: [], publication: null, summary: null, completion: new Map(), evidence: new Map(), queue: [], queueIndex: 0, queueFilters: null, active: null, origin: null, mutation: null, loadedFingerprint: "", mode: "queue", zoom: 1, conflict: null, pendingDestination: null, session: new ReviewSessionGate(), activeMontageVerified: "", saveInFlight: false, verificationInFlight: false, position: { parsed: null, summary: null, evidence: new Map(), queue: [], queueIndex: 0, denominator: 0, active: null, mode: "queue", mutation: null, loadedFingerprint: "", cleanVerified: "", montageMode: "clean", saveInFlight: false, conflict: null } };

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
  function filters() { return { wafer: waferFilter?.value || "", serial: serialFilter?.value || "", candidate: candidateFilter?.value || "all", completion: completionFilter?.value || "pending", order: orderFilter?.value || "candidate" }; }
  function currentDraft() { const selected = dialog.querySelector("input[name='etroc-review-state']:checked"); return { state: selected?.value || "", note: note.value.trim(), expected_current_event_id: state.summary?.reviews?.[state.active?.acquisition_id]?.current_event_id ?? null }; }
  function fingerprint(draft) { return JSON.stringify(draft); }
  function refreshMutation() { const draft = currentDraft(); const value = fingerprint(draft); state.mutation = { fingerprint: value, id: draftMutation(draft, state.mutation && { fingerprint: state.mutation.fingerprint, mutationId: state.mutation.id }, () => crypto.randomUUID()) }; return { ...draft, mutation_id: state.mutation.id }; }
  function dirty() { return positionDirty(); }
  function zoom(value) { state.zoom = Math.max(0.5, Math.min(3, value)); positionCanvas.style.transform = `scale(${state.zoom})`; }
  function reviewedCount() { return state.records.filter((record) => state.summary?.reviews?.[record.acquisition_id]).length; }
  function updateProgress() { progress.textContent = state.active ? `ETROC ${state.active.etroc_serial} · classify NEED_INSPECT positions below` : "Choose an ETROC with NEED_INSPECT targets."; }
  function utcTimestamp(value) { const millis = typeof value === "number" ? value * 1000 : Date.parse(value || ""); return Number.isFinite(millis) ? new Date(millis).toISOString() : "Timestamp unavailable"; }
  function setHistory(items) { history.replaceChildren(); (items || []).forEach((item) => { const row = document.createElement("li"); row.textContent = `${item.state} · ${item.author_display || item.author || "Unknown reviewer"} · ${utcTimestamp(item.created_at ?? item.created_at_utc)} · ${item.note || "No note"}`; history.append(row); }); }
  function updateScientificContext(record) { scientificCandidateCounts(record).forEach((count, index) => { scientificCountNodes[index].textContent = String(count); }); }
  async function fetchSummary() { const response = await fetch(`/api/etroc-reviews?dataset_id=${encodeURIComponent(DATASET_ID)}`, { credentials: "same-origin", headers: { Accept: "application/json" } }); if (!response.ok) throw new Error("review service unavailable"); return response.json(); }
  async function fetchCompletionSummary() { const response = await fetch(`/api/etroc-position-reviews/completion?dataset_id=${encodeURIComponent(DATASET_ID)}`, { credentials: "same-origin", headers: { Accept: "application/json" } }); if (!response.ok) throw new Error("position completion service unavailable"); return response.json(); }
  async function fetchHistory(record) { const response = await fetch(`/api/etroc-reviews/history?acquisition_id=${encodeURIComponent(record.acquisition_id)}`, { credentials: "same-origin" }); if (!response.ok) throw new Error("review history unavailable"); return validatedHistory(await response.json(), record); }
  async function fetchPositionSummary(record) { const response = await fetch(`/api/etroc-position-reviews?dataset_id=${encodeURIComponent(DATASET_ID)}&acquisition_id=${encodeURIComponent(record.acquisition_id)}`, { credentials: "same-origin", headers: { Accept: "application/json" } }); if (!response.ok) throw new Error("position review service unavailable"); return response.json(); }
  async function fetchPositionHistory(record, position) { const response = await fetch(`/api/etroc-position-reviews/history?acquisition_id=${encodeURIComponent(record.acquisition_id)}&position=${position}`, { credentials: "same-origin", headers: { Accept: "application/json" } }); if (!response.ok) throw new Error("position review history unavailable"); return response.json(); }
  function positionFingerprint(position) { return POSITION_KEY_FIELDS.map((field) => position[field]).join("\u0000"); }
  function positionDraft() { const selected = dialog.querySelector("input[name='etroc-position-label']:checked"); return { label: selected?.value || "", note: positionNote.value.trim(), expected_current_event_id: state.position.summary?.reviews?.[String(state.position.active?.position)]?.current_event_id ?? null }; }
  function positionDirty() { return Boolean(state.position.active) && fingerprint(positionDraft()) !== state.position.loadedFingerprint; }
  function syncPositionDraft(review) { dialog.querySelectorAll("input[name='etroc-position-label']").forEach((control) => { control.checked = control.value === review?.label; }); positionNote.value = review?.note || ""; state.position.loadedFingerprint = fingerprint(positionDraft()); state.position.mutation = null; state.position.conflict = null; positionReapply.hidden = true; }
  function positionCanSave() { return Boolean(state.position.active?.review_target && HUMAN_LABELS.includes(positionDraft().label) && state.position.montageMode === "clean" && state.position.cleanVerified === state.position.active.clean_montage_sha256 && state.position.summary?.viewer?.can_append_review && !state.position.saveInFlight && !state.position.conflict); }
  function positionControlsEnabled(enabled) { const writable = Boolean(enabled && state.position.active?.review_target && state.position.mode !== "inspection"); [...dialog.querySelectorAll("input[name='etroc-position-label']"), positionNote, positionSave, positionSaveNext, positionPrevious].filter(Boolean).forEach((control) => { control.disabled = !writable; }); positionSave.disabled = !positionCanSave(); positionSaveNext.disabled = !positionCanSave() || state.position.mode !== "queue"; positionPrevious.disabled = state.position.mode !== "queue" || state.position.queueIndex <= 0; }
  function updatePositionProgress() { if (!state.position.parsed || !state.position.summary) { positionProgress.textContent = "Position evidence unavailable."; positionStart.disabled = true; return; } const reviews = state.position.summary.reviews; const labelledTargets = state.position.parsed.positions.filter((item) => item.review_target && reviews[String(item.position)]).length; const counts = Object.fromEntries(HUMAN_LABELS.map((label) => [label, Object.values(reviews).filter((review) => review.label === label).length])); positionProgress.textContent = `${labelledTargets} / ${state.position.parsed.targetCount} NEED_INSPECT positions labelled · GREEN ${counts.GREEN} · BLUE ${counts.BLUE} · YELLOW ${counts.YELLOW} · RED ${counts.RED}${state.position.active ? ` · position ${state.position.active.position} (row ${state.position.active.row}, column ${state.position.active.column})` : ""}`; positionStart.disabled = !state.position.summary.viewer.can_append_review || !makePositionQueue(state.position.parsed.positions, reviews).length; }
  function setPositionHistory(items) { positionHistory.replaceChildren(); (items || []).forEach((item) => { const row = document.createElement("li"); row.textContent = `${item.label} · ${item.author_display || item.author || "Unknown reviewer"} · ${utcTimestamp(item.created_at)} · ${item.note || "No note"}`; positionHistory.append(row); }); }
  function updatePositionContext(position) { positionContext.replaceChildren(); const heading = document.createElement("h4"); heading.textContent = `Position ${position.position} · row ${position.row} · column ${position.column}`; const algorithm = document.createElement("p"); algorithm.textContent = `Algorithm: ${position.algorithm_category} · ${position.algorithm_reason}. Exploratory signal, not a confirmed disposition.`; const measurement = position.height_measurement; const contract = position.height_contract; const heightEvidence = document.createElement("dl"); heightEvidence.className = "etroc-position-height-evidence"; const addHeight = (label, value) => { const term = document.createElement("dt"); term.textContent = label; const detail = document.createElement("dd"); detail.textContent = value; heightEvidence.append(term, detail); }; const heightMm = measurement.value; const heightUm = heightMm * 1000; addHeight("Measured height", `${heightMm.toFixed(4)} mm (${heightUm.toFixed(1)} µm)`); addHeight("Height status", measurement.status); addHeight("No-ball threshold", `≤ ${contract.no_ball_lte.toFixed(3)} mm (≤ ${(contract.no_ball_lte * 1000).toFixed(1)} µm)`); addHeight("In-spec range", `${contract.in_spec_min.toFixed(3)} ≤ height < ${contract.in_spec_max_exclusive.toFixed(3)} mm`); const delta = heightMm < contract.in_spec_min ? `${((contract.in_spec_min - heightMm) * 1000).toFixed(1)} µm below in-spec minimum` : heightMm >= contract.in_spec_max_exclusive ? `${((heightMm - contract.in_spec_max_exclusive) * 1000).toFixed(1)} µm above in-spec upper boundary` : "Within in-spec range"; addHeight("Reference delta", delta); const digest = document.createElement("p"); digest.textContent = `Source SHA-256 ${position.source_image_sha256}`; const canvas = document.createElement("canvas"); canvas.className = "etroc-position-context-crop"; canvas.width = 300; canvas.height = 240; canvas.setAttribute("aria-label", `Clean crop for position ${position.position}`); const context = canvas.getContext("2d"); if (context && image.complete && image.naturalWidth) context.drawImage(image, position.cell.x, position.cell.y + position.cell.image_y, position.cell.width, position.cell.image_height, 0, 0, 300, 240); positionContext.append(heading, algorithm, heightEvidence, digest, canvas); }
  function renderPositionGrid() { positionGrid.replaceChildren(); if (!state.position.parsed) return; const showAlgorithm = positionAlgorithmOverlay.checked; const showHuman = positionHumanOverlay.checked; state.position.parsed.positions.forEach((position) => { const review = state.position.summary?.reviews?.[String(position.position)]; const cell = document.createElementNS("http://www.w3.org/2000/svg", "rect"); cell.setAttribute("x", position.cell.x); cell.setAttribute("y", position.cell.y); cell.setAttribute("width", position.cell.width); cell.setAttribute("height", position.cell.height); cell.setAttribute("role", "gridcell"); cell.setAttribute("tabindex", state.position.active?.position === position.position ? "0" : "-1"); cell.setAttribute("aria-label", `Position ${position.position}, algorithm ${position.algorithm_category}, human ${review?.label || "unlabelled"}`); cell.dataset.position = String(position.position); cell.classList.add("position-cell"); if (showAlgorithm && position.review_target) cell.classList.add("target"); if (showHuman && review) cell.classList.add(`human-${review.label.toLowerCase()}`); if (state.position.active?.position === position.position) cell.classList.add("active"); cell.addEventListener("click", () => selectPosition(position)); cell.addEventListener("keydown", (event) => { let next = position.position; if (event.key === "ArrowRight") next += 1; else if (event.key === "ArrowLeft") next -= 1; else if (event.key === "ArrowDown") next += 16; else if (event.key === "ArrowUp") next -= 16; else if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectPosition(position); return; } else return; if (next >= 0 && next < 256) { event.preventDefault(); selectPosition(state.position.parsed.positions[next]); requestAnimationFrame(() => positionGrid.querySelector(`[data-position="${next}"]`)?.focus()); } }); positionGrid.append(cell); }); }
  async function selectPosition(position, queueMode = null) { if (!position || state.position.saveInFlight || positionDirty()) { if (positionDirty()) setStatus("Save or discard the active position draft before changing positions.", "failed"); return; } const reviewed = state.position.summary?.reviews?.[String(position.position)]; state.position.mode = queueMode || positionOpenMode(position, reviewed); state.position.active = position; if (state.position.mode === "queue") { const index = state.position.queue.findIndex((item) => item.position === position.position); if (index >= 0) state.position.queueIndex = index; } syncPositionDraft(reviewed); renderPositionGrid(); updatePositionContext(position); updatePositionProgress(); positionControlsEnabled(Boolean(state.position.summary?.viewer?.can_append_review)); if (state.position.mode === "inspection") setStatus("Non-target position: read-only inspection. Only NEED_INSPECT targets can be labelled.", "readonly"); try { const history = await fetchPositionHistory(state.active, position.position); if (state.position.active?.position === position.position) setPositionHistory(history.history); } catch (_) { setPositionHistory([]); positionControlsEnabled(false); } }
  async function loadPositionWorkspace(record) { state.position = { parsed: null, summary: null, evidence: new Map(), queue: [], queueIndex: 0, denominator: 0, active: null, mode: "queue", mutation: null, loadedFingerprint: "", cleanVerified: "", montageMode: "clean", saveInFlight: false, conflict: null }; positionGrid.replaceChildren(); setPositionHistory([]); updatePositionProgress(); const [publicationResponse, heightResponse, summary] = await Promise.all([fetch(`${DATA_BASE}${record.position_publication_uri}`, { credentials: "same-origin" }), fetch(`${DATA_BASE}${record.height_publication_uri}`, { credentials: "same-origin" }), fetchPositionSummary(record)]); if (!publicationResponse.ok) throw new Error("position publication unavailable"); if (!heightResponse.ok) throw new Error("height publication unavailable"); const [bytes, heightBytes] = await Promise.all([publicationResponse.arrayBuffer(), heightResponse.arrayBuffer()]); const parsed = await parsePositionPublication(bytes, record); const parsedHeight = reconcileHeightEvidence(record, await parseHeightPublication(heightBytes, record), summary); parsed.positions.forEach((position) => { position.height_measurement = parsedHeight.measurements[position.position]; position.height_contract = parsedHeight.contract; }); const evidence = reconcilePositionEvidence(record, parsed, summary, state.publication.publicationSha256); const cleanRecord = { montage_sha256: record.clean_montage_sha256, montage_uri: record.clean_montage_uri }; const cleanReady = await montage.load(cleanRecord); if (!cleanReady) throw new Error("clean montage verification failed"); state.position.parsed = parsed; state.position.summary = summary; state.position.evidence = evidence; state.position.queue = makePositionQueue(parsed.positions, summary.reviews); state.position.denominator = parsed.targetCount; state.position.cleanVerified = record.clean_montage_sha256; state.position.montageMode = "clean"; positionModeControls.forEach((control) => { control.checked = control.value === "clean"; }); renderPositionGrid(); updatePositionProgress(); positionStart.disabled = !summary.viewer.can_append_review || !state.position.queue.length; }
  async function switchPositionMontage(mode) { if (!state.active || !state.position.parsed || positionDirty()) { if (positionDirty()) setStatus("Save or discard the position draft before switching evidence modes.", "failed"); return; } state.position.cleanVerified = ""; state.position.montageMode = "loading"; positionControlsEnabled(false); controlsEnabled(false); const record = mode === "clean" ? { montage_sha256: state.active.clean_montage_sha256, montage_uri: state.active.clean_montage_uri } : state.active; const ready = await montage.load(record); if (!ready) { state.position.montageMode = "unavailable"; positionControlsEnabled(false); return; } state.position.montageMode = mode; if (mode === "clean") { state.position.cleanVerified = state.active.clean_montage_sha256; if (state.position.active) updatePositionContext(state.position.active); } controlsEnabled(mode === "analysis" && Boolean(state.summary?.viewer?.can_append_review)); positionControlsEnabled(mode === "clean" && Boolean(state.position.summary?.viewer?.can_append_review)); }
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
    title.textContent = `Classify NEED_INSPECT positions — ${record.etroc_serial}`;
    updateScientificContext(record);
    provenance.textContent = `${record.acquisition_id} · ${record.analysis_run_id} · montage SHA-256 ${record.montage_sha256} · ${record.montage_uri}`;
    setPositionHistory([]);
    zoom(1);
    updateProgress();
    setStatus("Verifying exact montage and position evidence", "");
    const montageReady = await montage.load(record);
    if (!state.session.accept(token, record.acquisition_id)) return;
    state.verificationInFlight = false;
    if (!montageReady) {
      controlsEnabled(false);
      updateProgress();
      return;
    }
    state.session.markVerified(token, record.acquisition_id, evidenceKey(record));
    state.activeMontageVerified = evidenceKey(record);
    try {
      await loadPositionWorkspace(record);
      inspectionControlsEnabled(true);
      positionControlsEnabled(false);
      updateProgress();
      setStatus(state.position.summary.viewer.can_append_review ? "Verified clean evidence. Select a NEED_INSPECT target or start the queue." : `Verified clean evidence for ${state.position.summary.viewer.identity_display || "current identity"}. Read-only access.`, state.position.summary.viewer.can_append_review ? "verified" : "readonly");
    } catch (error) {
      positionControlsEnabled(false);
      positionProgress.textContent = `Position classification unavailable: ${error.message}`;
      updateProgress();
      setStatus("Verified acquisition evidence. Position classification unavailable.", "failed");
    }
    void preloadAdjacent();
  }
  function applyQueue(record, origin) { const item = state.completion.get(record.acquisition_id); const queue = makeCompletionQueue(state.records, state.completion, filters()); const index = queue.findIndex((candidate) => candidate.acquisition_id === record.acquisition_id); state.mode = item?.status === "review_complete" ? "correction" : "queue"; state.queue = index < 0 ? [record] : queue.slice(index); state.queueIndex = 0; state.queueFilters = filters(); state.active = record; state.origin = origin; dialog.hidden = false; updateDialog(); close.focus(); }
  function interactionBusy() { return state.saveInFlight || state.verificationInFlight || state.position.saveInFlight; }
  function requestDestination(destination) { if (!dirty()) return destination(); state.pendingDestination = destination; confirmDiscard.showModal(); confirmDiscard.querySelector("[data-etroc-review-keep]")?.focus(); }
  function requestClose() { if (interactionBusy()) { setStatus("Wait for the active save or verification before closing.", "failed"); return; } requestDestination(closeDialog); }
  function closeDialog() { if (interactionBusy()) return; state.pendingDestination = null; state.session.begin(""); preloadAbort?.abort(); state.activeMontageVerified = ""; state.position.cleanVerified = ""; positionGrid.replaceChildren(); positionControlsEnabled(false); controlsEnabled(false); montage.close(); image.removeAttribute("src"); dialog.hidden = true; state.origin?.focus(); }
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
  async function savePositionReview(andNext) {
    if (!positionCanSave()) return;
    const active = state.position.active; const draft = validatePositionDraft(positionDraft());
    if (!active.review_target) { setStatus("Only NEED_INSPECT target positions can be labelled.", "failed"); return; }
    const draftFingerprint = fingerprint(draft); state.position.mutation = { fingerprint: draftFingerprint, id: draftMutation(draft, state.position.mutation && { fingerprint: state.position.mutation.fingerprint, mutationId: state.position.mutation.id }, () => crypto.randomUUID()) };
    const payload = Object.fromEntries(POSITION_KEY_FIELDS.map((field) => [field, active[field]])); Object.assign(payload, draft, { mutation_id: state.position.mutation.id });
    state.position.saveInFlight = true; positionControlsEnabled(false);
    try {
      const response = await fetch("/api/etroc-position-reviews", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const body = await response.json();
      if (response.status === 409) {
        const conflict = body.error;
        if (!conflict || typeof conflict.code !== "string") throw new Error("position conflict response is malformed");
        const summary = await fetchPositionSummary(state.active);
        state.position.evidence = reconcilePositionEvidence(state.active, state.position.parsed, summary, state.publication.publicationSha256);
        state.position.summary = summary;
        state.position.conflict = { ...conflict, current: summary.reviews[String(active.position)] || null };
        positionReapply.hidden = false;
        renderPositionGrid(); updatePositionProgress(); positionControlsEnabled(false);
        setStatus(`${conflict.message || "Position conflict"} Draft retained; explicitly reapply with a fresh mutation ID.`, "failed");
        return;
      }
      if (!response.ok || body.ok !== true || typeof body.idempotent_replay !== "boolean" || !body.event || POSITION_KEY_FIELDS.some((field) => body.event[field] !== active[field]) || body.event.label !== draft.label || body.event.note !== draft.note || body.event.mutation_id !== payload.mutation_id || body.event.supersedes_event_id !== draft.expected_current_event_id) throw new Error(body.error?.message || "position save failed");
      const summary = await fetchPositionSummary(state.active); const reconciled = reconcilePositionEvidence(state.active, state.position.parsed, summary, state.publication.publicationSha256); state.position.summary = summary; state.position.evidence = reconciled;
      state.completion.set(state.active.acquisition_id, { acquisition_id: state.active.acquisition_id, etroc_serial: state.active.etroc_serial, target_count: summary.target_count, reviewed_target_count: summary.reviewed_target_count, status: summary.completion_status });
      updateReviewSurface();
      const current = summary.reviews[String(active.position)]; if (!current || current.current_event_id < body.event.event_id || current.label !== draft.label || POSITION_KEY_FIELDS.some((field) => current[field] !== active[field])) throw new Error("position save readback mismatch");
      const history = await fetchPositionHistory(state.active, active.position); if (!history.history?.some((item) => item.event_id === body.event.event_id)) throw new Error("position history readback mismatch");
      setPositionHistory(history.history); renderPositionGrid(); updatePositionProgress();
      if (current.current_event_id > body.event.event_id) {
        state.position.conflict = { code: "post_save_successor", current };
        positionReapply.hidden = false;
        positionControlsEnabled(false);
        setStatus("Position review saved, then changed by another reviewer. Draft retained; explicitly reapply.", "failed");
        return;
      }
      if (current.current_event_id !== body.event.event_id) throw new Error("position current event does not match saved event");
      syncPositionDraft(current); setStatus(summary.completion_status === "review_complete" ? "Position review saved. ETROC review complete." : "Position review saved and read back.", "verified");
      if (andNext && state.position.mode === "queue") { const nextIndex = state.position.queue.findIndex((item, index) => index > state.position.queueIndex && !summary.reviews[String(item.position)]); if (nextIndex >= 0) { state.position.queueIndex = nextIndex; state.position.saveInFlight = false; await selectPosition(state.position.queue[nextIndex], "queue"); return; } setStatus(summary.completion_status === "review_complete" ? "ETROC review complete. All NEED_INSPECT positions are labelled." : "Position target queue complete for this snapshot.", "verified"); }
    } catch (error) { setStatus(`Position save unavailable: ${error.message}. Retry retains this mutation ID.`, "failed"); }
    finally { state.position.saveInFlight = false; positionControlsEnabled(Boolean(state.position.summary?.viewer?.can_append_review) && state.position.montageMode === "clean"); }
  }
  function reapplyPositionConflict() {
    if (!state.position.conflict || !state.position.active) return;
    state.position.mutation = null;
    state.position.conflict = null;
    positionReapply.hidden = true;
    positionControlsEnabled(Boolean(state.position.summary?.viewer?.can_append_review) && state.position.montageMode === "clean");
    setStatus("Intervening position version adopted. Draft is ready with a fresh mutation ID.", "verified");
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
  function updateCardReview(card, record) { if (!card) return; let detail = card.querySelector("[data-etroc-review-card-state]"); if (!detail) { detail = document.createElement("small"); detail.setAttribute("data-etroc-review-card-state", ""); card.querySelector(".etroc-pool-card-body")?.append(detail); } const item = state.completion.get(record.acquisition_id); card.dataset.reviewCompletion = item?.status || "unavailable"; card.classList.toggle("review-complete", item?.status === "review_complete"); if (item?.status === "review_complete") detail.textContent = `${item.reviewed_target_count} / ${item.target_count} NEED_INSPECT positions labelled · Review complete`; else if (item?.status === "review_pending") detail.textContent = `${item.reviewed_target_count} / ${item.target_count} NEED_INSPECT positions labelled · Review pending`; else if (item?.status === "not_applicable") detail.textContent = "No NEED_INSPECT targets · Not applicable"; else detail.textContent = "Review completion unavailable"; }
  function updateReviewSurface() { if (!state.summary || !state.completion.size) return; let visible = 0; let complete = 0; let pending = 0; state.records.forEach((record) => { const item = state.completion.get(record.acquisition_id); complete += Number(item?.status === "review_complete"); pending += Number(item?.status === "review_pending"); const matches = candidateMatch(record, candidateFilter?.value || "needs_inspection") && completionMatch(completionFilter?.value || "pending", item); const card = document.querySelector(`[data-etroc-acquisition="${record.acquisition_id}"]`); card?.classList.toggle("review-filter-hidden", !matches); updateCardReview(card, record); visible += Number(matches); }); document.querySelectorAll(".etroc-pool-group").forEach((group) => { const cards = [...group.querySelectorAll(".etroc-pool-card")]; const shown = cards.filter((card) => !card.classList.contains("review-filter-hidden")).length; const label = group.querySelector(".wafer span"); if (label) label.textContent = `${shown} / ${cards.length} ETROCs shown · ETROC_OI_2608 exploratory montages`; }); summaryNode.textContent = `${visible} / ${state.records.length} ETROCs shown · ${complete} review complete · ${pending} review pending`; const queue = makeCompletionQueue(state.records, state.completion, filters()); start.disabled = !state.verified || !queue.length; }

  globalThis.addEventListener("etroc-optical-publication", async (event) => { try { const detail = event.detail || {}; const parsed = detail.records && detail.publicationSha256 ? publicationFromEvent(detail) : await parsePublication(detail.bytes); const [summary, completionPayload] = await Promise.all([fetchSummary(), fetchCompletionSummary()]); state.evidence = reconcileEvidence(parsed, summary); state.completion = reconcileCompletion(parsed.records, completionPayload, parsed.publicationSha256); state.records = parsed.records; state.publication = parsed; state.summary = summary; state.verified = true; bindRecords(state.records); updateReviewSurface(); setStatus("Verified position classification workspace available.", "verified"); } catch (error) { state.verified = false; controlsEnabled(false); setStatus(`Review unavailable: ${error.message}`, "failed"); } });
  dialog.addEventListener("keydown", (event) => { trapFocus(event); if (confirmDiscard.open) return; if (event.key === "Escape") { event.preventDefault(); requestClose(); return; } if (["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) return; if (event.key === "+") zoom(state.zoom + .25); if (event.key === "-") zoom(state.zoom - .25); });
  dialog.addEventListener("click", (event) => { if (event.target === dialog) requestClose(); });
  close.addEventListener("click", requestClose); reset.addEventListener("click", () => zoom(1)); fit.addEventListener("click", () => zoom(1)); zoomIn.addEventListener("click", () => zoom(state.zoom + .25)); zoomOut.addEventListener("click", () => zoom(state.zoom - .25)); confirmDiscard.addEventListener("cancel", () => { state.pendingDestination = null; }); confirmDiscard.querySelector("[data-etroc-review-keep]")?.addEventListener("click", () => { state.pendingDestination = null; confirmDiscard.close(); }); confirmDiscard.querySelector("[data-etroc-review-discard]")?.addEventListener("click", () => { const destination = state.pendingDestination; state.pendingDestination = null; confirmDiscard.close(); destination?.(); }); dialog.querySelectorAll("input[name='etroc-position-label']").forEach((control) => control.addEventListener("change", () => positionControlsEnabled(Boolean(state.position.summary?.viewer?.can_append_review) && state.position.montageMode === "clean"))); positionNote.addEventListener("input", () => positionControlsEnabled(Boolean(state.position.summary?.viewer?.can_append_review) && state.position.montageMode === "clean")); positionAlgorithmOverlay.addEventListener("change", renderPositionGrid); positionHumanOverlay.addEventListener("change", renderPositionGrid); positionModeControls.forEach((control) => control.addEventListener("change", () => { if (control.checked) void switchPositionMontage(control.value); })); positionStart.addEventListener("click", async () => { if (!state.active || !state.position.parsed || positionDirty()) return; try { const summary = await fetchPositionSummary(state.active); state.position.evidence = reconcilePositionEvidence(state.active, state.position.parsed, summary, state.publication.publicationSha256); state.position.summary = summary; state.position.queue = makePositionQueue(state.position.parsed.positions, summary.reviews); state.position.queueIndex = 0; state.position.denominator = state.position.parsed.targetCount; renderPositionGrid(); updatePositionProgress(); if (state.position.queue.length) await selectPosition(state.position.queue[0], "queue"); } catch (error) { setStatus(`Position queue unavailable: ${error.message}`, "failed"); } }); positionPrevious.addEventListener("click", () => { if (state.position.mode === "queue" && state.position.queueIndex > 0 && !positionDirty()) { state.position.queueIndex -= 1; void selectPosition(state.position.queue[state.position.queueIndex], "queue"); } }); positionSave.addEventListener("click", () => void savePositionReview(false)); positionSaveNext.addEventListener("click", () => void savePositionReview(true)); positionReapply.addEventListener("click", reapplyPositionConflict); start.addEventListener("click", async () => { try { const [summary, completionPayload] = await Promise.all([fetchSummary(), fetchCompletionSummary()]); const reconciled = reconcileEvidence(state.publication, summary); state.summary = summary; state.evidence = reconciled; state.completion = reconcileCompletion(state.records, completionPayload, state.publication.publicationSha256); updateReviewSurface(); const queue = makeCompletionQueue(state.records, state.completion, filters()); if (queue.length) applyQueue(queue[0], start); } catch (error) { setStatus(`Review unavailable: ${error.message}`, "failed"); } }); [stateFilter, orderFilter, waferFilter, serialFilter, candidateFilter, completionFilter].forEach((control) => control?.addEventListener("change", updateReviewSurface)); globalThis.addEventListener("beforeunload", (event) => { if (dirty()) { event.preventDefault(); event.returnValue = ""; } });
})();
