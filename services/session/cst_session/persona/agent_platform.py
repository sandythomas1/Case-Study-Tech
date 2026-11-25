"""The persona adapter for Gemini Enterprise Agent Platform, over REST (FR-5, FR-7, T4, T6).

One ``generateContent`` call per turn, to the ``us`` multi-region endpoint
only (ARCHITECTURE section 6). The request is a typed model with exactly three
keys: ``systemInstruction`` (the verified scenario's prompt), ``contents`` and
``generationConfig``. It never carries tools, cached content, a store flag or
session resumption, and it sets no safety settings, so the model defaults apply.

Every failure raises ``PersonaUnavailable`` with one fixed code. The upstream
body of a failed call is never read, and nothing from a reply, a request or
the conversation reaches an error message or a log. The access token comes
from Application Default Credentials, refreshed in a worker thread under a lock
only when it is no longer valid, and is never logged.
"""

import asyncio
import json
import re
import threading
import unicodedata
from collections.abc import Sequence
from typing import Any, Final, Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from cst_session.persona.port import (
    PersonaFailure,
    PersonaMessage,
    PersonaReply,
    PersonaUnavailable,
    valid_turn_text,
)

AGENT_PLATFORM_HOSTS: Final = {"us": "https://aiplatform.us.rep.googleapis.com"}
PERSONA_DEADLINE_S: Final = 20
MAX_RESPONSE_BYTES: Final = 256 * 1024
CLOUD_PLATFORM_SCOPE: Final = "https://www.googleapis.com/auth/cloud-platform"
ACCEPTED_FINISH_REASONS: Final = frozenset({"STOP", "MAX_TOKENS"})

_MODEL = re.compile(r"gemini-[a-z0-9.-]{1,48}", re.ASCII)
_PROJECT = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", re.ASCII)
_KEPT_FORMAT = frozenset({"\u200c", "\u200d"})  # ZWNJ, ZWJ
_ROLES: Final = {"student": "user", "client": "model"}


class PersonaConfigError(ValueError):
    """The persona endpoint settings are not allowed. Stops startup."""


class TokenUnavailable(Exception):
    """No access token could be obtained. The message is fixed."""

    def __init__(self) -> None:
        super().__init__("token_unavailable")


class TokenSource(Protocol):
    def token(self) -> str:
        """A valid access token. Blocking; raises ``TokenUnavailable``."""
        ...


