"""WebSocket client for the STT proxy server."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Callable

    from homeassistant.components.stt import SpeechMetadata

_LOGGER = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 300


class STTProxyError(Exception):
    """Raised on protocol-level errors from the STT proxy."""


class STTProxyConnectionError(STTProxyError):
    """Raised when the WebSocket connection is lost."""


class STTProxyClient:
    """Persistent WebSocket client for the STT proxy server."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        token: str,
        on_disconnect: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._url = url
        self._token = token
        self._on_disconnect = on_disconnect
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session_lock = asyncio.Lock()
        self._idle_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        """Open the WebSocket connection to the STT proxy.

        Raises aiohttp.ClientError if the server is unreachable.
        """
        self._ws = await self._session.ws_connect(
            self._url,
            headers={"Authorization": f"Bearer {self._token}"},
            heartbeat=HEARTBEAT_INTERVAL,
        )
        _LOGGER.debug("Connected to STT proxy at %s", self._url)
        self._start_idle_listener()

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        self._stop_idle_listener()
        if self._ws is not None and not self._ws.closed:
            with contextlib.suppress(aiohttp.ClientError):
                await self._ws.close()
        _LOGGER.debug("Disconnected from STT proxy")

    def _start_idle_listener(self) -> None:
        """Start a background task that monitors for connection drops."""
        self._idle_task = asyncio.create_task(self._idle_listen())

    def _stop_idle_listener(self) -> None:
        """Cancel the idle listener if running."""
        if self._idle_task is not None and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None

    async def _idle_listen(self) -> None:
        """Wait for a message while idle; any frame means trouble."""
        try:
            received = await self._ws.receive()
        except asyncio.CancelledError:
            return

        if received.type in (
            aiohttp.WSMsgType.CLOSED,
            aiohttp.WSMsgType.CLOSING,
            aiohttp.WSMsgType.ERROR,
        ):
            _LOGGER.warning("STT proxy connection lost while idle")
        else:
            _LOGGER.warning(
                "Unexpected message from STT proxy while idle: %s", received.type
            )

        if self._on_disconnect is not None:
            self._on_disconnect()

    async def transcribe(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> str | None:
        """Run a full transcription session on the persistent connection.

        Returns the transcript text, or None if no speech was detected.

        Raises STTProxyConnectionError if the WebSocket connection drops.
        Raises STTProxyError on protocol-level errors (connection still usable).
        """
        async with self._session_lock:
            self._stop_idle_listener()

            if self._ws is None or self._ws.closed:
                msg = "WebSocket is not connected"
                raise STTProxyConnectionError(msg)

            try:
                return await self._run_session(metadata, stream)
            except aiohttp.ClientError as err:
                msg = f"WebSocket send failed: {err}"
                raise STTProxyConnectionError(msg) from err
            finally:
                if self._ws is not None and not self._ws.closed:
                    self._start_idle_listener()

    async def _run_session(
        self,
        metadata: SpeechMetadata,
        stream: AsyncIterable[bytes],
    ) -> str | None:
        """Execute the send/receive session protocol."""
        await self._ws.send_json(
            {
                "language": metadata.language,
                "format": metadata.format.value,
                "codec": metadata.codec.value,
                "bit_rate": metadata.bit_rate.value,
                "sample_rate": metadata.sample_rate.value,
                "channel": metadata.channel.value,
            }
        )

        receive_task: asyncio.Task[dict[str, Any]] = asyncio.create_task(
            self._receive_json()
        )

        try:
            async for chunk in stream:
                if receive_task.done():
                    break
                await self._ws.send_bytes(chunk)

            if not receive_task.done():
                await self._ws.send_json({"type": "stop_session"})
        except BaseException:
            if not receive_task.done():
                receive_task.cancel()
                with contextlib.suppress(
                    asyncio.CancelledError, STTProxyConnectionError
                ):
                    await receive_task
            else:
                with contextlib.suppress(Exception):
                    receive_task.result()
            raise

        response = (
            receive_task.result() if receive_task.done() else await receive_task
        )
        return self._handle_session_ended(response)

    @staticmethod
    def _handle_session_ended(response: dict[str, Any]) -> str | None:
        """Extract the transcript from a session_ended response."""
        match response:
            case {"type": "session_ended", "reason": reason, **rest}:
                if reason != "finished":
                    msg = f"Session ended with reason: {reason}"
                    raise STTProxyError(msg)
                transcript = rest.get("transcript")
                _LOGGER.debug("Transcription complete: %s", transcript)
                return transcript
            case {"error": error}:
                raise STTProxyError(error)
            case _:
                msg = f"Unexpected response: {response}"
                raise STTProxyError(msg)

    async def _receive_json(self) -> dict[str, Any]:
        """Receive a JSON text frame from the WebSocket.

        Raises STTProxyConnectionError on closed/error frames.
        """
        received = await self._ws.receive()

        if received.type == aiohttp.WSMsgType.TEXT:
            try:
                return received.json()
            except ValueError as err:
                msg = f"Invalid JSON in WebSocket message: {received.data!r}"
                raise STTProxyError(msg) from err

        if received.type in (
            aiohttp.WSMsgType.CLOSED,
            aiohttp.WSMsgType.CLOSING,
            aiohttp.WSMsgType.ERROR,
        ):
            msg = f"WebSocket connection lost: {received.type}"
            raise STTProxyConnectionError(msg)

        msg = f"Unexpected WebSocket message type: {received.type}"
        raise STTProxyError(msg)
