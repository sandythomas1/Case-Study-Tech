import asyncio
import logging
from pathlib import Path

import pytest

from cst_session.speech import (
    SYNTHESIS_FORMAT,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SpeechProviderError,
    TranscriptEvent,
    UnsupportedAudioError,
)
from cst_session.speech.fake import (
    FakeSpeechProvider,
    ScriptedTranscript,
    SimulatedFailure,
)
from tests.synthetic_audio import stream, tone_chunks

SCRIPT = ScriptedTranscript(
    final="I keep putting things off.", partials=("I keep", "I keep putting")
)


async def _transcribe_all(
    provider: FakeSpeechProvider, chunks: list[bytes]
) -> list[TranscriptEvent]:
    return [event async for event in provider.transcribe(stream(chunks))]


async def _synthesize_all(provider: FakeSpeechProvider, text: str) -> list[bytes]:
    return [chunk async for chunk in provider.synthesize(text)]


class RecordingSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def test_plays_the_scripted_partials_then_the_final_text() -> None:
    events = asyncio.run(_transcribe_all(FakeSpeechProvider([SCRIPT]), tone_chunks()))

    assert events == [
        TranscriptEvent(text="I keep", is_final=False),
        TranscriptEvent(text="I keep putting", is_final=False),
        TranscriptEvent(text="I keep putting things off.", is_final=True),
    ]


def test_partials_left_over_after_the_audio_still_precede_the_final() -> None:
    script = ScriptedTranscript(final="c", partials=("a", "b"))

    events = asyncio.run(
        _transcribe_all(FakeSpeechProvider([script]), tone_chunks(count=1))
    )

    assert [(event.text, event.is_final) for event in events] == [
        ("a", False),
        ("b", False),
        ("c", True),
    ]


def test_each_call_consumes_the_next_script() -> None:
    provider = FakeSpeechProvider(
        [ScriptedTranscript(final="first"), ScriptedTranscript(final="second")]
    )

    first = asyncio.run(_transcribe_all(provider, tone_chunks()))
    second = asyncio.run(_transcribe_all(provider, tone_chunks()))

    assert [first[-1].text, second[-1].text] == ["first", "second"]


def test_an_exhausted_script_is_a_test_setup_error() -> None:
    with pytest.raises(RuntimeError):
        asyncio.run(_transcribe_all(FakeSpeechProvider(), tone_chunks()))


def test_applies_latency_before_the_first_event_and_chunk() -> None:
    sleep = RecordingSleep()
    provider = FakeSpeechProvider([SCRIPT], latency_s=1.5, sleep=sleep)

    asyncio.run(_transcribe_all(provider, tone_chunks()))
    asyncio.run(_synthesize_all(provider, "Hello."))

    assert sleep.delays == [1.5, 1.5]


def test_zero_latency_never_sleeps() -> None:
    sleep = RecordingSleep()

    asyncio.run(
        _transcribe_all(FakeSpeechProvider([SCRIPT], sleep=sleep), tone_chunks())
    )

    assert sleep.delays == []


def test_latency_is_observable_by_a_caller_deadline() -> None:
    provider = FakeSpeechProvider([SCRIPT], latency_s=1.0)

    async def with_deadline() -> list[TranscriptEvent]:
        return await asyncio.wait_for(
            _transcribe_all(provider, tone_chunks()), timeout=0.01
        )

    with pytest.raises(TimeoutError):
        asyncio.run(with_deadline())


def test_rejects_negative_latency() -> None:
    with pytest.raises(ValueError):
        FakeSpeechProvider(latency_s=-0.1)


@pytest.mark.parametrize(
    ("failure", "error_type"),
    [
        (SimulatedFailure.UNAVAILABLE, ProviderUnavailableError),
        (SimulatedFailure.TIMEOUT, ProviderTimeoutError),
        (SimulatedFailure.UNSUPPORTED_AUDIO, UnsupportedAudioError),
    ],
)
def test_simulates_each_typed_error_in_both_directions(
    failure: SimulatedFailure, error_type: type[SpeechProviderError]
) -> None:
    provider = FakeSpeechProvider([SCRIPT], failure=failure)

    with pytest.raises(error_type):
        asyncio.run(_transcribe_all(provider, tone_chunks()))
    with pytest.raises(error_type):
        asyncio.run(_synthesize_all(provider, "Hello."))


def test_simulated_failure_happens_after_the_latency() -> None:
    sleep = RecordingSleep()
    provider = FakeSpeechProvider(
        latency_s=2.0, failure=SimulatedFailure.TIMEOUT, sleep=sleep
    )

    with pytest.raises(ProviderTimeoutError):
        asyncio.run(_transcribe_all(provider, tone_chunks()))
    assert sleep.delays == [2.0]


def test_rejects_an_empty_chunk() -> None:
    with pytest.raises(UnsupportedAudioError):
        asyncio.run(_transcribe_all(FakeSpeechProvider([SCRIPT]), [b""]))


def test_synthesis_returns_silence_in_the_synthesis_format() -> None:
    text = "x" * 25

    chunks = asyncio.run(_synthesize_all(FakeSpeechProvider(), text))

    total_samples = sum(len(chunk) for chunk in chunks) // 2
    assert total_samples == SYNTHESIS_FORMAT.sample_rate_hz * 250 // 1000
    assert all(set(chunk) == {0} for chunk in chunks)


def test_short_text_still_gets_a_full_first_chunk() -> None:
    chunks = asyncio.run(_synthesize_all(FakeSpeechProvider(), "Hi"))

    assert [len(chunk) for chunk in chunks] == [
        SYNTHESIS_FORMAT.sample_rate_hz // 10 * 2
    ]


def test_transcript_text_is_hidden_from_repr() -> None:
    event = TranscriptEvent(text="something private", is_final=True)

    assert "something private" not in repr(event)


def test_error_messages_never_echo_content() -> None:
    secret = "my private disclosure"
    provider = FakeSpeechProvider(
        [ScriptedTranscript(final=secret)], failure=SimulatedFailure.UNAVAILABLE
    )

    with pytest.raises(ProviderUnavailableError) as error:
        asyncio.run(_synthesize_all(provider, secret))

    assert secret not in str(error.value)


def test_writes_nothing_to_logs_or_disk(
    caplog: pytest.LogCaptureFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    caplog.set_level(logging.DEBUG)
    provider = FakeSpeechProvider([SCRIPT])

    asyncio.run(_transcribe_all(provider, tone_chunks()))
    asyncio.run(_synthesize_all(provider, "Tell me more about that."))
    with pytest.raises(UnsupportedAudioError):
        asyncio.run(_transcribe_all(FakeSpeechProvider([SCRIPT]), [b"\x00"]))

    assert [
        record for record in caplog.records if record.name.startswith("cst_session")
    ] == []
    assert list(tmp_path.iterdir()) == []
