"""Records the #59 demo: a transcript of the report-contract checker and its tests.

Each scene runs the real command first (argument lists, no shell), asserts its exit
code, and then replays its actual output in a captioned terminal page. Only result
lines are shown, so no local paths appear. Every document is a synthetic fixture.

    uv run --no-project --python 3.12 --with playwright==1.58.0 \
        python specs/059-report-contract/demo-recording.py OUT_DIR

The video goes to OUT_DIR. Encode it with the pr-demo skill's to_gif.py.
"""

import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / "scripts" / "ci" / "check_report_contract.py"
sys.path.insert(0, str(CHECKER.parent))
import check_report_contract as contract

PY = sys.executable


def run(command: list[str], expect: int) -> str:
    proc = subprocess.run(command, check=False, cwd=REPO, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    assert proc.returncode == expect, f"{command} exited {proc.returncode}, expected {expect}\n{out}"
    return out


def scene_checker() -> list[tuple[str, list[str]]]:
    out = run([PY, str(CHECKER)], expect=0)
    fixtures = sorted(p.name for p in (REPO / "report" / "fixtures" / "v1").glob("*.json"))
    cases = len(list((REPO / "report" / "validation-cases" / "v1" / "invalid").glob("*.json")))
    lines = [f"fixtures/v1: {', '.join(fixtures)}", f"validation-cases/v1/invalid: {cases} cases", *out.splitlines()]
    return [("$ python scripts/ci/check_report_contract.py   # exit 0", lines)]


INVALID = REPO / "report" / "validation-cases" / "v1" / "invalid"
CASE_COUNT = len(list(INVALID.glob("*.json")))


def scene_invalid(name: str, reason: str) -> list[tuple[str, list[str]]]:
    case = json.loads((INVALID / f"{name}.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "report"
        shutil.copytree(REPO / "report", copy)
        base = json.loads((copy / "fixtures" / "v1" / case["base"]).read_text(encoding="utf-8"))
        bad = contract.apply_patch(base, case["patch"])
        (copy / "fixtures" / "v1" / f"zz-{name}.json").write_text(json.dumps(bad), encoding="utf-8")
        out = run([PY, str(CHECKER), "--report-dir", str(copy)], expect=1)
    lines = [line for line in out.splitlines() if line.startswith(("zz-", "report contract check"))]
    assert any(reason in line for line in lines), out
    shown = [f"case: {case['case']}  (base {case['base']}, patch {json.dumps(case['patch'])})", *lines]
    return [("$ python scripts/ci/check_report_contract.py --report-dir <copy + the patched report>   # exit 1", shown)]


def scene_tests() -> list[tuple[str, list[str]]]:
    out = run(
        [PY, "-m", "unittest", "discover", "-s", "scripts/ci/tests", "-p", "test_check_report_contract.py", "-v"], expect=0
    )
    lines = []
    for line in out.splitlines():
        if match := re.match(r"(test_\w+) \(.*\) \.\.\. (ok|FAIL|ERROR)$", line):
            lines.append(f"{match.group(1)} ... {match.group(2)}")
        elif line.startswith("Ran ") or line in {"OK", "FAILED"}:
            lines.append(line)
    assert lines[-1] == "OK", out
    # The summary goes first so the caption bar never covers it.
    summary = f"{lines[-2]}: {lines[-1]}"
    return [("$ python -m unittest discover -s scripts/ci/tests -p test_check_report_contract.py -v",
             [summary, *lines[:-2]])]


SCENES = [
    (f"AC1-AC3 · A synthetic fixture for every state passes; {CASE_COUNT} invalid cases are each rejected", scene_checker),
    ("SCO-4 · A report citing a turn beyond turn_count is rejected as a fabricated turn",
     lambda: scene_invalid("fabricated-turn", "a fabricated turn")),
    ("SCO-5 · A crisis report that leaves out its safety result is rejected (owner, 2026-11-23)",
     lambda: scene_invalid("crisis-narrative-only-without-safety", "always carries its safety result")),
    ("Tests · every report-contract test passes (states, scoring, crisis safety, history, comparison)", scene_tests),
]


def colour(line: str) -> str:
    if line.startswith("zz-") or "problem" in line or "FAIL" in line:
        return "#fca5a5"
    if line.endswith((" ok", ": OK")) or "fixtures valid" in line:
        return "#86efac"
    return "#e5e7eb"


def scene_html(caption: str, blocks: list[tuple[str, list[str]]], small: bool) -> str:
    size = "12px/1.35" if small else "15px/1.6"
    body = "".join(
        f'<div class="l" style="color:#93c5fd;margin-top:10px">{html.escape(cmd)}</div>'
        + "".join(f'<div class="l" style="color:{colour(line)}">{html.escape(line)}</div>' for line in lines)
        for cmd, lines in blocks
    )
    return (
        f'<body style="margin:0;background:#0b1220;color:#e5e7eb;font:{size} Consolas,monospace;'
        'padding:20px 28px 80px">'
        '<h2 style="font:600 22px system-ui,sans-serif;margin:0 0 6px">Report contract v1 (#59)'
        " · real checker runs, synthetic fixtures</h2>"
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
            many = sum(len(lines) for _, lines in blocks) > 20
            page.set_content(scene_html(caption, blocks, small=many))
            page.evaluate(REVEAL_JS, 45 if many else 250)
            page.wait_for_timeout(3500)
        context.close()
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: demo-recording.py OUT_DIR")
    main(Path(sys.argv[1]))
