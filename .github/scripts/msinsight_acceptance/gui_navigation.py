"""Draft real UI navigation; numerical lifecycle assertions are a separate protocol gate.
Never uploads screenshots, logs, DOM or fixture bytes. No security flags or UI overrides.
"""

import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError("Use a fresh output path")
    assert args.fixture.is_absolute() and args.fixture.is_file()
    checks = []
    page_errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(locale="en-US", viewport={"width": 1600, "height": 1000})
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(type(error).__name__))
        page.goto("http://127.0.0.1:5174/", wait_until="domcontentloaded")
        page.locator(".btn-import").click()
        field = page.get_by_test_id("filePathInput")
        field.fill(str(args.fixture))
        field.press("Enter")
        confirm = page.get_by_role("button", name="Confirm", exact=True)
        expect(confirm).to_be_enabled(timeout=30000)
        confirm.click()
        frame = page.frame_locator('iframe[src*="plugins/Leaks"]')
        overview = frame.get_by_test_id("snapshotSliceOverview")
        expect(overview).to_be_visible(timeout=180000)
        windows = overview.locator('[role="button"]')
        expect(windows).to_have_count(5)
        for index in (0, 1, 0, 3):
            button = windows.nth(index)
            if index != 0 or len(checks):
                button.click()
            expect(button).to_have_attribute("aria-pressed", "true", timeout=30000)
            expect(button).to_have_attribute("data-ready", "true")
            checks.append({"window": index + 1, "selected": True, "ready": True})
        peak = windows.nth(3).get_by_test_id("globalPeakMarker")
        expect(peak.first).to_be_visible()
        expect(peak.first).to_have_attribute("aria-label", re.compile(r"\b7430\b"))
        checks.append({"window_4_global_peak_marker": True, "event_id": 7430})
        # Close the sole GUI WebSocket before the separate protocol client starts.
        context.close()
        browser.close()
    args.output.write_text(
        json.dumps(
            {
                "status": "failed" if page_errors else "passed",
                "GUI_windows": checks,
                "page_error_count": len(page_errors),
                "scope": "Actual GUI import and window navigation only; cross-shard IDs and byte counters require the separate protocol gate.",
            },
            indent=2,
        )
    )
    if page_errors:
        raise RuntimeError("GUI page errors observed; inspect private diagnostics")


if __name__ == "__main__":
    main()
