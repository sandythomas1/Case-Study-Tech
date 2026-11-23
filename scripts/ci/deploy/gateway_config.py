"""Render the shared API Gateway config and decide whether it must roll (#105, AD-4).

`render` reproduces Terraform's templatefile() for the constructs infra/gateway.yaml.template
uses: ${NAME} interpolation, and `%{ if NAME != "" ~}` ... `%{ endif ~}` on lines of their own,
which Terraform drops whole (checked against `terraform console` on 2026-11-22). Any other
template construct fails closed, so the deploy never ships a config Terraform would not render.

`changed` compares the rendered config with the live one after normalizing line endings, so a
config applied from a Windows checkout (CRLF) does not count as a change. Standard library only.

Usage (from the repository root):
    python scripts/ci/deploy/gateway_config.py render --template T --out F \
        --project-id P --accounts-url A --session-url S
    python scripts/ci/deploy/gateway_config.py changed --rendered F --live-json L
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
import sys
from pathlib import Path
from typing import Any

INTERPOLATION = re.compile(r"\$\{([A-Z_]+)\}")
IF_LINE = re.compile(r'^%\{ if ([A-Z_]+) != "" ~\}$')
ENDIF_LINE = "%{ endif ~}"
PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
RUN_URL = re.compile(r"^https://[a-z0-9-]+\.a\.run\.app$")


class TemplateError(ValueError):
    """The template uses a construct this renderer does not reproduce, or a value is unsafe."""


def render(template: str, values: dict[str, str]) -> str:
    text = template.replace("\r\n", "\n")
    out: list[str] = []
    skipping = False
    in_block = False
    for line in text.split("\n"):
        match = IF_LINE.fullmatch(line)
        if match:
            if in_block:
                raise TemplateError("nested if blocks are not supported")
            name = match.group(1)
            if name not in values:
                raise TemplateError(f"if block uses unknown variable {name}")
            in_block = True
            skipping = values[name] == ""
            continue
        if line == ENDIF_LINE:
            if not in_block:
                raise TemplateError("endif without if")
            in_block = False
            skipping = False
            continue
        if "%{" in line or "$${" in line or "%%{" in line:
            raise TemplateError("unsupported template directive or escape")
        if not skipping:
            out.append(_interpolate(line, values))
    if in_block:
        raise TemplateError("if block is never closed")
    return "\n".join(out)


def _interpolate(line: str, values: dict[str, str]) -> str:
    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise TemplateError(f"unknown variable {name}")
        return values[name]

    result = INTERPOLATION.sub(substitute, line)
    if "${" in result:
        raise TemplateError("unsupported interpolation")
    return result


def template_values(project_id: str, accounts_url: str, session_url: str) -> dict[str, str]:
    if not PROJECT_ID.fullmatch(project_id):
        raise TemplateError("project id is malformed")
    if not RUN_URL.fullmatch(accounts_url):
        raise TemplateError("accounts URL must be a Cloud Run URL")
    if session_url != "" and not RUN_URL.fullmatch(session_url):
        raise TemplateError("session URL must be empty or a Cloud Run URL")
    return {
        "PROJECT_ID": project_id,
        "ACCOUNTS_SERVICE_URL": accounts_url,
        "SESSION_SERVICE_URL": session_url,
    }


def live_document(api_config: Any) -> str:
    """Return the one OpenAPI document of a `gcloud api-gateway api-configs describe
    --view=FULL --format=json` result."""
    try:
        documents = api_config["openapiDocuments"]
        if len(documents) != 1:
            raise TemplateError("the live config must hold exactly one OpenAPI document")
        encoded = documents[0]["document"]["contents"]
        return base64.b64decode(encoded, validate=True).decode("utf-8")
    except (KeyError, IndexError, TypeError, binascii.Error, UnicodeDecodeError):
        raise TemplateError("the live config has no readable OpenAPI document") from None


def changed(rendered: str, live: str) -> bool:
    return _normalize(rendered) != _normalize(live)


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").rstrip("\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    render_cmd = commands.add_parser("render")
    render_cmd.add_argument("--template", type=Path, required=True)
    render_cmd.add_argument("--out", type=Path, required=True)
    render_cmd.add_argument("--project-id", required=True)
    render_cmd.add_argument("--accounts-url", required=True)
    render_cmd.add_argument("--session-url", required=True)
    changed_cmd = commands.add_parser("changed")
    changed_cmd.add_argument("--rendered", type=Path, required=True)
    changed_cmd.add_argument("--live-json", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    try:
        if args.command == "render":
            values = template_values(args.project_id, args.accounts_url, args.session_url)
            text = render(args.template.read_text(encoding="utf-8"), values)
            args.out.write_text(text, encoding="utf-8", newline="\n")
            print("Rendered the gateway config.")
        else:
            live = live_document(json.loads(args.live_json.read_text(encoding="utf-8")))
            result = changed(args.rendered.read_text(encoding="utf-8"), live)
            print(f"changed={'true' if result else 'false'}")
    except (TemplateError, OSError, json.JSONDecodeError) as error:
        print(f"::error::Gateway config: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
