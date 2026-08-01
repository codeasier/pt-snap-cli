from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

FocusSource = Literal["explicit", "env", "project", "global", "none"]
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
]
MetadataStatus = Literal["available", "unavailable", "invalid"]
SplitFormat = Literal["pickle", "json"]


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


@dataclass(frozen=True)
class TemplateParameter:
    type: str
    default: object | None
    required: bool
    description: str


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
    output_schema: list[dict[str, str]] | None


@dataclass(frozen=True)
class QueryResult:
    total: int
    returned: int
    device_id: int | None
    rows: list[dict[str, Any]]


@dataclass(frozen=True)
class PeakMemoryReport:
    device_id: int | None
    metric: str
    event_id: int | None
    peak: dict[str, Any]
    allocator_gap: dict[str, Any] | None
    callstack_groups: list[dict[str, Any]]


@dataclass(frozen=True)
class ImportOptions:
    """Options for `pt-snap import`.

    Attributes:
        snapshot_file: Path to the input `.pkl` or `.pickle` snapshot.
        output_dir: Directory where the generated `<name>.db` is written.
            Defaults to the snapshot file's parent directory.
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
        db_path: Path to the generated SQLite database.
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
