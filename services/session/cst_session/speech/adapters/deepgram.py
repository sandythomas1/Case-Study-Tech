"""Deepgram speech adapter: Flux streaming STT and Aura-2 TTS (#101).

Data handling (POLICY DAT-4 to DAT-7)
-------------------------------------
* Every request URL carries ``mip_opt_out=true``, so Deepgram keeps the
  request only as long as it needs to process it and never trains on it.
  ``_with_mip_opt_out`` is the only way this module builds a URL.
* Deepgram is approved for synthetic-audio benchmarking only, until its written
  terms are confirmed (``docs/decisions/speech-deepgram.md``).
* Audio and text stay in memory. Error messages are fixed strings that never
  include audio, transcript text, synthesis input or vendor error bodies.
* The API key travels only in the ``Authorization`` header. It is excluded
  from ``repr`` and never appears in a URL, a message or an error.

Wire format
-----------
* STT: WebSocket ``/v2/listen`` with ``flux-general-en``, raw ``linear16`` at
  16 kHz, which is the interface's own transcription format, so no resampling.
  Flux reports turns. Completed turns are joined into the one final transcript
  the interface promises. When the audio ends the adapter sends
  ``ForceEndTurn`` and ``CloseStream``. The final event comes from the forced
  ``EndOfTurn`` or, failing that, from a normal close of the socket.
* TTS: ``POST /v1/speak`` with ``aura-2-<voice>-en``, ``linear16`` at 24 kHz
  and ``container=none``, which is the interface's synthesis format.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterable, AsyncIterator, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Any, Final, Protocol
from urllib.parse import urlencode

from cst_session.speech.errors import (
    ProviderTimeoutError,
    ProviderUnavailableError,
    UnsupportedAudioError,
)
from cst_session.speech.interface import (
    SYNTHESIS_FORMAT,
    TRANSCRIPTION_FORMAT,
    AudioFormat,
    TranscriptEvent,
    is_whole_samples,
)

LISTEN_URL: Final = "wss://api.deepgram.com/v2/listen"
SPEAK_URL: Final = "https://api.deepgram.com/v1/speak"
STT_MODEL: Final = "flux-general-en"
DEFAULT_VOICE: Final = "thalia"

FORCE_END_TURN: Final = json.dumps({"type": "ForceEndTurn"})
CLOSE_STREAM: Final = json.dumps({"type": "CloseStream"})

_VOICE_PATTERN: Final = re.compile(r"[a-z]{1,32}")
_SPEAK_CONTENT_TYPE: Final = "audio/l16"


class DeepgramStream(Protocol):
    """An open Flux WebSocket."""

    async def send_audio(self, chunk: bytes) -> None: ...

    async def send_text(self, message: str) -> None: ...

    async def receive(self) -> str | bytes | None:
        """The next server message, or ``None`` once the server closed normally."""
        ...


@dataclass(frozen=True)
class SpeakResponse:
    """The status, content type and body of a ``/v1/speak`` response."""

    status: int
    content_type: str
    body: AsyncIterator[bytes]


class DeepgramTransport(Protocol):
    """The network seam. Implementations raise ``ProviderUnavailableError`` or
    ``ProviderTimeoutError`` for every network failure, never a library error.
    """

    def connect(
        self, url: str, headers: Mapping[str, str]
    ) -> AbstractAsyncContextManager[DeepgramStream]: ...

    def post(
        self, url: str, headers: Mapping[str, str], body: bytes
    ) -> AbstractAsyncContextManager[SpeakResponse]: ...


@dataclass(frozen=True)
class DeepgramSettings:
    """Adapter settings. The key comes from Secret Manager, never from code."""

    api_key: str = field(repr=False)
    voice: str = DEFAULT_VOICE
    finalize_timeout_s: float = 5.0

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("a Deepgram API key is required")
        if not _VOICE_PATTERN.fullmatch(self.voice):
            raise ValueError("voice must be a lower-case Aura-2 voice name")
        if self.finalize_timeout_s <= 0:
            raise ValueError("finalize_timeout_s must be positive")

    @property
    def tts_model(self) -> str:
        return f"aura-2-{self.voice}-en"


def listen_url() -> str:
    return _with_mip_opt_out(
        LISTEN_URL,
        {
            "model": STT_MODEL,
            "encoding": "linear16",
            "sample_rate": str(TRANSCRIPTION_FORMAT.sample_rate_hz),
        },
    )


def speak_url(settings: DeepgramSettings) -> str:
    return _with_mip_opt_out(
        SPEAK_URL,
        {
            "model": settings.tts_model,
            "encoding": "linear16",
            "sample_rate": str(SYNTHESIS_FORMAT.sample_rate_hz),
            "container": "none",
        },
    )


def _with_mip_opt_out(base_url: str, params: dict[str, str]) -> str:
    return f"{base_url}?{urlencode({**params, 'mip_opt_out': 'true'})}"


class DeepgramSpeechProvider:
    """A ``SpeechProvider`` backed by Deepgram Flux and Aura-2."""

    def __init__(
        self, settings: DeepgramSettings, transport: DeepgramTransport
    ) -> None:
        self._settings = settings
        self._transport = transport

    def __repr__(self) -> str:
        return f"DeepgramSpeechProvider(voice={self._settings.voice!r})"

    async def transcribe(
        self,
        audio: AsyncIterable[bytes],
        audio_format: AudioFormat = TRANSCRIPTION_FORMAT,
    ) -> AsyncIterator[TranscriptEvent]:
        _require_format(audio_format, TRANSCRIPTION_FORMAT)
        chunks = aiter(audio)
        first = await _first_chunk(chunks)

        async with self._transport.connect(
            listen_url(), self._auth_headers()
        ) as stream:
            sender = asyncio.create_task(_send_audio(stream, first, chunks))
            try:
                async for event in self._turn_events(stream, sender):
                    yield event
            finally:
                await _cancel(sender)

    async def synthesize(
        self,
        text: str,
        audio_format: AudioFormat = SYNTHESIS_FORMAT,
    ) -> AsyncIterator[bytes]:
        if not text.strip():
            raise ValueError("text to synthesize must not be empty")
        _require_format(audio_format, SYNTHESIS_FORMAT)

        body = json.dumps({"text": text}).encode()
        headers = {**self._auth_headers(), "Content-Type": "application/json"}
        async with self._transport.post(
            speak_url(self._settings), headers, body
        ) as response:
            _require_audio_response(response)
            async for chunk in _whole_samples(response.body):
                yield chunk

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Token {self._settings.api_key}"}

    async def _turn_events(
        self, stream: DeepgramStream, sender: asyncio.Task[None]
    ) -> AsyncIterator[TranscriptEvent]:
        transcript = _Transcript()
        receiver = _Receiver(stream, sender, self._settings.finalize_timeout_s)
        while True:
            message = await receiver.next()
            if message is None:
                if not receiver.audio_sent:
                    raise ProviderUnavailableError("speech provider closed the stream")
                yield TranscriptEvent(text=transcript.text(), is_final=True)
                return
            turn = _parse_turn(message)
            if turn is None:
                continue
            if turn.is_forced_end and receiver.audio_sent:
                transcript.end_turn(turn.text)
                yield TranscriptEvent(text=transcript.text(), is_final=True)
                return
            if transcript.update(turn):
                yield TranscriptEvent(text=transcript.text(), is_final=False)


@dataclass(frozen=True)
class _Turn:
    event: str
    text: str
    trigger: str | None

    @property
    def is_end(self) -> bool:
        return self.event == "EndOfTurn"

    @property
    def is_forced_end(self) -> bool:
        return self.is_end and self.trigger == "manual"


class _Transcript:
    """Joins Flux turns into the one transcript the interface delivers."""

    def __init__(self) -> None:
        self._completed: list[str] = []
        self._current = ""

    def update(self, turn: _Turn) -> bool:
        """Apply a non-final turn event. Returns whether the text changed."""
        before = self.text()
        if turn.is_end:
            self.end_turn(turn.text)
        else:
            self._current = turn.text
        return self.text() != before

    def end_turn(self, text: str) -> None:
        if text.strip():
            self._completed.append(text.strip())
        self._current = ""

    def text(self) -> str:
        parts = [*self._completed, self._current.strip()]
        return " ".join(part for part in parts if part)


class _Receiver:
    """Reads server messages while the audio sender runs.

    A sender failure (bad audio or a network error) is raised here. Once the
    sender has finished, each read has ``finalize_timeout_s`` to arrive.
    """

    def __init__(
        self,
        stream: DeepgramStream,
        sender: asyncio.Task[None],
        finalize_timeout_s: float,
    ) -> None:
        self._stream = stream
        self._sender = sender
        self._finalize_timeout_s = finalize_timeout_s

    @property
    def audio_sent(self) -> bool:
        return self._sender.done() and not self._sender.cancelled()

    async def next(self) -> str | bytes | None:
        receive = asyncio.ensure_future(self._stream.receive())
        try:
            if not self._sender.done():
                await asyncio.wait(
                    {receive, self._sender}, return_when=asyncio.FIRST_COMPLETED
                )
                if receive.done():
                    return receive.result()
            self._sender.result()
            async with asyncio.timeout(self._finalize_timeout_s):
                return await receive
        except TimeoutError as error:
            raise ProviderTimeoutError("speech provider timed out") from error
        finally:
            await _cancel(receive)


async def _first_chunk(chunks: AsyncIterator[bytes]) -> bytes:
    """Read and check the first chunk before opening a billed connection."""
    try:
        first = await anext(chunks)
    except StopAsyncIteration:
        raise UnsupportedAudioError("no audio was received") from None
    _require_whole_samples(first)
    return first


async def _send_audio(
    stream: DeepgramStream, first: bytes, chunks: AsyncIterator[bytes]
) -> None:
    await stream.send_audio(first)
    async for chunk in chunks:
        _require_whole_samples(chunk)
        await stream.send_audio(chunk)
    await stream.send_text(FORCE_END_TURN)
    await stream.send_text(CLOSE_STREAM)


def _parse_turn(message: str | bytes) -> _Turn | None:
    """A ``TurnInfo`` message as a turn, ``None`` for other known messages."""
    if isinstance(message, bytes):
        return None
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        raise ProviderUnavailableError(
            "speech provider sent an unreadable message"
        ) from None
    if not isinstance(payload, dict):
        raise ProviderUnavailableError("speech provider sent an unreadable message")
    message_type = payload.get("type")
    if message_type == "Error":
        raise ProviderUnavailableError("speech provider reported an error")
    if message_type != "TurnInfo":
        return None
    text = payload.get("transcript")
    event = payload.get("event")
    trigger = payload.get("trigger")
    if not isinstance(text, str) or not isinstance(event, str):
        raise ProviderUnavailableError("speech provider sent an unreadable message")
    return _Turn(
        event=event,
        text=text,
        trigger=trigger if isinstance(trigger, str) else None,
    )


def _require_audio_response(response: SpeakResponse) -> None:
    if response.status != 200:
        raise ProviderUnavailableError("speech provider refused the request")
    media_type, *params = (
        part.strip().lower() for part in response.content_type.split(";")
    )
    rates = {
        value for name, _, value in (p.partition("=") for p in params) if name == "rate"
    }
    if media_type != _SPEAK_CONTENT_TYPE or not rates <= {
        str(SYNTHESIS_FORMAT.sample_rate_hz)
    }:
        raise ProviderUnavailableError("speech provider returned an unexpected format")


async def _whole_samples(body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """Re-chunk a byte stream so every chunk holds whole 16-bit samples."""
    carry = b""
    received = False
    async for data in body:
        data = carry + data
        cut = len(data) - len(data) % 2
        carry = data[cut:]
        if cut:
            received = True
            yield data[:cut]
    if carry:
        raise ProviderUnavailableError("speech provider returned incomplete audio")
    if not received:
        raise ProviderUnavailableError("speech provider returned no audio")


def _require_format(actual: AudioFormat, expected: AudioFormat) -> None:
    if actual != expected:
        raise UnsupportedAudioError("audio format is not supported")


def _require_whole_samples(chunk: bytes) -> None:
    if not chunk or not is_whole_samples(chunk):
        raise UnsupportedAudioError("audio chunk is not whole 16-bit samples")


async def _cancel(task: "asyncio.Future[Any]") -> None:
    """Stop ``task`` and wait for it, without raising its result.

    A cleanup must not hide the error already on its way to the caller.
    """
    task.cancel()
    await asyncio.wait({task})
    if not task.cancelled():
        task.exception()
