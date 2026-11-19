"""The contract every ``SpeechProvider`` adapter must pass.

To check an adapter, subclass ``SpeechProviderContract`` in a ``test_*.py``
module, name the subclass ``Test<Adapter>Contract`` and implement
``make_provider``. For the failure conditions, build the adapter against a
stubbed transport that fails the way the condition says. Never call a real
vendor, and use only generated audio from ``tests.synthetic_audio``.
"""

import asyncio
from collections.abc import AsyncIterable
from enum import Enum

import pytest

from cst_session.speech import (
    SYNTHESIS_FORMAT,
    TRANSCRIPTION_FORMAT,
    AudioFormat,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SpeechProvider,
    SpeechProviderError,
    TranscriptEvent,
    UnsupportedAudioError,
)
from tests.synthetic_audio import sine_tone, stream, tone_chunks

SYNTHESIS_TEXT = "I have been feeling stuck at work lately."


class ProviderCondition(Enum):
    HEALTHY = "healthy"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"


async def _collect_transcript(
    provider: SpeechProvider,
    audio: AsyncIterable[bytes],
    audio_format: AudioFormat = TRANSCRIPTION_FORMAT,
) -> tuple[list[TranscriptEvent], SpeechProviderError | None]:
    events: list[TranscriptEvent] = []
    try:
        async for event in provider.transcribe(audio, audio_format):
            events.append(event)
    except SpeechProviderError as error:
        return events, error
    return events, None


async def _collect_synthesis(
    provider: SpeechProvider,
    text: str,
    audio_format: AudioFormat = SYNTHESIS_FORMAT,
) -> tuple[list[bytes], SpeechProviderError | None]:
    chunks: list[bytes] = []
    try:
        async for chunk in provider.synthesize(text, audio_format):
            chunks.append(chunk)
    except SpeechProviderError as error:
        return chunks, error
    return chunks, None


def _transcribe(
    provider: SpeechProvider,
    chunks: list[bytes],
    audio_format: AudioFormat = TRANSCRIPTION_FORMAT,
) -> tuple[list[TranscriptEvent], SpeechProviderError | None]:
    return asyncio.run(_collect_transcript(provider, stream(chunks), audio_format))


def _synthesize(
    provider: SpeechProvider,
    text: str = SYNTHESIS_TEXT,
    audio_format: AudioFormat = SYNTHESIS_FORMAT,
) -> tuple[list[bytes], SpeechProviderError | None]:
    return asyncio.run(_collect_synthesis(provider, text, audio_format))


class SpeechProviderContract:
    """Behavior every adapter shares. Not collected until subclassed as ``Test*``."""

    def make_provider(self, condition: ProviderCondition) -> SpeechProvider:
        raise NotImplementedError

    def test_satisfies_the_protocol(self) -> None:
        assert isinstance(self.make_provider(ProviderCondition.HEALTHY), SpeechProvider)

    # Event order and final transcript delivery

    def test_transcription_ends_with_exactly_one_final_event(self) -> None:
        events, error = _transcribe(
            self.make_provider(ProviderCondition.HEALTHY), tone_chunks()
        )

        assert error is None
        assert events, "a transcription must yield at least the final event"
        assert events[-1].is_final
        assert [event.is_final for event in events].count(True) == 1

    def test_partial_events_all_come_before_the_final_event(self) -> None:
        events, _ = _transcribe(
            self.make_provider(ProviderCondition.HEALTHY), tone_chunks()
        )

        final_index = next(i for i, event in enumerate(events) if event.is_final)
        assert final_index == len(events) - 1
        assert all(not event.is_final for event in events[:final_index])

    def test_final_transcript_is_text(self) -> None:
        events, _ = _transcribe(
            self.make_provider(ProviderCondition.HEALTHY), tone_chunks()
        )

        assert isinstance(events[-1].text, str)

    def test_synthesis_yields_non_empty_whole_sample_chunks(self) -> None:
        chunks, error = _synthesize(self.make_provider(ProviderCondition.HEALTHY))

        assert error is None
        assert chunks
        assert all(chunk and len(chunk) % 2 == 0 for chunk in chunks)

    # Input validation

    def test_transcription_rejects_a_partial_sample(self) -> None:
        odd_chunk = sine_tone(100) + b"\x00"

        events, error = _transcribe(
            self.make_provider(ProviderCondition.HEALTHY), [odd_chunk]
        )

        assert isinstance(error, UnsupportedAudioError)
        assert not any(event.is_final for event in events)

    def test_transcription_rejects_an_unsupported_format(self) -> None:
        cd_quality = AudioFormat(sample_rate_hz=44_100)

        events, error = _transcribe(
            self.make_provider(ProviderCondition.HEALTHY),
            tone_chunks(audio_format=cd_quality),
            cd_quality,
        )

        assert isinstance(error, UnsupportedAudioError)
        assert events == []

    def test_transcription_rejects_an_empty_stream(self) -> None:
        events, error = _transcribe(self.make_provider(ProviderCondition.HEALTHY), [])

        assert isinstance(error, UnsupportedAudioError)
        assert events == []

    def test_synthesis_rejects_empty_text(self) -> None:
        with pytest.raises(ValueError):
            _synthesize(self.make_provider(ProviderCondition.HEALTHY), text="  ")

    # Typed failures: no final transcript is delivered. Synthesis may already
    # have sent audio chunks before its error, so only the error type is checked.

    @pytest.mark.parametrize(
        ("condition", "error_type"),
        [
            (ProviderCondition.UNAVAILABLE, ProviderUnavailableError),
            (ProviderCondition.TIMEOUT, ProviderTimeoutError),
        ],
    )
    def test_failed_transcription_raises_a_typed_error_and_no_final_event(
        self, condition: ProviderCondition, error_type: type[SpeechProviderError]
    ) -> None:
        events, error = _transcribe(self.make_provider(condition), tone_chunks())

        assert isinstance(error, error_type)
        assert not any(event.is_final for event in events)

    @pytest.mark.parametrize(
        ("condition", "error_type"),
        [
            (ProviderCondition.UNAVAILABLE, ProviderUnavailableError),
            (ProviderCondition.TIMEOUT, ProviderTimeoutError),
        ],
    )
    def test_failed_synthesis_raises_a_typed_error(
        self, condition: ProviderCondition, error_type: type[SpeechProviderError]
    ) -> None:
        _, error = _synthesize(self.make_provider(condition))

        assert isinstance(error, error_type)
