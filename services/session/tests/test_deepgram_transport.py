"""The real ``websockets`` + ``httpx`` transport, against local stand-ins (#101).

A WebSocket server on 127.0.0.1 plays Flux, and ``httpx.MockTransport`` plays
``/v1/speak``. Nothing reaches Deepgram, and the audio is generated (DAT-6).
These tests check what actually goes on the wire.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

from cst_session.speech import (
    ProviderTimeoutError,
    ProviderUnavailableError,
    SpeechProviderError,
    TranscriptEvent,
)
from cst_session.speech.adapters import deepgram
from cst_session.speech.adapters.deepgram import (
    CLOSE_STREAM,
    FORCE_END_TURN,
    DeepgramSettings,
    DeepgramSpeechProvider,
)
from cst_session.speech.adapters.deepgram_transport import (
    HttpxWebsocketsTransport,
    TransportTimeouts,
)
from tests.deepgram_fakes import TEST_API_KEY, turn_info
from tests.synthetic_audio import stream, tone_chunks

FAST = TransportTimeouts(connect_s=0.5, read_s=0.5)
SETTINGS = DeepgramSettings(api_key=TEST_API_KEY, finalize_timeout_s=1.0)

Handler = Callable[[ServerConnection], Awaitable[None]]


class FluxServer:
    """Records each handshake, then runs ``handler`` on the connection."""

    def __init__(self, handler: Handler, reject_with: HTTPStatus | None = None) -> None:
        self._handler = handler
        self._reject_with = reject_with
        self.paths: list[str] = []
        self.headers: list[Headers] = []
        self.received: list[str | bytes] = []

    def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        self.paths.append(request.path)
        self.headers.append(request.headers)
        if self._reject_with is not None:
            return connection.respond(self._reject_with, "rejected\n")
        return None

    async def handle(self, connection: ServerConnection) -> None:
        await self._handler(connection)


async def flux_like(server: FluxServer, connection: ServerConnection) -> None:
    """Answer partials during audio, the forced end turn, then close on CloseStream."""
    async for message in connection:
        server.received.append(message)
        if isinstance(message, bytes):
            await connection.send(turn_info("Update", "I have been"))
        elif message == FORCE_END_TURN:
            await connection.send(
                turn_info("EndOfTurn", "I have been tired.", "manual")
            )
        elif message == CLOSE_STREAM:
            await connection.close()
            return


async def _transcribe_against(
    server: FluxServer,
    monkeypatch: pytest.MonkeyPatch,
    transport: HttpxWebsocketsTransport | None = None,
) -> tuple[list[TranscriptEvent], SpeechProviderError | None]:
    async with serve(
        server.handle, "127.0.0.1", 0, process_request=server.process_request
    ) as ws_server:
        port = ws_server.sockets[0].getsockname()[1]
        monkeypatch.setattr(deepgram, "LISTEN_URL", f"ws://127.0.0.1:{port}/v2/listen")
        transport = transport or HttpxWebsocketsTransport(FAST)
        provider = DeepgramSpeechProvider(SETTINGS, transport)
        events: list[TranscriptEvent] = []
        try:
            async for event in provider.transcribe(stream(tone_chunks(3))):
                events.append(event)
        except SpeechProviderError as error:
            return events, error
        finally:
            await transport.aclose()
        return events, None


def _flux_server(**kwargs: Any) -> FluxServer:
    server: FluxServer

    async def handler(connection: ServerConnection) -> None:
        await flux_like(server, connection)

    server = FluxServer(handler, **kwargs)
    return server


# Flux over a real WebSocket


def test_transcription_round_trip_over_a_real_websocket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _flux_server()

    events, error = asyncio.run(_transcribe_against(server, monkeypatch))

    assert error is None
    assert events[-1] == TranscriptEvent("I have been tired.", is_final=True)
    assert [message for message in server.received if isinstance(message, str)] == [
        FORCE_END_TURN,
        CLOSE_STREAM,
    ]
    assert sum(isinstance(message, bytes) for message in server.received) == 3


def test_the_handshake_carries_mip_opt_out_and_the_key_header_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _flux_server()

    asyncio.run(_transcribe_against(server, monkeypatch))

    (path,) = server.paths
    assert parse_qs(urlsplit(path).query)["mip_opt_out"] == ["true"]
    assert TEST_API_KEY not in path
    assert server.headers[0]["Authorization"] == f"Token {TEST_API_KEY}"


@pytest.mark.parametrize(
    "status", [HTTPStatus.UNAUTHORIZED, HTTPStatus.PAYMENT_REQUIRED]
)
def test_a_rejected_handshake_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, status: HTTPStatus
) -> None:
    server = _flux_server(reject_with=status)

    events, error = asyncio.run(_transcribe_against(server, monkeypatch))

    assert isinstance(error, ProviderUnavailableError)
    assert events == []


def test_an_abnormal_close_mid_stream_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def drop(connection: ServerConnection) -> None:
        await connection.recv()
        await connection.close(code=1011, reason="internal error")

    events, error = asyncio.run(_transcribe_against(FluxServer(drop), monkeypatch))

    assert isinstance(error, ProviderUnavailableError)
    assert not any(event.is_final for event in events)


def test_a_connection_dropped_during_the_handshake_is_unavailable() -> None:
    async def run() -> SpeechProviderError | None:
        async def hang_up(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            writer.close()

        tcp = await asyncio.start_server(hang_up, "127.0.0.1", 0)
        port = tcp.sockets[0].getsockname()[1]
        transport = HttpxWebsocketsTransport(FAST)
        try:
            async with transport.connect(f"ws://127.0.0.1:{port}/v2/listen", {}):
                return None
        except SpeechProviderError as error:
            return error
        finally:
            await transport.aclose()
            tcp.close()

    assert isinstance(asyncio.run(run()), ProviderUnavailableError)


def test_a_handshake_that_never_answers_times_out() -> None:
    async def run() -> SpeechProviderError | None:
        async def silent(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            await reader.read()

        tcp = await asyncio.start_server(silent, "127.0.0.1", 0)
        port = tcp.sockets[0].getsockname()[1]
        transport = HttpxWebsocketsTransport(TransportTimeouts(connect_s=0.2))
        try:
            async with transport.connect(f"ws://127.0.0.1:{port}/v2/listen", {}):
                return None
        except SpeechProviderError as error:
            return error
        finally:
            await transport.aclose()
            tcp.close()

    assert isinstance(asyncio.run(run()), ProviderTimeoutError)


# Aura-2 over httpx


class _FailingBody(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield bytes(480)
        raise httpx.ReadError("connection reset")


def _speak_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _synthesize_with(
    client: httpx.AsyncClient,
) -> tuple[list[bytes], SpeechProviderError | None]:
    transport = HttpxWebsocketsTransport(FAST, http_client=client)
    provider = DeepgramSpeechProvider(SETTINGS, transport)
    chunks: list[bytes] = []
    try:
        async for chunk in provider.synthesize("What brings you in today?"):
            chunks.append(chunk)
    except SpeechProviderError as error:
        return chunks, error
    finally:
        await transport.aclose()
    return chunks, None


def test_synthesis_round_trip_over_httpx() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, headers={"content-type": "audio/l16;rate=24000"}, content=bytes(9600)
        )

    chunks, error = asyncio.run(_synthesize_with(_speak_client(handler)))

    assert error is None
    assert b"".join(chunks) == bytes(9600)
    (request,) = seen
    assert request.url.params["mip_opt_out"] == "true"
    assert request.headers["authorization"] == f"Token {TEST_API_KEY}"
    assert json.loads(request.content) == {"text": "What brings you in today?"}


@pytest.mark.parametrize(
    ("raised", "error_type"),
    [
        (httpx.ConnectTimeout("slow"), ProviderTimeoutError),
        (httpx.ReadTimeout("slow"), ProviderTimeoutError),
        (httpx.ConnectError("refused"), ProviderUnavailableError),
    ],
)
def test_http_failures_become_typed_errors(
    raised: httpx.HTTPError, error_type: type[SpeechProviderError]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise raised

    _, error = asyncio.run(_synthesize_with(_speak_client(handler)))

    assert isinstance(error, error_type)


def test_a_read_failure_mid_body_is_unavailable_after_the_first_audio() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, headers={"content-type": "audio/l16;rate=24000"}, stream=_FailingBody()
        )

    chunks, error = asyncio.run(_synthesize_with(_speak_client(handler)))

    assert chunks == [bytes(480)]
    assert isinstance(error, ProviderUnavailableError)


def test_an_error_status_body_never_reaches_the_error_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"err_code": "INVALID", "err_msg": "echo: What brings you in"}
        )

    _, error = asyncio.run(_synthesize_with(_speak_client(handler)))

    assert isinstance(error, ProviderUnavailableError)
    assert "What brings you" not in str(error)


# Logs


def test_no_log_record_contains_the_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, headers={"content-type": "audio/l16;rate=24000"}, content=bytes(960)
        )

    asyncio.run(_transcribe_against(_flux_server(), monkeypatch))
    asyncio.run(_synthesize_with(_speak_client(handler)))

    # The local stand-in server logs the headers it receives. It is test code,
    # so only the client side, which is ours, is checked.
    client_records = [
        record
        for record in caplog.records
        if not record.name.startswith("websockets.server")
    ]
    assert client_records
    assert all(TEST_API_KEY not in record.getMessage() for record in client_records)


def test_timeouts_must_be_positive() -> None:
    with pytest.raises(ValueError):
        TransportTimeouts(connect_s=0)
