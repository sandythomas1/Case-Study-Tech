"""Generate the session state-signing key and add it to Secret Manager unprinted.

Run only after Terraform has created the empty `session-state-signing-key`
secret. The key exists in this process's memory and the HTTPS request body only:
never in a file, an environment variable, Terraform state, a log or git.
Authentication is the current gcloud principal; no service-account key is used.

The secret holds the key as text: 32 random bytes in unpadded base64url, 43
characters. Cloud Run injects it as an environment variable, which cannot carry
arbitrary bytes, and the session service decodes it strictly back to exactly 32
bytes (L2-2, owner decided 2026-11-25). A version stored as raw bytes by an
earlier run fails that check, so re-run this before turning key injection on.

Each run adds a new version and the session service reads `latest`, so rotating
invalidates every signed state in flight (those sessions take the lost-content
path, ARCHITECTURE flow 8). Run it for initialization or intentional rotation.
"""

import base64
import json
import secrets
import subprocess
import urllib.error
import urllib.request

PROJECT = "casestudy-tech-dev-2e03d0"
SECRET = "session-state-signing-key"
KEY_BYTES = 32  # 256-bit HMAC key


def new_key_text() -> bytes:
    """A fresh 256-bit key as 43 ASCII characters of unpadded base64url."""
    return base64.urlsafe_b64encode(secrets.token_bytes(KEY_BYTES)).rstrip(b"=")


def add_version_body(key_text: bytes) -> dict[str, dict[str, str]]:
    """The addVersion request body. The API wants the secret value base64-encoded."""
    return {"payload": {"data": base64.b64encode(key_text).decode("ascii")}}


def main() -> None:
    token = subprocess.check_output(
        ["gcloud.cmd", "auth", "print-access-token", "--project=" + PROJECT, "--quiet"],
        text=True,
    ).strip()
    body = add_version_body(new_key_text())
    request = urllib.request.Request(
        f"https://secretmanager.googleapis.com/v1/projects/{PROJECT}/secrets/{SECRET}:addVersion",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "x-goog-user-project": PROJECT,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        version = json.load(response)["name"].rsplit("/", 1)[-1]
    print(f"State-signing key version {version} added to Secret Manager.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        # Never print response bodies, request headers or values.
        raise SystemExit(f"Signing-key bootstrap failed: HTTP {error.code}") from None
