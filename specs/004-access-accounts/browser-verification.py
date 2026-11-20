"""Browser checks for issue #4 account access; requires Python Playwright/Chromium.

Signed-out checks use the production web export with no Google client ID:
    (apps/student) npm run export:web

Signed-in checks need real Google sign-in, which needs registered OAuth clients.
Until then they run against the development server pointed at a local fake
accounts API, with a stand-in for the Google Identity Services script that
returns a fake credential. Production code is unchanged. These checks prove
the screens and guards, not Google sign-in. Start the server first, with
placeholder public values (not real client IDs):
    (apps/student) CI=1 EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=qa-stub-web-client-id \
        EXPO_PUBLIC_API_URL=http://127.0.0.1:8899 npx expo start --web --port 8092
then set QA_STUB_ORIGIN=http://localhost:8092. Without it, the stubbed tests are skipped.
(A `expo export --dev` build fails at runtime with "Requiring unknown module",
so the stubbed checks use the development server.)
"""
import json
import os
import threading
import unittest
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

HERE = Path(__file__).resolve().parent
SHOTS = HERE / 'screenshots'
SHOTS.mkdir(exist_ok=True)
PRODUCTION_EXPORT = HERE.parent.parent / 'apps/student/dist/web'
STUB_ORIGIN = os.environ.get('QA_STUB_ORIGIN', '').rstrip('/')
FAKE_API_PORT = 8899
GSI_URL = 'https://accounts.google.com/gsi/client'

PROTECTED = [('/library', 'Library'), ('/library/preparation', 'Preparation'),
             ('/library/session', 'Session'), ('/library/report', 'Report'),
             ('/history', 'Score history'), ('/account', 'Account')]
DELETION_NOTICE = 'Deletion requested. Your account and scores will be removed within 30 days.'

# Stand-in for Google Identity Services: renders one button that hands back a fake credential.
GSI_STUB = """
window.google = { accounts: { id: {
  initialize(options) { window.__qaGsi = options; },
  renderButton(element) {
    const button = document.createElement('button');
    button.textContent = 'Continue with Google (QA stand-in)';
    button.style.cssText = 'font-size:16px;padding:10px 16px;border:1px solid #747775;border-radius:4px;background:#fff';
    button.onclick = () => window.__qaGsi.callback({ credential: 'qa-stub-credential' });
    element.append(button);
  },
  disableAutoSelect() { window.__qaGsiSignedOut = true; },
} } };
"""


class SPA(SimpleHTTPRequestHandler):
    def do_GET(self):
        if not Path(self.translate_path(self.path)).is_file():
            self.path = '/index.html'
        super().do_GET()

    def log_message(self, *_):
        pass


