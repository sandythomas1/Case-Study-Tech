"""Generated test audio. Tests never use recorded speech (POLICY DAT-6)."""

import math
import struct
from collections.abc import AsyncIterator, Iterable

from cst_session.speech.interface import TRANSCRIPTION_FORMAT, AudioFormat


def sine_tone(
    duration_ms: int,
    audio_format: AudioFormat = TRANSCRIPTION_FORMAT,
    frequency_hz: float = 440.0,
) -> bytes:
    """A mono signed 16-bit little-endian sine tone."""
    samples = audio_format.sample_rate_hz * duration_ms // 1000
    amplitude = 0.3 * 32767
    values = (
        round(
            amplitude
            * math.sin(2 * math.pi * frequency_hz * i / audio_format.sample_rate_hz)
        )
        for i in range(samples)
    )
    return struct.pack(f"<{samples}h", *values)


def tone_chunks(
    count: int = 5,
    chunk_ms: int = 100,
    audio_format: AudioFormat = TRANSCRIPTION_FORMAT,
) -> list[bytes]:
    return [sine_tone(chunk_ms, audio_format) for _ in range(count)]


async def stream(chunks: Iterable[bytes]) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk
