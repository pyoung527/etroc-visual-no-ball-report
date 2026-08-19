# Graph Report - bbqc-etroc-oi-2608  (2026-08-19)

## Corpus Check
- 27 files · ~31,204,511 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 537 nodes · 1050 edges · 20 communities detected
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 149 edges (avg confidence: 0.8)
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
1. `LxplusDashboardDeployTests` - 72 edges
2. `append()` - 46 edges
3. `init_db()` - 33 edges
4. `HybridRegistryMigrationTests` - 21 edges
5. `saveReview()` - 20 edges
6. `updateDialog()` - 19 edges
7. `load_etroc_review_evidence()` - 18 edges
8. `ETROCReviewFrontendTests` - 16 edges
9. `EtrocOpticalPoolTests` - 15 edges
10. `load_server_module()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `collect_scans()` --calls--> `append()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → hybrid-bbqc/etroc_reviews.py
- `scan_block()` --calls--> `append()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → hybrid-bbqc/etroc_reviews.py
- `main()` --calls--> `parse_args()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → hybrid-bbqc/openshift/validate_build_provenance.py
- `main()` --calls--> `append()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → hybrid-bbqc/etroc_reviews.py
- `make_snapshot()` --calls--> `append()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/apply_comment_concordance.py → hybrid-bbqc/etroc_reviews.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (33): bind_hybrid(), canonical_cern_principal(), discover_canonical_pairs(), discover_redirect_aliases(), etroc_error(), _etroc_evidence_identity(), etroc_query(), etroc_reviewer_allowlist() (+25 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (1): LxplusDashboardDeployTests

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (54): applyQueue(), canonicalComparator(), canonicalMontageUri(), canSaveActive(), closeDialog(), controls(), controlsEnabled(), currentDraft() (+46 more)

### Community 3 - "Community 3"
Cohesion: 0.13
Nodes (29): analyze_one(), grid_centers(), grid_scores(), main(), optical_labels(), overlay(), _peaks(), read_manifest() (+21 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (11): append_etroc_review(), init_etroc_review_schema(), initialize_store(), load_etroc_review_evidence(), reset_etroc_review_evidence_cache(), EvidenceTests, load_server_module(), ReviewApiTests (+3 more)

### Community 5 - "Community 5"
Cohesion: 0.13
Nodes (15): atomic_replace_directory(), build_pool(), int_field(), main(), render_jpegs(), resolve_under(), sha256(), validate_position_results() (+7 more)

### Community 6 - "Community 6"
Cohesion: 0.12
Nodes (22): exact_owned_replica_sets(), main(), owner_matches(), pod_owned_by_replica_set(), pod_uses_pvc(), select_single_app_pod(), validate_all_pvc_pods(), HybridRegistryDeploymentTests (+14 more)

### Community 7 - "Community 7"
Cohesion: 0.13
Nodes (15): animateCounters(), csvCell(), loadAdditionalTests(), loadReviewStatus(), number(), renderDonut(), safeSpreadsheetValue(), setKpi() (+7 more)

### Community 8 - "Community 8"
Cohesion: 0.16
Nodes (13): CardStateParser, choose_latest(), classify_comment(), current_states(), main(), make_snapshot(), _replace_fragment(), _replace_one() (+5 more)

### Community 9 - "Community 9"
Cohesion: 0.16
Nodes (18): appendCell(), element(), initStatistics(), initStatisticsTableSorting(), ratioLabel(), render(), renderCard(), renderCategoryRows() (+10 more)

### Community 10 - "Community 10"
Cohesion: 0.17
Nodes (5): parseVerifiedPublication(), validate(), _classes(), DashboardStructureParser, TabLocalDashboardTests

### Community 11 - "Community 11"
Cohesion: 0.2
Nodes (14): canonical_etroc(), clean_reason(), collect_scans(), DashboardRow, HybridTableParser, main(), parse_dashboard_rows(), replace_attr() (+6 more)

### Community 12 - "Community 12"
Cohesion: 0.21
Nodes (1): ETROCReviewFrontendTests

### Community 13 - "Community 13"
Cohesion: 0.34
Nodes (14): esc(), etroc_for_zip_name(), key_for_etroc(), main(), note_for_crops(), reason_after_mapping(), slug_name(), update_chip_page() (+6 more)

### Community 14 - "Community 14"
Cohesion: 0.13
Nodes (1): AnalyticsDashboardTests

### Community 15 - "Community 15"
Cohesion: 0.4
Nodes (3): buildconfig(), BuildProvenanceValidatorTests, completed_build()

### Community 16 - "Community 16"
Cohesion: 0.22
Nodes (1): LxplusAdditionalTestsDeployTests

### Community 17 - "Community 17"
Cohesion: 0.43
Nodes (6): api(), esc(), fmt(), loadComments(), loadMe(), renderComment()

### Community 18 - "Community 18"
Cohesion: 0.48
Nodes (1): HybridRegistryHttpTests

### Community 19 - "Community 19"
Cohesion: 0.33
Nodes (1): HybridPairCorrectionTests

## Knowledge Gaps
- **1 isolated node(s):** `Normalize API-defaulted empty containers without hiding non-empty drift.`
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 1`** (70 nodes): `LxplusDashboardDeployTests`, `.test_authenticated_browser_qa_is_explicitly_deferred()`, `.test_backup_dir_override_defaults_exactly_and_rejects_unsafe_paths()`, `.test_candidate_create_failure_never_adopts_or_operates_on_a_same_name_pod()`, `.test_candidate_creation_captures_uid_from_create_response_and_uses_uid_precondition()`, `.test_candidate_image_entrypoint_and_evidence_loader_run_before_deployment_mutation()`, `.test_candidate_probe_cleanup_is_uid_guarded_and_owned_before_possible_failures()`, `.test_canonical_manifests_define_one_verified_oauth_exposure_boundary()`, `.test_captured_rollback_renderer_preserves_route_wildcard_policy()`, `.test_captured_topology_classification_binds_legacy_rollback_before_live_refetch()`, `.test_dashboard_headroom_gate_accepts_sufficient_numeric_space()`, `.test_dashboard_headroom_gate_precedes_backup_and_release_artifact_writes()`, `.test_dashboard_headroom_gate_rejects_low_afs_space()`, `.test_dashboard_headroom_gate_rejects_low_pvc_space()`, `.test_dashboard_headroom_gate_rejects_malformed_or_overflow_values()`, `.test_dashboard_headroom_gate_rejects_malformed_web_container_output()`, `.test_dashboard_headroom_gate_rejects_retention_cap_without_deleting_evidence()`, `.test_deployment_declares_the_exact_loopback_oauth2_proxy_boundary()`, `.test_event_snapshot_is_ordered_and_captures_mutable_review_fields()`, `.test_forward_render_uses_pinned_baseline_and_rejects_live_spec_drift()`, `.test_forward_renderer_normalizes_only_reviewed_route_server_defaults()`, `.test_forward_renderer_normalizes_only_the_exact_reviewed_legacy_deltas()`, `.test_forward_renderer_preserves_only_baseline_approved_annotations()`, `.test_forward_renderer_rejects_annotation_drift_except_known_generated_values()`, `.test_headroom_counts_wal_and_shm_and_retention_rejects_unknown_artifacts()`, `.test_helper_bootstraps_official_device_flow_without_printing_tokens()`, `.test_helper_compares_the_full_api_evidence_map_to_locally_validated_publication()`, `.test_helper_exercises_etroc_assets_through_runtime_http()`, `.test_helper_exercises_review_mutation_only_on_disposable_candidate_copies()`, `.test_helper_fails_after_permanent_or_exhausted_download_errors()`, `.test_helper_fails_closed_on_context_and_permissions()`, `.test_helper_gates_content_addressed_montages_and_publication_hash()`, `.test_helper_gates_exact_review_runtime_contract_and_identity_boundary()`, `.test_helper_handles_interrupts_and_preserves_full_replace_metadata()`, `.test_helper_has_no_cookie_export_or_production_review_post_workflow()`, `.test_helper_has_valid_bash_syntax()`, `.test_helper_makes_disposable_empty_and_existing_review_history_gates_deterministic()`, `.test_helper_never_accepts_operator_scientific_review_inputs()`, `.test_helper_packages_applies_and_validates_all_three_canonical_manifests()`, `.test_helper_packages_pinned_review_frontend_and_backend_runtime()`, `.test_helper_pins_and_verifies_rollout_and_static_files()`, `.test_helper_pins_complete_etroc_dataset_and_runtime_verification()`, `.test_helper_pins_release_and_download_checksums()`, `.test_helper_preflights_candidate_review_migration_and_legacy_comments_before_rollout()`, `.test_helper_preflights_normalized_reviewer_allowlist_without_logging_values()`, `.test_helper_preserves_etroc_events_and_identity_chain_across_release_boundaries()`, `.test_helper_probes_content_addressed_montage_from_publication()`, `.test_helper_probes_exact_schema_and_rejects_attached_object_drift()`, `.test_helper_proves_unauthenticated_spoofed_identity_headers_cannot_bypass_sso()`, `.test_helper_refetches_and_validates_exact_oauth_topology_before_and_after_rollout()`, `.test_helper_retries_transient_asset_downloads()`, `.test_helper_runs_pinned_executable_build_provenance_validator()`, `.test_helper_uses_immutable_overlay_build_with_allowlisted_context()`, `.test_helper_verifies_backup_and_preserves_rollback_coordinates()`, `.test_legacy_compatibility_is_local_and_never_copies_a_candidate_db_to_production()`, `.test_old_runtime_server_extraction_is_digest_pinned_and_rejects_bad_output()`, `.test_post_migration_compares_the_complete_existing_hybrid_schema()`, `.test_retention_treats_checksum_sidecar_as_one_release_set()`, `.test_rollback_attempts_remaining_objects_after_restore_failure()`, `.test_rollback_fixture_attempts_later_restores_after_first_or_second_failure()`, `.test_rollback_keeps_pre_rollout_etroc_snapshot_as_the_invariant()`, `.test_rollback_renderer_recovers_each_partial_forward_state()`, `.test_rollback_renderer_rejects_same_name_with_new_uid()`, `.test_rollback_replaces_only_restore_marked_objects()`, `.test_rollback_scope_captures_and_restores_service_and_route_fail_closed()`, `.test_runtime_http_montage_bytes_equal_the_published_digest()`, `.test_storage_measurement_uses_afs_then_df_and_rejects_malformed_output()`, `.test_topology_inventory_covers_every_service_and_route_selecting_live_pods()`, `.test_topology_pins_oauth_proxy_to_captured_digest_not_merely_a_digest()`, `test_lxplus_dashboard_deploy.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 12`** (17 nodes): `ETROCReviewFrontendTests`, `.node()`, `.test_active_record_scientific_context_contract()`, `.test_candidate_priority_filter_and_remote_save_next_refresh()`, `.test_controller_montage_generation_ignores_stale_bytes_and_revokes_urls()`, `.test_controller_queue_snapshot_and_direct_open_modes()`, `.test_controller_revokes_a_verified_url_when_image_decode_fails()`, `.test_generation_gate_rejects_stale_async_completion_and_requires_active_verified_blob()`, `.test_mutation_identity_and_conflict_draft_contract()`, `.test_reconciliation_rejects_review_with_mismatched_provenance()`, `.test_same_byte_publication_event_derives_dataset_identity_before_reconciliation()`, `.test_save_and_history_envelopes_require_exact_evidence_event_and_chain()`, `.test_stale_decode_revokes_only_its_local_object_url()`, `.test_successful_save_uses_validated_refreshed_current_not_post_envelope()`, `.test_verified_evidence_contract_and_queue_are_fail_closed()`, `.test_workspace_markup_and_safe_dom_contract()`, `test_etroc_review_frontend.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (15 nodes): `AnalyticsDashboardTests`, `.test_additional_test_failure_marks_table_cells_unavailable()`, `.test_additional_tests_use_live_registry_api_and_safe_badges()`, `.test_dashboard_does_not_change_canonical_hybrid_inventory()`, `.test_dashboard_does_not_present_absence_of_optical_candidate_as_review_ready()`, `.test_dashboard_exposes_semantic_chart_regions_and_scientific_caveat()`, `.test_dashboard_handles_untrusted_group_labels_and_pending_rows_safely()`, `.test_dashboard_script_uses_existing_rows_and_live_comment_summary()`, `.test_dashboard_styles_are_responsive_and_respect_reduced_motion()`, `.test_live_updates_are_announced_and_only_animate_the_reviewed_counter()`, `.test_main_page_loads_local_dashboard_assets_and_places_dashboard_first()`, `.test_table_csv_export_contract()`, `.test_table_filters_and_sorting_are_keyboard_and_screen_reader_accessible()`, `.test_table_has_static_advanced_tests_column_for_every_hybrid()`, `test_analytics_dashboard.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (9 nodes): `LxplusAdditionalTestsDeployTests`, `.test_candidate_probe_precedes_production_mutation()`, `.test_exact_candidate_image_uses_real_startup_probe_contract()`, `.test_external_sso_gate_retries_without_client_identity_header()`, `.test_forward_deployment_normalizes_localhost_probes()`, `.test_helper_has_valid_bash_syntax()`, `.test_helper_pins_advanced_table_csv_release()`, `.test_rollback_renderer_rejects_same_name_with_new_uid()`, `test_lxplus_additional_tests_deploy.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (7 nodes): `HybridRegistryHttpTests`, `.request()`, `._stop_server()`, `.test_bind_api_rejects_spoofed_identity_csrf_and_partial_payloads()`, `.test_legacy_comment_target_reads_and_writes_canonical_registry()`, `.test_registry_read_and_admin_bind_api()`, `.test_summary_targets_parameter_preserves_non_hybrid_behavior()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (6 nodes): `HybridPairCorrectionTests`, `.test_concordance_snapshot_uses_the_corrected_comment_target()`, `.test_corrected_detail_page_keeps_an_old_url_redirect()`, `.test_dashboard_uses_only_the_corrected_w04f2_81_slug()`, `.test_manifest_preserves_w04f2_34_and_corrects_w04f2_81()`, `test_hybrid_pair_correction.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `append()` connect `Community 3` to `Community 0`, `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 8`, `Community 9`, `Community 10`, `Community 11`, `Community 13`?**
  _High betweenness centrality (0.530) - this node is a cross-community bridge._
- **Why does `LxplusDashboardDeployTests` connect `Community 1` to `Community 3`, `Community 6`?**
  _High betweenness centrality (0.212) - this node is a cross-community bridge._
- **Why does `sha256()` connect `Community 5` to `Community 0`, `Community 2`, `Community 3`, `Community 4`, `Community 8`, `Community 10`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Are the 38 inferred relationships involving `append()` (e.g. with `.handle_data()` and `.handle_endtag()`) actually correct?**
  _`append()` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `init_db()` (e.g. with `.test_required_missing_manifest_fails_before_database_mutation()` and `.test_incompatible_partial_schema_rolls_back_all_migration_changes()`) actually correct?**
  _`init_db()` has 25 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Normalize API-defaulted empty containers without hiding non-empty drift.` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.06 - nodes in this community are weakly interconnected._