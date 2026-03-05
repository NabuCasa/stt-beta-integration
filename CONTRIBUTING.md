# Contributing to STT Beta Integration

## Development Environment

### Using the devcontainer (recommended)

1. Install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension in VS Code.
2. Open this repository in VS Code.
3. When prompted, click **Reopen in Container** (or use the command palette: *Dev Containers: Reopen in Container*).
4. The container will install all dependencies automatically via `scripts/setup`.

### Manual setup

```bash
python3 -m pip install -r requirements.txt
```

## Running Home Assistant for development

```bash
scripts/develop
```

This starts Home Assistant on port **8123** with debug logging enabled for the integration. The integration code is loaded from `custom_components/` via `PYTHONPATH`.

## Linting

This project uses [Ruff](https://docs.astral.sh/ruff/) with the same configuration as Home Assistant core.

```bash
ruff check .
ruff format .
```

## Submitting changes

1. Fork the repository and create a feature branch.
2. Make your changes and ensure `ruff check .` passes.
3. Open a pull request against `main`.
