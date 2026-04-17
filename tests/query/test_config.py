"""Tests for query configuration."""

import pytest

from pt_snap_cli.query.config import QueryConfig, QueryParameter, QueryTemplate


class TestQueryParameter:
    def test_validate_string(self):
        param = QueryParameter(name="test", type="str", required=False)
        result = param.validate("hello")
        assert result == "hello"

    def test_validate_int(self):
        param = QueryParameter(name="test", type="int", required=False)
        result = param.validate("42")
        assert result == 42

    def test_validate_float(self):
        param = QueryParameter(name="test", type="float", required=False)
        result = param.validate("3.14")
        assert result == 3.14

    def test_validate_bool(self):
        param = QueryParameter(name="test", type="bool", required=False)
        assert param.validate("true") is True
        assert param.validate("false") is False
        assert param.validate("True") is True
        assert param.validate("False") is False
        assert param.validate("1") is True
        assert param.validate("0") is False
        assert param.validate("yes") is True
        assert param.validate(False) is False
        assert param.validate(True) is True

    def test_validate_missing_optional(self):
        param = QueryParameter(name="test", type="str", required=False, default="default")
        result = param.validate(None)
        assert result == "default"

    def test_validate_missing_required(self):
        param = QueryParameter(name="test", type="str", required=True)
        with pytest.raises(ValueError, match="Required parameter"):
            param.validate(None)

    def test_validate_invalid_type(self):
        param = QueryParameter(name="test", type="int", required=False)
        with pytest.raises(TypeError):
            param.validate("not a number")


class TestQueryTemplate:
    def test_from_dict(self):
        data = {
            "name": "test_query",
            "description": "Test query",
            "devices": ["all", "0"],
            "parameters": {
                "min_size": {
                    "type": "int",
                    "default": 1024,
                    "required": False,
                    "description": "Minimum size",
                }
            },
            "query": "SELECT * FROM table WHERE size >= {{ min_size }}",
            "output_schema": [
                {"column": "id", "type": "int"},
            ],
        }
        template = QueryTemplate.from_dict(data)
        assert template.name == "test_query"
        assert template.description == "Test query"
        assert template.devices == ["all", "0"]
        assert "min_size" in template.parameters
        assert template.parameters["min_size"].type == "int"
        assert template.category == "basic"

    def test_from_dict_with_category(self):
        data = {
            "name": "test_query",
            "description": "Test query",
            "category": "statistical",
            "query": "SELECT COUNT(*) FROM table",
        }
        template = QueryTemplate.from_dict(data)
        assert template.category == "statistical"

    def test_default_category_is_basic(self):
        template = QueryTemplate(name="test")
        assert template.category == "basic"

    def test_validate_params(self):
        template = QueryTemplate(
            name="test",
            parameters={
                "min_size": QueryParameter(name="min_size", type="int", default=0),
                "required_param": QueryParameter(name="required_param", type="str", required=True),
            },
        )
        params = {"required_param": "value", "min_size": "100"}
        validated = template.validate_params(params)
        assert validated["required_param"] == "value"
        assert validated["min_size"] == 100

    def test_validate_params_missing_required(self):
        template = QueryTemplate(
            name="test",
            parameters={
                "required_param": QueryParameter(name="required_param", type="str", required=True),
            },
        )
        with pytest.raises(ValueError):
            template.validate_params({})


class TestQueryConfig:
    def test_load_yaml_from_string(self):
        yaml_content = """
version: "1.0"
queries:
  test_query:
    description: A test query
    category: business
    devices:
      - all
    parameters:
      limit:
        type: int
        default: 100
        required: false
    query: "SELECT * FROM table LIMIT {{ limit }}"
    output_schema:
      - column: id
        type: int
"""
        config = QueryConfig.load_yaml_from_string(yaml_content)
        assert config.version == "1.0"
        assert "test_query" in config.queries
        assert config.get_query("test_query").description == "A test query"
        assert config.get_query("test_query").category == "business"

    def test_load_yaml_default_category(self):
        yaml_content = """
version: "1.0"
queries:
  no_category_query:
    description: Query without category
    query: "SELECT 1"
"""
        config = QueryConfig.load_yaml_from_string(yaml_content)
        assert config.get_query("no_category_query").category == "basic"

    def test_list_queries(self):
        config = QueryConfig(
            version="1.0",
            queries={
                "query1": QueryTemplate(name="query1"),
                "query2": QueryTemplate(name="query2"),
            },
        )
        assert set(config.list_queries()) == {"query1", "query2"}

    def test_get_query_not_found(self):
        config = QueryConfig()
        assert config.get_query("nonexistent") is None

    def test_load_yaml_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            QueryConfig.load_yaml("/nonexistent/path.yaml")
