"""QA acceptance tests for #31: the real app wired to the real persona adapter.

The other suites test each layer with a fake persona port. These tests close
the gap between them: the real ``create_app`` and ``Sessions``, the real
``AgentPlatformPersona`` over ``httpx.MockTransport`` (no network, a synthetic
token), the real ``UnavailableGrader`` behind a spy, and the real
``FirestoreAccess`` over a read-only fake Firestore client. Identity is a fake
verifier with synthetic UIDs.

- AC1: the client replies within each selected scenario.
- AC2 and owner decision L2-1: the time limit, manual end and what a stale
  pre-end state can still do.
- AC3: the access store only reads.
- AC4: every adapter failure gives 503 with no state, and no ending is scored.
- Carry-over #72: the copied guard with the real ``FirebaseIdentity`` and
  ``FirestoreAccess`` fails closed (only the Google signature check is stubbed).
- Carry-over #64 for #43: the running app has no speech wiring, and voice
  is refused.
"""

import asyncio
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from firebase_admin import auth as firebase_auth
from firebase_admin import exceptions as firebase_exceptions
from google.api_core.exceptions import ServiceUnavailable

from cst_session.api import create_app
from cst_session.grading import UnavailableGrader
from cst_session.handoff import CompletedSession
from cst_session.identity.firebase import FirebaseIdentity
from cst_session.identity.store import FirestoreAccess
from cst_session.lifecycle import END_GRACE_MS, Sessions
from cst_session.persona.agent_platform import AgentPlatformPersona, model_copy_text
from cst_session.scenarios import SCENARIO_IDS, load_catalogue
from cst_session.scenarios.prompts import load_prompts
from cst_session.state import StateCodec
from tests.api_fakes import TOKEN, FakeAuth, FakeStore
from tests.lifecycle_fakes import LIMIT_MS, OWNER, FakeClock
from tests.state_fixtures import KEY

SERVICE_ROOT = Path(__file__).resolve().parents[1]
AUTH = {"Authorization": f"Bearer {TOKEN}"}
PROJECT = "cst-synthetic-01"
MODEL = "gemini-3.8-flash"
EXPECTED_URL = (
    "https://aiplatform.us.rep.googleapis.com/v1/projects/cst-synthetic-01"
    "/locations/us/publishers/google/models/gemini-3.8-flash:generateContent"
)
SCORE_KEYS = {"score", "scores", "overall", "categories", "report", "graded"}


class SyntheticToken:
    def token(self) -> str:
        return "synthetic-access-token"


def gemini_reply(text: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": text}]},
                    "finishReason": "STOP",
                }
            ]
        },
    )


@dataclass
class SpyGrader:
    """The real interim grader, recording what it is handed."""

    received: list[CompletedSession] = field(default_factory=list)

    async def submit(self, session: CompletedSession) -> None:
        self.received.append(session)
        await UnavailableGrader().submit(session)


@dataclass
class Wired:
    client: TestClient
    clock: FakeClock
    grader: SpyGrader
    requests: list[httpx.Request]
    codec: StateCodec

    def start(self, scenario_id: str = "routine_intake", **body: Any) -> Any:
        payload = {
            "scenario_id": scenario_id,
            "crisis_opt_in": scenario_id == "crisis_risk",
            "save_transcript": False,
            "modality": "text",
            **body,
        }
        return self.client.post("/v1/sessions", json=payload, headers=AUTH)

    def turn(self, state: str, text: str = "Hi, what brings you in today?") -> Any:
        return self.client.post(
            "/v1/sessions/turns", json={"state": state, "text": text}, headers=AUTH
        )

    def end(self, state: str) -> Any:
        return self.client.post("/v1/sessions/end", json={"state": state}, headers=AUTH)

    def sent(self, index: int = -1) -> dict[str, Any]:
        body: dict[str, Any] = json.loads(self.requests[index].content)
        return body


Respond = Callable[[httpx.Request], Any]


