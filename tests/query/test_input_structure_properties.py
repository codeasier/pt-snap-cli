"""Bounded loader shape regressions, not a new closed YAML schema."""

from __future__ import annotations

import copy
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from pt_snap_cli.query import config as config_module
from pt_snap_cli.query.config import QueryConfig, QueryTemplate

PROPERTY_SETTINGS = settings(
    max_examples=25, derandomize=True, database=None, deadline=None, print_blob=True
)
NAMES = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=16)
SCALARS = st.one_of(
    st.none(), st.booleans(), st.integers(-(1 << 65), 1 << 65), st.text(max_size=20)
)
NON_MAPPINGS = st.one_of(SCALARS, st.lists(SCALARS, max_size=4))
INVALID_NAMES = st.one_of(
    st.none(), st.booleans(), st.integers(-(1 << 65), 1 << 65), st.sampled_from(["", " "])
)


def _assert_both_loaders_reject(content: str, label: str) -> None:
    with pytest.raises(ValueError, match=f"{label} must be a mapping"):
        QueryConfig.load_yaml_from_string(content)
    with TemporaryDirectory() as directory:
        source = Path(directory) / "template.yaml"
        source.write_text(content, encoding="utf-8")
        before = source.read_bytes()
        with pytest.raises(ValueError, match=f"{label} must be a mapping"):
            QueryConfig.load_yaml(source)
        assert source.read_bytes() == before
        assert list(source.parent.iterdir()) == [source]


@PROPERTY_SETTINGS
@given(
    value=st.one_of(
        st.booleans(),
        st.integers(-(1 << 65), 1 << 65),
        st.text(max_size=20),
        st.lists(SCALARS, max_size=4),
    )
)
def test_generated_non_mapping_roots_reject_including_falsy_values(value: object) -> None:
    _assert_both_loaders_reject(yaml.safe_dump(value), "configuration")


@pytest.mark.parametrize("location", ["queries", "query", "parameters", "parameter"])
@PROPERTY_SETTINGS
@given(value=NON_MAPPINGS)
def test_generated_nested_non_mappings_raise_validation_error(location: str, value: object) -> None:
    content = {
        "queries": {"queries": value},
        "query": {"queries": {"generated": value}},
        "parameters": {"queries": {"generated": {"parameters": value}}},
        "parameter": {"queries": {"generated": {"parameters": {"selected": value}}}},
    }[location]
    label = {
        "queries": "queries",
        "query": "query 'generated'",
        "parameters": "parameters",
        "parameter": "parameter 'selected'",
    }[location]
    _assert_both_loaders_reject(yaml.safe_dump(content), label)


@pytest.mark.parametrize("location", ["query", "parameter"])
@PROPERTY_SETTINGS
@given(name=INVALID_NAMES)
def test_generated_invalid_declaration_names_are_rejected(location: str, name: object) -> None:
    definitions = (
        {name: {"query": "SELECT 1"}}
        if location == "query"
        else {"generated": {"query": "SELECT 1", "parameters": {name: {}}}}
    )
    content = yaml.safe_dump({"queries": definitions})
    with pytest.raises(ValueError, match=f"{location} name must be a non-empty string"):
        QueryConfig.load_yaml_from_string(content)
    with TemporaryDirectory() as directory:
        source = Path(directory) / "template.yaml"
        source.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError, match=f"{location} name must be a non-empty string"):
            QueryConfig.load_yaml(source)
        assert source.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("location", ["template", "parameters", "parameter"])
@PROPERTY_SETTINGS
@given(value=NON_MAPPINGS)
def test_direct_template_parser_uses_the_same_mapping_validation(
    location: str, value: object
) -> None:
    data = {
        "template": value,
        "parameters": {"parameters": value},
        "parameter": {"parameters": {"selected": value}},
    }[location]
    with pytest.raises(ValueError, match="must be a mapping"):
        QueryTemplate.from_dict(data)


