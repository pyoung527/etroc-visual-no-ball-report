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
        self.assertIn('href="dashboard.css?v=5f9d7e3bab4a"', html)
        self.assertIn('src="dashboard.js?v=317e358631a8"', html)
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
            "additional-tests-chart",
        ):
            with self.subTest(chart_id=chart_id):
                self.assertIn(f'id="{chart_id}"', html)
        self.assertIn('aria-labelledby="bbqc-analytics-title"', html)
        self.assertIn("screening candidate", html.lower())
        self.assertIn("not direct proof of bump failure", html.lower())
        self.assertIn("test assignment only", html.lower())
        self.assertIn("not test completion or result", html.lower())

    def test_additional_tests_use_live_registry_api_and_safe_badges(self):
        script = JS.read_text(encoding="utf-8")
        css = CSS.read_text(encoding="utf-8")
        self.assertIn("/api/hybrids", script)
        self.assertIn("additional_tests", script)
        self.assertIn("additional-test-badge", script)
        self.assertIn("source_hybrid_identifier", script)
        self.assertIn("label.textContent = `Assigned: ${test.display_name}`", script)
        self.assertIn("source.textContent = `Source identifier: ${test.source_hybrid_identifier}`", script)
        self.assertIn(".additional-test-badge", css)
        self.assertIn(".additional-tests-summary", css)
        self.assertIn("data-advanced-tests-heading", script)
        self.assertIn("data-advanced-tests-cell", script)
        self.assertIn("active memberships", script)
        self.assertIn("group.remove()", script)
        self.assertIn("data-additional-tests-card", script)
        self.assertIn("Additional test assignments", script)
        self.assertIn("liveSourceStatus.additionalTests = 'failed'", script)
        self.assertIn("unavailable.join(' + ')", script)
        self.assertNotIn("node.cells[3]", script)
        self.assertNotIn(": node.querySelector('.card-consistency')", script)
        html = INDEX.read_text(encoding="utf-8")
        additional_card = html[
            html.index('id="additional-tests-chart"') : html.index('id="review-chart"')
        ]
        self.assertIn('role="status" aria-live="polite"', additional_card)
        additional_block = script[
            script.index("async function loadAdditionalTests") : script.index(
                "async function loadReviewStatus"
            )
        ]
        self.assertNotIn("innerHTML", additional_block)

    def test_additional_test_failure_marks_table_cells_unavailable(self):
        script = JS.read_text(encoding="utf-8")
        failure_block = script.split("loadAdditionalTests().catch(() => {", 1)[1].split(
            "async function loadReviewStatus", 1
        )[0]
        self.assertIn("[data-advanced-tests-cell]", failure_block)
        self.assertIn("Advanced test data unavailable", failure_block)
        self.assertIn("cell.replaceChildren(unavailable)", failure_block)

    def test_table_filters_and_sorting_are_keyboard_and_screen_reader_accessible(self):
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn("const columnName=th.textContent.trim()", html)
        self.assertIn("setAttribute('aria-label',`Filter ${columnName}`)", html)
        self.assertIn("th.tabIndex=0", html)
        self.assertIn("th.setAttribute('aria-sort','none')", html)
        self.assertIn("th.addEventListener('keydown'", html)
        self.assertIn("e.key==='Enter'||e.key===' '", html)
        self.assertIn("'aria-sort',sortDir===1?'ascending':'descending'", html)

    def test_table_csv_export_contract(self):
        html = INDEX.read_text(encoding="utf-8")
        script = JS.read_text(encoding="utf-8")
        self.assertIn('data-export-table-csv', html)
        self.assertIn('Export visible rows as CSV', html)
        self.assertIn("table.tBodies[0].rows", script)
        self.assertIn("row.classList.contains('filter-hidden')", script)
        self.assertIn("row.classList.contains('column-filter-hidden')", script)
        self.assertIn("replaceAll('\"', '\"\"')", script)
        self.assertIn("/^[=+\\-@]/", script)
        self.assertIn("String.fromCharCode(0xFEFF)", script)
        self.assertIn("text/csv;charset=utf-8", script)
        self.assertIn("etl-hybrid-bbqc-table-", script)
        self.assertIn("URL.revokeObjectURL", script)

    def test_table_has_static_advanced_tests_column_for_every_hybrid(self):
        html = INDEX.read_text(encoding="utf-8")
        script = JS.read_text(encoding="utf-8")
        self.assertIn(
            '<th data-advanced-tests-heading>Advanced tests</th>',
            html,
        )
        self.assertEqual(html.count("data-advanced-tests-cell"), 72)
        self.assertEqual(html.count('class="additional-tests-empty">—</span>'), 72)
        self.assertIn("[data-advanced-tests-cell]", script)
        self.assertIn("No advanced test assignment", script)
        self.assertNotIn("row.append(cell)", script)

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
