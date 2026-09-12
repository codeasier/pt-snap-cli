"""Query configuration and template management."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class QueryParameter:
    """Definition of a query parameter."""

    name: str
    type: str = "str"
    default: Any = None
    required: bool = False
    description: str = ""
    # Closed set of accepted values. Required for parameters that are rendered
    # into SQL as identifiers or keywords (e.g. ORDER BY column / direction),
    # where the type alone cannot bound what reaches the database.
    choices: list[Any] | None = None

    def __post_init__(self) -> None:
        if self.choices is None:
            return
        if not isinstance(self.choices, list) or not self.choices:
            raise ValueError(f"Parameter '{self.name}' choices must be a non-empty list")
        if self.default is not None and self._match_choice(self.default) is None:
            raise ValueError(
                f"Parameter '{self.name}' default {self.default!r} is not one of its choices"
            )

    def _match_choice(self, value: Any) -> Any | None:
        """Return the canonical choice equal to ``value``, or None when not allowed."""
        if self.choices is None:
            return value
        if self.type == "str" and isinstance(value, str):
            for choice in self.choices:
                if isinstance(choice, str) and choice.lower() == value.lower():
                    return choice
            return None
        return value if value in self.choices else None

    def validate(self, value: Any) -> Any:
        """Validate and convert parameter value.

        Args:
            value: Value to validate.

        Returns:
            Converted value. For ``str`` parameters with ``choices`` the
            canonical spelling from ``choices`` is returned, so case-insensitive
            input (``"desc"``) renders as declared (``"DESC"``).

        Raises:
            TypeError: If value cannot be converted to expected type.
            ValueError: If required parameter is missing or the value is not one
                of the declared choices.
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
            converted = converter(value)
        except (ValueError, TypeError) as e:
            raise TypeError(
                f"Parameter '{self.name}' cannot be converted to {self.type}: {e}"
            ) from e

        if self.choices is None:
            return converted
        matched = self._match_choice(converted)
        if matched is None:
            allowed = ", ".join(str(choice) for choice in self.choices)
            raise ValueError(f"Parameter '{self.name}' must be one of: {allowed} (got {value!r})")
        return matched


@dataclass
class QueryTemplate:
    """SQL query template definition."""

    name: str
    description: str = ""
    devices: list[str] = field(default_factory=lambda: ["all"])
    parameters: dict[str, QueryParameter] = field(default_factory=dict)
    query: str = ""
    output_schema: list[dict[str, str]] = field(default_factory=list)
    category: str = "basic"

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate and convert parameters.

        Args:
            params: Parameter values.

        Returns:
            Validated and converted parameters.

        Raises:
            ValueError: If a required parameter is missing, a value is not one
                of the parameter's declared choices, or ``params`` contains a
                name the template does not declare. Unknown names are rejected
                rather than ignored so that a misspelled filter cannot silently
                widen a query.
            TypeError: If parameter type is invalid.
        """
        unknown = sorted(name for name in params if name not in self.parameters)
        if unknown:
            accepted = ", ".join(self.parameters) if self.parameters else "none"
            raise ValueError(
                f"Unknown parameter(s) for template '{self.name}': {', '.join(unknown)} "
                f"(accepted: {accepted})"
            )

        validated = {}
        for name, param_def in self.parameters.items():
            value = params.get(name)
            validated[name] = param_def.validate(value)

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
                choices=param_data.get("choices"),
            )

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            devices=data.get("devices", ["all"]),
            parameters=parameters,
            query=data.get("query", ""),
            output_schema=data.get("output_schema", []),
            category=data.get("category") or default_category or "basic",
        )


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
