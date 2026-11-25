"""Records the #31 demo: a transcript of the session service over real HTTP.

Each scene runs the real code first (argument lists, no shell), asserts the
outcome, and then replays the actual output in a captioned terminal page. The
HTTP scenes drive the real ``create_app`` and ``Sessions`` under a real uvicorn
server on 127.0.0.1 (access log off, as in the Dockerfile), with:

- the real ``AgentPlatformPersona`` over ``httpx.MockTransport``, playing a
  synthetic model, so nothing reaches Agent Platform;
- a fake token verifier and access store, with one synthetic UID;
- the real ``UnavailableGrader`` behind a call counter;
- a demo clock that can fast-forward, so the 10-minute limit is shown.

No real Google or Firebase credentials are used.

    uv run --no-project --python 3.12 --with playwright==1.58.0 \
        python specs/031-session-service/demo-recording.py OUT_DIR

The video goes to OUT_DIR. Encode it with the pr-demo skill's to_gif.py.
"""

import html
import os
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
SESSION = REPO / "services" / "session"
ENV = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}

# Runs in services/session. Prints "SCENE <n>" headers and one line per request.
FLOW = r"""
import asyncio, contextlib, io, json, logging, secrets, socket, sys, threading, time
import httpx, uvicorn
from cst_session.api import create_app
from cst_session.grading import UnavailableGrader
from cst_session.identity.domain import AccessState, Rejected, Student
from cst_session.lifecycle import Sessions
from cst_session.persona.agent_platform import AgentPlatformPersona
from cst_session.scenarios import load_catalogue
from cst_session.scenarios.prompts import load_prompts
from cst_session.state import StateCodec

UID, TOKEN = "synthUid001", "synthetic-id-token-1"
prompts = load_prompts()

class Auth:
    def verify(self, token):
        if token != TOKEN:
            raise Rejected()
        return Student(uid=UID)

class Store:
    state = AccessState.APPROVED
    reads = []
    def pending(self, uid):
        self.reads.append("pending"); return False
    def access_state(self, uid):
        self.reads.append("access_state"); return self.state

class Clock:
    offset = 0
    def now_ms(self):
        return time.time_ns() // 1_000_000 + self.offset

class Grader:
    calls = 0
    async def submit(self, session):
        Grader.calls += 1
        await UnavailableGrader().submit(session)

REPLIES = {
    "routine_intake": "Mostly classes, I guess. I haven't been sleeping well.",
    "resistant_client": "My advisor made me come. I don't really need this.",
    "crisis_risk": "It's been really hard lately. I'm tired all the time.",
}
mode = {"value": "ok"}
model_calls = []

async def model(request):
    body = json.loads(request.content)
    system = body["systemInstruction"]["parts"][0]["text"]
    scenario = next(s for s in REPLIES if prompts.for_scenario(s) == system)
    model_calls.append((str(request.url), sorted(body), scenario, len(body["contents"])))
    if mode["value"] == "hang":
        await asyncio.sleep(5)
    if mode["value"] == "upstream_503":
        return httpx.Response(503, text="synthetic upstream outage")
    if mode["value"] == "blocked":
        return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
    reply = {"content": {"role": "model", "parts": [{"text": REPLIES[scenario]}]},
             "finishReason": "STOP"}
    return httpx.Response(200, json={"candidates": [reply]})

clock, store = Clock(), Store()
persona = AgentPlatformPersona(project="cst-synthetic-01", location="us",
    model="gemini-3.8-flash", tokens=type("T", (), {"token": lambda self: "synthetic-access-token"})(),
    transport=httpx.MockTransport(model), deadline_s=1.5)
sessions = Sessions(catalogue=load_catalogue(), prompts=prompts,
    codec=StateCodec(secrets.token_bytes(32)), persona=persona, grader=Grader(), clock=clock)
app = create_app(Auth(), store, sessions)

logs = io.StringIO()
pyhandler = logging.StreamHandler(logs)
pyhandler.setFormatter(logging.Formatter("pylog %(name)s %(levelname)s %(message)s"))
logging.getLogger().addHandler(pyhandler)
logging.getLogger().setLevel(logging.DEBUG)
for name in ("httpx", "httpcore"):
    logging.getLogger(name).setLevel(logging.WARNING)  # as main.quiet_client_loggers()

sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
real = sys.stdout
service_out = io.StringIO()
sys.stdout = service_out  # content_free_log writes JSON lines to stdout
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
    access_log=False, log_config=None, log_level="debug"))
threading.Thread(target=server.run, daemon=True).start()
while not server.started:
    time.sleep(0.05)
http = httpx.Client(base_url=f"http://127.0.0.1:{port}", headers={"Authorization": f"Bearer {TOKEN}"}, timeout=10)
sent_texts, states = [], []

def short(value):
    return f"v1.<signed state, {len(value)} chars>" if isinstance(value, str) and value.startswith("v1.") else value

def call(path, body):
    response = http.post(path, json=body)
    data = response.json()
    if "state" in data:
        states.append(data["state"])
    shown_body = {k: short(v) for k, v in body.items()}
    shown = {k: short(v) for k, v in data.items()}
    lines.append(f"POST {path} {json.dumps(shown_body)}  ->  {response.status_code} {json.dumps(shown)}")
    return response

def turn(state, text):
    sent_texts.append(text)
    return call("/v1/sessions/turns", {"state": state, "text": text})

def start(scenario, opt_in=False):
    return call("/v1/sessions", {"scenario_id": scenario, "crisis_opt_in": opt_in,
                                 "save_transcript": False, "modality": "text"})

def note(text):
    lines.append(text)

def scene(n, fn):
    global lines
    lines = []
    fn()
    real.write(f"SCENE {n}\n" + "\n".join(lines) + "\n")

def scene1():
    # AC1: the client replies within the selected scenario.
    s = start("routine_intake").json()
    assert s["time_limit_ms"] == 600000
    r = turn(s["state"], "Hi, thanks for coming in. What brings you here today?")
    assert r.status_code == 200 and r.json()["reply"] == REPLIES["routine_intake"]
    url, keys, scenario, n = model_calls[-1]
    note(f"model call -> {url.split('/v1/')[0]}/.../gemini-3.8-flash:generateContent")
    note(f"  body keys = {keys}; systemInstruction = prompts/{scenario}.txt; contents = {n}")
    assert scenario == "routine_intake" and keys == ["contents", "generationConfig", "systemInstruction"]
    r = start("crisis_risk")
    assert (r.status_code, r.json()) == (403, {"detail": "opt_in_required"})
    c = start("crisis_risk", opt_in=True).json()
    r = turn(c["state"], "Hi, I'm glad you came in. How have things been?")
    assert r.json()["reply"] == REPLIES["crisis_risk"] and model_calls[-1][2] == "crisis_risk"
    note(f"model call -> systemInstruction = prompts/{model_calls[-1][2]}.txt")

def scene2():
    # AC2: the time limit and manual end.
    a = start("resistant_client").json()
    t = turn(a["state"], "What would you like to get out of today?")
    assert t.status_code == 200
    clock.offset += 600_000
    note("clock: fast-forward 10:00 (the scenario's time limit)")
    r = turn(t.json()["state"], "Is there anything else on your mind?")
    assert (r.status_code, r.json()) == (409, {"detail": "session_time_limit"})
    r = call("/v1/sessions/end", {"state": t.json()["state"]})
    assert r.json() == {"outcome": "unscored", "reason": "grading_unavailable", "ended_by": "time_limit"}
    clock.offset += 60_000
    note("clock: fast-forward 1:00 more (past the end grace)")
    r = call("/v1/sessions/end", {"state": t.json()["state"]})
    assert (r.status_code, r.json()) == (409, {"detail": "session_expired"})
    b = start("routine_intake").json()
    t = turn(b["state"], "What brings you in?")
    r = call("/v1/sessions/end", {"state": t.json()["state"]})
    assert r.json()["ended_by"] == "student" and "state" not in r.json()
    note("manual end returns no state: there is nothing new to continue from")
    note("owner-accepted L2-1 (AD-2): a kept pre-end copy still works until 10:00; #68 scores once per session")
    clock.offset += 600_000
    r = turn(t.json()["state"], "One more question?")
    assert r.json() == {"detail": "session_time_limit"}

def scene3():
    # AC4: a model failure gives an unscored ending, not a partial score.
    calls_before = Grader.calls
    c = start("routine_intake").json()
    for failure, label in (("hang", "the model hangs past the deadline"),
                           ("upstream_503", "the model returns 503"),
                           ("blocked", "the model blocks the reply")):
        mode["value"] = failure
        note(f"injected: {label}")
        r = turn(c["state"], "How has your week been?")
        assert (r.status_code, r.json()) == (503, {"detail": "persona_unavailable"})
    mode["value"] = "ok"
    assert Grader.calls == calls_before
    note(f"grader port calls during the failures = {Grader.calls - calls_before}; no state returned, no score")
    failed = [json.loads(l) for l in service_out.getvalue().splitlines() if '"persona_failed"' in l]
    for entry in failed[-3:]:
        note(f"log: event={entry['event']} error_code={entry['error_code']} status_code={entry.get('status_code', '-')}")

for n, fn in enumerate((scene1, scene2, scene3), start=1):
    scene(n, fn)

# AC3: audit every log line the service wrote in scenes 1-3.
server.should_exit = True
time.sleep(0.5)
sys.stdout = real
service = [l for l in service_out.getvalue().splitlines() if l.strip()]
python_logs = [l for l in logs.getvalue().splitlines() if l.strip()]
everything = service + python_logs
needles = sent_texts + list(REPLIES.values()) + [UID, TOKEN, "synthetic-access-token"] + [s[:40] for s in states]
needles += [prompts.for_scenario(s)[:60] for s in REPLIES]
leaks = sum(1 for l in everything for n in needles if n in l)
assert leaks == 0, leaks
fields = sorted({k for l in service for k in json.loads(l)})
real.write("SCENE 4\n")
real.write(f"service log lines (stdout JSON): {len(service)}; Python logging lines: {len(python_logs)}\n")
real.write(f"searched for: {len(sent_texts)} student turns, 3 replies, 3 prompts, the UID, both tokens, {len(states)} states\n")
real.write(f"lines containing any of them: {leaks}\n")
real.write(f"log fields used: {fields}\n")
real.write(f"access store operations: {sorted(set(store.reads))} (point reads only, {len(store.reads)} total)\n")
for l in service[:5]:
    real.write(l + "\n")
"""


