"""Fakes for the HTTP tests: a token verifier, an access store and an app client.

Tokens and UIDs are synthetic. The store records every read, so tests can show
the guard only does point reads by the verified UID.
"""

from dataclasses import dataclass, field
from typing import Any

from fastapi.testclient import TestClient

from cst_session.api import create_app
from cst_session.identity.domain import AccessState, Rejected, Student, Unavailable
from cst_session.scenarios import Catalogue
from tests.lifecycle_fakes import OTHER_OWNER, OWNER, FakePersona, Harness, harness

TOKEN = "synthetic-id-token-1"
OTHER_TOKEN = "synthetic-id-token-2"
ORIGIN = "https://app.example.test"


@dataclass
class FakeAuth:
    tokens: dict[str, str] = field(
        default_factory=lambda: {TOKEN: OWNER, OTHER_TOKEN: OTHER_OWNER}
    )
    unavailable: bool = False
    verified: list[str] = field(default_factory=list)

    def verify(self, token: str) -> Student:
        if self.unavailable:
            raise Unavailable()
        uid = self.tokens.get(token)
        if uid is None:
            raise Rejected()
        self.verified.append(token)
        return Student(uid=uid)


@dataclass
class FakeStore:
    access: dict[str, AccessState] = field(
        default_factory=lambda: {
            OWNER: AccessState.APPROVED,
            OTHER_OWNER: AccessState.APPROVED,
        }
    )
    deletions: set[str] = field(default_factory=set)
    unavailable: bool = False
    reads: list[tuple[str, str]] = field(default_factory=list)

    def pending(self, uid: str) -> bool:
        self.reads.append(("pending", uid))
        if self.unavailable:
            raise Unavailable()
        return uid in self.deletions

    def access_state(self, uid: str) -> AccessState:
        self.reads.append(("access_state", uid))
        if self.unavailable:
            raise Unavailable()
        return self.access.get(uid, AccessState.MISSING)


@dataclass
class Api:
    client: TestClient
    auth: FakeAuth
    store: FakeStore
    h: Harness

    @property
    def persona(self) -> FakePersona:
        return self.h.persona

    def post(
        self, path: str, body: object, token: str | None = TOKEN, **kwargs: Any
    ) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        if token is not None:
            headers.setdefault("Authorization", f"Bearer {token}")
        return self.client.post(path, json=body, headers=headers, **kwargs)

    def start(
        self,
        scenario_id: str = "routine_intake",
        *,
        token: str | None = TOKEN,
        headers: dict[str, str] | None = None,
        **body: Any,
    ) -> Any:
        return self.post(
            "/v1/sessions",
            {
                "scenario_id": scenario_id,
                "crisis_opt_in": False,
                "save_transcript": False,
                "modality": "text",
                **body,
            },
            token=token,
            headers=headers or {},
        )

    def turn(
        self, state: str, text: str = "What brings you in today?", **kw: Any
    ) -> Any:
        return self.post("/v1/sessions/turns", {"state": state, "text": text}, **kw)

    def end(self, state: str, **kw: Any) -> Any:
        return self.post("/v1/sessions/end", {"state": state}, **kw)


def api(
    persona: FakePersona | None = None,
    origins: tuple[str, ...] = (ORIGIN,),
    catalogue: Catalogue | None = None,
) -> Api:
    h = harness(persona=persona, catalogue=catalogue)
    auth = FakeAuth()
    store = FakeStore()
    app = create_app(auth, store, h.sessions, origins)
    client = TestClient(app, raise_server_exceptions=False)
    return Api(client, auth, store, h)
