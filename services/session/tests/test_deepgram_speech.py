"""Deepgram adapter behavior beyond the shared contract (#101).

Every test runs on ``FakeDeepgramTransport`` with generated audio (DAT-6).
"""

import asyncio
import json
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import pytest

from cst_session.speech import (
    ProviderTimeoutError,
    ProviderUnavailableError,
    SpeechProviderError,
    TranscriptEvent,
    UnsupportedAudioError,
)
from cst_session.speech.adapters.deepgram import (
    CLOSE_STREAM,
    FORCE_END_TURN,
    DeepgramSettings,
    DeepgramSpeechProvider,
    listen_url,
    speak_url,
)
from tests.deepgram_fakes import (
    CONNECTED,
    TEST_API_KEY,
    FakeDeepgramTransport,
    FluxScript,
    SpeakScript,
    healthy_flux,
    turn_info,
)
from tests.speech_contract import ProviderCondition
from tests.synthetic_audio import sine_tone, stream, tone_chunks
from tests.test_deepgram_contract import make_deepgram

SETTINGS = DeepgramSettings(api_key=TEST_API_KEY, finalize_timeout_s=0.05)


def _provider(transport: FakeDeepgramTransport) -> DeepgramSpeechProvider:
    return DeepgramSpeechProvider(SETTINGS, transport)


def _query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(url).query)


async def _drain_transcript(
    provider: DeepgramSpeechProvider, chunks: list[bytes]
) -> tuple[list[TranscriptEvent], SpeechProviderError | None]:
    events: list[TranscriptEvent] = []
    try:
        async for event in provider.transcribe(stream(chunks)):
            events.append(event)
    except SpeechProviderError as error:
        return events, error
    return events, None


def _transcribe(
    transport: FakeDeepgramTransport, chunks: list[bytes] | None = None
) -> tuple[list[TranscriptEvent], SpeechProviderError | None]:
    chunks = tone_chunks() if chunks is None else chunks
    return asyncio.run(_drain_transcript(_provider(transport), chunks))


async def _drain_synthesis(
    provider: DeepgramSpeechProvider, text: str
) -> tuple[list[bytes], SpeechProviderError | None]:
    chunks: list[bytes] = []
    try:
        async for chunk in provider.synthesize(text):
            chunks.append(chunk)
    except SpeechProviderError as error:
        return chunks, error
    return chunks, None


def _synthesize(
    transport: FakeDeepgramTransport, text: str = "How are you sleeping?"
) -> tuple[list[bytes], SpeechProviderError | None]:
    return asyncio.run(_drain_synthesis(_provider(transport), text))


# AC2: every request carries mip_opt_out=true


def _every_call_path() -> list[FakeDeepgramTransport]:
    """Run each transcribe and synthesize path the adapter has, and return the
    transports so their recorded requests can be checked."""
    transports: list[FakeDeepgramTransport] = []
    for condition in ProviderCondition:
        provider = make_deepgram(condition)
        transport = provider._transport
        assert isinstance(transport, FakeDeepgramTransport)
        asyncio.run(_drain_transcript(provider, tone_chunks()))
        asyncio.run(_drain_synthesis(provider, "Tell me more about that."))
        transports.append(transport)
    return transports


def test_every_request_on_every_path_carries_mip_opt_out_true() -> None:
    requests = [
        request for transport in _every_call_path() for request in transport.requests
    ]

    assert len(requests) == 2 * len(ProviderCondition)
    assert all(_query(request.url)["mip_opt_out"] == ["true"] for request in requests)


@pytest.mark.parametrize("voice", ["thalia", "apollo", "zeus"])
def test_both_endpoint_urls_carry_mip_opt_out_true(voice: str) -> None:
    settings = DeepgramSettings(api_key=TEST_API_KEY, voice=voice)

    for url in (listen_url(), speak_url(settings)):
        assert _query(url)["mip_opt_out"] == ["true"]


def test_listen_url_asks_flux_for_raw_16_khz_linear16() -> None:
    url = listen_url()

    assert url.startswith("wss://api.deepgram.com/v2/listen?")
    assert _query(url) == {
        "model": ["flux-general-en"],
        "encoding": ["linear16"],
        "sample_rate": ["16000"],
        "mip_opt_out": ["true"],
    }


