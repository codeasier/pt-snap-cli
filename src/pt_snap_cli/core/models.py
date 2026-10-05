from __future__ import annotations

# pyright: reportAny=error, reportExplicitAny=error, reportUnknownArgumentType=error, reportUnknownVariableType=error, reportUnknownMemberType=error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pt_snap_cli.config import FocusSource

CacheMissReason = Literal[
    "database_missing",
    "database_invalid",
    "metadata_missing",
    "metadata_invalid",
    "metadata_version_unsupported",
    "source_changed",
    "import_format_changed",
    "device_changed",
    "forced",
    "dataset_identity_changed",
]
MetadataStatus = Literal["available", "unavailable", "invalid"]
SplitFormat = Literal["pickle", "json"]
SkillHost = Literal["agents", "claude", "cursor", "codex", "custom"]
SkillScope = Literal["user", "project"]
SKILL_CONFIG_ENV: dict[str, str] = {
    "claude": "CLAUDE_CONFIG_DIR",
    "codex": "CODEX_HOME",
}
SkillStatus = Literal["installed", "outdated", "missing"]
SkillInstallAction = Literal[
    "installed",
    "updated",
    "already_installed",
    "not_installed",
    "uninstalled",
]
SKILL_RESTART_ACTIONS: frozenset[SkillInstallAction] = frozenset(
    {"installed", "updated", "uninstalled"}
)
SKILL_RESTART_HINT = (
    "Restart the agent after install, upgrade, or uninstall so the skill change takes effect."
)
SKILL_HOSTS: tuple[SkillHost, ...] = ("agents", "claude", "cursor", "codex")
SKILL_SCOPES: tuple[SkillScope, ...] = ("user", "project")


@dataclass(frozen=True)
class ResolvedFocus:
    db_path: Path | None
    device_id: int | None
    source: FocusSource
    focus_file: Path | None = None

    @property
    def is_configured(self) -> bool:
        return self.db_path is not None


@dataclass(frozen=True)
class FocusState:
    db_path: Path | None
    device_id: int | None
    available_devices: list[int] = field(default_factory=list)
    source: FocusSource = "none"
    focus_file: Path | None = None
    callstack_layout: str | None = None
    callstack_layout_error: str | None = None


@dataclass(frozen=True)
class TemplateParameter:
    type: str
    default: object | None
    required: bool
    description: str
    choices: list[object] | None = None


@dataclass(frozen=True)
class TemplateSummary:
    name: str
    description: str
    category: str | None


@dataclass(frozen=True)
class TemplateInfo:
    name: str
    description: str
    category: str | None
    devices: str | None
    parameters: dict[str, TemplateParameter]
    output_schema: list[dict[str, object]] | None
    semantics_version: int | None = None
    interpretation_limits: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class QueryResult:
    total: int
    returned: int
    device_id: int | None
    rows: list[dict[str, object]]
    template: str | None = None
    semantics_version: int | None = None
    has_more: bool = False
    truncated: bool = False
    total_is_exact: bool = False
    timeout_s: float | None = None
    scope: dict[str, object] | None = None


@dataclass(frozen=True)
class PeakMemoryReport:
    device_id: int | None
    metric: str
    event_id: int | None
    peak: dict[str, object]
    allocator_gap: dict[str, object] | None
    callstack_groups: list[dict[str, object]]
    has_more: bool = False
    truncated: bool = False
    total_is_exact: bool = False
    effective_params: dict[str, object] = field(default_factory=dict)
    included_bytes: int = 0
    percent_denominator: str = "included_bytes"
    active_bytes_at_event: int | None = None
    coverage_percent: float | None = None
    source_coverage: dict[str, object] | None = None


@dataclass(frozen=True)
class ImportOptions:
    """Options for `pt-snap import`.

    Attributes:
        snapshot_file: Path to the input `.pkl` or `.pickle` snapshot.
        output_dir: Parent of the generated standalone DB or native dataset.
            Defaults to the snapshot file's parent directory.
        events_per_slice: Positive real-event capacity per device shard; None
            preserves standalone behavior unless msinsight is explicit (500000).
            Negative boundaries do not count.
        format: None selects single-db or pt-snap-native-v2 from capacity;
            msinsight/compatibility-v1 explicitly selects fixed-target inline v1.
        device: Optional device id to focus on. When None, all available
            devices are imported.
        set_focus: When True (default), also write project focus so subsequent
            `pt-snap query` / `pt-snap report` commands reuse the new DB.
    """

    snapshot_file: Path
    output_dir: Path | None = None
    device: int | None = None
    set_focus: bool = True
    force: bool = False
    events_per_slice: int | None = None
    format: str | None = None


@dataclass(frozen=True)
class ImportMetadata:
    metadata_schema_version: int
    import_format_version: int
    source_sha256: str
    source_size: int
    source_name: str
    requested_device: int | None
    importer_name: str
    importer_version: str
    completed_at: str


@dataclass(frozen=True)
class MetadataInspection:
    db_path: Path
    status: MetadataStatus
    metadata: ImportMetadata | None = None
    reason: CacheMissReason | None = None


@dataclass(frozen=True)
class CacheDecision:
    reused: bool
    metadata: ImportMetadata | None
    reason: CacheMissReason | None


@dataclass(frozen=True)
class ImportResult:
    """Result of `pt-snap import`.

    Attributes:
        db_path: Path to the standalone SQLite database or native dataset directory.
        dataset_path: Native dataset directory, or None for standalone imports.
        devices/slice_count/omitted_devices: Complete native output inventory.
        device_id: Device id used during import, or None when not specified.
        focus_state: The FocusState written to project focus when
            options.set_focus is True, otherwise None.
    """

    db_path: Path
    device_id: int | None
    focus_state: FocusState | None
    reused: bool
    metadata: ImportMetadata
    cache_miss_reason: CacheMissReason | None
    dataset_path: Path | None = None
    devices: tuple[int, ...] = ()
    slice_count: int = 0
    format: str = "single-db"
    omitted_devices: tuple[int, ...] = ()


@dataclass(frozen=True)
class SplitOptions:
    snapshot_file: Path
    output: Path
    device: int | None = None
    slices: int | None = None
    max_entries: int | None = None
    format: str = "pickle"


@dataclass(frozen=True)
class SplitResult:
    output: Path
    files: tuple[Path, ...]
    devices: tuple[int, ...]
    format: SplitFormat


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    source_dir: Path


@dataclass(frozen=True)
class SkillLocationStatus:
    host: SkillHost
    scope: SkillScope
    path: Path
    status: SkillStatus


@dataclass(frozen=True)
class SkillListing:
    name: str
    description: str
    source_dir: Path
    status: SkillStatus
    locations: list[SkillLocationStatus]


@dataclass(frozen=True)
class SkillInstallResult:
    name: str
    host: SkillHost
    scope: SkillScope
    path: Path
    action: SkillInstallAction


@dataclass(frozen=True)
class SkillInstallReport:
    results: list[SkillInstallResult]


@dataclass(frozen=True)
class DeviceTraceBounds:
    device_id: int
    first_event_id: int | None
    last_event_id: int | None


@dataclass(frozen=True)
class DatabaseOverview:
    db_path: Path
    focus_source: FocusSource
    devices: list[DeviceTraceBounds]
    metadata: MetadataInspection
    dataset: dict[str, object] | None = None


@dataclass(frozen=True)
class CapabilityCatalog:
    cli_version: str
    templates: list[TemplateInfo]
    skills: list[SkillListing]
