#!/usr/bin/env python3
"""Minimal BBQC X-ray vs optical montage comparison.

Ponytail version: no cv2/scipy. Uses PIL + numpy only.
Finds weak/missing X-ray grid dots and compares them to optical montage labels.
"""
from __future__ import annotations
import csv, re, math, html
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "analysis-out" / "xray_optical_missing"
GRID = 16


def read_manifest():
    idx = (ROOT / "hybrid-bbqc/index.html").read_text(errors="ignore")
    rows = []
    pat = re.compile(r'<a class="card[^>]*data-nw="([01])" data-xray="([01])"[^>]*data-yellow="(\d+)" data-noball="(\d+)" data-chip="(\d+)"[^>]*data-text="([^"]+)" href="([^"]+)".*?</a>', re.S)
    for m in pat.finditer(idx):
        nw, xray, yellow, noball, chip, text, href = m.groups()
        if not (nw == "0" and xray == "1"):
            continue
        et = re.search(r"W\d{2}[A-Z]\d-\d+", text).group(0)
        lg = re.search(r"(HPK|FBK)[A-Za-z0-9_\-./]+", text)
        imgs = re.findall(r'<img src="([^"]+)"', m.group(0))
        rows.append({
            "etroc": et, "lgad": lg.group(0) if lg else "", "chip": chip,
            "yellow_count": int(yellow), "optical_noball_count": int(noball),
            "montage": imgs[0], "xray": imgs[1], "href": href,
        })
    return rows


def _peaks(proj, k=GRID, min_dist=45):
    p = proj.astype(float)
    p = np.convolve(p, np.ones(9) / 9, mode="same")
    cand = [(p[i], i) for i in range(25, len(p) - 25) if p[i] >= p[i-1] and p[i] >= p[i+1]]
    picked = []
    for _, i in sorted(cand, reverse=True):
        if all(abs(i - j) >= min_dist for j in picked):
            picked.append(i)
            if len(picked) == k:
                break
    return sorted(picked)


def grid_centers(gray: np.ndarray):
    # Dark solder dots dominate the 1D projection; this avoids connected-component edge drift.
    base = np.percentile(gray, 65)
    resp = np.maximum(0, base - gray)
    return _peaks(resp.sum(axis=0)), _peaks(resp.sum(axis=1))


def grid_scores(gray: np.ndarray, xs, ys):
    out = []
    h, w = gray.shape
    yy, xx = np.ogrid[-18:19, -18:19]
    center_mask = (xx * xx + yy * yy) <= 6 * 6
    ring_mask = ((xx * xx + yy * yy) >= 10 * 10) & ((xx * xx + yy * yy) <= 17 * 17)
    for r, y in enumerate(ys):
        for c, x in enumerate(xs):
            x, y = int(round(x)), int(round(y))
            x0, x1 = max(0, x - 18), min(w, x + 19)
            y0, y1 = max(0, y - 18), min(h, y + 19)
            patch = gray[y0:y1, x0:x1]
            cm = center_mask[:patch.shape[0], :patch.shape[1]]
            rm = ring_mask[:patch.shape[0], :patch.shape[1]]
            center = patch[cm]
            ring = patch[rm]
            center_mean = float(center.mean())
            center_min = float(center.min())
            ring_med = float(np.median(ring))
            # Dark dot => center much darker than local ring.
            dot_score = ring_med - center_mean
            out.append({"pos": r * GRID + c, "row": r, "col": c, "x": x, "y": y, "dist": 0.0, "area": int((center < ring_med - 12).sum()), "mean": center_mean, "min": center_min, "dot_score": float(dot_score)})
    scores = np.array([o["dot_score"] for o in out], dtype=float)
    med = float(np.median(scores)); mad = float(np.median(np.abs(scores - med))) or 1.0
    for o in out:
        o["weak_z"] = (med - o["dot_score"]) / mad
    return out


def optical_labels(montage_path: Path):
    im = np.asarray(Image.open(montage_path).convert("RGB"))
    h, w, _ = im.shape
    tw, th = w / GRID, h / GRID
    labs = []
    for r in range(GRID):
        for c in range(GRID):
            y0, y1 = int(r * th), int(r * th + min(14, th * 0.12))
            x0, x1 = int(c * tw), int((c + 1) * tw)
            strip = im[y0:y1, x0:x1]
            rgb = strip.reshape(-1, 3).mean(axis=0)
            R, G, B = rgb
            if R > 160 and G < 120 and B < 120:
                lab = "RED"
            elif R > 150 and G > 120 and B < 80:
                lab = "YELLOW"
            elif G > R and G > B:
                lab = "GREEN"
            else:
                lab = "BLUE"
            labs.append(lab)
    return labs


