"""Discover bundled agent skills and install them into host skill directories."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from collections.abc import Iterable, Mapping
from importlib.resources import files
from pathlib import Path

import yaml

from pt_snap_cli.core.errors import (
    InvalidSkillTargetError,
    SkillCatalogError,
    SkillInstallError,
    SkillNotFoundError,
)
from pt_snap_cli.core.models import (
    SKILL_CONFIG_ENV,
    SKILL_HOSTS,
    SKILL_RESTART_ACTIONS,
    SKILL_RESTART_HINT,
    SKILL_SCOPES,
    SkillHost,
    SkillInstallAction,
    SkillInstallReport,
    SkillInstallResult,
    SkillListing,
    SkillLocationStatus,
    SkillScope,
    SkillSpec,
    SkillStatus,
)

ENV_SKILLS_DIR = "PT_SNAP_SKILLS_DIR"
_DEFAULT_INSTALL_HOSTS: tuple[SkillHost, ...] = ("agents", "claude")
_SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class SkillService:
    """List packaged agent skills and copy them into host skill directories."""

    def __init__(
        self,
        *,
        catalog_dir: Path | None = None,
        home: Path | None = None,
        cwd: Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self._catalog_dir = catalog_dir
        self._home = home
        self._cwd = cwd
        self._environ = environ

    @property
    def home(self) -> Path:
        return self._home if self._home is not None else Path.home()

    @property
    def cwd(self) -> Path:
        return self._cwd if self._cwd is not None else Path.cwd()

    def catalog_dir(self) -> Path:
        if self._catalog_dir is not None:
            return self._catalog_dir
        return default_catalog_dir(self._environ_map)

    def list_catalog(self) -> list[SkillSpec]:
        return list_catalog_skills(self.catalog_dir())

    def list_skills(
        self,
        *,
        hosts: Iterable[str] | None = None,
        scopes: Iterable[str] | None = None,
        dest_dir: Path | str | None = None,
    ) -> list[SkillListing]:
        listings: list[SkillListing] = []
        for spec in self.list_catalog():
            if dest_dir is not None:
                if hosts is not None or scopes is not None:
                    raise InvalidSkillTargetError(
                        "A custom skill directory cannot be combined with "
                        "--target, --user, or --project."
                    )
                locations = [self._custom_location_status(spec, dest_dir)]
            else:
                selected_hosts = self._resolve_hosts(hosts, default=SKILL_HOSTS)
                selected_scopes = self._resolve_scopes(scopes)
                locations = [
                    self._location_status(spec, host, scope)
                    for scope in selected_scopes
                    for host in selected_hosts
                ]
            listings.append(
                SkillListing(
                    name=spec.name,
                    description=spec.description,
                    source_dir=spec.source_dir,
                    status=_summary_status(locations),
                    locations=locations,
                )
            )
        return listings

    def install_skills(
        self,
        names: Iterable[str] | None = None,
        *,
        hosts: Iterable[str] | None = None,
        scope: str = "user",
        force: bool = False,
        dest_dir: Path | str | None = None,
    ) -> SkillInstallReport:
        catalog = {spec.name: spec for spec in self.list_catalog()}
        requested = self._resolve_names(names, catalog)
        results: list[SkillInstallResult] = []
        for name in requested:
            spec = catalog[name]
            for host, selected_scope, dest in self._mutation_targets(name, hosts, scope, dest_dir):
                results.append(
                    self._install_one(spec, host, selected_scope, dest=dest, force=force)
                )
        return SkillInstallReport(results=results)

    def upgrade_skills(
        self,
        names: Iterable[str] | None = None,
        *,
        hosts: Iterable[str] | None = None,
        scope: str = "user",
        dest_dir: Path | str | None = None,
    ) -> SkillInstallReport:
        catalog = {spec.name: spec for spec in self.list_catalog()}
        requested = self._resolve_names(names, catalog)
        results: list[SkillInstallResult] = []
        for name in requested:
            spec = catalog[name]
            for host, selected_scope, dest in self._mutation_targets(name, hosts, scope, dest_dir):
                results.append(self._upgrade_one(spec, host, selected_scope, dest=dest))
        return SkillInstallReport(results=results)

    def uninstall_skills(
        self,
        names: Iterable[str] | None = None,
        *,
        hosts: Iterable[str] | None = None,
        scope: str = "user",
        dest_dir: Path | str | None = None,
    ) -> SkillInstallReport:
        catalog = {spec.name: spec for spec in self.list_catalog()}
        requested = self._resolve_names(names, catalog)
        results: list[SkillInstallResult] = []
        for name in requested:
            for host, selected_scope, dest in self._mutation_targets(name, hosts, scope, dest_dir):
                results.append(self._uninstall_one(name, host, selected_scope, dest=dest))
        return SkillInstallReport(results=results)

    def listing_to_dict(self, listings: list[SkillListing]) -> dict[str, object]:
        return {
            "skills": [
                {
                    "name": item.name,
                    "description": item.description,
                    "source_dir": str(item.source_dir),
                    "status": item.status,
                    "locations": [
                        {
                            "host": location.host,
                            "scope": location.scope,
                            "path": str(location.path),
                            "status": location.status,
                        }
                        for location in item.locations
                    ],
                }
                for item in listings
            ],
        }

    def install_report_to_dict(self, report: SkillInstallReport) -> dict[str, object]:
        restart_required = any(item.action in SKILL_RESTART_ACTIONS for item in report.results)
        return {
            "results": [
                {
                    "name": item.name,
                    "host": item.host,
                    "scope": item.scope,
                    "path": str(item.path),
                    "action": item.action,
                }
                for item in report.results
            ],
            "restart_required": restart_required,
            "restart_hint": SKILL_RESTART_HINT if restart_required else None,
        }

    def skill_destination(self, host: str, scope: str, name: str) -> Path:
        resolved_host = self._resolve_host(host)
        resolved_scope = self._resolve_scope(scope)
        return self._host_root(resolved_host, resolved_scope) / name

    def _mutation_targets(
        self,
        name: str,
        hosts: Iterable[str] | None,
        scope: str,
        dest_dir: Path | str | None,
    ) -> list[tuple[SkillHost, SkillScope, Path]]:
        if dest_dir is not None:
            if hosts is not None:
                raise InvalidSkillTargetError(
                    "A custom skill directory cannot be combined with --target."
                )
            if scope != "user":
                raise InvalidSkillTargetError(
                    "A custom skill directory cannot be combined with --project."
                )
            return [("custom", "user", _explicit_skills_dir(dest_dir) / name)]
        selected_hosts = self._resolve_hosts(hosts, default=_DEFAULT_INSTALL_HOSTS)
        selected_scope = self._resolve_scope(scope)
        return [
            (host, selected_scope, self._host_root(host, selected_scope) / name)
            for host in selected_hosts
        ]

    def _location_status(
        self, spec: SkillSpec, host: SkillHost, scope: SkillScope
    ) -> SkillLocationStatus:
        path = self._host_root(host, scope) / spec.name
        return SkillLocationStatus(
            host=host,
            scope=scope,
            path=path,
            status=_install_status(spec.source_dir, path),
        )

    def _custom_location_status(self, spec: SkillSpec, dest_dir: Path | str) -> SkillLocationStatus:
        path = _explicit_skills_dir(dest_dir) / spec.name
        return SkillLocationStatus(
            host="custom",
            scope="user",
            path=path,
            status=_install_status(spec.source_dir, path),
        )

    def _install_one(
        self,
        spec: SkillSpec,
        host: SkillHost,
        scope: SkillScope,
        *,
        dest: Path,
        force: bool,
    ) -> SkillInstallResult:
        status = _install_status(spec.source_dir, dest)
        if status == "installed":
            return SkillInstallResult(
                name=spec.name,
                host=host,
                scope=scope,
                path=dest,
                action="already_installed",
            )
        if status == "outdated" and not force:
            raise SkillInstallError(
                f"Skill '{spec.name}' already exists at '{dest}' and differs from "
                f"the bundled copy. Re-run with --force to replace it."
            )
        _publish_skill(spec.source_dir, dest)
        action: SkillInstallAction = "updated" if status == "outdated" else "installed"
        return SkillInstallResult(
            name=spec.name,
            host=host,
            scope=scope,
            path=dest,
            action=action,
        )

    def _upgrade_one(
        self,
        spec: SkillSpec,
        host: SkillHost,
        scope: SkillScope,
        *,
        dest: Path,
    ) -> SkillInstallResult:
        status = _install_status(spec.source_dir, dest)
        if status == "missing":
            return SkillInstallResult(
                name=spec.name,
                host=host,
                scope=scope,
                path=dest,
                action="not_installed",
            )
        if status == "installed":
            return SkillInstallResult(
                name=spec.name,
                host=host,
                scope=scope,
                path=dest,
                action="already_installed",
            )
        _publish_skill(spec.source_dir, dest)
        return SkillInstallResult(
            name=spec.name,
            host=host,
            scope=scope,
            path=dest,
            action="updated",
        )

    def _uninstall_one(
        self,
        name: str,
        host: SkillHost,
        scope: SkillScope,
        *,
        dest: Path,
    ) -> SkillInstallResult:
        if not dest.exists() and not dest.is_symlink():
            return SkillInstallResult(
                name=name,
                host=host,
                scope=scope,
                path=dest,
                action="not_installed",
            )
        try:
            _remove_path(dest)
        except OSError as exc:
            raise SkillInstallError(f"Failed to uninstall '{name}' at '{dest}': {exc}") from exc
        return SkillInstallResult(
            name=name,
            host=host,
            scope=scope,
            path=dest,
            action="uninstalled",
        )

    def _host_root(self, host: SkillHost, scope: SkillScope) -> Path:
        if host == "custom":
            raise InvalidSkillTargetError(
                "Custom destinations require an explicit skill directory."
            )
        if scope == "project":
            return self.cwd / f".{host}" / "skills"
        env_name = SKILL_CONFIG_ENV.get(host)
        if env_name:
            override = self._environ_map.get(env_name, "")
            if override.strip():
                return Path(override).expanduser() / "skills"
        return self.home / f".{host}" / "skills"

    @property
    def _environ_map(self) -> Mapping[str, str]:
        return self._environ if self._environ is not None else os.environ

    def _resolve_names(
        self, names: Iterable[str] | None, catalog: dict[str, SkillSpec]
    ) -> list[str]:
        if names is None:
            return list(catalog)
        requested = list(names)
        unknown = [name for name in requested if name not in catalog]
        if unknown:
            available = ", ".join(catalog) or "(none)"
            raise SkillNotFoundError(
                f"Unknown skill(s): {', '.join(unknown)}. Available: {available}"
            )
        return requested

    def _resolve_hosts(
        self, hosts: Iterable[str] | None, *, default: tuple[SkillHost, ...]
    ) -> tuple[SkillHost, ...]:
        if hosts is None:
            return default
        return tuple(self._resolve_host(host) for host in hosts)

    def _resolve_host(self, host: str) -> SkillHost:
        normalized = host.strip().lower()
        if normalized not in SKILL_HOSTS:
            raise InvalidSkillTargetError(
                f"Unknown skill target '{host}'. Choose from: {', '.join(SKILL_HOSTS)}"
            )
        return normalized

    def _resolve_scopes(self, scopes: Iterable[str] | None) -> tuple[SkillScope, ...]:
        if scopes is None:
            return SKILL_SCOPES
        return tuple(self._resolve_scope(scope) for scope in scopes)

    def _resolve_scope(self, scope: str) -> SkillScope:
        normalized = scope.strip().lower()
        if normalized not in SKILL_SCOPES:
            raise InvalidSkillTargetError(
                f"Unknown skill scope '{scope}'. Choose from: {', '.join(SKILL_SCOPES)}"
            )
        return normalized


def default_catalog_dir(environ: Mapping[str, str] | None = None) -> Path:
    env_map = environ if environ is not None else os.environ
    env = env_map.get(ENV_SKILLS_DIR)
    if env:
        path = Path(env).expanduser()
        if not _looks_like_catalog(path):
            raise SkillCatalogError(f"PT_SNAP_SKILLS_DIR is not a skill catalog: {path}")
        return path
    repo = _discover_repo_skills_dir()
    if repo is not None:
        return repo
    packaged = _packaged_skills_dir()
    if packaged is not None:
        return packaged
    raise SkillCatalogError("Bundled agent skills are not available in this installation.")


def list_catalog_skills(catalog_dir: Path) -> list[SkillSpec]:
    if not catalog_dir.is_dir():
        raise SkillCatalogError(f"Skill catalog directory does not exist: {catalog_dir}")
    skills: list[SkillSpec] = []
    for child in sorted(catalog_dir.iterdir(), key=lambda path: path.name):
        if not child.is_dir() or child.name.startswith("."):
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        metadata = _parse_skill_frontmatter(skill_md)
        name = _validated_skill_name(str(metadata.get("name") or child.name), source=skill_md)
        description = str(metadata.get("description") or "").strip()
        skills.append(SkillSpec(name=name, description=description, source_dir=child))
    if not skills:
        raise SkillCatalogError(f"No SKILL.md directories found in '{catalog_dir}'")
    return skills


def parse_host_option(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    hosts = [item.strip() for item in value.split(",") if item.strip()]
    if not hosts:
        raise InvalidSkillTargetError("Skill target list must not be empty.")
    return tuple(hosts)


def format_skill_location(location: SkillLocationStatus) -> str:
    if location.host == "custom":
        return str(location.path.parent)
    return f"{location.host}:{location.scope}"


def format_skill_install_target(item: SkillInstallResult) -> str:
    if item.host == "custom":
        return str(item.path)
    return f"{item.path} ({item.host}, {item.scope})"


def _discover_repo_skills_dir() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "skills"
        project_marker = parent / "pyproject.toml"
        if _looks_like_catalog(candidate) and project_marker.is_file():
            return candidate
    return None


def _packaged_skills_dir() -> Path | None:
    packaged = files("pt_snap_cli").joinpath("bundled_skills")
    path = Path(str(packaged))
    if _looks_like_catalog(path):
        return path
    return None


def _looks_like_catalog(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any((child / "SKILL.md").is_file() for child in path.iterdir() if child.is_dir())


def _validated_skill_name(name: str, *, source: Path) -> str:
    if not _SKILL_NAME_PATTERN.fullmatch(name):
        raise SkillCatalogError(
            f"Skill name {name!r} from '{source}' is not a valid skill directory name."
        )
    return name


def _parse_skill_frontmatter(skill_md: Path) -> dict[str, object]:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillCatalogError(f"Failed to read skill file '{skill_md}': {exc}") from exc
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        loaded = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise SkillCatalogError(f"Invalid SKILL.md frontmatter in '{skill_md}': {exc}") from exc
    return loaded if isinstance(loaded, dict) else {}


def _iter_skill_files(skill_dir: Path) -> list[Path]:
    files_found: list[Path] = []
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {".DS_Store"} or "__pycache__" in path.parts:
            continue
        files_found.append(path)
    return files_found


def skill_dir_digest(skill_dir: Path) -> str:
    hasher = hashlib.sha256()
    for path in _iter_skill_files(skill_dir):
        relative = path.relative_to(skill_dir).as_posix()
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _install_status(source_dir: Path, dest: Path) -> SkillStatus:
    skill_md = dest / "SKILL.md"
    if not skill_md.is_file():
        if dest.exists() or dest.is_symlink():
            return "outdated"
        return "missing"
    if skill_dir_digest(source_dir) == skill_dir_digest(dest):
        return "installed"
    return "outdated"


def display_description(text: str) -> str:
    return " ".join(text.split())


def human_skill_summary(text: str, *, max_chars: int = 140) -> str:
    """Return a one-sentence, terminal-friendly skill summary."""
    collapsed = display_description(text)
    if not collapsed:
        return ""
    in_ticks = False
    for index, char in enumerate(collapsed):
        if char == "`":
            in_ticks = not in_ticks
            continue
        if in_ticks:
            continue
        if char == "." and (index + 1 == len(collapsed) or collapsed[index + 1].isspace()):
            return collapsed[: index + 1]
    if len(collapsed) <= max_chars:
        return collapsed
    clipped = collapsed[: max_chars - 1]
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return f"{clipped}…"


def _summary_status(locations: list[SkillLocationStatus]) -> SkillStatus:
    statuses = {location.status for location in locations}
    if "installed" in statuses:
        return "installed"
    if "outdated" in statuses:
        return "outdated"
    return "missing"


def _explicit_skills_dir(dest_dir: Path | str) -> Path:
    path = Path(dest_dir).expanduser()
    if path.exists() and not path.is_dir():
        raise InvalidSkillTargetError(f"Skill directory must be a directory, not a file: {path}")
    return path


def _remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def _publish_skill(source_dir: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.parent / f".{dest.name}.pt-snap-staging"
    try:
        _remove_path(staging)
        shutil.copytree(source_dir, staging)
        _remove_path(dest)
        try:
            staging.replace(dest)
        except OSError:
            shutil.move(str(staging), str(dest))
    except OSError as exc:
        _remove_path(staging)
        raise SkillInstallError(f"Failed to install skill at '{dest}': {exc}") from exc