def wired(
    respond: Respond | None = None,
    *,
    deadline_s: float = 20,
    store: Any = None,
    auth: Any = None,
) -> Wired:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if respond is None:
            return gemini_reply("Honestly, work has been a lot lately.")
        result = respond(request)
        if asyncio.iscoroutine(result):
            result = await result
        assert isinstance(result, httpx.Response)
        return result

    persona = AgentPlatformPersona(
        project=PROJECT,
        location="us",
        model=MODEL,
        tokens=SyntheticToken(),
        transport=httpx.MockTransport(handler),
        deadline_s=deadline_s,
    )
    clock = FakeClock()
    grader = SpyGrader()
    codec = StateCodec(KEY)
    sessions = Sessions(
        catalogue=load_catalogue(),
        prompts=load_prompts(),
        codec=codec,
        persona=persona,
        grader=grader,
        clock=clock,
    )
    app = create_app(
        auth if auth is not None else FakeAuth(),
        store if store is not None else FakeStore(),
        sessions,
    )
    client = TestClient(app, raise_server_exceptions=False)
    return Wired(client, clock, grader, requests, codec)


# --- AC1: the simulated client responds within the selected scenario -----------


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_ac1_the_client_replies_within_each_selected_scenario(scenario_id: str) -> None:
    target = wired()
    started = target.start(scenario_id)
    assert started.status_code == 200

    target.clock.now += 2_000
    turned = target.turn(started.json()["state"], "Hi, I'm the counselor today.")

    assert turned.status_code == 200
    assert turned.json()["reply"] == "Honestly, work has been a lot lately."
    assert str(target.requests[0].url) == EXPECTED_URL
    sent = target.sent()
    prompt = load_prompts().for_scenario(scenario_id)
    assert sent["systemInstruction"] == {"parts": [{"text": model_copy_text(prompt)}]}
    assert sent["contents"] == [
        {"role": "user", "parts": [{"text": "Hi, I'm the counselor today."}]}
    ]
    signed = target.codec.verify(turned.json()["state"])
    assert signed.scenario_id == scenario_id
    assert [(t.speaker, t.text) for t in signed.turns] == [
        ("student", "Hi, I'm the counselor today."),
        ("client", "Honestly, work has been a lot lately."),
    ]


def test_ac1_each_scenario_sends_its_own_prompt_and_no_other() -> None:
    prompts = load_prompts()
    sent: dict[str, str] = {}
    for scenario_id in SCENARIO_IDS:
        target = wired()
        target.turn(target.start(scenario_id).json()["state"])
        sent[scenario_id] = target.sent()["systemInstruction"]["parts"][0]["text"]
    assert len(set(sent.values())) == len(SCENARIO_IDS)
    for scenario_id, text in sent.items():
        assert text == model_copy_text(prompts.for_scenario(scenario_id))


def test_ac1_the_second_turn_carries_the_ordered_history() -> None:
    target = wired()
    first = target.turn(target.start().json()["state"], "What brings you in?")
    target.clock.now += 1_000
    second = target.turn(first.json()["state"], "How long has that gone on?")
    assert second.status_code == 200
    assert [c["role"] for c in target.sent()["contents"]] == ["user", "model", "user"]
    assert target.sent()["contents"][1]["parts"][0]["text"] == (
        "Honestly, work has been a lot lately."
    )


# --- AC2 and L2-1: the time limit, manual end and stale pre-end states ------------


def test_ac2_a_session_at_the_limit_rejects_turns_and_ends_by_time_limit() -> None:
    target = wired()
    state = target.turn(target.start().json()["state"]).json()["state"]
    target.clock.now += LIMIT_MS
    refused = target.turn(state, "One more thing.")
    assert (refused.status_code, refused.json()) == (
        409,
        {"detail": "session_time_limit"},
    )
    assert len(target.requests) == 1
    ended = target.end(state)
    assert ended.json() == {
        "outcome": "unscored",
        "reason": "grading_unavailable",
        "ended_by": "time_limit",
    }
    target.clock.now += END_GRACE_MS
    assert target.end(state).json() == {"detail": "session_expired"}
    assert target.turn(state).json() == {"detail": "session_time_limit"}


def test_ac2_manual_end_returns_no_state_to_continue_from() -> None:
    target = wired()
    state = target.turn(target.start().json()["state"]).json()["state"]
    ended = target.end(state)
    assert ended.status_code == 200
    assert ended.json()["ended_by"] == "student"
    assert set(ended.json()) == {"outcome", "reason", "ended_by"}


