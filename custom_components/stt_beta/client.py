"""WebSocket client for the STT proxy server."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

if TYPE_CHECKING:
    from collections.abc import AsyncIterable

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
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._url = url
        self._token = token
        self._ws: aiohttp.ClientWebSocketResponse | None = None

    @property
    def connected(self) -> bool:
        """Return True if the WebSocket connection is open."""
        return self._ws is not None and not self._ws.closed

    async def connect(self) -> None:
        """Open the WebSocket connection to the STT proxy.

        Raises aiohttp.ClientError if the server is unreachable.
        """  # noqa: D213
        self._ws = await self._session.ws_connect(
            self._url,
            headers={"Authorization": f"Bearer {self._token}"},
            heartbeat=HEARTBEAT_INTERVAL,
        )
        _LOGGER.debug("Connected to STT proxy at %s", self._url)

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        _LOGGER.debug("Disconnected from STT proxy")

    async def transcribe(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> str | None:
        """Run a full transcription session on the persistent connection.

        Returns the transcript text, or None if no speech was detected.

        Raises STTProxyConnectionError if the WebSocket connection drops.
        Raises STTProxyError on protocol-level errors (connection still usable).
        """  # noqa: D213
        if not self.connected:
            msg = "WebSocket is not connected"
            raise STTProxyConnectionError(msg)

        ws = self._ws

        await ws.send_json(
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
                await ws.send_bytes(chunk)

            if not receive_task.done():
                await ws.send_json({"type": "stop_session"})
        except Exception:
            if not receive_task.done():
                receive_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await receive_task
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
        """  # noqa: D213
        ws = self._ws
        if ws is None:
            msg = "WebSocket is not connected"
            raise STTProxyConnectionError(msg)

        received = await ws.receive()

        if received.type == aiohttp.WSMsgType.TEXT:
            return json.loads(received.data)

        if received.type in (
            aiohttp.WSMsgType.CLOSED,
            aiohttp.WSMsgType.CLOSING,
            aiohttp.WSMsgType.ERROR,
        ):
            msg = f"WebSocket connection lost: {received.type}"
            raise STTProxyConnectionError(msg)

        msg = f"Unexpected WebSocket message type: {received.type}"
        raise STTProxyError(msg)
