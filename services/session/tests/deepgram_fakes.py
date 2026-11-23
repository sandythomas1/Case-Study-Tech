"""A scripted stand-in for Deepgram's network, for the adapter tests.

``FakeDeepgramTransport`` records every URL and header it is handed, so tests
can check what would have gone on the wire. It never opens a socket.
"""

import asyncio
import json
from collections import deque
from collections.abc import AsyncIterator, Iterable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from cst_session.speech.adapters.deepgram import (
    CLOSE_STREAM,
    FORCE_END_TURN,
    DeepgramStream,
    SpeakResponse,
)
from cst_session.speech.errors import ProviderUnavailableError, SpeechProviderError

TEST_API_KEY = "dg-test-key-not-a-secret"


def turn_info(event: str, transcript: str, trigger: str | None = None) -> str:
    """A Flux ``TurnInfo`` message as the server would send it."""
    message: dict[str, object] = {
        "type": "TurnInfo",
        "request_id": "00000000-0000-0000-0000-000000000000",
        "sequence_id": 1,
        "event": event,
        "turn_index": 0,
        "audio_window_start": 0.0,
        "audio_window_end": 0.5,
        "transcript": transcript,
        "words": [],
        "end_of_turn_confidence": 0.9,
    }
    if trigger is not None:
        message["trigger"] = trigger
    return json.dumps(message)


CONNECTED = json.dumps({"type": "Connected", "request_id": "r", "sequence_id": 0})


@dataclass
class FluxScript:
    """How the fake Flux server answers one connection.

    ``per_chunk`` messages are released one per audio chunk received, any left
    after the audio ends come next, then ``on_force_end`` once ``ForceEndTurn``
    arrives. ``close_on_close_stream`` closes normally on ``CloseStream``.
    ``close_after_chunks`` closes normally after that many chunks.
    ``hang`` means the server never answers.
    """

    per_chunk: list[str | bytes] = field(default_factory=list)
    on_force_end: list[str | bytes] = field(default_factory=list)
    close_on_close_stream: bool = False
    close_after_chunks: int | None = None
    hang: bool = False


class FakeFluxStream:
    def __init__(self, script: FluxScript) -> None:
        self._script = script
        self._pending = deque(script.per_chunk)
        self._inbox: asyncio.Queue[str | bytes | None] = asyncio.Queue()
        self.audio: list[bytes] = []
        self.texts: list[str] = []
        self.closed = False
        self._server_closed = False

    def _close_from_server(self) -> None:
        self._server_closed = True
        self._inbox.put_nowait(None)

    def _require_open(self) -> None:
        if self._server_closed:
            raise ProviderUnavailableError("speech provider closed the stream")

    async def send_audio(self, chunk: bytes) -> None:
        self._require_open()
        self.audio.append(chunk)
        if self._script.hang:
            return
        if self._pending:
            self._inbox.put_nowait(self._pending.popleft())
        if self._script.close_after_chunks == len(self.audio):
            self._close_from_server()

    async def send_text(self, message: str) -> None:
        self._require_open()
        self.texts.append(message)
        if self._script.hang:
            return
        if message == FORCE_END_TURN:
            while self._pending:
                self._inbox.put_nowait(self._pending.popleft())
            for reply in self._script.on_force_end:
                self._inbox.put_nowait(reply)
        elif message == CLOSE_STREAM and self._script.close_on_close_stream:
            self._close_from_server()

    async def receive(self) -> str | bytes | None:
        return await self._inbox.get()


@dataclass
class SpeakScript:
    status: int = 200
    content_type: str = "audio/l16;rate=24000"
    chunks: list[bytes] = field(default_factory=lambda: [bytes(4800)] * 3)
    error_after_chunks: SpeechProviderError | None = None


@dataclass(frozen=True)
class RecordedRequest:
    url: str
    headers: Mapping[str, str]
    body: bytes = b""


class FakeDeepgramTransport:
    """A ``DeepgramTransport`` that plays scripts and records each request."""

    def __init__(
        self,
        flux: Iterable[FluxScript] = (),
        speak: SpeakScript | None = None,
        connect_error: SpeechProviderError | None = None,
        post_error: SpeechProviderError | None = None,
    ) -> None:
        self._flux = deque(flux)
        self._speak = speak or SpeakScript()
        self._connect_error = connect_error
        self._post_error = post_error
        self.connections: list[RecordedRequest] = []
        self.posts: list[RecordedRequest] = []
        self.streams: list[FakeFluxStream] = []

    @property
    def requests(self) -> list[RecordedRequest]:
        return [*self.connections, *self.posts]

    @asynccontextmanager
    async def connect(
        self, url: str, headers: Mapping[str, str]
    ) -> AsyncIterator[DeepgramStream]:
        self.connections.append(RecordedRequest(url, dict(headers)))
        if self._connect_error is not None:
            raise self._connect_error
        stream = FakeFluxStream(self._flux.popleft() if self._flux else FluxScript())
        self.streams.append(stream)
        try:
            yield stream
        finally:
            stream.closed = True

    @asynccontextmanager
    async def post(
        self, url: str, headers: Mapping[str, str], body: bytes
    ) -> AsyncIterator[SpeakResponse]:
        self.posts.append(RecordedRequest(url, dict(headers), body))
        if self._post_error is not None:
            raise self._post_error
        yield SpeakResponse(
            status=self._speak.status,
            content_type=self._speak.content_type,
            body=self._body(),
        )

    async def _body(self) -> AsyncIterator[bytes]:
        for chunk in self._speak.chunks:
            yield chunk
        if self._speak.error_after_chunks is not None:
            raise self._speak.error_after_chunks


def healthy_flux() -> FluxScript:
    return FluxScript(
        per_chunk=[
            CONNECTED,
            turn_info("StartOfTurn", "I have"),
            turn_info("Update", "I have been feeling"),
        ],
        on_force_end=[
            turn_info("EndOfTurn", "I have been feeling stuck at work.", "manual")
        ],
    )
