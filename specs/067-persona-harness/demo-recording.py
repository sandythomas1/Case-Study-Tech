"""Records the #67 demo: a transcript of the persona prompts and the offline harness.

Each scene runs the real code first (argument lists, no shell), asserts the
outcome, and then replays the actual output in a captioned terminal page.

The harness scene drives the real ``python -m harness.run`` entry point
(``harness.run.main``) with the committed catalogue, prompts, scripts and pins,
and the real ``Sessions`` lifecycle. Only the persona is a fake: it answers
each session from the synthetic replies in ``tests/test_harness_checks.py``.
Nothing reaches Agent Platform, no credential is used and the scene prints the
content-free check report only. It also audits that no reply, script turn or
prompt line reached stdout, stderr or Python logging.

The live part of AC2 and AC3 is the owner's run (T7) and is not shown.

    uv run --no-project --python 3.12 --with playwright==1.58.0 \
        python specs/067-persona-harness/demo-recording.py OUT_DIR

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

# Runs in services/session. Prints "SCENE <n>" headers, then content-free lines.
FLOW = r"""
import contextlib, hashlib, io, logging, sys
from cst_session.scenarios import ScenarioUnavailable, load_catalogue
from cst_session.scenarios.prompts import load_prompts
from harness.run import main
from harness.script import SCRIPT_IDS
from tests.lifecycle_fakes import with_release
from tests.test_qa_persona_harness import ByScript, secrets_in

real = sys.stdout

def scene(n, lines):
    real.write(f"SCENE {n}\n" + "\n".join(lines) + "\n")

# AC1: one vetted, versioned prompt per #27 config.
catalogue, prompts = load_catalogue(), load_prompts()
lines = []
for s in catalogue.scenarios:
    text = prompts.for_scenario(s.id)
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    lines.append(f"config {s.id:<17} released={str(s.released).lower():<5} "
                 f"prompt v{prompts.version_for(s.id)}  {len(text)} chars  sha256={digest}...")
assert {s.id for s in catalogue.scenarios} == set(prompts.texts)
lines.append("manifest.toml digests match: the loader refuses any prompt edit without a new digest")
scene(1, lines)

# AC2/AC3 (unit level): the real entry point with a fake persona.
def harness(persona, *argv, **kw):
    out, err, logs = io.StringIO(), io.StringIO(), io.StringIO()
    handler = logging.StreamHandler(logs)
    logging.getLogger().addHandler(handler); logging.getLogger().setLevel(logging.DEBUG)
    try:
        code = main(list(argv), persona_factory=lambda pins: persona, out=out, err=err, **kw)
    finally:
        logging.getLogger().removeHandler(handler)
    return code, out.getvalue(), err.getvalue(), logs.getvalue()

code, out, err, logs = harness(ByScript(SCRIPT_IDS, 1), "--repeat", "1")
assert code == 0, out
leaks = secrets_in([out, err, logs])
assert leaks == []
scene(2, [*out.splitlines(), f"exit code {code}"])
scene(3, [f"stdout lines: {len(out.splitlines())}; lifecycle log lines (stderr): {len(err.splitlines())}",
          "searched for: every synthetic reply, every script turn, every prompt line",
          f"lines containing any of them: {len(leaks)}"])

# AC5: a released=false scenario can't start, in the service and in the harness.
held = with_release(load_catalogue(), "routine_intake", released=False)
try:
    held.startable("routine_intake")
    raise AssertionError("started")
except ScenarioUnavailable:
    service = "Catalogue.startable('routine_intake') -> ScenarioUnavailable"
code, out, err, logs = harness(ByScript([], 1), "--scenario", "routine_intake", "--repeat", "1",
                               catalogue=held)
assert code == 1 and "FAIL start_refused(scenario_unavailable)  0/1" in out.splitlines()
scene(4, ["catalogue: routine_intake released=false", service,
          "$ python -m harness.run --scenario routine_intake --repeat 1", *out.splitlines(),
          f"exit code {code}"])
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


UNIT_FILES = [
    "tests/test_prompts.py",
    "tests/test_harness_checks.py",
    "tests/test_harness_run.py",
    "tests/test_scenario_write_paths.py",
]


