"""Tests for query registry."""

from pt_snap_cli.query.config import QueryParameter, QueryTemplate
from pt_snap_cli.query.registry import (
    QueryRegistry,
    _load_all_templates,
    get_query,
    get_template_info,
    list_by_category,
    list_by_category_with_details,
    list_queries,
    list_queries_with_details,
    register_query,
)


class TestQueryRegistry:
    def setup_method(self):
        QueryRegistry.reset()
        self.registry = QueryRegistry()

    def test_register_and_get(self):
        template = QueryTemplate(name="test_query", query="SELECT 1")
        self.registry.register(template)

        result = self.registry.get("test_query")
        assert result is not None
        assert result.name == "test_query"

    def test_get_nonexistent(self):
        result = self.registry.get("nonexistent")
        assert result is None

    def test_register_factory(self):
        def factory():
            return QueryTemplate(name="factory_query", query="SELECT 2")

        self.registry.register_factory("factory_query", factory)

        result = self.registry.get("factory_query")
        assert result is not None
        assert result.name == "factory_query"

    def test_list_queries(self):
        self.registry.register(QueryTemplate(name="query1", query="SELECT 1"))
        self.registry.register(QueryTemplate(name="query2", query="SELECT 2"))

        queries = self.registry.list_queries()
        assert "query1" in queries
        assert "query2" in queries

    def test_unregister(self):
        self.registry.register(QueryTemplate(name="to_remove", query="SELECT 1"))

        removed = self.registry.unregister("to_remove")
        assert removed is True
        assert self.registry.get("to_remove") is None

    def test_unregister_nonexistent(self):
        removed = self.registry.unregister("nonexistent")
        assert removed is False


class TestModuleFunctions:
    def setup_method(self):
        QueryRegistry.reset()

    def test_register_query_function(self):
        template = QueryTemplate(name="module_query", query="SELECT 1")
        register_query(template)

        result = get_query("module_query")
        assert result is not None
        assert result.name == "module_query"

    def test_list_queries_function(self):
        register_query(QueryTemplate(name="q1", query="SELECT 1"))
        register_query(QueryTemplate(name="q2", query="SELECT 2"))

        queries = list_queries()
        assert "q1" in queries
        assert "q2" in queries

    def test_list_queries_with_details(self):
        template1 = QueryTemplate(
            name="detailed_query1", description="First detailed query", query="SELECT 1"
        )
        template2 = QueryTemplate(
            name="detailed_query2", description="Second detailed query", query="SELECT 2"
        )
        register_query(template1)
        register_query(template2)

        details = list_queries_with_details()
        assert len(details) >= 2

        found_q1 = False
        found_q2 = False
        for detail in details:
            if detail["name"] == "detailed_query1":
                assert detail["description"] == "First detailed query"
                found_q1 = True
            elif detail["name"] == "detailed_query2":
                assert detail["description"] == "Second detailed query"
                found_q2 = True

        assert found_q1 and found_q2

    def test_get_template_info(self):
        template = QueryTemplate(
            name="info_query",
            description="Query for testing info",
            query="SELECT * FROM blocks WHERE device_id = ?",
            devices=[0, 1],
            parameters={
                "device_id": QueryParameter(
                    name="device_id",
                    type="int",
                    default=0,
                    required=False,
                    description="Device ID to filter",
                ),
                "min_size": QueryParameter(
                    name="min_size",
                    type="int",
                    default=None,
                    required=True,
                    description="Minimum block size",
                ),
            },
            output_schema=[
                {"column": "block_id", "type": "int"},
                {"column": "size", "type": "int"},
            ],
        )
        register_query(template)

        info = get_template_info("info_query")
        assert info is not None
        assert info["name"] == "info_query"
        assert info["description"] == "Query for testing info"
        assert info["devices"] == [0, 1]
        assert "device_id" in info["parameters"]
        assert "min_size" in info["parameters"]
        assert info["parameters"]["device_id"]["type"] == "int"
        assert info["parameters"]["device_id"]["default"] == 0
        assert info["parameters"]["device_id"]["required"] is False
        assert info["parameters"]["min_size"]["required"] is True
        assert len(info["output_schema"]) == 2
        assert info["query"] == "SELECT * FROM blocks WHERE device_id = ?"

    def test_get_template_info_nonexistent(self):
        info = get_template_info("nonexistent_template")
        assert info is None

    def test_get_template_info_without_parameters(self):
        template = QueryTemplate(
            name="simple_query",
            description="Simple query without parameters",
            query="SELECT COUNT(*) FROM blocks",
        )
        register_query(template)

        info = get_template_info("simple_query")
        assert info is not None
        assert info["parameters"] == {}
        assert info["output_schema"] == [] or info["output_schema"] is None

    def test_registry_singleton(self):
        registry1 = QueryRegistry()
        registry2 = QueryRegistry()
        assert registry1 is registry2

    def test_registry_reset(self):
        register_query(QueryTemplate(name="test", query="SELECT 1"))
        assert get_query("test") is not None

        QueryRegistry.reset()
        new_registry = QueryRegistry()
        assert new_registry.get("test") is None


class TestListByCategory:
    def setup_method(self):
        QueryRegistry.reset()
        _load_all_templates()

    def test_list_by_category_basic(self):
        register_query(QueryTemplate(name="test_basic", query="SELECT 1", category="basic"))

        result = list_by_category("basic")
        assert "test_basic" in result
        # Packaged basic templates should also be present
        assert "active_blocks" in result

    def test_list_by_category_statistical(self):
        register_query(
            QueryTemplate(name="test_stat", query="SELECT COUNT(*)", category="statistical")
        )

        result = list_by_category("statistical")
        assert "test_stat" in result
        assert "memory_peak" in result

    def test_list_by_category_business(self):
        register_query(QueryTemplate(name="test_biz", query="SELECT 1", category="business"))

        result = list_by_category("business")
        assert "test_biz" in result
        assert "leak_detection" in result

    def test_list_by_category_with_details(self):
        register_query(
            QueryTemplate(
                name="test_detail", description="Test detail", query="SELECT 1", category="basic"
            )
        )

        result = list_by_category_with_details("basic")
        # Should include our registered template
        names = [d["name"] for d in result]
        assert "test_detail" in names
        detail = next(d for d in result if d["name"] == "test_detail")
        assert detail["description"] == "Test detail"

    def test_list_by_category_unknown_returns_empty(self):
        result = list_by_category("nonexistent")
        assert result == []
