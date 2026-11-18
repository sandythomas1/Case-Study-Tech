"""The replaceable speech provider interface (RC-16, plan CD-1).

Audio contract
--------------
All audio crossing this interface is raw PCM: signed 16-bit little-endian
samples, mono, no container or header.

* Transcription input uses ``TRANSCRIPTION_FORMAT``: 16 000 Hz.
* Synthesis output uses ``SYNTHESIS_FORMAT``: 24 000 Hz.

These are the only formats the interface accepts. A provider raises
``UnsupportedAudioError`` for any other format, even one its vendor could
handle, so swapping providers never changes what callers may send. It also
raises it when a chunk is empty or does not hold a whole number of samples
(an odd byte length), or when the audio stream ends without any audio.
Adapters resample or re-encode internally. Callers never see vendor formats.

Event contract
--------------
``transcribe`` yields zero or more partial events, then exactly one final
event, then ends. A provider raises a ``SpeechProviderError`` subclass from
the iterator instead of yielding the final event when it fails, so a final
event always means a complete transcript.

``synthesize`` yields one or more non-empty audio chunks, each a whole number
of samples, then ends.

Data handling
-------------
Implementations hold audio and text in memory only. They never write either
to disk, a cache or a log (RC-03, POLICY DAT-1 and DAT-7).
"""

from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass, field
from typing import Final, Literal, Protocol, runtime_checkable

PCM_S16LE: Final = "pcm_s16le"
BYTES_PER_SAMPLE: Final = 2


@dataclass(frozen=True)
class AudioFormat:
    """Raw PCM audio layout. Only mono signed 16-bit little-endian is defined."""

    sample_rate_hz: int
    encoding: Literal["pcm_s16le"] = PCM_S16LE
    channels: Literal[1] = 1


TRANSCRIPTION_FORMAT: Final = AudioFormat(sample_rate_hz=16_000)
SYNTHESIS_FORMAT: Final = AudioFormat(sample_rate_hz=24_000)


@dataclass(frozen=True)
class TranscriptEvent:
    """A transcript update.

    ``text`` is excluded from ``repr`` so an event that ends up in a log or a
    traceback does not leak what the student said (POLICY DAT-7).
    """

    text: str = field(repr=False)
    is_final: bool


@runtime_checkable
class SpeechProvider(Protocol):
    """Speech-to-text and text-to-speech behind one vendor-neutral seam."""

    def transcribe(
        self,
        audio: AsyncIterable[bytes],
        audio_format: AudioFormat = TRANSCRIPTION_FORMAT,
    ) -> AsyncIterator[TranscriptEvent]:
        """Stream audio chunks in and transcript events out.

        Raises ``UnsupportedAudioError``, ``ProviderUnavailableError`` or
        ``ProviderTimeoutError`` from the returned iterator.
        """
        ...

    def synthesize(
        self,
        text: str,
        audio_format: AudioFormat = SYNTHESIS_FORMAT,
    ) -> AsyncIterator[bytes]:
        """Turn text into a stream of audio chunks in ``audio_format``.

        Raises ``ValueError`` for empty text, or ``UnsupportedAudioError``,
        ``ProviderUnavailableError`` or ``ProviderTimeoutError``, all from the
        returned iterator.
        """
        ...


def is_whole_samples(chunk: bytes) -> bool:
    """Whether ``chunk`` holds a whole number of 16-bit mono samples."""
    return len(chunk) % BYTES_PER_SAMPLE == 0