def test_speak_url_asks_aura_2_for_headerless_24_khz_linear16() -> None:
    url = speak_url(SETTINGS)

    assert url.startswith("https://api.deepgram.com/v1/speak?")
    assert _query(url) == {
        "model": ["aura-2-thalia-en"],
        "encoding": ["linear16"],
        "sample_rate": ["24000"],
        "container": ["none"],
        "mip_opt_out": ["true"],
    }


# The API key


def test_the_key_goes_only_in_the_authorization_header() -> None:
    transport = FakeDeepgramTransport(flux=[healthy_flux()])
    _transcribe(transport)
    _synthesize(transport)

    for request in transport.requests:
        assert request.headers["Authorization"] == f"Token {TEST_API_KEY}"
        assert TEST_API_KEY not in request.url
        assert TEST_API_KEY.encode() not in request.body


def test_the_key_never_appears_in_a_repr() -> None:
    provider = _provider(FakeDeepgramTransport())

    assert TEST_API_KEY not in repr(SETTINGS)
    assert TEST_API_KEY not in repr(provider)


@pytest.mark.parametrize("api_key", ["", "   "])
def test_settings_reject_a_missing_key(api_key: str) -> None:
    with pytest.raises(ValueError):
        DeepgramSettings(api_key=api_key)


@pytest.mark.parametrize(
    "voice", ["", "Thalia", "thalia&mip_opt_out=false", "thalia-en", "a" * 33]
)
def test_settings_reject_a_voice_that_is_not_a_plain_name(voice: str) -> None:
    with pytest.raises(ValueError):
        DeepgramSettings(api_key=TEST_API_KEY, voice=voice)


def test_settings_reject_a_non_positive_finalize_timeout() -> None:
    with pytest.raises(ValueError):
        DeepgramSettings(api_key=TEST_API_KEY, finalize_timeout_s=0)


# Transcription: mapping Flux turns onto transcript events


def test_partials_follow_flux_updates_and_the_forced_end_is_final() -> None:
    events, error = _transcribe(FakeDeepgramTransport(flux=[healthy_flux()]))

    assert error is None
    assert events == [
        TranscriptEvent("I have", is_final=False),
        TranscriptEvent("I have been feeling", is_final=False),
        TranscriptEvent("I have been feeling stuck at work.", is_final=True),
    ]


def test_completed_turns_are_joined_into_one_final_transcript() -> None:
    script = FluxScript(
        per_chunk=[
            turn_info("Update", "I moved here"),
            turn_info("EndOfTurn", "I moved here in August.", "model"),
            turn_info("StartOfTurn", "It has"),
        ],
        on_force_end=[turn_info("EndOfTurn", "It has been lonely.", "manual")],
    )

    events, error = _transcribe(FakeDeepgramTransport(flux=[script]))

    assert error is None
    assert [event.is_final for event in events].count(True) == 1
    assert events[-1].text == "I moved here in August. It has been lonely."
    assert TranscriptEvent("I moved here in August.", is_final=False) in events


def test_an_update_that_does_not_change_the_text_yields_no_event() -> None:
    script = FluxScript(
        per_chunk=[turn_info("Update", "Okay"), turn_info("Update", "Okay")],
        on_force_end=[turn_info("EndOfTurn", "Okay.", "manual")],
    )

    events, _ = _transcribe(FakeDeepgramTransport(flux=[script]))

    assert [event.text for event in events] == ["Okay", "Okay."]


def test_eager_end_of_turn_and_resumed_turns_stay_partial() -> None:
    script = FluxScript(
        per_chunk=[
            turn_info("EagerEndOfTurn", "I think"),
            turn_info("TurnResumed", "I think so"),
        ],
        on_force_end=[turn_info("EndOfTurn", "I think so.", "manual")],
    )

    events, _ = _transcribe(FakeDeepgramTransport(flux=[script]))

    assert [event.is_final for event in events] == [False, False, True]


