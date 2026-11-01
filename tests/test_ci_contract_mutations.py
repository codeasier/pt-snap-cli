"""Acceptance and adversarial mutations for the bounded CI semantic reader."""

from copy import deepcopy

import pytest

from tests._ci_contract import command_tokens, commands, expression, matrix_rows
from tests.test_ci_tiers import project, validate_workflow, workflow


def _step(config, job, program, contains=None):
    matching = [
        command.step
        for command in commands(config["jobs"][job], config)
        if command.words[0] == program and (contains is None or contains in command.words)
    ]
    assert matching
    return matching[0]


def _rewrite(config, job, program, before, after, contains=None):
    step = _step(config, job, program, contains)
    assert before in step["run"]
    step["run"] = step["run"].replace(before, after)


def _renamed(config):
    for job in config["jobs"].values():
        job["name"] = "A display label, not a contract"
        for step in job["steps"]:
            step.pop("name", None)


def _actions_and_cache(config):
    for job in config["jobs"].values():
        for step in job["steps"]:
            if "uses" in step:
                step["uses"] = step["uses"].split("@")[0] + "@v99"
            if step.get("uses", "").startswith("actions/setup-python@"):
                step.setdefault("with", {})["cache"] = "pip"


def _quotes_and_commands(config):
    _rewrite(
        config,
        "test",
        "pytest",
        'pytest -m "not slow and not nightly"',
        "python -m pytest -m 'not (nightly or slow)'",
        "not slow and not nightly",
    )
    _rewrite(
        config,
        "test",
        "pytest",
        'pytest -m "not nightly" --cov --cov-report=xml --cov-report=term-missing',
        "python3 -m pytest --cov-report term-missing --cov -m 'not nightly' --cov-report xml",
        "--cov",
    )
    guard = _step(config, "test", "coverage")
    guard["run"] = (
        guard["run"]
        .replace("--include='", '--include "')
        .replace(".py'", '.py"')
        .replace("--fail-under=", "--fail-under ")
    )


def _conditions(config):
    _step(config, "test", "pytest", "--cov")["if"] = "${{ !(matrix.python-version != '3.13') }}"
    _step(config, "test", "pytest", "not slow and not nightly")[
        "if"
    ] = "('3.13' != matrix.python-version) && success()"
    config["jobs"]["dataset-acceptance"][
        "if"
    ] = "${{ github.event_name == 'workflow_dispatch' || ('schedule' == github.event_name) }}"


def _uppercase_events(config):
    config["jobs"]["dataset-acceptance"][
        "if"
    ] = "github.event_name == 'SCHEDULE' || github.event_name == 'WORKFLOW_DISPATCH'"


def _excluded_then_restored_matrix(config):
    matrix = config["jobs"]["test"]["strategy"]["matrix"]
    matrix["exclude"] = [{"python-version": "3.13"}]
    matrix["include"] = [{"python-version": "3.13"}]


def _split_and_merge(config):
    job = config["jobs"]["test"]
    guard = _step(config, "test", "coverage")
    index = job["steps"].index(guard)
    parts = [dict(guard, run=line) for line in guard["run"].splitlines() if line.strip()]
    job["steps"][index : index + 1] = parts
    # Merge full pytest with the first independent floor; labels are irrelevant.
    full = _step(config, "test", "pytest", "--cov")
    full["run"] += "\n" + parts[0]["run"]
    job["steps"].remove(parts[0])


def _and_chain(config):
    guard = _step(config, "test", "coverage")
    guard["run"] = " && ".join(guard["run"].splitlines())


def _include_matrix(config):
    matrix = config["jobs"]["test"]["strategy"]["matrix"]
    versions = matrix.pop("python-version")
    matrix["include"] = [{"python-version": version} for version in versions]


