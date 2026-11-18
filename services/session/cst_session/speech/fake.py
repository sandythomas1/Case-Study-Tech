"""In-memory speech provider for tests.

The fake plays scripted transcripts and returns synthetic silence. It can add
latency and raise each typed error, so callers can test their failure paths
(#44) without a network or a vendor. It keeps nothing beyond the call and
never logs or writes to disk.
"""

import asyncio
from collections import deque
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Iterable
from dataclasses import dataclass
from enum import Enum

from cst_session.speech.errors import (
    ProviderTimeoutError,
    ProviderUnavailableError,
    SpeechProviderError,
    UnsupportedAudioError,
)
from cst_session.speech.interface import (
    BYTES_PER_SAMPLE,
    SYNTHESIS_FORMAT,
    TRANSCRIPTION_FORMAT,
    AudioFormat,
    TranscriptEvent,
    is_whole_samples,
)

Sleep = Callable[[float], Awaitable[None]]

SYNTHESIS_CHUNK_MS = 100
SYNTHESIS_MS_PER_CHARACTER = 10


class SimulatedFailure(Enum):
    """A typed error the fake raises, after any configured latency."""

    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    UNSUPPORTED_AUDIO = "unsupported_audio"


@dataclass(frozen=True)
class ScriptedTranscript:
    """What one ``transcribe`` call returns: partial texts, then a final text."""

    final: str
    partials: tuple[str, ...] = ()


class FakeSpeechProvider:
    """A deterministic ``SpeechProvider``.

    Each ``transcribe`` call consumes the next scripted transcript. Partial
    events are interleaved with the incoming audio, one after each chunk,
    and any left over follow the end of the audio. The final event comes last.
    """

    def __init__(
        self,
        transcripts: Iterable[ScriptedTranscript] = (),
        *,
        latency_s: float = 0.0,
        failure: SimulatedFailure | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if latency_s < 0:
            raise ValueError("latency_s must not be negative")
        self._transcripts = deque(transcripts)
        self._latency_s = latency_s
        self._failure = failure
        self._sleep = sleep

    async def transcribe(
        self,
        audio: AsyncIterable[bytes],
        audio_format: AudioFormat = TRANSCRIPTION_FORMAT,
    ) -> AsyncIterator[TranscriptEvent]:
        _require_format(audio_format, TRANSCRIPTION_FORMAT)
        await self._respond()
        script = self._next_transcript()
        pending_partials = deque(script.partials)
        received_audio = False

        async for chunk in audio:
            if not chunk or not is_whole_samples(chunk):
                raise UnsupportedAudioError("audio chunk is not whole 16-bit samples")
            received_audio = True
            if pending_partials:
                yield TranscriptEvent(text=pending_partials.popleft(), is_final=False)

        if not received_audio:
            raise UnsupportedAudioError("no audio was received")
        while pending_partials:
            yield TranscriptEvent(text=pending_partials.popleft(), is_final=False)
        yield TranscriptEvent(text=script.final, is_final=True)

    async def synthesize(
        self,
        text: str,
        audio_format: AudioFormat = SYNTHESIS_FORMAT,
    ) -> AsyncIterator[bytes]:
        if not text.strip():
            raise ValueError("text to synthesize must not be empty")
        _require_format(audio_format, SYNTHESIS_FORMAT)
        await self._respond()

        total_ms = max(SYNTHESIS_CHUNK_MS, len(text) * SYNTHESIS_MS_PER_CHARACTER)
        for start_ms in range(0, total_ms, SYNTHESIS_CHUNK_MS):
            chunk_ms = min(SYNTHESIS_CHUNK_MS, total_ms - start_ms)
            yield _silence(chunk_ms, audio_format)

    async def _respond(self) -> None:
        if self._latency_s:
            await self._sleep(self._latency_s)
        if self._failure is not None:
            raise _error_for(self._failure)

    def _next_transcript(self) -> ScriptedTranscript:
        if not self._transcripts:
            raise RuntimeError("FakeSpeechProvider has no scripted transcript left")
        return self._transcripts.popleft()


def _require_format(actual: AudioFormat, expected: AudioFormat) -> None:
    if actual != expected:
        raise UnsupportedAudioError("audio format is not supported")


def _error_for(failure: SimulatedFailure) -> SpeechProviderError:
    errors: dict[SimulatedFailure, SpeechProviderError] = {
        SimulatedFailure.UNAVAILABLE: ProviderUnavailableError(
            "speech provider is unavailable"
        ),
        SimulatedFailure.TIMEOUT: ProviderTimeoutError("speech provider timed out"),
        SimulatedFailure.UNSUPPORTED_AUDIO: UnsupportedAudioError(
            "audio is not supported"
        ),
    }
    return errors[failure]


def _silence(duration_ms: int, audio_format: AudioFormat) -> bytes:
    samples = audio_format.sample_rate_hz * duration_ms // 1000
    return bytes(samples * BYTES_PER_SAMPLE)
