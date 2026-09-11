# Graph Report - bbqc-etroc-production  (2026-09-11)

## Corpus Check
- 42 files · ~35,552,272 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 725 nodes · 1574 edges · 20 communities detected
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 327 edges (avg confidence: 0.8)
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
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]

## God Nodes (most connected - your core abstractions)
1. `LxplusDashboardDeployTests` - 83 edges
2. `append()` - 63 edges
3. `run()` - 56 edges
4. `append()` - 44 edges
5. `init_db()` - 33 edges
6. `sha256()` - 22 edges
7. `HybridRegistryMigrationTests` - 21 edges
8. `saveReview()` - 20 edges
9. `init_schema()` - 20 edges
10. `ETROCReviewFrontendTests` - 20 edges

## Surprising Connections (you probably didn't know these)
- `collect_scans()` --calls--> `append()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → hybrid-bbqc/etroc_position_reviews.py
- `scan_block()` --calls--> `append()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → hybrid-bbqc/etroc_position_reviews.py
- `main()` --calls--> `append()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → hybrid-bbqc/etroc_position_reviews.py
- `make_snapshot()` --calls--> `append()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/apply_comment_concordance.py → hybrid-bbqc/etroc_position_reviews.py
- `make_snapshot()` --calls--> `sha256()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/apply_comment_concordance.py → hybrid-bbqc/etroc-review.js

## Communities

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (20): Behavioral regressions for the post-review save/readback UI boundary., test_actual_position_save_refreshes_only_validated_readback(), test_result_style_selectors_and_pending_copy_match_runtime(), Execute the real result viewer/controller in a small native-DOM boundary harness, test_read_only_result_viewer(), LxplusAdditionalTestsDeployTests, LxplusDashboardDeployTests, Execute supplied-image lifecycle against real controller, with native DOM bounda (+12 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (74): applyQueue(), canonicalMontageUri(), canSaveActive(), closeDialog(), controls(), controlsEnabled(), currentDraft(), dirty() (+66 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (36): bind_hybrid(), canonical_cern_principal(), discover_canonical_pairs(), discover_redirect_aliases(), etroc_error(), _etroc_evidence_identity(), etroc_query(), etroc_reviewer_allowlist() (+28 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (44): append(), _asset_bytes(), audit(), _checksum_inventory(), _completion(), completion_summary(), _current(), _digest() (+36 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (43): analyze_one(), grid_centers(), grid_scores(), main(), optical_labels(), overlay(), _peaks(), read_manifest() (+35 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (26): atomic_replace_directory(), build_pool(), height_publication(), int_field(), load_height_contract(), main(), position_publication(), render_clean_montage() (+18 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (23): appendCell(), element(), initStatistics(), initStatisticsTableSorting(), parseVerifiedPublication(), ratioLabel(), renderCategoryRows(), renderStatistics() (+15 more)

### Community 7 - "Community 7"
Cohesion: 0.14
Nodes (10): append_etroc_review(), init_etroc_review_schema(), load_etroc_review_evidence(), reset_etroc_review_evidence_cache(), EvidenceTests, load_server_module(), ReviewApiTests, ReviewServiceTests (+2 more)

### Community 8 - "Community 8"
Cohesion: 0.12
Nodes (22): exact_owned_replica_sets(), main(), owner_matches(), pod_owned_by_replica_set(), pod_uses_pvc(), select_single_app_pod(), validate_all_pvc_pods(), HybridRegistryDeploymentTests (+14 more)

### Community 9 - "Community 9"
Cohesion: 0.11
Nodes (17): animateCounters(), csvCell(), loadAdditionalTests(), loadReviewStatus(), number(), renderDonut(), safeSpreadsheetValue(), setKpi() (+9 more)

### Community 10 - "Community 10"
Cohesion: 0.16
Nodes (13): CardStateParser, choose_latest(), classify_comment(), current_states(), main(), make_snapshot(), _replace_fragment(), _replace_one() (+5 more)

### Community 11 - "Community 11"
Cohesion: 0.18
Nodes (1): ETROCReviewFrontendTests

### Community 12 - "Community 12"
Cohesion: 0.28
Nodes (15): apply(), categoryStrip(), clear(), counts(), createViewer(), exact(), node(), openResultViewer() (+7 more)

### Community 13 - "Community 13"
Cohesion: 0.34
Nodes (14): esc(), etroc_for_zip_name(), key_for_etroc(), main(), note_for_crops(), reason_after_mapping(), slug_name(), update_chip_page() (+6 more)

### Community 14 - "Community 14"
Cohesion: 0.13
Nodes (1): AnalyticsDashboardTests

### Community 15 - "Community 15"
Cohesion: 0.27
Nodes (12): apply(), createComments(), createViewer(), digest(), exact(), hash(), node(), parseVerified() (+4 more)

### Community 16 - "Community 16"
Cohesion: 0.4
Nodes (3): buildconfig(), BuildProvenanceValidatorTests, completed_build()

### Community 17 - "Community 17"
Cohesion: 0.29
Nodes (3): PositionApiTests, ResultApiTests, HybridRegistryHttpTests

### Community 18 - "Community 18"
Cohesion: 0.43
Nodes (6): api(), esc(), fmt(), loadComments(), loadMe(), renderComment()

### Community 19 - "Community 19"
Cohesion: 0.33
Nodes (1): HybridPairCorrectionTests

## Knowledge Gaps
- **10 isolated node(s):** `Deterministic, byte-preserving publication of the approved supplied batch.`, `Bounded current labels from one read snapshot, never history or review notes.`, `Normalize API-defaulted empty containers without hiding non-empty drift.`, `Execute the real result viewer/controller in a small native-DOM boundary harness`, `Executable comparison contract; native DOM/decode boundary stand-ins only.` (+5 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 11`** (21 nodes): `ETROCReviewFrontendTests`, `.node()`, `.test_active_record_scientific_context_contract()`, `.test_candidate_priority_filter_and_remote_save_next_refresh()`, `.test_controller_montage_generation_ignores_stale_bytes_and_revokes_urls()`, `.test_controller_queue_snapshot_and_direct_open_modes()`, `.test_controller_revokes_a_verified_url_when_image_decode_fails()`, `.test_generation_gate_rejects_stale_async_completion_and_requires_active_verified_blob()`, `.test_mutation_identity_and_conflict_draft_contract()`, `.test_persisted_completion_summary_drives_card_state_filter_and_pending_queue()`, `.test_position_height_publication_is_verified_and_quantitative()`, `.test_position_human_label_and_target_only_mode_contract()`, `.test_position_publication_reconciliation_and_target_queue_are_fail_closed()`, `.test_reconciliation_rejects_review_with_mismatched_provenance()`, `.test_same_byte_publication_event_derives_dataset_identity_before_reconciliation()`, `.test_save_and_history_envelopes_require_exact_evidence_event_and_chain()`, `.test_stale_decode_revokes_only_its_local_object_url()`, `.test_successful_save_uses_validated_refreshed_current_not_post_envelope()`, `.test_verified_evidence_contract_and_queue_are_fail_closed()`, `.test_workspace_markup_and_safe_dom_contract()`, `test_etroc_review_frontend.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (15 nodes): `AnalyticsDashboardTests`, `.test_additional_test_failure_marks_table_cells_unavailable()`, `.test_additional_tests_use_live_registry_api_and_safe_badges()`, `.test_dashboard_does_not_change_canonical_hybrid_inventory()`, `.test_dashboard_does_not_present_absence_of_optical_candidate_as_review_ready()`, `.test_dashboard_exposes_semantic_chart_regions_and_scientific_caveat()`, `.test_dashboard_handles_untrusted_group_labels_and_pending_rows_safely()`, `.test_dashboard_script_uses_existing_rows_and_live_comment_summary()`, `.test_dashboard_styles_are_responsive_and_respect_reduced_motion()`, `.test_live_updates_are_announced_and_only_animate_the_reviewed_counter()`, `.test_main_page_loads_local_dashboard_assets_and_places_dashboard_first()`, `.test_table_csv_export_contract()`, `.test_table_filters_and_sorting_are_keyboard_and_screen_reader_accessible()`, `.test_table_has_static_advanced_tests_column_for_every_hybrid()`, `test_analytics_dashboard.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (6 nodes): `HybridPairCorrectionTests`, `.test_concordance_snapshot_uses_the_corrected_comment_target()`, `.test_corrected_detail_page_keeps_an_old_url_redirect()`, `.test_dashboard_uses_only_the_corrected_w04f2_81_slug()`, `.test_manifest_preserves_w04f2_34_and_corrects_w04f2_81()`, `test_hybrid_pair_correction.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `append()` connect `Community 3` to `Community 0`, `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 10`, `Community 12`, `Community 13`, `Community 15`?**
  _High betweenness centrality (0.371) - this node is a cross-community bridge._
- **Why does `run()` connect `Community 0` to `Community 3`, `Community 5`, `Community 6`, `Community 11`, `Community 16`?**
  _High betweenness centrality (0.208) - this node is a cross-community bridge._
- **Why does `append()` connect `Community 4` to `Community 0`, `Community 2`, `Community 3`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 10`, `Community 13`?**
  _High betweenness centrality (0.184) - this node is a cross-community bridge._
- **Are the 55 inferred relationships involving `append()` (e.g. with `.handle_data()` and `.handle_endtag()`) actually correct?**
  _`append()` has 55 INFERRED edges - model-reasoned connections that need verification._
- **Are the 49 inferred relationships involving `run()` (e.g. with `.test_lgad_statistics_contract_reconciles_and_rejects_bad_inventory()` and `.test_backup_dir_override_defaults_exactly_and_rejects_unsafe_paths()`) actually correct?**
  _`run()` has 49 INFERRED edges - model-reasoned connections that need verification._
- **Are the 36 inferred relationships involving `append()` (e.g. with `.handle_data()` and `.handle_endtag()`) actually correct?**
  _`append()` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `init_db()` (e.g. with `.test_required_missing_manifest_fails_before_database_mutation()` and `.test_incompatible_partial_schema_rolls_back_all_migration_changes()`) actually correct?**
  _`init_db()` has 25 INFERRED edges - model-reasoned connections that need verification._