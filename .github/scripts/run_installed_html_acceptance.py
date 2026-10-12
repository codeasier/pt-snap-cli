"""Pinned candidate wheel -> isolated console -> real loopback Chromium acceptance.

Only summary.json and masked screenshots are public artifacts. Raw fixture paths,
HTML, database and CLI outputs stay in a temporary private directory.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import traceback
import venv
from collections import Counter, defaultdict
from contextlib import closing
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zipfile import ZipFile

CANDIDATE = "07bdf660f10f03a9c13ab313fae149adf62355f8"
FIXTURE_NAME = "snapshot_with_empty_cache.pkl"
FIXTURE_SHA = "d5cb93fa1e1689f0debb31cbc064d1cbc13f2f44204b9c76dd2c47aa8ba85b3f"
LOCAL_REFERENCE_WHEEL_SHA = "b3448724b16a638cf68d00b62cedfa892b6c396b8dc9b9550187357f95290bf3"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class AcceptanceError(RuntimeError):
    """Only fixed, explicitly safe diagnostic messages may use this type."""


def require(condition, message):
    if not condition:
        raise AcceptanceError(message)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_input(source, wheel):
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    require(actual == CANDIDATE, "Candidate source SHA mismatch")
    audit = load_module(source / ".github/scripts/audit_wheel.py", "html_wheel_audit")
    require(not audit.audit_wheel(wheel, source / "src"), "Wheel/source byte audit failed")
    provenance = load_module(source / "tests/_fixture_provenance.py", "html_fixture_gate")
    fixtures = source / "tests/fixtures/snapshots"
    provenance.verify_snapshot_fixtures(fixtures, fixtures / "SHA256SUMS")
    fixture = fixtures / FIXTURE_NAME
    require(
        sha(fixture) == FIXTURE_SHA and fixture.stat().st_size == 617060,
        "Trusted executable fixture identity mismatch",
    )
    return fixture


def tree_oracle(db, event):
    """Reconstruct caller paths per live block; no product imports or template SQL."""
    expected = defaultdict(
        lambda: {"size_bytes": 0, "requested_bytes": 0, "block_count": 0, "self_bytes": 0}
    )
    with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as con:
        con.row_factory = sqlite3.Row
        blocks = con.execute(
            "SELECT b.*,t.callstackId FROM block_0 b LEFT JOIN trace_entry_0 t "
            "ON t.id=b.allocEventId WHERE (b.allocEventId=-1 OR b.allocEventId<=?) "
            "AND (b.freeEventId IS NULL OR b.freeEventId<0 OR b.freeEventId>?)",
            (event, event),
        ).fetchall()
        for block in blocks:
            path = ["root"]
            if block["allocEventId"] == -1:
                path.append("static" if block["freeEventId"] == -1 else "preexisting_live_at_event")
            else:
                frames = con.execute(
                    "SELECT frameId FROM callstack_frame WHERE callstackId=? ORDER BY position DESC",
                    (block["callstackId"],),
                ).fetchall()
                if frames:
                    identity = "frame"
                    for frame in frames:
                        identity += "/" + str(frame[0])
                        path.append(identity)
                else:
                    empty = con.execute(
                        "SELECT 1 FROM callstack_frame_manifest WHERE callstackId=? AND frameCount=0",
                        (block["callstackId"],),
                    ).fetchone()
                    path.append("empty_callstack" if empty else "missing")
            for identity in path:
                row = expected[identity]
                row["size_bytes"] += block["size"]
                row["requested_bytes"] += block["requestedSize"] or 0
                row["block_count"] += 1
            expected[path[-1]]["self_bytes"] += block["size"]
    return dict(expected)


def compare_tree(nodes, expected):
    require(set(nodes) == set(expected), "Oracle node identity set mismatch")
    total = expected["root"]["size_bytes"]
    for identity, row in expected.items():
        for field, value in row.items():
            require(nodes[identity][field] == value, f"Oracle {field} mismatch")
        percent = round(row["size_bytes"] * 100 / total, 4) if total else None
        require(nodes[identity]["percent_of_total"] == percent, "Oracle proportion mismatch")


def sanitized_screenshot(page, output, name, nodes):
    # Mask every surface capable of rendering fixture labels/callstacks or search text.
    # This leaves chart geometry, controls and numeric totals visible for proof.
    selectors = [
        "#chart text",
        "#detail",
        "#focus-path",
        "#children-list",
        "#search-results",
        "#search",
    ]
    covered = page.locator(",".join(selectors)).all_text_contents()
    require(
        all(
            n["label"] in "\n".join(covered)
            for n in nodes.values()
            if page.locator('#chart .node[data-node-id="' + n["node_id"] + '"]').count()
        ),
        "Screenshot privacy coverage failed",
    )
    target = output / f"{name}.png"
    raw = page.screenshot(full_page=True, mask=[page.locator(s) for s in selectors])
    require(raw.startswith(b"\x89PNG\r\n\x1a\n"), "Invalid screenshot PNG")
    cursor = 8
    while cursor < len(raw):
        require(cursor + 12 <= len(raw), "Incomplete screenshot PNG chunk")
        length = int.from_bytes(raw[cursor : cursor + 4], "big")
        kind = raw[cursor + 4 : cursor + 8]
        require(kind not in {b"tEXt", b"zTXt", b"iTXt"}, "Unexpected PNG text metadata")
        cursor += length + 12
        require(cursor <= len(raw), "Incomplete screenshot PNG payload")
    # No rejected bytes reach the public allowlist, even when CI uploads after failure.
    with tempfile.NamedTemporaryFile(
        dir=output.parent, prefix="html-proof-", delete=False
    ) as staged:
        staged.write(raw)
        staging_path = Path(staged.name)
    try:
        os.replace(staging_path, target)
    finally:
        staging_path.unlink(missing_ok=True)
    return {
        "name": target.name,
        "sha256": sha(target),
        "privacy": "all fixture-text surfaces masked",
    }


class QuietHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *_args):
        pass


def browser_checks(html, nodes, output, summary):
    from playwright.sync_api import expect, sync_playwright

    errors = []
    root = nodes["root"]
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(html.parent))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as runtime:
            with runtime.chromium.launch(headless=True) as browser:
                summary["browser_version"] = browser.version
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1000}, locale="en-US"
                )
                try:
                    page = context.new_page()
                    page.on("pageerror", lambda _e: errors.append("pageerror"))
                    page.on(
                        "console",
                        lambda e: errors.append("console-error") if e.type == "error" else None,
                    )

                    def selected(identity):
                        expect(page.locator("#chart .node").first).to_have_attribute(
                            "data-node-id", identity
                        )
                        expect(page.locator("#detail")).to_contain_text(identity)
                        require(
                            page.locator("#focus-path").evaluate("e=>e===document.activeElement"),
                            "Keyboard focus not retained",
                        )

                    def geometry():
                        return page.locator("#chart .node").evaluate_all(
                            "gs=>gs.map(g=>({id:g.dataset.nodeId,width:Number(g.querySelector('rect').getAttribute('width'))}))"
                        )

                    def shot(name):
                        summary["screenshots"].append(
                            sanitized_screenshot(page, output, name, nodes)
                        )

                    page.goto(
                        f"http://127.0.0.1:{server.server_port}/{html.name}", wait_until="load"
                    )
                    expect(page.locator("#chart .node")).to_have_count(len(nodes))
                    expect(page.locator("#summary")).to_have_text(
                        f"Showing {root['size_bytes']:,} bytes"
                    )
                    initial = geometry()
                    for row in initial:
                        wanted = max(
                            0, 1200 * nodes[row["id"]]["size_bytes"] / root["size_bytes"] - 0.6
                        )
                        require(
                            abs(row["width"] - wanted) < 1e-6, "DOM proportional geometry mismatch"
                        )
                    summary["checks"].append("initial-node-count-bytes-proportions")
                    shot("initial")
                    deepest = max(nodes.values(), key=lambda n: n["depth"])
                    search = page.locator("#search")
                    search.fill(deepest["node_id"].upper())
                    expect(page.locator("#search-results button")).to_have_count(1)
                    require(geometry() == initial, "Search changed proportional layout")
                    shot("search")
                    # Reach result via native Tab order, then Enter, rather than focusing it directly.
                    search.focus()
                    for _ in range(200):
                        page.keyboard.press("Tab")
                        if page.locator("#search-results button").evaluate(
                            "e=>e===document.activeElement"
                        ):
                            break
                    else:
                        raise AcceptanceError("Search result unreachable by keyboard")
                    page.keyboard.press("Enter")
                    selected(deepest["node_id"])
                    shot("deep-focus")
                    summary["checks"].append("case-insensitive-search-keyboard-deep-focus")
                    page.locator("#parent").click()
                    selected(deepest["parent_id"])
                    for _ in range(3):
                        page.locator("#reset").click()
                        selected("root")
                        require(geometry() == initial, "Repeated reset changed geometry")
                    search.fill("没有匹配_RELEASE_NEVER_EXISTS")
                    expect(page.locator("#search-results button")).to_have_count(0)
                    expect(page.locator("#search-status")).to_have_text("No matching frames.")
                    shot("empty")
                    search.fill("")
                    require(geometry() == initial, "Empty-search recovery changed geometry")
                    summary["checks"].append("parent-repeated-reset-unicode-no-results-recovery")
                    for label, count in Counter(n["label"] for n in nodes.values()).items():
                        if count > 1:
                            search.fill(label.swapcase())
                            texts = page.locator("#search-results button").all_text_contents()
                            require(
                                len(texts) >= count and len(set(texts)) == len(texts),
                                "Duplicate path ambiguity",
                            )
                    for node in nodes.values():
                        if "<" in node["label"]:
                            search.fill(node["node_id"])
                            require(
                                node["label"] in page.locator("#search-results").inner_text(),
                                "HTML-like text lost",
                            )
                    require(
                        page.locator(
                            "#chart script,#chart img,#search-results script,#search-results img"
                        ).count()
                        == 0,
                        "Unexpected injected elements",
                    )
                    summary["checks"].append("duplicate-paths-html-like-labels")
                    search.fill("")
                    child = next(
                        n
                        for n in nodes.values()
                        if n["parent_id"] == "root" and n["size_bytes"] > 0
                    )
                    group = page.locator('#chart .node[data-node-id="' + child["node_id"] + '"]')
                    group.hover()
                    expect(page.locator("#detail")).to_contain_text(child["node_id"])
                    expect(group.locator("title")).to_contain_text(
                        f"Inclusive: {child['size_bytes']:,} bytes"
                    )
                    group.click()
                    selected(child["node_id"])
                    page.goto("about:blank")
                    page.go_back(wait_until="load")
                    restored = page.locator("#chart .node").first.get_attribute("data-node-id")
                    require(
                        restored in {"root", child["node_id"]}, "Unexpected Back navigation focus"
                    )
                    expect(page.locator("#summary")).to_have_text(
                        f"Showing {nodes[restored]['size_bytes']:,} bytes"
                    )
                    expect(page.locator("#detail")).to_contain_text(restored)
                    page.locator("#reset").click()
                    selected("root")
                    expect(page.locator("#chart .node")).to_have_count(len(nodes))
                    require(geometry() == initial, "Back and Reset did not restore root geometry")
                    summary["checks"].append("hover-tooltip-svg-zoom-browser-back")
                    require(not errors, "Browser console/page errors")
                    summary["console_page_error_count"] = len(errors)
                finally:
                    context.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def run(args, summary):
    source, wheel, wheelhouse, output = (
        getattr(args, key).resolve() for key in ("source", "wheel", "wheelhouse", "output_dir")
    )
    fixture = verify_input(source, wheel)
    summary.update(
        candidate_sha=CANDIDATE,
        fixture_sha256=sha(fixture),
        wheel_sha256=sha(wheel),
        local_reference_wheel_sha256=LOCAL_REFERENCE_WHEEL_SHA,
        same_binary_as_local_reference=sha(wheel) == LOCAL_REFERENCE_WHEEL_SHA,
        wheel_source_byte_audit="PASS",
    )
    with ZipFile(wheel) as archive:
        metadata = archive.read(
            next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
        ).decode()
        summary["wheel_version"] = re.search(r"^Version: (.+)$", metadata, re.M).group(1)
    with tempfile.TemporaryDirectory(prefix="ptsnap-html-") as temp:
        private = Path(temp)
        home, cwd, environment = (private / n for n in ("home", "work", "venv"))
        home.mkdir()
        cwd.mkdir()
        venv.EnvBuilder(with_pip=True, system_site_packages=False).create(environment)
        python, cli = environment / "bin/python", environment / "bin/pt-snap"
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("PYTHON", "PT_SNAP_", "SETUPTOOLS_SCM"))
        }
        env.update(HOME=str(home), PYTHONNOUSERSITE="1", NO_COLOR="1", TERM="dumb")

        command_index = 0

        def command(argv):
            nonlocal command_index
            command_index += 1
            result = subprocess.run(
                [str(x) for x in argv], cwd=cwd, env=env, capture_output=True, timeout=120
            )
            private_log = args.private_dir / f"command-{command_index:02d}"
            private_log.with_suffix(".stdout").write_bytes(result.stdout)
            private_log.with_suffix(".stderr").write_bytes(result.stderr)
            private_log.with_suffix(".argv.json").write_text(json.dumps([str(x) for x in argv]))
            require(
                result.returncode == 0,
                "Isolated subprocess failed (raw output retained only privately)",
            )
            return result.stdout

        command([python, "-m", "pip", "install", "--no-index", "--find-links", wheelhouse, wheel])
        origin = json.loads(
            command(
                [
                    python,
                    "-c",
                    "import pt_snap_cli,json,sys;print(json.dumps({'origin':pt_snap_cli.__file__,'prefix':sys.prefix}))",
                ]
            )
        )
        require(Path(origin["origin"]).is_relative_to(environment), "Package escaped clean venv")
        require(Path(origin["prefix"]) == environment, "Wrong installed interpreter")
        summary["isolated_install"] = (
            "PASS: no system packages; isolated HOME/CWD; no source PYTHONPATH"
        )
        command([cli, "import", "--help"])
        command([cli, "report", "memory-tree", "--help"])
        imported = json.loads(
            command(
                [
                    cli,
                    "import",
                    fixture,
                    "--output-dir",
                    cwd / "imported",
                    "--format",
                    "single-db",
                    "--no-focus",
                    "--json",
                ]
            )
        )
        require(imported["ok"] is True, "CLI import did not succeed")
        db = Path(imported["db_path"])
        before = sha(db)
        with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as con:
            event = con.execute(
                "SELECT id FROM trace_entry_0 WHERE id>=0 ORDER BY active DESC,id LIMIT 1"
            ).fetchone()[0]
        raw = command([cli, "report", "memory-tree", db, "--event-id", event, "--format", "html"])
        html = cwd / "memory-tree.html"
        html.write_bytes(raw)
        payload = json.loads(
            re.search(
                rb'<script id="tree-data" type="application/json">(.*?)</script>', raw, re.S
            ).group(1)
        )
        nodes = {n["node_id"]: n for n in payload["nodes"]}
        require(len(nodes) == len(payload["nodes"]), "Duplicate node IDs")
        compare_tree(nodes, tree_oracle(db, event))
        summary.update(
            html_sha256=sha(html),
            database_sha256=before,
            event_id=event,
            node_count=len(nodes),
            root_bytes=nodes["root"]["size_bytes"],
            max_depth=max(n["depth"] for n in nodes.values()),
            unicode_label_count=sum(any(ord(c) > 127 for c in n["label"]) for n in nodes.values()),
            synthetic_edges="Separate source 12-case browser suite; not installed-wheel evidence",
        )
        summary["checks"].append("installed-cli-import-report-independent-sql-oracle")
        browser_checks(html, nodes, output, summary)
        require(sha(db) == before and sha(fixture) == FIXTURE_SHA, "Source/database changed")
        summary["checks"].append("source-database-immutable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "wheel", "wheelhouse", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--private-dir", type=Path)
    args = parser.parse_args()
    args.private_dir = (
        args.private_dir or args.output_dir.with_name(args.output_dir.name + "-private")
    ).resolve()
    if args.private_dir == args.output_dir.resolve() or args.private_dir.is_relative_to(
        args.output_dir.resolve()
    ):
        parser.error("Private diagnostics must be outside the public artifact directory")
    args.private_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = {"status": "FAIL", "checks": [], "screenshots": []}
    try:
        run(args, summary)
        summary["status"] = "PASS"
    except Exception as exc:
        # Avoid publishing traceback, absolute capture paths or fixture contents.
        summary["failure_type"] = type(exc).__name__
        (args.private_dir / "failure.txt").write_text(traceback.format_exc())
        if isinstance(exc, AcceptanceError):
            summary["failure_reason"] = str(exc)
        print("Installed HTML acceptance failed; see sanitized summary.", file=sys.stderr)
    finally:
        (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
