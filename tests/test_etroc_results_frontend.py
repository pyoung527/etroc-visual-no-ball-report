import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_etroc_results import load_module, STATIC_ROOT, seed_reviews


class ResultFrontendTests(unittest.TestCase):
    def test_effective_results_contract_complete_pending_correction_and_malformed(self):
        module = load_module()
        evidence = module.load_evidence(STATIC_ROOT)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            db = path / "test-only.sqlite3"
            module.init_schema(db)
            pending = module.results_summary(db, evidence)
            seed_reviews(module, db, evidence)
            complete = module.results_summary(db, evidence)
            (path / "fixtures.json").write_text(json.dumps({"pending": pending, "complete": complete}))
            program = r'''
const assert = require('node:assert/strict'), fs = require('node:fs');
global.document = {querySelector: () => null};
require(process.argv[1] + '/etroc-optical.js');
require(process.argv[1] + '/etroc-results.js');
const c = global.ETROCResultsContract;
const publication = JSON.parse(fs.readFileSync(process.argv[1] + '/data/etroc-optical/ETROC_OI_2608/chips.json'));
const records = global.ETROCOpticalContract.validate(publication);
const {pending, complete} = JSON.parse(fs.readFileSync(process.argv[2]));
const p = c.reconcile(records, pending, pending.publication_sha256);
assert.equal(c.summarize(p).pending, 82);
const models = c.reconcile(records, complete, complete.publication_sha256);
const total = c.summarize(models);
assert.equal(models.length, 36); assert.equal(total.positions, 9216);
assert.equal(total.human, 82); assert.equal(total.algorithm, 9134);
assert.equal(total.pending, 0); assert.equal(total.noTargets, 14);
assert.equal(Object.values(total.categories).reduce((a,b)=>a+b), 9216);
assert.equal(c.select(models, {status:'all'}).length, 36);
assert.equal(c.select(models, {status:'pending'}).length, 0);
const model = models.find(m => m.target_count > 0);
const position = model.positions.find(p => p.source === 'human');
assert.equal(position.label, 'GREEN');
assert(!model.positions.some(p => p.label === 'NEED_INSPECT'));
const changed = structuredClone(complete);
changed.results[model.acquisition_id].human_labels[position.position].label = 'RED';
changed.results[model.acquisition_id].human_labels[position.position].current_event_id += 1000;
const updated = c.reconcile(records, changed, complete.publication_sha256);
assert.equal(c.summarize(updated).categories.RED, total.categories.RED + 1);
assert.equal(c.summarize(updated).categories.GREEN, total.categories.GREEN - 1);
assert(c.select(updated, {category:'RED'}).some(m => m.acquisition_id === model.acquisition_id));
const subset = c.select(updated, {wafer:'W02G4', serial:'67'});
assert.equal(subset.length, 1); assert.equal(c.summarize(subset).positions, 256);
for (const mutate of [
 x => {delete x.results[model.acquisition_id]},
 x => {x.reviewed_target_count--},
 x => {x.publication_sha256 = 'a'.repeat(64)},
 x => {x.results[model.acquisition_id].human_labels[position.position].label = 'NEED_INSPECT'},
 x => {x.results[model.acquisition_id].human_labels[position.position].current_event_id = 0},
 x => {x.results[model.acquisition_id].algorithm_labels.pop()},
 x => {x.results[model.acquisition_id].status = 'review_pending'},
 x => {x.results[model.acquisition_id].human_labels['0255'] = {label:'RED',current_event_id:7}},
 x => {x.results[model.acquisition_id].position_publication_sha256 = 'b'.repeat(64)},
 x => {x.results[model.acquisition_id].algorithm_labels[0] = 'WRONG'},
 x => {x.results[model.acquisition_id].human_labels = []},
]) { const invalid = structuredClone(complete); mutate(invalid); assert.throws(() => c.reconcile(records, invalid, complete.publication_sha256)); }
console.log('effective result contract verified: complete, pending, filters, correction, 11 malformed cases');
'''
            result = subprocess.run(["node", "-e", program, str(STATIC_ROOT), str(path / "fixtures.json")], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
