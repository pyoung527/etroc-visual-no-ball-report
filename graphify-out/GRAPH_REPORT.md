# Graph Report - etroc-visual-no-ball-report-plan  (2026-07-21)

## Corpus Check
- 8 files · ~27,893,251 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 90 nodes · 166 edges · 7 communities detected
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]

## God Nodes (most connected - your core abstractions)
1. `Handler` - 9 edges
2. `main()` - 8 edges
3. `HybridTableParser` - 7 edges
4. `main()` - 7 edges
5. `main()` - 6 edges
6. `esc()` - 6 edges
7. `update_detail_page()` - 6 edges
8. `CommentConcordanceTests` - 6 edges
9. `parse_dashboard_rows()` - 5 edges
10. `update_index()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `make_snapshot()` --calls--> `sha256()`  [INFERRED]
  apply_comment_concordance.py → import_new_nw_scans.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.2
Nodes (11): choose_latest(), classify_comment(), current_states(), main(), make_snapshot(), _replace_fragment(), _replace_one(), _revision_key() (+3 more)

### Community 1 - "Community 1"
Cohesion: 0.25
Nodes (7): Handler, identity(), json_response(), normalize_status(), normalize_target(), read_json(), SimpleHTTPRequestHandler

### Community 2 - "Community 2"
Cohesion: 0.34
Nodes (14): esc(), etroc_for_zip_name(), key_for_etroc(), main(), note_for_crops(), reason_after_mapping(), slug_name(), update_chip_page() (+6 more)

### Community 3 - "Community 3"
Cohesion: 0.32
Nodes (13): canonical_etroc(), clean_reason(), collect_scans(), DashboardRow, main(), parse_dashboard_rows(), replace_attr(), scan_block() (+5 more)

### Community 4 - "Community 4"
Cohesion: 0.22
Nodes (3): CardStateParser, HTMLParser, HybridTableParser

### Community 5 - "Community 5"
Cohesion: 0.42
Nodes (8): analyze_one(), grid_centers(), grid_scores(), main(), optical_labels(), overlay(), _peaks(), read_manifest()

### Community 6 - "Community 6"
Cohesion: 0.43
Nodes (6): api(), esc(), fmt(), loadComments(), loadMe(), renderComment()

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `make_snapshot()` connect `Community 0` to `Community 3`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `sha256()` connect `Community 3` to `Community 0`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `HybridTableParser` connect `Community 4` to `Community 3`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._