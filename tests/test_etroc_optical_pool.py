import hashlib
import json
import re
import subprocess
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from PIL import Image

from tools.build_etroc_optical_pool import (
    APPROVED_ETROC_SERIALS,
    atomic_replace_directory,
    build_pool,
    resolve_under,
    validate_summary_rows,
)


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hybrid-bbqc"
DATASET = APP / "data" / "etroc-optical" / "ETROC_OI_2608"
POOL = DATASET / "chips.json"
CHECKSUMS = DATASET / "SHA256SUMS"
INDEX = APP / "index.html"
SCRIPT = APP / "etroc-optical.js"
STYLE = APP / "etroc-optical.css"


class EtrocOpticalPoolTests(unittest.TestCase):
    @staticmethod
    def valid_summary_rows():
        rows = []
        for serial in sorted(APPROVED_ETROC_SERIALS):
            wafer, chip = serial.split("-", 1)
            lineage = "supplement-re" if serial in {"W02G4-51", "W05E5-24"} else "base"
            rows.append({
                "etroc_serial": serial, "wafer": wafer, "chip": chip,
                "acquisition_id": f"ETROC_OI_2608:{lineage}",
                "dataset_id": "ETROC_OI_2608_complete",
                "publication_status": "exploratory_review_pending",
                "position_count": "256", "image_count": "256", "height_count": "256",
                "etl_etroc_id": "", "hybrid_registry_id": "",
                "green_count": "256", "blue_count": "0", "yellow_count": "0",
                "red_count": "0", "need_inspect_count": "0",
                "review_candidate_count": "0", "optical_no_ball_count": "0",
                "montage_overlay_relpath": f"batches/{serial}/montage_overlay.png",
            })
        return rows

    def test_builder_rejects_unapproved_or_inconsistent_etroc_identity(self):
        rows = self.valid_summary_rows()
        self.assertEqual(set(validate_summary_rows(rows)), APPROVED_ETROC_SERIALS)
        malicious = [dict(row) for row in rows]
        malicious[0]["etroc_serial"] = "../../../escaped"
        with self.assertRaisesRegex(ValueError, "approved 36-serial allowlist"):
            validate_summary_rows(malicious)
        mismatched = [dict(row) for row in rows]
        mismatched[0]["chip"] = "999"
        with self.assertRaisesRegex(ValueError, "inconsistent ETROC identity"):
            validate_summary_rows(mismatched)
        wrong_lineage = [dict(row) for row in rows]
        wrong_lineage[0]["acquisition_id"] = "ETROC_OI_2608:supplement-re"
        with self.assertRaisesRegex(ValueError, "unexpected acquisition lineage"):
            validate_summary_rows(wrong_lineage)

    def test_atomic_directory_swap_restores_previous_bundle_on_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "dataset"
            staged = root / "staged"
            destination.mkdir()
            staged.mkdir()
            (destination / "sentinel").write_text("previous", encoding="utf-8")
            (staged / "new").write_text("candidate", encoding="utf-8")
            real_replace = __import__("os").replace
            calls = 0

            def fail_second_replace(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated publish failure")
                return real_replace(source, target)

            with mock.patch("tools.build_etroc_optical_pool.os.replace", side_effect=fail_second_replace):
                with self.assertRaisesRegex(OSError, "simulated publish failure"):
                    atomic_replace_directory(staged, destination)
            self.assertEqual((destination / "sentinel").read_text(encoding="utf-8"), "previous")
            self.assertFalse((destination / "new").exists())

    def test_builder_rejects_absolute_and_traversing_source_paths(self):
        root = Path("/safe/analysis")
        self.assertEqual(resolve_under(root, "batches/chip/montage.png"), root / "batches/chip/montage.png")
        for unsafe in ("/etc/passwd", "../outside.png", "batches/../../outside.png"):
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(ValueError):
                    resolve_under(root, unsafe)

    def test_builder_rejects_mismatched_complete_manifest_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            analysis = root / "analysis"
            analysis.mkdir()
            (analysis / "bbqc_chip_summary_exploratory.csv").write_text("etroc_serial\n", encoding="utf-8")
            (analysis / "provenance.json").write_text(
                json.dumps({"source_complete_manifest_sha256": "0" * 64}),
                encoding="utf-8",
            )
            manifest = root / "complete_manifest.json"
            manifest.write_text("{}\n", encoding="utf-8")
            app = root / "app"
            with self.assertRaisesRegex(ValueError, "checksum does not match"):
                build_pool(analysis, app, manifest)
            self.assertFalse(app.exists())

    def load_pool(self):
        return json.loads(POOL.read_text(encoding="utf-8"))

    def test_pool_has_exact_complete_unbonded_etroc_inventory(self):
        payload = self.load_pool()
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["dataset_id"], "ETROC_OI_2608")
        self.assertEqual(payload["publication_status"], "exploratory_review_pending")
        records = payload["records"]
        self.assertEqual(len(records), 36)
        self.assertEqual(len({row["etroc_serial"] for row in records}), 36)
        self.assertEqual(Counter(row["wafer"] for row in records), {"W02G4": 18, "W03F7": 9, "W05E5": 9})
        self.assertTrue(all(row["image_count"] == 256 for row in records))
        self.assertTrue(all(row["height_count"] == 256 for row in records))
        self.assertTrue(all(row["review_state"] == "not_reviewed" for row in records))
        self.assertTrue(all("lgad" not in key.lower() and "hybrid" not in key.lower() for row in records for key in row))

    def test_pool_assets_are_relative_integrity_checked_web_files(self):
        payload = self.load_pool()
        for row in payload["records"]:
            for prefix in ("montage", "preview"):
                uri = row[f"{prefix}_uri"]
                self.assertFalse(uri.startswith("/"), uri)
                self.assertNotIn("/home/", uri)
                asset = DATASET / uri
                self.assertTrue(asset.is_file(), asset)
                self.assertEqual(hashlib.sha256(asset.read_bytes()).hexdigest(), row[f"{prefix}_sha256"])
                self.assertEqual(asset.stat().st_size, row[f"{prefix}_size_bytes"])
                self.assertEqual(asset.suffix.lower(), ".jpg")
                with Image.open(asset) as image:
                    image.verify()
                with Image.open(asset) as image:
                    self.assertEqual(image.format, "JPEG")
                    self.assertEqual(image.mode, "RGB")
                    self.assertEqual(image.info.get("progressive"), 1)
                    expected_size = (2400, 2176) if prefix == "montage" else (720, 653)
                    self.assertEqual(image.size, expected_size)

    def test_montage_uris_are_content_addressed_and_publish_only_digests(self):
        payload = self.load_pool()
        for row in payload["records"]:
            montage_uri = row["montage_uri"]
            self.assertTrue(montage_uri.startswith("montages/sha256/"), montage_uri)
            self.assertFalse(montage_uri.startswith("montages/" + row["etroc_serial"]), montage_uri)
            self.assertEqual(Path(montage_uri).name, f"{row['montage_sha256']}.jpg")
            montage = DATASET / montage_uri
            self.assertTrue(montage.is_file(), montage)
            self.assertEqual(hashlib.sha256(montage.read_bytes()).hexdigest(), row["montage_sha256"])

    def test_clean_montages_and_position_publications_are_exact_and_content_addressed(self):
        payload = self.load_pool()
        self.assertEqual(payload["position_geometry_version"], "etroc-grid-16x16-v1")
        self.assertEqual(payload["position_review_target_count"], 82)
        seen_positions = set()
        target_count = 0
        for record in payload["records"]:
            self.assertRegex(record["clean_montage_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(record["clean_montage_uri"], f"clean-montages/sha256/{record['clean_montage_sha256']}.jpg")
            clean = DATASET / record["clean_montage_uri"]
            self.assertTrue(clean.is_file(), clean)
            self.assertEqual(hashlib.sha256(clean.read_bytes()).hexdigest(), record["clean_montage_sha256"])
            self.assertEqual(clean.stat().st_size, record["clean_montage_size_bytes"])
            with Image.open(clean) as image:
                self.assertEqual(image.size, (2400, 2176))
                self.assertEqual(image.mode, "RGB")
                self.assertEqual(image.info.get("progressive"), 1)
            self.assertRegex(record["position_publication_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(record["position_publication_uri"], f"positions/sha256/{record['position_publication_sha256']}.json")
            position_file = DATASET / record["position_publication_uri"]
            self.assertTrue(position_file.is_file(), position_file)
            raw = position_file.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), record["position_publication_sha256"])
            document = json.loads(raw)
            self.assertEqual(document["schema_version"], "1.0")
            self.assertEqual(document["geometry_version"], "etroc-grid-16x16-v1")
            self.assertEqual(document["dataset_id"], "ETROC_OI_2608")
            self.assertEqual(document["etroc_serial"], record["etroc_serial"])
            self.assertEqual(document["acquisition_id"], record["acquisition_id"])
            self.assertEqual(document["analysis_run_id"], record["analysis_run_id"])
            self.assertEqual(document["labelled_montage_sha256"], record["montage_sha256"])
            self.assertEqual(document["clean_montage_sha256"], record["clean_montage_sha256"])
            self.assertEqual(len(document["positions"]), 256)
            self.assertEqual(document["review_target_count"], record["position_review_target_count"])
            for expected_position, position in enumerate(document["positions"]):
                self.assertEqual(position["position"], expected_position)
                self.assertEqual(position["row"], expected_position // 16)
                self.assertEqual(position["column"], expected_position % 16)
                self.assertRegex(position["source_image_sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(position["review_target"], position["algorithm_category"] == "NEED_INSPECT")
                self.assertEqual(position["cell"], {
                    "x": (expected_position % 16) * 150,
                    "y": (expected_position // 16) * 136,
                    "width": 150,
                    "height": 136,
                    "image_y": 16,
                    "image_height": 120,
                })
                key = (record["etroc_serial"], expected_position)
                self.assertNotIn(key, seen_positions)
                seen_positions.add(key)
                target_count += int(position["review_target"])
        self.assertEqual(len(seen_positions), 9216)
        self.assertEqual(target_count, 82)

    def test_clean_publication_preserves_existing_labelled_montage_bytes(self):
        payload = self.load_pool()
        expected = {
            row["etroc_serial"]: (row["montage_sha256"], hashlib.sha256((DATASET / row["montage_uri"]).read_bytes()).hexdigest())
            for row in payload["records"]
        }
        self.assertEqual(len(expected), 36)
        self.assertTrue(all(metadata == (metadata[0], metadata[0]) for metadata in expected.values()))
        self.assertTrue(all(row["clean_montage_sha256"] != row["montage_sha256"] for row in payload["records"]))

    def test_dataset_checksum_manifest_is_complete_and_exact(self):
        entries = {}
        for line in CHECKSUMS.read_text(encoding="utf-8").splitlines():
            digest, relative = line.split("  ", 1)
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            self.assertNotIn(relative, entries)
            entries[relative] = digest
        expected = {
            path.relative_to(DATASET).as_posix()
            for path in DATASET.rglob("*")
            if path.is_file() and path != CHECKSUMS
        }
        self.assertEqual(set(entries), expected)
        for relative, digest in entries.items():
            self.assertEqual(hashlib.sha256((DATASET / relative).read_bytes()).hexdigest(), digest)

    def test_pool_provenance_identity_and_web_size_budget(self):
        payload = self.load_pool()
        serialized = json.dumps(payload)
        self.assertNotIn("/home/", serialized)
        self.assertEqual(payload["base_archive_sha256"], "5eefc4b0d97a72fd11b1e6c6a44c515c9c5175e92df28fdde384ff06bbf0b2bc")
        self.assertEqual(payload["supplement_archive_sha256"], "68ba3593fc9f2e4fb43b69e58e755e2f41be30546e957bb6847ab236c6ec9ecc")
        self.assertEqual(payload["position_record_count"], 9216)
        self.assertRegex(payload["position_results_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(payload["encoder"], {"libjpeg": "6.2", "pillow": "12.2.0"})
        self.assertEqual(len(payload["pipeline_files_sha256"]), 8)
        records = payload["records"]
        self.assertEqual(len({row["acquisition_id"] for row in records}), 36)
        self.assertTrue(all(row["analysis_run_id"].startswith("ETROC_OI_2608:common-baseline-v0:") for row in records))
        self.assertTrue(all(len(row["source_montage_sha256"]) == 64 for row in records))
        asset_bytes = sum(path.stat().st_size for path in DATASET.rglob("*") if path.is_file())
        self.assertLess(asset_bytes, 180 * 1024 * 1024)

    def test_optical_tab_loads_pool_without_changing_hybrid_inventory(self):
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn('href="etroc-optical.css', html)
        self.assertIn('src="etroc-optical.js', html)
        self.assertIn('data-etroc-optical-pool', html)
        self.assertIn('data-etroc-optical-status', html)
        pairs = set(re.findall(r"hybrids/([A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+)\.html", html))
        self.assertEqual(len(pairs), 72)
        canonical_digest = hashlib.sha256(("\n".join(sorted(pairs)) + "\n").encode()).hexdigest()
        self.assertEqual(canonical_digest, "6586c3ab854f1f0f317e2b62608cd1f7d2a935e9e6f30c8d6627b16f10599a06")

    def test_browser_contract_rejects_malformed_scientific_payloads(self):
        program = r'''
global.document = {querySelector: () => null};
require(process.argv[1]);
const source = require(process.argv[2]);
const validate = global.ETROCOpticalContract.validate;
validate(structuredClone(source));
const mutations = [
  p => { p.records[0].red_candidate_count = -999; },
  p => { p.records[0].needs_inspection_count = "<b>bad</b>"; },
  p => { p.records[0].chip = "999"; },
  p => { p.records[0].preview_uri = "previews/W02G4-45.jpg"; },
  p => { p.position_record_count = 9215; },
  p => { p.analysis_config_sha256 = "bad"; },
  p => { p.analysis_created_at_utc = "not-a-timestamp"; },
  p => { delete p.records[0].analysis_run_id; },
  p => { p.records[0].analysis_run_id = "ETROC_OI_2608:common-baseline-v0:unknown"; },
  p => { p.records[0].analysis_batch = "pack1"; },
  p => { p.records[0].montage_sha256 = "not-a-hash"; },
  p => { p.records[0].preview_sha256 = "not-a-hash"; },
  p => { p.records[0].source_montage_sha256 = "not-a-hash"; },
  p => { p.records[0].montage_size_bytes = 0; },
  p => { p.records[0].preview_size_bytes = 1.5; },
  p => { p.records[0].source_montage_size_bytes = -1; },
  p => {
    const hash = p.pipeline_files_sha256["etroc_inspection/__init__.py"];
    delete p.pipeline_files_sha256["etroc_inspection/__init__.py"];
    p.pipeline_files_sha256["arbitrary.py"] = hash;
  },
  p => {
    p.records[0].source_revision = "supplement-re";
    p.records[0].acquisition_id = `ETROC_OI_2608:${p.records[0].etroc_serial}:supplement-re`;
  },
];
for (const mutate of mutations) {
  const payload = structuredClone(source);
  mutate(payload);
  let rejected = false;
  try { validate(payload); } catch (_) { rejected = true; }
  if (!rejected) process.exit(20);
}
'''
        result = subprocess.run(
            ["node", "-e", program, str(SCRIPT), str(POOL)],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_statistics_contract_reconciles_exact_dataset_and_wafer_totals(self):
        program = r'''
global.document = {querySelector: () => null};
require(process.argv[1]);
const source = require(process.argv[2]);
const contract = global.ETROCOpticalContract;
const records = contract.validate(structuredClone(source));
const all = contract.summarize(records);
const w02 = contract.summarize(contract.selectRecords(records, "W02G4", ""));
const one = contract.selectRecords(records, "W02G4", "w02g4-68");
const empty = contract.selectRecords(records, "W03F7", "does-not-exist");
const provenance = contract.summarizeProvenance(records);
const expectedAll = {
  recordCount: 36, positionCount: 9216,
  categoryTotals: {green:6512, blue:2035, yellow:570, redCandidate:17, needsInspection:82},
  reviewCandidateCount:669, noBallCandidateCount:3,
  redCandidateRecordCount:9, needsInspectionRecordCount:22, noBallCandidateRecordCount:3,
};
const expectedW02 = {
  recordCount: 18, positionCount: 4608,
  categoryTotals: {green:3216, blue:924, yellow:388, redCandidate:12, needsInspection:68},
  reviewCandidateCount:468, noBallCandidateCount:1,
  redCandidateRecordCount:5, needsInspectionRecordCount:16, noBallCandidateRecordCount:1,
};
if (JSON.stringify(all) !== JSON.stringify(expectedAll)) process.exit(31);
if (JSON.stringify(w02) !== JSON.stringify(expectedW02)) process.exit(32);
if (one.length !== 1 || one[0].etroc_serial !== "W02G4-68") process.exit(33);
if (empty.length !== 0) process.exit(34);
const expectedRuns = {
  runCount: 5,
  runs: [
    {analysisRunId:"ETROC_OI_2608:common-baseline-v0:pack1", recordCount:9},
    {analysisRunId:"ETROC_OI_2608:common-baseline-v0:pack1_original", recordCount:8},
    {analysisRunId:"ETROC_OI_2608:common-baseline-v0:pack2", recordCount:17},
    {analysisRunId:"ETROC_OI_2608:common-baseline-v0:re_chip24", recordCount:1},
    {analysisRunId:"ETROC_OI_2608:common-baseline-v0:re_chip51", recordCount:1},
  ],
};
if (JSON.stringify(provenance) !== JSON.stringify(expectedRuns)) process.exit(35);
'''
        result = subprocess.run(
            ["node", "-e", program, str(SCRIPT), str(POOL)],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_pool_renderer_is_safe_accessible_and_fail_visible(self):
        script = SCRIPT.read_text(encoding="utf-8")
        style = STYLE.read_text(encoding="utf-8")
        self.assertIn("/data/etroc-optical/ETROC_OI_2608/chips.json", script)
        self.assertIn("textContent", script)
        self.assertNotIn("innerHTML", script)
        self.assertIn("ETROC optical dataset unavailable", script)
        html = INDEX.read_text(encoding="utf-8")
        self.assertRegex(html, r'data-etroc-optical-status[^>]*role="status"[^>]*aria-live="polite"')
        self.assertIn('data-etroc-optical-pool aria-busy="true"', html)
        self.assertIn('root.setAttribute("aria-busy", "false")', script)
        self.assertIn("@media", style)
        self.assertIn("prefers-reduced-motion", style)


if __name__ == "__main__":
    unittest.main()
