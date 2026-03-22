import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import voluptuous as vol

from custom_components.stt_beta.config_flow import (
    InvalidAuthError,
    _build_data_schema,
    async_validate_input,
)


class TestConfigFlow(unittest.IsolatedAsyncioTestCase):
    def test_build_data_schema_uses_url_and_password_selectors(self) -> None:
        schema = _build_data_schema(
            {
                "stt_service_url": "wss://example.com/stt",
                "stt_service_key": "secret",
            }
        )

        url_selector, key_selector = list(schema.schema.values())

        self.assertEqual(url_selector.config["type"], "url")
        self.assertEqual(key_selector.config["type"], "password")

    async def test_async_validate_input_normalizes_url_and_disconnects(self) -> None:
        flow = SimpleNamespace(hass=object())
        session = object()
        client = MagicMock()
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()

        with (
            patch(
                "custom_components.stt_beta.config_flow.async_get_clientsession",
                return_value=session,
            ),
            patch(
                "custom_components.stt_beta.config_flow.STTProxyClient",
                return_value=client,
            ) as mock_client,
        ):
            validated = await async_validate_input(
                flow,
                {
                    "stt_service_url": "  wss://example.com/stt  ",
                    "stt_service_key": "secret",
                },
            )

        self.assertEqual(
            validated,
            {
                "stt_service_url": "wss://example.com/stt",
                "stt_service_key": "secret",
            },
        )
        mock_client.assert_called_once_with(session, "wss://example.com/stt", "secret")
        client.connect.assert_awaited_once()
        client.disconnect.assert_awaited_once()

    async def test_async_validate_input_rejects_invalid_url(self) -> None:
        flow = SimpleNamespace(hass=object())

        with self.assertRaises(vol.Invalid):
            await async_validate_input(
                flow,
                {
                    "stt_service_url": "https://example.com/stt",
                    "stt_service_key": "secret",
                },
            )

    async def test_async_validate_input_rejects_invalid_auth(self) -> None:
        flow = SimpleNamespace(hass=object())
        client = MagicMock()
        client.connect = AsyncMock(
            side_effect=aiohttp.WSServerHandshakeError(
                None, (), status=401, message="unauthorized"
            )
        )
        client.disconnect = AsyncMock()

        with (
            patch(
                "custom_components.stt_beta.config_flow.async_get_clientsession",
                return_value=object(),
            ),
            patch(
                "custom_components.stt_beta.config_flow.STTProxyClient",
                return_value=client,
            ),
            self.assertRaises(InvalidAuthError),
        ):
            await async_validate_input(
                flow,
                {
                    "stt_service_url": "wss://example.com/stt",
                    "stt_service_key": "secret",
                },
            )

        client.disconnect.assert_awaited_once()
