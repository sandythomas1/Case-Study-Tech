"""Invariants of .github/workflows/deploy.yml and infra/ci-deploy that #105's AC2 and AC3 rely on
(stdlib unittest only).

GitHub settings and Google Cloud IAM cannot be checked offline, but the files that configure them
can. These tests fail if a change gives a job other than the development deploy an OIDC token,
drops the production approval gate, adds a stored credential, adds another trigger, or lets the
workflow and the Workload Identity provider disagree on the branch or environment.

Run from the repository root: python -m unittest discover -s scripts/ci/tests
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOW = _ROOT / ".github" / "workflows" / "deploy.yml"
_CI_DEPLOY = _ROOT / "infra" / "ci-deploy" / "main.tf"
_ENVIRONMENT = _ROOT / "infra" / "environments" / "development.json"


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _top_level_block(lines: list[str], key: str) -> list[str]:
    """The lines under a column-0 YAML key, up to the next column-0 key."""
    start = lines.index(f"{key}:")
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line and not line[0].isspace() and not line.startswith("#"):
            break
        block.append(line)
    return block


def _jobs(lines: list[str]) -> dict[str, str]:
    """Each job's body text, keyed by job ID (two-space indented keys under `jobs:`)."""
    jobs: dict[str, list[str]] = {}
    current: str | None = None
    for line in _top_level_block(lines, "jobs"):
        match = re.fullmatch(r"  ([A-Za-z0-9_-]+):\s*", line)
        if match:
            current = match.group(1)
            jobs[current] = []
        elif current is not None:
            jobs[current].append(line)
    return {name: "\n".join(body) for name, body in jobs.items()}


def _uncommented(text: str) -> str:
    return "\n".join(line.split(" #", 1)[0] for line in text.splitlines())


class WorkflowInvariantsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lines = _lines(_WORKFLOW)
        cls.text = "\n".join(cls.lines)
        cls.jobs = _jobs(cls.lines)

    def test_has_exactly_the_development_and_production_jobs(self) -> None:
        self.assertEqual(set(self.jobs), {"development", "production"})

    def test_only_pushes_to_staging_and_main_start_a_deploy(self) -> None:
        trigger = "\n".join(_top_level_block(self.lines, "on"))
        self.assertRegex(trigger, r"(?m)^  push:\s*$")
        self.assertRegex(trigger, r"(?m)^    branches: \[staging, main\]\s*$")
        for event in (
            "workflow_dispatch",
            "workflow_call",
            "workflow_run",
            "pull_request",
            "pull_request_target",
            "schedule",
            "repository_dispatch",
            "tags",
        ):
            self.assertNotRegex(trigger, rf"\b{event}\b", event)

    def test_workflow_token_defaults_to_read_only(self) -> None:
        permissions = "\n".join(_top_level_block(self.lines, "permissions"))
        self.assertEqual(permissions.strip(), "contents: read")

    def test_a_started_deploy_is_never_cancelled(self) -> None:
        concurrency = "\n".join(_top_level_block(self.lines, "concurrency"))
        self.assertRegex(concurrency, r"(?m)^  cancel-in-progress: false\s*$")

    def test_production_waits_for_the_production_environment(self) -> None:
        production = _uncommented(self.jobs["production"])
        self.assertRegex(production, r"(?m)^    environment: production\s*$")
        self.assertRegex(production, r"(?m)^    if: github\.ref == 'refs/heads/main'\s*$")

    def test_production_has_no_way_to_reach_google_cloud(self) -> None:
        production = _uncommented(self.jobs["production"])
        self.assertNotIn("id-token", production)
        self.assertNotIn("google-github-actions/auth", production)
        self.assertNotIn("gcloud", production)

    def test_development_runs_only_on_staging_in_the_development_environment(self) -> None:
        development = _uncommented(self.jobs["development"])
        self.assertRegex(development, r"(?m)^    environment: development\s*$")
        self.assertRegex(development, r"(?m)^    if: github\.ref == 'refs/heads/staging'\s*$")
        self.assertRegex(development, r"(?m)^      id-token: write\s*$")

    def test_no_stored_credential_is_read(self) -> None:
        workflow = _uncommented(self.text)
        self.assertNotRegex(workflow, r"\bsecrets\.")
        self.assertNotIn("credentials_json", workflow)
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS", workflow)
        self.assertNotIn("GOOGLE_CREDENTIALS", workflow)

    def test_auth_uses_workload_identity_from_the_validated_config(self) -> None:
        development = _uncommented(self.jobs["development"])
        self.assertEqual(development.count("google-github-actions/auth@"), 1)
        self.assertRegex(
            development,
            r"workload_identity_provider: \$\{\{ steps\.config\.outputs\.wif_provider \}\}",
        )
        self.assertRegex(
            development,
            r"service_account: \$\{\{ steps\.config\.outputs\.deploy_service_account \}\}",
        )
        # The config is validated before the job signs in.
        self.assertLess(
            development.index("scripts/ci/deploy/deploy_config.py"),
            development.index("google-github-actions/auth@"),
        )

    def test_every_rollout_returns_traffic_to_the_newest_revision(self) -> None:
        # The runbook's rollback test relies on the next deploy undoing a pinned rollback.
        self.assertIn('update-traffic "$name" --to-latest', self.jobs["development"])

    def test_gateway_backends_come_from_the_live_services(self) -> None:
        development = _uncommented(self.jobs["development"])
        self.assertIn('if [ "$accounts_url" != "$ACCOUNTS_URL" ]; then', development)
        self.assertIn('--accounts-url "$accounts_url" --session-url "$session_url"', development)
        self.assertNotIn('--accounts-url "$ACCOUNTS_URL"', development)


class ProviderMatchesWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.terraform = _CI_DEPLOY.read_text(encoding="utf-8")

    def test_provider_accepts_only_staging_in_the_development_environment(self) -> None:
        self.assertRegex(self.terraform, r'(?m)^\s*environment\s*=\s*"development"\s*$')
        self.assertIn("\"assertion.ref == 'refs/heads/staging'\"", self.terraform)
        self.assertIn("\"assertion.environment == '${local.environment}'\"", self.terraform)
        self.assertIn(
            "\"assertion.repository_id == '${var.github_repository_id}'\"", self.terraform
        )

    def test_provider_rejects_reruns_other_events_and_other_workflows(self) -> None:
        self.assertIn("\"assertion.event_name == 'push'\"", self.terraform)
        self.assertIn("\"assertion.run_attempt == '1'\"", self.terraform)
        workflow_ref = re.search(
            r"\"assertion\.job_workflow_ref == '\$\{var\.github_repository\}/"
            r"(\.github/workflows/[A-Za-z0-9_.-]+)@refs/heads/staging'\"",
            self.terraform,
        )
        assert workflow_ref is not None, "job_workflow_ref condition is missing"
        self.assertEqual(_ROOT / workflow_ref.group(1), _WORKFLOW)

    def test_impersonation_is_bound_to_the_environment_subject_only(self) -> None:
        self.assertIn("/subject/${local.github_subject}\"", self.terraform)
        self.assertNotIn("principalSet://", self.terraform)

    def test_subject_uses_githubs_immutable_format(self) -> None:
        # The repository sets use_immutable_subject, so the token's sub is
        # repo:OWNER@OWNER_ID/REPO@REPO_ID:environment:ENV (#124).
        self.assertIn(
            'github_subject   = "repo:${local.github_owner}@${var.github_owner_id}/'
            '${local.github_repo_name}@${var.github_repository_id}'
            ':environment:${local.environment}"',
            self.terraform,
        )

    def test_old_name_based_subject_is_gone(self) -> None:
        # The name-based subject never matches an immutable-format token (run 45109763808).
        self.assertNotRegex(self.terraform, r"subject/repo:\$\{var\.github_repository\}")
        self.assertNotRegex(self.terraform, r"repo:[A-Za-z0-9-]+/[A-Za-z0-9_.-]+:environment:")

    def test_owner_and_repository_ids_are_the_live_ones(self) -> None:
        owner_id = re.search(
            r'variable "github_owner_id" \{\s*type\s*=\s*string\s*default\s*=\s*"([0-9]+)"',
            self.terraform,
        )
        repository_id = re.search(
            r'variable "github_repository_id" \{\s*type\s*=\s*string\s*default\s*=\s*"([0-9]+)"',
            self.terraform,
        )
        assert owner_id and repository_id
        self.assertEqual(owner_id.group(1), "145699956")
        self.assertEqual(repository_id.group(1), "1382155772")

    def test_environment_file_names_what_terraform_creates(self) -> None:
        data = json.loads(_ENVIRONMENT.read_text(encoding="utf-8"))
        pool = re.search(r'workload_identity_pool_id\s*=\s*"([a-z0-9-]+)"', self.terraform)
        provider = re.search(
            r'workload_identity_pool_provider_id\s*=\s*"([a-z0-9-]+)"', self.terraform
        )
        account = re.search(r'account_id\s*=\s*"(cst-deploy)"', self.terraform)
        assert pool and provider and account
        self.assertEqual(
            data["workloadIdentityProvider"],
            f"projects/{data['projectNumber']}/locations/global/workloadIdentityPools/"
            f"{pool.group(1)}/providers/{provider.group(1)}",
        )
        self.assertEqual(
            data["deployServiceAccount"],
            f"{account.group(1)}@{data['projectId']}.iam.gserviceaccount.com",
        )

    def test_no_terraform_module_creates_a_service_account_key(self) -> None:
        for path in sorted((_ROOT / "infra").rglob("*.tf")):
            if ".terraform" in path.parts:
                continue
            with self.subTest(path=path.relative_to(_ROOT).as_posix()):
                self.assertNotIn("google_service_account_key", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
