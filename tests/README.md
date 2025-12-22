# Envoy Web Integration Tests

This directory contains basic integration test scaffolding for the Envoy Web custom component.

## Quick Start

Run tests:
```bash
./scripts/test
```

Run a specific test:
```bash
./scripts/test tests/test_init.py::test_setup_entry_registers_service
```

## Bootstrapping

If you're using direnv with the flake (Python 3.13.2+), `scripts/setup` installs
runtime and test dependencies into `.venv` (via `uv` when available):

```bash
direnv allow
./scripts/setup
./scripts/test
```

Note: test deps require Python 3.13, so refresh the direnv shell if you update the flake.

## Notes

- `conftest.py` enables custom integrations and provides a mock config entry.
- `test_init.py` verifies that setup registers the service without touching the network.
