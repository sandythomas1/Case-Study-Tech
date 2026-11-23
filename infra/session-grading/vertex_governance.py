"""Apply and verify the Vertex AI zero-retention settings that Terraform can't express (#65).

The owner runs this script: changing the live project is owner work, like a deploy (AG-9).
Authentication uses the current gcloud principal, so no service-account key is involved. The owner's account needs roles/aiplatform.admin
for `disable-cache`; the read-only commands need only read access.

    python vertex_governance.py disable-cache   # setting 1: PATCH cacheConfig, then verify it
    python vertex_governance.py check           # settings 1, 2 and 3: read-only evidence
    python vertex_governance.py probe           # location pin: one synthetic call per pinned model

It prints PASS/FAIL lines and a UTC timestamp to paste into docs/decisions/vertex-ai-governance.md.
It never prints a model response, a request header or a token. The probe prompt is a fixed
synthetic string with no session content (RC-03, PA-3).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT = "casestudy-tech-dev-2e03d0"
# Must match `local.vertex` in main.tf; test_vertex_governance.py fails if they drift.
LOCATION = "us"
# The `us` multi-region needs its `.rep.` host (Google's Vertex AI locations page). us-central1
# returned 404 for both models on 2026-11-23, so the owner's fallback applies (ARCHITECTURE §6).
ENDPOINTS = {"us": "https://aiplatform.us.rep.googleapis.com"}
ALLOWED_LOCATIONS = frozenset(ENDPOINTS)
CONFIG_BASE = "https://aiplatform.googleapis.com/v1"
MODELS = {"persona": "gemini-3.8-flash", "grader": "gemini-4-argon"}
PROBE_PROMPT = "Reply with the single word OK."
TIMEOUT_SECONDS = 60

Json = dict[str, Any]
# (method, url, body) -> (HTTP status, parsed JSON body or {}).
Send = Callable[[str, str, Json | None], tuple[int, Json]]


@dataclass(frozen=True)
class Result:
    check: str
    passed: bool
    detail: str

    def line(self) -> str:
        return f"{'PASS' if self.passed else 'FAIL'}  {self.check}: {self.detail}"


def endpoint_base(location: str = LOCATION, version: str = "v1") -> str:
    # An allowlist, not a "global" denylist: a new location needs its own reviewed host.
    if location not in ALLOWED_LOCATIONS:
        raise ValueError(
            f"Location {location!r} is not allowed. Never global (ARCHITECTURE §6)."
        )
    return f"{ENDPOINTS[location]}/{version}"


def describe(status: int) -> str:
    return "no response (network error or timeout)" if status == 0 else f"HTTP {status}"


def cache_config_url(project: str = PROJECT) -> str:
    # The project-level config host Google documents for cacheConfig. It routes no prompt.
    return f"{CONFIG_BASE}/projects/{project}/cacheConfig"


def cached_contents_url(project: str = PROJECT, location: str = LOCATION) -> str:
    return f"{endpoint_base(location)}/projects/{project}/locations/{location}/cachedContents"


def model_path(model: str, project: str, location: str) -> str:
    return f"projects/{project}/locations/{location}/publishers/google/models/{model}"


def generate_url(model: str, project: str = PROJECT, location: str = LOCATION) -> str:
    return f"{endpoint_base(location)}/{model_path(model, project, location)}:generateContent"


def logging_config_url(
    model: str, project: str = PROJECT, location: str = LOCATION
) -> str:
    # Request-response logging config exists only in v1beta1, one per model and location.
    base = endpoint_base(location, version="v1beta1")
    return f"{base}/{model_path(model, project, location)}:fetchPublisherModelConfig"


def model_read_url(model: str, location: str = LOCATION) -> str:
    # Control read for setting 2: a 200 proves the host, API version and model ID resolve, so a 404
    # from fetchPublisherModelConfig can only mean "never configured".
    return (
        f"{endpoint_base(location, version='v1beta1')}/publishers/google/models/{model}"
    )


def disable_cache_body(project: str = PROJECT) -> Json:
    return {"name": f"projects/{project}/cacheConfig", "disableCache": True}


def probe_body() -> Json:
    return {
        "contents": [{"role": "user", "parts": [{"text": PROBE_PROMPT}]}],
        "generationConfig": {"maxOutputTokens": 8},
    }


def evaluate_cache_config(status: int, body: Json) -> Result:
    if status != 200:
        return Result("setting 1, implicit caching off", False, describe(status))
    if body.get("disableCache") is True:
        return Result("setting 1, implicit caching off", True, "disableCache: true")
    retention = body.get("retentionConfig", {}).get(
        "retentionType", "DURABLE (default)"
    )
    return Result(
        "setting 1, implicit caching off",
        False,
        f"caching is on, retentionType {retention}",
    )


def evaluate_cached_contents(status: int, body: Json) -> Result:
    if status != 200:
        return Result("setting 3, no explicit context caches", False, describe(status))
    count = len(body.get("cachedContents", []))
    return Result("setting 3, no explicit context caches", count == 0, f"{count} found")


def evaluate_logging_config(
    model: str, status: int, body: Json, model_read_status: int
) -> Result:
    check = f"setting 2, request-response logging off for {model}"
    if status == 404:
        # A wrong host, version or model ID also returns 404, so the control read must succeed.
        if model_read_status != 200:
            return Result(
                check,
                False,
                f"HTTP 404, but the model read got {describe(model_read_status)}, so it proves nothing",
            )
        # Google: no PublisherModelConfig exists, and logging is off until one does.
        return Result(
            check,
            True,
            "HTTP 404, never configured (off by default); model read HTTP 200",
        )
    if status != 200:
        return Result(check, False, describe(status))
    enabled = body.get("loggingConfig", {}).get("enabled", False)
    if enabled is False:
        return Result(check, True, "loggingConfig.enabled: false")
    return Result(check, False, "loggingConfig.enabled: true")


def evaluate_probe(role: str, model: str, status: int) -> Result:
    check = f"location, {role} model {model} served in {LOCATION}"
    if status == 200:
        return Result(check, True, "HTTP 200")
    # 404 means the model isn't served on this endpoint; 400 can say the same.
    hint = " (not served on this endpoint)" if status in (400, 404) else ""
    return Result(check, False, describe(status) + hint)


def check(send: Send) -> list[Result]:
    logging = [
        evaluate_logging_config(
            model,
            *send("GET", logging_config_url(model), None),
            send("GET", model_read_url(model), None)[0],
        )
        for model in MODELS.values()
    ]
    return [
        evaluate_cache_config(*send("GET", cache_config_url(), None)),
        *logging,
        evaluate_cached_contents(*send("GET", cached_contents_url(), None)),
    ]


def disable_cache(send: Send) -> list[Result]:
    status, _ = send("PATCH", cache_config_url(), disable_cache_body())
    if status != 200:
        return [Result("setting 1, PATCH cacheConfig", False, describe(status))]
    # PATCH returns a long-running operation, so read the setting back to prove it.
    return [
        Result("setting 1, PATCH cacheConfig", True, "HTTP 200"),
        evaluate_cache_config(*send("GET", cache_config_url(), None)),
    ]


def probe(send: Send) -> list[Result]:
    results = []
    for role, model in MODELS.items():
        status, _ = send("POST", generate_url(model), probe_body())
        results.append(evaluate_probe(role, model, status))
    return results


def find_on_path(names: tuple[str, ...], path: str) -> str | None:
    """Search PATH entries only. shutil.which on Windows also tries the current directory."""
    for directory in path.split(os.pathsep):
        if not directory or directory == os.curdir:
            continue
        for name in names:
            candidate = Path(directory) / name
            if candidate.is_file():
                return str(candidate)
    return None


def access_token() -> str:
    gcloud = find_on_path(("gcloud.cmd", "gcloud"), os.environ.get("PATH", ""))
    if gcloud is None:
        raise SystemExit("gcloud is not on PATH.")
    return subprocess.check_output(
        [gcloud, "auth", "print-access-token", "--project=" + PROJECT, "--quiet"],
        text=True,
    ).strip()


def http_sender(token: str) -> Send:
    def send(method: str, url: str, body: Json | None) -> tuple[int, Json]:
        request = urllib.request.Request(
            url,
            data=None if body is None else json.dumps(body).encode(),
            method=method,
            headers={
                "Authorization": "Bearer " + token,
                "x-goog-user-project": PROJECT,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            # Never read or print an error body: it can echo the request.
            error.close()
            return error.code, {}
        except (urllib.error.URLError, TimeoutError, ValueError):
            # No response, a timeout or a non-JSON body: report a FAIL line, not a traceback.
            return 0, {}

    return send


COMMANDS: dict[str, Callable[[Send], list[Result]]] = {
    "check": check,
    "disable-cache": disable_cache,
    "probe": probe,
}


def run(command: str, send: Send, now: datetime) -> tuple[str, bool]:
    results = COMMANDS[command](send)
    header = f"{command} · project {PROJECT} · {now.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    report = "\n".join([header, *(result.line() for result in results)])
    return report, all(result.passed for result in results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args(argv)
    report, passed = run(args.command, http_sender(access_token()), datetime.now(UTC))
    print(report)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
