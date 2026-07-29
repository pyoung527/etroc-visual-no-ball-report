# Graph Report - etroc-visual-no-ball-report-plan  (2026-07-29)

## Corpus Check
- 12 files · ~27,884,481 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 153 nodes · 287 edges · 11 communities detected
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 30 edges (avg confidence: 0.8)
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
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]

## God Nodes (most connected - your core abstractions)
1. `init_db()` - 20 edges
2. `HybridRegistryMigrationTests` - 16 edges
3. `Handler` - 9 edges
4. `main()` - 8 edges
5. `HybridRegistryHttpTests` - 8 edges
6. `HybridTableParser` - 7 edges
7. `main()` - 7 edges
8. `bind_hybrid()` - 7 edges
9. `main()` - 6 edges
10. `esc()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `sha256()` --calls--> `make_snapshot()`  [INFERRED]
  import_new_nw_scans.py → apply_comment_concordance.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.16
Nodes (13): CardStateParser, choose_latest(), classify_comment(), current_states(), main(), make_snapshot(), _replace_fragment(), _replace_one() (+5 more)

### Community 1 - "Community 1"
Cohesion: 0.22
Nodes (12): discover_canonical_pairs(), discover_redirect_aliases(), Handler, identity(), json_response(), mutation_request_error(), normalize_status(), normalize_target() (+4 more)

### Community 2 - "Community 2"
Cohesion: 0.2
Nodes (14): canonical_etroc(), clean_reason(), collect_scans(), DashboardRow, HybridTableParser, main(), parse_dashboard_rows(), replace_attr() (+6 more)

### Community 3 - "Community 3"
Cohesion: 0.21
Nodes (5): bind_hybrid(), init_db(), list_hybrids(), split_pair_key(), HybridRegistryMigrationTests

### Community 4 - "Community 4"
Cohesion: 0.34
Nodes (14): esc(), etroc_for_zip_name(), key_for_etroc(), main(), note_for_crops(), reason_after_mapping(), slug_name(), update_chip_page() (+6 more)

### Community 5 - "Community 5"
Cohesion: 0.23
Nodes (5): create_legacy_comments_db(), create_static_site(), HybridRegistryHttpTests, HybridRegistryRealStaticTests, load_server_module()

### Community 6 - "Community 6"
Cohesion: 0.25
Nodes (6): HybridRegistryDeploymentTests, main(), owner_matches(), pod_template_spec(), uses_pvc(), validate_pvc_controllers()

### Community 7 - "Community 7"
Cohesion: 0.42
Nodes (8): analyze_one(), grid_centers(), grid_scores(), main(), optical_labels(), overlay(), _peaks(), read_manifest()

### Community 8 - "Community 8"
Cohesion: 0.43
Nodes (6): api(), esc(), fmt(), loadComments(), loadMe(), renderComment()

### Community 9 - "Community 9"
Cohesion: 0.54
Nodes (7): exact_owned_replica_sets(), main(), owner_matches(), pod_owned_by_replica_set(), pod_uses_pvc(), select_single_app_pod(), validate_all_pvc_pods()

### Community 10 - "Community 10"
Cohesion: 0.33
Nodes (1): HybridPairCorrectionTests

## Knowledge Gaps
- **Thin community `Community 10`** (6 nodes): `HybridPairCorrectionTests`, `.test_concordance_snapshot_uses_the_corrected_comment_target()`, `.test_corrected_detail_page_keeps_an_old_url_redirect()`, `.test_dashboard_uses_only_the_corrected_w04f2_81_slug()`, `.test_manifest_preserves_w04f2_34_and_corrects_w04f2_81()`, `test_hybrid_pair_correction.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `HybridRegistryDeploymentTests` connect `Community 6` to `Community 5`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Why does `init_db()` connect `Community 3` to `Community 1`, `Community 5`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `HybridRegistryMigrationTests` connect `Community 3` to `Community 5`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `init_db()` (e.g. with `.test_init_db_seeds_registry_aliases_and_backfills_legacy_comments()` and `.test_init_db_is_idempotent()`) actually correct?**
  _`init_db()` has 16 INFERRED edges - model-reasoned connections that need verification._