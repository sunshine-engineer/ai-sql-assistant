"""Capture the actual localhost UI. Requires Playwright and Chromium, no provider key.

File: scripts/capture_demo.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    """Capture the actual reviewer UI screenshots and video using Playwright.

    Raises:
        playwright.sync_api.Error: If Chromium is unavailable or the expected UI workflow cannot complete.
        OSError: If the media output directory or capture files cannot be written.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8507")
    parser.add_argument("--output", type=Path, default=Path("assets/current"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            record_video_dir=str(args.output / "video"),
            record_video_size={"width": 1440, "height": 1000},
        )
        page = context.new_page()
        page.goto(args.url)
        page.get_by_role("combobox", name="Workspace", exact=True).wait_for()
        page.get_by_role("combobox", name="Workspace", exact=True).click()
        page.get_by_role("option", name="Plan demo", exact=True).click()
        page.get_by_role("button", name="Run reviewed plan", exact=True).click()
        page.get_by_text("Verified query values:", exact=False).wait_for()
        page.get_by_text("Verified query values:", exact=False).scroll_into_view_if_needed()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(args.output / "plan.png"), full_page=True)
        page.get_by_role("button", name="Compare with previous month", exact=True).click()
        page.get_by_text("Compared the previous and selected months", exact=False).wait_for()
        page.get_by_text("Query inspection", exact=True).scroll_into_view_if_needed()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(args.output / "comparison.png"), full_page=True)
        page.get_by_role("combobox", name="Workspace", exact=True).click()
        page.get_by_role("option", name="Evaluation", exact=True).click()
        page.get_by_role("button", name="Run evaluation", exact=True).click()
        page.get_by_text("Mode: reference_fixture.", exact=False).wait_for()
        page.get_by_text("Mode: reference_fixture.", exact=False).scroll_into_view_if_needed()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(args.output / "evaluation.png"), full_page=True)
        page.get_by_role("combobox", name="Workspace", exact=True).click()
        page.get_by_role("option", name="Benchmarks", exact=True).click()
        page.get_by_role("combobox", name="Recorded run", exact=True).click()
        page.get_by_role("option", name="2026-10-20-paced-pilot.json", exact=True).click()
        page.get_by_text("Failure categories", exact=False).wait_for()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(args.output / "benchmark.png"), full_page=True)
        assert not page.get_by_test_id("stException").count()
        video = page.video
        context.close()
        video.save_as(str(args.output / "reviewer-demo.webm"))
        video.delete()
        browser.close()
        print("Captured real plan, comparison and evaluation UI; no browser exceptions.")


if __name__ == "__main__":
    main()
