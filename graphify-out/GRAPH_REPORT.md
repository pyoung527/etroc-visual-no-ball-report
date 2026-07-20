# Graph Report - etroc-visual-no-ball-report-plan  (2026-07-20)

## Corpus Check
- 6 files · ~27,891,112 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 69 nodes · 129 edges · 6 communities detected
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]

## God Nodes (most connected - your core abstractions)
1. `Handler` - 9 edges
2. `main()` - 8 edges
3. `HybridTableParser` - 7 edges
4. `main()` - 6 edges
5. `esc()` - 6 edges
6. `update_detail_page()` - 6 edges
7. `parse_dashboard_rows()` - 5 edges
8. `update_index()` - 5 edges
9. `analyze_one()` - 5 edges
10. `update_evidence_section()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `parse_dashboard_rows()` --calls--> `HybridTableParser`  [EXTRACTED]
  import_new_nw_scans.py → import_new_nw_scans.py  _Bridges community 5 → community 2_

## Communities

### Community 0 - "Community 0"
Cohesion: 0.25
Nodes (7): Handler, identity(), json_response(), normalize_status(), normalize_target(), read_json(), SimpleHTTPRequestHandler

### Community 1 - "Community 1"
Cohesion: 0.34
Nodes (14): esc(), etroc_for_zip_name(), key_for_etroc(), main(), note_for_crops(), reason_after_mapping(), slug_name(), update_chip_page() (+6 more)

### Community 2 - "Community 2"
Cohesion: 0.32
Nodes (13): canonical_etroc(), clean_reason(), collect_scans(), DashboardRow, main(), parse_dashboard_rows(), replace_attr(), scan_block() (+5 more)

### Community 3 - "Community 3"
Cohesion: 0.42
Nodes (8): analyze_one(), grid_centers(), grid_scores(), main(), optical_labels(), overlay(), _peaks(), read_manifest()

### Community 4 - "Community 4"
Cohesion: 0.43
Nodes (6): api(), esc(), fmt(), loadComments(), loadMe(), renderComment()

### Community 5 - "Community 5"
Cohesion: 0.33
Nodes (2): HTMLParser, HybridTableParser

## Knowledge Gaps
- **Thin community `Community 5`** (6 nodes): `HTMLParser`, `HybridTableParser`, `.handle_data()`, `.handle_endtag()`, `.handle_starttag()`, `.__init__()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `HybridTableParser` connect `Community 5` to `Community 2`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Why does `parse_dashboard_rows()` connect `Community 2` to `Community 5`?**
  _High betweenness centrality (0.004) - this node is a cross-community bridge._