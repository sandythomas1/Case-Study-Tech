"""Read and validate one deploy environment file for the deploy workflow (#105).

The workflow passes every value this prints to gcloud through environment variables, so each
value is checked against a strict pattern here first. A malformed or unexpected value stops the
deploy before any cloud call. Standard library only.

Usage (from the repository root):
    python scripts/ci/deploy/deploy_config.py infra/environments/development.json >> "$GITHUB_OUTPUT"
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
PROJECT_NUMBER = re.compile(r"^[0-9]{6,20}$")
REGION = re.compile(r"^[a-z]+-[a-z]+[0-9]$")
DIGEST = r"@sha256:[0-9a-f]{64}"
GATEWAY_URL = re.compile(r"^https://[a-z0-9-]+\.[a-z0-9]+\.gateway\.dev$")
RUN_URL = re.compile(r"^https://[a-z0-9-]+\.a\.run\.app$")
WIF_PROVIDER = re.compile(
    r"^projects/[0-9]{6,20}/locations/global/workloadIdentityPools/[a-z0-9-]{4,32}"
    r"/providers/[a-z0-9-]{4,32}$"
)

# Session and grading may run only Google's public hello placeholder or an image from this
# project's own practice repository. Switching to a real image is a reviewed change to the
# environment file, and the runbook's #72 precondition still applies before it.
PLACEHOLDER_REPOSITORY = "us-docker.pkg.dev/cloudrun/container/hello"


class ConfigError(ValueError):
    """The environment file is missing a field or holds a value the deploy must not use."""


@dataclass(frozen=True)
class DeployConfig:
    project_id: str
    project_number: str
    region: str
    wif_provider: str
    deploy_service_account: str
    accounts_gateway_url: str
    private_accounts_service_url: str
    accounts_repository: str
    session_image: str
    grading_image: str

    def outputs(self) -> dict[str, str]:
        return {
            "project_id": self.project_id,
            "project_number": self.project_number,
            "region": self.region,
            "wif_provider": self.wif_provider,
            "deploy_service_account": self.deploy_service_account,
            "accounts_gateway_url": self.accounts_gateway_url,
            "private_accounts_service_url": self.private_accounts_service_url,
            "accounts_repository": self.accounts_repository,
            "session_image": self.session_image,
            "grading_image": self.grading_image,
        }


def _field(data: dict[str, Any], name: str, pattern: re.Pattern[str]) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ConfigError(f"{name} is missing or malformed")
    return value


def _practice_image(project_id: str, region: str, service: str) -> re.Pattern[str]:
    repository = re.escape(f"{region}-docker.pkg.dev/{project_id}/practice/{service}")
    placeholder = re.escape(PLACEHOLDER_REPOSITORY)
    return re.compile(rf"^(?:{placeholder}|{repository}){DIGEST}$")


def parse(data: Any) -> DeployConfig:
    if not isinstance(data, dict):
        raise ConfigError("the environment file must hold a JSON object")
    project_id = _field(data, "projectId", PROJECT_ID)
    project_number = _field(data, "projectNumber", PROJECT_NUMBER)
    region = _field(data, "region", REGION)
    wif_provider = _field(data, "workloadIdentityProvider", WIF_PROVIDER)
    if not wif_provider.startswith(f"projects/{project_number}/"):
        raise ConfigError("workloadIdentityProvider must belong to this project's number")
    deploy_account = _field(
        data,
        "deployServiceAccount",
        re.compile(rf"^cst-deploy@{re.escape(project_id)}\.iam\.gserviceaccount\.com$"),
    )
    return DeployConfig(
        project_id=project_id,
        project_number=project_number,
        region=region,
        wif_provider=wif_provider,
        deploy_service_account=deploy_account,
        accounts_gateway_url=_field(data, "accountsGatewayUrl", GATEWAY_URL),
        private_accounts_service_url=_field(data, "privateAccountsServiceUrl", RUN_URL),
        accounts_repository=f"{region}-docker.pkg.dev/{project_id}/accounts/accounts",
        session_image=_field(data, "sessionImage", _practice_image(project_id, region, "session")),
        grading_image=_field(data, "gradingImage", _practice_image(project_id, region, "grading")),
    )


def load(path: Path) -> DeployConfig:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"cannot read {path.name}: {error.__class__.__name__}") from None
    return parse(data)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: deploy_config.py <environment.json>", file=sys.stderr)
        return 2
    try:
        config = load(Path(argv[1]))
    except ConfigError as error:
        print(f"::error::Deploy config rejected: {error}", file=sys.stderr)
        return 1
    for key, value in config.outputs().items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