@PROPERTY_SETTINGS
@given(name=NAMES, value=st.integers(-1000, 1000))
def test_generated_valid_templates_keep_defaults_names_and_category(name: str, value: int) -> None:
    body = {
        "description": "generated",
        "parameters": {"selected": {"type": "int", "default": value}},
        "query": "SELECT {{ selected }} AS value",
    }
    content = yaml.safe_dump({"queries": {name: body}})
    from_string = QueryConfig.load_yaml_from_string(content)
    with TemporaryDirectory() as directory:
        source = Path(directory) / "template.yaml"
        source.write_text(content, encoding="utf-8")
        from_file = QueryConfig.load_yaml(source)
        assert from_file == from_string
        categorized = QueryConfig.load_yaml(source, default_category="custom")
        assert categorized.queries[name].category == "custom"
        assert source.read_text(encoding="utf-8") == content
    template = from_string.queries[name]
    assert template.name == name
    assert template.category == "basic"
    assert template.validate_params({}) == {"selected": value}
    assert template.output_schema == []
    assert template.query == body["query"]


@PROPERTY_SETTINGS
@given(name=NAMES, value=SCALARS)
def test_shared_yaml_alias_data_is_not_mutated_and_unknown_fields_remain_compatible(
    name: str, value: object
) -> None:
    body = {
        "query": "SELECT 1",
        "extension": value,
        "parameters": {"selected": {"type": "int", "extension": value}},
    }
    data = {"queries": {name: body, f"other_{name}": body}, "extension": value}
    before = copy.deepcopy(data)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(config_module.yaml, "safe_load", lambda stream: data)
        config = QueryConfig.load_yaml_from_string("loader result supplied above")
    assert data == before
    assert data["queries"][name] is data["queries"][f"other_{name}"]
    assert config.queries[name].name == name
    assert config.queries[f"other_{name}"].name == f"other_{name}"
    assert all(template.query == "SELECT 1" for template in config.queries.values())


@pytest.mark.parametrize("content", ["", "# comment only\n", "null", "{}", "queries: {}"])
def test_empty_configuration_contract_is_preserved(content: str) -> None:
    assert QueryConfig.load_yaml_from_string(content) == QueryConfig()


@PROPERTY_SETTINGS
@given(name=NAMES)
def test_yaml_syntax_errors_retain_the_documented_parser_error(name: str) -> None:
    content = f"queries: [{name}"
    with pytest.raises(yaml.YAMLError):
        QueryConfig.load_yaml_from_string(content)
    with TemporaryDirectory() as directory:
        source = Path(directory) / "template.yaml"
        source.write_text(content, encoding="utf-8")
        with pytest.raises(yaml.YAMLError):
            QueryConfig.load_yaml(source)
        assert source.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("field", ["query", "parameter_type"])
@PROPERTY_SETTINGS
@given(
    value=st.one_of(
        st.booleans(),
        st.integers(-100, 100),
        st.lists(SCALARS, max_size=4),
        st.dictionaries(NAMES, SCALARS, max_size=4),
    )
)
def test_generated_invalid_sql_and_parameter_type_metadata_is_rejected(
    field: str, value: object
) -> None:
    body = {"query": value} if field == "query" else {"parameters": {"selected": {"type": value}}}
    content = yaml.safe_dump({"queries": {"generated": body}})
    message = "must be a SQL string" if field == "query" else "type must be a string"
    with pytest.raises(ValueError, match=message):
        QueryConfig.load_yaml_from_string(content)
    with TemporaryDirectory() as directory:
        source = Path(directory) / "template.yaml"
        source.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            QueryConfig.load_yaml(source)
        assert source.read_text(encoding="utf-8") == content


@PROPERTY_SETTINGS
@given(name=INVALID_NAMES)
def test_direct_template_parser_rejects_invalid_explicit_names(name: object) -> None:
    with pytest.raises(ValueError, match="template name must be a non-empty string"):
        QueryTemplate.from_dict({"name": name, "query": "SELECT 1"})


def test_null_parameter_type_is_not_a_string_but_null_query_keeps_its_default() -> None:
    with pytest.raises(ValueError, match="type must be a string"):
        QueryTemplate.from_dict({"parameters": {"selected": {"type": None}}})
    assert QueryTemplate.from_dict({"query": None}).query == ""
    legacy = QueryTemplate.from_dict({"parameters": {"selected": {"type": "custom_legacy"}}})
    assert legacy.validate_params({"selected": 42}) == {"selected": "42"}
