import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OLD_SLUG = "W04F2-81__FBK_LF-W14_34"
NEW_SLUG = "W04F2-81__FBK_LF-W14_35"
CORRECT_EXISTING_SLUG = "W04F2-34__FBK_LF-W14_34"


class HybridPairCorrectionTests(unittest.TestCase):
    def test_manifest_preserves_w04f2_34_and_corrects_w04f2_81(self):
        manifest = json.loads(
            (ROOT / "assets" / "nw_scans" / "nw_scan_manifest.json").read_text()
        )

        self.assertEqual(manifest["W04F2-34"]["lgad"], "FBK_LF-W14_34")
        self.assertEqual(manifest["W04F2-81"]["lgad"], "FBK_LF-W14_35")

    def test_dashboard_uses_only_the_corrected_w04f2_81_slug(self):
        dashboard = (ROOT / "hybrid-bbqc" / "index.html").read_text()

        self.assertIn(CORRECT_EXISTING_SLUG, dashboard)
        self.assertIn(NEW_SLUG, dashboard)
        self.assertNotIn(OLD_SLUG, dashboard)

    def test_corrected_detail_page_keeps_an_old_url_redirect(self):
        detail_dir = ROOT / "hybrid-bbqc" / "hybrids"
        corrected = detail_dir / f"{NEW_SLUG}.html"
        redirect = detail_dir / f"{OLD_SLUG}.html"

        self.assertTrue(corrected.is_file())
        corrected_html = corrected.read_text()
        self.assertIn("Hybrid W04F2-81 + FBK_LF-W14_35", corrected_html)
        self.assertIn(f'data-comments-target="hybrid:{NEW_SLUG}"', corrected_html)

        self.assertTrue(redirect.is_file())
        redirect_html = redirect.read_text()
        self.assertIn(f"url={NEW_SLUG}.html", redirect_html)
        self.assertIn(f'rel="canonical" href="{NEW_SLUG}.html"', redirect_html)

    def test_concordance_snapshot_uses_the_corrected_comment_target(self):
        snapshot = json.loads(
            (ROOT / "hybrid-bbqc" / "data" / "comment_concordance_snapshot.json").read_text()
        )
        records = {row["target"]: row for row in snapshot["records"]}

        old_target = f"hybrid:{OLD_SLUG}"
        new_target = f"hybrid:{NEW_SLUG}"
        self.assertNotIn(old_target, records)
        self.assertEqual(records[new_target]["concordance"], "match")


if __name__ == "__main__":
    unittest.main()
