"""Behavioral regressions for the post-review save/readback UI boundary."""
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hybrid-bbqc"


@pytest.mark.parametrize("scenario", ["normal", "successor", "blue_successor", "bad_chain", "bad_history_key", "bad_history_event", "bad_current_history", "exact_wrong_label", "bad_event_id", "stale_current", "invalid_summary", "invalid_history", "invalid_envelope", "invalid_current", "stale_invalid_summary", "stale_missing_current", "mutation_id_conflict", "evidence_changed"])
def test_actual_position_save_refreshes_only_validated_readback(scenario):
    program = r'''
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
global.document = {querySelector: () => null}; require(process.argv[1]);
const c = global.ETROCReviewContract, scenario = process.argv[2];
const source = fs.readFileSync(process.argv[1], 'utf8');
const actual = source.slice(source.indexOf('  async function savePositionReview('), source.indexOf('  function reapplyPositionConflict('));
const active = Object.fromEntries(c.POSITION_KEY_FIELDS.map(k => [k, k]));
active.position = 127; active.review_target = true;
const draft = {label:'RED', note:'retained correction', expected_current_event_id:1};
const successor = ['successor','blue_successor','bad_chain','bad_history_key','bad_history_event','bad_current_history'].includes(scenario);
const saved = {...active, ...draft, event_id:2, mutation_id:'stable-mutation', supersedes_event_id:1};
const current = {...saved, label:successor && scenario !== 'successor' || scenario === 'exact_wrong_label' ? 'BLUE' : 'RED', current_event_id:successor ? 3 : 2};
const items = successor ? [{...current,event_id:3,supersedes_event_id:2}, {...saved}] : [{...saved}];
if (scenario === 'bad_chain') items[0].supersedes_event_id = 1;
if (scenario === 'bad_history_key') items[0].position = 126;
if (scenario === 'bad_history_event') items.at(-1).note = 'not the draft';
if (scenario === 'bad_current_history') items[0].label = 'YELLOW';
if (scenario === 'invalid_current') current.position = 126;
const summary = {reviews:{127:current}, target_count:1, reviewed_target_count:1, completion_status:'review_complete', viewer:{can_append_review:true}};
if (scenario === 'stale_missing_current') summary.reviews = {};
const conflict = scenario.startsWith('stale_') || ['mutation_id_conflict','evidence_changed'].includes(scenario);
let events = [], synced = 0, posted = [], validated = false, historyValidated = false;
const state = {active:{acquisition_id:'a',etroc_serial:'s'}, publication:{publicationSha256:'digest'}, completion:new Map(), position:{active, parsed:{}, mutation:null, mode:'single', montageMode:'clean', loadedFingerprint:'original'}};
const context = {state, POSITION_KEY_FIELDS:c.POSITION_KEY_FIELDS, crypto:{randomUUID:()=> 'stable-mutation'},
 positionCanSave:()=>true, positionDraft:()=>draft, validatePositionDraft:c.validatePositionDraft,
 fingerprint:JSON.stringify, draftMutation:c.draftMutation, positionControlsEnabled:()=>{},
 fetch:async (_, options)=>{const payload=JSON.parse(options.body); posted.push(payload);return {status:conflict?409:200,ok:!conflict,json:async()=>conflict?{error:{code:scenario.startsWith('stale_')?'stale_current':scenario,current}}:{ok:true,idempotent_replay:posted.length>1,event:{...payload,event_id:scenario==='bad_event_id'?'2':2,supersedes_event_id:1,label:scenario==='invalid_envelope'?'BLUE':payload.label}}}},
 fetchPositionSummary:async()=>summary,
 reconcilePositionEvidence:()=>{if(scenario==='invalid_summary'||scenario==='stale_invalid_summary')throw Error('invalid evidence');validated=true;return new Map()},
 fetchPositionHistory:async()=>{historyValidated=true;return {history:scenario==='invalid_history'?[]:items}},
 positionReapply:{hidden:true}, renderPositionGrid:()=>{}, updatePositionProgress:()=>{}, updateReviewSurface:()=>{},
 setPositionHistory:()=>{}, setStatus:(message)=>{context.status=message}, syncPositionDraft:()=>{synced++},
 CustomEvent:class {constructor(type){this.type=type}}, dispatchEvent:event=>{assert(validated);if(!conflict)assert(historyValidated);events.push(event.type)}
};
vm.createContext(context);vm.runInContext(actual+';globalThis.save = savePositionReview;',context);
(async()=>{
 await context.save(false);
 const shouldRefresh = ['normal','successor','blue_successor','stale_current'].includes(scenario);
 assert.deepEqual(events,shouldRefresh?['etroc-position-review-updated']:[],scenario+' refresh');
 assert.equal(synced,scenario==='normal'?1:0,'conflicts/errors must preserve dirty draft');
 assert.equal(state.position.loadedFingerprint,'original');
 assert.equal(state.position.saveInFlight,false);
 if(['successor','blue_successor','stale_current'].includes(scenario)) {assert.equal(state.position.conflict.code,successor?'post_save_successor':scenario);assert.equal(context.positionReapply.hidden,false)}
 const id=state.position.mutation.id;
 await context.save(false);
 assert.equal(events.length,shouldRefresh?2:0,'idempotent replay refresh');
 assert.equal(synced,scenario==='normal'?2:0,'idempotent replay retains conflicting draft');
 if(scenario==='blue_successor') {assert.equal(state.position.conflict.code,'post_save_successor');assert.equal(context.positionReapply.hidden,false)}
 assert.equal(state.position.mutation.id,id,'retry keeps mutation id');
 assert.equal(posted[1].expected_current_event_id,1,'optimistic predecessor retained');
 assert.equal(posted[1].note,draft.note);
})().catch(error=>{console.error(error);process.exitCode=1});
'''
    result = subprocess.run(["node", "-e", program, str(APP / "etroc-review.js"), scenario], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_result_style_selectors_and_pending_copy_match_runtime():
    # Keep the stylesheet contract attached to actual rendered classes, not a
    # parallel mock renderer. Browser computed styles are checked during QA.
    program = r'''
const assert=require('node:assert/strict'),fs=require('node:fs');
const nodes=[];
class Element {constructor(tag){this.tag=tag;this.dataset={};this.children=[];this.classList={add:()=>{}};nodes.push(this)}append(...x){this.children.push(...x)}setAttribute(){}addEventListener(){}}
global.document={querySelector:()=>null,createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)};
require(process.argv[1]+'/etroc-results.js');
ETROCResultsContract.renderCard({etroc_serial:'test',acquisition_id:'test',positions:[],categories:{GREEN:0,BLUE:0,YELLOW:0,RED:0,PENDING:0},reviewed_target_count:0,target_count:0});
const css=fs.readFileSync(process.argv[1]+'/etroc-optical.css','utf8');
for(const label of ['green','blue','yellow','red','pending']){assert(nodes.some(n=>n.className==='etroc-result-category '+label));assert(css.includes('.etroc-result-category.'+label))}
assert(nodes.some(n=>n.className==='etroc-result-categories'));assert(css.includes('.etroc-result-categories { display: flex;'));
const index=fs.readFileSync(process.argv[1]+'/index.html','utf8');assert.match(index,/<section class="[^"]*\betroc-results\b[^"]*" data-etroc-results/);
const script=fs.readFileSync(process.argv[1]+'/etroc-results.js','utf8');assert(script.includes('Pending review positions'));assert(!/Missing target labels|missing labels|\} missing/.test(script));
assert(nodes.some(n=>n.textContent==='0 human · 0 algorithm · 0 unreviewed'));
assert(script.includes('${totals.pending} unreviewed'));
'''
    result = subprocess.run(["node", "-e", program, str(APP)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
