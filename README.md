# STT Beta Integration

> **⚠️ For testing purposes only.**
>
> This is a STT (Speech-to-Text) Beta integration for [Home Assistant](https://www.home-assistant.io/),
> intended for use with [HACS](https://hacs.xyz/) for testing purposes only.
> It is **not** production-ready.

## Installation via HACS

1. Open HACS in your Home Assistant instance.
2. Go to **Integrations**.
3. Click the three-dot menu in the top-right corner and choose **Custom repositories**.
4. Add `https://github.com/NabuCasa/stt-beta-integration` as a repository with category **Integration**.
5. Find **STT Beta Integration** in the list and install it.
6. Restart Home Assistant.

## Configuration

After installation, add the integration through **Settings → Devices & Services → Add Integration** and search for **STT Beta**.

The config flow requires:

- `STT Service URL`: A WebSocket endpoint for the proxy, such as `wss://example.com/stt`.
- `STT Service Key`: The bearer token used to authenticate to the STT proxy.

The integration validates the WebSocket connection during setup, and you can update the URL or key later from the integration's **Reconfigure** action.

## Development

This integration implements the Home Assistant
[Speech-to-Text entity API](https://developers.home-assistant.io/docs/core/entity/stt/)
by streaming audio to a remote STT proxy server over a persistent WebSocket connection.
