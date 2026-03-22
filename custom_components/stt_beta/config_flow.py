"""Config flow for STT Beta Integration."""

from __future__ import annotations

import contextlib
import logging

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from yarl import URL

from . import DOMAIN
from .client import STTProxyClient
from .const import CONF_STT_SERVICE_KEY, CONF_STT_SERVICE_URL

_LOGGER = logging.getLogger(__name__)


class CannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuthError(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class EmptyKeyError(HomeAssistantError):
    """Error to indicate the STT service key is missing."""


def _build_data_schema(
    data: dict[str, str] | None = None,
    *,
    include_key_default: bool = True,
    require_key: bool = True,
) -> vol.Schema:
    """Build the config schema with selectors and defaults."""
    data = data or {}
    key_marker = vol.Required if require_key else vol.Optional
    key_default = data.get(CONF_STT_SERVICE_KEY, "") if include_key_default else ""

    return vol.Schema(
        {
            vol.Required(
                CONF_STT_SERVICE_URL, default=data.get(CONF_STT_SERVICE_URL, "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            ),
            key_marker(
                CONF_STT_SERVICE_KEY,
                default=key_default,
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
        }
    )


def _normalize_service_url(url: str) -> str:
    """Validate and normalize the configured STT proxy URL."""
    normalized = url.strip()
    if not normalized:
        msg = "URL cannot be empty"
        raise vol.Invalid(msg)

    try:
        parsed = URL(normalized)
    except (TypeError, ValueError) as err:
        msg = "URL must be a valid ws:// or wss:// address"
        raise vol.Invalid(msg) from err

    if parsed.scheme not in ("ws", "wss") or parsed.host is None:
        msg = "URL must be a valid ws:// or wss:// address"
        raise vol.Invalid(msg)

    return str(parsed)


async def async_validate_input(
    flow: ConfigFlow, user_input: dict[str, str]
) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    service_key = user_input[CONF_STT_SERVICE_KEY].strip()
    validated_data = {
        CONF_STT_SERVICE_URL: _normalize_service_url(user_input[CONF_STT_SERVICE_URL]),
        CONF_STT_SERVICE_KEY: service_key,
    }

    if not service_key:
        msg = "Service key cannot be empty"
        raise EmptyKeyError(msg)

    client = STTProxyClient(
        async_get_clientsession(flow.hass),
        validated_data[CONF_STT_SERVICE_URL],
        service_key,
    )

    try:
        await client.connect()
    except aiohttp.WSServerHandshakeError as err:
        if err.status in (401, 403):
            raise InvalidAuthError from err
        raise CannotConnectError from err
    except (aiohttp.ClientError, TimeoutError) as err:
        raise CannotConnectError from err
    finally:
        with contextlib.suppress(Exception):
            await client.disconnect()

    return validated_data


class STTBetaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for STT Beta."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            try:
                validated_data = await async_validate_input(self, user_input)
            except vol.Invalid:
                errors["base"] = "invalid_url"
            except EmptyKeyError:
                errors["base"] = "key_required"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception validating STT Beta config")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="STT Beta", data=validated_data)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_data_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            reconfigure_input = dict(user_input)
            if not reconfigure_input.get(CONF_STT_SERVICE_KEY, "").strip():
                reconfigure_input[CONF_STT_SERVICE_KEY] = entry.data[
                    CONF_STT_SERVICE_KEY
                ]

            try:
                validated_data = await async_validate_input(self, reconfigure_input)
            except vol.Invalid:
                errors["base"] = "invalid_url"
            except EmptyKeyError:
                errors["base"] = "key_required"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception reconfiguring STT Beta")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=validated_data
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_data_schema(
                dict(entry.data), include_key_default=False, require_key=False
            ),
            errors=errors,
        )
