"""One shared, explicit per-template dataset execution support matrix."""

DATASET_SUPPORT: dict[str, str] = {
    "event": "real_events_global_filter_sort_page",
    "allocation": "real_events_global_filter_sort_page",
    "memory_peak": "independent_real_counter_peaks_earliest_id",
    "allocator_gap": "global_peaks_same_event_counters",
    "active_blocks_at_event": "owner_event_active_set_cross_slice_sources",
    "active_memory_callstack_at_event": "owner_event_global_source_groups_before_top_n",
    "preexisting_live": "owner_event_preexisting_occupancy",
    "block": "proved_lifecycles_dedup_latest_observation",
    "freed_block_lifetime": "proved_completed_lifecycles_once",
    "leak_detection": "terminal_dataset_dynamic_survivors_not_confirmed_leaks",
    "callstack_analysis": "all_real_stack_bearing_actions_global_identity_weighted_stats",
}


def dataset_support(name: str, packaged: bool) -> dict[str, object]:
    semantics = DATASET_SUPPORT.get(name) if packaged else None
    return {
        "supported": semantics is not None,
        "semantics": semantics,
        "device_scope": "one_selected_device; never sum device peaks",
        "custom_sql": "unsupported; select an explicit standalone member",
        "work_limit_rows": 100_000,
        "work_limit_bytes": 64 * 1024 * 1024,
        "budget_scope": "one_query_or_explicit_report_composition",
    }
