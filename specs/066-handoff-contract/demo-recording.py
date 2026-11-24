"""Records the #66 demo: a transcript of the handoff validator, its logs and its tests.

Each scene runs the real code first (argument lists, no shell) in the session service's
own environment, asserts the outcome, and then replays the actual output in a captioned
terminal page. Only result lines are shown, so no local paths appear. Every payload is a
committed synthetic fixture (handoff/fixtures/v1).

    uv run --no-project --python 3.12 --with playwright==1.58.0 \
        python specs/066-handoff-contract/demo-recording.py OUT_DIR

The video goes to OUT_DIR. Encode it with the pr-demo skill's to_gif.py.
"""

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
SESSION = REPO / "services" / "session"
ENV = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}

# Runs in services/session. Prints one result line per fixture, then the log lines
# the validator wrote while checking it, then a leak count over every log line.
VALIDATE = r"""
import contextlib, io, json
from cst_session.handoff import HandoffRejected, parse_handoff
from tests.handoff_fixtures import ACCEPTED, REJECTED, expected_reason, load

logs, leaks = [], 0
for path in ACCEPTED + REJECTED:
    payload = load(path)
    secrets = [t["text"] for t in payload["turns"]] + [payload["owner_uid"]]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            session = parse_handoff(path.read_bytes())
            result = "ACCEPTED"
        except HandoffRejected as rejected:
            result = "rejected: " + rejected.reason.value
            assert rejected.reason == expected_reason(path), path.name
    assert (path in ACCEPTED) == (result == "ACCEPTED"), path.name
    leaks += sum(secret in out.getvalue() for secret in secrets)
    logs += out.getvalue().splitlines()
    if path in ACCEPTED:
        uncertain = sum(getattr(t, "uncertain_recognition", False) for t in session.turns)
        detail = (f"{session.scenario.id} {session.modality} turns={len(session.turns)} "
                  f"uncertain={uncertain} warnings={session.conduct.warnings}")
    else:
        detail = f"status={payload['status']} version={payload['contract_version']}"
    print(f"RESULT {path.parent.name}/{path.name}	{result}	{detail}")
for line in logs:
    print("LOG " + line)
assert leaks == 0
print(f"LEAKS turn text or owner_uid found in {len(logs)} log lines: {leaks}")
"""


def run(command: list[str], cwd: Path, expect: int = 0) -> str:
    proc = subprocess.run(command, check=False, cwd=cwd, capture_output=True, text=True, env=ENV)
    out = proc.stdout + proc.stderr
    assert proc.returncode == expect, f"{command} exited {proc.returncode}, expected {expect}\n{out}"
    return out


VALIDATION = run(["uv", "run", "--frozen", "python", "-c", VALIDATE], SESSION)
PYTEST_LINE = re.compile(r"(PASSED|FAILED|ERROR)|^=+ .*(passed|failed)|^E +AssertionError: .*is stale")


def tagged(tag: str) -> list[str]:
    return [line[len(tag) + 1 :] for line in VALIDATION.splitlines() if line.startswith(tag + " ")]


def columns(rows: list[str]) -> list[str]:
    """Align the tab-separated RESULT fields so each row fits on one line."""
    cells = [row.split("	") for row in rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(cells[0]) - 1)]
    return ["  ".join([*(c.ljust(w) for c, w in zip(row, widths, strict=False)), row[-1]]) for row in cells]


def pytest(args: list[str], cwd: Path = SESSION, expect: int = 0, keep: int = 8) -> list[str]:
    out = run(["uv", "run", "--frozen", "--project", str(SESSION), "pytest", "-v", "-p",
               "no:cacheprovider", "--no-header", *args], cwd, expect)
    lines = [re.sub(r"\s+\[\s*\d+%\]$|^E +", "", line) for line in out.splitlines() if PYTEST_LINE.search(line)]
    assert lines and ("passed" in lines[-1] or "failed" in lines[-1]), out
    # The summary goes first so the caption bar never covers it.
    return [lines[-1], *lines[:-1][:keep]]


def scene_accepted() -> list[tuple[str, list[str]]]:
    results = columns([line for line in tagged("RESULT") if line.startswith("accepted/")])
    assert len(results) == 3 and all("ACCEPTED" in line for line in results)
    return [
        ("$ uv run python -c <parse_handoff(each fixture)>", results),
        ("$ uv run pytest tests/test_handoff_contract.py -k accepted", pytest(
            ["tests/test_handoff_contract.py", "-k", "accepted or same_session or reliability_flags or save_choice or dont_save"])),
    ]


