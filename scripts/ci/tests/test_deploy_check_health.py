"""Tests for scripts/ci/deploy/check_health.py (stdlib unittest only).

Run from the repository root: python -m unittest discover -s scripts/ci/tests
"""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

_SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "check_health.py"
_SPEC = importlib.util.spec_from_file_location("check_health", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
check_health = importlib.util.module_from_spec(_SPEC)
sys.modules["check_health"] = check_health
_SPEC.loader.exec_module(check_health)

IMAGE = "us-docker.pkg.dev/cloudrun/container/hello@sha256:" + "a" * 64
HEALTHY: dict[str, Any] = {
    "spec": {"template": {"spec": {"containers": [{"image": IMAGE}]}}},
    "status": {
        "conditions": [{"type": "Ready", "status": "True"}],
        "latestCreatedRevisionName": "session-00003-abc",
        "latestReadyRevisionName": "session-00003-abc",
        "traffic": [{"latestRevision": True, "percent": 100}],
    },
}


def mutated(path: list[str | int], value: Any) -> dict[str, Any]:
    data = copy.deepcopy(HEALTHY)
    target: Any = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return data


class ServiceProblemsTest(unittest.TestCase):
    def test_healthy_service_has_no_problems(self) -> None:
        self.assertEqual(check_health.service_problems(HEALTHY, IMAGE), [])

    def test_each_failure_is_reported(self) -> None:
        cases = {
            "not Ready": (mutated(["status", "conditions"], [{"type": "Ready", "status": "False"}]),
                          "not Ready"),
            "no conditions": (mutated(["status", "conditions"], []), "not Ready"),
            "revision still rolling": (mutated(["status", "latestReadyRevisionName"], "session-00002"),
                                       "newest revision"),
            "old image": (mutated(["spec", "template", "spec", "containers"],
                                  [{"image": IMAGE.replace("a", "b")}]), "image"),
            "sidecar added": (mutated(["spec", "template", "spec", "containers"],
                                      [{"image": IMAGE}, {"image": IMAGE}]), "image"),
            "traffic pinned to an old revision": (
                mutated(["status", "traffic"], [{"revisionName": "session-00001", "percent": 100}]),
                "traffic"),
            "traffic split": (mutated(["status", "traffic"], [{"latestRevision": True, "percent": 50}]),
                              "traffic"),
        }
        for label, (describe, fragment) in cases.items():
            with self.subTest(label):
                problems = check_health.service_problems(describe, IMAGE)
                self.assertTrue(any(fragment in p for p in problems), problems)

    def test_unreadable_describe_is_a_problem(self) -> None:
        self.assertEqual(len(check_health.service_problems(None, IMAGE)), 1)
        self.assertGreaterEqual(len(check_health.service_problems({}, IMAGE)), 3)


class HttpChecksTest(unittest.TestCase):
    def test_checks_cover_both_gateway_routes_and_the_private_url(self) -> None:
        checks = check_health.http_checks("https://g.gateway.dev", "https://a.a.run.app")
        self.assertEqual(
            [(c.url, c.expected) for c in checks],
            [
                ("https://g.gateway.dev/health", 200),
                ("https://g.gateway.dev/v1/sessions/health", 200),
                ("https://a.a.run.app/health", 403),
            ],
        )

    def test_retries_until_the_expected_status(self) -> None:
        responses = iter([404, 503, 200])
        sleeps: list[float] = []
        with redirect_stdout(io.StringIO()):
            failures = check_health.run_http_checks(
                [check_health.HttpCheck("x", "u", 200)],
                fetch=lambda _url: next(responses),
                attempts=5,
                wait_seconds=1,
                sleep=sleeps.append,
            )
        self.assertEqual((failures, sleeps), ([], [1, 1]))

    def test_gives_up_after_the_last_attempt_without_a_final_sleep(self) -> None:
        sleeps: list[float] = []
        out = io.StringIO()
        with redirect_stdout(out):
            failures = check_health.run_http_checks(
                [check_health.HttpCheck("private", "u", 403)],
                fetch=lambda _url: 200,
                attempts=3,
                wait_seconds=2,
                sleep=sleeps.append,
            )
        self.assertEqual((failures, sleeps), (["private"], [2, 2]))
        self.assertIn("HTTP 200 (expected 403)", out.getvalue())


class MainTest(unittest.TestCase):
    def call(self, describe: str, http_failures: list[str]) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.json"
            path.write_text(describe, encoding="utf-8")
            out = io.StringIO()
            with mock.patch.object(check_health, "run_http_checks", return_value=http_failures),                     redirect_stdout(out), io.StringIO() as err, mock.patch("sys.stderr", err):
                code = check_health.main([
                    "check_health.py", "--gateway-url", "https://g.example",
                    "--private-accounts-url", "https://a.run.app",
                    "--service", f"session={path}={IMAGE}",
                ])
            return code, out.getvalue()

    def test_healthy_run_passes(self) -> None:
        code, out = self.call(json.dumps(HEALTHY), [])
        self.assertEqual(code, 0)
        self.assertIn("session: healthy (revision session-00003-abc)", out)

    def test_http_failure_fails_the_run(self) -> None:
        self.assertEqual(self.call(json.dumps(HEALTHY), ["private"])[0], 1)

    def test_unreadable_or_odd_describe_output_fails_without_crashing(self) -> None:
        for label, describe in {"not JSON": "{", "a list": "[1]", "null status": '{"status": null}'}.items():
            with self.subTest(label):
                code, out = self.call(describe, [])
                self.assertEqual(code, 1)
                self.assertIn("(revision -)", out)


if __name__ == "__main__":
    unittest.main()
