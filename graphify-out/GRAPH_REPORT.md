# Graph Report - etroc-visual-no-ball-report-plan  (2026-07-13)

## Corpus Check
- 5 files · ~24,945,005 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 49 nodes · 93 edges · 9 communities detected
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]

## God Nodes (most connected - your core abstractions)
1. `Handler` - 9 edges
2. `main()` - 8 edges
3. `esc()` - 6 edges
4. `update_detail_page()` - 6 edges
5. `analyze_one()` - 5 edges
6. `update_evidence_section()` - 5 edges
7. `update_chip_page()` - 5 edges
8. `identity()` - 5 edges
9. `json_response()` - 5 edges
10. `main()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `xray_full_article()` --calls--> `esc()`  [EXTRACTED]
  update_second_batch_xray_mapping.py → update_second_batch_xray_mapping.py  _Bridges community 4 → community 5_
- `update_chip_page()` --calls--> `esc()`  [EXTRACTED]
  update_second_batch_xray_mapping.py → update_second_batch_xray_mapping.py  _Bridges community 4 → community 2_
- `main()` --calls--> `note_for_crops()`  [EXTRACTED]
  update_second_batch_xray_mapping.py → update_second_batch_xray_mapping.py  _Bridges community 5 → community 2_

## Communities

### Community 0 - "Community 0"
Cohesion: 0.42
Nodes (8): analyze_one(), grid_centers(), grid_scores(), main(), optical_labels(), overlay(), _peaks(), read_manifest()

### Community 1 - "Community 1"
Cohesion: 0.43
Nodes (6): api(), esc(), fmt(), loadComments(), loadMe(), renderComment()

### Community 2 - "Community 2"
Cohesion: 0.67
Nodes (5): etroc_for_zip_name(), key_for_etroc(), main(), slug_name(), update_chip_page()

### Community 3 - "Community 3"
Cohesion: 0.53
Nodes (3): identity(), json_response(), normalize_target()

### Community 4 - "Community 4"
Cohesion: 0.5
Nodes (5): esc(), reason_after_mapping(), update_detail_page(), update_index(), update_index_segment()

### Community 5 - "Community 5"
Cohesion: 0.5
Nodes (4): note_for_crops(), update_evidence_section(), xray_crop_article(), xray_full_article()

### Community 6 - "Community 6"
Cohesion: 0.5
Nodes (2): Handler, SimpleHTTPRequestHandler

### Community 7 - "Community 7"
Cohesion: 0.67
Nodes (1): read_json()

### Community 8 - "Community 8"
Cohesion: 0.67
Nodes (1): normalize_status()

## Knowledge Gaps
- **Thin community `Community 6`** (4 nodes): `Handler`, `.log_message()`, `.translate_path()`, `SimpleHTTPRequestHandler`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 7`** (3 nodes): `server.py`, `init_db()`, `read_json()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 8`** (3 nodes): `.do_PATCH()`, `.do_PUT()`, `normalize_status()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Handler` connect `Community 6` to `Community 8`, `Community 3`, `Community 7`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `main()` connect `Community 2` to `Community 4`, `Community 5`?**
  _High betweenness centrality (0.008) - this node is a cross-community bridge._
- **Why does `identity()` connect `Community 3` to `Community 8`, `Community 7`?**
  _High betweenness centrality (0.005) - this node is a cross-community bridge._