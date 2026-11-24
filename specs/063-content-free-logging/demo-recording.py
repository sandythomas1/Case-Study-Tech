"""Records the #63 demo: a transcript of the AC1-AC4 tests running in both services.

Each scene runs the real commands first (argument lists, no shell), asserts they
passed, and then replays their actual output in a captioned terminal page. Only
pytest's per-test lines and summaries are shown, so no local paths appear. The
tests use synthetic data only.

    uv run --no-project --python 3.12 --with playwright==1.58.0 \
        python specs/063-content-free-logging/demo-recording.py OUT_DIR

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
SERVICES = {"accounts": REPO / "services" / "accounts", "session": REPO / "services" / "session"}
PYTEST = ("uv", "run", "--frozen", "pytest", "-v", "-p", "no:cacheprovider", "--no-header")
SHOWN = re.compile(r"(PASSED|FAILED|ERROR|SKIPPED)|^=+ .*(passed|failed)|All checks passed|Success:")

# (caption, [(service, extra args)])
SCENES = [
    (
        "AC1 · A field outside the allow-list (transcript, text, ...) never emits its value",
        [
            ("accounts", ("tests/test_content_free_log.py", "-k",
                          "outside_the_allow_list or reserved_keys or wrong_typed_or_malformed_value_is_dropped and session_id")),
            ("session", ("tests/test_content_free_log_copies.py",)),
        ],
    ),
    (
        "AC2 · An exception carrying a synthetic turn logs its class only: no turn, no traceback",
        [
            ("accounts", ("tests/test_accounts.py", "-k",
                          "unhandled or failing_request or after_the_response or crashing")),
            ("accounts", ("tests/test_content_free_log.py", "-k", "an_error")),
        ],
    ),
    (
        "AC3 · Body logging is off at API Gateway and Cloud Run (--no-access-log)",
        [("accounts", ("tests/test_body_logging_off.py",))],
    ),
    (
        "AC4 · Service code is checked for print, root-logger and std-stream logging (ruff + AST), both services",
        [
            ("accounts", ("tests/test_logging_calls.py", "-k", "helper or bypass")),
            ("session", ("tests/test_logging_calls.py", "-k", "only_through_the_helper")),
            ("accounts", ("RUFF",)),
            ("session", ("RUFF",)),
        ],
    ),
]


def run(service: str, args: tuple[str, ...]) -> tuple[str, list[str]]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    if args == ("RUFF",):
        command = ("uv", "run", "--frozen", "ruff", "check", "--select", "T20,LOG015", ".")
    else:
        command = (*PYTEST, *args)
    proc = subprocess.run(command, cwd=SERVICES[service], capture_output=True, text=True, env=env)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"{service}: {' '.join(command)} failed\n{out}"
    lines = [line for line in out.splitlines() if SHOWN.search(line)]
    assert lines, f"{service}: no result lines\n{out}"
    shown = " ".join(a if " " not in a else f'"{a}"' for a in command[2:])
    return f"(services/{service}) $ uv run {shown}", lines


def scene_html(caption: str, blocks: list[tuple[str, list[str]]]) -> str:
    def colour(line: str) -> str:
        if "PASSED" in line or "passed" in line or "All checks" in line or "Success" in line:
            return "#86efac"
        return "#fca5a5"

    body = "".join(
        f'<div class="l" style="color:#93c5fd;margin-top:10px">{html.escape(cmd)}</div>'
        + "".join(
            f'<div class="l" style="color:{colour(line)}">{html.escape(line)}</div>' for line in lines
        )
        for cmd, lines in blocks
    )
    return (
        '<body style="margin:0;background:#0b1220;color:#e5e7eb;font:14px/1.5 Consolas,monospace;'
        'padding:20px 28px 80px">'
        '<h2 style="font:600 22px system-ui,sans-serif;margin:0 0 6px">Content-free logging (#63)'
        " · real test runs, synthetic data</h2>"
        f"{body}"
        '<div style="position:fixed;left:0;right:0;bottom:0;padding:14px 24px;'
        'background:rgba(17,24,39,.95);color:#fff;font:600 20px system-ui,sans-serif">'
        f"{html.escape(caption)}</div>"
        "<style>.l{visibility:hidden;white-space:pre-wrap}</style></body>"
    )


REVEAL_JS = """async () => {
  for (const el of document.querySelectorAll('.l')) {
    el.style.visibility = 'visible';
    await new Promise(r => setTimeout(r, 70));
  }
}"""


def main(out_dir: Path) -> None:
    scenes = [(caption, [run(s, a) for s, a in runs]) for caption, runs in SCENES]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=str(out_dir),
            record_video_size={"width": 1280, "height": 800},
        )
        page = context.new_page()
        for caption, blocks in scenes:
            page.set_content(scene_html(caption, blocks))
            page.evaluate(REVEAL_JS)
            page.wait_for_timeout(3200)
        context.close()
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: demo-recording.py OUT_DIR")
    main(Path(sys.argv[1]))
