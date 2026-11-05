"""Transfer the restricted API key into Secret Manager without printing it.

Run only after Terraform has created the named key and secret. Authentication is
the current gcloud principal; no downloaded service-account key is required.
"""

import base64
import json
import subprocess
import urllib.error
import urllib.request

PROJECT = "casestudy-tech-dev-2e03d0"


def main() -> None:
    token = subprocess.check_output(
        ["gcloud.cmd", "auth", "print-access-token", "--project=" + PROJECT, "--quiet"],
        text=True,
    ).strip()
    headers = {
        "Authorization": "Bearer " + token,
        "x-goog-user-project": PROJECT,
        "Content-Type": "application/json",
    }

    def request(url: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode()
        with urllib.request.urlopen(
            urllib.request.Request(url, data=data, headers=headers), timeout=30
        ) as response:
            return json.load(response)

    key = request(
        f"https://apikeys.googleapis.com/v2/projects/{PROJECT}/locations/global/keys/accounts-identity/keyString"
    )["keyString"]
    request(
        f"https://secretmanager.googleapis.com/v1/projects/{PROJECT}/secrets/accounts-identity-api-key:addVersion",
        {"payload": {"data": base64.b64encode(key.encode()).decode()}},
    )
    print("Restricted Identity Platform key transferred to Secret Manager.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        # Never print response bodies, request headers, API-key URLs or values.
        raise SystemExit(f"Secret bootstrap failed: HTTP {error.code}") from None
