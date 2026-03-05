"""STT platform for STT Beta Integration."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterable

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the STT Beta entity from a config entry."""
    async_add_entities([STTBetaEntity(config_entry)])


class STTBetaEntity(SpeechToTextEntity):
    """STT Beta speech-to-text entity."""

    _attr_name = "STT Beta"

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the STT Beta entity."""
        self._config_entry = config_entry
        self._attr_unique_id = config_entry.entry_id

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return ["en-US"]

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
        """Process an audio stream to STT service.

        TODO: Implement full STT backend processing here.
        Consume the audio stream and return the transcribed text.
        """
        _LOGGER.debug(
            "Received audio stream: language=%s, format=%s, codec=%s",
            metadata.language,
            metadata.format,
            metadata.codec,
        )

        # Drain the stream and track total bytes received
        total_bytes = 0
        async for chunk in stream:
            total_bytes += len(chunk)
        _LOGGER.debug("Received %d bytes of audio data", total_bytes)

        # Stub: return an error result until a real STT backend is wired up
        return SpeechResult(text=None, result=SpeechResultState.ERROR)
