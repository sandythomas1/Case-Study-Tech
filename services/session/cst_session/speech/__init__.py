"""Provider-neutral speech interface (RC-16, ARCHITECTURE §5).

Session code depends only on this package. Vendor SDKs may be imported only
inside ``cst_session.speech.adapters``.
"""

from cst_session.speech.errors import (
    ProviderTimeoutError,
    ProviderUnavailableError,
    SpeechProviderError,
    UnsupportedAudioError,
)
from cst_session.speech.interface import (
    SYNTHESIS_FORMAT,
    TRANSCRIPTION_FORMAT,
    AudioFormat,
    SpeechProvider,
    TranscriptEvent,
)

__all__ = [
    "SYNTHESIS_FORMAT",
    "TRANSCRIPTION_FORMAT",
    "AudioFormat",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "SpeechProvider",
    "SpeechProviderError",
    "TranscriptEvent",
    "UnsupportedAudioError",
]
