"""Tests for query executor."""

import pytest

from pt_snap_cli.query.config import QueryParameter, QueryTemplate
from pt_snap_cli.query.executor import QueryExecutor, TemplateRenderError


class TestQueryExecutor:
    def test_render_simple_template(self):
        template = QueryTemplate(
            name="test",
            query="SELECT * FROM table WHERE size >= {{ min_size }}",
            parameters={
                "min_size": QueryParameter(name="min_size", type="int", default=0),
            },
        )
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env

        sql = executor.render(template, {"min_size": 1024})
        assert "SELECT * FROM table WHERE size >= 1024" == sql

    def test_render_with_device_trace_table(self):
        template = QueryTemplate(
            name="test",
            query="SELECT * FROM {{ device_trace_table }} WHERE id = 1",
            parameters={},
        )
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env

        sql = executor.render(template, {}, device_id=0)
        assert "SELECT * FROM trace_entry_0 WHERE id = 1" == sql

    def test_render_with_device_block_table(self):
        template = QueryTemplate(
            name="test",
            query="SELECT * FROM {{ device_block_table }} WHERE id = 1",
            parameters={},
        )
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env

        sql = executor.render(template, {}, device_id=0)
        assert "SELECT * FROM block_0 WHERE id = 1" == sql

    def test_render_with_conditional(self):
        template = QueryTemplate(
            name="test",
            query="SELECT * FROM table{% if filter %} WHERE type = '{{ filter }}'{% endif %}",
            parameters={
                "filter": QueryParameter(name="filter", type="str", default=None),
            },
        )
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env

        sql_with_filter = executor.render(template, {"filter": "alloc"})
        assert "WHERE type = 'alloc'" in sql_with_filter

        sql_without_filter = executor.render(template, {})
        assert "WHERE" not in sql_without_filter

    def test_render_invalid_syntax(self):
        template = QueryTemplate(
            name="test",
            query="SELECT * FROM table {% invalid %}",
            parameters={},
        )
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env

        with pytest.raises(TemplateRenderError, match="Template syntax error"):
            executor.render(template, {})

    def test_render_missing_required_param(self):
        template = QueryTemplate(
            name="test",
            query="SELECT * FROM table WHERE id = {{ id }}",
            parameters={
                "id": QueryParameter(name="id", type="int", required=True),
            },
        )
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env

        with pytest.raises(ValueError, match="Required parameter"):
            executor.render(template, {})

    def test_validate_output(self):
        executor = QueryExecutor.__new__(QueryExecutor)

        schema = [
            {"column": "id", "type": "int"},
            {"column": "name", "type": "str"},
        ]

        result = [
            {"id": 1, "name": "test", "extra": "value"},
            {"id": 2, "name": "test2"},
        ]

        assert executor.validate_output(result, schema) is True

    def test_validate_output_missing_column(self):
        executor = QueryExecutor.__new__(QueryExecutor)

        schema = [
            {"column": "id", "type": "int"},
            {"column": "required_column", "type": "str"},
        ]

        result = [
            {"id": 1, "name": "test"},
        ]

        assert executor.validate_output(result, schema) is False

    def test_validate_output_empty_result(self):
        executor = QueryExecutor.__new__(QueryExecutor)

        schema = [
            {"column": "id", "type": "int"},
        ]

        assert executor.validate_output([], schema) is True

    def test_list_templates(self):
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._configs = {}
        executor._context = None

        template = QueryTemplate(name="test_query", query="SELECT 1")
        executor.register_template(template)

        assert "test_query" in executor.list_templates()

    def test_execute_on_all_devices(self):
        """Test execute_on_all_devices runs template on each device."""
        mock_context = _make_mock_context(device_ids=[0, 1])
        executor = QueryExecutor(mock_context)
        executor.register_template(
            QueryTemplate(
                name="device_test",
                description="Test",
                query="SELECT {{ device_id }} as dev",
            )
        )

        results = executor.execute_on_all_devices("device_test")
        assert 0 in results
        assert 1 in results

    def test_execute_on_all_devices_template_not_found(self):
        """Test execute_on_all_devices raises for missing template."""
        mock_context = _make_mock_context(device_ids=[0])
        executor = QueryExecutor(mock_context)

        from pt_snap_cli.query.executor import QueryExecutionError

        with pytest.raises(QueryExecutionError, match="Template not found"):
            executor.execute_on_all_devices("nonexistent")

    def test_execute_on_all_devices_empty_device_list(self):
        """Test execute_on_all_devices with no devices returns empty dict."""
        mock_context = _make_mock_context(device_ids=[])
        executor = QueryExecutor(mock_context)
        executor.register_template(
            QueryTemplate(name="empty_test", description="Test", query="SELECT 1")
        )

        results = executor.execute_on_all_devices("empty_test")
        assert results == {}


def _make_mock_context(device_ids: list[int]):
    """Create a mock Context with the given device IDs."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.device_ids = device_ids
    return mock
