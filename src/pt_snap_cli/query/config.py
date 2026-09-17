"""Query configuration and template management."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_CALLSTACK_VARIANTS = ("v1", "v2")


@dataclass
class QueryParameter:
    """Definition of a query parameter."""

    name: str
    type: str = "str"
    default: Any = None
    required: bool = False
    description: str = ""

    def validate(self, value: Any) -> Any:
        """Validate and convert parameter value.

        Args:
            value: Value to validate.

        Returns:
            Converted value.

        Raises:
            TypeError: If value cannot be converted to expected type.
            ValueError: If required parameter is missing.
        """
        if value is None:
            if self.required:
                raise ValueError(f"Required parameter '{self.name}' is missing")
            return self.default

        type_converters = {
            "str": str,
            "int": int,
            "float": float,
            "bool": lambda x: x.lower() in ("true", "1", "yes") if isinstance(x, str) else bool(x),
        }

        converter = type_converters.get(self.type, str)
        try:
            return converter(value)
        except (ValueError, TypeError) as e:
            raise TypeError(
                f"Parameter '{self.name}' cannot be converted to {self.type}: {e}"
            ) from e


@dataclass
class QueryTemplate:
    """SQL query template definition."""

    name: str
    description: str = ""
    devices: list[str] = field(default_factory=lambda: ["all"])
    parameters: dict[str, QueryParameter] = field(default_factory=dict)
    query: str = ""
    query_variants: dict[str, str] = field(default_factory=dict)
    output_schema: list[dict[str, str]] = field(default_factory=list)
    category: str = "basic"

    def sql_for_layout(self, layout: str | None) -> str | None:
        """Return SQL for a detected callstack layout.

        Templates without variants always use ``query``. Variant templates
        return the matching body, or ``None`` when the layout is missing or
        unknown.
        """
        if not self.query_variants:
            return self.query
        if layout is None:
            return None
        return self.query_variants.get(layout)

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate and convert parameters.

        Args:
            params: Parameter values.

        Returns:
            Validated and converted parameters.

        Raises:
            ValueError: If required parameter is missing.
            TypeError: If parameter type is invalid.
        """
        validated = {}
        for name, param_def in self.parameters.items():
            value = params.get(name)
            validated[name] = param_def.validate(value)

        for name, value in params.items():
            if name not in self.parameters:
                validated[name] = value

        return validated

    @classmethod
    def from_dict(cls, data: dict[str, Any], default_category: str | None = None) -> QueryTemplate:
        """Create QueryTemplate from dictionary.

        Args:
            data: Dictionary with template data.
            default_category: Category inferred from directory structure when
                not explicitly declared in the YAML.

        Returns:
            QueryTemplate instance.
        """
        parameters = {}
        for name, param_data in data.get("parameters", {}).items():
            parameters[name] = QueryParameter(
                name=name,
                type=param_data.get("type", "str"),
                default=param_data.get("default"),
                required=param_data.get("required", False),
                description=param_data.get("description", ""),
            )

        query_variants = _parse_query_variants(data.get("name", ""), data.get("query_variants"))
        query = data.get("query") or ""
        if query_variants:
            query = query_variants.get("v2") or query

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            devices=data.get("devices", ["all"]),
            parameters=parameters,
            query=query,
            query_variants=query_variants,
            output_schema=data.get("output_schema", []),
            category=data.get("category") or default_category or "basic",
        )


def _parse_query_variants(template_name: str, raw: Any) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"query_variants for '{template_name}' must be a mapping of layout to SQL")
    if not raw:
        return {}

    unknown = set(raw) - set(_CALLSTACK_VARIANTS)
    if unknown:
        raise ValueError(
            f"query_variants for '{template_name}' has unsupported layouts: "
            f"{', '.join(sorted(str(key) for key in unknown))}"
        )
    missing = [name for name in _CALLSTACK_VARIANTS if name not in raw]
    if missing:
        raise ValueError(
            f"query_variants for '{template_name}' must include {_CALLSTACK_VARIANTS}, "
            f"missing: {', '.join(missing)}"
        )

    variants: dict[str, str] = {}
    for name in _CALLSTACK_VARIANTS:
        sql = raw[name]
        if not isinstance(sql, str) or not sql.strip():
            raise ValueError(f"query_variants.{name} for '{template_name}' must be a SQL string")
        variants[name] = sql
    return variants


@dataclass
class QueryConfig:
    """Query configuration containing multiple templates."""

    version: str = "1.0"
    queries: dict[str, QueryTemplate] = field(default_factory=dict)

    def get_query(self, name: str) -> QueryTemplate | None:
        """Get a query template by name.

        Args:
            name: Template name.

        Returns:
            QueryTemplate or None if not found.
        """
        return self.queries.get(name)

    def list_queries(self) -> list[str]:
        """List all available query names.

        Returns:
            List of query names.
        """
        return list(self.queries.keys())

    @classmethod
    def load_yaml(cls, path: str | Path, default_category: str | None = None) -> QueryConfig:
        """Load configuration from YAML file.

        Args:
            path: Path to YAML file.
            default_category: Category inferred from directory structure when
                not explicitly declared in the YAML.

        Returns:
            QueryConfig instance.

        Raises:
            FileNotFoundError: If file does not exist.
            yaml.YAMLError: If YAML is invalid.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        queries = {}
        for name, query_data in data.get("queries", {}).items():
            query_data["name"] = name
            queries[name] = QueryTemplate.from_dict(query_data, default_category=default_category)

        return cls(
            version=data.get("version", "1.0"),
            queries=queries,
        )

    @classmethod
    def load_yaml_from_string(cls, content: str) -> QueryConfig:
        """Load configuration from YAML string.

        Args:
            content: YAML content string.

        Returns:
            QueryConfig instance.
        """
        data = yaml.safe_load(content) or {}

        queries = {}
        for name, query_data in data.get("queries", {}).items():
            query_data["name"] = name
            queries[name] = QueryTemplate.from_dict(query_data)

        return cls(
            version=data.get("version", "1.0"),
            queries=queries,
        )
