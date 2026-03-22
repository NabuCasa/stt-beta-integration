import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch

import aiohttp
from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
)

import custom_components.stt_beta.client as stt_client_module
from custom_components.stt_beta.client import (
    STTProxyClient,
    STTProxyConnectionError,
    STTProxyError,
)


class _FakeMessage:
    def __init__(self, payload: dict[str, str]) -> None:
        self.type = aiohttp.WSMsgType.TEXT
        self.data = json.dumps(payload)
        self._payload = payload

    def json(self) -> dict[str, str]:
        return self._payload


class _FakeWebSocket:
    def __init__(
        self,
        *,
        initial_messages: list[_FakeMessage] | None = None,
        terminal_response: dict[str, str] | None = None,
    ) -> None:
        self.closed = False
        self.sent_bytes: list[bytes] = []
        self.sent_json: list[dict[str, str]] = []
        self._messages: asyncio.Queue[_FakeMessage] = asyncio.Queue()
        self._terminal_response = terminal_response

        for message in initial_messages or []:
            self._messages.put_nowait(message)

    async def send_json(self, data: dict[str, str]) -> None:
        self.sent_json.append(data)
        if data == {"type": "stop_session"} and self._terminal_response is not None:
            self._messages.put_nowait(_FakeMessage(self._terminal_response))
            self._terminal_response = None

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(bytes(data))

    async def receive(self) -> _FakeMessage:
        return await self._messages.get()

    async def close(self) -> None:
        self.closed = True


def _speech_metadata(codec: AudioCodecs) -> SpeechMetadata:
    return SpeechMetadata(
        language="en",
        format=AudioFormats.WAV,
        codec=codec,
        bit_rate=AudioBitRates.BITRATE_16,
        sample_rate=AudioSampleRates.SAMPLERATE_16000,
        channel=AudioChannels.CHANNEL_MONO,
    )


async def _stream_chunks(chunks: list[bytes]):
    for chunk in chunks:
        await asyncio.sleep(0)
        yield chunk


class TestSTTProxyClient(unittest.IsolatedAsyncioTestCase):
    async def test_run_session_waits_for_terminal_response(self) -> None:
        ws = _FakeWebSocket(
            initial_messages=[_FakeMessage({"type": "partial_result", "text": "hel"})],
            terminal_response={
                "type": "session_ended",
                "reason": "finished",
                "transcript": "hello",
            },
        )
        client = STTProxyClient(MagicMock(), "wss://example.com/stt", "token")
        client._ws = ws

        result = await client._run_session(
            _speech_metadata(AudioCodecs.PCM),
            _stream_chunks([b"ab", b"cd"]),
        )

        self.assertEqual(result, "hello")
        self.assertEqual(ws.sent_bytes, [b"ab", b"cd"])
        self.assertEqual(ws.sent_json[-1], {"type": "stop_session"})

    async def test_run_session_preserves_opus_chunk_boundaries(self) -> None:
        ws = _FakeWebSocket(
            terminal_response={
                "type": "session_ended",
                "reason": "finished",
                "transcript": "ok",
            }
        )
        client = STTProxyClient(MagicMock(), "wss://example.com/stt", "token")
        client._ws = ws

        result = await client._run_session(
            _speech_metadata(AudioCodecs.OPUS),
            _stream_chunks([b"a", b"bc"]),
        )

        self.assertEqual(result, "ok")
        self.assertEqual(ws.sent_bytes, [b"a", b"bc"])

    async def test_run_session_rejects_incomplete_pcm_frames(self) -> None:
        ws = _FakeWebSocket()
        client = STTProxyClient(MagicMock(), "wss://example.com/stt", "token")
        client._ws = ws

        with self.assertRaisesRegex(
            STTProxyError, "Incomplete PCM audio frame received from stream"
        ):
            await client._run_session(
                _speech_metadata(AudioCodecs.PCM),
                _stream_chunks([b"a"]),
            )

        self.assertTrue(ws.closed)
        self.assertIsNone(client._ws)

    def test_handle_session_ended_rejects_unexpected_payload(self) -> None:
        with self.assertRaisesRegex(STTProxyError, "Unexpected response"):
            STTProxyClient._handle_session_ended({"type": "session_started"})

    async def test_receive_terminal_response_times_out(self) -> None:
        ws = _FakeWebSocket(
            initial_messages=[_FakeMessage({"type": "partial", "text": "x"})]
        )
        client = STTProxyClient(MagicMock(), "wss://example.com/stt", "token")
        client._ws = ws

        with (
            patch.object(
                stt_client_module, "RECEIVE_TERMINAL_RESPONSE_TIMEOUT", 0.05
            ),
            self.assertRaisesRegex(
                STTProxyConnectionError,
                "Timed out waiting for terminal response",
            ),
        ):
            await client._receive_terminal_response()
