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

    def test_validate_choices_accepts_declared_value(self):
        param = QueryParameter(name="order_by", type="str", default="id", choices=["id", "size"])
        assert param.validate("size") == "size"

    def test_validate_str_choices_are_case_insensitive_and_canonical(self):
        param = QueryParameter(name="order_dir", type="str", default="ASC", choices=["ASC", "DESC"])
        assert param.validate("desc") == "DESC"
        assert param.validate("Asc") == "ASC"

    def test_validate_choices_rejects_undeclared_value(self):
        param = QueryParameter(name="order_by", type="str", default="id", choices=["id", "size"])
        with pytest.raises(
            ValueError, match=r"'order_by' must be one of: id, size \(got '\(SELECT 1\)'\)"
        ):
            param.validate("(SELECT 1)")

    def test_validate_int_choices_match_after_conversion(self):
        param = QueryParameter(name="level", type="int", default=1, choices=[1, 2, 3])
        assert param.validate("2") == 2
        with pytest.raises(ValueError, match="'level' must be one of: 1, 2, 3"):
            param.validate("4")

    def test_validate_missing_optional_with_choices_returns_default(self):
        param = QueryParameter(name="order_dir", type="str", default="ASC", choices=["ASC", "DESC"])
        assert param.validate(None) == "ASC"

    def test_choices_default_must_be_a_choice(self):
        with pytest.raises(ValueError, match="default 'name' is not one of its choices"):
            QueryParameter(name="order_by", type="str", default="name", choices=["id", "size"])

    def test_choices_must_be_a_non_empty_list(self):
        with pytest.raises(ValueError, match="choices must be a non-empty list"):
            QueryParameter(name="order_by", type="str", choices=[])
        with pytest.raises(ValueError, match="choices must be a non-empty list"):
            QueryParameter(name="order_by", type="str", choices="id")


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

    def test_validate_params_rejects_unknown_parameter(self):
        """A misspelled filter must fail loudly instead of silently widening the query."""
        template = QueryTemplate(
            name="leak_detection",
            parameters={
                "min_size": QueryParameter(name="min_size", type="int", default=0),
                "limit": QueryParameter(name="limit", type="int", default=-1),
            },
        )
        with pytest.raises(
            ValueError,
            match=(
                r"Unknown parameter\(s\) for template 'leak_detection': min_sze "
                r"\(accepted: min_size, limit\)"
            ),
        ):
            template.validate_params({"min_sze": 1024})

    def test_validate_params_lists_every_unknown_parameter_sorted(self):
        template = QueryTemplate(
            name="test",
            parameters={"min_size": QueryParameter(name="min_size", type="int", default=0)},
        )
        with pytest.raises(ValueError, match=r"test': a_param, z_param \(accepted: min_size\)"):
            template.validate_params({"z_param": 1, "a_param": 2, "min_size": 3})

    def test_validate_params_rejects_unknown_when_template_declares_none(self):
        template = QueryTemplate(name="test", parameters={})
        with pytest.raises(ValueError, match=r"test': device_id \(accepted: none\)"):
            template.validate_params({"device_id": 0})

    def test_validate_params_applies_choices(self):
        template = QueryTemplate(
            name="test",
            parameters={
                "order_by": QueryParameter(
                    name="order_by", type="str", default="id", choices=["id", "size"]
                ),
                "order_dir": QueryParameter(
                    name="order_dir", type="str", default="ASC", choices=["ASC", "DESC"]
                ),
            },
        )
        assert template.validate_params({"order_by": "size", "order_dir": "desc"}) == {
            "order_by": "size",
            "order_dir": "DESC",
        }
        with pytest.raises(ValueError, match="'order_dir' must be one of: ASC, DESC"):
            template.validate_params({"order_dir": "SIDEWAYS"})

    def test_from_dict_reads_choices(self):
        template = QueryTemplate.from_dict(
            {
                "name": "test_query",
                "parameters": {
                    "order_dir": {
                        "type": "str",
                        "default": "ASC",
                        "choices": ["ASC", "DESC"],
                    },
                    "min_size": {"type": "int", "default": 0},
                },
                "query": "SELECT 1",
            }
        )
        assert template.parameters["order_dir"].choices == ["ASC", "DESC"]
        assert template.parameters["min_size"].choices is None


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
