from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .descriptors import EvalCase, EvalSuite
from .grader import RunRecord


@dataclass(frozen=True)
class RunRequest:
    suite: EvalSuite
    case: EvalCase
    working_directory: Path


class AgentRunner(Protocol):
    """Adapter boundary for fresh-session local agent implementations."""

    def run(self, request: RunRequest) -> RunRecord: ...


@dataclass(frozen=True)
class ScriptedRunner:
    """Deterministic runner used to test policy and grading without a model."""

    record: RunRecord

    def run(self, request: RunRequest) -> RunRecord:
        return self.record
