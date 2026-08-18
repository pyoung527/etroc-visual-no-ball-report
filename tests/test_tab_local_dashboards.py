from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hybrid-bbqc"
INDEX = APP / "index.html"
LGAD_SCRIPT = APP / "lgad-optical-stats.js"


class DashboardStructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[dict[str, Any]] = []
        self.dashboard_tabs: dict[str, str | None] = {}
        self.lgad_group_counts: Counter[str] = Counter()
        self.lgad_sensors: list[str] = []
        self._heading_group: str | None = None
        self._heading_text: list[str] = []

    @staticmethod
    def _classes(attributes: dict[str, str | None]) -> set[str]:
        return set((attributes.get("class") or "").split())

    def _current_tab(self) -> str | None:
        for entry in reversed(self.stack):
            if "tab" in entry["classes"]:
                return entry["id"] if isinstance(entry["id"], str) else None
        return None

    def _current_lgad_group(self) -> dict[str, Any] | None:
        for entry in reversed(self.stack):
            if "lgad-group" in entry["classes"]:
                return entry
        return None

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        classes = self._classes(attributes)
        node_id = attributes.get("id")
        if isinstance(node_id, str) and node_id.endswith("-analytics"):
            self.dashboard_tabs[node_id] = self._current_tab()
        if tag == "a" and "lgad-card" in classes:
            sensor = attributes.get("data-sensor")
            if isinstance(sensor, str):
                self.lgad_sensors.append(sensor)
                group = self._current_lgad_group()
                if group and isinstance(group.get("group_name"), str):
                    self.lgad_group_counts[group["group_name"]] += 1
        entry: dict[str, Any] = {
            "tag": tag,
            "id": node_id,
            "classes": classes,
            "group_name": None,
        }
        self.stack.append(entry)
        if tag in {"h2", "h3"} and self._current_lgad_group():
            self._heading_group = "pending"
            self._heading_text = []

    def handle_data(self, data: str) -> None:
        if self._heading_group:
            self._heading_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h2", "h3"} and self._heading_group:
            name = " ".join("".join(self._heading_text).split())
            group = self._current_lgad_group()
            if group and name:
                group["group_name"] = name
            self._heading_group = None
            self._heading_text = []
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break


class TabLocalDashboardTests(unittest.TestCase):
    def parse(self) -> tuple[str, DashboardStructureParser]:
        html = INDEX.read_text(encoding="utf-8")
        parser = DashboardStructureParser()
        parser.feed(html)
        return html, parser

    def test_each_scientific_dashboard_is_inside_its_matching_tab(self):
        _html, parser = self.parse()
        self.assertEqual(
            parser.dashboard_tabs,
            {
                "bbqc-analytics": "bbqc",
                "etroc-optical-analytics": "optical",
                "lgad-optical-analytics": "lgad-optical",
            },
        )

    def test_etroc_dashboard_has_monitor_regions_and_interpretation_boundary(self):
        html, _parser = self.parse()
        for required in (
            'id="etroc-optical-analytics"',
            'id="etroc-category-chart"',
            'id="etroc-wafer-chart"',
            'id="etroc-workload-chart"',
            'data-etroc-stats-table',
            'data-etroc-wafer-filter',
            'data-etroc-search',
            "Algorithmic screening only",
            "not a confirmed QC disposition",
        ):
            self.assertIn(required, html)

    def test_lgad_dashboard_uses_exact_inventory_and_availability_semantics(self):
        html, parser = self.parse()
        self.assertEqual(len(parser.lgad_sensors), 35)
        self.assertEqual(len(set(parser.lgad_sensors)), 35)
        self.assertEqual(parser.lgad_group_counts, {"HPK1": 8, "HPK3": 9, "LF1": 9, "LF2": 9})
        self.assertIn('src="lgad-optical-stats.js', html)
        self.assertTrue(LGAD_SCRIPT.is_file())
        for required in (
            "Evidence availability only",
            "not a QC disposition",
            'id="lgad-group-chart"',
            'data-lgad-analytics-state',
        ):
            self.assertIn(required, html)

    def test_lgad_statistics_contract_reconciles_and_rejects_bad_inventory(self):
        _html, parser = self.parse()
        items = [
            {"sensor": sensor, "group": sensor.split("/", 1)[0]}
            for sensor in parser.lgad_sensors
        ]
        program = r'''
global.document = {querySelector: () => null};
require(process.argv[1]);
const items = JSON.parse(process.argv[2]);
const summarize = global.LGADOpticalStatsContract.summarizeInventory;
const summary = summarize(structuredClone(items));
if (JSON.stringify(summary) !== JSON.stringify({
  sensorCount:35, tileCount:8960, panoramaCount:35, groupCount:4,
  groups:{HPK1:8, HPK3:9, LF1:9, LF2:9},
})) process.exit(41);
const invalid = [];
invalid.push(items.slice(0, -1));
const duplicate = structuredClone(items); duplicate[1].sensor = duplicate[0].sensor; invalid.push(duplicate);
const mismatch = structuredClone(items); mismatch[0].group = "LF1"; invalid.push(mismatch);
for (const candidate of invalid) {
  let rejected = false;
  try { summarize(candidate); } catch { rejected = true; }
  if (!rejected) process.exit(42);
}
'''
        result = subprocess.run(
            ["node", "-e", program, str(LGAD_SCRIPT), json.dumps(items)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_tab_local_change_preserves_canonical_hybrid_inventory(self):
        html, _parser = self.parse()
        pairs = set(re.findall(r"hybrids/([A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+)\.html", html))
        self.assertEqual(len(pairs), 72)
        digest = hashlib.sha256(("\n".join(sorted(pairs)) + "\n").encode()).hexdigest()
        self.assertEqual(digest, "6586c3ab854f1f0f317e2b62608cd1f7d2a935e9e6f30c8d6627b16f10599a06")

    def test_tab_and_etroc_table_controls_have_keyboard_screen_reader_semantics(self):
        html, _parser = self.parse()
        script = (APP / "etroc-optical.js").read_text(encoding="utf-8")
        self.assertIn('<html lang="en">', html)
        self.assertIn('<nav class="tabs" role="tablist"', html)
        for button_id, tab_id, selected in (
            ("tab-bbqc", "bbqc", "true"),
            ("tab-optical", "optical", "false"),
            ("tab-lgad-optical", "lgad-optical", "false"),
        ):
            self.assertRegex(
                html,
                rf'id="{button_id}"[^>]*role="tab"[^>]*aria-controls="{tab_id}"[^>]*aria-selected="{selected}"',
            )
            self.assertRegex(
                html,
                rf'<section id="{tab_id}"[^>]*role="tabpanel"[^>]*aria-labelledby="{button_id}"',
            )
        self.assertIn("e.key === 'ArrowRight'", html)
        self.assertIn("e.key === 'ArrowLeft'", html)
        self.assertIn('data-etroc-sort="etroc_serial"', html)
        self.assertIn("header.tabIndex = 0", script)
        self.assertIn('header.setAttribute("aria-sort", "none")', script)
        self.assertIn("event.key === \"Enter\" || event.key === \" \"", script)
        self.assertIn("ratioLabel(summary.categoryTotals[key], summary.positionCount)", script)

    def test_tab_dashboards_use_local_assets_and_existing_visibility_controller(self):
        html, _parser = self.parse()
        self.assertNotRegex(html, r"https?://[^\"']*(?:chart|d3|plotly)")
        self.assertIn("document.querySelectorAll('[data-tab]').forEach", html)
        self.assertIn(".tab.active,.view.active{display:block}", html.replace(" ", ""))


if __name__ == "__main__":
    unittest.main()
