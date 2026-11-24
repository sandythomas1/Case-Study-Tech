"""Test the real provider adapter with SDK/network boundaries replaced."""

from unittest.mock import Mock, patch

import httpx
import pytest

from cst_accounts.domain import DeletionPending, ProfileUnusable, Rejected, Unavailable
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


def test_api_key_travels_in_a_header_never_in_the_url():
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.host == "securetoken.googleapis.com":
            return httpx.Response(
                200,
                json={"id_token": "s", "refresh_token": "r", "expires_in": "3600"},
            )
        return httpx.Response(
            200, json={"idToken": "s", "refreshToken": "r", "expiresIn": "3600"}
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = FirebaseIdentity(
            Mock(), "test-project-key", "https://example.invalid", client
        )
        provider.exchange("google-credential")
        provider.refresh("refresh")
    assert [r.url.host for r in seen] == [
        "identitytoolkit.googleapis.com",
        "securetoken.googleapis.com",
    ]
    for request in seen:
        assert request.headers["x-goog-api-key"] == "test-project-key"
        assert not request.url.query
        assert "test-project-key" not in str(request.url)


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


@pytest.mark.parametrize("message", ["USER_DISABLED", "USER_DISABLED : private-marker"])
def test_disabled_account_maps_to_pending_deletion_without_provider_details(message):
    def handler(request):
        return httpx.Response(400, json={"error": {"message": message}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = FirebaseIdentity(
            Mock(), "test-project-key", "https://example.invalid", client
        )
        for attempt in (
            lambda: provider.exchange("google-credential"),
            lambda: provider.refresh("refresh"),
        ):
            with pytest.raises(DeletionPending) as error:
                attempt()
            assert "private-marker" not in str(error.value)
            assert error.value.__cause__ is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(400, json={"error": {"message": "TOKEN_EXPIRED"}}),
        httpx.Response(400, json={"error": "USER_DISABLED"}),
        httpx.Response(400, text="USER_DISABLED"),
        httpx.Response(403, json={"error": {"message": ["USER_DISABLED"]}}),
    ],
)
def test_other_provider_rejections_stay_rejected(response):
    with httpx.Client(transport=httpx.MockTransport(lambda r: response)) as client:
        provider = FirebaseIdentity(
            Mock(), "test-project-key", "https://example.invalid", client
        )
        with pytest.raises(Rejected):
            provider.refresh("refresh")


GOOGLE = {"uid": "a", "firebase": {"sign_in_provider": "google.com"}}


def test_profile_takes_name_and_email_from_the_verified_token():
    provider = FirebaseIdentity(Mock(), "test-project-key", "https://example.invalid")
    claims = {
        **GOOGLE,
        "name": "Synthetic Student",
        "email": "synthetic@test.invalid",
        "email_verified": True,
    }
    with patch(
        "cst_accounts.firebase.auth.verify_id_token", return_value=claims
    ) as verify:
        profile = provider.profile("signed-token")
    assert verify.call_args.kwargs["check_revoked"] is True
    assert (profile.uid, profile.display_name, profile.email) == (
        "a",
        "Synthetic Student",
        "synthetic@test.invalid",
    )


def test_profile_without_a_name_stores_an_empty_name():
    provider = FirebaseIdentity(Mock(), "test-project-key", "https://example.invalid")
    claims = {**GOOGLE, "email": "s@test.invalid", "email_verified": True}
    with patch("cst_accounts.firebase.auth.verify_id_token", return_value=claims):
        assert provider.profile("signed-token").display_name == ""


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"email": "s@test.invalid"},
        {"email": "s@test.invalid", "email_verified": False},
        {"email": "s@test.invalid", "email_verified": "true"},
        {"email": "no-at-sign", "email_verified": True},
        {"email": 7, "email_verified": True},
        {"email": "a" * 320 + "@x", "email_verified": True},
        {"email": "s@test.invalid", "email_verified": True, "name": 5},
        {"email": "s@test.invalid", "email_verified": True, "name": "n" * 257},
        {"email": "s@test.invalid", "email_verified": 1},
        {"email": "s @test.invalid", "email_verified": True},
        {"email": "s@test.invalid\r\nBcc: x@y", "email_verified": True},
    ],
)
def test_profile_rejects_a_missing_unverified_or_malformed_claim(extra):
    # A stable 403, not 401: signing in again would return the same claims.
    provider = FirebaseIdentity(Mock(), "test-project-key", "https://example.invalid")
    with (
        patch(
            "cst_accounts.firebase.auth.verify_id_token",
            return_value={**GOOGLE, **extra},
        ),
        pytest.raises(ProfileUnusable),
    ):
        provider.profile("signed-token")


@pytest.mark.parametrize(
    "claims",
    [
        {"uid": "a", "firebase": {"sign_in_provider": "password"}},
        {"uid": "bad/path", "firebase": {"sign_in_provider": "google.com"}},
    ],
)
def test_profile_applies_the_same_provider_and_uid_checks_as_verify(claims):
    provider = FirebaseIdentity(Mock(), "test-project-key", "https://example.invalid")
    claims = {**claims, "email": "s@test.invalid", "email_verified": True}
    with (
        patch("cst_accounts.firebase.auth.verify_id_token", return_value=claims),
        pytest.raises(Rejected),
    ):
        provider.profile("signed-token")


def test_profile_outage_is_unavailable_and_hides_the_provider_error():
    provider = FirebaseIdentity(Mock(), "test-project-key", "https://example.invalid")
    with (
        patch(
            "cst_accounts.firebase.auth.verify_id_token",
            side_effect=ConnectionError("synthetic@test.invalid"),
        ),
        pytest.raises(Unavailable) as raised,
    ):
        provider.profile("credential")
    assert raised.value.__cause__ is None


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("Ana Lopez", "Ana Lopez"),
        ("Ana\r\nBcc: x@y", "Ana Bcc: x@y"),
        ("Ana\u202eetouq\u202c", "Anaetouq"),
        ("A\u200bna\u2066\u2069\ufeff", "Ana"),
        ("Cafe\u0301", "Caf\u00e9"),
        ("\u0915\u094d\u200d\u0937", "\u0915\u094d\u200d\u0937"),
        ("  Ana   Lopez \t", "Ana Lopez"),
        ("\x00\x1b[31m", "[31m"),
    ],
)
def test_the_display_name_is_normalized_and_stripped_of_invisible_controls(raw, stored):
    provider = FirebaseIdentity(Mock(), "test-project-key", "https://example.invalid")
    claims = {**GOOGLE, "email": "s@test.invalid", "email_verified": True, "name": raw}
    with patch("cst_accounts.firebase.auth.verify_id_token", return_value=claims):
        assert provider.profile("signed-token").display_name == stored
