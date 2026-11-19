from cst_session.speech import SpeechProvider
from cst_session.speech.fake import (
    FakeSpeechProvider,
    ScriptedTranscript,
    SimulatedFailure,
)
from tests.speech_contract import ProviderCondition, SpeechProviderContract

_FAILURES = {
    ProviderCondition.UNAVAILABLE: SimulatedFailure.UNAVAILABLE,
    ProviderCondition.TIMEOUT: SimulatedFailure.TIMEOUT,
}


class TestFakeSpeechProviderContract(SpeechProviderContract):
    def make_provider(self, condition: ProviderCondition) -> SpeechProvider:
        script = ScriptedTranscript(
            final="I have been feeling stuck at work.",
            partials=("I have", "I have been feeling"),
        )
        return FakeSpeechProvider([script], failure=_FAILURES.get(condition))