@pytest.mark.parametrize(
    "mutation",
    [
        _renamed,
        _actions_and_cache,
        _quotes_and_commands,
        _conditions,
        _uppercase_events,
        _excluded_then_restored_matrix,
        _split_and_merge,
        _and_chain,
        _include_matrix,
    ],
    ids=lambda mutation: mutation.__name__.removeprefix("_"),
)
def test_semantically_equivalent_workflow_refactors_are_accepted(mutation):
    config = workflow()
    mutation(config)
    validate_workflow(config, project())


def _weaken(config, case):
    job = config["jobs"]["test"]
    full = _step(config, "test", "pytest", "--cov")
    fast = _step(config, "test", "pytest", "not slow and not nightly")
    guard = _step(config, "test", "coverage")
    browser = _step(config, "browser", "pytest")
    if case == "missing-python":
        job["strategy"]["matrix"]["python-version"].remove("3.12")
    elif case == "excluded-python":
        job["strategy"]["matrix"]["exclude"] = [{"python-version": "3.12"}]
    elif case == "extra-python":
        job["strategy"]["matrix"]["include"] = [{"python-version": "3.14"}]
    elif case == "wrong-matrix-interpreter":
        next(
            step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-python")
        )["with"]["python-version"] = "3.13"
    elif case == "filtered-pr-trigger":
        config["on"]["pull_request"]["paths"] = ["never-tests/**"]
    elif case == "wrong-full-condition":
        full["if"] = "matrix.python-version == '3.12'"
    elif case == "uppercase-pr-exclusion":
        full["if"] += " && github.event_name != 'PULL_REQUEST'"
    elif case == "python-escape-condition":
        full["if"] += r" && '\x61' == 'a'"
    elif case == "wrong-unary-precedence":
        fast["if"] = "!matrix.python-version == '3.13'"
    elif case == "mixed-type-coercion":
        full["if"] += " && (true && github.event_name) == true"
    elif case == "wrong-provenance-base":
        step = next(
            step
            for step in config["jobs"]["snapshot-provenance"]["steps"]
            if "PR_BODY" in step.get("env", {})
        )
        step["env"]["BASE_SHA"] = "${{ github.event.pull_request.head.sha }}"
    elif case == "full-or-bypass":
        full["if"] += " || true"
    elif case == "skip-full-job":
        job["if"] = "github.event_name != 'pull_request'"
    elif case == "skippable-dependency":
        job["needs"] = "dataset-acceptance"
    elif case == "ignored-job-failure":
        job["continue-on-error"] = "true"
    elif case == "ignored-step-failure":
        full["continue-on-error"] = "true"
    elif case == "disabled-errexit":
        full["run"] = "set +e\n" + full["run"]
    elif case == "custom-shell":
        full["shell"] = "bash {0}"
    elif case == "default-shell":
        job["defaults"] = {"run": {"shell": "bash {0}"}}
    elif case == "wrong-directory":
        full["working-directory"] = "tests/core"
    elif case == "hidden-pytest-selector":
        full["env"] = {"PYTEST_ADDOPTS": "-k passing_only"}
    elif case == "optimized-away-wheel-assert":
        job["env"] = {"PYTHONOPTIMIZE": "1"}
    elif case == "suppressed-resource-warnings":
        full["env"] = {"PYTHONWARNINGS": "ignore"}
    elif case == "redirected-pythonpath":
        job["env"] = {"PYTHONPATH": "other-source"}
    elif case == "redirected-path":
        full["env"] = {"PATH": "fake-gate-binaries"}
    elif case == "shell-or-true":
        full["run"] += " || true"
    elif case == "shell-pipe":
        full["run"] += " | tee ignored.log"
    elif case == "and-list-swallow":
        full["run"] += " && pip --version\npip --version"
    elif case == "wrong-fast-selector":
        fast["run"] = fast["run"].replace("not slow and not nightly", "not slow or not nightly")
    elif case == "full-excludes-slow":
        full["run"] = full["run"].replace("not nightly", "not slow and not nightly")
    elif case == "full-includes-nightly":
        full["run"] = full["run"].replace("not nightly", "not nightly or slow")
    elif case == "pytest-k-filter":
        full["run"] += " -k passing_only"
    elif case == "pytest-path-filter":
        full["run"] += " tests/core"
    elif case == "coverage-threshold":
        guard["run"] = guard["run"].replace("--fail-under=90", "--fail-under=89")
    elif case == "coverage-combined-selector":
        guard["run"] = guard["run"].replace("*/core/snapshot_import_backend.py", "*/core/*.py")
    elif case == "coverage-wrong-file":
        guard["run"] = guard["run"].replace(
            "*/core/snapshot_import_backend.py", "*/core/import_metadata.py"
        )
    elif case == "coverage-before-measurement":
        job["steps"].remove(guard)
        job["steps"].insert(job["steps"].index(full), guard)
    elif case == "fixture-after-tests":
        fixture = _step(config, "test", "pytest", "tests/test_fixture_provenance.py")
        job["steps"].remove(fixture)
        job["steps"].append(fixture)
    elif case == "optional-browser":
        browser["env"]["PT_SNAP_REQUIRE_BROWSER"] = "0"
    elif case == "filtered-browser":
        browser["run"] += " -k zero_total"
    elif case == "missing-browser-install":
        install = _step(config, "browser", "playwright")
        install["run"] = "pip install -e '.[dev]'"
    elif case == "non-linux-browser":
        config["jobs"]["browser"]["runs-on"] = "macos-latest"
    elif case == "conditional-browser":
        browser["if"] = "github.event_name == 'schedule'"
    elif case == "nightly-runs-on-pr":
        config["jobs"]["dataset-acceptance"].pop("if")
    elif case == "nightly-not-manual":
        config["jobs"]["dataset-acceptance"]["if"] = "github.event_name == 'schedule'"
    elif case == "ambiguous-wheel":
        audit = _step(config, "test", ".github/scripts/audit_wheel.py")
        audit["run"] = audit["run"].replace(
            "assert len(wheels) == 1, wheels", "assert len(wheels) >= 1, wheels"
        )
    elif case == "cross-step-wheel-substitution":
        acceptance = _step(config, "test", ".github/scripts/clean_wheel_agent_acceptance.py")
        acceptance["run"] = "\n".join(
            line for line in acceptance["run"].splitlines() if not line.startswith("WHEEL=")
        )
        acceptance["env"] = {"WHEEL": "unrelated.whl"}
    elif case == "wrong-wheel":
        acceptance = _step(config, "test", ".github/scripts/clean_wheel_agent_acceptance.py")
        acceptance["run"] = acceptance["run"].replace(
            '--wheel "$WHEEL"', '--wheel "dist/unrelated.whl"'
        )
    elif case == "missing-sharded-acceptance":
        acceptance = _step(config, "test", ".github/scripts/clean_wheel_agent_acceptance.py")
        acceptance["run"] = acceptance["run"].replace(
            "--events-per-slice 4096", "--events-per-slice 8192"
        )
    elif case == "missing-differential-seeds":
        acceptance = _step(
            config, "dataset-acceptance", ".github/scripts/run_differential_acceptance.py"
        )
        acceptance["run"] = acceptance["run"].replace("--seed-count 200", "--seed-count 20")
    elif case == "hidden-failed-evidence":
        for step in config["jobs"]["dataset-acceptance"]["steps"]:
            if step.get("uses", "").startswith("actions/upload-artifact"):
                step.pop("if")
    elif case == "checkout-main-not-pr":
        job["steps"][0]["with"]["ref"] = "main"
    else:
        raise AssertionError(case)


