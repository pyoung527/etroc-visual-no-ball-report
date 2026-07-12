# Graph Report - etroc-visual-no-ball-report-plan  (2026-07-12)

## Corpus Check
- 3 files · ~24,776,782 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 39 nodes · 78 edges · 8 communities detected
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

## God Nodes (most connected - your core abstractions)
1. `Handler` - 9 edges
2. `main()` - 8 edges
3. `esc()` - 6 edges
4. `update_detail_page()` - 6 edges
5. `update_evidence_section()` - 5 edges
6. `update_chip_page()` - 5 edges
7. `identity()` - 5 edges
8. `json_response()` - 5 edges
9. `key_for_etroc()` - 4 edges
10. `xray_crop_article()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `update_chip_page()` --calls--> `esc()`  [EXTRACTED]
  update_second_batch_xray_mapping.py → update_second_batch_xray_mapping.py  _Bridges community 1 → community 3_
- `update_index_segment()` --calls--> `esc()`  [EXTRACTED]
  update_second_batch_xray_mapping.py → update_second_batch_xray_mapping.py  _Bridges community 1 → community 4_
- `main()` --calls--> `update_index()`  [EXTRACTED]
  update_second_batch_xray_mapping.py → update_second_batch_xray_mapping.py  _Bridges community 4 → community 3_

## Communities

### Community 0 - "Community 0"
Cohesion: 0.43
Nodes (6): api(), esc(), fmt(), loadComments(), loadMe(), renderComment()

### Community 1 - "Community 1"
Cohesion: 0.47
Nodes (6): esc(), note_for_crops(), update_detail_page(), update_evidence_section(), xray_crop_article(), xray_full_article()

### Community 2 - "Community 2"
Cohesion: 0.53
Nodes (3): identity(), json_response(), normalize_target()

### Community 3 - "Community 3"
Cohesion: 0.5
Nodes (5): etroc_for_zip_name(), key_for_etroc(), main(), slug_name(), update_chip_page()

### Community 4 - "Community 4"
Cohesion: 0.83
Nodes (3): reason_after_mapping(), update_index(), update_index_segment()

### Community 5 - "Community 5"
Cohesion: 0.5
Nodes (2): Handler, SimpleHTTPRequestHandler

### Community 6 - "Community 6"
Cohesion: 0.67
Nodes (1): normalize_status()

### Community 7 - "Community 7"
Cohesion: 0.67
Nodes (1): read_json()

## Knowledge Gaps
- **Thin community `Community 5`** (4 nodes): `Handler`, `.log_message()`, `.translate_path()`, `SimpleHTTPRequestHandler`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 6`** (3 nodes): `.do_PATCH()`, `.do_PUT()`, `normalize_status()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 7`** (3 nodes): `server.py`, `init_db()`, `read_json()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Handler` connect `Community 5` to `Community 2`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Why does `main()` connect `Community 3` to `Community 1`, `Community 4`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **Why does `identity()` connect `Community 2` to `Community 6`, `Community 7`?**
  _High betweenness centrality (0.008) - this node is a cross-community bridge._