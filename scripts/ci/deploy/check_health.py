"""Post-deploy health check for the development services (#105, AC1).

Two kinds of evidence, neither of which needs a credential:

- Cloud Run status from `gcloud run services describe --format=json`: the service is Ready, its
  newest revision is the one serving, that revision runs the image this deploy set, and it gets
  all the traffic. This is grading's only health check, because cst-session stays its only
  invoker (ARCHITECTURE §9) and the deploy identity never gets to call it.
- Anonymous HTTP: accounts and session answer /health with 200 through the gateway, and every
  service's own run.app URL refuses an anonymous caller with 403, so the deploy made none of them
  public.

It prints status codes and revision names only, never a response body. Standard library only.

Usage (from the repository root):
    python scripts/ci/deploy/check_health.py --gateway-url G \
        --service accounts=accounts.json=IMAGE --service session=session.json=IMAGE ...
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Fetch = Callable[[str], int]

RUN_URL = re.compile(r"^https://[a-z0-9-]+(\.[a-z0-9-]+)*\.run\.app$")


@dataclass(frozen=True)
class HttpCheck:
    name: str
    url: str
    expected: int


def service_problems(describe: Any, expected_image: str) -> list[str]:
    """Return what is wrong with one `gcloud run services describe` result; empty means healthy."""
    if not isinstance(describe, dict):
        return ["the describe output is not a JSON object"]
    status = describe.get("status") or {}
    problems: list[str] = []
    conditions = {c.get("type"): c.get("status") for c in status.get("conditions") or []}
    if conditions.get("Ready") != "True":
        problems.append("the service is not Ready")
    created = status.get("latestCreatedRevisionName")
    ready = status.get("latestReadyRevisionName")
    if not created or created != ready:
        problems.append("the newest revision is not the ready one")
    containers = ((describe.get("spec") or {}).get("template") or {}).get("spec") or {}
    images = [c.get("image") for c in containers.get("containers") or []]
    if images != [expected_image]:
        problems.append("the revision does not run the image this deploy set")
    traffic = status.get("traffic") or []
    if not any(t.get("latestRevision") and t.get("percent") == 100 for t in traffic):
        problems.append("the newest revision does not get 100% of traffic")
    return problems


def private_url(describe: Any) -> str | None:
    """The service's own run.app URL, or None if the describe output has no valid one."""
    status = describe.get("status") if isinstance(describe, dict) else None
    url = (status or {}).get("url")
    return url if isinstance(url, str) and RUN_URL.fullmatch(url) else None


def http_checks(gateway_url: str, private_urls: list[tuple[str, str]]) -> list[HttpCheck]:
    checks = [
        HttpCheck("accounts through the gateway", f"{gateway_url}/health", 200),
        HttpCheck("session through the gateway", f"{gateway_url}/v1/sessions/health", 200),
    ]
    checks += [
        HttpCheck(f"{name} refuses anonymous callers", f"{url}/health", 403)
        for name, url in private_urls
    ]
    return checks


def fetch_status(url: str) -> int:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return int(response.status)
    except urllib.error.HTTPError as error:
        return int(error.code)
    except (urllib.error.URLError, TimeoutError):
        return 0


def run_http_checks(
    checks: list[HttpCheck],
    fetch: Fetch = fetch_status,
    attempts: int = 10,
    wait_seconds: float = 15.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[str]:
    """Retry each check, because a new gateway config can take minutes to serve."""
    failures: list[str] = []
    for check in checks:
        status = 0
        for attempt in range(attempts):
            status = fetch(check.url)
            if status == check.expected:
                break
            if attempt < attempts - 1:
                sleep(wait_seconds)
        print(f"{check.name}: HTTP {status} (expected {check.expected})")
        if status != check.expected:
            failures.append(check.name)
    return failures


def _parse_service(value: str) -> tuple[str, Path, str]:
    name, path, image = value.split("=", 2)
    return name, Path(path), image


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--service", action="append", type=_parse_service, required=True)
    args = parser.parse_args(argv[1:])
    failed = False
    private_urls: list[tuple[str, str]] = []
    for name, path, image in args.service:
        try:
            describe = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            describe = None
        problems = service_problems(describe, image)
        url = private_url(describe)
        if url is None:
            problems.append("the service has no Cloud Run URL")
        else:
            private_urls.append((name, url))
        status = describe.get("status") if isinstance(describe, dict) else None
        revision = (status or {}).get("latestReadyRevisionName") or "-"
        print(f"{name}: {'healthy' if not problems else '; '.join(problems)} (revision {revision})")
        failed = failed or bool(problems)
    failures = run_http_checks(http_checks(args.gateway_url, private_urls))
    if failed or failures:
        print("::error::Post-deploy health check failed.", file=sys.stderr)
        return 1
    print("All services are healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
