"""Tests for query executor."""

import pytest

from pt_snap_analyzer.query.config import QueryParameter, QueryTemplate
from pt_snap_analyzer.query.executor import QueryExecutor, TemplateRenderError


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
