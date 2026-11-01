"""Protect CI behavior without coupling gates to human labels or shell quoting."""

from pathlib import Path

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10: also a pytest dependency.
    import tomli as tomllib

from tests._ci_contract import (
    EVENTS,
    PYTHONS,
    commands,
    condition_matches,
    matrix_rows,
    one,
    options,
    pytest_options,
    require,
    select,
)


def workflow():
    return yaml.load(
        Path(".github/workflows/test.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )


def project():
    return tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))


def _action_steps(job, action):
    return [step for step in job["steps"] if step.get("uses", "").partition("@")[0] == action]


def _full(job, step):
    condition_matches(job, step, predicate=lambda version, event, status: version == "3.13")


def _all(job, step):
    condition_matches(job, step, predicate=lambda version, event, status: True)


def _check_wheel_gate(job, all_commands, command, *, nightly=False):
    opts, positional = options(
        command.words[1:], valued=("--wheel", "--fixture", "--events-per-slice", "--output-dir")
    )
    require(
        not positional and len(opts.get("--wheel", [])) == 1,
        "Wheel gate must consume one verified wheel",
    )
    variable = opts["--wheel"][0]
    require(
        variable.startswith("$") and len(variable) > 1, "Wheel gate must consume the built wheel"
    )
    variable = variable[1:].removeprefix("{").removesuffix("}")
    selectors = [
        item
        for item in all_commands
        if item.words == ("__verified_wheel__", variable)
        and item.index < command.index
        and item.step is command.step
    ]
    require(selectors, "Wheel selection must validate exactly one artifact before use")
    if nightly:
        _nightly(job, selectors[-1].step)
        _nightly(job, command.step)
    else:
        _full(job, selectors[-1].step)
        _full(job, command.step)
    return opts


def validate_tiers(config, settings):
    job = config["jobs"]["test"]
    rows = matrix_rows(job["strategy"]["matrix"])
    require(
        sorted(row["python-version"] for row in rows) == list(PYTHONS),
        "Compatibility matrix must execute each supported Python exactly once",
    )
    all_commands = commands(job, config)
    pytest = select(all_commands, "pytest")
    require(len(pytest) == 3, "Fixture, compatibility and full pytest gates are mandatory")
    fixture = [command for command in pytest if "tests/test_fixture_provenance.py" in command.words]
    require(len(fixture) == 1, "Missing fixture provenance gate")
    fixture = fixture[0]
    pytest_options(fixture, paths=("tests/test_fixture_provenance.py",))
    _all(job, fixture.step)
    full = [command for command in pytest if "--cov" in command.words]
    require(len(full) == 1, "Exactly one full coverage gate is mandatory")
    full = full[0]
    fast = next(command for command in pytest if command is not full and command is not fixture)
    pytest_options(fast, expected_marker=lambda slow, nightly: not slow and not nightly)
    pytest_options(full, expected_marker=lambda slow, nightly: not nightly, coverage=True)
    condition_matches(job, fast.step, predicate=lambda version, event, status: version != "3.13")
    _full(job, full.step)
    require(
        fixture.index < fast.index and fixture.index < full.index,
        "Fixture provenance must precede execution",
    )
    require(
        any(
            marker.partition(":")[0] == "nightly"
            for marker in settings["tool"]["pytest"]["ini_options"]["markers"]
        ),
        "Nightly marker must be registered",
    )

    coverage = settings["tool"]["coverage"]
    require(coverage["run"]["branch"] is True, "Branch coverage is mandatory")
    require(
        coverage["report"]["fail_under"] >= 90,
        "Overall coverage floor must not decrease",
    )
    require(
        coverage["run"].get("source") == ["pt_snap_cli"],
        "Coverage must measure the entire runtime package",
    )
    require(
        set(coverage["run"].get("omit", [])) == {"*/tests/*", "*/__pycache__/*"},
        "Runtime modules cannot be omitted from coverage",
    )
    require(
        not coverage["run"].get("include")
        and not coverage["report"].get("include")
        and not coverage["report"].get("omit"),
        "Coverage measurement/report selectors must not narrow the package",
    )
    require(
        set(coverage["report"].get("exclude_lines", []))
        == {"pragma: no cover", "if __name__ == .__main__.", "if TYPE_CHECKING:"}
        and not coverage["report"].get("exclude_also")
        and not any(key.startswith("partial_") for key in coverage["report"]),
        "Coverage exclusions must not hide runtime statements or branches",
    )
    require(
        not select(all_commands, "coverage"),
        "Alternate coverage commands cannot replace or bypass the critical checker",
    )
    guard = one(all_commands, ".github/scripts/check_critical_coverage.py")
    require(
        len(guard.words) == 1,
        "Critical coverage checker must use its complete fixed inventory without overrides",
    )
    require(full.index < guard.index, "Coverage must be measured before its floors")
    _full(job, guard.step)

    build = one(all_commands, "build")
    require(build.words[1:] == ("--wheel",), "Build must produce the wheel")
    _full(job, build.step)
    audit = one(all_commands, ".github/scripts/audit_wheel.py")
    require(
        set(_check_wheel_gate(job, all_commands, audit)) == {"--wheel"},
        "Wheel audit arguments changed",
    )
    acceptance = one(all_commands, ".github/scripts/clean_wheel_agent_acceptance.py")
    opts = _check_wheel_gate(job, all_commands, acceptance)
    require(
        opts.get("--fixture") == ["tests/fixtures/snapshots/snapshot_with_empty_cache.pkl"]
        and opts.get("--events-per-slice") == ["4096"]
        and set(opts) == {"--wheel", "--fixture", "--events-per-slice"},
        "Clean-wheel fixture/sharded acceptance is mandatory",
    )
    require(
        full.index < build.index < audit.index < acceptance.index,
        "Wheel acceptance must follow tests, build and audit",
    )
    upload = [
        step
        for step in _action_steps(job, "actions/upload-artifact")
        if step.get("with", {}).get("path") == "coverage.xml"
    ]
    require(len(upload) == 1, "Coverage evidence must be uploaded")
    condition_matches(
        job,
        upload[0],
        predicate=lambda version, event, status: version == "3.13",
        statuses=("success", "failure", "cancelled"),
    )


