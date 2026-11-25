"""Verifies the forwarded Identity Platform token, copied from accounts (T2).

``_claims`` and ``verify`` are verbatim copies of ``cst_accounts.firebase``.
The session service never exchanges or refreshes tokens, so it holds no API key.
"""

from typing import Any

from firebase_admin import App, auth
from firebase_admin.exceptions import FirebaseError

from .domain import Rejected, Student, Unavailable


class FirebaseIdentity:
    def __init__(self, app: App) -> None:
        self.app = app

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
