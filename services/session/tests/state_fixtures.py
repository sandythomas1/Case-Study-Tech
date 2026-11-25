"""Shared builders for signed-state tests. Synthetic data only."""

import base64
import hashlib
import hmac
import json
from typing import Any

from cst_session.state import SessionState, StateTurn

KEY = bytes(range(32))
OTHER_KEY = bytes(range(1, 33))
SESSION_ID = "0b8f4a52-6c1e-4d9b-9a3f-2f6e8c1d7a40"
OWNER = "synthUid001"
STARTED_AT_MS = 1_790_000_000_000


def state(**changes: Any) -> SessionState:
    fields: dict[str, Any] = {
        "session_id": SESSION_ID,
        "owner_uid": OWNER,
        "scenario_id": "routine_intake",
        "scenario_version": "1.0.0",
        "started_at_ms": STARTED_AT_MS,
        "modality": "text",
        "crisis_opt_in": False,
        "save_transcript": True,
        "conduct_warnings": 0,
        "turns": [
            StateTurn(speaker="student", text="Hello, what brings you in?", at_ms=0),
            StateTurn(
                speaker="client", text="School has been a lot lately.", at_ms=900
            ),
        ],
    }
    fields.update(changes)
    return SessionState(**fields)


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def tag_for(payload_b64: str, key: bytes = KEY) -> str:
    """The v1 tag, computed independently of the codec to pin the format."""
    message = b"cst.session_state.v1." + payload_b64.encode("ascii")
    return b64(hmac.new(key, message, hashlib.sha256).digest())


def forge(payload: bytes, key: bytes = KEY) -> str:
    """A token over arbitrary payload bytes with a valid MAC for ``key``."""
    payload_b64 = b64(payload)
    return f"v1.{payload_b64}.{tag_for(payload_b64, key)}"


def payload_json(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = state().model_dump(mode="json")
    data.update(changes)
    return data


def encode_json(data: object) -> bytes:
    return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
