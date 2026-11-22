from cst_session.speech import (
    ProviderTimeoutError,
    ProviderUnavailableError,
    SpeechProvider,
)
from cst_session.speech.adapters.deepgram import (
    DeepgramSettings,
    DeepgramSpeechProvider,
)
from tests.deepgram_fakes import (
    TEST_API_KEY,
    FakeDeepgramTransport,
    FluxScript,
    healthy_flux,
)
from tests.speech_contract import ProviderCondition, SpeechProviderContract


def make_deepgram(condition: ProviderCondition) -> DeepgramSpeechProvider:
    """The adapter on a fake network that behaves the way ``condition`` says.

    A timeout is the adapter's own deadline expiring on a silent server for
    transcription, and the transport's timeout for synthesis.
    """
    settings = DeepgramSettings(api_key=TEST_API_KEY, finalize_timeout_s=0.05)
    if condition is ProviderCondition.UNAVAILABLE:
        error = ProviderUnavailableError("speech provider is unavailable")
        transport = FakeDeepgramTransport(connect_error=error, post_error=error)
    elif condition is ProviderCondition.TIMEOUT:
        transport = FakeDeepgramTransport(
            flux=[FluxScript(hang=True)],
            post_error=ProviderTimeoutError("speech provider timed out"),
        )
    else:
        transport = FakeDeepgramTransport(flux=[healthy_flux()])
    return DeepgramSpeechProvider(settings, transport)


class TestDeepgramSpeechProviderContract(SpeechProviderContract):
    def make_provider(self, condition: ProviderCondition) -> SpeechProvider:
        return make_deepgram(condition)
