import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import voluptuous as vol

from custom_components.stt_beta.config_flow import (
    CannotConnectError,
    EmptyKeyError,
    InvalidAuthError,
    STTBetaConfigFlow,
    _build_data_schema,
    _normalize_service_url,
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

    def test_reconfigure_schema_does_not_prefill_key(self) -> None:
        schema = _build_data_schema(
            {
                "stt_service_url": "wss://example.com/stt",
                "stt_service_key": "secret",
            },
            include_key_default=False,
            require_key=False,
        )

        _, key_selector = list(schema.schema.values())

        self.assertEqual(key_selector.config["type"], "password")
        self.assertEqual(next(reversed(schema.schema)).default(), "")

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

    async def test_async_validate_input_strips_service_key(self) -> None:
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
                    "stt_service_url": "wss://example.com/stt",
                    "stt_service_key": "  trimmed-secret  ",
                },
            )

        self.assertEqual(
            validated["stt_service_key"],
            "trimmed-secret",
        )
        mock_client.assert_called_once_with(
            session, "wss://example.com/stt", "trimmed-secret"
        )

    async def test_async_validate_input_rejects_empty_key(self) -> None:
        flow = SimpleNamespace(hass=object())

        with self.assertRaises(EmptyKeyError):
            await async_validate_input(
                flow,
                {
                    "stt_service_url": "wss://example.com/stt",
                    "stt_service_key": "",
                },
            )

    async def test_async_validate_input_rejects_whitespace_only_key(self) -> None:
        flow = SimpleNamespace(hass=object())

        with self.assertRaises(EmptyKeyError):
            await async_validate_input(
                flow,
                {
                    "stt_service_url": "wss://example.com/stt",
                    "stt_service_key": "   ",
                },
            )

    def test_normalize_service_url_wraps_url_parse_errors(self) -> None:
        with (
            patch(
                "custom_components.stt_beta.config_flow.URL",
                side_effect=ValueError("bad"),
            ),
            self.assertRaises(vol.Invalid),
        ):
            _normalize_service_url("wss://example.com/stt")

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


class TestReconfigureFlow(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.entry = SimpleNamespace(
            data={
                "stt_service_url": "wss://example.com/stt",
                "stt_service_key": "existing-secret",
            }
        )
        self.flow = STTBetaConfigFlow()
        self.flow._get_reconfigure_entry = MagicMock(return_value=self.entry)
        self.flow.async_show_form = MagicMock(return_value={"type": "form"})
        self.flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": "abort"}
        )

    async def test_reconfigure_blank_key_keeps_existing_secret(self) -> None:
        with patch(
            "custom_components.stt_beta.config_flow.async_validate_input",
            new=AsyncMock(
                return_value={
                    "stt_service_url": "wss://example.com/new",
                    "stt_service_key": "existing-secret",
                }
            ),
        ) as validate_input:
            result = await self.flow.async_step_reconfigure(
                {
                    "stt_service_url": "wss://example.com/new",
                    "stt_service_key": "",
                }
            )

        self.assertEqual(result, {"type": "abort"})
        validate_input.assert_awaited_once_with(
            self.flow,
            {
                "stt_service_url": "wss://example.com/new",
                "stt_service_key": "existing-secret",
            },
        )
        self.flow.async_update_reload_and_abort.assert_called_once_with(
            self.entry,
            data_updates={
                "stt_service_url": "wss://example.com/new",
                "stt_service_key": "existing-secret",
            },
        )

    async def test_reconfigure_accepts_new_secret(self) -> None:
        with patch(
            "custom_components.stt_beta.config_flow.async_validate_input",
            new=AsyncMock(
                return_value={
                    "stt_service_url": "wss://example.com/new",
                    "stt_service_key": "new-secret",
                }
            ),
        ) as validate_input:
            await self.flow.async_step_reconfigure(
                {
                    "stt_service_url": "wss://example.com/new",
                    "stt_service_key": "new-secret",
                }
            )

        validate_input.assert_awaited_once_with(
            self.flow,
            {
                "stt_service_url": "wss://example.com/new",
                "stt_service_key": "new-secret",
            },
        )

    async def test_reconfigure_shows_blank_password_field(self) -> None:
        result = await self.flow.async_step_reconfigure()

        self.assertEqual(result, {"type": "form"})
        data_schema = self.flow.async_show_form.call_args.kwargs["data_schema"]
        key_marker = next(reversed(data_schema.schema))
        self.assertEqual(key_marker.default(), "")

    async def test_reconfigure_maps_invalid_url_error(self) -> None:
        with patch(
            "custom_components.stt_beta.config_flow.async_validate_input",
            new=AsyncMock(side_effect=vol.Invalid("bad url")),
        ):
            result = await self.flow.async_step_reconfigure(
                {
                    "stt_service_url": "bad",
                    "stt_service_key": "new-secret",
                }
            )

        self.assertEqual(result, {"type": "form"})
        self.assertEqual(
            self.flow.async_show_form.call_args.kwargs["errors"],
            {"base": "invalid_url"},
        )

    async def test_reconfigure_maps_invalid_auth_error(self) -> None:
        with patch(
            "custom_components.stt_beta.config_flow.async_validate_input",
            new=AsyncMock(side_effect=InvalidAuthError),
        ):
            result = await self.flow.async_step_reconfigure(
                {
                    "stt_service_url": "wss://example.com/new",
                    "stt_service_key": "new-secret",
                }
            )

        self.assertEqual(result, {"type": "form"})
        self.assertEqual(
            self.flow.async_show_form.call_args.kwargs["errors"],
            {"base": "invalid_auth"},
        )

    async def test_reconfigure_maps_cannot_connect_error(self) -> None:
        with patch(
            "custom_components.stt_beta.config_flow.async_validate_input",
            new=AsyncMock(side_effect=CannotConnectError),
        ):
            result = await self.flow.async_step_reconfigure(
                {
                    "stt_service_url": "wss://example.com/new",
                    "stt_service_key": "new-secret",
                }
            )

        self.assertEqual(result, {"type": "form"})
        self.assertEqual(
            self.flow.async_show_form.call_args.kwargs["errors"],
            {"base": "cannot_connect"},
        )
