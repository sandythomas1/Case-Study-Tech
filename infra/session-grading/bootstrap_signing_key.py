"""Generate the session state-signing key and add it to Secret Manager unprinted.

Run only after Terraform has created the empty `session-state-signing-key`
secret. The key exists in this process's memory and the HTTPS request body only:
never in a file, an environment variable, Terraform state, a log or git.
Authentication is the current gcloud principal; no service-account key is used.

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


def main() -> None:
    token = subprocess.check_output(
        ["gcloud.cmd", "auth", "print-access-token", "--project=" + PROJECT, "--quiet"],
        text=True,
    ).strip()
    body = {"payload": {"data": base64.b64encode(secrets.token_bytes(KEY_BYTES)).decode()}}
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