@pytest.mark.parametrize(
    "case",
    [
        "missing-python",
        "excluded-python",
        "extra-python",
        "wrong-matrix-interpreter",
        "filtered-pr-trigger",
        "wrong-full-condition",
        "full-or-bypass",
        "uppercase-pr-exclusion",
        "python-escape-condition",
        "wrong-unary-precedence",
        "mixed-type-coercion",
        "wrong-provenance-base",
        "skip-full-job",
        "skippable-dependency",
        "ignored-job-failure",
        "ignored-step-failure",
        "disabled-errexit",
        "custom-shell",
        "default-shell",
        "wrong-directory",
        "hidden-pytest-selector",
        "redirected-pythonpath",
        "optimized-away-wheel-assert",
        "suppressed-resource-warnings",
        "redirected-path",
        "shell-or-true",
        "shell-pipe",
        "and-list-swallow",
        "wrong-fast-selector",
        "full-excludes-slow",
        "full-includes-nightly",
        "pytest-k-filter",
        "pytest-path-filter",
        "coverage-threshold",
        "coverage-combined-selector",
        "coverage-wrong-file",
        "coverage-before-measurement",
        "fixture-after-tests",
        "optional-browser",
        "filtered-browser",
        "missing-browser-install",
        "non-linux-browser",
        "conditional-browser",
        "nightly-runs-on-pr",
        "nightly-not-manual",
        "ambiguous-wheel",
        "wrong-wheel",
        "cross-step-wheel-substitution",
        "missing-sharded-acceptance",
        "missing-differential-seeds",
        "hidden-failed-evidence",
        "checkout-main-not-pr",
    ],
)
def test_workflow_gate_regressions_are_rejected(case):
    config = workflow()
    _weaken(config, case)
    with pytest.raises(AssertionError):
        validate_workflow(config, project())


