# Graph Report - bbqc-etroc-oi-2608  (2026-08-18)

## Corpus Check
- 23 files · ~31,178,184 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 324 nodes · 571 edges · 18 communities detected
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 60 edges (avg confidence: 0.8)
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

## God Nodes (most connected - your core abstractions)
1. `init_db()` - 31 edges
2. `HybridRegistryMigrationTests` - 21 edges
3. `LxplusDashboardDeployTests` - 15 edges
4. `EtrocOpticalPoolTests` - 14 edges
5. `AnalyticsDashboardTests` - 14 edges
6. `build_pool()` - 12 edges
7. `sha256()` - 10 edges
8. `load_server_module()` - 10 edges
9. `Handler` - 9 edges
10. `renderStatistics()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `parse_args()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → hybrid-bbqc/openshift/validate_build_provenance.py
- `make_snapshot()` --calls--> `sha256()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/apply_comment_concordance.py → tools/build_etroc_optical_pool.py
- `main()` --calls--> `parse_args()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/apply_comment_concordance.py → hybrid-bbqc/openshift/validate_build_provenance.py
- `main()` --calls--> `parse_args()`  [INFERRED]
  tools/build_etroc_optical_pool.py → hybrid-bbqc/openshift/validate_build_provenance.py
- `sha256()` --calls--> `make_snapshot()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → /tmp/etroc-visual-no-ball-report-plan/apply_comment_concordance.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (12): bind_hybrid(), init_db(), validate_additional_test_schema(), AdditionalTestManifestTests, _canonical_pairs(), create_legacy_comments_db(), create_static_site(), HybridRegistryHttpTests (+4 more)

### Community 1 - "Community 1"
Cohesion: 0.14
Nodes (13): atomic_replace_directory(), build_pool(), int_field(), main(), render_jpegs(), resolve_under(), sha256(), validate_position_results() (+5 more)

### Community 2 - "Community 2"
Cohesion: 0.18
Nodes (16): discover_canonical_pairs(), discover_redirect_aliases(), Handler, identity(), json_response(), list_hybrids(), load_additional_tests_manifest(), mutation_request_error() (+8 more)

### Community 3 - "Community 3"
Cohesion: 0.13
Nodes (15): animateCounters(), csvCell(), loadAdditionalTests(), loadReviewStatus(), number(), renderDonut(), safeSpreadsheetValue(), setKpi() (+7 more)

### Community 4 - "Community 4"
Cohesion: 0.16
Nodes (13): CardStateParser, choose_latest(), classify_comment(), current_states(), main(), make_snapshot(), _replace_fragment(), _replace_one() (+5 more)

### Community 5 - "Community 5"
Cohesion: 0.16
Nodes (18): appendCell(), element(), initStatistics(), initStatisticsTableSorting(), ratioLabel(), render(), renderCard(), renderCategoryRows() (+10 more)

### Community 6 - "Community 6"
Cohesion: 0.2
Nodes (14): canonical_etroc(), clean_reason(), collect_scans(), DashboardRow, HybridTableParser, main(), parse_dashboard_rows(), replace_attr() (+6 more)

### Community 7 - "Community 7"
Cohesion: 0.18
Nodes (4): validate(), _classes(), DashboardStructureParser, TabLocalDashboardTests

### Community 8 - "Community 8"
Cohesion: 0.24
Nodes (14): compact(), fail(), load_object(), main(), parse_args(), Normalize API-defaulted empty containers without hiding non-empty drift., require_int(), require_mapping() (+6 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (1): LxplusDashboardDeployTests

### Community 10 - "Community 10"
Cohesion: 0.34
Nodes (14): esc(), etroc_for_zip_name(), key_for_etroc(), main(), note_for_crops(), reason_after_mapping(), slug_name(), update_chip_page() (+6 more)

### Community 11 - "Community 11"
Cohesion: 0.13
Nodes (1): AnalyticsDashboardTests

### Community 12 - "Community 12"
Cohesion: 0.26
Nodes (8): exact_owned_replica_sets(), main(), owner_matches(), pod_owned_by_replica_set(), pod_uses_pvc(), select_single_app_pod(), validate_all_pvc_pods(), HybridRegistryDeploymentTests

### Community 13 - "Community 13"
Cohesion: 0.4
Nodes (3): buildconfig(), BuildProvenanceValidatorTests, completed_build()

### Community 14 - "Community 14"
Cohesion: 0.42
Nodes (8): analyze_one(), grid_centers(), grid_scores(), main(), optical_labels(), overlay(), _peaks(), read_manifest()

### Community 15 - "Community 15"
Cohesion: 0.22
Nodes (1): LxplusAdditionalTestsDeployTests

### Community 16 - "Community 16"
Cohesion: 0.43
Nodes (6): api(), esc(), fmt(), loadComments(), loadMe(), renderComment()

### Community 17 - "Community 17"
Cohesion: 0.33
Nodes (1): HybridPairCorrectionTests

## Knowledge Gaps
- **1 isolated node(s):** `Normalize API-defaulted empty containers without hiding non-empty drift.`
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 9`** (16 nodes): `LxplusDashboardDeployTests`, `.test_helper_bootstraps_official_device_flow_without_printing_tokens()`, `.test_helper_exercises_etroc_assets_through_runtime_http()`, `.test_helper_fails_after_permanent_or_exhausted_download_errors()`, `.test_helper_fails_closed_on_context_and_permissions()`, `.test_helper_handles_interrupts_and_preserves_full_replace_metadata()`, `.test_helper_has_valid_bash_syntax()`, `.test_helper_pins_and_verifies_rollout_and_static_files()`, `.test_helper_pins_complete_etroc_dataset_and_runtime_verification()`, `.test_helper_pins_release_and_download_checksums()`, `.test_helper_retries_transient_asset_downloads()`, `.test_helper_runs_pinned_executable_build_provenance_validator()`, `.test_helper_uses_immutable_overlay_build_with_allowlisted_context()`, `.test_helper_verifies_backup_and_preserves_rollback_coordinates()`, `.test_rollback_renderer_rejects_same_name_with_new_uid()`, `test_lxplus_dashboard_deploy.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 11`** (15 nodes): `AnalyticsDashboardTests`, `.test_additional_test_failure_marks_table_cells_unavailable()`, `.test_additional_tests_use_live_registry_api_and_safe_badges()`, `.test_dashboard_does_not_change_canonical_hybrid_inventory()`, `.test_dashboard_does_not_present_absence_of_optical_candidate_as_review_ready()`, `.test_dashboard_exposes_semantic_chart_regions_and_scientific_caveat()`, `.test_dashboard_handles_untrusted_group_labels_and_pending_rows_safely()`, `.test_dashboard_script_uses_existing_rows_and_live_comment_summary()`, `.test_dashboard_styles_are_responsive_and_respect_reduced_motion()`, `.test_live_updates_are_announced_and_only_animate_the_reviewed_counter()`, `.test_main_page_loads_local_dashboard_assets_and_places_dashboard_first()`, `.test_table_csv_export_contract()`, `.test_table_filters_and_sorting_are_keyboard_and_screen_reader_accessible()`, `.test_table_has_static_advanced_tests_column_for_every_hybrid()`, `test_analytics_dashboard.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (9 nodes): `LxplusAdditionalTestsDeployTests`, `.test_candidate_probe_precedes_production_mutation()`, `.test_exact_candidate_image_uses_real_startup_probe_contract()`, `.test_external_sso_gate_retries_without_client_identity_header()`, `.test_forward_deployment_normalizes_localhost_probes()`, `.test_helper_has_valid_bash_syntax()`, `.test_helper_pins_advanced_table_csv_release()`, `.test_rollback_renderer_rejects_same_name_with_new_uid()`, `test_lxplus_additional_tests_deploy.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (6 nodes): `HybridPairCorrectionTests`, `.test_concordance_snapshot_uses_the_corrected_comment_target()`, `.test_corrected_detail_page_keeps_an_old_url_redirect()`, `.test_dashboard_uses_only_the_corrected_w04f2_81_slug()`, `.test_manifest_preserves_w04f2_34_and_corrects_w04f2_81()`, `test_hybrid_pair_correction.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `sha256()` connect `Community 1` to `Community 0`, `Community 4`, `Community 7`?**
  _High betweenness centrality (0.225) - this node is a cross-community bridge._
- **Why does `make_snapshot()` connect `Community 4` to `Community 1`, `Community 6`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Are the 25 inferred relationships involving `init_db()` (e.g. with `.test_required_missing_manifest_fails_before_database_mutation()` and `.test_incompatible_partial_schema_rolls_back_all_migration_changes()`) actually correct?**
  _`init_db()` has 25 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Normalize API-defaulted empty containers without hiding non-empty drift.` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.14 - nodes in this community are weakly interconnected._
- **Should `Community 3` be split into smaller, more focused modules?**
  _Cohesion score 0.13 - nodes in this community are weakly interconnected._