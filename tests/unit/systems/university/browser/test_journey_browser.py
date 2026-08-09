"""Real-browser quality gates for the supported student web journey."""

from pathlib import Path

from axe_playwright_python.sync_playwright import Axe

STATIC = (
    Path(__file__).resolve().parents[5]
    / "education_system/platform/delivery/api/university/static"
)


def test_journey_has_no_automatic_wcag_aa_violations(page) -> None:
    page.goto((STATIC / "journey.html").as_uri())
    results = Axe().run(page, options={"runOnly": {"type": "tag", "values": ["wcag2aa", "wcag22aa"]}})
    assert results.response["violations"] == []


def test_keyboard_user_can_reach_and_submit_application(page) -> None:
    page.goto((STATIC / "journey.html").as_uri())
    page.locator("#application").scroll_into_view_if_needed()
    form = page.locator("#application-form")
    assert form.is_visible()
    first = form.locator("input, select, textarea, button").first
    first.focus()
    assert page.evaluate(
        "(element) => document.activeElement === element", first.element_handle()
    )
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement !== document.body")
