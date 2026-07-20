#!/usr/bin/env python3
"""Import PNG-only NW scan histories into the ETL Hybrid BBQC dashboard.

The importer preserves every complete 2D-map + 1D-histogram timestamp pair,
selects the newest timestamp as primary, updates evidence availability, and
marks newly complete concordance as Review pending rather than inferring
Match/Mismatch from plot images alone.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


@dataclass(frozen=True)
class DashboardRow:
    qc: str
    concordance: str
    etroc: str
    lgad: str
    batch: str
    optical_no_ball: str
    yellow: str
    xray: str
    nw: str
    status: str


class HybridTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.section = ""
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.headers: list[str] = []
        self.rows: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "hybrid-table":
            self.in_table = True
        elif self.in_table and tag in ("thead", "tbody"):
            self.section = tag
        elif self.in_table and tag == "tr":
            self.row = []
        elif self.in_table and tag in ("th", "td") and self.row is not None:
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.in_table and self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.in_table:
            return
        if tag in ("th", "td") and self.cell is not None:
            assert self.row is not None
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.section == "thead" and not self.headers:
                self.headers = self.row
            elif self.section == "tbody":
                self.rows.append(dict(zip(self.headers, self.row)))
            self.row = None
        elif tag in ("thead", "tbody"):
            self.section = ""
        elif tag == "table":
            self.in_table = False


def canonical_etroc(folder_name: str) -> str | None:
    match = re.fullmatch(r"W0?7_(\d+)", folder_name)
    if match:
        return f"W07D3-{int(match.group(1))}"
    match = re.fullmatch(r"W0?4_(\d+)", folder_name)
    if match:
        return f"W04F2-{int(match.group(1))}"
    return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_scans(source: Path) -> dict[str, list[dict[str, object]]]:
    grouped: dict[tuple[str, str], dict[str, Path]] = defaultdict(dict)
    pattern = re.compile(
        r"BL_NW_(2D_map|1D_hist)_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.png$"
    )
    for path in sorted(source.rglob("*.png")):
        etroc = canonical_etroc(path.parent.name)
        match = pattern.search(path.name)
        if etroc and match:
            grouped[(etroc, match.group(2))][match.group(1)] = path

    incomplete = [key for key, value in grouped.items() if set(value) != {"2D_map", "1D_hist"}]
    if incomplete:
        raise RuntimeError(f"Incomplete NW timestamp pairs: {incomplete[:10]}")

    scans: dict[str, list[dict[str, object]]] = defaultdict(list)
    for (etroc, scan_id), value in grouped.items():
        map_path = value["2D_map"]
        hist_path = value["1D_hist"]
        scans[etroc].append(
            {
                "scan_id": scan_id,
                "map_source": map_path,
                "hist_source": hist_path,
            }
        )
    for values in scans.values():
        values.sort(key=lambda item: str(item["scan_id"]), reverse=True)
    return dict(scans)


def parse_dashboard_rows(index_html: str) -> dict[str, DashboardRow]:
    parser = HybridTableParser()
    parser.feed(index_html)
    result: dict[str, DashboardRow] = {}
    for row in parser.rows:
        item = DashboardRow(
            qc=row["QC result"],
            concordance=row["QC evidence concordance"],
            etroc=row["ETROC"],
            lgad=row["LGAD"],
            batch=row["Batch"],
            optical_no_ball=row["Optical no-ball"],
            yellow=row["Yellow"],
            xray=row["X-ray"],
            nw=row["NW"],
            status=row["Status"],
        )
        result[item.etroc] = item
    return result


def clean_reason(reason: str, qc: str) -> str:
    if qc == "Review ready":
        return "optical / X-ray / NW evidence available"
    parts = [part.strip() for part in reason.split(";")]
    parts = [part for part in parts if part not in {"NW missing", "X-ray evidence available"}]
    return "; ".join(parts)


def scan_block(etroc: str, scans: list[dict[str, object]]) -> str:
    blocks: list[str] = []
    for index, scan in enumerate(scans):
        scan_id = str(scan["scan_id"])
        map_name = Path(str(scan["map_source"])).name
        hist_name = Path(str(scan["hist_source"])).name
        kind = "primary" if index == 0 else "secondary"
        title = "Primary scan" if index == 0 else "Previous scan"
        blocks.append(
            f'''          <section class="scan-block {kind}">
            <div class="scan-head"><h2>{title}</h2><span>{scan_id}</span></div>
            <div class="nw-large-grid">
              <figure><img src="/assets/nw_scans/{etroc}/{map_name}" alt="{etroc} BL/NW 2D map {scan_id}" /><figcaption>BL/NW 2D map — main NW review view</figcaption></figure>
              <figure><img src="/assets/nw_scans/{etroc}/{hist_name}" alt="{etroc} BL/NW 1D histogram {scan_id}" /><figcaption>BL/NW 1D histogram</figcaption></figure>
            </div>
          </section>'''
        )
    return '<article class="panel wide"><h2>NW scan result - large review view</h2>\n' + "\n".join(blocks) + "\n</article>"


def update_detail_page(path: Path, row: DashboardRow, scans: list[dict[str, object]]) -> None:
    content = path.read_text(errors="ignore")
    summary_match = re.search(
        r'<section class="summary ([^"]+)"><div><span>QC result</span><strong>(.*?)</strong></div>'
        r'<div><span>Reasons</span><strong>(.*?)</strong></div></section>',
        content,
        re.S,
    )
    if not summary_match:
        raise RuntimeError(f"Summary block not found: {path}")
    current_qc = html.unescape(re.sub(r"<.*?>", "", summary_match.group(2))).strip()
    current_reason = html.unescape(re.sub(r"<.*?>", "", summary_match.group(3))).strip()
    new_qc = "Review ready" if current_qc == "Missing evidence" else current_qc
    new_class = "ready" if new_qc == "Review ready" else "fail" if new_qc == "FAIL candidate" else summary_match.group(1)
    new_reason = clean_reason(current_reason, new_qc)
    replacement = (
        f'<section class="summary {new_class}"><div><span>QC result</span><strong>{html.escape(new_qc)}</strong></div>'
        f'<div><span>Reasons</span><strong>{html.escape(new_reason)}</strong></div></section>'
    )
    content = content[: summary_match.start()] + replacement + content[summary_match.end() :]

    primary = str(scans[0]["scan_id"])
    content, count = re.subn(
        r'(<span>NW source</span><strong>).*?(</strong>)',
        rf'\1{row.etroc} · {primary}\2',
        content,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError(f"NW source block not found: {path}")
    content, count = re.subn(
        r'<article class="panel wide"><h2>NW scan result - large review view</h2>.*?</article>',
        scan_block(row.etroc, scans),
        content,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError(f"NW evidence article not found: {path}")
    path.write_text(content)


def replace_attr(fragment: str, name: str, value: str) -> str:
    updated, count = re.subn(rf'\b{re.escape(name)}="[^"]*"', f'{name}="{html.escape(value, quote=True)}"', fragment, count=1)
    if count != 1:
        raise RuntimeError(f"Attribute {name} missing in fragment")
    return updated


def update_card(fragment: str, row: DashboardRow) -> str:
    new_qc = "Review ready" if row.qc == "Missing evidence" else row.qc
    new_reason = clean_reason(row.status, new_qc)
    new_class = "ready" if new_qc == "Review ready" else "fail"
    fragment = re.sub(r'<a class="card [^"]+"', f'<a class="card {new_class}"', fragment, count=1)
    fragment = replace_attr(fragment, "data-nw", "1")
    fragment = replace_attr(fragment, "data-missing", "0")
    fragment = replace_attr(fragment, "data-consistency", "review-pending")
    search_text = f"{row.etroc} {row.lgad} {row.batch} {new_qc} Review pending {new_reason}"
    fragment = replace_attr(fragment, "data-text", search_text)
    if row.qc == "Missing evidence":
        fragment = fragment.replace('<span class="pill missing">Missing evidence</span>', '<span class="pill ready">Review ready</span>', 1)
    fragment = fragment.replace('<span class="consistency incomplete">Incomplete</span>', '<span class="consistency pending">Review pending</span>', 1)
    fragment = fragment.replace('<span class="badge miss">No NW</span>', '<span class="badge blue">NW scan</span>', 1)
    matches = list(re.finditer(r'<div class="muted">(.*?)</div>', fragment, re.S))
    if len(matches) < 2:
        raise RuntimeError(f"Expected two muted blocks for {row.etroc}")
    target = matches[1]
    fragment = fragment[: target.start()] + f'<div class="muted">{html.escape(new_reason)}</div>' + fragment[target.end() :]
    return fragment


def update_table_row(fragment: str, row: DashboardRow) -> str:
    already_nw = 'data-nw="1"' in fragment
    new_qc = "Review ready" if row.qc == "Missing evidence" else row.qc
    new_reason = clean_reason(row.status, new_qc)
    fragment = replace_attr(fragment, "data-nw", "1")
    fragment = replace_attr(fragment, "data-missing", "0")
    fragment = replace_attr(fragment, "data-consistency", "review-pending")
    search_text = f"{row.etroc} {row.lgad} {row.batch} {new_qc} Review pending {new_reason}"
    fragment = replace_attr(fragment, "data-text", search_text)
    if row.qc == "Missing evidence":
        fragment = fragment.replace('<span class="pill missing">Missing evidence</span>', '<span class="pill ready">Review ready</span>', 1)
    fragment = fragment.replace('<span class="consistency incomplete">Incomplete</span>', '<span class="consistency pending">Review pending</span>', 1)
    # X-ray is yes for all targeted rows, so the only plain no cell is NW.
    if not already_nw:
        fragment, count = re.subn(r'<td>no</td>', '<td>yes</td>', fragment, count=1)
        if count != 1:
            raise RuntimeError(f"NW cell not found for {row.etroc}")
    fragment, count = re.subn(r'<td>([^<]*)</td>\s*</tr>$', f'<td>{html.escape(new_reason)}</td></tr>', fragment, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"Status cell not found for {row.etroc}")
    return fragment


def update_index(index_path: Path, rows: dict[str, DashboardRow], target: list[str]) -> None:
    content = index_path.read_text(errors="ignore")
    pending_css = '.consistency.pending{background:#fff3cd;color:#7a5b00}'
    if pending_css not in content:
        anchor = '.consistency.incomplete{background:#eeeeee;color:#6d756f}'
        if anchor not in content:
            raise RuntimeError("Consistency CSS anchor missing")
        content = content.replace(anchor, anchor + pending_css, 1)

    for etroc in target:
        row = rows[etroc]
        card_pattern = re.compile(r'<a class="card [^"]+"[^>]*data-text="[^"]*\b' + re.escape(etroc) + r'\b[^"]*"[^>]*>.*?</a>', re.S)
        match = card_pattern.search(content)
        if not match:
            raise RuntimeError(f"Card not found: {etroc}")
        content = content[: match.start()] + update_card(match.group(0), row) + content[match.end() :]

        row_pattern = re.compile(r'<tr[^>]*data-text="[^"]*\b' + re.escape(etroc) + r'\b[^"]*"[^>]*>.*?</tr>', re.S)
        match = row_pattern.search(content)
        if not match:
            raise RuntimeError(f"Table row not found: {etroc}")
        content = content[: match.start()] + update_table_row(match.group(0), row) + content[match.end() :]

    # Recompute summary metrics from the transformed table rather than preserving stale counts.
    transformed_rows = parse_dashboard_rows(content)
    nw_count = sum(item.nw.lower() == "yes" for item in transformed_rows.values())
    missing_count = sum(item.qc == "Missing evidence" for item in transformed_rows.values())
    content, n1 = re.subn(r'(<span>NW scan available</span><strong>)\d+(</strong>)', rf'\g<1>{nw_count}\2', content, count=1)
    content, n2 = re.subn(r'(<span>Missing evidence</span><strong>)\d+(</strong>)', rf'\g<1>{missing_count}\2', content, count=1)
    if n1 != 1 or n2 != 1:
        raise RuntimeError("Summary metric anchors missing")
    index_path.write_text(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = args.source.resolve()
    repo = args.repo.resolve()
    index_path = repo / "hybrid-bbqc" / "index.html"
    manifest_path = repo / "assets" / "nw_scans" / "nw_scan_manifest.json"
    rows = parse_dashboard_rows(index_path.read_text(errors="ignore"))
    scans = collect_scans(source)
    target = sorted(set(scans) & set(rows))
    unmapped = sorted(set(scans) - set(rows))
    if unmapped:
        raise RuntimeError(f"Source chips absent from dashboard: {unmapped}")
    if len(target) != 44:
        raise RuntimeError(f"Expected 44 source-mapped hybrids, got {len(target)}")
    missing_after = sorted(etroc for etroc, row in rows.items() if row.nw.lower() == "no" and etroc not in target)

    all_pairs = sum(len(scans[etroc]) for etroc in target)
    print(f"TARGET_HYBRIDS {len(target)}")
    print(f"SCAN_PAIRS {all_pairs}")
    print(f"MISSING_AFTER {missing_after}")
    for etroc in target:
        print(f"MAP {etroc} {rows[etroc].lgad} scans={len(scans[etroc])} primary={scans[etroc][0]['scan_id']}")
    if args.dry_run:
        return

    manifest = json.loads(manifest_path.read_text())
    provenance_files: list[dict[str, object]] = []
    for etroc in target:
        destination = repo / "assets" / "nw_scans" / etroc
        destination.mkdir(parents=True, exist_ok=True)
        manifest_scans: list[dict[str, str]] = []
        for scan in scans[etroc]:
            map_source = Path(str(scan["map_source"]))
            hist_source = Path(str(scan["hist_source"]))
            for source_path in (map_source, hist_source):
                target_path = destination / source_path.name
                shutil.copy2(source_path, target_path)
                provenance_files.append(
                    {
                        "path": str(source_path.relative_to(source)),
                        "size": source_path.stat().st_size,
                        "sha256": sha256(source_path),
                    }
                )
            manifest_scans.append(
                {
                    "scan_id": str(scan["scan_id"]),
                    "map_2d": f"assets/nw_scans/{etroc}/{map_source.name}",
                    "hist_1d": f"assets/nw_scans/{etroc}/{hist_source.name}",
                }
            )
        source_chip = re.sub(r"_BL_NW_.*$", "", Path(str(scans[etroc][0]["map_source"])).name)
        manifest[etroc] = {
            "source_chip": source_chip,
            "etroc": etroc,
            "lgad": rows[etroc].lgad,
            "primary_scan_id": str(scans[etroc][0]["scan_id"]),
            "scans": manifest_scans,
        }
        detail_path = repo / "hybrid-bbqc" / "hybrids" / f"{etroc}__{rows[etroc].lgad}.html"
        if not detail_path.is_file():
            raise RuntimeError(f"Mapped detail page missing for {etroc}: {detail_path}")
        update_detail_page(detail_path, rows[etroc], scans[etroc])

    manifest_path.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n")
    provenance = {
        "source_dataset": source.name,
        "nw_file_count": len(provenance_files),
        "total_bytes": sum(int(str(item["size"])) for item in provenance_files),
        "files": sorted(provenance_files, key=lambda item: str(item["path"])),
    }
    provenance_path = repo / "assets" / "nw_scans" / "source_manifest_2026-07-20.json"
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n")
    update_index(index_path, rows, target)
    print(f"COPIED_FILES {len(provenance_files)}")
    print(f"PROVENANCE {provenance_path}")


if __name__ == "__main__":
    main()
