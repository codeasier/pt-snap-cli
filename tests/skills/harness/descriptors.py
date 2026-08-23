from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]


class DescriptorError(ValueError):
    """Raised when an evaluation descriptor violates the v1 contract."""


@dataclass(frozen=True)
class Objective:
    id: str
    mode: str
    scorer: str
    weight: int


@dataclass(frozen=True)
class ExpectedAction:
    id: str
    operation: str
    match: dict[str, Any]


@dataclass(frozen=True)
class EvalCase:
    id: str
    path: Path
    title: str
    covers: tuple[str, ...]
    initial_user: str
    fixture: dict[str, Any] | None
    actions: tuple[ExpectedAction, ...]
    partial_order: tuple[tuple[str, str], ...]
    forbidden_operations: tuple[str, ...]
    oracle_facts: dict[str, Any]
    allowed_classifications: tuple[str, ...]
    prohibited_classifications: tuple[str, ...]
    required_unknowns: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    required_evidence: tuple[tuple[str, str], ...]
    mandatory_objectives: tuple[str, ...]


@dataclass(frozen=True)
class EvalSuite:
    id: str
    path: Path
    skill_path: Path
    skill_name: str
    profile: str
    classifications: tuple[str, ...]
    objectives: tuple[Objective, ...]
    required_branches: tuple[str, ...]
    allowed_operations: tuple[str, ...]
    forbidden_operations: tuple[str, ...]
    max_calls: int
    max_failed_calls: int
    max_repeated_semantic_calls: int
    cases: tuple[EvalCase, ...]

    @property
    def objectives_by_id(self) -> dict[str, Objective]:
        return {objective.id: objective for objective in self.objectives}

    def case(self, case_id: str) -> EvalCase:
        for case in self.cases:
            if case.id == case_id:
                return case
        raise KeyError(case_id)


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise DescriptorError(f"Cannot load {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise DescriptorError(f"{path} must contain a YAML mapping")
    return data


def _strict_mapping(
    value: Any,
    *,
    context: str,
    required: set[str],
    allowed: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DescriptorError(f"{context} must be a mapping")
    missing = required - value.keys()
    unknown = value.keys() - allowed
    if missing:
        raise DescriptorError(f"{context} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise DescriptorError(f"{context} has unknown fields: {', '.join(sorted(unknown))}")
    return value


def _string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DescriptorError(f"{context} must be a non-empty string")
    return value


def _string_list(value: Any, context: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise DescriptorError(f"{context} must be a list")
    result = tuple(_string(item, f"{context} item") for item in value)
    if len(result) != len(set(result)):
        raise DescriptorError(f"{context} contains duplicate values")
    return result


def _positive_int(value: Any, context: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise DescriptorError(f"{context} must be an integer >= {minimum}")
    return value


def _safe_path(base: Path, raw_path: Any, context: str) -> Path:
    text = _string(raw_path, context)
    relative = Path(text)
    if relative.is_absolute() or ".." in relative.parts:
        raise DescriptorError(f"{context} must be a repository-relative path without '..'")
    resolved = (base / relative).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError as exc:
        raise DescriptorError(f"{context} escapes its descriptor root") from exc
    return resolved


def _validate_dag(action_ids: set[str], edges: tuple[tuple[str, str], ...], context: str) -> None:
    successors = {action_id: set() for action_id in action_ids}
    incoming = dict.fromkeys(action_ids, 0)
    for before, after in edges:
        if before not in action_ids or after not in action_ids:
            raise DescriptorError(f"{context} references an unknown action")
        if before == after:
            raise DescriptorError(f"{context} cannot order an action before itself")
        if after not in successors[before]:
            successors[before].add(after)
            incoming[after] += 1

    ready = [action_id for action_id, count in incoming.items() if count == 0]
    visited = 0
    while ready:
        current = ready.pop()
        visited += 1
        for successor in successors[current]:
            incoming[successor] -= 1
            if incoming[successor] == 0:
                ready.append(successor)
    if visited != len(action_ids):
        raise DescriptorError(f"{context} contains a cycle")


def _load_case(
    path: Path,
    *,
    suite_root: Path,
    suite_objectives: set[str],
    classifications: set[str],
    suite_forbidden: tuple[str, ...],
) -> EvalCase:
    data = _strict_mapping(
        _load_yaml(path),
        context=str(path),
        required={
            "schema_version",
            "kind",
            "id",
            "title",
            "covers",
            "task",
            "expected_tools",
            "oracle",
            "scoring",
        },
        allowed={
            "schema_version",
            "kind",
            "id",
            "title",
            "tags",
            "covers",
            "task",
            "fixture",
            "dialog",
            "expected_tools",
            "oracle",
            "scoring",
        },
    )
    if data["schema_version"] != 1 or data["kind"] != "skill-eval-case":
        raise DescriptorError(f"{path} must declare skill-eval-case schema version 1")

    task = _strict_mapping(
        data["task"],
        context=f"{path}: task",
        required={"initial_user"},
        allowed={"initial_user"},
    )
    expected_tools = _strict_mapping(
        data["expected_tools"],
        context=f"{path}: expected_tools",
        required={"actions", "partial_order", "forbidden"},
        allowed={"actions", "partial_order", "forbidden"},
    )
    if not isinstance(expected_tools["actions"], list):
        raise DescriptorError(f"{path}: expected_tools.actions must be a list")
    actions: list[ExpectedAction] = []
    for index, raw_action in enumerate(expected_tools["actions"]):
        action = _strict_mapping(
            raw_action,
            context=f"{path}: action {index}",
            required={"id", "operation", "match"},
            allowed={"id", "operation", "match"},
        )
        if not isinstance(action["match"], dict):
            raise DescriptorError(f"{path}: action {index}.match must be a mapping")
        actions.append(
            ExpectedAction(
                id=_string(action["id"], f"{path}: action id"),
                operation=_string(action["operation"], f"{path}: action operation"),
                match=dict(action["match"]),
            )
        )
    action_ids = {action.id for action in actions}
    if len(action_ids) != len(actions):
        raise DescriptorError(f"{path}: action IDs must be unique")

    if not isinstance(expected_tools["partial_order"], list):
        raise DescriptorError(f"{path}: partial_order must be a list")
    edges: list[tuple[str, str]] = []
    for index, raw_edge in enumerate(expected_tools["partial_order"]):
        edge = _strict_mapping(
            raw_edge,
            context=f"{path}: partial_order {index}",
            required={"before", "after"},
            allowed={"before", "after"},
        )
        edges.append(
            (
                _string(edge["before"], f"{path}: partial_order.before"),
                _string(edge["after"], f"{path}: partial_order.after"),
            )
        )
    partial_order = tuple(edges)
    _validate_dag(action_ids, partial_order, f"{path}: partial_order")

    forbidden: list[str] = []
    if not isinstance(expected_tools["forbidden"], list):
        raise DescriptorError(f"{path}: forbidden must be a list")
    for index, raw_forbidden in enumerate(expected_tools["forbidden"]):
        entry = _strict_mapping(
            raw_forbidden,
            context=f"{path}: forbidden {index}",
            required={"operation"},
            allowed={"operation"},
        )
        forbidden.append(_string(entry["operation"], f"{path}: forbidden operation"))
    forbidden_operations = tuple(dict.fromkeys((*suite_forbidden, *forbidden)))
    conflicts = {action.operation for action in actions} & set(forbidden_operations)
    if conflicts:
        raise DescriptorError(
            f"{path}: required and forbidden operations conflict: {', '.join(sorted(conflicts))}"
        )

    oracle = _strict_mapping(
        data["oracle"],
        context=f"{path}: oracle",
        required={"facts", "result", "required_evidence"},
        allowed={"facts", "result", "required_evidence"},
    )
    if not isinstance(oracle["facts"], dict):
        raise DescriptorError(f"{path}: oracle.facts must be a mapping")
    result = _strict_mapping(
        oracle["result"],
        context=f"{path}: oracle.result",
        required={
            "allowed_classifications",
            "prohibited_classifications",
            "required_unknowns",
            "prohibited_claims",
        },
        allowed={
            "allowed_classifications",
            "prohibited_classifications",
            "required_unknowns",
            "prohibited_claims",
        },
    )
    allowed_classifications = _string_list(
        result["allowed_classifications"], f"{path}: allowed_classifications"
    )
    prohibited_classifications = _string_list(
        result["prohibited_classifications"], f"{path}: prohibited_classifications"
    )
    unknown_classifications = (
        set(allowed_classifications) | set(prohibited_classifications)
    ) - classifications
    if unknown_classifications:
        raise DescriptorError(
            f"{path}: classifications are not declared by the suite: "
            f"{', '.join(sorted(unknown_classifications))}"
        )

    if not isinstance(oracle["required_evidence"], list):
        raise DescriptorError(f"{path}: required_evidence must be a list")
    required_evidence: list[tuple[str, str]] = []
    for index, raw_evidence in enumerate(oracle["required_evidence"]):
        evidence = _strict_mapping(
            raw_evidence,
            context=f"{path}: required_evidence {index}",
            required={"claim", "produced_by"},
            allowed={"claim", "produced_by"},
        )
        claim = _string(evidence["claim"], f"{path}: evidence claim")
        produced_by = _string(evidence["produced_by"], f"{path}: evidence produced_by")
        if produced_by not in action_ids:
            raise DescriptorError(f"{path}: evidence references unknown action {produced_by}")
        required_evidence.append((claim, produced_by))

    scoring = _strict_mapping(
        data["scoring"],
        context=f"{path}: scoring",
        required={"mandatory_objectives"},
        allowed={"mandatory_objectives"},
    )
    mandatory_objectives = _string_list(
        scoring["mandatory_objectives"], f"{path}: mandatory_objectives"
    )
    unknown_objectives = set(mandatory_objectives) - suite_objectives
    if unknown_objectives:
        raise DescriptorError(
            f"{path}: unknown objectives: {', '.join(sorted(unknown_objectives))}"
        )

    fixture: dict[str, Any] | None = None
    if "fixture" in data:
        raw_fixture = _strict_mapping(
            data["fixture"],
            context=f"{path}: fixture",
            required={"builder", "definition", "mount_path", "read_only"},
            allowed={"builder", "definition", "mount_path", "read_only"},
        )
        if raw_fixture["builder"] != "synthetic-snapshotdb":
            raise DescriptorError(f"{path}: only synthetic-snapshotdb fixtures are supported")
        definition = _safe_path(
            suite_root, raw_fixture["definition"], f"{path}: fixture.definition"
        )
        if not definition.is_file():
            raise DescriptorError(f"{path}: fixture definition does not exist: {definition}")
        if raw_fixture["read_only"] is not True:
            raise DescriptorError(f"{path}: diagnostic fixtures must be read-only")
        mount_path = _string(raw_fixture["mount_path"], f"{path}: fixture.mount_path")
        if not mount_path.startswith("/fixtures/"):
            raise DescriptorError(f"{path}: fixture.mount_path must be under /fixtures/")
        fixture = {**raw_fixture, "definition_path": definition}

    return EvalCase(
        id=_string(data["id"], f"{path}: id"),
        path=path,
        title=_string(data["title"], f"{path}: title"),
        covers=_string_list(data["covers"], f"{path}: covers"),
        initial_user=_string(task["initial_user"], f"{path}: task.initial_user"),
        fixture=fixture,
        actions=tuple(actions),
        partial_order=partial_order,
        forbidden_operations=forbidden_operations,
        oracle_facts=dict(oracle["facts"]),
        allowed_classifications=allowed_classifications,
        prohibited_classifications=prohibited_classifications,
        required_unknowns=_string_list(result["required_unknowns"], f"{path}: required_unknowns"),
        prohibited_claims=_string_list(result["prohibited_claims"], f"{path}: prohibited_claims"),
        required_evidence=tuple(required_evidence),
        mandatory_objectives=mandatory_objectives,
    )


def load_suite(path: Path, *, repo_root: Path = REPO_ROOT) -> EvalSuite:
    path = path.resolve()
    data = _strict_mapping(
        _load_yaml(path),
        context=str(path),
        required={
            "schema_version",
            "kind",
            "metadata",
            "skill",
            "result_contract",
            "objectives",
            "coverage",
            "defaults",
            "cases",
        },
        allowed={
            "schema_version",
            "kind",
            "metadata",
            "skill",
            "result_contract",
            "objectives",
            "coverage",
            "defaults",
            "cases",
        },
    )
    if data["schema_version"] != 1 or data["kind"] != "skill-eval-suite":
        raise DescriptorError(f"{path} must declare skill-eval-suite schema version 1")

    metadata = _strict_mapping(
        data["metadata"],
        context=f"{path}: metadata",
        required={"id", "title", "description"},
        allowed={"id", "title", "description"},
    )
    suite_id = _string(metadata["id"], f"{path}: metadata.id")
    skill = _strict_mapping(
        data["skill"],
        context=f"{path}: skill",
        required={"path", "expected_name", "profile"},
        allowed={"path", "expected_name", "profile"},
    )
    skill_path = _safe_path(repo_root, skill["path"], f"{path}: skill.path")
    if not skill_path.is_file():
        raise DescriptorError(f"{path}: skill path does not exist: {skill_path}")
    skill_name = _string(skill["expected_name"], f"{path}: skill.expected_name")
    if f"name: {skill_name}" not in skill_path.read_text():
        raise DescriptorError(f"{path}: expected skill name is not present in {skill_path}")
    profile = _string(skill["profile"], f"{path}: skill.profile")
    if profile != "diagnostic-readonly":
        raise DescriptorError(f"{path}: v1 supports only diagnostic-readonly suites")

    result_contract = _strict_mapping(
        data["result_contract"],
        context=f"{path}: result_contract",
        required={"required_fields", "classifications"},
        allowed={"required_fields", "classifications"},
    )
    required_result_fields = set(
        _string_list(result_contract["required_fields"], f"{path}: required_fields")
    )
    required_v1_fields = {"classification", "facts", "claims", "unknowns"}
    if not required_v1_fields <= required_result_fields:
        raise DescriptorError(
            f"{path}: result_contract must require {', '.join(sorted(required_v1_fields))}"
        )
    classifications = _string_list(result_contract["classifications"], f"{path}: classifications")

    if not isinstance(data["objectives"], list) or not data["objectives"]:
        raise DescriptorError(f"{path}: objectives must be a non-empty list")
    objectives: list[Objective] = []
    for index, raw_objective in enumerate(data["objectives"]):
        objective = _strict_mapping(
            raw_objective,
            context=f"{path}: objective {index}",
            required={"id", "mode", "scorer"},
            allowed={"id", "mode", "scorer", "weight"},
        )
        mode = _string(objective["mode"], f"{path}: objective mode")
        if mode not in {"gate", "score"}:
            raise DescriptorError(f"{path}: objective mode must be gate or score")
        weight = objective.get("weight", 0)
        if mode == "gate" and weight != 0:
            raise DescriptorError(f"{path}: gate objectives cannot have weight")
        if mode == "score":
            weight = _positive_int(weight, f"{path}: objective weight")
        objectives.append(
            Objective(
                id=_string(objective["id"], f"{path}: objective id"),
                mode=mode,
                scorer=_string(objective["scorer"], f"{path}: objective scorer"),
                weight=weight,
            )
        )
    objective_ids = {objective.id for objective in objectives}
    if len(objective_ids) != len(objectives):
        raise DescriptorError(f"{path}: objective IDs must be unique")
    supported_scorers = {
        "safety",
        "tool_path",
        "facts",
        "evidence",
        "classification",
        "uncertainty",
    }
    unknown_scorers = {objective.scorer for objective in objectives} - supported_scorers
    if unknown_scorers:
        raise DescriptorError(
            f"{path}: unsupported objective scorers: {', '.join(sorted(unknown_scorers))}"
        )
    if sum(objective.weight for objective in objectives if objective.mode == "score") != 100:
        raise DescriptorError(f"{path}: score objective weights must total 100")

    coverage = _strict_mapping(
        data["coverage"],
        context=f"{path}: coverage",
        required={"required_branches"},
        allowed={"required_branches"},
    )
    required_branches = _string_list(coverage["required_branches"], f"{path}: required_branches")

    defaults = _strict_mapping(
        data["defaults"],
        context=f"{path}: defaults",
        required={"runner", "repetitions", "timeout_seconds", "sandbox", "tool_policy"},
        allowed={"runner", "repetitions", "timeout_seconds", "sandbox", "tool_policy"},
    )
    _positive_int(defaults["repetitions"], f"{path}: repetitions")
    _positive_int(defaults["timeout_seconds"], f"{path}: timeout_seconds")
    sandbox = _strict_mapping(
        defaults["sandbox"],
        context=f"{path}: sandbox",
        required={"network", "home", "project", "fixtures", "clear_environment"},
        allowed={"network", "home", "project", "fixtures", "clear_environment"},
    )
    expected_sandbox = {
        "network": "disabled",
        "home": "isolated",
        "project": "read_only",
        "fixtures": "read_only",
    }
    for key, expected in expected_sandbox.items():
        if sandbox[key] != expected:
            raise DescriptorError(f"{path}: diagnostic sandbox requires {key}: {expected}")
    _string_list(sandbox["clear_environment"], f"{path}: clear_environment")

    tool_policy = _strict_mapping(
        defaults["tool_policy"],
        context=f"{path}: tool_policy",
        required={
            "allowed",
            "forbidden",
            "max_calls",
            "max_failed_calls",
            "max_repeated_semantic_calls",
        },
        allowed={
            "allowed",
            "forbidden",
            "max_calls",
            "max_failed_calls",
            "max_repeated_semantic_calls",
        },
    )
    allowed_operations = _string_list(tool_policy["allowed"], f"{path}: tool_policy.allowed")
    forbidden_operations = _string_list(tool_policy["forbidden"], f"{path}: tool_policy.forbidden")
    conflicts = set(allowed_operations) & set(forbidden_operations)
    if conflicts:
        raise DescriptorError(
            f"{path}: allowed and forbidden operations conflict: {', '.join(sorted(conflicts))}"
        )

    if not isinstance(data["cases"], list) or not data["cases"]:
        raise DescriptorError(f"{path}: cases must be a non-empty list")
    cases: list[EvalCase] = []
    suite_root = path.parent.resolve()
    for index, raw_case_ref in enumerate(data["cases"]):
        case_ref = _strict_mapping(
            raw_case_ref,
            context=f"{path}: case {index}",
            required={"id", "path"},
            allowed={"id", "path"},
        )
        case_path = _safe_path(suite_root, case_ref["path"], f"{path}: case path")
        if not case_path.is_file():
            raise DescriptorError(f"{path}: case file does not exist: {case_path}")
        case = _load_case(
            case_path,
            suite_root=suite_root,
            suite_objectives=objective_ids,
            classifications=set(classifications),
            suite_forbidden=forbidden_operations,
        )
        expected_id = _string(case_ref["id"], f"{path}: case id")
        if case.id != expected_id:
            raise DescriptorError(
                f"{path}: case reference {expected_id} does not match descriptor ID {case.id}"
            )
        cases.append(case)
    case_ids = {case.id for case in cases}
    if len(case_ids) != len(cases):
        raise DescriptorError(f"{path}: case IDs must be unique")
    covered = {branch for case in cases for branch in case.covers}
    missing_branches = set(required_branches) - covered
    if missing_branches:
        raise DescriptorError(
            f"{path}: required branches are uncovered: {', '.join(sorted(missing_branches))}"
        )

    return EvalSuite(
        id=suite_id,
        path=path,
        skill_path=skill_path,
        skill_name=skill_name,
        profile=profile,
        classifications=classifications,
        objectives=tuple(objectives),
        required_branches=required_branches,
        allowed_operations=allowed_operations,
        forbidden_operations=forbidden_operations,
        max_calls=_positive_int(tool_policy["max_calls"], f"{path}: max_calls"),
        max_failed_calls=_positive_int(
            tool_policy["max_failed_calls"], f"{path}: max_failed_calls", allow_zero=True
        ),
        max_repeated_semantic_calls=_positive_int(
            tool_policy["max_repeated_semantic_calls"],
            f"{path}: max_repeated_semantic_calls",
            allow_zero=True,
        ),
        cases=tuple(cases),
    )
