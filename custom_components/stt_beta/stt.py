"""STT platform for STT Beta Integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)

from .client import STTProxyConnectionError, STTProxyError
from .const import SUPPORTED_LANGUAGES

if TYPE_CHECKING:
    from collections.abc import AsyncIterable

    from homeassistant.components.stt import SpeechMetadata
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import STTBetaConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: STTBetaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the STT Beta entity from a config entry."""
    async_add_entities([STTBetaEntity(config_entry)])


class STTBetaEntity(SpeechToTextEntity):
    """STT Beta speech-to-text entity."""

    _attr_name = "STT Beta"

    def __init__(self, config_entry: STTBetaConfigEntry) -> None:
        """Initialize the STT Beta entity."""
        self._config_entry = config_entry
        self._attr_unique_id = config_entry.entry_id
        self._client = config_entry.runtime_data

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bit rates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream via the STT proxy WebSocket."""
        _LOGGER.debug(
            "Starting transcription: language=%s, format=%s, codec=%s",
            metadata.language,
            metadata.format,
            metadata.codec,
        )

        try:
            text = await self._client.transcribe(metadata, stream)
        except STTProxyConnectionError:
            _LOGGER.exception("STT proxy connection lost, scheduling reload")
            self.hass.config_entries.async_schedule_reload(
                self._config_entry.entry_id
            )
            return SpeechResult(text=None, result=SpeechResultState.ERROR)
        except STTProxyError:
            _LOGGER.exception("STT proxy error during transcription")
            return SpeechResult(text=None, result=SpeechResultState.ERROR)

        if text is None:
            _LOGGER.debug("Transcription completed but no speech was detected")
            return SpeechResult(text=None, result=SpeechResultState.ERROR)
        return SpeechResult(text=text, result=SpeechResultState.SUCCESS)
