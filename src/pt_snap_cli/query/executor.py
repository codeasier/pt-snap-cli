"""Query executor for running SQL queries with template rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError

from pt_snap_cli.context import Context
from pt_snap_cli.query.config import QueryConfig, QueryTemplate


class QueryExecutionError(Exception):
    """Raised when query execution fails."""

    pass


class TemplateRenderError(Exception):
    """Raised when template rendering fails."""

    pass


class QueryExecutor:
    """Executes SQL queries with template rendering support."""

    def __init__(
        self,
        context: Context,
        template_dir: str | Path | None = None,
    ):
        """Initialize query executor.

        Args:
            context: Database context for executing queries.
            template_dir: Optional directory containing YAML template files.
        """
        self._context = context
        self._template_dir = Path(template_dir) if template_dir else None
        self._configs: dict[str, QueryConfig] = {}
        self._env = Environment(
            undefined=StrictUndefined,
            autoescape=False,
        )

        if self._template_dir and self._template_dir.exists():
            self._load_templates()

    def _load_templates(self) -> None:
        """Load all YAML templates from template directory."""
        if not self._template_dir:
            return

        for yaml_file in self._template_dir.glob("*.yaml"):
            try:
                config = QueryConfig.load_yaml(yaml_file)
                self._configs[yaml_file.stem] = config
            except Exception:
                pass

    def render(
        self,
        template: QueryTemplate,
        params: dict[str, Any],
        device_id: int | None = None,
    ) -> str:
        """Render SQL template with parameters.

        Args:
            template: Query template to render.
            params: Parameters for template rendering.
            device_id: Optional device ID for device-specific tables.

        Returns:
            Rendered SQL string.

        Raises:
            TemplateRenderError: If template rendering fails.
        """
        validated_params = template.validate_params(params)

        render_context = dict(validated_params)
        if device_id is not None:
            render_context["device_id"] = device_id
            render_context["device_trace_table"] = f"trace_entry_{device_id}"
            render_context["device_block_table"] = f"block_{device_id}"

        try:
            jinja_template = self._env.from_string(template.query)
            return jinja_template.render(render_context)
        except TemplateSyntaxError as e:
            raise TemplateRenderError(f"Template syntax error in '{template.name}': {e}") from e
        except Exception as e:
            raise TemplateRenderError(f"Failed to render template '{template.name}': {e}") from e

    def execute(
        self,
        sql: str,
        params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute raw SQL query.

        Args:
            sql: SQL query string.
            params: Optional list of parameters.

        Returns:
            List of result rows as dictionaries.

        Raises:
            QueryExecutionError: If query execution fails.
        """
        try:
            with self._context.connect() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        except Exception as e:
            raise QueryExecutionError(f"Query execution failed: {e}") from e

    def execute_template(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        device_id: int | None = None,
        config_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a named template query.

        Args:
            name: Template name to execute.
            params: Parameters for template rendering.
            device_id: Optional device ID to filter results.
            config_name: Optional config name if multiple configs loaded.

        Returns:
            List of result rows as dictionaries.

        Raises:
            QueryExecutionError: If template not found or execution fails.
            TemplateRenderError: If template rendering fails.
        """
        template = self._find_template(name, config_name)
        if template is None:
            raise QueryExecutionError(f"Template not found: {name}")

        sql = self.render(template, params or {}, device_id)

        if device_id is not None and device_id not in self._context.device_ids:
            return []

        return self.execute(sql)

    def execute_on_all_devices(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        config_name: str | None = None,
    ) -> dict[int, list[dict[str, Any]]]:
        """Execute template on all available devices.

        Args:
            name: Template name to execute.
            params: Parameters for template rendering.
            config_name: Optional config name if multiple configs loaded.

        Returns:
            Dictionary mapping device IDs to results.
        """
        template = self._find_template(name, config_name)
        if template is None:
            raise QueryExecutionError(f"Template not found: {name}")

        results = {}
        for device_id in self._context.device_ids:
            try:
                results[device_id] = self.execute_template(name, params, device_id, config_name)
            except QueryExecutionError:
                results[device_id] = []

        return results

    def _find_template(
        self,
        name: str,
        config_name: str | None = None,
    ) -> QueryTemplate | None:
        """Find a template by name across loaded configs and registry.

        Args:
            name: Template name.
            config_name: Optional config to search in.

        Returns:
            QueryTemplate or None if not found.
        """
        from pt_snap_cli.query.registry import get_query

        if config_name:
            config = self._configs.get(config_name)
            return config.get_query(name) if config else None

        for config in self._configs.values():
            template = config.get_query(name)
            if template:
                return template

        return get_query(name)

    def load_config(self, path: str | Path, name: str | None = None) -> None:
        """Load additional config from file.

        Args:
            path: Path to YAML config file.
            name: Optional name for the config. Defaults to file stem.
        """
        config = QueryConfig.load_yaml(path)
        config_name = name or Path(path).stem
        self._configs[config_name] = config

    def register_template(self, template: QueryTemplate, config_name: str = "default") -> None:
        """Register a template directly.

        Args:
            template: Template to register.
            config_name: Config name to register under.
        """
        if config_name not in self._configs:
            self._configs[config_name] = QueryConfig()
        self._configs[config_name].queries[template.name] = template

    def list_templates(self) -> list[str]:
        """List all available template names.

        Returns:
            List of template names.
        """
        from pt_snap_cli.query.registry import list_queries

        names = []
        for config in self._configs.values():
            names.extend(config.list_queries())
        names.extend(list_queries())
        return list(set(names))

    def validate_output(
        self,
        result: list[dict[str, Any]],
        schema: list[dict[str, str]],
    ) -> bool:
        """Validate query result against output schema.

        Args:
            result: Query result rows.
            schema: Expected output schema.

        Returns:
            True if result matches schema.
        """
        if not result:
            return True

        expected_columns = {col["column"] for col in schema}
        actual_columns = set(result[0].keys())

        return expected_columns.issubset(actual_columns)