def _nightly(job, step, *, always=False):
    condition_matches(
        job,
        step,
        predicate=lambda version, event, status: event in {"schedule", "workflow_dispatch"},
        statuses=("success", "failure", "cancelled") if always else ("success",),
    )


def validate_nightly(config):
    require("workflow_dispatch" in config["on"], "Manual acceptance dispatch is mandatory")
    require(
        config["on"].get("schedule") == [{"cron": "17 3 * * *"}],
        "Nightly acceptance schedule changed",
    )
    job = config["jobs"]["dataset-acceptance"]
    require(job["timeout-minutes"] == "30", "Dataset acceptance timeout changed")
    checkout = _action_steps(job, "actions/checkout")
    require(
        len(checkout) == 1 and checkout[0]["with"].get("fetch-depth") == "0",
        "Dataset acceptance needs full checkout history",
    )
    require(
        "".join(checkout[0]["with"].get("ref", "").split()) == "${{github.sha}}",
        "Dataset acceptance must use the dispatched commit",
    )
    setup = _action_steps(job, "actions/setup-python")
    require(
        len(setup) == 1 and setup[0].get("with", {}).get("python-version") == "3.13",
        "Nightly acceptance requires Python 3.13",
    )
    _nightly(job, setup[0])
    all_commands = commands(job, config)
    for command in all_commands:
        _nightly(job, command.step)
    fixture = one(all_commands, "pytest")
    pytest_options(fixture, paths=("tests/test_fixture_provenance.py",))
    build = one(all_commands, "build")
    require(build.words[1:] == ("--wheel",), "Nightly acceptance requires a built wheel")
    audit = one(all_commands, ".github/scripts/audit_wheel.py")
    require(
        set(_check_wheel_gate(job, all_commands, audit, nightly=True)) == {"--wheel"},
        "Nightly wheel audit arguments changed",
    )
    acceptance = one(all_commands, ".github/scripts/run_dataset_acceptance.py")
    opts = _check_wheel_gate(job, all_commands, acceptance, nightly=True)
    require(
        opts.get("--output-dir") == [".tmp/dataset-acceptance"]
        and set(opts) == {"--wheel", "--output-dir"},
        "Nightly evidence destination changed",
    )
    differential = one(all_commands, ".github/scripts/run_differential_acceptance.py")
    opts, positional = options(differential.words[1:], valued=("--seed-count", "--output-dir"))
    require(
        not positional
        and opts == {"--seed-count": ["200"], "--output-dir": [".tmp/differential-acceptance"]},
        "Required 200-seed paired acceptance must not weaken",
    )
    require(
        fixture.index < build.index < audit.index < acceptance.index < differential.index,
        "Nightly acceptance order must preserve provenance/build/audit",
    )
    uploads = _action_steps(job, "actions/upload-artifact")
    for path in (".tmp/dataset-acceptance/", ".tmp/differential-acceptance/*.log"):
        matching = [
            step for step in uploads if path in step.get("with", {}).get("path", "").splitlines()
        ]
        require(len(matching) == 1, f"Missing acceptance evidence upload: {path}")
        upload = matching[0]
        _nightly(job, upload, always=True)
        require(
            upload["with"].get("if-no-files-found") == "error"
            and upload["with"].get("include-hidden-files") == "true",
            "Missing acceptance evidence must fail",
        )
        require(
            "${{github.sha}}" in "".join(upload["with"].get("name", "").split()),
            "Evidence must identify the checkout commit",
        )
        require(
            job["steps"].index(upload) > job["steps"].index(differential.step),
            "Evidence must be uploaded after acceptance",
        )