class AdcTokenSource:
    """Application Default Credentials, loaded on first use and refreshed when invalid."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._credentials: Any = None

    def token(self) -> str:
        # Imported here so the module imports without the auth stack loaded.
        import google.auth
        import google.auth.exceptions
        import google.auth.transport.requests

        with self._lock:
            try:
                if self._credentials is None:
                    self._credentials, _ = google.auth.default(
                        scopes=[CLOUD_PLATFORM_SCOPE]
                    )
                if not self._credentials.valid:
                    self._credentials.refresh(google.auth.transport.requests.Request())
                token = self._credentials.token
            except (google.auth.exceptions.GoogleAuthError, OSError, ValueError):
                raise TokenUnavailable() from None
        if not isinstance(token, str) or not token:
            raise TokenUnavailable()
        return token


def endpoint_url(*, project: str, location: str, model: str) -> str:
    """The ``generateContent`` URL. Only the closed host map is allowed (T4)."""
    host = AGENT_PLATFORM_HOSTS.get(location)
    if host is None:
        raise PersonaConfigError(
            "CST_AGENT_PLATFORM_LOCATION must be one of: "
            + ", ".join(sorted(AGENT_PLATFORM_HOSTS))
        )
    if _MODEL.fullmatch(model) is None:
        raise PersonaConfigError("CST_PERSONA_MODEL is not an allowed model name.")
    if _PROJECT.fullmatch(project) is None:
        raise PersonaConfigError("CST_PROJECT_ID is not a valid project id.")
    return (
        f"{host}/v1/projects/{project}/locations/{location}"
        f"/publishers/google/models/{model}:generateContent"
    )


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Part(_Request):
    text: str


class Content(_Request):
    role: Literal["user", "model"]
    parts: list[Part] = Field(min_length=1, max_length=1)


class SystemInstruction(_Request):
    parts: list[Part] = Field(min_length=1, max_length=1)


class GenerationConfig(_Request):
    candidateCount: Literal[1] = 1
    maxOutputTokens: Literal[400] = 400
    temperature: float = 0.8


class GenerateContentRequest(_Request):
    """The only request shape this adapter can send: three keys, nothing else."""

    systemInstruction: SystemInstruction
    contents: list[Content] = Field(min_length=1)
    generationConfig: GenerationConfig = GenerationConfig()


def model_copy_text(text: str) -> str:
    """The text sent to the model: tag and other format characters removed (T6).

    Joiners stay, because they shape scripts and emoji. The signed state keeps
    the original text.
    """
    return "".join(
        char
        for char in text
        if not (0xE0000 <= ord(char) <= 0xE007F)
        and (unicodedata.category(char) != "Cf" or char in _KEPT_FORMAT)
    )


def build_request(
    system_prompt: str, history: Sequence[PersonaMessage]
) -> GenerateContentRequest:
    return GenerateContentRequest(
        systemInstruction=SystemInstruction(
            parts=[Part(text=model_copy_text(system_prompt))]
        ),
        contents=[
            Content(
                role=_ROLES[message.speaker],
                parts=[Part(text=model_copy_text(message.text))],
            )
            for message in history
        ],
    )


class AgentPlatformPersona:
    """``PersonaPort`` over the Agent Platform REST API."""

    def __init__(
        self,
        *,
        project: str,
        location: str,
        model: str,
        tokens: TokenSource,
        transport: httpx.AsyncBaseTransport | None = None,
        deadline_s: float = PERSONA_DEADLINE_S,
    ) -> None:
        self._url = endpoint_url(project=project, location=location, model=model)
        self._tokens = tokens
        self._deadline_s = deadline_s
        # One pooled client. No redirects and no proxy or CA settings from the
        # environment: the request may only reach the closed host map (T4).
        self._client = httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            trust_env=False,
            verify=True,
            timeout=httpx.Timeout(deadline_s),
        )

    def __repr__(self) -> str:
        return "AgentPlatformPersona()"

    async def reply(
        self, *, system_prompt: str, history: Sequence[PersonaMessage]
    ) -> PersonaReply:
        body = build_request(system_prompt, history).model_dump(mode="json")
        try:
            async with asyncio.timeout(self._deadline_s):
                token = await asyncio.to_thread(self._tokens.token)
                status, raw = await self._post(token, body)
        except TimeoutError:
            raise PersonaUnavailable(PersonaFailure.TIMEOUT) from None
        except TokenUnavailable:
            raise PersonaUnavailable(PersonaFailure.AUTH) from None
        except httpx.TimeoutException:
            raise PersonaUnavailable(PersonaFailure.TIMEOUT) from None
        except httpx.HTTPError:
            raise PersonaUnavailable(PersonaFailure.UNREACHABLE) from None
        if status in {401, 403}:
            raise PersonaUnavailable(PersonaFailure.AUTH, status_code=status)
        if status >= 300 or status < 200:
            raise PersonaUnavailable(PersonaFailure.HTTP_ERROR, status_code=status)
        if raw is None:
            raise PersonaUnavailable(PersonaFailure.BAD_RESPONSE, status_code=status)
        return PersonaReply(text=_reply_text(raw, status))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post(self, token: str, body: dict[str, Any]) -> tuple[int, bytes | None]:
        """The status and, for a 2xx only, the decoded body up to the cap.

        Any other status, or a body over the cap, gives ``None``: a failed
        call's body is never read.
        """
        async with self._client.stream(
            "POST",
            self._url,
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        ) as response:
            if not 200 <= response.status_code < 300:
                return response.status_code, None
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    return response.status_code, None
                chunks.append(chunk)
            return response.status_code, b"".join(chunks)


def _reply_text(raw: bytes, status: int) -> str:
    """The candidate's text, or raise ``PersonaUnavailable`` (T6)."""
    failure, text = _parse_reply(raw)
    if failure is not None:
        raise PersonaUnavailable(failure, status_code=status)
    valid = valid_turn_text(text)
    if valid is None:
        raise PersonaUnavailable(PersonaFailure.BAD_REPLY, status_code=status)
    return valid


def _parse_reply(raw: bytes) -> tuple[PersonaFailure | None, str]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return PersonaFailure.BAD_RESPONSE, ""
    if not isinstance(payload, dict):
        return PersonaFailure.BAD_RESPONSE, ""
    feedback = payload.get("promptFeedback")
    if isinstance(feedback, dict) and feedback.get("blockReason"):
        return PersonaFailure.BLOCKED, ""
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return PersonaFailure.BAD_RESPONSE, ""
    candidate = candidates[0]
    if not isinstance(candidate, dict):
        return PersonaFailure.BAD_RESPONSE, ""
    if candidate.get("finishReason") not in ACCEPTED_FINISH_REASONS:
        return PersonaFailure.BLOCKED, ""
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return PersonaFailure.BAD_REPLY, ""
    texts: list[str] = []
    for part in parts:
        if not isinstance(part, dict) or "functionCall" in part:
            return PersonaFailure.BAD_REPLY, ""
        if part.get("thought") is True:
            continue
        text = part.get("text")
        if not isinstance(text, str):
            return PersonaFailure.BAD_REPLY, ""
        texts.append(text)
    joined = "".join(texts).strip()
    if not joined:
        return PersonaFailure.BAD_REPLY, ""
    return None, joined
