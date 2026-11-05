"""Real Identity Platform adapter. API keys stay on this server."""

import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from firebase_admin import App, auth
from firebase_admin.exceptions import FirebaseError
from pydantic import ValidationError

from .domain import Rejected, Student, Tokens, Unavailable


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
        # HTTP client INFO logs include query API keys. Own logs contain counts only.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    def verify(self, token: str) -> Student:
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
        return Student(uid=uid)

    def _tokens(self, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self.client.post(url, params={"key": self.api_key}, **kwargs)
            if response.status_code in {400, 401, 403}:
                raise Rejected()
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise Unavailable()
            return payload
        except Rejected:
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