def analyze_one(item):
    xray_path = ROOT / item["xray"].lstrip("/")
    montage_path = ROOT / item["montage"].lstrip("/")
    gray = np.asarray(Image.open(xray_path).convert("L"))
    xs, ys = grid_centers(gray)
    if len(xs) != GRID or len(ys) != GRID:
        raise RuntimeError(f"grid center detection failed for {item['etroc']}: xs={len(xs)} ys={len(ys)}")
    cells = grid_scores(gray, xs, ys)
    labels = optical_labels(montage_path)
    for cell, lab in zip(cells, labels):
        cell.update(item)
        cell["optical_label"] = lab
        cell["raw_xray_weak"] = cell["weak_z"] >= 4.0
    row_counts = {r: sum(c["raw_xray_weak"] for c in cells if c["row"] == r) for r in range(GRID)}
    col_counts = {c: sum(x["raw_xray_weak"] for x in cells if x["col"] == c) for c in range(GRID)}
    for cell in cells:
        cell["edge_cell"] = cell["row"] in (0, GRID - 1) or cell["col"] in (0, GRID - 1)
        cell["line_artifact"] = row_counts[cell["row"]] >= 5 or col_counts[cell["col"]] >= 5
        cell["xray_missing_candidate"] = bool(cell["raw_xray_weak"] and not cell["edge_cell"] and not cell["line_artifact"])
        cell["bumpbond_missing_candidate"] = cell["xray_missing_candidate"] and cell["optical_label"] != "RED"
    return cells, xs, ys


def overlay(item, cells, xs, ys):
    im = Image.open(ROOT / item["xray"].lstrip("/")).convert("RGB")
    draw = ImageDraw.Draw(im)
    for c in cells:
        if c["xray_missing_candidate"]:
            color = (255, 0, 0) if c["optical_label"] != "RED" else (255, 180, 0)
            x, y = c["x"], c["y"]
            draw.rectangle([x-13, y-13, x+13, y+13], outline=color, width=3)
            draw.text((x+15, y-10), str(c["pos"]), fill=color)
    out = OUT / "overlays" / f"{item['etroc']}__xray_candidates.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=90)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    items = read_manifest()
    allrows = []
    overlays = []
    for item in items:
        cells, xs, ys = analyze_one(item)
        allrows.extend(cells)
        if any(c["xray_missing_candidate"] for c in cells):
            overlays.append(str(overlay(item, cells, xs, ys)))
    csv_path = OUT / "cell_scores.csv"
    fields = ["etroc","lgad","chip","href","montage","xray","pos","row","col","x","y","optical_label","area","mean","min","dist","dot_score","weak_z","raw_xray_weak","edge_cell","line_artifact","xray_missing_candidate","bumpbond_missing_candidate","yellow_count","optical_noball_count"]
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(allrows)
    summary_path = OUT / "hybrid_summary.csv"
    sums = []
    for item in items:
        rows = [r for r in allrows if r["etroc"] == item["etroc"]]
        miss = [r for r in rows if r["xray_missing_candidate"]]
        bump = [r for r in rows if r["bumpbond_missing_candidate"]]
        sums.append({**item, "xray_missing_cells": len(miss), "bumpbond_missing_cells": len(bump), "bumpbond_positions": ";".join(str(r["pos"]) for r in bump), "xray_missing_positions": ";".join(str(r["pos"]) for r in miss), "min_dot_score": round(min(r["dot_score"] for r in rows), 3), "max_weak_z": round(max(r["weak_z"] for r in rows), 3)})
    with summary_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sums[0].keys()))
        w.writeheader(); w.writerows(sums)
    print("items", len(items), "cells", len(allrows))
    print("summary", summary_path)
    print("cell_scores", csv_path)
    print("overlays", len(overlays))
    for s in sorted(sums, key=lambda x: (-x["bumpbond_missing_cells"], -x["xray_missing_cells"], -x["max_weak_z"]))[:20]:
        print(s["etroc"], "bump", s["bumpbond_missing_cells"], s["bumpbond_positions"], "xray", s["xray_missing_cells"], s["xray_missing_positions"], "max_z", s["max_weak_z"], "optical_noball", s["optical_noball_count"])

if __name__ == "__main__":
    main()