def test_l2_1_a_pre_end_state_keeps_working_only_until_the_limit_under_ad_2() -> None:
    """Owner decision L2-1 (2026-11-25): accepted as an AD-2 risk.

    The service is stateless, so it cannot know a session was ended. A client
    that kept the state it sent to end can still take turns until L and end
    again until L + G. #68's create-only write keyed on session_id blocks a
    second score. This test pins that behavior so a change to it is deliberate.
    """
    target = wired()
    pre_end = target.turn(target.start().json()["state"]).json()["state"]
    assert target.end(pre_end).status_code == 200

    target.clock.now += 1_000
    replayed = target.turn(pre_end, "Still here?")
    assert replayed.status_code == 200
    again = target.end(pre_end)
    assert again.status_code == 200
    assert again.json()["outcome"] == "unscored"
    sessions = {s.session_id for s in target.grader.received}
    assert len(sessions) == 1 and len(target.grader.received) == 2

    target.clock.now += LIMIT_MS
    assert target.turn(pre_end).json() == {"detail": "session_time_limit"}
    assert target.turn(replayed.json()["state"]).json() == {
        "detail": "session_time_limit"
    }
    target.clock.now += END_GRACE_MS
    assert target.end(pre_end).json() == {"detail": "session_expired"}


# --- AC3: the access store only reads ---------------------------------------------


class ReadOnlyDocument:
    def __init__(self, log: list[str], path: str, data: dict[str, Any] | None) -> None:
        self._log, self._path, self._data = log, path, data

    def get(self) -> Any:
        self._log.append(f"get {self._path}")
        data = self._data

        class Snapshot:
            exists = data is not None

            def to_dict(self) -> dict[str, Any] | None:
                return data

        return Snapshot()

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"write-capable call {name} on {self._path}")


class ReadOnlyFirestore:
    """A Firestore client that allows only collection(...).document(...).get()."""

    def __init__(self, docs: dict[str, dict[str, Any]]) -> None:
        self.docs = docs
        self.log: list[str] = []

    def collection(self, name: str) -> Any:
        outer = self

        class Collection:
            def document(self, doc_id: str) -> ReadOnlyDocument:
                path = f"{name}/{doc_id}"
                return ReadOnlyDocument(outer.log, path, outer.docs.get(path))

            def __getattr__(self, attr: str) -> Any:
                raise AssertionError(f"collection call {attr} on {name}")

        return Collection()

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"client call {name}")


def test_ac3_a_whole_session_makes_only_point_reads_on_the_real_access_store() -> None:
    client = ReadOnlyFirestore({f"access/{OWNER}": {"state": "approved", "version": 2}})
    target = wired(store=FirestoreAccess(client))  # type: ignore[arg-type]
    started = target.start()
    assert started.status_code == 200
    turned = target.turn(started.json()["state"], "Content that must not be stored.")
    assert turned.status_code == 200
    assert target.end(turned.json()["state"]).status_code == 200
    assert client.log == [
        f"{op}{OWNER}"
        for _ in range(3)
        for op in ("get account_deletions/", "get access/")
    ]


def test_ac3_the_real_access_store_refuses_a_pending_account() -> None:
    client = ReadOnlyFirestore({f"access/{OWNER}": {"state": "pending", "version": 1}})
    target = wired(store=FirestoreAccess(client))  # type: ignore[arg-type]
    response = target.start()
    assert (response.status_code, response.json()) == (
        403,
        {"detail": "access_not_approved"},
    )


# --- AC4: a model failure produces an unscored ending ---------------------------


async def _too_slow(_: httpx.Request) -> httpx.Response:
    await asyncio.sleep(2)
    return gemini_reply("late")


def _raise(error: Exception) -> Respond:
    def respond(_: httpx.Request) -> httpx.Response:
        raise error

    return respond


