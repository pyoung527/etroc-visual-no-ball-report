import unittest

from apply_comment_concordance import (
    classify_comment,
    choose_latest,
    update_detail_html,
    update_index_html,
)


class CommentConcordanceTests(unittest.TestCase):
    def test_classifies_explicit_review_labels(self):
        self.assertEqual(classify_comment("Match(OI=X-ray=NW)")[0], "match")
        self.assertEqual(classify_comment("Mismatch (OI != X-ray = NW)")[0], "mismatch")
        self.assertEqual(
            classify_comment("NW scan not available. I2C scan doesn't work.")[0],
            "incomplete",
        )

    def test_classifies_explicit_post_bond_loss_as_mismatch(self):
        state, rule = classify_comment(
            "The solder ball (99) missed during the bump-bonding process"
        )
        self.assertEqual(state, "mismatch")
        self.assertEqual(rule, "post-bond-loss")

    def test_choose_latest_per_target(self):
        rows = [
            {"id": 1, "target": "hybrid:A__B", "updated_at": 10, "body": "Match"},
            {"id": 2, "target": "hybrid:A__B", "updated_at": 20, "body": "Mismatch"},
        ]
        self.assertEqual(choose_latest(rows)["hybrid:A__B"]["id"], 2)

    def test_updates_card_and_table_together(self):
        html = (
            '<a class="card ready" data-consistency="review-pending" '
            'data-text="A B Review ready Review pending evidence" '
            'href="hybrids/A__B.html"><span class="consistency pending">'
            'Review pending</span></a>'
            '<table id="hybrid-table"><tbody><tr data-consistency="review-pending" '
            'data-text="A B Review ready Review pending evidence" '
            "onclick=\"location.href='hybrids/A__B.html'\">"
            '<td>Review ready</td><td><span class="consistency pending">'
            'Review pending</span></td></tr></tbody></table>'
        )
        changed, stats = update_index_html(html, {"A__B": "match"})
        self.assertEqual(stats, {"cards": 1, "rows": 1})
        self.assertEqual(changed.count('data-consistency="match"'), 2)
        self.assertEqual(changed.count('class="consistency aligned">Match'), 2)
        self.assertNotIn("Review pending", changed)

    def test_detail_badge_is_inserted_then_updated_without_duplicate(self):
        html = (
            '<style>body{color:black}</style><body><section class="meta-grid">'
            '<div class="meta"><span>ETROC</span><strong>A</strong></div>'
            '<div class="meta"><span>LGAD</span><strong>B</strong></div>'
            '<div class="meta"><span>Optical no-ball</span><strong>0</strong></div>'
            '</section></body>'
        )
        inserted = update_detail_html(html, "match")
        self.assertEqual(inserted.count("<span>QC evidence concordance</span>"), 1)
        self.assertIn('class="consistency aligned">Match', inserted)
        updated = update_detail_html(inserted, "mismatch")
        self.assertEqual(updated.count("<span>QC evidence concordance</span>"), 1)
        self.assertIn('class="consistency mismatch">Mismatch', updated)
        self.assertNotIn('class="consistency aligned">Match', updated)


if __name__ == "__main__":
    unittest.main()