def scene_rejected() -> list[tuple[str, list[str]]]:
    results = columns([line for line in tagged("RESULT") if line.startswith("rejected/")])
    assert len(results) == 9 and not any("ACCEPTED" in line for line in results)
    return [
        ("$ uv run python -c <parse_handoff(each fixture)>", results),
        ("$ uv run pytest tests/test_handoff_contract.py -k rejected_fixtures", pytest(
            ["tests/test_handoff_contract.py", "-k", "rejected_fixtures"], keep=0)),
    ]


def scene_logs() -> list[tuple[str, list[str]]]:
    logs = tagged("LOG")
    assert len(logs) == 12
    (leaks,) = tagged("LEAKS")
    return [
        ("# every line the validator logged while checking the 12 fixtures", [leaks, *logs]),
        ("$ uv run pytest tests/test_handoff_logging.py", pytest(["tests/test_handoff_logging.py"], keep=0)),
    ]


def scene_schema() -> list[tuple[str, list[str]]]:
    in_sync = pytest(["tests/test_handoff_schema.py"], keep=6)
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp)
        shutil.copytree(REPO / "handoff", copy / "handoff")
        shutil.copytree(SESSION, copy / "services" / "session",
                        ignore=shutil.ignore_patterns(".venv", "__pycache__", ".*_cache"))
        contract = copy / "services" / "session" / "cst_session" / "handoff" / "contract.py"
        source = contract.read_text(encoding="utf-8")
        assert "MAX_TURN_CHARACTERS = 2000" in source
        contract.write_text(source.replace("MAX_TURN_CHARACTERS = 2000", "MAX_TURN_CHARACTERS = 2500"),
                            encoding="utf-8")
        stale = pytest(["tests/test_handoff_schema.py", "-k", "matches_the_models"],
                       cwd=copy / "services" / "session", expect=1, keep=2)
    assert "1 failed" in stale[0]
    return [
        ("$ uv run pytest tests/test_handoff_schema.py", in_sync),
        ("# in a throwaway copy: MAX_TURN_CHARACTERS 2000 -> 2500, schema not re-exported",
         ["$ uv run pytest tests/test_handoff_schema.py -k matches_the_models   # exit 1", *stale]),
    ]


def scene_suite() -> list[tuple[str, list[str]]]:
    tests = run(["uv", "run", "--frozen", "pytest", "-q", "-p", "no:cacheprovider"], SESSION)
    summary = [line for line in tests.splitlines() if re.search(r"\d+ passed", line)]
    lint = run(["uv", "run", "--frozen", "ruff", "check", "."], SESSION).strip().splitlines()[-1:]
    fmt = run(["uv", "run", "--frozen", "ruff", "format", "--check", "."], SESSION).strip().splitlines()[-1:]
    types = run(["uv", "run", "--frozen", "mypy", "."], SESSION).strip().splitlines()[-1:]
    fixtures = run([sys.executable, "scripts/ci/check_synthetic_fixtures.py"], REPO).strip().splitlines()[-1:]
    return [
        ("$ uv run pytest", summary),
        ("$ uv run ruff check .", lint),
        ("$ uv run ruff format --check .", fmt),
        ("$ uv run mypy .", types),
        ("$ python scripts/ci/check_synthetic_fixtures.py", fixtures),
    ]


SCENES = [
    ("AC1 · The three completed synthetic sessions (one per scenario) are accepted", scene_accepted),
    ("AC1 · Incomplete, content-lost, conduct-ended and wrong-version sessions are rejected", scene_rejected),
    ("AC2 · Validating logs only the event and session ID: no turn text, no owner UID", scene_logs),
    ("AC3 · The regenerated JSON Schema matches the committed copy; a model change fails it", scene_schema),
    ("Checks · the whole session suite, lint, format, types and the fixture check pass", scene_suite),
]


def colour(line: str) -> str:
    if "rejected:" in line or "FAILED" in line or "failed" in line or "is stale" in line:
        return "#fca5a5"
    if "ACCEPTED" in line or "PASSED" in line or "passed" in line or line.startswith(
        ("All checks", "Success", "Synthetic-fixture check passed", "turn text or owner_uid")
    ) or "already formatted" in line:
        return "#86efac"
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
        '<h2 style="font:600 22px system-ui,sans-serif;margin:0 0 6px">Completed-session handoff v1 (#66)'
        " · real validator runs, synthetic fixtures</h2>"
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
    scenes = [(caption, build()) for caption, build in SCENES]
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
            page.evaluate(REVEAL_JS, min(200, 1800 // count))
            page.wait_for_timeout(3600)
        context.close()
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: demo-recording.py OUT_DIR")
    main(Path(sys.argv[1]))
