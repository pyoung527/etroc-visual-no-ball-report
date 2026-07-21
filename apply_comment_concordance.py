#!/usr/bin/env python3
"""Apply live reviewer-comment decisions to BBQC concordance surfaces.

The raw comments export is an ephemeral input. The committed provenance snapshot stores
only comment IDs/timestamps, derived labels, rule names, and SHA256 body hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

LABELS = {
    "match": ("Match", "aligned"),
    "mismatch": ("Mismatch", "mismatch"),
    "incomplete": ("Incomplete", "incomplete"),
}
VISIBLE_PATTERN = re.compile(r"\b(?:Review pending|Match|Mismatch|Incomplete)\b")
DETAIL_STYLE = """/* QC evidence concordance badge */
.consistency{display:inline-flex;border-radius:999px;padding:3px 8px;font-size:11px;font-weight:830;border:1px solid rgba(0,0,0,.08)}
.consistency.aligned{background:#e2f2e7;color:#104b3a}.consistency.mismatch{background:#ffe0d8;color:#d7301f}.consistency.incomplete{background:#eeeeee;color:#6d756f}
"""


def classify_comment(body: str) -> tuple[str, str]:
    text = " ".join((body or "").split()).lower()
    if text.startswith("mismatch"):
        return "mismatch", "explicit-mismatch"
    if text.startswith("match"):
        return "match", "explicit-match"
    if "nw scan not available" in text or "i2c scan doesn't work" in text:
        return "incomplete", "missing-nw"
    if (
        "missed during the bump-bonding process" in text
        or "lost during handling or the bump-bonding process" in text
    ):
        return "mismatch", "post-bond-loss"
    raise ValueError(f"unclassified reviewer comment: {body!r}")


def _revision_key(row: dict[str, Any]) -> tuple[int, int, int]:
    def integer(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    return integer(row.get("updated_at")), integer(row.get("created_at")), integer(row.get("id"))


def choose_latest(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        target = str(row.get("target") or "").strip()
        if not target:
            raise ValueError("comment row has no target")
        if target not in latest or _revision_key(row) > _revision_key(latest[target]):
            latest[target] = row
    return latest


def _replace_fragment(fragment: str, state: str) -> str:
    label, css_class = LABELS[state]
    fragment, attr_count = re.subn(
        r'data-consistency="[^"]+"', f'data-consistency="{state}"', fragment, count=1
    )
    if attr_count != 1:
        raise ValueError("concordance data attribute not found exactly once")

    def update_data_text(match: re.Match[str]) -> str:
        text = match.group(1)
        changed, count = VISIBLE_PATTERN.subn(label, text, count=1)
        if count != 1:
            raise ValueError(f"concordance text not found in data-text: {text}")
        return f'data-text="{changed}"'

    fragment, text_count = re.subn(r'data-text="([^"]*)"', update_data_text, fragment, count=1)
    if text_count != 1:
        raise ValueError("data-text attribute not found exactly once")
    fragment, badge_count = re.subn(
        r'<span class="consistency [^"]+">(?:Review pending|Match|Mismatch|Incomplete)</span>',
        f'<span class="consistency {css_class}">{label}</span>',
        fragment,
        count=1,
    )
    if badge_count != 1:
        raise ValueError("visible concordance badge not found exactly once")
    return fragment


def _replace_one(html: str, pattern: str, state: str, name: str) -> tuple[str, int]:
    match = re.search(pattern, html, re.S)
    if not match:
        raise ValueError(f"{name} fragment not found")
    changed = _replace_fragment(match.group(0), state)
    return html[: match.start()] + changed + html[match.end() :], 1


def update_index_html(html: str, expected: dict[str, str]) -> tuple[str, dict[str, int]]:
    stats = {"cards": 0, "rows": 0}
    for slug, state in expected.items():
        escaped = re.escape(slug)
        html, count = _replace_one(
            html,
            rf'<a class="card[^"]*"[^>]*href="hybrids/{escaped}\.html".*?</a>',
            state,
            f"card {slug}",
        )
        stats["cards"] += count
        html, count = _replace_one(
            html,
            rf'<tr[^>]*onclick="location\.href=\'hybrids/{escaped}\.html\'"[^>]*>.*?</tr>',
            state,
            f"table row {slug}",
        )
        stats["rows"] += count
    return html, stats


def update_detail_html(html: str, state: str) -> str:
    label, css_class = LABELS[state]
    badge = (
        '<div class="meta concordance-meta"><span>QC evidence concordance</span>'
        f'<strong><span class="consistency {css_class}">{label}</span></strong></div>'
    )
    pattern = re.compile(
        r'<div class="meta concordance-meta"><span>QC evidence concordance</span>.*?</div>',
        re.S,
    )
    if pattern.search(html):
        html = pattern.sub(badge, html, count=1)
    else:
        lgad = re.search(
            r'<div class="meta"><span>LGAD</span><strong>.*?</strong></div>', html, re.S
        )
        if not lgad:
            raise ValueError("LGAD metadata block not found")
        html = html[: lgad.end()] + badge + html[lgad.end() :]
    if "/* QC evidence concordance badge */" not in html:
        marker = "/* Mobile clipping guardrails */"
        if marker in html:
            html = html.replace(marker, DETAIL_STYLE + marker, 1)
        elif "</style>" in html:
            html = html.replace("</style>", DETAIL_STYLE + "</style>", 1)
        else:
            raise ValueError("detail style block not found")
    return html


class CardStateParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.states: dict[str, str | None] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag != "a" or "card" not in (values.get("class") or "").split():
            return
        match = re.search(r"hybrids/([^/]+)\.html$", values.get("href") or "")
        if match:
            self.states[match.group(1)] = values.get("data-consistency")


def current_states(html: str) -> dict[str, str | None]:
    parser = CardStateParser()
    parser.feed(html)
    return parser.states


def make_snapshot(latest: dict[str, dict[str, Any]]) -> dict[str, Any]:
    records = []
    for target, row in sorted(latest.items()):
        state, rule = classify_comment(str(row.get("body") or ""))
        body = " ".join(str(row.get("body") or "").split())
        records.append(
            {
                "target": target,
                "comment_id": row.get("id"),
                "updated_at": row.get("updated_at"),
                "concordance": state,
                "rule": rule,
                "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            }
        )
    return {
        "source": "live /data/comments.sqlite3 latest non-deleted comment per target",
        "raw_comment_bodies_committed": False,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("comments_json", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = json.loads(args.comments_json.read_text())
    if not isinstance(rows, list):
        raise ValueError("comments JSON must contain a list")
    latest = choose_latest(rows)
    expected: dict[str, str] = {}
    for target, row in latest.items():
        if not target.startswith("hybrid:"):
            raise ValueError(f"unexpected comment target: {target}")
        slug = target.removeprefix("hybrid:")
        expected[slug] = classify_comment(str(row.get("body") or ""))[0]

    site = args.root / "hybrid-bbqc"
    index_path = site / "index.html"
    index_before = index_path.read_text()
    before = current_states(index_before)
    missing = sorted(set(expected) - set(before))
    extra = sorted(set(before) - set(expected))
    if missing or extra:
        raise ValueError(f"target/page mismatch: missing={missing} extra={extra}")
    diffs = sorted((slug, before[slug], state) for slug, state in expected.items() if before[slug] != state)
    index_after, stats = update_index_html(index_before, expected)
    if stats != {"cards": len(expected), "rows": len(expected)}:
        raise ValueError(f"incomplete index update: {stats}")

    detail_changes = 0
    detail_outputs: list[tuple[Path, str]] = []
    for slug, state in sorted(expected.items()):
        path = site / "hybrids" / f"{slug}.html"
        before_detail = path.read_text()
        after_detail = update_detail_html(before_detail, state)
        detail_outputs.append((path, after_detail))
        detail_changes += before_detail != after_detail

    snapshot = make_snapshot(latest)
    counts = Counter(expected.values())
    print("COMMENTS", len(rows), "UNIQUE_TARGETS", len(latest))
    print("EXPECTED_COUNTS", dict(sorted(counts.items())))
    print("INDEX_DIFFS", len(diffs), "DETAIL_FILES_CHANGED", detail_changes)
    for slug, old, new in diffs:
        print("DIFF", slug, old, "->", new)
    if args.dry_run:
        return 0

    if index_before != index_after:
        index_path.write_text(index_after)
    for path, content in detail_outputs:
        if path.read_text() != content:
            path.write_text(content)
    snapshot_path = site / "data" / "comment_concordance_snapshot.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")
    print("APPLIED", index_path, "SNAPSHOT", snapshot_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
