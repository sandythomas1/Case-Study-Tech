"""Test the real provider adapter with SDK/network boundaries replaced."""

from unittest.mock import Mock, patch

import httpx
import pytest

from cst_accounts.domain import Rejected, Unavailable
from cst_accounts.firebase import FirebaseIdentity


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"uid": "a", "firebase": {"sign_in_provider": "password"}},
        {"uid": "a", "firebase": {"sign_in_provider": "custom"}},
        {"uid": "bad/path", "firebase": {"sign_in_provider": "google.com"}},
    ],
)
def test_other_providers_and_invalid_claims_are_rejected(claims):
    provider = FirebaseIdentity(Mock(), "test-project-key", "https://example.invalid")
    with patch(
        "cst_accounts.firebase.auth.verify_id_token", return_value=claims
    ) as verify:
        with pytest.raises(Rejected):
            provider.verify("signed-token")
        assert verify.call_args.kwargs["check_revoked"] is True


def test_google_verified_subject_is_used():
    provider = FirebaseIdentity(Mock(), "test-project-key", "https://example.invalid")
    with patch(
        "cst_accounts.firebase.auth.verify_id_token",
        return_value={"uid": "a", "firebase": {"sign_in_provider": "google.com"}},
    ):
        assert provider.verify("signed-token").uid == "a"


def test_provider_network_failure_is_unavailable_not_authorized():
    provider = FirebaseIdentity(Mock(), "test-project-key", "https://example.invalid")
    with (
        patch(
            "cst_accounts.firebase.auth.verify_id_token",
            side_effect=ConnectionError("private-marker"),
        ),
        pytest.raises(Unavailable),
    ):
        provider.verify("credential")


def test_exchange_fixes_provider_and_does_not_accept_client_request_uri():
    def handler(request):
        assert request.url.host == "identitytoolkit.googleapis.com"
        assert b"google.com" in request.content
        assert b"https://example.invalid" in request.content
        return httpx.Response(
            200,
            json={"idToken": "signed", "refreshToken": "refresh", "expiresIn": "3600"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = FirebaseIdentity(
            Mock(), "test-project-key", "https://example.invalid", client
        )
        assert provider.exchange("google-credential").expires_in == 3600


def test_rest_errors_do_not_leak_provider_payloads():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(400, json={"error": {"message": "private-marker"}})
        )
    ) as client:
        provider = FirebaseIdentity(
            Mock(), "test-project-key", "https://example.invalid", client
        )
        with pytest.raises(Rejected) as error:
            provider.refresh("refresh")
        assert "private-marker" not in str(error.value)
