"""Every synthetic script against the live persona, through the real entry point (#67 FR-6).

Owner-run only: ``uv run pytest -m live`` from ``services/session``, logged in
with ``gcloud auth login`` on the dev project. The default ``uv run pytest``
skips it (``addopts`` in ``pyproject.toml``). The harness prints check results
only, so a failure message holds counts, never a reply.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness.run import GCLOUD_NAMES, find_on_path
from harness.script import SCRIPT_IDS

SERVICE_ROOT = Path(__file__).resolve().parents[2]
RUN_TIMEOUT_S = 900

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        find_on_path(GCLOUD_NAMES, os.environ.get("PATH", "")) is None,
        reason="gcloud is not on PATH: install the Google Cloud CLI and run "
        "gcloud auth login to run the live persona checks",
    ),
]


@pytest.mark.parametrize("script_id", SCRIPT_IDS)
def test_the_live_persona_passes_every_gating_check(script_id: str) -> None:
    ran = subprocess.run(
        [sys.executable, "-m", "harness.run", "--scenario", script_id],
        cwd=SERVICE_ROOT,
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT_S,
        check=False,
    )

    assert ran.returncode == 0, ran.stdout
