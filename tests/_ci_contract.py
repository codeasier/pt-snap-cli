"""Small, fail-closed semantic reader for this repository's CI gate language.

This is deliberately not a general shell or GitHub Actions interpreter. Harmless
formatting/quoting, action versions, boolean rearrangements and sequential step
splits/merges are supported. New shell control flow or expression features need
an explicit contract extension and negative tests, not substring acceptance.
"""

from __future__ import annotations

import ast
import itertools
import re
import shlex
from dataclasses import dataclass

EVENTS = ("pull_request", "push", "workflow_call", "schedule", "workflow_dispatch")
PYTHONS = ("3.10", "3.11", "3.12", "3.13")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def expression(source, values, status="success"):
    """Evaluate the supported GHA grammar, including its quoting and precedence.

    GitHub string equality ignores case; quotes escape by doubling apostrophes,
    not by Python backslash escapes. Mixed-type loose coercion is unsupported.
    Reference: https://docs.github.com/en/actions/reference/workflows-and-actions/expressions
    """
    if source is None:
        return status == "success"
    source = str(source).strip()
    if source.startswith("${{") and source.endswith("}}"):
        source = source[3:-2].strip()
    pattern = re.compile(r"\s*(?:('(?:[^']|'')*')|([\w.-]+)|(&&|\|\||==|!=|!|\(|\)))")
    position = 0
    tokens = []
    uses_status = False
    while position < len(source):
        match = pattern.match(source, position)
        require(match is not None, f"Unsupported CI condition: {source}")
        literal, name, operator = match.groups()
        position = match.end()
        if literal is not None:
            value = literal[1:-1].replace("''", "'")
            require(value.isascii(), "Non-ASCII CI comparison literals need explicit support")
            tokens.append(("value", value))
        elif name is not None:
            if name in {"always", "success", "failure", "cancelled"}:
                call = re.match(r"\s*\(\s*\)", source[position:])
                require(call is not None, "Status predicate must be called")
                position += call.end()
                uses_status = True
                tokens.append(("value", name == "always" or name == status))
            elif name in {"true", "false"}:
                tokens.append(("value", name == "true"))
            else:
                require(name in values, f"Unsupported CI context: {name}")
                tokens.append(("value", values[name]))
        else:
            tokens.append((operator, None))
    index = 0

    def take(kind):
        nonlocal index
        if index < len(tokens) and tokens[index][0] == kind:
            index += 1
            return True
        return False

    def unary():
        nonlocal index
        if take("!"):
            return not unary()
        if take("("):
            value = disjunction()
            require(take(")"), f"Unclosed CI condition: {source}")
            return value
        require(index < len(tokens) and tokens[index][0] == "value", f"Expected CI value: {source}")
        value = tokens[index][1]
        index += 1
        return value

    def comparison():
        left = unary()
        operator = tokens[index][0] if index < len(tokens) else None
        if operator in {"==", "!="}:
            take(operator)
            right = unary()
            require(type(left) is type(right), "Mixed-type CI coercion is unsupported")
            if isinstance(left, str):
                require(
                    left.isascii() and right.isascii(),
                    "Non-ASCII CI comparison needs explicit support",
                )
                left, right = left.lower(), right.lower()
            else:
                require(isinstance(left, bool), "Only string/bool CI comparisons are supported")
            return (left == right) if operator == "==" else (left != right)
        return left

    def conjunction():
        value = comparison()
        while take("&&"):
            right = comparison()
            value = right if value else value
        return value

    def disjunction():
        value = conjunction()
        while take("||"):
            right = conjunction()
            value = value if value else right
        return value

    value = disjunction()
    require(index == len(tokens), f"Unsupported CI condition: {source}")
    return bool(value) and (uses_status or status == "success")


