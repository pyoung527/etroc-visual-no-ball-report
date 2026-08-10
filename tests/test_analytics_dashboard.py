import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "hybrid-bbqc" / "index.html"
CSS = ROOT / "hybrid-bbqc" / "dashboard.css"
JS = ROOT / "hybrid-bbqc" / "dashboard.js"


class AnalyticsDashboardTests(unittest.TestCase):
    def test_main_page_loads_local_dashboard_assets_and_places_dashboard_first(self):
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn('href="dashboard.css"', html)
        self.assertIn('src="dashboard.js"', html)
        dashboard_at = html.index('id="bbqc-analytics"')
        legacy_summary_at = html.index('class="summary-grid"')
        self.assertLess(dashboard_at, legacy_summary_at)
        self.assertNotRegex(html, r"https?://[^\"']*(?:chart|d3|plotly)")

    def test_dashboard_exposes_semantic_chart_regions_and_scientific_caveat(self):
        html = INDEX.read_text(encoding="utf-8")
        for chart_id in (
            "screening-chart",
            "evidence-chart",
            "concordance-chart",
            "wafer-chart",
            "review-chart",
        ):
            with self.subTest(chart_id=chart_id):
                self.assertIn(f'id="{chart_id}"', html)
        self.assertIn('aria-labelledby="bbqc-analytics-title"', html)
        self.assertIn("screening candidate", html.lower())
        self.assertIn("not direct proof of bump failure", html.lower())

    def test_dashboard_script_uses_existing_rows_and_live_comment_summary(self):
        script = JS.read_text(encoding="utf-8")
        self.assertIn("#hybrid-table tbody tr", script)
        self.assertIn("/api/comments/summary?", script)
        self.assertIn("requestAnimationFrame", script)
        self.assertIn("IntersectionObserver", script)
        self.assertRegex(script, r"latest\?\.status|latest\.status")
        self.assertNotRegex(script, r"https?://")

    def test_dashboard_styles_are_responsive_and_respect_reduced_motion(self):
        css = CSS.read_text(encoding="utf-8")
        self.assertIn("@media(max-width:700px)", css.replace(" ", ""))
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn(".analytics-dashboard", css)
        self.assertIn(".analytics-bar-fill", css)

    def test_dashboard_does_not_present_absence_of_optical_candidate_as_review_ready(self):
        script = JS.read_text(encoding="utf-8")
        self.assertIn("No optical no-ball candidate", script)
        screening_block = script[script.index("#screening-chart") : script.index("#evidence-chart")]
        self.assertNotIn("Review ready", screening_block)

    def test_dashboard_handles_untrusted_group_labels_and_pending_rows_safely(self):
        script = JS.read_text(encoding="utf-8")
        self.assertIn("consistency: row.dataset.consistency || 'review-pending'", script)
        self.assertIn("waferBody.replaceChildren", script)
        wafer_block = script[script.index("const waferMax") : script.index("function animateCounters")]
        self.assertNotIn("innerHTML", wafer_block)
        self.assertIn("textContent = name", wafer_block)

    def test_live_updates_are_announced_and_only_animate_the_reviewed_counter(self):
        html = INDEX.read_text(encoding="utf-8")
        script = JS.read_text(encoding="utf-8")
        self.assertIn('data-analytics-state role="status" aria-live="polite"', html)
        self.assertIn("const reviewedNode = setKpi('reviewed', reviewed)", script)
        self.assertIn("animateCounters(reviewedNode ? [reviewedNode] : [])", script)
        live_block = script[script.index("async function loadReviewStatus") :]
        self.assertNotIn("\n      animateCounters();", live_block)

    def test_dashboard_does_not_change_canonical_hybrid_inventory(self):
        html = INDEX.read_text(encoding="utf-8")
        pairs = set(re.findall(r"hybrids/([A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+)\.html", html))
        self.assertEqual(len(pairs), 72)
        self.assertIn("W04F2-81__FBK_LF-W14_35", pairs)
        self.assertNotIn("W04F2-81__FBK_LF-W14_34", pairs)


if __name__ == "__main__":
    unittest.main()
