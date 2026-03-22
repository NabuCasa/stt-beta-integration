import unittest
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResultState,
)

from custom_components.stt_beta.client import STTProxyConnectionError, STTProxyError
from custom_components.stt_beta.stt import STTBetaEntity


def _speech_metadata() -> SpeechMetadata:
    return SpeechMetadata(
        language="en",
        format=AudioFormats.WAV,
        codec=AudioCodecs.PCM,
        bit_rate=AudioBitRates.BITRATE_16,
        sample_rate=AudioSampleRates.SAMPLERATE_16000,
        channel=AudioChannels.CHANNEL_MONO,
    )


async def _empty_stream():
    if False:
        yield b""


class TestSTTBetaEntity(unittest.IsolatedAsyncioTestCase):
    async def test_no_speech_returns_error_without_reload(self) -> None:
        client = MagicMock()
        client.transcribe = AsyncMock(return_value=None)
        entry = MagicMock(entry_id="entry-1", runtime_data=client)
        hass = MagicMock()
        entity = STTBetaEntity(entry)
        entity.hass = hass

        result = await entity.async_process_audio_stream(
            _speech_metadata(), _empty_stream()
        )

        self.assertEqual(result.result, SpeechResultState.ERROR)
        self.assertIsNone(result.text)
        hass.config_entries.async_schedule_reload.assert_not_called()

    async def test_connection_error_schedules_reload(self) -> None:
        client = MagicMock()
        client.transcribe = AsyncMock(side_effect=STTProxyConnectionError("lost"))
        entry = MagicMock(entry_id="entry-1", runtime_data=client)
        hass = MagicMock()
        entity = STTBetaEntity(entry)
        entity.hass = hass

        result = await entity.async_process_audio_stream(
            _speech_metadata(), _empty_stream()
        )

        self.assertEqual(result.result, SpeechResultState.ERROR)
        hass.config_entries.async_schedule_reload.assert_called_once_with("entry-1")

    async def test_proxy_error_returns_error_without_reload(self) -> None:
        client = MagicMock()
        client.transcribe = AsyncMock(side_effect=STTProxyError("protocol"))
        entry = MagicMock(entry_id="entry-1", runtime_data=client)
        hass = MagicMock()
        entity = STTBetaEntity(entry)
        entity.hass = hass

        result = await entity.async_process_audio_stream(
            _speech_metadata(), _empty_stream()
        )

        self.assertEqual(result.result, SpeechResultState.ERROR)
        hass.config_entries.async_schedule_reload.assert_not_called()