def validate_other_gates(config):
    require(config["permissions"] == {"contents": "read"}, "CI permissions must stay read-only")
    require(
        "pull_request_target" not in config["on"], "Untrusted PRs cannot use privileged trigger"
    )
    require(
        set(config["on"]["pull_request"]["types"])
        == {"opened", "synchronize", "reopened", "edited"},
        "PR gate triggers changed",
    )
    require(set(EVENTS) <= set(config["on"]), "Required CI triggers are missing")
    for event in ("push", "pull_request"):
        require(config["on"][event].get("branches") == ["main"], "Main push/PR gates are required")
        require(
            not set(config["on"][event]) & {"paths", "paths-ignore", "branches-ignore"},
            "Gate triggers cannot silently filter changes",
        )
    for name in ("snapshot-provenance", "lint", "browser", "test"):
        job = config["jobs"][name]
        require(
            job.get("continue-on-error", "false") == "false", "Job failures must not be ignored"
        )
        require(not job.get("needs"), "Independent CI gates cannot depend on skippable jobs")
        require(
            job.get("permissions", {"contents": "read"}) == {"contents": "read"},
            "Job permissions must stay read-only",
        )
        checkout = _action_steps(job, "actions/checkout")
        require(len(checkout) == 1, "Exactly one gate checkout is required")
        require(
            "".join(checkout[0].get("with", {}).get("ref", "").split())
            == "${{github.event.pull_request.head.sha||github.sha}}",
            "CI must check the published PR/triggering commit",
        )
        _all(job, checkout[0])
        require(job["steps"].index(checkout[0]) == 0, "Gate checkout must precede commands")
        if name != "snapshot-provenance":
            setup = _action_steps(job, "actions/setup-python")
            require(len(setup) == 1, "Every execution tier must select its Python")
            version = "".join(setup[0].get("with", {}).get("python-version", "").split())
            require(
                version == ("${{matrix.python-version}}" if name == "test" else "3.13"),
                "Python setup must match its execution tier",
            )
            _all(job, setup[0])
    provenance = config["jobs"]["snapshot-provenance"]
    require(
        _action_steps(provenance, "actions/checkout")[0]["with"].get("fetch-depth") == "0",
        "Provenance requires full history",
    )
    # This PR gate is a simple command. The separate non-PR base-resolution
    # script is deliberately not interpreted as part of the tier contract.
    pr_steps = [step for step in provenance["steps"] if "PR_BODY" in step.get("env", {})]
    require(len(pr_steps) == 1, "PR provenance decision gate is required")
    pr = one(commands({"steps": pr_steps}, config), ".github/scripts/check_snapshot_provenance.py")
    for key, context in (("BASE_SHA", "base.sha"), ("HEAD_SHA", "head.sha"), ("PR_BODY", "body")):
        require(
            "".join(pr.env.get(key, "").split())
            == "${{github.event.pull_request." + context + "}}",
            "PR provenance must compare the actual base/head and decision body",
        )
    opts, positional = options(
        pr.words[1:], valued=("--base", "--head"), flags=("--require-decision",)
    )
    require(
        not positional
        and opts
        == {"--base": ["$BASE_SHA"], "--head": ["$HEAD_SHA"], "--require-decision": [True]},
        "PR provenance decision cannot be bypassed",
    )
    condition_matches(
        provenance, pr.step, predicate=lambda version, event, status: event == "pull_request"
    )
    lint = config["jobs"]["lint"]
    lint_commands = commands(lint, config)
    for program, arguments in (
        ("ruff", ("check", ".")),
        ("black", ("--check", ".")),
        ("basedpyright", ("--pythonpath", "__selected_python__")),
    ):
        command = one(lint_commands, program)
        require(
            command.words[1:] == arguments, f"{program} must check the intended source/interpreter"
        )
        _all(lint, command.step)
    browser = config["jobs"]["browser"]
    require(
        browser["runs-on"].startswith("ubuntu-"), "Real Chromium regression must remain on Linux"
    )
    browser_commands = commands(browser, config)
    install = one(browser_commands, "playwright")
    opts, positional = options(install.words[1:], flags=("--with-deps",))
    require(
        positional == ["install", "chromium"] and opts == {"--with-deps": [True]},
        "CI must install real Chromium with OS dependencies",
    )
    test = one(browser_commands, "pytest")
    pytest_options(
        test, paths=("tests/test_fixture_provenance.py", "tests/test_memory_tree_browser.py")
    )
    require(
        test.env.get("PT_SNAP_REQUIRE_BROWSER") == "1", "Browser absence must fail the required job"
    )
    require(install.index < test.index, "Chromium must be installed before required regression")
    _all(browser, install.step)
    _all(browser, test.step)


def validate_workflow(config, settings):
    validate_tiers(config, settings)
    validate_nightly(config)
    validate_other_gates(config)


def test_ci_semantic_contract():
    validate_workflow(workflow(), project())
