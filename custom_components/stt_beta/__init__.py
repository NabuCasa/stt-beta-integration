"""STT Beta Integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import STTProxyClient
from .const import CONF_STT_SERVICE_KEY, CONF_STT_SERVICE_URL

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

type STTBetaConfigEntry = ConfigEntry[STTProxyClient]

DOMAIN = "stt_beta"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: STTBetaConfigEntry
) -> bool:
    """Set up STT Beta from a config entry."""
    session = async_get_clientsession(hass)
    client = STTProxyClient(
        session,
        entry.data[CONF_STT_SERVICE_URL],
        entry.data[CONF_STT_SERVICE_KEY],
        on_disconnect=lambda: hass.config_entries.async_schedule_reload(entry.entry_id),
    )

    try:
        await client.connect()
    except (aiohttp.ClientError, TimeoutError) as err:
        msg = f"Unable to connect to STT proxy: {err}"
        raise ConfigEntryNotReady(msg) from err

    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, ["stt"])
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: STTBetaConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["stt"])
    if unload_ok:
        await entry.runtime_data.disconnect()
    return unload_ok
