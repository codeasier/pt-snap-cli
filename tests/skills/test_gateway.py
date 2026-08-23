from pathlib import Path

import pytest

from tests.skills.harness.descriptors import load_suite
from tests.skills.harness.gateway import RecordingToolGateway, ToolDeniedError

SUITE_PATH = Path("tests/skills/suites/pt-snap-memory-leak/suite.yaml")


def test_gateway_records_success_and_tool_errors() -> None:
    suite = load_suite(SUITE_PATH)

    def executor(operation: str, arguments: dict):
        if arguments.get("fail"):
            raise RuntimeError("query failed")
        return {"operation": operation, "rows": 1}

    gateway = RecordingToolGateway(suite, executor)

    assert gateway.call("pt_snap.metadata", {"database": "/fixtures/cache.db"}) == {
        "operation": "pt_snap.metadata",
        "rows": 1,
    }
    with pytest.raises(RuntimeError, match="query failed"):
        gateway.call("pt_snap.query", {"fail": True})

    assert [call.status for call in gateway.calls] == ["success", "error"]
    assert gateway.calls[0].output == {"operation": "pt_snap.metadata", "rows": 1}
    assert gateway.calls[1].error == "RuntimeError: query failed"


def test_gateway_records_and_denies_forbidden_operations() -> None:
    suite = load_suite(SUITE_PATH)
    gateway = RecordingToolGateway(suite, lambda operation, arguments: None)

    with pytest.raises(ToolDeniedError, match="diagnostic-readonly"):
        gateway.call("pt_snap.import", {"source": "/fixtures/input.pkl"})

    assert gateway.calls[0].operation == "pt_snap.import"
    assert gateway.calls[0].status == "denied"
