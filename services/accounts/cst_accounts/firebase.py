"""Real Identity Platform adapter. API keys stay on this server."""

import logging
import unicodedata
from typing import Any
from urllib.parse import urlencode

import httpx
from firebase_admin import App, auth
from firebase_admin.exceptions import FirebaseError
from pydantic import ValidationError

from .domain import (
    DeletionPending,
    Profile,
    ProfileUnusable,
    Rejected,
    Student,
    Tokens,
    Unavailable,
)

# RFC 5321 path limit and a generous display-name bound. Longer claims are
# rejected rather than truncated, so a stored value is always the real one.
MAX_EMAIL = 320
MAX_DISPLAY_NAME = 256
# Joiners shape Indic scripts and emoji, so they stay. Every other control or
# format character (bidi overrides, zero-width space, BOM) is removed.
_KEPT_FORMAT = {"\u200c", "\u200d"}


def display_name(raw: str) -> str:
    """NFC-normalize a name, drop invisible format characters, fold controls.

    Line breaks and other controls become spaces, so "A<CR><LF>B" is "A B".
    """
    normalized = unicodedata.normalize("NFC", raw)
    kept = []
    for c in normalized:
        category = unicodedata.category(c)
        if category in {"Cc", "Zl", "Zp"}:
            kept.append(" ")
        elif category != "Cf" or c in _KEPT_FORMAT:
            kept.append(c)
    return " ".join("".join(kept).split())


def _reports_disabled(response: httpx.Response) -> bool:
    """True when signInWithIdp or securetoken refused a disabled account.

    Deletion is the only path in this system that disables users, so a disabled
    account always means a pending deletion. Only the error code is read; the
    provider's message text never leaves this function.
    """
    try:
        error = response.json().get("error")
        message = error.get("message") if isinstance(error, dict) else None
    except (ValueError, AttributeError):
        return False
    if not isinstance(message, str):
        return False
    return message.split(":")[0].strip() == "USER_DISABLED"


class FirebaseIdentity:
    def __init__(
        self,
        app: App,
        api_key: str,
        request_uri: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.app, self.api_key, self.request_uri = app, api_key, request_uri
        self.client = client or httpx.Client(timeout=10, follow_redirects=False)
        # The API key travels in a header, so request URLs carry no secret. HTTP
        # client INFO logs stay off as defense in depth; own logs hold counts only.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    def _claims(self, token: str) -> dict[str, Any]:
        """Verified claims of a non-revoked Google ID token, or Rejected."""
        try:
            claims = auth.verify_id_token(token, app=self.app, check_revoked=True)
        except (
            ValueError,
            auth.InvalidIdTokenError,
            auth.UserDisabledError,
            auth.UserNotFoundError,
        ):
            raise Rejected() from None
        except (FirebaseError, OSError):
            # SDK transport/certificate failures cannot authorize a caller.
            raise Unavailable() from None
        uid = claims.get("uid")
        if not isinstance(uid, str) or not uid or len(uid) > 128 or "/" in uid:
            raise Rejected()
        firebase_claims = claims.get("firebase")
        if (
            not isinstance(firebase_claims, dict)
            or firebase_claims.get("sign_in_provider") != "google.com"
        ):
            raise Rejected()
        return claims

    def verify(self, token: str) -> Student:
        return Student(uid=self._claims(token)["uid"])

    def profile(self, token: str) -> Profile:
        """The verified name and Google email, never values a client supplied.

        The name is free text that #73, #74 and #76 will show the owner, so it is
        normalized and stripped of control and invisible direction characters.
        Consumers must still escape it, and never put it in a mail header or URL.
        """
        claims = self._claims(token)
        email, name = claims.get("email"), claims.get("name", "")
        if (
            not isinstance(email, str)
            or not 3 <= len(email) <= MAX_EMAIL
            or "@" not in email
            or any(c.isspace() or not c.isprintable() for c in email)
            or claims.get("email_verified") is not True
        ):
            raise ProfileUnusable()
        if not isinstance(name, str):
            raise ProfileUnusable()
        name = display_name(name)
        if len(name) > MAX_DISPLAY_NAME:
            raise ProfileUnusable()
        return Profile(uid=claims["uid"], display_name=name, email=email)

    def _tokens(self, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self.client.post(
                url, headers={"X-Goog-Api-Key": self.api_key}, **kwargs
            )
            if response.status_code in {400, 401, 403}:
                if _reports_disabled(response):
                    raise DeletionPending()
                raise Rejected()
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise Unavailable()
            return payload
        except (Rejected, DeletionPending):
            raise
        except (httpx.HTTPError, ValueError, TypeError):
            raise Unavailable() from None

    def exchange(self, credential: str) -> Tokens:
        data = self._tokens(
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp",
            json={
                "postBody": urlencode(
                    {"id_token": credential, "providerId": "google.com"}
                ),
                "requestUri": self.request_uri,
                "returnSecureToken": True,
            },
        )
        try:
            return Tokens(
                id_token=data["idToken"],
                refresh_token=data["refreshToken"],
                expires_in=int(data["expiresIn"]),
            )
        except (KeyError, ValueError, TypeError, ValidationError):
            raise Unavailable() from None

    def refresh(self, refresh_token: str) -> Tokens:
        data = self._tokens(
            "https://securetoken.googleapis.com/v1/token",
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        )
        try:
            return Tokens(
                id_token=data["id_token"],
                refresh_token=data["refresh_token"],
                expires_in=int(data["expires_in"]),
            )
        except (KeyError, ValueError, TypeError, ValidationError):
            raise Unavailable() from None

    def disable(self, uid: str) -> None:
        try:
            auth.update_user(uid, disabled=True, app=self.app)
            auth.revoke_refresh_tokens(uid, app=self.app)
        except auth.UserNotFoundError:
            pass
        except (FirebaseError, OSError, ValueError):
            raise Unavailable() from None

    def delete(self, uid: str) -> None:
        try:
            auth.delete_user(uid, app=self.app)
        except auth.UserNotFoundError:
            pass
        except (FirebaseError, OSError, ValueError):
            raise Unavailable() from None
