"""Records the #27 demo: a transcript of the AC1-AC4 tests running in the session service.

Each scene runs the real commands first (argument lists, no shell), asserts they
passed, and then replays their actual output in a captioned terminal page. Only
pytest's per-test lines and summaries, and the catalogue's own printout, are
shown, so no local paths appear. The scenario wording is the synthetic,
vetted config in services/session/cst_session/scenarios/configs/.

    uv run --no-project --python 3.12 --with playwright==1.58.0 \
        python specs/027-scenario-configs/demo-recording.py OUT_DIR

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
PYTEST = ("uv", "run", "--frozen", "pytest", "-p", "no:cacheprovider", "--no-header")
SHOWN = re.compile(
    r"(PASSED|FAILED|ERROR|SKIPPED)|^=+ .*(passed|failed)|^[0-9]+ passed|^  [a-z_]+: "
)
SCENARIOS = "tests/test_scenarios.py"

# Prints what the library and session start would see, from the real catalogue.
CATALOGUE_PRINTOUT = (
    "from cst_session.scenarios import load_catalogue\n"
    "for s in load_catalogue().scenarios:\n"
    "    print(f'  {s.id}: time_limit_minutes={s.time_limit_minutes} released={s.released}')\n"
)

# (caption, [(service, kind, args)]); kind is "v" (each test), "q" (summary) or "py".
SCENES = [
    (
        "AC1 · Exactly three configurations load and pass schema validation",
        [
            ("session", "v", (SCENARIOS, "-k",
                              "exactly_the_three or anchor_spec or preparation_fields "
                              "or only_the_crisis or fourth_scenario or missing_scenario")),
            ("session", "q", (SCENARIOS, "tests/test_scenario_config_edges.py", "-k",
                              "malformed or utf8 or crlf or byte_order or array_or_table "
                              "or table_header")),
        ],
    ),
    (
        "AC2 · The time limit is read from config and is 10 minutes for each scenario",
        [
            ("session", "py", (CATALOGUE_PRINTOUT,)),
            ("session", "v", (SCENARIOS, "-k", "time_limit_is")),
        ],
    ),
    (
        "AC3 · A release flag turned off hides the scenario from the library and blocks its start",
        [("session", "v", (SCENARIOS, "-k",
                           "release_flag_off or every_released or held_back_and_unknown"))],
    ),
    (
        "AC4 · No API path creates or edits a scenario (route scan of every service + read-only model)",
        [
            ("session", "v", ("tests/test_scenario_write_paths.py",)),
            ("session", "v", (SCENARIOS, "-k",
                              "cannot_be_changed or only_reads or no_write_function")),
        ],
    ),
    (
        "FR-8 · The logging helper keeps exactly the three scenario ids, in both services",
        [
            ("accounts", "v", ("tests/test_content_free_log.py", "-k",
                               "each_catalogue_scenario_id or exact_shape and scenario_id")),
            ("session", "v", (SCENARIOS, "-k", "logging_helper")),
        ],
    ),
]


def run(service: str, kind: str, args: tuple[str, ...]) -> tuple[str, list[str]]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    if kind == "py":
        env["PYTHONPATH"] = "."
        command: tuple[str, ...] = ("uv", "run", "--frozen", "python", "-c", *args)
        shown = 'uv run python -c "<print each scenario from load_catalogue()>"'
    else:
        command = (*PYTEST, "-v" if kind == "v" else "-q", *args)
        shown = "uv run " + " ".join(a if " " not in a else f'"{a}"' for a in command[3:])
    proc = subprocess.run(command, cwd=SERVICES[service], capture_output=True, text=True, env=env)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"{service}: {' '.join(command)} failed\n{out}"
    lines = [line for line in out.splitlines() if SHOWN.search(line)]
    assert lines, f"{service}: no result lines\n{out}"
    if kind == "py":
        expected = "time_limit_minutes=10 released=True"
        assert len(lines) == 3 and all(expected in line for line in lines), out
    return f"(services/{service}) $ {shown}", lines


def scene_html(caption: str, blocks: list[tuple[str, list[str]]]) -> str:
    def colour(line: str) -> str:
        if "FAILED" in line or "ERROR" in line or " failed" in line:
            return "#fca5a5"
        return "#86efac"

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
        '<h2 style="font:600 22px system-ui,sans-serif;margin:0 0 6px">Three vetted scenario configs (#27)'
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
    await new Promise(r => setTimeout(r, 60));
  }
}"""


def main(out_dir: Path) -> None:
    scenes = [(caption, [run(*step) for step in steps]) for caption, steps in SCENES]
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
            page.wait_for_timeout(3000)
        context.close()
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: demo-recording.py OUT_DIR")
    main(Path(sys.argv[1]))
