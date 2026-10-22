"""Read-only access/CORS smoke checks for the explicit development gateway.

The deletion-route probe has no identity credential and must be rejected before
any mutation. Never add a real student token to this script or its logs.
"""

import urllib.error
import urllib.request

GATEWAY = "https://accounts-7tnmor5w.uc.gateway.dev"
ORIGIN = "https://casestudy-tech-dev-2e03d0.web.app"


def main() -> None:
    checks = [
        ("GET", "/health", {}, None, 200),
        ("GET", "/v1/me", {}, None, 401),
        ("GET", "/v1/scores", {"Authorization": "Bearer invalid"}, None, 401),
        (
            "POST",
            "/v1/account/deletion",
            {"Content-Type": "application/json"},
            b'{"confirmation":"DELETE"}',
            401,
        ),
        (
            "OPTIONS",
            "/v1/scores",
            {
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
            None,
            200,
        ),
        (
            "OPTIONS",
            "/v1/scores",
            {
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
            None,
            400,
        ),
    ]
    for method, path, headers, body, expected in checks:
        request = urllib.request.Request(
            GATEWAY + path, data=body, headers=headers, method=method
        )
        try:
            response = urllib.request.urlopen(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            if response.status != expected:
                raise SystemExit(
                    f"FAIL {method} {path}: HTTP {response.status}, expected {expected}"
                )
            if method == "OPTIONS":
                permission = response.headers.get("Access-Control-Allow-Origin")
                if headers["Origin"] == ORIGIN and permission != ORIGIN:
                    raise SystemExit("FAIL: allowlisted preflight permission missing.")
                if headers["Origin"] != ORIGIN and permission is not None:
                    raise SystemExit("FAIL: untrusted origin received CORS permission.")
        print(f"PASS {method} {path}: HTTP {expected}")


if __name__ == "__main__":
    main()
