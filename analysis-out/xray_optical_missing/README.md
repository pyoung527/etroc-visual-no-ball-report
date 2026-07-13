# X-ray vs Optical Missing Solder Ball Scan

Scope: 45 recently updated hybrids (`NW no` + `X-ray yes`).

Method: minimal PIL/numpy script (`analyze_xray_optical_missing.py`) compares each 16x16 X-ray dot grid against the corresponding optical montage tile labels.

Conservative filters:
- X-ray grid centers from 1D dark-dot projections.
- Weak X-ray dot = robust low local dot contrast (`weak_z >= 4`).
- Exclude outer border cells and row/column line artifacts.
- Candidate bump-bond missing = weak X-ray dot while optical label is not `RED`.

Main result:
- Confirmed missing-ball candidate: `W07D3-20`, position `99` (`row=6`, `col=3`, optical `YELLOW`). X-ray dot is nearly absent while optical shows a solder ball.
- Master reviewed the remaining auto/review candidates and confirmed they are **not** missing-ball defects; treat them as weak-contrast false positives, not dashboard failures.

Artifacts:
- `hybrid_summary.csv`: per-hybrid counts.
- `cell_scores.csv`: per-cell scores and flags.
- `candidate_contact_sheet.jpg`: X-ray crop vs optical tile for auto candidates.
- `overlays/`: X-ray overlays for hybrids with candidates.