FAILURES: dict[str, tuple[Respond, str]] = {
    "deadline": (_too_slow, "persona_timeout"),
    "read_timeout": (_raise(httpx.ReadTimeout("synthetic")), "persona_timeout"),
    "connect_error": (_raise(httpx.ConnectError("synthetic")), "persona_unreachable"),
    "http_500": (lambda _: httpx.Response(500, text="upstream"), "persona_http_error"),
    "http_429": (lambda _: httpx.Response(429), "persona_http_error"),
    "redirect": (
        lambda _: httpx.Response(302, headers={"Location": "https://example.test"}),
        "persona_http_error",
    ),
    "http_403": (lambda _: httpx.Response(403), "persona_auth"),
    "bad_json": (
        lambda _: httpx.Response(200, content=b"{not json"),
        "persona_bad_response",
    ),
    "blocked": (
        lambda _: httpx.Response(
            200, json={"promptFeedback": {"blockReason": "SAFETY"}}
        ),
        "persona_blocked",
    ),
    "function_call": (
        lambda _: httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"functionCall": {"name": "x"}}]},
                        "finishReason": "STOP",
                    }
                ]
            },
        ),
        "persona_bad_reply",
    ),
    "empty_reply": (lambda _: gemini_reply("   "), "persona_bad_reply"),
}


@pytest.mark.parametrize("case", sorted(FAILURES))
def test_ac4_every_model_failure_is_503_with_no_state_and_no_grading(
    case: str, capsys: pytest.CaptureFixture[str]
) -> None:
    respond, code = FAILURES[case]
    target = wired(respond, deadline_s=0.2)
    state = target.start().json()["state"]
    capsys.readouterr()

    response = target.turn(state, "Synthetic student turn.")

    assert response.status_code == 503
    assert response.json() == {"detail": "persona_unavailable"}
    assert "state" not in response.text and "reply" not in response.text
    assert target.grader.received == []
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    failed = [e for e in events if e.get("message") == "persona_failed"]
    assert len(failed) == 1 and failed[0]["error_code"] == code
    assert "Synthetic student turn" not in json.dumps(events)


def test_ac4_no_ending_carries_a_score_even_after_a_full_session() -> None:
    target = wired()
    state = target.start().json()["state"]
    for number in range(3):
        target.clock.now += 1_000
        state = target.turn(state, f"Synthetic turn {number}.").json()["state"]
    ended = target.end(state)
    assert ended.json() == {
        "outcome": "unscored",
        "reason": "grading_unavailable",
        "ended_by": "student",
    }
    assert not SCORE_KEYS & set(ended.json())
    assert len(target.grader.received) == 1
    assert target.grader.received[0].status == "completed"


def test_ac4_a_failed_turn_is_never_signed_into_any_state() -> None:
    target = wired(lambda _: httpx.Response(500))
    state = target.start().json()["state"]
    assert target.turn(state, "Synthetic student turn.").status_code == 503
    # The only state the client holds is the one from before the failure.
    assert target.codec.verify(state).turns == []
    assert target.end(state).json()["reason"] == "empty_session"
    assert target.grader.received == []


# --- carry-over #64 for #43: no speech wiring, and voice is refused ---------------


