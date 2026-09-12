"""End-to-end round trip against a running server.

Usage: python scripts/e2e_smoke.py [base_url]

Pass A drives the JS path, Pass B disables JavaScript entirely to prove the
native form POST still lands on thanks.html via the server's 303.
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else "/tmp"
# Set when the sandbox ships a browser Playwright's default path won't find.
CHROMIUM = os.environ.get("CHROMIUM_PATH", "/opt/pw-browsers/chromium")
# The dashboard is behind auth; the feedback form deliberately is not.
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
ADMIN_CREDENTIALS = (
    {"username": ADMIN_USER, "password": ADMIN_PASSWORD} if ADMIN_PASSWORD else None
)


def submit_feedback(page, comment: str) -> None:
    page.goto(f"{BASE}/form.html")
    page.click("label[for='input-rating-1']")
    page.fill("#input-comment", comment)
    page.check("#input-late")
    page.check("#input-damaged")
    page.click("#btn-submit-feedback")


def pass_a_javascript_on(browser) -> None:
    page = browser.new_page(viewport={"width": 1280, "height": 900}, http_credentials=ADMIN_CREDENTIALS)
    submit_feedback(page, "e2e: box arrived crushed")
    page.wait_for_url("**/thanks.html")
    expect(page.locator("#heading-thanks")).to_be_visible()

    page.goto(f"{BASE}/dashboard.html")
    page.wait_for_selector("#tbody-exceptions tr:not(.table-empty-row)")

    assert page.text_content("#stat-exceptions-today .stat-card-value") != "0"
    newest = page.locator("#tbody-exceptions tr").first
    cells = [c.strip() for c in newest.locator("td").all_text_contents()]
    assert cells[1] == "Alex M.", cells
    assert cells[3] == "Job #4821 — Alex M.", cells
    assert cells[4] == "Damaged + Late", cells
    assert cells[6] == "$17.00", cells
    assert cells[7] == "Pending", cells
    print("pass A: submitted row renders as", cells[4], cells[6], cells[7])

    page.screenshot(path=f"{SHOTS}/e2e-dashboard-all.png", full_page=True)

    # Waits on the filter request rather than evaluating a predicate string:
    # the page's CSP forbids eval, which is the point of having it.
    with page.expect_response(lambda r: "status=approved" in r.url):
        page.click("#filter-tab-approved")
    page.wait_for_timeout(200)
    statuses = page.locator("#tbody-exceptions .status-cell").all_text_contents()
    assert set(statuses) <= {"Approved"}, statuses
    print("pass A: approved filter shows", len(statuses), "rows, all Approved")
    page.screenshot(path=f"{SHOTS}/e2e-dashboard-approved.png", full_page=True)
    page.close()


def pass_b_javascript_off(browser) -> None:
    context = browser.new_context(java_script_enabled=False, http_credentials=ADMIN_CREDENTIALS)
    page = context.new_page()
    before = page.request.get(f"{BASE}/api/stats").json()["exceptions_today"]

    submit_feedback(page, "e2e: no-js submission")
    page.wait_for_url("**/thanks.html")
    expect(page.locator("#heading-thanks")).to_be_visible()

    after = page.request.get(f"{BASE}/api/stats").json()["exceptions_today"]
    assert after == before + 1, f"no-JS submission did not persist ({before} -> {after})"
    print("pass B: no-JS POST persisted and redirected, exceptions_today", before, "->", after)
    context.close()


def pass_c_admin_surface_is_closed(browser) -> None:
    """The public form must work without credentials; the dashboard must not."""
    context = browser.new_context()  # deliberately no credentials
    page = context.new_page()

    assert page.request.get(f"{BASE}/form.html").status == 200
    for path in ("/dashboard.html", "/api/stats", "/api/exceptions"):
        status = page.request.get(f"{BASE}{path}").status
        assert status == 401, f"{path} returned {status}, expected 401"
    print("pass C: form public, dashboard and APIs return 401 without credentials")
    context.close()


def main() -> None:
    with sync_playwright() as p:
        launch_args = {"executable_path": CHROMIUM} if Path(CHROMIUM).exists() else {}
        browser = p.chromium.launch(**launch_args)
        pass_a_javascript_on(browser)
        pass_b_javascript_off(browser)
        if ADMIN_CREDENTIALS:
            pass_c_admin_surface_is_closed(browser)
        browser.close()
    print("e2e OK")


if __name__ == "__main__":
    main()
