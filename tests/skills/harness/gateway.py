from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .descriptors import EvalSuite
from .grader import ToolCall


class ToolDeniedError(PermissionError):
    """Raised after a disallowed operation is recorded in the run trace."""


ToolExecutor = Callable[[str, dict[str, Any]], Any]


@dataclass
class RecordingToolGateway:
    """Allowlist semantic operations and retain the evidence-bearing trace."""

    suite: EvalSuite
    executor: ToolExecutor
    _calls: list[ToolCall] = field(default_factory=list, init=False)

    @property
    def calls(self) -> tuple[ToolCall, ...]:
        return tuple(self._calls)

    def call(self, operation: str, arguments: dict[str, Any]) -> Any:
        call_id = f"call-{len(self._calls) + 1}"
        if (
            operation in self.suite.forbidden_operations
            or operation not in self.suite.allowed_operations
        ):
            error = f"operation denied by {self.suite.profile} policy: {operation}"
            self._calls.append(
                ToolCall(call_id, operation, dict(arguments), status="denied", error=error)
            )
            raise ToolDeniedError(error)
        if len(self._calls) >= self.suite.max_calls:
            error = f"tool call budget exceeded: {self.suite.max_calls}"
            self._calls.append(
                ToolCall(call_id, operation, dict(arguments), status="denied", error=error)
            )
            raise ToolDeniedError(error)

        try:
            output = self.executor(operation, dict(arguments))
        except Exception as exc:
            self._calls.append(
                ToolCall(
                    call_id,
                    operation,
                    dict(arguments),
                    status="error",
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            raise
        self._calls.append(
            ToolCall(call_id, operation, dict(arguments), status="success", output=output)
        )
        return output
