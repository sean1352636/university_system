"""Browser-test fixtures that remain optional in lightweight test installs."""

import pytest


@pytest.fixture
def page():
    """Provide a clean Chromium page or skip when browser binaries are absent."""
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        pytest.skip("browser tests require Playwright")

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Error as exc:
            if "Executable doesn't exist" in str(exc):
                pytest.skip("Chromium is not installed; run: playwright install chromium")
            raise
        context = browser.new_context()
        browser_page = context.new_page()
        try:
            yield browser_page
        finally:
            context.close()
            browser.close()
