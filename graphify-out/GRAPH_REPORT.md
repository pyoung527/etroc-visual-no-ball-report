# Graph Report - bbqc-etroc-production  (2026-08-24)

## Corpus Check
- 29 files · ~34,260,455 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 627 nodes · 1319 edges · 19 communities detected
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 224 edges (avg confidence: 0.8)
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

## God Nodes (most connected - your core abstractions)
1. `LxplusDashboardDeployTests` - 83 edges
2. `append()` - 53 edges
3. `append()` - 47 edges
4. `init_db()` - 33 edges
5. `HybridRegistryMigrationTests` - 21 edges
6. `saveReview()` - 20 edges
7. `updateDialog()` - 19 edges
8. `load_etroc_review_evidence()` - 19 edges
9. `ETROCReviewFrontendTests` - 18 edges
10. `EtrocOpticalPoolTests` - 17 edges

## Surprising Connections (you probably didn't know these)
- `collect_scans()` --calls--> `append()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → hybrid-bbqc/etroc_position_reviews.py
- `collect_scans()` --calls--> `append()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → hybrid-bbqc/etroc_reviews.py
- `scan_block()` --calls--> `append()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → hybrid-bbqc/etroc_position_reviews.py
- `scan_block()` --calls--> `append()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → hybrid-bbqc/etroc_reviews.py
- `main()` --calls--> `append()`  [INFERRED]
  /tmp/etroc-visual-no-ball-report-plan/import_new_nw_scans.py → hybrid-bbqc/etroc_position_reviews.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (72): applyQueue(), canonicalComparator(), canonicalMontageUri(), canSaveActive(), closeDialog(), controls(), controlsEnabled(), currentDraft() (+64 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (1): LxplusDashboardDeployTests

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (45): analyze_one(), grid_centers(), grid_scores(), main(), optical_labels(), overlay(), _peaks(), read_manifest() (+37 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (14): bind_hybrid(), init_db(), list_hybrids(), split_pair_key(), validate_additional_test_schema(), AdditionalTestManifestTests, _canonical_pairs(), create_legacy_comments_db() (+6 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (28): _asset_bytes(), audit(), _checksum_inventory(), _current(), _digest(), _drop_empty_legacy_schema(), _drop_position_schema(), _event() (+20 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (20): initStatistics(), initStatisticsTableSorting(), parseVerifiedPublication(), ratioLabel(), renderCategoryRows(), renderStatistics(), renderStatisticsTable(), renderWaferRows() (+12 more)

### Community 6 - "Community 6"
Cohesion: 0.13
Nodes (16): atomic_replace_directory(), build_pool(), int_field(), main(), position_publication(), render_clean_montage(), render_jpegs(), resolve_under() (+8 more)

### Community 7 - "Community 7"
Cohesion: 0.13
Nodes (22): canonical_cern_principal(), discover_canonical_pairs(), discover_redirect_aliases(), etroc_error(), _etroc_evidence_identity(), etroc_query(), etroc_reviewer_allowlist(), etroc_viewer() (+14 more)

### Community 8 - "Community 8"
Cohesion: 0.14
Nodes (10): append_etroc_review(), init_etroc_review_schema(), load_etroc_review_evidence(), reset_etroc_review_evidence_cache(), EvidenceTests, load_server_module(), ReviewApiTests, ReviewServiceTests (+2 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (22): exact_owned_replica_sets(), main(), owner_matches(), pod_owned_by_replica_set(), pod_uses_pvc(), select_single_app_pod(), validate_all_pvc_pods(), HybridRegistryDeploymentTests (+14 more)

### Community 10 - "Community 10"
Cohesion: 0.13
Nodes (15): animateCounters(), csvCell(), loadAdditionalTests(), loadReviewStatus(), number(), renderDonut(), safeSpreadsheetValue(), setKpi() (+7 more)

### Community 11 - "Community 11"
Cohesion: 0.22
Nodes (18): audit(), _checksum_inventory(), _current(), _digest(), _error(), _event(), EvidenceRecord, EvidenceSet (+10 more)

### Community 12 - "Community 12"
Cohesion: 0.19
Nodes (1): ETROCReviewFrontendTests

### Community 13 - "Community 13"
Cohesion: 0.22
Nodes (15): HTMLParser, canonical_etroc(), clean_reason(), collect_scans(), DashboardRow, HybridTableParser, main(), parse_dashboard_rows() (+7 more)

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
Cohesion: 0.33
Nodes (1): HybridPairCorrectionTests

## Knowledge Gaps
- **1 isolated node(s):** `Normalize API-defaulted empty containers without hiding non-empty drift.`
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 1`** (80 nodes): `LxplusDashboardDeployTests`, `.test_authenticated_browser_qa_is_explicitly_deferred()`, `.test_backup_dir_override_defaults_exactly_and_rejects_unsafe_paths()`, `.test_buildconfig_manifest_pins_build_history_retention()`, `.test_candidate_create_failure_never_adopts_or_operates_on_a_same_name_pod()`, `.test_candidate_creation_captures_uid_from_create_response_and_uses_uid_precondition()`, `.test_candidate_host_rehearsal_uses_the_pod_compatible_python_before_backup()`, `.test_candidate_image_entrypoint_and_evidence_loader_run_before_deployment_mutation()`, `.test_candidate_probe_cleanup_is_uid_guarded_and_owned_before_possible_failures()`, `.test_canonical_manifests_define_one_verified_oauth_exposure_boundary()`, `.test_captured_rollback_renderer_preserves_route_wildcard_policy()`, `.test_captured_topology_classification_binds_legacy_rollback_before_live_refetch()`, `.test_dashboard_headroom_gate_accepts_sufficient_numeric_space()`, `.test_dashboard_headroom_gate_precedes_backup_and_release_artifact_writes()`, `.test_dashboard_headroom_gate_rejects_low_afs_space()`, `.test_dashboard_headroom_gate_rejects_low_pvc_space()`, `.test_dashboard_headroom_gate_rejects_malformed_or_overflow_values()`, `.test_dashboard_headroom_gate_rejects_malformed_web_container_output()`, `.test_dashboard_headroom_gate_rejects_retention_cap_without_deleting_evidence()`, `.test_dashboard_headroom_probe_forwards_heredoc_stdin_to_the_container()`, `.test_deployment_declares_the_exact_loopback_oauth2_proxy_boundary()`, `.test_deployment_pins_web_probe_timeout_above_internal_http_timeout()`, `.test_event_snapshot_is_ordered_and_captures_mutable_review_fields()`, `.test_every_oc_exec_heredoc_forwards_stdin_without_a_tty()`, `.test_forward_render_uses_pinned_baseline_and_rejects_live_spec_drift()`, `.test_forward_renderer_accepts_exact_validated_release_annotations_on_all_objects()`, `.test_forward_renderer_normalizes_only_reviewed_route_server_defaults()`, `.test_forward_renderer_normalizes_only_the_exact_reviewed_legacy_deltas()`, `.test_forward_renderer_preserves_only_attested_cern_route_annotations()`, `.test_forward_renderer_preserves_only_baseline_approved_annotations()`, `.test_forward_renderer_rejects_annotation_drift_except_known_generated_values()`, `.test_headroom_counts_wal_and_shm_and_retention_rejects_unknown_artifacts()`, `.test_helper_bootstraps_official_device_flow_without_printing_tokens()`, `.test_helper_compares_the_full_api_evidence_map_to_locally_validated_publication()`, `.test_helper_exercises_etroc_assets_through_runtime_http()`, `.test_helper_exercises_review_mutation_only_on_disposable_candidate_copies()`, `.test_helper_fails_after_permanent_or_exhausted_download_errors()`, `.test_helper_fails_closed_on_context_and_permissions()`, `.test_helper_gates_content_addressed_montages_and_publication_hash()`, `.test_helper_gates_exact_review_runtime_contract_and_identity_boundary()`, `.test_helper_handles_interrupts_and_preserves_full_replace_metadata()`, `.test_helper_has_no_cookie_export_or_production_review_post_workflow()`, `.test_helper_has_valid_bash_syntax()`, `.test_helper_makes_disposable_empty_and_existing_review_history_gates_deterministic()`, `.test_helper_never_accepts_operator_scientific_review_inputs()`, `.test_helper_packages_applies_and_validates_all_three_canonical_manifests()`, `.test_helper_packages_pinned_review_frontend_and_backend_runtime()`, `.test_helper_pins_and_verifies_rollout_and_static_files()`, `.test_helper_pins_complete_etroc_dataset_and_runtime_verification()`, `.test_helper_pins_release_and_download_checksums()`, `.test_helper_preflights_candidate_review_migration_and_legacy_comments_before_rollout()`, `.test_helper_preflights_normalized_reviewer_allowlist_without_logging_values()`, `.test_helper_preserves_etroc_events_and_identity_chain_across_release_boundaries()`, `.test_helper_probes_content_addressed_montage_from_publication()`, `.test_helper_probes_exact_schema_and_rejects_attached_object_drift()`, `.test_helper_proves_unauthenticated_spoofed_identity_headers_cannot_bypass_sso()`, `.test_helper_refetches_and_validates_exact_oauth_topology_before_and_after_rollout()`, `.test_helper_retries_transient_asset_downloads()`, `.test_helper_runs_pinned_executable_build_provenance_validator()`, `.test_helper_uses_immutable_overlay_build_with_allowlisted_context()`, `.test_helper_verifies_backup_and_preserves_rollback_coordinates()`, `.test_invalid_created_candidate_spec_triggers_uid_preconditioned_cleanup()`, `.test_legacy_compatibility_is_local_and_never_copies_a_candidate_db_to_production()`, `.test_old_runtime_server_extraction_is_digest_pinned_and_rejects_bad_output()`, `.test_post_migration_compares_the_complete_existing_hybrid_schema()`, `.test_previous_release_annotations_are_bound_to_completed_build_digest()`, `.test_previous_release_build_owner_reference_rejection_is_executable()`, `.test_retention_treats_checksum_sidecar_as_one_release_set()`, `.test_rollback_attempts_remaining_objects_after_restore_failure()`, `.test_rollback_fixture_attempts_later_restores_after_first_or_second_failure()`, `.test_rollback_keeps_pre_rollout_etroc_snapshot_as_the_invariant()`, `.test_rollback_renderer_recovers_each_partial_forward_state()`, `.test_rollback_renderer_rejects_same_name_with_new_uid()`, `.test_rollback_replaces_only_restore_marked_objects()`, `.test_rollback_scope_captures_and_restores_service_and_route_fail_closed()`, `.test_runtime_http_montage_bytes_equal_the_published_digest()`, `.test_storage_measurement_uses_afs_then_df_and_rejects_malformed_output()`, `.test_topology_inventory_covers_every_service_and_route_selecting_live_pods()`, `.test_topology_pins_oauth_proxy_to_captured_digest_not_merely_a_digest()`, `test_lxplus_dashboard_deploy.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 12`** (19 nodes): `ETROCReviewFrontendTests`, `.node()`, `.test_active_record_scientific_context_contract()`, `.test_candidate_priority_filter_and_remote_save_next_refresh()`, `.test_controller_montage_generation_ignores_stale_bytes_and_revokes_urls()`, `.test_controller_queue_snapshot_and_direct_open_modes()`, `.test_controller_revokes_a_verified_url_when_image_decode_fails()`, `.test_generation_gate_rejects_stale_async_completion_and_requires_active_verified_blob()`, `.test_mutation_identity_and_conflict_draft_contract()`, `.test_position_human_label_and_target_only_mode_contract()`, `.test_position_publication_reconciliation_and_target_queue_are_fail_closed()`, `.test_reconciliation_rejects_review_with_mismatched_provenance()`, `.test_same_byte_publication_event_derives_dataset_identity_before_reconciliation()`, `.test_save_and_history_envelopes_require_exact_evidence_event_and_chain()`, `.test_stale_decode_revokes_only_its_local_object_url()`, `.test_successful_save_uses_validated_refreshed_current_not_post_envelope()`, `.test_verified_evidence_contract_and_queue_are_fail_closed()`, `.test_workspace_markup_and_safe_dom_contract()`, `test_etroc_review_frontend.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (15 nodes): `AnalyticsDashboardTests`, `.test_additional_test_failure_marks_table_cells_unavailable()`, `.test_additional_tests_use_live_registry_api_and_safe_badges()`, `.test_dashboard_does_not_change_canonical_hybrid_inventory()`, `.test_dashboard_does_not_present_absence_of_optical_candidate_as_review_ready()`, `.test_dashboard_exposes_semantic_chart_regions_and_scientific_caveat()`, `.test_dashboard_handles_untrusted_group_labels_and_pending_rows_safely()`, `.test_dashboard_script_uses_existing_rows_and_live_comment_summary()`, `.test_dashboard_styles_are_responsive_and_respect_reduced_motion()`, `.test_live_updates_are_announced_and_only_animate_the_reviewed_counter()`, `.test_main_page_loads_local_dashboard_assets_and_places_dashboard_first()`, `.test_table_csv_export_contract()`, `.test_table_filters_and_sorting_are_keyboard_and_screen_reader_accessible()`, `.test_table_has_static_advanced_tests_column_for_every_hybrid()`, `test_analytics_dashboard.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (9 nodes): `LxplusAdditionalTestsDeployTests`, `.test_candidate_probe_precedes_production_mutation()`, `.test_exact_candidate_image_uses_real_startup_probe_contract()`, `.test_external_sso_gate_retries_without_client_identity_header()`, `.test_forward_deployment_normalizes_localhost_probes()`, `.test_helper_has_valid_bash_syntax()`, `.test_helper_pins_advanced_table_csv_release()`, `.test_rollback_renderer_rejects_same_name_with_new_uid()`, `test_lxplus_additional_tests_deploy.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (6 nodes): `HybridPairCorrectionTests`, `.test_concordance_snapshot_uses_the_corrected_comment_target()`, `.test_corrected_detail_page_keeps_an_old_url_redirect()`, `.test_dashboard_uses_only_the_corrected_w04f2_81_slug()`, `.test_manifest_preserves_w04f2_34_and_corrects_w04f2_81()`, `test_hybrid_pair_correction.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `append()` connect `Community 2` to `Community 0`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 13`?**
  _High betweenness centrality (0.311) - this node is a cross-community bridge._
- **Why does `append()` connect `Community 2` to `Community 3`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 11`, `Community 13`?**
  _High betweenness centrality (0.232) - this node is a cross-community bridge._
- **Why does `LxplusDashboardDeployTests` connect `Community 1` to `Community 9`, `Community 2`?**
  _High betweenness centrality (0.212) - this node is a cross-community bridge._
- **Are the 45 inferred relationships involving `append()` (e.g. with `.handle_data()` and `.handle_endtag()`) actually correct?**
  _`append()` has 45 INFERRED edges - model-reasoned connections that need verification._
- **Are the 39 inferred relationships involving `append()` (e.g. with `.handle_data()` and `.handle_endtag()`) actually correct?**
  _`append()` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `init_db()` (e.g. with `.test_required_missing_manifest_fails_before_database_mutation()` and `.test_incompatible_partial_schema_rolls_back_all_migration_changes()`) actually correct?**
  _`init_db()` has 25 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Normalize API-defaulted empty containers without hiding non-empty drift.` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._