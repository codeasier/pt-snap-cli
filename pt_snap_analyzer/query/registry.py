"""Query registry for managing predefined queries."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pt_snap_analyzer.query.config import QueryConfig, QueryTemplate

QueryFactory = Callable[[], QueryTemplate]


class QueryRegistry:
    """Registry for predefined query templates."""

    _instance: QueryRegistry | None = None

    def __new__(cls) -> QueryRegistry:
        """Singleton pattern for global registry."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queries: dict[str, QueryTemplate] = {}
            cls._instance._factories: dict[str, QueryFactory] = {}
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None

    def register(self, template: QueryTemplate) -> None:
        """Register a query template.

        Args:
            template: Template to register.
        """
        self._queries[template.name] = template

    def register_factory(self, name: str, factory: QueryFactory) -> None:
        """Register a factory function for lazy template creation.

        Args:
            name: Template name.
            factory: Factory function that returns QueryTemplate.
        """
        self._factories[name] = factory

    def get(self, name: str) -> QueryTemplate | None:
        """Get a registered template by name.

        Args:
            name: Template name.

        Returns:
            QueryTemplate or None if not found.
        """
        if name in self._queries:
            return self._queries[name]

        if name in self._factories:
            template = self._factories[name]()
            self._queries[name] = template
            return template

        return None

    def list_queries(self) -> list[str]:
        """List all registered query names.

        Returns:
            List of query names.
        """
        return list(set(self._queries.keys()) | set(self._factories.keys()))

    def list_queries_with_details(self) -> list[dict[str, str]]:
        """List all registered queries with details.

        Returns:
            List of dicts with name and description.
        """
        details = []
        all_names = set(self._queries.keys()) | set(self._factories.keys())
        
        for name in sorted(all_names):
            template = self.get(name)
            if template:
                details.append({
                    "name": name,
                    "description": template.description,
                })
        
        return details

    def unregister(self, name: str) -> bool:
        """Unregister a query template.

        Args:
            name: Template name to remove.

        Returns:
            True if template was removed.
        """
        removed = False
        if name in self._queries:
            del self._queries[name]
            removed = True
        if name in self._factories:
            del self._factories[name]
            removed = True
        return removed


_registry = QueryRegistry()


def register_query(template: QueryTemplate) -> None:
    """Register a query template in the global registry.

    Args:
        template: Template to register.
    """
    _registry.register(template)


def get_query(name: str) -> QueryTemplate | None:
    """Get a query template from the global registry.

    Args:
        name: Template name.

    Returns:
        QueryTemplate or None if not found.
    """
    return _registry.get(name)


def get_template_info(name: str) -> dict | None:
    """Get detailed information about a template.

    Args:
        name: Template name.

    Returns:
        Dictionary with template details or None if not found.
    """
    template = _registry.get(name)
    if not template:
        return None
    
    return {
        "name": template.name,
        "description": template.description,
        "devices": template.devices,
        "parameters": {
            param_name: {
                "type": param.type,
                "default": param.default,
                "required": param.required,
                "description": param.description,
            }
            for param_name, param in template.parameters.items()
        },
        "output_schema": template.output_schema,
        "query": template.query,
    }


def list_queries() -> list[str]:
    """List all registered queries.

    Returns:
        List of query names.
    """
    return _registry.list_queries()


def list_queries_with_details() -> list[dict[str, str]]:
    """List all registered queries with details.

    Returns:
        List of dicts with name, description, devices, and parameters.
    """
    return _registry.list_queries_with_details()


def _load_yaml_templates(template_dir: Path | str | None = None) -> None:
    """Load all YAML templates from the template directory.
    
    Args:
        template_dir: Path to template directory. Defaults to package templates dir.
    """
    if template_dir is None:
        template_dir = Path(__file__).parent / "templates"
    else:
        template_dir = Path(template_dir)
    
    if not template_dir.exists():
        return
    
    for yaml_file in template_dir.glob("*.yaml"):
        try:
            config = QueryConfig.load_yaml(yaml_file)
            for query_name, template in config.queries.items():
                _registry.register(template)
        except Exception:
            pass


def _load_all_templates() -> None:
    """Load all templates from YAML files."""
    _load_yaml_templates()


try:
    _load_all_templates()
except Exception:
    pass
