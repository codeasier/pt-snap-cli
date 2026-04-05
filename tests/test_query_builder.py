"""Tests for query builder."""

import pytest

from pt_snap_analyzer.query.builder import QueryBuilder
from pt_snap_analyzer.query.condition import And, Equal, GreaterThan, In, Or


class TestQueryBuilder:
    def test_basic_select(self):
        builder = QueryBuilder()
        sql, params = builder.from_table("trace_entry_0").build()
        assert sql == "SELECT * FROM trace_entry_0"
        assert params == []

    def test_select_specific_columns(self):
        builder = QueryBuilder()
        sql, params = (
            builder.from_table("trace_entry_0")
            .columns("id", "address", "size")
            .build()
        )
        assert sql == "SELECT id, address, size FROM trace_entry_0"
        assert params == []

    def test_where_clause(self):
        builder = QueryBuilder()
        sql, params = (
            builder.from_table("trace_entry_0")
            .where(Equal("status", "active"))
            .build()
        )
        assert "WHERE" in sql
        assert "(status = ?)" in sql
        assert params == ["active"]

    def test_multiple_where_clauses(self):
        builder = QueryBuilder()
        sql, params = (
            builder.from_table("trace_entry_0")
            .where(Equal("status", "active"))
            .where(GreaterThan("size", 1024))
            .build()
        )
        assert "WHERE" in sql
        assert "(status = ?)" in sql
        assert "(size > ?)" in sql
        assert "AND" in sql
        assert params == ["active", 1024]

    def test_order_by(self):
        builder = QueryBuilder()
        sql, params = (
            builder.from_table("trace_entry_0")
            .order_by("size", descending=True)
            .build()
        )
        assert "ORDER BY size DESC" in sql

    def test_order_by_multiple(self):
        builder = QueryBuilder()
        sql, params = (
            builder.from_table("trace_entry_0")
            .order_by("status")
            .order_by("size", descending=True)
            .build()
        )
        assert "ORDER BY status, size DESC" in sql

    def test_group_by(self):
        builder = QueryBuilder()
        sql, params = (
            builder.from_table("trace_entry_0")
            .group_by("eventType")
            .build()
        )
        assert "GROUP BY eventType" in sql

    def test_limit(self):
        builder = QueryBuilder()
        sql, params = (
            builder.from_table("trace_entry_0")
            .limit(100)
            .build()
        )
        assert "LIMIT 100" in sql

    def test_offset(self):
        builder = QueryBuilder()
        sql, params = (
            builder.from_table("trace_entry_0")
            .limit(100)
            .offset(50)
            .build()
        )
        assert "LIMIT 100" in sql
        assert "OFFSET 50" in sql

    def test_full_query(self):
        builder = QueryBuilder()
        sql, params = (
            builder.from_table("trace_entry_0")
            .columns("id", "address", "size")
            .where(Equal("status", "active"))
            .where(GreaterThan("size", 1024))
            .order_by("size", descending=True)
            .limit(100)
            .build()
        )
        assert sql.startswith("SELECT id, address, size FROM trace_entry_0")
        assert "WHERE" in sql
        assert "ORDER BY size DESC" in sql
        assert "LIMIT 100" in sql
        assert params == ["active", 1024]

    def test_no_table_raises(self):
        builder = QueryBuilder()
        with pytest.raises(ValueError, match="Table must be set"):
            builder.build()

    def test_reset(self):
        builder = QueryBuilder()
        builder.from_table("trace_entry_0").where(Equal("a", 1)).limit(10)
        builder.reset()
        with pytest.raises(ValueError):
            builder.build()

    def test_in_condition(self):
        builder = QueryBuilder()
        sql, params = (
            builder.from_table("trace_entry_0")
            .where(In("eventType", ["alloc", "free"]))
            .build()
        )
        assert "eventType IN (?, ?)" in sql
        assert params == ["alloc", "free"]

    def test_combined_conditions(self):
        builder = QueryBuilder()
        cond = And([
            Equal("status", "active"),
            Or([
                Equal("type", "malloc"),
                Equal("type", "cudaMalloc"),
            ]),
        ])
        sql, params = (
            builder.from_table("trace_entry_0")
            .where(cond)
            .build()
        )
        assert "WHERE" in sql
        assert "AND" in sql
        assert "OR" in sql
