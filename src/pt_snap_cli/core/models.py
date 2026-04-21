from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

FocusSource = Literal["explicit", "env", "project", "global", "none"]


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
