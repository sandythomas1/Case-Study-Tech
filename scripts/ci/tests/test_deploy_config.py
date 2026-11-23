"""Tests for scripts/ci/deploy/deploy_config.py (stdlib unittest only).

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
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "ci" / "deploy" / "deploy_config.py"
_SPEC = importlib.util.spec_from_file_location("deploy_config", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
deploy_config = importlib.util.module_from_spec(_SPEC)
sys.modules["deploy_config"] = deploy_config
_SPEC.loader.exec_module(deploy_config)

HELLO = "us-docker.pkg.dev/cloudrun/container/hello@sha256:" + "a" * 64
VALID: dict[str, Any] = {
    "projectId": "casestudy-tech-dev-2e03d0",
    "projectNumber": "613104664964",
    "region": "us-central1",
    "workloadIdentityProvider": (
        "projects/613104664964/locations/global/workloadIdentityPools/github/providers/case-study-tech"
    ),
    "deployServiceAccount": "cst-deploy@casestudy-tech-dev-2e03d0.iam.gserviceaccount.com",
    "accountsGatewayUrl": "https://accounts-7tnmor5w.uc.gateway.dev",
    "privateAccountsServiceUrl": "https://accounts-447ob3nwoa-uc.a.run.app",
    "sessionImage": HELLO,
    "gradingImage": HELLO,
}


def with_value(field: str, value: Any) -> dict[str, Any]:
    data = copy.deepcopy(VALID)
    data[field] = value
    return data


class ParseTest(unittest.TestCase):
    def test_valid_config_derives_the_accounts_repository(self) -> None:
        config = deploy_config.parse(VALID)
        self.assertEqual(
            config.accounts_repository,
            "us-central1-docker.pkg.dev/casestudy-tech-dev-2e03d0/accounts/accounts",
        )
        self.assertEqual(config.session_image, HELLO)

    def test_the_real_development_file_is_valid(self) -> None:
        config = deploy_config.load(_ROOT / "infra" / "environments" / "development.json")
        self.assertEqual(config.project_id, "casestudy-tech-dev-2e03d0")
        self.assertTrue(config.session_image.startswith(deploy_config.PLACEHOLDER_REPOSITORY))
        self.assertTrue(config.grading_image.startswith(deploy_config.PLACEHOLDER_REPOSITORY))

    def test_project_practice_images_are_allowed(self) -> None:
        image = (
            "us-central1-docker.pkg.dev/casestudy-tech-dev-2e03d0/practice/session@sha256:"
            + "b" * 64
        )
        self.assertEqual(deploy_config.parse(with_value("sessionImage", image)).session_image, image)

    def test_rejected_images(self) -> None:
        cases = {
            "tag instead of digest": "us-docker.pkg.dev/cloudrun/container/hello:latest",
            "short digest": "us-docker.pkg.dev/cloudrun/container/hello@sha256:abc",
            "another registry": "docker.io/library/nginx@sha256:" + "a" * 64,
            "another project": "us-central1-docker.pkg.dev/other-project-123/practice/session@sha256:"
            + "a" * 64,
            "wrong service in practice": "us-central1-docker.pkg.dev/casestudy-tech-dev-2e03d0/"
            "practice/grading@sha256:" + "a" * 64,
            "shell metacharacters": HELLO + "; echo pwned",
            "newline injection": HELLO + "\nproject_id=evil",
        }
        for label, image in cases.items():
            with self.subTest(label), self.assertRaises(deploy_config.ConfigError):
                deploy_config.parse(with_value("sessionImage", image))

    def test_rejected_identity_values(self) -> None:
        cases = {
            "provider in another project": (
                "workloadIdentityProvider",
                "projects/999999999/locations/global/workloadIdentityPools/github/providers/x-repo",
            ),
            "deploy account in another project": (
                "deployServiceAccount",
                "cst-deploy@other-project-123.iam.gserviceaccount.com",
            ),
            "a different service account": (
                "deployServiceAccount",
                "cst-accounts@casestudy-tech-dev-2e03d0.iam.gserviceaccount.com",
            ),
            "plain http gateway": ("accountsGatewayUrl", "http://accounts-7tnmor5w.uc.gateway.dev"),
            "non Cloud Run service URL": ("privateAccountsServiceUrl", "https://example.com"),
            "upper-case project": ("projectId", "CaseStudy"),
        }
        for label, (field, value) in cases.items():
            with self.subTest(label), self.assertRaises(deploy_config.ConfigError):
                deploy_config.parse(with_value(field, value))

    def test_missing_field_and_non_string_values_are_rejected(self) -> None:
        data = copy.deepcopy(VALID)
        del data["gradingImage"]
        with self.assertRaises(deploy_config.ConfigError):
            deploy_config.parse(data)
        with self.assertRaises(deploy_config.ConfigError):
            deploy_config.parse(with_value("projectNumber", 613104664964))
        with self.assertRaises(deploy_config.ConfigError):
            deploy_config.parse([VALID])


class MainTest(unittest.TestCase):
    def run_main(self, content: str) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "env.json"
            path.write_text(content, encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = deploy_config.main(["deploy_config.py", str(path)])
        return code, out.getvalue(), err.getvalue()

    def test_valid_file_prints_one_output_per_line(self) -> None:
        code, out, _ = self.run_main(json.dumps(VALID))
        self.assertEqual(code, 0)
        lines = dict(line.split("=", 1) for line in out.splitlines())
        self.assertEqual(lines["session_image"], HELLO)
        self.assertEqual(len(lines), 10)

    def test_invalid_file_prints_nothing_to_stdout(self) -> None:
        code, out, err = self.run_main(json.dumps(with_value("sessionImage", "bad")))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("sessionImage", err)
        self.assertNotIn("bad", err)

    def test_unreadable_json_fails(self) -> None:
        code, out, _ = self.run_main("{not json")
        self.assertEqual((code, out), (1, ""))

    def test_wrong_argument_count(self) -> None:
        with redirect_stderr(io.StringIO()):
            self.assertEqual(deploy_config.main(["deploy_config.py"]), 2)


if __name__ == "__main__":
    unittest.main()
