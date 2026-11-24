"""Request and response body logging stays off at the gateway and Cloud Run (AC3).

ARCHITECTURE section 7 and plan IR-5. Neither platform can be told "off" in
configuration, because neither has a body-logging setting to turn on:

- API Gateway runs a managed ESPv2 whose OpenAPI config has no logging
  extension. The ESPv2 flags that log headers or JWT payloads
  (``--log_request_headers``, ``--log_response_headers``,
  ``--log_jwt_payloads``) are not exposed by the managed gateway, so the check
  is that none of them, nor any logging key, appears in our config.
- Cloud Run's request logs record method, URL, status, latency and sizes, never
  bodies. What the service itself writes is governed by the container command,
  so the check is that every uvicorn command has ``--no-access-log`` and no
  debug log level, and that neither Terraform nor the deploy workflow overrides
  the image's command, arguments or log settings.

So this test asserts absence. It reads repository files only. CI runs each
service from its own directory with the whole repository checked out, so paths
are resolved from this file.
"""

import json
import re
import shlex
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
INFRA = REPO_ROOT / "infra"
GATEWAY_TEMPLATE = INFRA / "gateway.yaml.template"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"

BODY_LOGGING_TOKENS = (
    "log_request",
    "log_response",
    "log_jwt",
    "request_body",
    "response_body",
    "access_log",
)
VERBOSE_LOG_LEVEL = re.compile(r"--log-level[ =\"',]+(debug|trace)", re.IGNORECASE)
CLOUD_RUN_BLOCK = re.compile(r'resource "google_cloud_run_v2_(service|job)" "(\w+)" \{')
COMMAND_OVERRIDE = re.compile(r"^\s*(command|args)\s*=", re.MULTILINE)
ENV_NAME = re.compile(r'^\s*name\s*=\s*"([^"]+)"', re.MULTILINE)


def terraform_files() -> list[Path]:
    return sorted(
        path
        for path in INFRA.rglob("*.tf")
        if not {".terraform", "node_modules"}.intersection(path.parts)
    )


def block_body(text: str, opening_brace: int) -> str:
    """The text of the HCL block whose ``{`` is at ``opening_brace``."""
    depth = 0
    for index in range(opening_brace, len(text)):
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        if depth == 0:
            return text[opening_brace : index + 1]
    raise AssertionError("unbalanced braces in Terraform")


def cloud_run_blocks() -> dict[str, str]:
    blocks: dict[str, str] = {}
    for path in terraform_files():
        text = path.read_text(encoding="utf-8")
        for match in CLOUD_RUN_BLOCK.finditer(text):
            blocks[f"{path.relative_to(INFRA).as_posix()}:{match.group(2)}"] = (
                block_body(text, match.end() - 1)
            )
    return blocks


def test_the_gateway_config_has_no_logging_settings() -> None:
    text = GATEWAY_TEMPLATE.read_text(encoding="utf-8")
    keys = re.findall(r"^\s*-?\s*([\w-]+):", text, re.MULTILINE)

    assert keys, "the gateway template no longer parses as key: value lines"
    assert [key for key in keys if "log" in key.lower()] == []
    assert [token for token in BODY_LOGGING_TOKENS if token in text.lower()] == []


def test_terraform_sets_no_body_or_verbose_logging() -> None:
    files = terraform_files()

    assert files
    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        assert [token for token in BODY_LOGGING_TOKENS if token in text] == [], path
        assert not VERBOSE_LOG_LEVEL.search(text), path


def test_cloud_run_services_keep_the_image_command_and_add_no_log_settings() -> None:
    blocks = cloud_run_blocks()
    services = {name for name in blocks if not name.endswith(":deletion")}

    assert {
        "accounts/main.tf:accounts",
        "session-grading/main.tf:session",
        "session-grading/main.tf:grading",
    } <= services
    for name in services:
        assert not COMMAND_OVERRIDE.search(blocks[name]), name
        env_names = ENV_NAME.findall(blocks[name])
        assert [env for env in env_names if re.search("LOG|DEBUG|TRACE", env)] == []


def test_the_deletion_job_runs_the_sweep_not_a_web_server() -> None:
    job = cloud_run_blocks()["accounts/main.tf:deletion"]

    assert 'command = ["python", "-m", "cst_accounts.main"]' in job
    assert "uvicorn" not in job


def dockerfile_instructions(text: str) -> list[str]:
    """Logical Dockerfile lines: continuations joined, comments and blanks dropped."""
    instructions: list[str] = []
    pending = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            pending += line[:-1].strip() + " "
            continue
        instructions.append(pending + line)
        pending = ""
    if pending:
        instructions.append(pending.strip())
    return instructions


