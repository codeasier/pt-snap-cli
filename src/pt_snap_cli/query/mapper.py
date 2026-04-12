"""Result mapper for converting query results to model objects."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class ResultMapper:
    """Maps query results to model objects."""

    def __init__(self):
        self._type_converters: dict[str, Callable[[Any], Any]] = {
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "hex": lambda x: hex(x) if isinstance(x, int) else x,
            "datetime": lambda x: x,
        }
        self._model_factories: dict[str, Callable[[dict], Any]] = {}

    def register_type_converter(self, type_name: str, converter: Callable[[Any], Any]) -> None:
        """Register a type converter.

        Args:
            type_name: Type name.
            converter: Converter function.
        """
        self._type_converters[type_name] = converter

    def register_model_factory(self, model_name: str, factory: Callable[[dict], Any]) -> None:
        """Register a model factory.

        Args:
            model_name: Model name.
            factory: Factory function that creates model from dict.
        """
        self._model_factories[model_name] = factory

    def map(
        self,
        row: dict[str, Any],
        schema: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Map a single row according to schema.

        Args:
            row: Result row dictionary.
            schema: Optional output schema for type conversion.

        Returns:
            Mapped row dictionary.
        """
        if not schema:
            return dict(row)

        result = {}
        for col_def in schema:
            col_name = col_def["column"]
            col_type = col_def.get("type", "str")

            if col_name in row:
                value = row[col_name]
                converter = self._type_converters.get(col_type, str)
                try:
                    result[col_name] = converter(value)
                except (ValueError, TypeError):
                    result[col_name] = value
            else:
                result[col_name] = None

        return result

    def map_all(
        self,
        rows: list[dict[str, Any]],
        schema: list[dict[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        """Map all rows according to schema.

        Args:
            rows: List of result rows.
            schema: Optional output schema for type conversion.

        Returns:
            List of mapped rows.
        """
        return [self.map(row, schema) for row in rows]

    def map_to_model(
        self,
        row: dict[str, Any],
        model_name: str,
    ) -> Any:
        """Map row to a model object.

        Args:
            row: Result row dictionary.
            model_name: Registered model name.

        Returns:
            Model object.

        Raises:
            KeyError: If model factory not registered.
        """
        factory = self._model_factories.get(model_name)
        if factory is None:
            raise KeyError(f"Model factory not registered: {model_name}")
        return factory(row)

    def map_all_to_model(
        self,
        rows: list[dict[str, Any]],
        model_name: str,
    ) -> list[Any]:
        """Map all rows to model objects.

        Args:
            rows: List of result rows.
            model_name: Registered model name.

        Returns:
            List of model objects.
        """
        return [self.map_to_model(row, model_name) for row in rows]


_default_mapper = ResultMapper()


def map_result(
    row: dict[str, Any],
    schema: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Map a result row using default mapper.

    Args:
        row: Result row dictionary.
        schema: Optional output schema.

    Returns:
        Mapped row dictionary.
    """
    return _default_mapper.map(row, schema)


def map_results(
    rows: list[dict[str, Any]],
    schema: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Map all result rows using default mapper.

    Args:
        rows: List of result rows.
        schema: Optional output schema.

    Returns:
        List of mapped rows.
    """
    return _default_mapper.map_all(rows, schema)


def register_type_converter(
    type_name: str,
    converter: Callable[[Any], Any],
) -> None:
    """Register a type converter with default mapper.

    Args:
        type_name: Type name.
        converter: Converter function.
    """
    _default_mapper.register_type_converter(type_name, converter)


def register_model_factory(
    model_name: str,
    factory: Callable[[dict], Any],
) -> None:
    """Register a model factory with default mapper.

    Args:
        model_name: Model name.
        factory: Factory function.
    """
    _default_mapper.register_model_factory(model_name, factory)
