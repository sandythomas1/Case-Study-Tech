"""Local app tests using isolated Chromium; requires Python Playwright/Chromium.

Run npm run export:web in apps/student before running this script.
"""
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import expect, sync_playwright

HERE = Path(__file__).resolve().parent
SHOTS = HERE / 'screenshots'
SHOTS.mkdir(exist_ok=True)
ROOT = HERE.parent.parent / 'apps/student/dist/web'
class SPA(SimpleHTTPRequestHandler):
    def do_GET(self):
        if not Path(self.translate_path(self.path)).is_file():
            self.path = '/index.html'
        super().do_GET()
    def log_message(self, *_):
        pass

ROUTES = [('/', 'Welcome'), ('/library', 'Library'),
          ('/library/preparation', 'Preparation'), ('/library/session', 'Session'),
          ('/library/report', 'Report'), ('/history', 'Score history'), ('/account', 'Account')]


class BrowserVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / 'index.html').is_file():
            raise RuntimeError('Run npm run export:web in apps/student first')
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SPA, directory=str(ROOT)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f'http://127.0.0.1:{cls.server.server_port}'
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1280, 'height': 800})
        self.errors, self.requests = [], []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.on('request', lambda request: self.requests.append(request.url))

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors, [], 'Browser JavaScript errors')
        external = [url for url in self.requests if urlsplit(url).scheme in {'http', 'https'}
                    and not url.startswith(self.origin + '/')]
        self.assertEqual(external, [], 'Unexpected application network requests')

    def assert_screen(self, path, title):
        expect(self.page).to_have_url(self.origin + path)
        expect(self.page.get_by_role('heading', name=title, exact=True)).to_be_visible()
        heading = self.page.get_by_role('heading', name=title, exact=True)
        expect(heading.locator('..').get_by_text('Navigation preview', exact=True)).to_be_visible()

    def open_route(self, path, title):
        self.page.goto(self.origin + path, wait_until='networkidle')
        self.assert_screen(path, title)

    def test_all_seven_direct_routes(self):
        for path, title in ROUTES:
            with self.subTest(path=path):
                self.open_route(path, title)
                expect(self.page.get_by_text('Explore the planned screens. Practice, scores, and accounts are not available in this preview.', exact=True)).to_be_visible()
                expect(self.page.get_by_role('textbox')).to_have_count(0)
                self.page.screenshot(path=str(SHOTS / f"web-{title.lower().replace(' ', '-')}.png"))

    def test_preview_flow_and_three_tabs(self):
        self.open_route('/', 'Welcome')
        for label, path, title in [
            ('Explore the preview', '/library', 'Library'),
            ('Preview Preparation', '/library/preparation', 'Preparation'),
            ('Preview Session', '/library/session', 'Session'),
            ('Preview Report', '/library/report', 'Report'),
            ('Return to Library', '/library', 'Library'),
        ]:
            self.page.get_by_role('link', name=label, exact=True).click()
            self.assert_screen(path, title)
            expect(self.page.get_by_role('tab')).to_have_count(3)
            expect(self.page.get_by_role('tab', name='Library', exact=True)).to_have_attribute('aria-selected', 'true')
        for label, path in [('Score history', '/history'), ('Account', '/account'), ('Library', '/library')]:
            self.page.get_by_role('tab', name=label, exact=True).click()
            self.assert_screen(path, label)
            expect(self.page.get_by_role('tab', name=label, exact=True)).to_have_attribute('aria-selected', 'true')

    def test_direct_entry_backward_links(self):
        for path, title, label, destination, destination_title in [
            ('/library/preparation', 'Preparation', 'Back to Library', '/library', 'Library'),
            ('/library/session', 'Session', 'Back to Preparation', '/library/preparation', 'Preparation'),
            ('/library/report', 'Report', 'Back to Session', '/library/session', 'Session'),
        ]:
            self.open_route(path, title)
            self.page.get_by_role('link', name=label, exact=True).click()
            self.assert_screen(destination, destination_title)

    def test_browser_back_through_practice(self):
        self.open_route('/library', 'Library')
        for label, path, title in [
            ('Preview Preparation', '/library/preparation', 'Preparation'),
            ('Preview Session', '/library/session', 'Session'),
            ('Preview Report', '/library/report', 'Report'),
        ]:
            self.page.get_by_role('link', name=label, exact=True).click()
            self.assert_screen(path, title)
        for path, title in reversed(ROUTES[1:4]):
            self.page.go_back()
            self.assert_screen(path, title)

    def test_keyboard_focus_and_activation(self):
        self.open_route('/', 'Welcome')
        link = self.page.get_by_role('link', name='Explore the preview', exact=True)
        for _ in range(8):
            self.page.keyboard.press('Tab')
            if link.evaluate('element => element === document.activeElement'):
                break
        expect(link).to_be_focused()
        self.assertEqual(link.evaluate('element => getComputedStyle(element).outlineStyle'), 'solid')
        self.page.screenshot(path=str(SHOTS / 'web-keyboard-focus.png'))
        self.page.keyboard.press('Enter')
        self.assert_screen('/library', 'Library')

    def test_narrow_and_scaled_layout(self):
        for path, title in ROUTES:
            self.page.set_viewport_size({'width': 320, 'height': 800})
            self.open_route(path, title)
            self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth + 1'))
            self.page.screenshot(path=str(SHOTS / f"web-narrow-{title.lower().replace(' ', '-')}.png"))
        self.page.set_viewport_size({'width': 1280, 'height': 1000})
        self.open_route('/library/report', 'Report')
        # CSS scale exercises doubled layout; this is not browser-chrome zoom evidence.
        self.page.evaluate("document.documentElement.style.zoom = '2'")
        self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth + 1'))
        expect(self.page.get_by_role('link', name='Return to Library', exact=True)).to_be_visible()
        self.page.screenshot(path=str(SHOTS / 'web-report-css-zoom-200.png'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