def run(command: list[str], cwd: Path, stdout_only: bool = False) -> str:
    proc = subprocess.run(
        command, check=False, cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=ENV
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"{command} exited {proc.returncode}\n{out}"
    # stderr can carry warnings with local paths, which must not reach the recording.
    return proc.stdout if stdout_only else out


def scenes_from_flow() -> dict[int, list[str]]:
    out = run(["uv", "run", "--frozen", "python", "-c", FLOW], SESSION, stdout_only=True)
    scenes: dict[int, list[str]] = {}
    current = 0
    for line in out.splitlines():
        if line.startswith("SCENE "):
            current = int(line.split()[1])
            scenes[current] = []
        elif current:
            scenes[current].append(line)
    assert sorted(scenes) == [1, 2, 3, 4], out
    return scenes


PYTEST_LINE = re.compile(r"(PASSED|FAILED|ERROR)|^=+ .*(passed|failed)")


def pytest(args: list[str], keep: int = 6) -> list[str]:
    out = run(["uv", "run", "--frozen", "pytest", "-v", "-p", "no:cacheprovider", "--no-header", *args], SESSION)
    lines = [re.sub(r"\s+\[\s*\d+%\]$", "", line) for line in out.splitlines() if PYTEST_LINE.search(line)]
    assert lines and "passed" in lines[-1] and "failed" not in lines[-1], out
    lines = [line.replace("tests/", "") for line in lines]
    return [lines[-1].strip("= "), *lines[:-1][:keep]]


def suite() -> list[tuple[str, list[str]]]:
    tests = run(["uv", "run", "--frozen", "pytest", "-q", "-p", "no:cacheprovider"], SESSION)
    summary = [line for line in tests.splitlines() if re.search(r"\d+ passed", line)]
    assert summary and "failed" not in summary[-1], tests
    lint = run(["uv", "run", "--frozen", "ruff", "check", "."], SESSION).strip().splitlines()[-1:]
    fmt = run(["uv", "run", "--frozen", "ruff", "format", "--check", "."], SESSION).strip().splitlines()[-1:]
    types = run(["uv", "run", "--frozen", "mypy", "."], SESSION).strip().splitlines()[-1:]
    return [
        ("$ uv run pytest   (services/session)", summary),
        ("$ uv run ruff check .", lint),
        ("$ uv run ruff format --check .", fmt),
        ("$ uv run mypy .", types),
    ]


def build_scenes() -> list[tuple[str, list[tuple[str, list[str]]]]]:
    flow = scenes_from_flow()
    http = "# real app under uvicorn on 127.0.0.1, synthetic model (MockTransport), synthetic account"
    return [
        ("AC1 · Start, then the simulated client replies within the selected scenario",
         [(http, flow[1])]),
        ("AC2 · Turns at the 10-minute limit are 409; ends by time limit or by the student, never scored",
         [(http, flow[2])]),
        ("AC4 · A model timeout, outage or block is 503 with no state and no grader call: unscored",
         [(http, flow[3])]),
        ("AC3 · No conversation content in any log line from the scenes above; the store only reads",
         [("# every log line the service and Python logging wrote in scenes 1-3", flow[4]),
          ("$ uv run pytest tests/test_session_no_content.py",
           pytest(["tests/test_session_no_content.py"], keep=3))]),
        ("Carry-overs · approved guard on every route (inventory incl. websockets); no speech wiring",
         [("$ uv run pytest tests/test_session_access.py tests/test_qa_acceptance.py -k \"inventory or every_route or carryover_the_running or carryover_a_voice or carryover_no_route\"",
           pytest(["tests/test_session_access.py", "tests/test_qa_acceptance.py", "-k",
                   "inventory or every_route or carryover_the_running or carryover_a_voice or carryover_no_route"],
                  keep=7))]),
        ("Checks · the whole session suite, lint, format and types pass",
         suite()),
    ]


def colour(line: str) -> str:
    if re.search(r"->  (4\d\d|5\d\d)|FAILED", line):
        return "#fca5a5"
    if re.search(r"->  2\d\d|PASSED|passed|All checks|Success|already formatted|: 0$", line):
        return "#86efac"
    if line.startswith(("clock", "injected", "owner-accepted", "manual end", "model call", "  body", "grader", "log:")):
        return "#fde68a"
    return "#e5e7eb"


def scene_html(caption: str, blocks: list[tuple[str, list[str]]], small: bool) -> str:
    size = "12px/1.35" if small else "14px/1.5"
    body = "".join(
        f'<div class="l" style="color:#93c5fd;margin-top:10px">{html.escape(cmd)}</div>'
        + "".join(f'<div class="l" style="color:{colour(line)}">{html.escape(line)}</div>' for line in lines)
        for cmd, lines in blocks
    )
    return (
        f'<body style="margin:0;background:#0b1220;color:#e5e7eb;font:{size} Consolas,monospace;'
        'padding:20px 28px 80px">'
        '<h2 style="font:600 22px system-ui,sans-serif;margin:0 0 6px">Session service (#31)'
        " · real HTTP calls, synthetic account and model</h2>"
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
            page.evaluate(REVEAL_JS, min(150, 1300 // count))
            page.wait_for_timeout(3000)
        context.close()
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: demo-recording.py OUT_DIR")
    main(Path(sys.argv[1]))
