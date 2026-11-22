"""The network transport for the Deepgram adapter: ``websockets`` and ``httpx``.

Every library failure becomes ``ProviderUnavailableError`` or
``ProviderTimeoutError``, so nothing vendor- or library-specific crosses the
speech interface. The ``websockets`` logger is disabled because its debug
output includes the handshake headers, and so the API key.
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Final

import httpx
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosedOK, InvalidStatus, WebSocketException

from cst_session.speech.adapters.deepgram import DeepgramStream, SpeakResponse
from cst_session.speech.errors import ProviderTimeoutError, ProviderUnavailableError

MAX_MESSAGE_BYTES: Final = 1 << 20

_SILENT_LOGGER: Final = logging.getLogger(__name__ + ".websockets")
_SILENT_LOGGER.disabled = True
_SILENT_LOGGER.propagate = False


@dataclass(frozen=True)
class TransportTimeouts:
    connect_s: float = 5.0
    read_s: float = 10.0

    def __post_init__(self) -> None:
        if self.connect_s <= 0 or self.read_s <= 0:
            raise ValueError("transport timeouts must be positive")


class _WebSocketStream:
    def __init__(self, connection: ClientConnection) -> None:
        self._connection = connection

    async def send_audio(self, chunk: bytes) -> None:
        await _guarded(self._connection.send(chunk))

    async def send_text(self, message: str) -> None:
        await _guarded(self._connection.send(message))

    async def receive(self) -> str | bytes | None:
        try:
            return await self._connection.recv()
        except ConnectionClosedOK:
            return None
        except WebSocketException as error:
            raise ProviderUnavailableError(
                "speech provider closed the stream"
            ) from error
        except OSError as error:
            raise ProviderUnavailableError("speech provider is unavailable") from error


async def _guarded(sending: Awaitable[None]) -> None:
    try:
        await sending
    except WebSocketException as error:
        raise ProviderUnavailableError("speech provider closed the stream") from error
    except OSError as error:
        raise ProviderUnavailableError("speech provider is unavailable") from error


class HttpxWebsocketsTransport:
    """A ``DeepgramTransport`` over ``websockets`` (STT) and ``httpx`` (TTS).

    It holds one ``httpx.AsyncClient`` so TTS requests reuse connections, which
    keeps TLS setup out of each turn's latency (PA-2). Call ``aclose`` on
    shutdown.
    """

    def __init__(
        self,
        timeouts: TransportTimeouts | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._timeouts = timeouts or TransportTimeouts()
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(
                self._timeouts.read_s, connect=self._timeouts.connect_s
            )
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    @asynccontextmanager
    async def connect(
        self, url: str, headers: Mapping[str, str]
    ) -> AsyncIterator[DeepgramStream]:
        try:
            connection = await connect(
                url,
                additional_headers=dict(headers),
                open_timeout=self._timeouts.connect_s,
                max_size=MAX_MESSAGE_BYTES,
                logger=_SILENT_LOGGER,
            )
        except TimeoutError as error:
            raise ProviderTimeoutError("speech provider timed out") from error
        except InvalidStatus as error:
            raise ProviderUnavailableError(
                "speech provider refused the request"
            ) from error
        except (WebSocketException, OSError) as error:
            raise ProviderUnavailableError("speech provider is unavailable") from error
        try:
            yield _WebSocketStream(connection)
        finally:
            await connection.close()

    @asynccontextmanager
    async def post(
        self, url: str, headers: Mapping[str, str], body: bytes
    ) -> AsyncIterator[SpeakResponse]:
        try:
            async with self._http.stream(
                "POST", url, headers=dict(headers), content=body
            ) as response:
                yield SpeakResponse(
                    status=response.status_code,
                    content_type=response.headers.get("content-type", ""),
                    body=_typed_body(response.aiter_bytes()),
                )
        except httpx.TimeoutException as error:
            raise ProviderTimeoutError("speech provider timed out") from error
        except httpx.TransportError as error:
            raise ProviderUnavailableError("speech provider is unavailable") from error


async def _typed_body(chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """The response body, with read failures turned into typed errors."""
    try:
        async for chunk in chunks:
            yield chunk
    except httpx.TimeoutException as error:
        raise ProviderTimeoutError("speech provider timed out") from error
    except httpx.TransportError as error:
        raise ProviderUnavailableError("speech provider is unavailable") from error