def test_carryover_the_running_app_imports_no_speech_code() -> None:
    probe = (
        "import sys, cst_session.main\n"
        "loaded = sorted(m for m in sys.modules if m.startswith('cst_session.speech'))\n"
        "print(loaded)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=SERVICE_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "[]"


def test_carryover_a_voice_start_fails_closed() -> None:
    target = wired()
    response = target.start(modality="voice")
    assert (response.status_code, response.json()) == (
        400,
        {"detail": "invalid_request"},
    )
    assert target.requests == []


def test_carryover_no_route_takes_audio_or_a_websocket() -> None:
    app = wired().client.app
    paths = {getattr(route, "path", "") for route in app.routes}  # type: ignore[attr-defined]
    assert paths == {
        "/health",
        "/v1/sessions",
        "/v1/sessions/turns",
        "/v1/sessions/end",
    }


# --- carry-over #72: the copied guard with the real identity adapters -----------


def google_claims(uid: str = OWNER, provider: str = "google.com") -> dict[str, Any]:
    return {"uid": uid, "firebase": {"sign_in_provider": provider}}


def real_guard(
    verify: Any, docs: dict[str, dict[str, Any]] | None = None
) -> tuple[Wired, Any]:
    approved = {f"access/{OWNER}": {"state": "approved", "version": 2}}
    client = ReadOnlyFirestore(approved if docs is None else docs)
    target = wired(
        store=FirestoreAccess(client),  # type: ignore[arg-type]
        auth=FirebaseIdentity(Mock()),
    )
    patcher = patch(
        "cst_session.identity.firebase.auth.verify_id_token", side_effect=verify
    )
    return target, patcher


def test_carryover_the_real_guard_admits_an_approved_google_account() -> None:
    target, patcher = real_guard(lambda token, **_: google_claims())
    with patcher as verify:
        response = target.start()
    assert response.status_code == 200
    assert verify.call_args.kwargs["check_revoked"] is True


@pytest.mark.parametrize(
    "error",
    [
        firebase_auth.InvalidIdTokenError("synthetic"),
        firebase_auth.ExpiredIdTokenError("synthetic", None),
        firebase_auth.RevokedIdTokenError("synthetic"),
        firebase_auth.UserDisabledError("synthetic"),
        ValueError("synthetic"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_carryover_the_real_guard_rejects_a_bad_token_with_401(
    error: Exception,
) -> None:
    def verify(token: str, **_: Any) -> Any:
        raise error

    target, patcher = real_guard(verify)
    with patcher:
        response = target.start()
    assert (response.status_code, response.json()) == (
        401,
        {"detail": "Sign in again."},
    )


@pytest.mark.parametrize(
    "claims",
    [
        google_claims(provider="password"),
        google_claims(provider="anonymous"),
        google_claims(uid=""),
        google_claims(uid="a/b"),
        google_claims(uid="x" * 129),
        {"uid": OWNER},
    ],
)
def test_carryover_the_real_guard_rejects_non_google_or_bad_uid_claims(
    claims: dict[str, Any],
) -> None:
    target, patcher = real_guard(lambda token, **_: claims)
    with patcher:
        response = target.start()
    assert response.status_code == 401
    assert target.requests == []


def test_carryover_an_identity_outage_is_503_never_approval() -> None:
    def verify(token: str, **_: Any) -> Any:
        raise firebase_exceptions.UnavailableError("synthetic")

    target, patcher = real_guard(verify)
    with patcher:
        response = target.start()
    assert response.status_code == 503


@pytest.mark.parametrize(
    "record",
    [{"state": "approved "}, {"state": "APPROVED"}, {"state": None}, {}, {"x": 1}],
)
def test_carryover_a_malformed_access_record_fails_closed(
    record: dict[str, Any],
) -> None:
    target, patcher = real_guard(
        lambda token, **_: google_claims(), {f"access/{OWNER}": record}
    )
    with patcher:
        response = target.start()
    assert response.status_code == 503
    assert target.requests == []


@pytest.mark.parametrize(
    ("docs", "detail"),
    [
        ({}, "access_not_approved"),
        ({f"access/{OWNER}": {"state": "denied"}}, "access_not_approved"),
        (
            {
                f"access/{OWNER}": {"state": "approved"},
                f"account_deletions/{OWNER}": {"requested": True},
            },
            "account_deletion_pending",
        ),
    ],
)
def test_carryover_the_real_store_refuses_missing_denied_and_deleting_accounts(
    docs: dict[str, dict[str, Any]], detail: str
) -> None:
    target, patcher = real_guard(lambda token, **_: google_claims(), docs)
    with patcher:
        response = target.start()
    assert (response.status_code, response.json()) == (403, {"detail": detail})


def test_carryover_a_firestore_outage_is_503_never_approval() -> None:
    class Outage(ReadOnlyFirestore):
        def collection(self, name: str) -> Any:
            raise ServiceUnavailable("synthetic")

    target = wired(
        store=FirestoreAccess(Outage({})),  # type: ignore[arg-type]
        auth=FirebaseIdentity(Mock()),
    )
    with patch(
        "cst_session.identity.firebase.auth.verify_id_token",
        side_effect=lambda token, **_: google_claims(),
    ):
        response = target.start()
    assert response.status_code == 503