def test_a_normal_close_after_close_stream_delivers_the_final_event() -> None:
    script = FluxScript(
        per_chunk=[turn_info("Update", "Not much to say")],
        close_on_close_stream=True,
    )

    events, error = _transcribe(FakeDeepgramTransport(flux=[script]))

    assert error is None
    assert events[-1] == TranscriptEvent("Not much to say", is_final=True)


def test_silence_gives_an_empty_final_transcript() -> None:
    events, error = _transcribe(
        FakeDeepgramTransport(flux=[FluxScript(close_on_close_stream=True)])
    )

    assert error is None
    assert events == [TranscriptEvent("", is_final=True)]


def test_non_turn_messages_are_ignored() -> None:
    script = FluxScript(
        per_chunk=[
            CONNECTED,
            json.dumps({"type": "Warning", "code": "W", "description": "slow down"}),
            json.dumps({"type": "ConfigureSuccess", "sequence_id": 2}),
            json.dumps({"type": "SomethingNew"}),
            b"\x00\x01",
        ],
        on_force_end=[turn_info("EndOfTurn", "Fine.", "manual")],
    )

    events, error = _transcribe(FakeDeepgramTransport(flux=[script]))

    assert error is None
    assert events == [TranscriptEvent("Fine.", is_final=True)]


def test_audio_is_sent_in_order_then_force_end_turn_then_close_stream() -> None:
    chunks = [sine_tone(80, frequency_hz=220.0 + i) for i in range(4)]
    transport = FakeDeepgramTransport(flux=[healthy_flux()])

    _transcribe(transport, chunks)

    sent = transport.streams[0]
    assert sent.audio == chunks
    assert sent.texts == [FORCE_END_TURN, CLOSE_STREAM]
    assert sent.closed


# Transcription failures: a typed error, never a final event


def test_a_flux_error_message_is_unavailable_and_hides_the_vendor_text() -> None:
    error_message = json.dumps(
        {"type": "Error", "code": "BAD", "description": "vendor detail 1234"}
    )
    script = FluxScript(per_chunk=[turn_info("Update", "I"), error_message])

    events, error = _transcribe(FakeDeepgramTransport(flux=[script]))

    assert isinstance(error, ProviderUnavailableError)
    assert "vendor detail" not in str(error)
    assert not any(event.is_final for event in events)


@pytest.mark.parametrize(
    "message",
    [
        "not json",
        json.dumps(["TurnInfo"]),
        json.dumps({"type": "TurnInfo", "event": "Update"}),
        json.dumps({"type": "TurnInfo", "event": 3, "transcript": "x"}),
    ],
)
def test_an_unreadable_message_is_unavailable(message: str) -> None:
    events, error = _transcribe(
        FakeDeepgramTransport(flux=[FluxScript(per_chunk=[message])])
    )

    assert isinstance(error, ProviderUnavailableError)
    assert not any(event.is_final for event in events)


def test_a_server_close_before_the_audio_ends_is_unavailable() -> None:
    script = FluxScript(per_chunk=[turn_info("Update", "I")], close_after_chunks=2)

    events, error = _transcribe(FakeDeepgramTransport(flux=[script]), tone_chunks(10))

    assert isinstance(error, ProviderUnavailableError)
    assert not any(event.is_final for event in events)


def test_a_silent_server_after_the_audio_times_out() -> None:
    transport = FakeDeepgramTransport(flux=[FluxScript(hang=True)])

    events, error = _transcribe(transport)

    assert isinstance(error, ProviderTimeoutError)
    assert events == []
    assert transport.streams[0].closed


def test_a_bad_chunk_mid_stream_stops_with_unsupported_audio() -> None:
    transport = FakeDeepgramTransport(flux=[healthy_flux()])
    chunks = [sine_tone(100), sine_tone(100) + b"\x00", sine_tone(100)]

    events, error = _transcribe(transport, chunks)

    assert isinstance(error, UnsupportedAudioError)
    assert not any(event.is_final for event in events)
    assert transport.streams[0].texts == []
    assert transport.streams[0].closed


@pytest.mark.parametrize("chunks", [[], [b""], [sine_tone(100) + b"\x00"]])
def test_bad_or_missing_first_audio_opens_no_connection(chunks: list[bytes]) -> None:
    transport = FakeDeepgramTransport(flux=[healthy_flux()])

    _, error = _transcribe(transport, chunks)

    assert isinstance(error, UnsupportedAudioError)
    assert transport.connections == []


