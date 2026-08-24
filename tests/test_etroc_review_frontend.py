from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hybrid-bbqc"
SCRIPT = APP / "etroc-review.js"
INDEX = APP / "index.html"


class ETROCReviewFrontendTests(unittest.TestCase):
    def node(self, program: str, *extra_args: str | Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["node", "-e", program, str(SCRIPT), *(str(path) for path in extra_args)],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_position_publication_reconciliation_and_target_queue_are_fail_closed(self):
        pool = json.loads((APP / "data/etroc-optical/ETROC_OI_2608/chips.json").read_text(encoding="utf-8"))
        record = next(item for item in pool["records"] if item["position_review_target_count"] > 0)
        position_path = APP / "data/etroc-optical/ETROC_OI_2608" / record["position_publication_uri"]
        program = r'''
const fs=require("fs"); const crypto=require("crypto").webcrypto; global.crypto=crypto; global.document={querySelector:()=>null}; require(process.argv[1]);
const c=global.ETROCReviewContract; if(!c.POSITION_KEY_FIELDS.includes("position_publication_sha256")) process.exit(100); const record=JSON.parse(process.argv[3]); record.dataset_id="ETROC_OI_2608"; const bytes=fs.readFileSync(process.argv[2]);
(async()=>{
 const parsed=await c.parsePositionPublication(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),record);
 if(parsed.positions.length!==256 || parsed.targetCount!==record.position_review_target_count) process.exit(101);
 const evidence=Object.fromEntries(parsed.positions.map(position=>[String(position.position),Object.fromEntries(c.POSITION_EVIDENCE_FIELDS.map(field=>[field,position[field]]))]));
 const summary={dataset_id:"ETROC_OI_2608",publication_sha256:"c".repeat(64),acquisition_id:record.acquisition_id,etroc_serial:record.etroc_serial,analysis_run_id:record.analysis_run_id,labelled_montage_sha256:record.montage_sha256,clean_montage_sha256:record.clean_montage_sha256,clean_montage_uri:`data/etroc-optical/ETROC_OI_2608/${record.clean_montage_uri}`,position_publication_sha256:record.position_publication_sha256,position_publication_uri:`data/etroc-optical/ETROC_OI_2608/${record.position_publication_uri}`,geometry_version:"etroc-grid-16x16-v1",position_count:256,target_count:parsed.targetCount,viewer:{identity_display:"reviewer",can_append_review:true},evidence,reviews:{}};
 const reconciled=c.reconcilePositionEvidence(record,parsed,summary,summary.publication_sha256); if(reconciled.size!==256) process.exit(102);
 const queue=c.makePositionQueue(parsed.positions,{}); if(queue.length!==parsed.targetCount || queue.some(position=>!position.review_target)) process.exit(103);
 const reviews={[String(queue[0].position)]:{label:"GREEN"}}; if(c.makePositionQueue(parsed.positions,reviews).length!==queue.length-1) process.exit(104);
 for(const mutate of [()=>{const x=structuredClone(summary);x.publication_sha256="d".repeat(64);return x},()=>{const x=structuredClone(summary);x.target_count++;return x},()=>{const x=structuredClone(summary);x.evidence["0"].source_image_sha256="b".repeat(64);return x},()=>{const x=structuredClone(summary);delete x.evidence["255"];return x}]){let rejected=false;try{c.reconcilePositionEvidence(record,parsed,mutate(),summary.publication_sha256)}catch(_){rejected=true}if(!rejected)process.exit(105)}
})().catch(error=>{console.error(error);process.exit(106)});
'''
        result = self.node(program, position_path, json.dumps(record))
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_verified_evidence_contract_and_queue_are_fail_closed(self):
        program = r'''
const crypto = require("crypto").webcrypto;
global.crypto = crypto;
global.document = { querySelector: () => null };
require(process.argv[1]);
const c = global.ETROCReviewContract;
if (!c) process.exit(10);
const digest = "a".repeat(64);
const records = Array.from({length: 36}, (_, index) => ({
  dataset_id:"ETROC_OI_2608", etroc_serial:`W02G4-${index + 1}`,
  acquisition_id:`ETROC_OI_2608:W02G4-${index + 1}:base`, analysis_run_id:"run",
  montage_sha256:digest, montage_uri:`montages/sha256/${digest}.jpg`,
  review_candidate_count:index === 1 ? 1 : 0, optical_no_ball_candidate_count:index === 0 ? 1 : 0,
}));
(async () => {
  const bytes = new TextEncoder().encode(JSON.stringify({dataset_id:"ETROC_OI_2608",record_count:36,records}));
  const publication = await c.parsePublication(bytes.buffer);
  const evidence = Object.fromEntries(records.map((record) => [record.acquisition_id, {...Object.fromEntries(c.EVIDENCE_FIELDS.map((field) => [field, record[field]])), montage_uri:`data/etroc-optical/ETROC_OI_2608/${record.montage_uri}`}]));
  const summary = {dataset_id:"ETROC_OI_2608",record_count:36,publication_sha256:await c.sha256(bytes.buffer),viewer:{identity_display:"reviewer",can_append_review:true},evidence,reviews:{}};
  const reconciled = c.reconcileEvidence(publication, summary);
  if (reconciled.size !== 36) process.exit(11);
  const queue = c.makeQueue(records, {}, {state:"unreviewed", wafer:"", serial:"", candidate:"all", order:"candidate"});
  if (queue.length !== 36 || queue[0].acquisition_id !== records[0].acquisition_id || queue.at(-1).acquisition_id !== records[35].acquisition_id) process.exit(12);
  for (const mutate of [
    () => { const broken = structuredClone(summary); broken.publication_sha256 = digest; return broken; },
    () => { const broken = structuredClone(summary); delete broken.evidence[records[0].acquisition_id]; return broken; },
    () => { const broken = structuredClone(summary); broken.evidence[records[0].acquisition_id].montage_sha256 = "b".repeat(64); return broken; },
    () => { const broken = structuredClone(summary); broken.viewer.extra = true; return broken; },
    () => { const broken = structuredClone(summary); broken.evidence[records[0].acquisition_id].extra = true; return broken; },
  ]) { let rejected = false; try { c.reconcileEvidence(publication, mutate()); } catch (_) { rejected = true; } if (!rejected) process.exit(13); }
})().catch(() => process.exit(14));
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_same_byte_publication_event_derives_dataset_identity_before_reconciliation(self):
        program = r'''
global.document = { querySelector: () => null }; require(process.argv[1]); const c = global.ETROCReviewContract;
const digest = "a".repeat(64);
const records = Array.from({length: 36}, (_, index) => ({
  etroc_serial:`W02G4-${index + 1}`, acquisition_id:`ETROC_OI_2608:W02G4-${index + 1}:base`,
  analysis_run_id:"run", montage_sha256:digest, montage_uri:`montages/sha256/${digest}.jpg`,
}));
const parsed = c.publicationFromEvent({records, publicationSha256:"b".repeat(64)});
if (parsed.records.length !== 36 || parsed.records.some(record => record.dataset_id !== "ETROC_OI_2608")) process.exit(15);
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_successful_save_uses_validated_refreshed_current_not_post_envelope(self):
        program = r'''
global.document = { querySelector: () => null }; require(process.argv[1]); const c = global.ETROCReviewContract;
const digest = "a".repeat(64);
const current = {dataset_id:"ETROC_OI_2608",etroc_serial:"W02G4-44",acquisition_id:"a",analysis_run_id:"run",montage_sha256:digest,state:"reviewed_concern_observed",note:"checked",current_event_id:9};
const summary = {reviews:{a:current}};
const accepted = c.validatedSaveCurrent(summary, "a", {ok:true,current:{...current},event:{event_id:9}});
if (accepted !== current || accepted.current_event_id !== 9) process.exit(16);
for (const body of [{ok:true,event:{event_id:9}}, {ok:true,current:{...current,current_event_id:8}}]) {
  let rejected=false; try { c.validatedSaveCurrent(summary,"a",body); } catch (_) { rejected=true; }
  if (!rejected) process.exit(17);
}
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_mutation_identity_and_conflict_draft_contract(self):
        program = r'''
global.document = { querySelector: () => null }; require(process.argv[1]); const c = global.ETROCReviewContract;
let ids = 0; const create = () => `uuid-${++ids}`;
const first = c.draftMutation({state:"reviewed_no_optical_concern", note:"", expected_current_event_id:null}, null, create);
const retry = c.draftMutation({state:"reviewed_no_optical_concern", note:"", expected_current_event_id:null}, first, create);
const changed = c.draftMutation({state:"follow_up_required", note:"reinspect", expected_current_event_id:null}, retry, create);
if (first !== retry || changed === retry || ids !== 2) process.exit(20);
const conflict = c.applySaveResult({draft:{state:"follow_up_required",note:"reinspect"}, queueIndex:2}, {status:409});
if (conflict.queueIndex !== 2 || conflict.draft.note !== "reinspect" || !conflict.conflict) process.exit(21);
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_controller_queue_snapshot_and_direct_open_modes(self):
        program = r'''
global.document = { querySelector: () => null }; require(process.argv[1]); const c = global.ETROCReviewContract;
const records = [
  {etroc_serial:"W02G4-10", wafer:"W02G4", chip:"10", acquisition_id:"a", optical_no_ball_candidate_count:0, review_candidate_count:4, red_candidate_count:1, needs_inspection_count:1},
  {etroc_serial:"W02G4-2", wafer:"W02G4", chip:"2", acquisition_id:"b", optical_no_ball_candidate_count:1, review_candidate_count:0, red_candidate_count:0, needs_inspection_count:0},
  {etroc_serial:"W03F7-1", wafer:"W03F7", chip:"1", acquisition_id:"c", optical_no_ball_candidate_count:0, review_candidate_count:9, red_candidate_count:3, needs_inspection_count:8},
];
const reviews = {c:{state:"reviewed_concern_observed", current_event_id:7}};
const snapshot = c.snapshotQueue(records, reviews, {state:"reviewed_concern_observed", wafer:"", serial:"", candidate:"all", order:"candidate"});
if (snapshot.map(r => r.acquisition_id).join(",") !== "b,a") process.exit(31);
const openingFilters = {wafer:"",serial:"",candidate:"all",order:"candidate"};
const opened = c.openQueue(records, reviews, records[0], openingFilters);
openingFilters.wafer = "W03F7";
if (opened.mode !== "queue" || opened.queue.map(r=>r.acquisition_id).join(",") !== "a" || opened.filters.wafer !== "") process.exit(32);
const correction = c.openQueue(records, reviews, records[2], {wafer:"",serial:"",candidate:"all",order:"candidate"});
if (correction.mode !== "correction" || correction.queue.length !== 1 || correction.saveNext || correction.filters.order !== "candidate") process.exit(33);
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_candidate_priority_filter_and_remote_save_next_refresh(self):
        program = r'''
global.document = { querySelector: () => null }; require(process.argv[1]); const c = global.ETROCReviewContract;
const records = [
  {etroc_serial:"W02G4-9", acquisition_id:"reviewed", optical_no_ball_candidate_count:8, red_candidate_count:8, needs_inspection_count:8, review_candidate_count:8},
  {etroc_serial:"W02G4-10", acquisition_id:"no-ball", optical_no_ball_candidate_count:1, red_candidate_count:0, needs_inspection_count:0, review_candidate_count:0},
  {etroc_serial:"W02G4-1", acquisition_id:"red", optical_no_ball_candidate_count:0, red_candidate_count:1, needs_inspection_count:99, review_candidate_count:99},
  {etroc_serial:"W02G4-2", acquisition_id:"needs", optical_no_ball_candidate_count:0, red_candidate_count:0, needs_inspection_count:9, review_candidate_count:1},
  {etroc_serial:"W02G4-3", acquisition_id:"candidate", optical_no_ball_candidate_count:0, red_candidate_count:0, needs_inspection_count:2, review_candidate_count:9},
  {etroc_serial:"W02G4-4", acquisition_id:"serial-a", optical_no_ball_candidate_count:0, red_candidate_count:0, needs_inspection_count:0, review_candidate_count:0},
  {etroc_serial:"W02G4-5", acquisition_id:"serial-b", optical_no_ball_candidate_count:0, red_candidate_count:0, needs_inspection_count:0, review_candidate_count:0},
];
const reviews = {reviewed:{state:"reviewed_no_optical_concern"}};
const filters = {wafer:"", serial:"", candidate:"all", order:"candidate"};
const ordered = c.makeQueue(records, reviews, {...filters, state:""}).map(record => record.acquisition_id).join(",");
if (ordered !== "no-ball,red,needs,candidate,serial-a,serial-b,reviewed") process.exit(70);
for (const [candidate, expected] of [["all", 7], ["no_ball", 2], ["red", 2], ["needs_inspection", 4], ["review_candidate", 4]]) {
  if (c.makeQueue(records, reviews, {...filters, state:"", candidate}).length !== expected) process.exit(71);
}
const nextReviews = {reviewed:{state:"reviewed_no_optical_concern"}, "no-ball":{state:"reviewed_no_optical_concern"}, red:{state:"reviewed_concern_observed"}};
const originalQueue = records.filter(record => record.acquisition_id !== "reviewed");
const next = c.refreshQueueAfterSave(originalQueue, nextReviews, "no-ball");
if (next.queue.map(record => record.acquisition_id).join(",") !== "needs,candidate,serial-a,serial-b" || next.queueIndex !== 0) process.exit(72);
const direct = c.refreshQueueAfterSave([{acquisition_id:"a"},{acquisition_id:"b"},{acquisition_id:"c"}], {}, "b");
if (direct.queue.map(record => record.acquisition_id).join(",") !== "c") process.exit(73);
if (c.nextQueueIndex([{acquisition_id:"a"},{acquisition_id:"b"},{acquisition_id:"c"}], {b:{state:"reviewed_no_optical_concern"}}, 0) !== 2) process.exit(74);
const lowRedHighNeeds = {etroc_serial:"W02G4-1",acquisition_id:"x",optical_no_ball_candidate_count:0,red_candidate_count:1,needs_inspection_count:9,review_candidate_count:0};
const highRedLowNeeds = {etroc_serial:"W02G4-2",acquisition_id:"y",optical_no_ball_candidate_count:0,red_candidate_count:8,needs_inspection_count:1,review_candidate_count:0};
if (c.canonicalComparator(lowRedHighNeeds, highRedLowNeeds, {}) >= 0) process.exit(75);
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_generation_gate_rejects_stale_async_completion_and_requires_active_verified_blob(self):
        program = r'''
global.document = { querySelector: () => null }; require(process.argv[1]); const c = global.ETROCReviewContract;
const gate = new c.ReviewSessionGate();
const first = gate.begin("first");
const second = gate.begin("second");
if (gate.accept(first, "first") || !gate.accept(second, "second") || gate.canSave("second")) process.exit(80);
gate.markVerified(second, "second", "hash-a");
if (!gate.canSave("second", "hash-a") || gate.canSave("second", "hash-b")) process.exit(81);
gate.begin("third");
if (gate.canSave("second", "hash-a")) process.exit(82);
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_controller_montage_generation_ignores_stale_bytes_and_revokes_urls(self):
        program = r'''
const crypto = require("crypto").webcrypto; global.crypto = crypto; global.document = {querySelector: () => null}; require(process.argv[1]);
const c = global.ETROCReviewContract; const digest = "a".repeat(64); let resolveFirst; let calls = 0; const revoked=[];
const loader = new c.MontageController({
  fetch: () => new Promise(resolve => { if (++calls === 1) resolveFirst=resolve; else resolve({ok:true, blob:async()=>new Blob(["second"])}); }),
  hash: async () => digest, createObjectURL: blob => blob === undefined ? "" : `blob:${calls}`, revokeObjectURL: value => revoked.push(value),
  decode: async () => {}, onReady: () => {}, onError: error => { throw error; },
});
const record = {montage_sha256:digest, montage_uri:`montages/sha256/${digest}.jpg`};
const first = loader.load(record); const second = loader.load(record); resolveFirst({ok:true, blob:async()=>new Blob(["first"])});
Promise.all([first, second]).then(() => { if (loader.objectUrl !== "blob:2" || revoked.includes("blob:2")) process.exit(41); loader.close(); if (!revoked.includes("blob:2")) process.exit(42); }).catch(() => process.exit(43));
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_controller_revokes_a_verified_url_when_image_decode_fails(self):
        program = r'''
global.document = {querySelector: () => null}; require(process.argv[1]); const c = global.ETROCReviewContract;
const digest = "a".repeat(64); const revoked=[]; let failures=0;
const loader = new c.MontageController({fetch:async()=>({ok:true,blob:async()=>new Blob(["bytes"])}),hash:async()=>digest,createObjectURL:()=>"blob:verified",revokeObjectURL:url=>revoked.push(url),decode:async()=>{throw new Error("decode failed")},onReady:()=>process.exit(51),onError:()=>{failures++}});
loader.load({montage_sha256:digest,montage_uri:`montages/sha256/${digest}.jpg`}).then(() => {if (failures !== 1 || loader.objectUrl || revoked.join(",") !== "blob:verified") process.exit(52);});
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_stale_decode_revokes_only_its_local_object_url(self):
        program = r'''
global.document = {querySelector: () => null}; require(process.argv[1]); const c = global.ETROCReviewContract;
const digest = "a".repeat(64); const revoked=[]; let resolveFirstDecode; let loads=0;
const loader = new c.MontageController({
  fetch: async () => ({ok:true,blob:async()=>new Blob(["bytes"])}), hash:async()=>digest,
  createObjectURL:()=>`blob:${++loads}`, revokeObjectURL:url=>revoked.push(url),
  decode:url=>url === "blob:1" ? new Promise(resolve=>{resolveFirstDecode=resolve}) : Promise.resolve(),
  onReady:()=>{}, onError:error=>{throw error},
});
const record={montage_sha256:digest,montage_uri:`montages/sha256/${digest}.jpg`};
(async()=>{const first=loader.load(record); while (!resolveFirstDecode) await Promise.resolve(); await loader.load(record); resolveFirstDecode(); await first; if (loader.objectUrl !== "blob:2" || revoked.includes("blob:2") || !revoked.includes("blob:1")) process.exit(53);})();
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_save_and_history_envelopes_require_exact_evidence_event_and_chain(self):
        program = r'''
global.document = {querySelector: () => null}; require(process.argv[1]); const c = global.ETROCReviewContract;
const hash="a".repeat(64); const evidence={dataset_id:"ETROC_OI_2608",etroc_serial:"W02G4-44",acquisition_id:"a",analysis_run_id:"run",montage_sha256:hash,montage_uri:`data/etroc-optical/ETROC_OI_2608/montages/sha256/${hash}.jpg`};
const payload={...Object.fromEntries(c.EVIDENCE_FIELDS.map(field=>[field,evidence[field]])),state:"follow_up_required",note:"reinspect",mutation_id:"11111111-1111-4111-8111-111111111111",expected_current_event_id:4};
const event={event_id:5,...Object.fromEntries(c.EVIDENCE_FIELDS.map(field=>[field,evidence[field]])),state:payload.state,note:payload.note,author:"reviewer@cern.ch",author_display:"reviewer",created_at:1,mutation_id:payload.mutation_id,supersedes_event_id:4};
const current={current_event_id:5,...Object.fromEntries(c.EVIDENCE_FIELDS.map(field=>[field,evidence[field]])),state:event.state,note:event.note,author:event.author,author_display:event.author_display,created_at:1,history_count:2};
const summary={reviews:{a:current}}; const body={ok:true,idempotent_replay:false,event,current};
const direct=c.validatedSaveEnvelope(summary,"a",body,payload);
if (direct.current!==current || direct.saved!==event || direct.superseded) process.exit(54);
const successor={...current,current_event_id:6,state:"reviewed_concern_observed",note:"newer",created_at:2,history_count:3};
const raced=c.validatedSaveEnvelope({reviews:{a:successor}},"a",body,payload);
if (raced.current!==successor || raced.saved!==event || !raced.superseded) process.exit(57);
const replayRaced=c.validatedSaveEnvelope({reviews:{a:successor}},"a",{...body,idempotent_replay:true,current:successor},payload);
if (replayRaced.current!==successor || replayRaced.saved!==event || !replayRaced.superseded) process.exit(58);
const root={...event,supersedes_event_id:null};
if (c.validatedHistory({evidence,current:root,history:[root]},evidence)[0] !== root) process.exit(55);
for (const broken of [{...body,event:{...event,mutation_id:"22222222-2222-4222-8222-222222222222"}}, {evidence,current,event,history:[{...event,event_id:4,supersedes_event_id:null}]}]) { let rejected=false; try { if (broken.ok) c.validatedSaveEnvelope(summary,"a",broken,payload); else c.validatedHistory(broken,evidence); } catch (_) { rejected=true; } if (!rejected) process.exit(56); }
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_reconciliation_rejects_review_with_mismatched_provenance(self):
        program = r'''
const crypto=require("crypto").webcrypto; global.crypto=crypto; global.document={querySelector:()=>null}; require(process.argv[1]); const c=global.ETROCReviewContract; const hash="a".repeat(64);
const records=Array.from({length:36},(_,i)=>({dataset_id:"ETROC_OI_2608",etroc_serial:`W02G4-${i}`,acquisition_id:`a${i}`,analysis_run_id:"run",montage_sha256:hash,montage_uri:`montages/sha256/${hash}.jpg`}));
(async()=>{const bytes=new TextEncoder().encode(JSON.stringify({dataset_id:"ETROC_OI_2608",record_count:36,records})); const publication=await c.parsePublication(bytes); const evidence=Object.fromEntries(records.map(r=>[r.acquisition_id,{...r,montage_uri:`data/etroc-optical/ETROC_OI_2608/${r.montage_uri}`}])) ; const summary={dataset_id:"ETROC_OI_2608",record_count:36,publication_sha256:await c.sha256(bytes),viewer:{can_append_review:true},evidence,reviews:{a0:{...records[0],montage_sha256:"b".repeat(64),state:"reviewed_no_optical_concern",current_event_id:1}}}; try {c.reconcileEvidence(publication,summary);process.exit(61)} catch (_) {}})();
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_active_record_scientific_context_contract(self):
        program = r'''
global.document = { querySelector: () => null }; require(process.argv[1]); const c = global.ETROCReviewContract;
const counts = c.scientificCandidateCounts({
  optical_no_ball_candidate_count: 2,
  red_candidate_count: 3,
  needs_inspection_count: 5,
  review_candidate_count: 7,
});
if (JSON.stringify(counts) !== JSON.stringify([2, 3, 5, 7])) process.exit(62);
for (const broken of [{}, { optical_no_ball_candidate_count: -1, red_candidate_count: 0, needs_inspection_count: 0, review_candidate_count: 0 }, { optical_no_ball_candidate_count: 0, red_candidate_count: 0, needs_inspection_count: 0, review_candidate_count: 1.5 }]) {
  let rejected = false; try { c.scientificCandidateCounts(broken); } catch (_) { rejected = true; }
  if (!rejected) process.exit(63);
}
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_position_human_label_and_target_only_mode_contract(self):
        program = r'''
global.document={querySelector:()=>null}; require(process.argv[1]); const c=global.ETROCReviewContract;
if (JSON.stringify([...c.HUMAN_LABELS]) !== JSON.stringify(["GREEN","BLUE","YELLOW","RED"])) process.exit(110);
for (const label of c.HUMAN_LABELS) {
  const draft=c.validatePositionDraft({label,note:"",expected_current_event_id:null});
  if (draft.label !== label || draft.note !== "") process.exit(111);
}
for (const label of ["NEED_INSPECT","reviewed_no_optical_concern","",null]) {
  let rejected=false; try { c.validatePositionDraft({label,note:"",expected_current_event_id:null}); } catch (_) { rejected=true; }
  if (!rejected) process.exit(112);
}
if (c.positionOpenMode({review_target:true},null) !== "queue") process.exit(113);
if (c.positionOpenMode({review_target:true},{label:"RED"}) !== "correction") process.exit(114);
if (c.positionOpenMode({review_target:false},null) !== "inspection") process.exit(115);
'''
        result = self.node(program)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_workspace_markup_and_safe_dom_contract(self):
        html = INDEX.read_text(encoding="utf-8")
        workspace = html[html.index('<section id="etroc-review-workspace"'):html.index('<h2 class="etroc-legacy-boundary"')]
        script = SCRIPT.read_text(encoding="utf-8") if SCRIPT.exists() else ""
        for required in (
            'role="dialog"', 'aria-modal="true"', 'aria-labelledby="etroc-review-title"',
            'data-etroc-review-status', 'data-etroc-review-close',
            'data-etroc-position-section', 'data-etroc-position-mode="clean"', 'data-etroc-position-mode="analysis"',
            'data-etroc-position-algorithm-overlay', 'data-etroc-position-human-overlay',
            'data-etroc-position-progress', 'data-etroc-position-grid', 'role="grid"',
            'data-etroc-position-context', 'name="etroc-position-label"', 'data-etroc-position-note',
            'data-etroc-position-history', 'data-etroc-position-save', 'data-etroc-position-save-next', 'data-etroc-position-reapply',
        ):
            self.assertIn(required, workspace)
        for removed in (
            'name="etroc-review-state"', 'data-etroc-review-note', 'data-etroc-review-save',
            'data-etroc-review-save-next', 'Reviewed: no optical concern',
            'Reviewed: concern observed', 'Follow-up required', 'name="etroc-position-state"',
        ):
            self.assertNotIn(removed, workspace)
        for label in ("GREEN", "BLUE", "YELLOW", "RED"):
            self.assertIn(f'name="etroc-position-label" value="{label}"', workspace)
        self.assertIn('src="etroc-review.js', html)
        self.assertLess(html.index('src="etroc-review.js'), html.index('src="etroc-optical.js'))
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("eval(", script)
        self.assertNotIn("javascript:", script)
        self.assertIn('setAttribute("aria-labelledby", "etroc-review-discard-title")', script)
        self.assertIn('dialog:not([open])', script)
        self.assertIn('reapply.hidden = true', script)
        self.assertIn('state.conflict = conflict;', script)
        stale_guard = script.index('if (conflict.code !== "stale_current"')
        self.assertLess(script.index('state.conflict = conflict;', stale_guard), script.index('const summary = await fetchSummary();', stale_guard))
        self.assertIn('reapply.hidden = false;', script)
        self.assertIn('conflict.code === "evidence_changed"', script)
        self.assertIn('state.saveInFlight = false;', script)
        self.assertIn('conflict.code === "mutation_id_conflict"', script)
        self.assertIn('const reconciled = reconcileEvidence(state.publication, summary);', script)
        self.assertIn('const summary = await fetchSummary();', script)
        self.assertIn('nextQueueIndex(state.queue, state.summary.reviews, state.queueIndex)', script)
        self.assertIn('scientificCandidateCounts(record)', script)
        self.assertIn('original.href = montage.objectUrl', script)
        self.assertNotIn('original.href = `${DATA_BASE}${record.montage_uri}`', script)
        self.assertIn('inspectionControlsEnabled(true)', script)
        self.assertIn('Verified clean evidence. Select a NEED_INSPECT target or start the queue.', script)
        switch_start = script.index("async function switchPositionMontage")
        switch_end = script.index("const montage = new MontageController", switch_start)
        self.assertLess(script.index('state.position.cleanVerified = "";', switch_start, switch_end), script.index("await montage.load(record)", switch_start, switch_end))
        self.assertIn('summary.publication_sha256 !== expectedPublicationSha256', script)
        position_save = script.index("async function savePositionReview")
        position_reapply = script.index("function reapplyPositionConflict", position_save)
        self.assertIn('code: "post_save_successor"', script[position_save:position_reapply])
        self.assertLess(script.index('state.position.conflict = { code: "post_save_successor"', position_save, position_reapply), script.index("if (andNext", position_save, position_reapply))
        self.assertIn("positionReapply.hidden = false", script[position_save:position_reapply])
        for required in (
            'data-etroc-review-no-ball-count', 'data-etroc-review-red-count',
            'data-etroc-review-needs-inspection-count', 'data-etroc-review-candidate-count',
            'Algorithmic screening candidates are exploratory and not a confirmed QC disposition.',
        ):
            self.assertIn(required, script)
        self.assertNotIn("innerHTML", script)


if __name__ == "__main__":
    unittest.main()
