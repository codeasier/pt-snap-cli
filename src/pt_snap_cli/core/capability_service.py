from __future__ import annotations

from typing import Any

from pt_snap_cli import __version__
from pt_snap_cli.core.models import CapabilityCatalog
from pt_snap_cli.core.query_service import QueryService
from pt_snap_cli.core.skill_service import SkillService


class CapabilityService:
    """Read-only catalog of CLI version, template contracts, and bundled skills."""

    def __init__(
        self,
        query_service: QueryService | None = None,
        skill_service: SkillService | None = None,
    ) -> None:
        self._query_service = query_service or QueryService()
        self._skill_service = skill_service or SkillService()

    def catalog(self) -> CapabilityCatalog:
        return CapabilityCatalog(
            cli_version=__version__,
            templates=self._query_service.list_template_contracts(),
            skills=self._skill_service.list_skills(),
        )

    def catalog_to_dict(self, catalog: CapabilityCatalog) -> dict[str, Any]:
        listed = self._skill_service.listing_to_dict(catalog.skills)
        return {
            "cli_version": catalog.cli_version,
            "templates": [
                self._query_service.template_info_to_dict(info) for info in catalog.templates
            ],
            "skills": listed["skills"],
        }
