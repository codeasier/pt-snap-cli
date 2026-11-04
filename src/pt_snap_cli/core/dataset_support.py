"""One shared, explicit per-template dataset execution support matrix."""

from pt_snap_cli.core.query_limits import QueryLimits

DATASET_SUPPORT: dict[str, str] = {
    "event": "real_events_global_filter_sort_page",
    "allocation": "real_events_global_filter_sort_page",
    "memory_peak": "independent_real_counter_peaks_earliest_id",
    "allocator_gap": "global_peaks_same_event_counters",
    "active_blocks_at_event": "owner_event_active_set_cross_slice_sources",
    "active_memory_callstack_at_event": "owner_event_global_source_groups_before_top_n",
    "active_memory_frame_tree_at_event": "owner_event_caller_paths_cross_slice_ordered_frames",
    "preexisting_live": "owner_event_preexisting_occupancy",
    "block": "proved_lifecycles_dedup_latest_observation",
    "freed_block_lifetime": "proved_completed_lifecycles_once",
    "leak_detection": "terminal_dataset_dynamic_survivors_not_confirmed_leaks",
    "callstack_analysis": "all_real_stack_bearing_actions_global_identity_weighted_stats",
}


def dataset_support(
    name: str, packaged: bool, limits: QueryLimits | None = None
) -> dict[str, object]:
    limits = limits if limits is not None else QueryLimits()
    semantics = DATASET_SUPPORT.get(name) if packaged else None
    return {
        "supported": semantics is not None,
        "semantics": semantics,
        "device_scope": "one_selected_device; never sum device peaks",
        "custom_sql": "unsupported; select an explicit standalone member",
        "work_limit_rows": limits.max_work_rows,
        "work_limit_bytes": limits.max_work_bytes,
        "max_scratch_db_bytes": limits.max_scratch_db_bytes,
        "budget_scope": "one_query_or_explicit_report_composition",
    }
