"""Records the PR #62 demo: one take of the #25, #46, #18 and #26 criteria, asserting each one.

The UI part runs against the stubbed development server and fake accounts API from
browser-verification.py (fake data and fake credentials, no real Google account). The last scene makes
real unauthenticated calls to the deployed development services and shows their actual status codes.
It sends no tokens.

    (apps/student) CI=1 EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=qa-stub-web-client-id \
        EXPO_PUBLIC_API_URL=http://127.0.0.1:8899 npx expo start --web --port 8092
    QA_STUB_ORIGIN=http://localhost:8092 python specs/004-access-accounts/demo-recording.py OUT_DIR

The video goes to OUT_DIR. Encode it with the pr-demo skill's to_gif.py.
"""
import html
import importlib.util
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('harness', HERE / 'browser-verification.py')
harness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harness)

GATEWAY = 'https://accounts-7tnmor5w.uc.gateway.dev'
SESSION = 'https://session-447ob3nwoa-uc.a.run.app'
GRADING = 'https://grading-447ob3nwoa-uc.a.run.app'
# (label, method, url, body, expected status) — no call carries a credential.
LIVE_CHECKS = [
    ('Session service, no identity', 'GET', f'{SESSION}/health', None, 403),
    ('Grading service, no identity', 'GET', f'{GRADING}/health', None, 403),
    ('Gateway reaches session', 'GET', f'{GATEWAY}/v1/sessions/health', None, 200),
    ('Session route, no sign-in', 'POST', f'{GATEWAY}/v1/sessions/end', b'{}', 401),
    ('Gateway has no grading route', 'GET', f'{GATEWAY}/v1/grading/health', None, 404),
    ('Scores, no sign-in (#26)', 'GET', f'{GATEWAY}/v1/scores', None, 401),
]

CAPTION_JS = """text => {
  let el = document.getElementById('pr-demo-caption');
  if (!el) {
    el = document.createElement('div');
    el.id = 'pr-demo-caption';
    el.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:2147483647;padding:14px 24px;' +
      'background:rgba(17,24,39,.92);color:#fff;font:600 20px system-ui,sans-serif;pointer-events:none';
    document.body.append(el);
  }
  el.textContent = text;
}"""


def caption(page, text):
    page.evaluate(CAPTION_JS, text)


def beat(page, ms=1300):
    page.wait_for_timeout(ms)


def status_of(method, url, body):
    request = urllib.request.Request(url, data=body, method=method,
                                     headers={'Content-Type': 'application/json'} if body else {})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def transcript_html(rows):
    lines = ''.join(
        f'<div><span style="color:#93c5fd">$ {html.escape(m)} {html.escape(u)}</span><br>'
        f'&nbsp;&nbsp;{html.escape(label)}: <b style="color:{"#86efac" if got == want else "#fca5a5"}">'
        f'{got}</b> (expected {want})</div>'
        for label, m, u, got, want in rows)
    return ('<body style="margin:0;background:#0b1220;color:#e5e7eb;font:17px/1.7 Consolas,monospace;'
            f'padding:32px 40px"><h2 style="font-family:system-ui">Live dev services, unauthenticated calls</h2>'
            f'{lines}</body>')


def main(out_dir: Path):
    origin = harness.STUB_ORIGIN
    if not origin:
        sys.exit('Set QA_STUB_ORIGIN to the stubbed development server.')
    harness.FakeAccountsApi.origin = origin
    api, api_thread = harness.serve(harness.FakeAccountsApi, harness.FAKE_API_PORT)
    rows = [(label, m, u, status_of(m, u, body), want) for label, m, u, body, want in LIVE_CHECKS]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        warm = browser.new_page()
        warm.goto(origin + '/sign-in', wait_until='networkidle')
        warm.close()
        context = browser.new_context(viewport={'width': 1280, 'height': 800}, record_video_dir=str(out_dir),
                                      record_video_size={'width': 1280, 'height': 800})
        context.route(harness.GSI_URL, lambda route: route.fulfill(
            status=200, content_type='text/javascript', body=harness.GSI_STUB))
        page = context.new_page()
        google = page.get_by_role('button', name='Continue with Google (QA stand-in)')
        heading = lambda name: page.get_by_role('heading', name=name, exact=True)

        page.goto(origin + '/sign-in', wait_until='networkidle')
        caption(page, '#25 AC1 · Google is the only way to sign in; it opens the Library')
        expect(page.get_by_role('textbox')).to_have_count(0)
        beat(page)
        google.click()
        expect(heading('Library')).to_be_visible()
        beat(page)

        caption(page, '#25 AC2 · Sign out: Back and deep links land on Sign in')
        page.get_by_role('tab', name='Account', exact=True).click()
        expect(heading('Account')).to_be_visible()
        beat(page, 900)
        page.get_by_role('button', name='Sign out', exact=True).click()
        expect(heading('Sign in')).to_be_visible()
        page.go_back()
        expect(heading('Account')).to_have_count(0)
        page.goto(origin + '/library/session', wait_until='networkidle')
        expect(page).to_have_url(origin + '/sign-in')
        caption(page, '#25 AC3 · A deep link to a practice session redirects to Sign in')
        beat(page)

        google.click()
        expect(heading('Library')).to_be_visible()
        page.get_by_role('tab', name='Account', exact=True).click()
        caption(page, '#46 AC1 · Deleting the account needs explicit confirmation')
        page.get_by_role('button', name='Delete account', exact=True).click()
        expect(heading('Delete your account?')).to_be_visible()
        beat(page, 1800)
        page.get_by_role('button', name='Delete my account', exact=True).click()
        expect(page.get_by_text(harness.DELETION_NOTICE, exact=True)).to_be_visible()
        assert harness.FakeAccountsApi.calls.count(('POST', '/v1/account/deletion', True)) == 1
        caption(page, '#46 AC3 · The student is signed out at once, with the deletion notice')
        beat(page, 1800)

        harness.FakeAccountsApi.exchange_pending_deletion = True
        google.click()
        expect(page.get_by_role('alert').filter(has_text=harness.BEING_DELETED)).to_be_visible()
        caption(page, '#46 · An account being deleted cannot sign back in')
        beat(page, 1800)

        page.set_content(transcript_html(rows))
        caption(page, '#18 · #26 · Private services; protected routes refuse unauthenticated calls')
        beat(page, 4500)
        failed = [row for row in rows if row[3] != row[4]]
        assert not failed, f'Live checks failed: {failed}'

        video = page.video.path()
        context.close()
        browser.close()
    api.shutdown()
    api.server_close()
    api_thread.join()
    print(json.dumps({'video': str(video), 'live_checks': [(r[0], r[3]) for r in rows]}))


if __name__ == '__main__':
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'demo')