class FakeAccountsApi(BaseHTTPRequestHandler):
    """Answers the four account routes the student app calls. Records paths only, never tokens."""
    calls: list[tuple[str, str, bool]] = []
    origin = ''

    def cors(self):
        self.send_header('Access-Control-Allow-Origin', self.origin)
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST')

    def reply(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def handle_call(self, method):
        length = int(self.headers.get('Content-Length') or 0)
        if length:
            self.rfile.read(length)
        authorized = self.headers.get('Authorization') == 'Bearer qa-id-token'
        FakeAccountsApi.calls.append((method, self.path, authorized))
        tokens = {'id_token': 'qa-id-token', 'refresh_token': 'qa-refresh-token', 'expires_in': 3600}
        routes = {
            ('POST', '/v1/auth/google'): (200, tokens),
            ('POST', '/v1/auth/refresh'): (200, tokens),
            ('GET', '/v1/me'): (200, {'uid': 'qa-student'}) if authorized else (401, {}),
            ('POST', '/v1/account/deletion'): (200, {'accepted': True}) if authorized else (401, {}),
        }
        self.reply(*routes.get((method, self.path), (404, {})))

    def do_GET(self):
        self.handle_call('GET')

    def do_POST(self):
        self.handle_call('POST')

    def log_message(self, *_):
        pass


def serve(handler, port=0):
    server = ThreadingHTTPServer(('127.0.0.1', port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


class BrowserCase(unittest.TestCase):
    export: Path | None = None
    server = None

    @classmethod
    def setUpClass(cls):
        cls.origin = cls.start_app()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def start_app(cls):
        if cls.export is None or not (cls.export / 'index.html').is_file():
            raise unittest.SkipTest(f'Web export missing: {cls.export}')
        cls.server, cls.thread = serve(partial(SPA, directory=str(cls.export)))
        return f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        if cls.server:
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

    def heading(self, name):
        return self.page.get_by_role('heading', name=name, exact=True)

    def expect_sign_in(self):
        expect(self.page).to_have_url(self.origin + '/sign-in')
        expect(self.heading('Sign in')).to_be_visible()

    def external_requests(self, allowed=()):
        return [url for url in self.requests if urlsplit(url).scheme in {'http', 'https'}
                and not url.startswith(self.origin + '/') and not url.startswith(allowed)]


class SignedOutProductionExport(BrowserCase):
    export = PRODUCTION_EXPORT

    def tearDown(self):
        super().tearDown()
        self.assertEqual(self.external_requests(), [], 'Unexpected network requests while signed out')

    def test_welcome_is_public(self):
        self.page.goto(self.origin + '/', wait_until='networkidle')
        expect(self.page).to_have_url(self.origin + '/')
        expect(self.heading('Welcome')).to_be_visible()
        expect(self.page.get_by_role('link', name='Sign in to explore', exact=True)).to_be_visible()
        self.page.screenshot(path=str(SHOTS / 'web-welcome-signed-out.png'))

    def test_sign_in_without_client_id_offers_no_other_method(self):
        self.page.goto(self.origin + '/sign-in', wait_until='networkidle')
        self.expect_sign_in()
        expect(self.page.get_by_text('Google sign-in is not available yet. Please try again later.', exact=True)).to_be_visible()
        expect(self.page.get_by_role('textbox')).to_have_count(0)
        expect(self.page.get_by_role('button')).to_have_count(0)
        expect(self.page.get_by_text('password', exact=False)).to_have_count(0)
        self.assertNotIn(GSI_URL, self.requests, 'Google script loads with no client ID')
        self.page.screenshot(path=str(SHOTS / 'web-sign-in-no-client-id.png'))

    def test_signed_out_deep_links_redirect_to_sign_in(self):
        for path, title in PROTECTED:
            with self.subTest(path=path):
                self.page.goto(self.origin + path, wait_until='networkidle')
                self.expect_sign_in()
                expect(self.heading(title)).to_have_count(0)
                expect(self.page.get_by_text('Navigation preview', exact=True)).to_have_count(0)
                if path == '/library/session':
                    self.page.screenshot(path=str(SHOTS / 'web-deep-link-session-redirects-to-sign-in.png'))


class StubbedSignIn(BrowserCase):
    @classmethod
    def start_app(cls):
        if not STUB_ORIGIN:
            raise unittest.SkipTest('QA_STUB_ORIGIN not set; start the development server first')
        return STUB_ORIGIN

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        FakeAccountsApi.origin = cls.origin
        cls.api, cls.api_thread = serve(FakeAccountsApi, FAKE_API_PORT)

    @classmethod
    def tearDownClass(cls):
        cls.api.shutdown()
        cls.api.server_close()
        cls.api_thread.join()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        FakeAccountsApi.calls = []
        self.page.route(GSI_URL, lambda route: route.fulfill(
            status=200, content_type='text/javascript', body=GSI_STUB))

    def tearDown(self):
        super().tearDown()
        allowed = (GSI_URL, f'http://127.0.0.1:{FAKE_API_PORT}/')
        self.assertEqual(self.external_requests(allowed), [], 'Unexpected network requests')

    def sign_in(self):
        self.page.goto(self.origin + '/sign-in', wait_until='networkidle')
        self.expect_sign_in()
        self.page.get_by_role('button', name='Continue with Google (QA stand-in)').click()
        expect(self.page).to_have_url(self.origin + '/library')
        expect(self.heading('Library')).to_be_visible()

    def open_account(self):
        self.page.get_by_role('tab', name='Account', exact=True).click()
        expect(self.page).to_have_url(self.origin + '/account')
        expect(self.heading('Account')).to_be_visible()

    def test_signed_in_library_and_account(self):
        self.sign_in()
        self.assertIn(('GET', '/v1/me', True), FakeAccountsApi.calls)
        self.page.screenshot(path=str(SHOTS / 'web-library-signed-in-stub.png'))
        self.open_account()
        expect(self.page.get_by_role('button', name='Sign out', exact=True)).to_be_visible()
        expect(self.page.get_by_role('button', name='Delete account', exact=True)).to_be_visible()
        self.page.screenshot(path=str(SHOTS / 'web-account-signed-in-stub.png'))

    def test_sign_out_closes_protected_routes(self):
        self.sign_in()
        self.open_account()
        self.page.get_by_role('button', name='Sign out', exact=True).click()
        self.expect_sign_in()
        self.assertTrue(self.page.evaluate('window.__qaGsiSignedOut === true'), 'Google auto-select not disabled')
        self.page.go_back()
        expect(self.heading('Account')).to_have_count(0)
        expect(self.page.get_by_role('heading', name='Sign in', exact=True)).to_be_visible()

    def test_deletion_confirmation_then_signed_out_with_notice(self):
        self.sign_in()
        self.open_account()
        self.page.get_by_role('button', name='Delete account', exact=True).click()
        expect(self.heading('Delete your account?')).to_be_visible()
        expect(self.page.get_by_role('button', name='Confirm deletion', exact=True)).to_be_visible()
        expect(self.page.get_by_role('button', name='Cancel', exact=True)).to_be_visible()
        self.assertNotIn(('POST', '/v1/account/deletion', True), FakeAccountsApi.calls)
        # The modal fades in; wait until no ancestor is still transparent before capturing it.
        self.heading('Delete your account?').evaluate(
            "e => new Promise(done => { const check = () => { for (let n = e; n; n = n.parentElement)"
            " if (getComputedStyle(n).opacity !== '1') return requestAnimationFrame(check); done(); }; check(); })")
        self.page.screenshot(path=str(SHOTS / 'web-delete-confirmation-stub.png'))
        self.page.get_by_role('button', name='Confirm deletion', exact=True).click()
        self.expect_sign_in()
        expect(self.page.get_by_text(DELETION_NOTICE, exact=True)).to_be_visible()
        self.assertEqual(FakeAccountsApi.calls.count(('POST', '/v1/account/deletion', True)), 1)
        self.page.screenshot(path=str(SHOTS / 'web-sign-in-after-deletion-stub.png'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