def matrix_rows(matrix):
    axes = {key: value for key, value in matrix.items() if key not in {"include", "exclude"}}
    require(
        all(isinstance(value, list) and value for value in axes.values()),
        "Matrix axes must be explicit nonempty lists",
    )
    originals = (
        [dict(zip(axes, values, strict=True)) for values in itertools.product(*axes.values())]
        if axes
        else []
    )
    # GitHub applies excludes before includes, which may add excluded rows back.
    originals = [
        row
        for row in originals
        if not any(
            all(row.get(key) == value for key, value in exclusion.items())
            for exclusion in matrix.get("exclude", [])
        )
    ]
    rows = [dict(row) for row in originals]
    for addition in matrix.get("include", []):
        matched = False
        for index, original in enumerate(originals):
            row = rows[index]
            if all(
                key not in original or original[key] == value for key, value in addition.items()
            ):
                row.update(addition)
                matched = True
        if not matched:
            rows.append(dict(addition))
            # Includes do not form new Cartesian base combinations.
    return rows


WHEEL_PROGRAM = """from pathlib import Path; wheels = sorted(Path("dist").glob("*.whl")); assert len(wheels) == 1, wheels; print(wheels[0])"""


def _canonical_program(program):
    try:
        return ast.dump(ast.parse(program))
    except SyntaxError as exc:
        raise AssertionError("Invalid wheel-selection program") from exc


def command_tokens(script):
    """Read failure-propagating simple commands, never search inside run text."""
    script = script.replace("\\\n", " ")

    def wheel(match):
        name, invocation = match.groups()
        words = shlex.split(invocation)
        require(
            len(words) == 3 and words[0] in {"python", "python3"} and words[1] == "-c",
            "Unsupported wheel selection",
        )
        require(
            _canonical_program(words[2]) == _canonical_program(WHEEL_PROGRAM),
            "Wheel selection must require exactly one built wheel",
        )
        return f"__verified_wheel__ {name}"

    script = re.sub(r"(?m)^\s*([A-Z_][A-Z_0-9]*)=\$\((.+)\)\s*$", wheel, script)
    # The interpreter path probe is one audited, side-effect-free substitution.
    script = script.replace(
        "\"$(python -c 'import sys; print(sys.executable)')\"", '"__selected_python__"'
    )
    tokens = []
    for line in script.splitlines():
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        tokens.extend(lexer)
        tokens.append("\n")
    commands, current, separators = [], [], []
    for token in tokens + ["\n"]:
        if token and all(char in ";&|\n" for char in token):
            require(
                "|" not in token and token.replace("\n", "") in {"", ";", "&&"},
                "Shell OR/pipes/background/control flow can hide a failed gate",
            )
            if current:
                commands.append(current)
                current = []
                separators.append(token.replace("\n", "") or ";")
        else:
            current.append(token)
    # `a && b; c` suppresses errexit for a. Only a single terminal AND chain is safe.
    if "&&" in separators:
        require(
            all(separator == "&&" for separator in separators[:-1]),
            "Mixed AND/sequential shell lists can ignore failures",
        )
    result = []
    for words in commands:
        if words[0] == "set":
            require(
                words[1:] in [["-euo", "pipefail"], ["-eu"], ["-e"]],
                "Shell failure handling must not be disabled",
            )
            continue
        if words[0] == "__verified_wheel__":
            result.append(tuple(words))
            continue
        require(
            not any(
                any(char in word for char in ("`", ">", "<")) or "$(" in word for word in words
            ),
            "Unsupported shell substitution/redirection",
        )
        if words[0] in {"python", "python3", "python3.13"}:
            words = words[2:] if len(words) > 2 and words[1] == "-m" else words[1:]
        require(
            words
            and words[0]
            in {
                "pytest",
                "pip",
                "ruff",
                "black",
                "basedpyright",
                "coverage",
                "build",
                "playwright",
                ".github/scripts/audit_wheel.py",
                ".github/scripts/clean_wheel_agent_acceptance.py",
                ".github/scripts/run_dataset_acceptance.py",
                ".github/scripts/run_differential_acceptance.py",
                ".github/scripts/check_snapshot_provenance.py",
                ".github/scripts/check_critical_coverage.py",
            },
            f"Unsupported gate command: {words}",
        )
        result.append(tuple(words))
    return result


def options(words, valued=(), flags=()):
    result, positional = {}, []
    index = 0
    while index < len(words):
        word = words[index]
        if word.startswith("-"):
            key, separator, value = word.partition("=")
            require(key in valued or key in flags, f"Unsupported gate option: {word}")
            if key in valued and not separator:
                index += 1
                require(index < len(words), f"Missing value: {key}")
                value = words[index]
            if key in flags:
                require(not separator, f"Flag does not take a value: {key}")
                value = True
            result.setdefault(key, []).append(value)
        else:
            positional.append(word)
        index += 1
    return result, positional


