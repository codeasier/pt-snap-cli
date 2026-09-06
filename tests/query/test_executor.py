"""Tests for query executor."""

import sqlite3

import pytest

from pt_snap_cli.context import Context
from pt_snap_cli.query.config import QueryParameter, QueryTemplate
from pt_snap_cli.query.executor import QueryExecutionError, QueryExecutor, TemplateRenderError


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
        executor._compiled_cache = {}

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
        executor._compiled_cache = {}

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
        executor._compiled_cache = {}

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
        executor._compiled_cache = {}

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
        executor._compiled_cache = {}

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
        executor._compiled_cache = {}

        with pytest.raises(TemplateRenderError, match="Required parameter"):
            executor.render(template, {})

    def test_render_invalid_parameter_type_is_normalized(self):
        template = QueryTemplate(
            name="test",
            query="SELECT {{ count }}",
            parameters={
                "count": QueryParameter(name="count", type="int", required=True),
            },
        )
        executor = QueryExecutor(context=None)

        with pytest.raises(TemplateRenderError, match="cannot be converted to int"):
            executor.render(template, {"count": "invalid"})

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

    def test_max_rows_appends_limit_when_template_has_none(self) -> None:
        """A positive max_rows must be pushed down as LIMIT for templates
        that don't already declare one (e.g. ``leak_detection``)."""
        template = QueryTemplate(
            name="no_limit",
            query="SELECT id FROM t ORDER BY id",
            parameters={},
        )
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env
        executor._compiled_cache = {}

        sql = executor.render(template, {}, max_rows=5)
        assert sql.endswith("LIMIT 5"), sql

    def test_max_rows_uses_template_limit_when_template_owns_one(self) -> None:
        """When the template already exposes ``limit`` via ``LIMIT {{ limit }}``
        the executor must inject the effective limit into that variable
        instead of appending a second LIMIT clause."""
        template = QueryTemplate(
            name="with_limit",
            query="SELECT id FROM t ORDER BY id LIMIT {{ limit|int }}",
            parameters={
                "limit": QueryParameter(name="limit", type="int", default=-1),
            },
        )
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env
        executor._compiled_cache = {}

        sql = executor.render(template, {}, max_rows=5)
        # Exactly one LIMIT and it carries the pushed-down value.
        upper = sql.upper()
        assert upper.count("LIMIT") == 1
        assert sql.endswith("LIMIT 5"), sql

    def test_max_rows_zero_or_none_keeps_template_default(self) -> None:
        """``max_rows <= 0`` (including None) must not override the
        template's default LIMIT, so a template with ``LIMIT -1`` stays
        unlimited."""
        template = QueryTemplate(
            name="with_limit",
            query="SELECT id FROM t LIMIT {{ limit|int }}",
            parameters={
                "limit": QueryParameter(name="limit", type="int", default=-1),
            },
        )
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env
        executor._compiled_cache = {}

        assert executor.render(template, {}, max_rows=None).endswith("LIMIT -1")
        assert executor.render(template, {}, max_rows=0).endswith("LIMIT -1")
        assert executor.render(template, {}, max_rows=-1).endswith("LIMIT -1")

    def test_max_rows_min_of_template_and_caller(self) -> None:
        """If the user also passes ``params={'limit': 3}``, the effective
        limit pushed to SQL is min(template_limit, max_rows)."""
        template = QueryTemplate(
            name="with_limit",
            query="SELECT id FROM t LIMIT {{ limit|int }}",
            parameters={
                "limit": QueryParameter(name="limit", type="int", default=-1),
            },
        )
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env
        executor._compiled_cache = {}

        # Template limit (3) is smaller than max_rows (10): use 3.
        assert executor.render(template, {"limit": 3}, max_rows=10).endswith("LIMIT 3")
        # max_rows (10) is smaller than template limit (50): use 10.
        assert executor.render(template, {"limit": 50}, max_rows=10).endswith("LIMIT 10")
        # Zero is an explicit empty result, not an unlimited value.
        assert executor.render(template, {"limit": 0}, max_rows=10).endswith("LIMIT 0")

    def test_max_rows_does_not_double_limit(self) -> None:
        """Templates that cap rows with a non-``limit`` variable (e.g.
        ``top_n``) keep their own LIMIT and the executor must not append
        a second one."""
        template = QueryTemplate(
            name="with_top_n",
            query="SELECT callstack FROM t GROUP BY callstack LIMIT {{ top_n|int }}",
            parameters={
                "top_n": QueryParameter(name="top_n", type="int", default=20),
            },
        )
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env
        executor._compiled_cache = {}

        sql = executor.render(template, {}, max_rows=100)
        # ``LIMIT`` appears exactly once and reflects the template's own
        # ``top_n`` default, not the caller's ``max_rows``.
        assert sql.upper().count("LIMIT") == 1
        assert sql.endswith("LIMIT 20"), sql

    def test_max_rows_tightens_non_limit_template_cap(self) -> None:
        """A caller cap must also tighten templates that use ``top_n``."""
        template = QueryTemplate(
            name="with_top_n",
            query="SELECT callstack FROM t GROUP BY callstack LIMIT {{ top_n|int }}",
            parameters={
                "top_n": QueryParameter(name="top_n", type="int", default=20),
            },
        )
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env
        executor._compiled_cache = {}

        sql = executor.render(template, {}, max_rows=5)

        assert sql.upper().count("LIMIT") == 1
        assert sql.endswith("LIMIT 5"), sql

    def test_jinja_template_compiled_once_per_template(self) -> None:
        """Long-lived executors (MCP server) must avoid re-parsing the
        same template body on every render call."""
        template = QueryTemplate(
            name="cached",
            query="SELECT {{ device_id }}",
            parameters={},
        )
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env
        executor._compiled_cache = {}

        first = executor._compiled_template(template)
        second = executor._compiled_template(template)
        assert first is second
        assert ("cached", template.query) in executor._compiled_cache

    def test_jinja_cache_distinguishes_same_name_with_new_query(self) -> None:
        first_template = QueryTemplate(name="cached", query="SELECT 1")
        second_template = QueryTemplate(name="cached", query="SELECT 2")
        executor = QueryExecutor.__new__(QueryExecutor)
        executor._env = QueryExecutor(context=None)._env
        executor._compiled_cache = {}

        first = executor._compiled_template(first_template)
        second = executor._compiled_template(second_template)

        assert first is not second
        assert len(executor._compiled_cache) == 2

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

    def test_legacy_callstack_schema_error_is_actionable(self, tmp_path):
        db_path = tmp_path / "legacy.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE dictionary (table_name TEXT)")
            conn.execute("CREATE TABLE trace_entry_0 " "(id INTEGER, callstack TEXT)")
        executor = QueryExecutor(Context(db_path))
        executor.register_template(
            QueryTemplate(
                name="legacy_callstack",
                query="SELECT callstack FROM callstack",
            )
        )

        with pytest.raises(QueryExecutionError, match="legacy inline-callstack layout"):
            executor.execute_template("legacy_callstack", device_id=0)


def _make_mock_context(device_ids: list[int]):
    """Create a mock Context with the given device IDs."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.device_ids = device_ids
    return mock