@pytest.mark.parametrize("field,value", [("branch", False), ("fail_under", 89)])
def test_coverage_configuration_cannot_weaken(field, value):
    settings = deepcopy(project())
    settings["tool"]["coverage"]["run" if field == "branch" else "report"][field] = value
    with pytest.raises(AssertionError):
        validate_workflow(workflow(), settings)


def test_include_matrix_rows_never_become_new_cartesian_originals():
    assert matrix_rows(
        {
            "python-version": ["3.10"],
            "include": [{"python-version": "3.13"}, {"python-version": "3.13", "extra": "second"}],
        }
    ) == [
        {"python-version": "3.10"},
        {"python-version": "3.13"},
        {"python-version": "3.13", "extra": "second"},
    ]
    assert matrix_rows(
        {
            "python-version": ["3.10", "3.13"],
            "include": [{"cache": "pip"}],
            "exclude": [{"python-version": "3.10"}],
        }
    ) == [{"python-version": "3.13", "cache": "pip"}]


@pytest.mark.parametrize(
    "source",
    [
        "contains(github.event_name, 'push')",
        "unknown.context == 'yes'",
        "success || true",
        "github.event_name =~ 'push'",
    ],
)
def test_unknown_condition_syntax_is_not_guessed(source):
    with pytest.raises(AssertionError):
        expression(source, {"github.event_name": "push"})


@pytest.mark.parametrize(
    "script",
    [
        "pytest || true",
        "pytest && pip --version; pip --version",
        "if true; then pytest; fi",
        "! pytest",
        "pytest &",
        "pytest > result.txt",
        "set +e\npytest",
        "exit 0\npytest",
        "pytest() { return 0; }; pytest",
    ],
)
def test_shell_failure_suppression_and_uninterpreted_control_flow_are_rejected(script):
    with pytest.raises(AssertionError):
        command_tokens(script)


def test_expression_semantics_match_github_not_python_literals_or_precedence():
    assert expression("'PUSH' == 'push'", {})
    assert expression("!'nonempty' == false", {})
    assert expression("'p''ush' != 'push'", {})
    assert not expression(r"'\x61' == 'a'", {})
    assert expression("'p''ush' == 'P''USH'", {})
    with pytest.raises(AssertionError, match="Mixed-type"):
        expression("(true && 'push') == true", {})
    with pytest.raises(AssertionError):
        expression("\"push\" == 'push'", {})
