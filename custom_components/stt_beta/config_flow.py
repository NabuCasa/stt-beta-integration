"""Config flow for STT Beta Integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from . import DOMAIN
from .const import CONF_STT_SERVICE_KEY, CONF_STT_SERVICE_URL

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STT_SERVICE_URL): str,
        vol.Required(CONF_STT_SERVICE_KEY): str,
    }
)


class STTBetaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for STT Beta."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="STT Beta", data=user_input)

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
