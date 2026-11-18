"""Typed speech errors.

Messages are fixed strings. They never include audio, transcript text or
synthesis input, so they are safe to log (POLICY DAT-7).
"""


class SpeechProviderError(Exception):
    """Base class for every error a speech provider may raise."""


class ProviderUnavailableError(SpeechProviderError):
    """The provider could not be reached or refused the request."""


class ProviderTimeoutError(SpeechProviderError):
    """The provider did not respond within its deadline."""


class UnsupportedAudioError(SpeechProviderError):
    """The audio format or the audio bytes do not meet the interface contract."""