def summary_of(args: list[str]) -> list[str]:
    out = run(["uv", "run", "--frozen", "pytest", "-q", "-p", "no:cacheprovider", *args], SESSION)
    summary = [line for line in out.splitlines() if re.search(r"\d+ passed", line)]
    assert summary and "failed" not in summary[-1], out
    return [re.sub(r" in [\d.]+s", "", summary[-1].strip("= "))]


PYTEST_LINE = re.compile(r"(PASSED|FAILED|ERROR)|^=+ .*(passed|failed)")


def verbose(args: list[str], keep: int) -> list[str]:
    out = run(["uv", "run", "--frozen", "pytest", "-v", "-p", "no:cacheprovider", "--no-header", *args], SESSION)
    lines = [re.sub(r"\s+\[\s*\d+%\]$", "", line) for line in out.splitlines() if PYTEST_LINE.search(line)]
    assert lines and "passed" in lines[-1] and "failed" not in lines[-1], out
    lines = [line.replace("tests/", "") for line in lines]
    return [re.sub(r" in [\d.]+s", "", lines[-1].strip("= ")), *lines[:-1][:keep]]


def checks() -> list[tuple[str, list[str]]]:
    tests = summary_of([])
    lint = run(["uv", "run", "--frozen", "ruff", "check", "."], SESSION).strip().splitlines()[-1:]
    fmt = run(["uv", "run", "--frozen", "ruff", "format", "--check", "."], SESSION).strip().splitlines()[-1:]
    types = run(["uv", "run", "--frozen", "mypy", "."], SESSION).strip().splitlines()[-1:]
    return [
        ("$ uv run pytest   (live tests deselected by default)", tests),
        ("$ uv run ruff check .", lint),
        ("$ uv run ruff format --check .", fmt),
        ("$ uv run mypy .", types),
    ]


def build_scenes() -> list[tuple[str, list[tuple[str, list[str]]]]]:
    flow = scenes_from_flow()
    fake = "# real harness.run.main + Sessions, committed prompts/scripts/pins; fake persona, no network"
    ac4 = [
        "tests/test_scenario_write_paths.py",
        "tests/test_prompts.py::test_the_loaded_prompts_have_no_write_path",
        "tests/test_qa_persona_harness.py",
        "-k",
        "write or no_route or the_service_image",
    ]
    return [
        ("Unit suites · prompts, checks, runner and write paths all pass",
         [("$ uv run pytest " + " ".join(UNIT_FILES) + " -q", summary_of(UNIT_FILES))]),
        ("AC1 · The three vetted, versioned persona prompts load for the three #27 configs",
         [("# load_catalogue() + load_prompts() (content-free: version, length, digest)", flow[1])]),
        ("AC2 + AC3 (unit level) · every script passes in character, on scenario, crisis stays active",
         [(fake, flow[2])]),
        ("FR-5 · The run printed check results only: no reply, turn or prompt text anywhere",
         [("# audit of stdout, stderr and Python logging from the run above", flow[3])]),
        ("AC5 · A released=false scenario can't start, in the service or in the harness",
         [("# with_release(load_catalogue(), 'routine_intake', released=False)", flow[4])]),
        ("AC4 · No API path writes a prompt or scenario; the image ships no harness",
         [("$ uv run pytest " + " ".join(ac4[:3]) + ' -k "write or no_route or the_service_image"',
           verbose(ac4, keep=17))]),
        ("Checks pass · the live AC2/AC3 run (T7) is pending the owner",
         checks()),
    ]


def colour(line: str) -> str:
    if re.search(r"^FAIL|FAILED|exit code [1-9]|ScenarioUnavailable|released=false", line):
        return "#fca5a5"
    if re.search(r"^PASS|PASSED|passed|All checks|Success|already formatted|exit code 0|: 0$", line):
        return "#86efac"
    if line.startswith(("#", "INFO", "manifest", "searched", "stdout", "catalogue", "config")):
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
        '<h2 style="font:600 22px system-ui,sans-serif;margin:0 0 6px">Persona prompt harness (#67)'
        " · offline, synthetic persona, check results only</h2>"
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
            page.evaluate(REVEAL_JS, min(120, 1000 // count))
            page.wait_for_timeout(2600)
        context.close()
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: demo-recording.py OUT_DIR")
    main(Path(sys.argv[1]))
