"""Records the #72 demo: a transcript of the owner approval gate over real HTTP.

Each scene runs the real code first (argument lists, no shell), asserts the outcome,
and then replays the actual output in a captioned terminal page. The HTTP scenes
drive the real FastAPI router, the real Firestore adapter against the local
emulator (127.0.0.1:8085, project demo-casestudy-tech) and the real
FirebaseIdentity, with only the Google signature check stubbed to return
synthetic claims. Every account is a fresh synthetic UID with a
"Synthetic Student" name and an @test.invalid email. No real credentials.

    FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 \
    uv run --no-project --python 3.12 --with playwright==1.58.0 \
        python specs/072-access-approval-gate/demo-recording.py OUT_DIR

The video goes to OUT_DIR. Encode it with the pr-demo skill's to_gif.py.
"""

import html
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
ACCOUNTS = REPO / "services" / "accounts"
INFRA = REPO / "infra"
EMULATOR = "127.0.0.1:8085"
ENV = {
    **{k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"},
    "FIRESTORE_EMULATOR_HOST": EMULATOR,
    "GOOGLE_CLOUD_PROJECT": "demo-casestudy-tech",
}

# Runs in services/accounts. Prints "SCENE <n>" headers and one line per request:
# "<METHOD> <path> [body]  ->  <status> <json>", plus owner and store facts.
FLOW = r"""
import contextlib, io, json, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore

from cst_accounts.api import create_app
from cst_accounts.deletion import process_deletions
from cst_accounts.domain import Unavailable
from cst_accounts.firebase import FirebaseIdentity
from cst_accounts.store import FirestoreAccounts

db = firestore.Client(project="demo-casestudy-tech", credentials=AnonymousCredentials())
store = FirestoreAccounts(db)
me, peer = f"demo-{uuid4().hex[:8]}", f"peer-{uuid4().hex[:8]}"
NAME = "Synthetic Student"
def claims(token):
    uid = {"token-me": me, "token-peer": peer}[token]
    return {"uid": uid, "firebase": {"sign_in_provider": "google.com"},
            "name": NAME, "email": f"{uid}@test.invalid", "email_verified": True}
for uid in (me, peer):
    db.collection("students").document(uid).collection("scores").document("one").set(
        {"scenario_id": "routine_intake", "overall": 4, "categories": [4] * 6})
db.collection("access").document(peer).set({"state": "approved", "version": 2})
access = db.collection("access").document(me)

provider = FirebaseIdentity(Mock(), "test-project-key", "https://example.invalid")
provider.disable = Mock()
provider.delete = Mock()
ME = {"Authorization": "Bearer token-me"}
logs = io.StringIO()

def show(method, path, response, body=None):
    shown = path.replace(me, "<me>")
    sent = f" {json.dumps(body)}" if body is not None else ""
    text = response.text.replace(me, "<me>").replace(peer, "<peer>")
    print(f"{method} {shown}{sent}  ->  {response.status_code} {text}")
    return response

def call(client, method, path, body=None, headers=ME):
    return show(method, path, client.request(method, path, headers=headers, json=body), body)

def records():
    return sum(1 for d in db.collection("access").stream() if d.id == me)

import logging
handler = logging.StreamHandler(logs)
handler.setFormatter(logging.Formatter("pylog %(name)s %(levelname)s %(message)s"))
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.DEBUG)
client = TestClient(create_app(provider, store), raise_server_exceptions=False)
client.__enter__()
real = sys.stdout

def run_scene(n, fn):
    emit_lines = io.StringIO()
    with contextlib.redirect_stdout(emit_lines), patch(
        "cst_accounts.firebase.auth.verify_id_token", side_effect=lambda t, **_: claims(t)
    ):
        fn()
    real.write(f"SCENE {n}\n")
    for line in emit_lines.getvalue().splitlines():
        if line.startswith("{"):
            logs.write(line + "\n")  # content-free log lines, shown in scene 5
        else:
            real.write(line + "\n")

def scene1():
    # AC2 / FR-5: a missing account is refused on every protected route.
    assert call(client, "GET", "/v1/access").json() == {"state": "missing"}
    for path in ("/v1/scores", "/v1/me"):
        r = call(client, "GET", path)
        assert (r.status_code, r.json()) == (403, {"detail": "access_not_approved"})

def scene2():
    # AC1: one pending record, idempotent and race-safe; AC3: forged body has no effect.
    assert call(client, "POST", "/v1/access/request").json() == {"state": "pending"}
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(lambda _: client.post("/v1/access/request", headers=ME), range(8)))
    # Shown as they came back: transaction contention can give a 503 (see verification.md).
    tally = {}
    for r in replies:
        key = f"{r.status_code} {r.json().get('state', r.json().get('detail'))}"
        tally[key] = tally.get(key, 0) + 1
    assert set(tally) <= {"200 pending", "503 Service temporarily unavailable."}, tally
    print("8 x POST /v1/access/request in parallel  ->  " + ", ".join(f"{k} x{v}" for k, v in sorted(tally.items())))
    forged = {"uid": "<peer>", "state": "approved", "email": "forged@test.invalid"}
    r = client.post("/v1/access/request", headers=ME, json={**forged, "uid": peer})
    show("POST", "/v1/access/request", r, forged)
    assert r.status_code == 400
    record = access.get().to_dict()
    assert records() == 1 and record["state"] == "pending" and record["version"] == 1
    print(f"store: access/<me> records = {records()}, state = {record['state']}, "
          f"version = {record['version']}, fields = {sorted(record)}")
    r = call(client, "GET", "/v1/scores")
    assert r.status_code == 403

def scene3():
    # AC2 + AC4: approve admits on the next request; a revoke refuses the next one.
    access.update({"state": "approved", "decided_at": datetime.now(UTC), "version": 2})
    print("owner (Admin SDK): access/<me>.state = approved")
    r = call(client, "GET", "/v1/scores")
    assert r.status_code == 200 and len(r.json()["scores"]) == 1
    assert call(client, "GET", "/v1/me").status_code == 200
    access.update({"state": "denied", "decided_at": datetime.now(UTC), "version": 3})
    print("owner (Admin SDK): access/<me>.state = denied   (revoke)")
    r = call(client, "GET", "/v1/scores")
    assert (r.status_code, r.json()) == (403, {"detail": "access_not_approved"})
    r = call(client, "POST", "/v1/access/request")
    assert (r.status_code, r.json()) == (403, {"detail": "access_denied"})
    assert access.get().to_dict()["version"] == 3 and records() == 1
    print("store: access/<me> unchanged (state = denied, version = 3, records = 1)")

def scene4():
    # AC2: a failed store read is a 503, never an approval.
    real_state = store.access_state
    def outage(uid):
        raise Unavailable()
    store.access_state = outage
    print("injected: the access-record read fails (store outage)")
    r = client.get("/v1/scores", headers={"Authorization": "Bearer token-peer"})
    show("GET", "/v1/scores  (approved <peer>)", r)
    assert r.status_code == 503
    store.access_state = real_state
    # AC7 error path: a crash whose message carries the verified name and email.
    real_request = store.request_access
    def crash(profile, now):
        raise RuntimeError(f"echo {profile.display_name} {profile.email}")
    store.request_access = crash
    print("injected: request_access crashes with the name and email in its message")
    r = call(client, "POST", "/v1/access/request", None, {"Authorization": "Bearer token-peer"})
    assert r.status_code == 500 and "@" not in r.text and NAME not in r.text
    store.request_access = real_request
    # AC6: the deletion sweep erases the access record with the scores.
    r = call(client, "POST", "/v1/account/deletion", {"confirmation": "DELETE"}, {"Authorization": "Bearer token-peer"})
    assert r.status_code == 202
    swept = process_deletions(provider, store, datetime.now(UTC))
    assert swept["completed"] >= 1 and swept["failed"] == 0
    print(f"process_deletions(now)  ->  completed = {swept['completed']}, failed = {swept['failed']}")
    gone = not db.collection("access").document(peer).get().exists
    scores = store.scores(peer)
    assert gone and scores == []
    print(f"store: access/<peer> exists = {not gone}, students/<peer>/scores = {len(scores)}")

for n, fn in enumerate((scene1, scene2, scene3, scene4), start=1):
    run_scene(n, fn)
lines = [l for l in logs.getvalue().splitlines() if l.strip()]
leaks = sum(v in l for l in lines for v in (NAME, "Synthetic", "test.invalid", "@"))
assert leaks == 0
service = [l for l in lines if l.startswith("{")]
assert any(json.loads(l).get("error_class") == "RuntimeError" for l in service)
real.write("SCENE 5\n")
real.write(f"service log lines (stdout JSON): {len(service)}; Python logging lines: {len(lines) - len(service)}\n")
real.write(f"lines containing the name, an email or '@': {leaks}\n")
for l in service[:6]:
    real.write(l.replace(me, "<me>").replace(peer, "<peer>") + "\n")
client.__exit__(None, None, None)
"""


def run(command: list[str], cwd: Path, expect: int = 0, stdout_only: bool = False) -> str:
    proc = subprocess.run(
        command, check=False, cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=ENV
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == expect, f"{command} exited {proc.returncode}, expected {expect}\n{out}"
    # stderr can carry warnings with local paths, which must not reach the recording.
    return proc.stdout if stdout_only else out


def scenes_from_flow() -> dict[int, list[str]]:
    out = run(["uv", "run", "--frozen", "python", "-c", FLOW], ACCOUNTS, stdout_only=True)
    scenes: dict[int, list[str]] = {}
    current = 0
    for line in out.splitlines():
        if line.startswith("SCENE "):
            current = int(line.split()[1])
            scenes[current] = []
        elif current:
            scenes[current].append(line)
    assert sorted(scenes) == [1, 2, 3, 4, 5], out
    return scenes


PYTEST_LINE = re.compile(r"(PASSED|FAILED|ERROR)|^=+ .*(passed|failed)")


def pytest(args: list[str], keep: int = 8) -> list[str]:
    out = run(["uv", "run", "--frozen", "pytest", "-v", "-p", "no:cacheprovider", "--no-header", *args], ACCOUNTS)
    lines = [re.sub(r"\s+\[\s*\d+%\]$", "", line) for line in out.splitlines() if PYTEST_LINE.search(line)]
    assert lines and "passed" in lines[-1] and "failed" not in lines[-1], out
    lines = [line.replace("tests/", "") for line in lines]
    return [lines[-1].strip("= "), *lines[:-1][:keep]]


def rules() -> list[str]:
    npm = shutil.which("npm") or "npm"
    out = run([npm, "test"], INFRA)
    shown = [line.strip() for line in out.splitlines() if re.match(r"\s*[✔✖] |\s*ℹ (tests|pass|fail) ", line)]
    assert any(line.startswith("ℹ fail 0") for line in shown), out
    return shown


def suite() -> list[tuple[str, list[str]]]:
    tests = run(["uv", "run", "--frozen", "pytest", "-q", "-p", "no:cacheprovider"], ACCOUNTS)
    summary = [line for line in tests.splitlines() if re.search(r"\d+ passed", line)]
    assert summary and "failed" not in summary[-1], tests
    lint = run(["uv", "run", "--frozen", "ruff", "check", "."], ACCOUNTS).strip().splitlines()[-1:]
    fmt = run(["uv", "run", "--frozen", "ruff", "format", "--check", "."], ACCOUNTS).strip().splitlines()[-1:]
    types = run(["uv", "run", "--frozen", "mypy", "."], ACCOUNTS).strip().splitlines()[-1:]
    return [
        ("$ uv run pytest   (services/accounts, emulator on 8085)", summary),
        ("$ uv run ruff check .", lint),
        ("$ uv run ruff format --check .", fmt),
        ("$ uv run mypy .", types),
    ]


def build_scenes() -> list[tuple[str, list[tuple[str, list[str]]]]]:
    flow = scenes_from_flow()
    http = "# real router + real Firestore adapter (emulator), synthetic token claims"
    return [
        ("AC2 · A missing account gets 403 access_not_approved on /v1/scores and /v1/me",
         [(http, flow[1])]),
        ("AC1 + AC3 · Exactly one pending record, even after 8 parallel requests; a forged body is a 400",
         [(http, flow[2])]),
        ("AC2 + AC4 · Approval admits on the next request; a revoke refuses the next one; denied can't re-request",
         [(http, flow[3])]),
        ("AC2 + AC6 · A store failure is a 503, not an approval; deletion erases the access record with the scores",
         [(http, flow[4])]),
        ("AC7 · Logs from every scene above carry no name and no email",
         [("# every content-free log line the service wrote in scenes 1-4", flow[5]),
          ("$ uv run pytest tests/test_access.py -k \"logs or repr\"",
           pytest(["tests/test_access.py", "-k", "logs or repr"], keep=2))]),
        ("AC5 · Firestore rules: only an approved owner reads their scores; nobody reads or writes access/",
         [("$ npm test   (infra, Firestore emulator)", rules())]),
        ("Checks · the whole accounts suite, lint, format and types pass",
         suite()),
    ]


def colour(line: str) -> str:
    if re.search(r"->  (4\d\d|5\d\d)|FAILED|✖", line):
        return "#fca5a5"
    if re.search(r"->  2\d\d|PASSED|passed|✔|ℹ pass|All checks|Success|already formatted|: 0$", line):
        return "#86efac"
    if line.startswith(("owner", "injected", "store:", "process_deletions")):
        return "#fde68a"
    return "#e5e7eb"


def scene_html(caption: str, blocks: list[tuple[str, list[str]]], small: bool) -> str:
    size = "12px/1.35" if small else "15px/1.55"
    body = "".join(
        f'<div class="l" style="color:#93c5fd;margin-top:10px">{html.escape(cmd)}</div>'
        + "".join(f'<div class="l" style="color:{colour(line)}">{html.escape(line)}</div>' for line in lines)
        for cmd, lines in blocks
    )
    return (
        f'<body style="margin:0;background:#0b1220;color:#e5e7eb;font:{size} Consolas,monospace;'
        'padding:20px 28px 80px">'
        '<h2 style="font:600 22px system-ui,sans-serif;margin:0 0 6px">Owner approval gate (#72)'
        " · real HTTP calls, synthetic accounts</h2>"
        f"{body}"
        '<div style="position:fixed;left:0;right:0;bottom:0;padding:14px 24px;'
        'background:rgba(17,24,39,.95);color:#fff;font:600 20px system-ui,sans-serif">'
        f"{html.escape(caption)}</div>"
        "<style>.l{visibility:hidden;white-space:pre-wrap;word-break:break-all}</style></body>"
    )


REVEAL_JS = """async (ms) => {
  for (const el of document.querySelectorAll('.l')) {
    el.style.visibility = 'visible';
    await new Promise(r => setTimeout(r, ms));
  }
}"""


def main(out_dir: Path) -> None:
    scenes = build_scenes()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=str(out_dir),
            record_video_size={"width": 1280, "height": 800},
        )
        page = context.new_page()
        for caption, blocks in scenes:
            count = sum(len(lines) + 1 for _, lines in blocks)
            page.set_content(scene_html(caption, blocks, small=count > 18))
            page.evaluate(REVEAL_JS, min(180, 1500 // count))
            page.wait_for_timeout(2600)
        context.close()
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: demo-recording.py OUT_DIR")
    main(Path(sys.argv[1]))