@dataclass
class Command:
    words: tuple[str, ...]
    step: dict
    index: int
    env: dict


def commands(job, workflow=None):
    require(job.get("continue-on-error", "false") == "false", "Jobs must propagate gate failures")
    require(not job.get("needs"), "Independent gates cannot depend on skippable jobs")
    defaults = (workflow or {}).get("defaults", {}).get("run", {}) | job.get("defaults", {}).get(
        "run", {}
    )
    require(not defaults.get("working-directory"), "Gate working directory must be repository root")
    result = []
    for step in job["steps"]:
        require(
            step.get("continue-on-error", "false") == "false", "Steps must propagate gate failures"
        )
        if "run" not in step:
            continue
        require(
            step.get("shell", defaults.get("shell", "bash")) == "bash",
            "Gate shell must retain bash errexit",
        )
        require(not step.get("working-directory"), "Gate working directory must be repository root")
        env = (workflow or {}).get("env", {}) | job.get("env", {}) | step.get("env", {})
        require(
            not any(
                key.startswith(("PYTEST_", "COVERAGE_"))
                or key
                in {
                    "BASH_ENV",
                    "ENV",
                    "PATH",
                    "PYTHONPATH",
                    "PYTHONHOME",
                    "VIRTUAL_ENV",
                    "PYTHONOPTIMIZE",
                    "PYTHONWARNINGS",
                }
                for key in env
            ),
            "Environment must not override gate execution",
        )
        for words in command_tokens(step["run"]):
            result.append(Command(words, step, len(result), env))
    return result


def select(commands_, program):
    return [command for command in commands_ if command.words[0] == program]


def one(commands_, program):
    matching = select(commands_, program)
    require(len(matching) == 1, f"Expected exactly one {program} gate, got {len(matching)}")
    return matching[0]


def condition_matches(
    job, step, *, versions=PYTHONS, events=EVENTS, predicate, statuses=("success",)
):
    for version, event, status in itertools.product(versions, events, statuses):
        values = {"matrix.python-version": version, "github.event_name": event}
        actual = expression(job.get("if"), values, status) and expression(
            step.get("if"), values, status
        )
        # Job-level default success does not suppress always() artifact steps in
        # an already-running job after a step failure.
        if status != "success":
            actual = expression(job.get("if"), values, "success") and expression(
                step.get("if"), values, status
            )
        require(
            actual == predicate(version, event, status),
            f"Wrong gate condition for Python {version}, {event}, {status}: {step.get('if')}",
        )


def marker_truth(source, slow, nightly):
    tree = ast.parse(source, mode="eval")

    def evaluate(node):
        if isinstance(node, ast.Name):
            require(node.id in {"slow", "nightly"}, f"Unexpected marker selector: {node.id}")
            return {"slow": slow, "nightly": nightly}[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not evaluate(node.operand)
        if isinstance(node, ast.BoolOp):
            values = [evaluate(value) for value in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        raise AssertionError(f"Unsupported pytest marker selector: {source}")

    return evaluate(tree.body)


def pytest_options(command, expected_marker=None, paths=(), coverage=False):
    opts, positional = options(
        command.words[1:],
        valued=("-m", "--cov-report"),
        flags=("--cov", "-q", "-v", "-vv", "-rs", "-ra"),
    )
    require(
        set(positional) == set(paths) and len(positional) == len(paths),
        "Pytest paths must cover the complete intended gate",
    )
    require(
        opts.get("--cov", []) == ([True] if coverage else []),
        "Coverage must run only on the full tier",
    )
    if expected_marker is None:
        require("-m" not in opts, "Required test paths cannot be marker-filtered")
    else:
        require(len(opts.get("-m", [])) == 1, "Exactly one pytest marker expression is required")
        for slow, nightly in itertools.product((False, True), repeat=2):
            require(
                marker_truth(opts["-m"][0], slow, nightly) == expected_marker(slow, nightly),
                "Pytest marker selector changes tier membership",
            )
    require(
        set(opts.get("--cov-report", [])) == ({"xml", "term-missing"} if coverage else set()),
        "Coverage outputs changed",
    )
