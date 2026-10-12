"""Draft real UI navigation; numerical lifecycle assertions are a separate protocol gate.
Never uploads screenshots, logs, DOM or fixture bytes. No security flags or UI overrides.
"""

import argparse
import json
import re
from pathlib import Path

GUI_PHASES = (
    "browser_launch",
    "page_open",
    "import_open",
    "fixture_input",
    "import_search",
    "confirm_ready",
    "import_confirm",
    "overview_visible",
    "window_count",
    "window_click",
    "window_selected",
    "window_ready",
    "peak_visible",
    "peak_event",
    "browser_close",
    "page_errors",
    "complete",
)
GUI_ERRORS = ("none", "timeout", "assertion", "runtime", "other")


def error_kind(exc):
    # Never serialize exception messages, custom class names, paths or DOM text.
    if isinstance(exc, AssertionError):
        return "assertion"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if type(exc).__module__ == "playwright._impl._errors" and type(exc).__name__ == "TimeoutError":
        return "timeout"
    if isinstance(exc, RuntimeError):
        return "runtime"
    return "other"


def record_navigation(output, action):
    state = {"phase": "browser_launch", "error_kind": "none", "transition": 0}
    checks, page_errors = [], []
    try:
        action(state, checks, page_errors)
        state["phase"] = "complete"
    except Exception as exc:
        state["error_kind"] = error_kind(exc)
        raise
    finally:
        state["completed_windows"] = [c["window"] for c in checks if "window" in c]
        state["page_error_count"] = len(page_errors)
        output.write_text(json.dumps(state, indent=2))


def navigate(fixture, state, checks, page_errors):
    from playwright.sync_api import expect, sync_playwright

    state["phase"] = "browser_launch"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(locale="en-US", viewport={"width": 1600, "height": 1000})
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(type(error).__name__))
        state["phase"] = "page_open"
        page.goto("http://127.0.0.1:5174/", wait_until="domcontentloaded")
        state["phase"] = "import_open"
        page.locator(".btn-import").click()
        field = page.get_by_test_id("filePathInput")
        state["phase"] = "fixture_input"
        field.fill(str(fixture))
        state["phase"] = "import_search"
        field.press("Enter")
        confirm = page.get_by_role("button", name="Confirm", exact=True)
        state["phase"] = "confirm_ready"
        expect(confirm).to_be_enabled(timeout=30000)
        state["phase"] = "import_confirm"
        confirm.click()
        frame = page.frame_locator('iframe[src*="plugins/Leaks"]')
        overview = frame.get_by_test_id("snapshotSliceOverview")
        state["phase"] = "overview_visible"
        expect(overview).to_be_visible(timeout=180000)
        windows = overview.locator('[role="button"]')
        state["phase"] = "window_count"
        expect(windows).to_have_count(5)
        for index in (0, 1, 0, 3):
            state["transition"] = len(checks)
            state["phase"] = "window_click"
            button = windows.nth(index)
            if index != 0 or len(checks):
                button.click()
            state["phase"] = "window_selected"
            expect(button).to_have_attribute("aria-pressed", "true", timeout=30000)
            state["phase"] = "window_ready"
            expect(button).to_have_attribute("data-ready", "true")
            checks.append({"window": index + 1, "selected": True, "ready": True})
        peak = windows.nth(3).get_by_test_id("globalPeakMarker")
        state["phase"] = "peak_visible"
        expect(peak.first).to_be_visible()
        state["phase"] = "peak_event"
        expect(peak.first).to_have_attribute("aria-label", re.compile(r"\b7430\b"))
        checks.append({"window_4_global_peak_marker": True, "event_id": 7430})
        # Close the sole GUI WebSocket before the separate protocol client starts.
        state["phase"] = "browser_close"
        context.close()
        browser.close()
    state["phase"] = "page_errors"
    if page_errors:
        raise RuntimeError("GUI page errors observed; inspect private diagnostics")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError("Use a fresh output path")
    assert args.fixture.is_absolute() and args.fixture.is_file()
    record_navigation(
        args.output,
        lambda state, checks, errors: navigate(args.fixture, state, checks, errors),
    )


if __name__ == "__main__":
    main()
