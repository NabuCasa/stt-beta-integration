"""Tests for custom_components.stt_beta.__init__."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.stt_beta import async_setup_entry


class TestAsyncSetupEntry(unittest.IsolatedAsyncioTestCase):
    async def test_forward_failure_still_raises_original_if_disconnect_fails(
        self,
    ) -> None:
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "stt_service_url": "wss://example.com/stt",
            "stt_service_key": "secret",
        }

        client = MagicMock()
        client.connect = AsyncMock()
        client.disconnect = AsyncMock(side_effect=RuntimeError("disconnect failed"))

        hass.config_entries.async_forward_entry_setups = AsyncMock(
            side_effect=ValueError("forward failed")
        )

        with (
            patch(
                "custom_components.stt_beta.async_get_clientsession",
                return_value=object(),
            ),
            patch(
                "custom_components.stt_beta.STTProxyClient",
                return_value=client,
            ),
            self.assertRaises(ValueError) as ctx,
        ):
            await async_setup_entry(hass, entry)

        self.assertEqual(str(ctx.exception), "forward failed")
        client.disconnect.assert_awaited_once()
