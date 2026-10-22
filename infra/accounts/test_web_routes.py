"""Rendered unauthenticated route checks against an exported student web app.

Run with an isolated Playwright installation; no Google account, token fixture or
production authentication bypass is used. Google OAuth itself is a separate gate.
"""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]


class StudentHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        # SPA host behavior for direct protected deep links.
        if not Path(self.translate_path(self.path)).is_file():
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, *args) -> None:
        pass


@pytest.fixture(scope="module")
def web_app():
    distribution = ROOT / "apps" / "student" / "dist"
    if not (distribution / "index.html").is_file():
        pytest.fail("Export the student web application before running this check.")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(StudentHandler, directory=str(distribution))
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                yield browser, f"http://127.0.0.1:{server.server_port}"
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize(
    "route",
    ["/", "/sign-in", "/history", "/account", "/preparation", "/session", "/report"],
)
def test_anonymous_deep_links_show_only_welcome(web_app, route):
    browser, base = web_app
    context = browser.new_context()
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base + route)
        expect(
            page.get_by_role("heading", name="A space to practice counseling")
        ).to_be_visible()
        expect(page.get_by_text("Delete account", exact=True)).to_have_count(0)
        expect(page.locator('input[type="password"]')).to_have_count(0)
        assert not errors, "The exported app raised a browser error."
        if route == "/":
            evidence = ROOT / "tmp" / "verification" / "welcome-web.png"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(evidence), full_page=True)
    finally:
        context.close()