def test_a_connect_failure_is_raised_as_is() -> None:
    transport = FakeDeepgramTransport(
        connect_error=ProviderTimeoutError("speech provider timed out")
    )

    _, error = _transcribe(transport)

    assert isinstance(error, ProviderTimeoutError)


def test_stopping_early_closes_the_stream_and_stops_sending() -> None:
    transport = FakeDeepgramTransport(flux=[healthy_flux()])

    async def first_event_only() -> None:
        events = _provider(transport).transcribe(_endless_audio())
        assert isinstance(events, AsyncIterator)
        await anext(events)
        await events.aclose()  # type: ignore[attr-defined]

    asyncio.run(first_event_only())

    sent = transport.streams[0]
    assert sent.closed
    assert FORCE_END_TURN not in sent.texts


async def _endless_audio() -> AsyncIterator[bytes]:
    while True:
        await asyncio.sleep(0)
        yield sine_tone(80)


# Synthesis


def test_synthesis_posts_the_text_as_json() -> None:
    transport = FakeDeepgramTransport()

    _synthesize(transport, "Can you say more?")

    request = transport.posts[0]
    assert json.loads(request.body) == {"text": "Can you say more?"}
    assert request.headers["Content-Type"] == "application/json"


def test_synthesis_rechunks_odd_sized_bodies_into_whole_samples() -> None:
    body = bytes(range(256)) * 10
    pieces = [body[:3], body[3:4], body[4:1001], body[1001:]]
    transport = FakeDeepgramTransport(speak=SpeakScript(chunks=pieces))

    chunks, error = _synthesize(transport)

    assert error is None
    assert b"".join(chunks) == body
    assert all(chunk and len(chunk) % 2 == 0 for chunk in chunks)


@pytest.mark.parametrize(
    "content_type", ["audio/l16;rate=24000", "audio/L16; rate=24000", "audio/l16"]
)
def test_synthesis_accepts_24_khz_l16(content_type: str) -> None:
    transport = FakeDeepgramTransport(speak=SpeakScript(content_type=content_type))

    _, error = _synthesize(transport)

    assert error is None


@pytest.mark.parametrize(
    "content_type", ["audio/wav", "audio/mpeg", "audio/l16;rate=16000", ""]
)
def test_synthesis_rejects_any_other_audio_format(content_type: str) -> None:
    transport = FakeDeepgramTransport(speak=SpeakScript(content_type=content_type))

    chunks, error = _synthesize(transport)

    assert isinstance(error, ProviderUnavailableError)
    assert chunks == []


@pytest.mark.parametrize("status", [400, 401, 402, 429, 500, 503])
def test_synthesis_maps_an_error_status_to_unavailable(status: int) -> None:
    transport = FakeDeepgramTransport(speak=SpeakScript(status=status))

    chunks, error = _synthesize(transport)

    assert isinstance(error, ProviderUnavailableError)
    assert chunks == []


@pytest.mark.parametrize(
    "pieces", [[], [b""], [bytes(10), b"\x00"]], ids=["none", "empty", "half-sample"]
)
def test_synthesis_rejects_a_missing_or_cut_body(pieces: list[bytes]) -> None:
    transport = FakeDeepgramTransport(speak=SpeakScript(chunks=pieces))

    _, error = _synthesize(transport)

    assert isinstance(error, ProviderUnavailableError)


def test_a_failure_mid_body_is_raised_after_the_audio_already_sent() -> None:
    script = SpeakScript(
        chunks=[bytes(480)],
        error_after_chunks=ProviderTimeoutError("speech provider timed out"),
    )

    chunks, error = _synthesize(FakeDeepgramTransport(speak=script))

    assert chunks == [bytes(480)]
    assert isinstance(error, ProviderTimeoutError)


def test_empty_text_is_rejected_before_any_request() -> None:
    transport = FakeDeepgramTransport()

    with pytest.raises(ValueError):
        _synthesize(transport, "\n ")

    assert transport.posts == []