def uvicorn_commands(text: str) -> list[list[str]]:
    """Each CMD or ENTRYPOINT that runs uvicorn, as a flat list of arguments.

    Both forms are parsed: a JSON array (``exec`` form) and a shell string.
    Arguments are split again so ``["sh", "-c", "uvicorn ..."]`` is seen too.
    """
    commands: list[list[str]] = []
    for instruction in dockerfile_instructions(text):
        match = re.match(r"(CMD|ENTRYPOINT)\s+(.+)", instruction, re.IGNORECASE)
        if not match:
            continue
        body = match.group(2).strip()
        parts = json.loads(body) if body.startswith("[") else [body]
        tokens = [token for part in parts for token in split_arguments(str(part))]
        if any(Path(token).name == "uvicorn" for token in tokens):
            commands.append(tokens)
    return commands


def split_arguments(text: str) -> list[str]:
    """Shell-split ``text``, then split again any argument that holds a space.

    That unwraps a quoted inner command such as ``sh -c "exec uvicorn app"``.
    Each pass strips one layer of quoting, so it ends.
    """
    tokens: list[str] = []
    for token in shlex.split(text):
        tokens += split_arguments(token) if " " in token else [token]
    return tokens


def access_log_problems(command: list[str]) -> list[str]:
    """Why ``command`` could log requests, or ``[]`` when it cannot."""
    problems = [] if "--no-access-log" in command else ["no --no-access-log"]
    if "--access-log" in command:
        problems.append("--access-log")
    for index, token in enumerate(command):
        level = None
        if token.startswith("--log-level="):
            level = token.split("=", 1)[1]
        elif token == "--log-level" and index + 1 < len(command):
            level = command[index + 1]
        if level is not None and level.lower() in {"debug", "trace"}:
            problems.append(f"--log-level {level}")
    return problems


def test_every_uvicorn_container_command_disables_the_access_log() -> None:
    commands = [
        command
        for dockerfile in sorted((REPO_ROOT / "services").glob("*/Dockerfile"))
        for command in uvicorn_commands(dockerfile.read_text(encoding="utf-8"))
    ]

    assert commands, "no service container runs uvicorn"
    assert [access_log_problems(command) for command in commands] == [
        [] for _ in commands
    ]


MULTI_LINE_CMD = r"""FROM python:3.12-slim
# The server command, split for readability.
CMD ["uvicorn", "cst_demo.main:app", \
     # host and port
     "--host", "0.0.0.0", \
     "--port", "8080"%s]
"""


@pytest.mark.parametrize(
    ("extra", "problems"),
    [
        (', "--no-access-log"', []),
        ("", ["no --no-access-log"]),
        (', "--no-access-log", "--log-level", "debug"', ["--log-level debug"]),
        (', "--no-access-log", "--log-level=TRACE"', ["--log-level TRACE"]),
    ],
)
def test_a_multi_line_exec_form_command_is_parsed_whole(
    extra: str, problems: list[str]
) -> None:
    (command,) = uvicorn_commands(MULTI_LINE_CMD % extra)

    assert command[:2] == ["uvicorn", "cst_demo.main:app"]
    assert access_log_problems(command) == problems


@pytest.mark.parametrize(
    ("dockerfile", "problems"),
    [
        ("CMD uvicorn app:app \\\n    --port 8080", ["no --no-access-log"]),
        ("CMD uvicorn app:app \\\n    --no-access-log", []),
        (
            'ENTRYPOINT ["sh", "-c", "uvicorn app:app --access-log"]',
            ["no --no-access-log", "--access-log"],
        ),
        ('CMD ["python", "-m", "uvicorn", "app:app"]', ["no --no-access-log"]),
        ('CMD sh -c "exec uvicorn app:app"', ["no --no-access-log"]),
        ('CMD sh -c "exec uvicorn app:app --no-access-log"', []),
        (
            "CMD sh -c \"exec uvicorn app:app --log-level 'debug' --no-access-log\"",
            ["--log-level debug"],
        ),
    ],
)
def test_shell_form_and_wrapped_commands_are_checked(
    dockerfile: str, problems: list[str]
) -> None:
    (command,) = uvicorn_commands(dockerfile)

    assert access_log_problems(command) == problems


def test_a_command_that_is_not_uvicorn_is_ignored() -> None:
    assert uvicorn_commands('CMD ["python", "-m", "cst_accounts.main"]') == []


def test_the_deploy_workflow_changes_only_the_image() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    flags = ("--args", "--command", "env-vars", "--log-level")

    assert "gcloud run services update" in text
    assert [flag for flag in flags if flag in text] == []
