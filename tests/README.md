# Envoy Web Integration Tests

This directory contains integration tests for the Envoy Web Home Assistant custom component.

## Test structure

- **conftest.py**: Common fixtures and test configuration
- **test_config_flow.py**: Tests for the configuration flow (setup and options)
- **test_init.py**: Tests for integration initialization, setup, and unload
- **test_coordinator.py**: Tests for the data update coordinator
- **test_entities.py**: Tests for entity state, attributes, and unit handling

## Running tests

### Quick start

Run all tests:
```bash
./scripts/test
```

Run tests with verbose output:
```bash
./scripts/test -v
```

Run a specific test file:
```bash
./scripts/test tests/test_config_flow.py
```

Run a specific test function:
```bash
./scripts/test tests/test_config_flow.py::test_form
```

### Manual setup

Install test dependencies:
```bash
pip install -r requirements_test.txt
```

Run tests:
```bash
pytest tests/
```

## Bootstrapping with direnv

If you're using direnv with the flake (Python 3.13.2+), `scripts/setup` installs
runtime and test dependencies into `.venv` (via `uv` when available):

```bash
direnv allow .
./scripts/setup
./scripts/test
```

Note: test deps require Python 3.13, so refresh the direnv shell if you update the flake.

## Test coverage

The current test suite covers:

- **Config flow tests** (`test_config_flow.py`):
  - User configuration flow
  - Invalid credentials handling
  - Duplicate entry prevention
  - Options flow

- **Initialization tests** (`test_init.py`):
  - Successful integration setup
  - Integration unload
  - Error handling during setup

- **Entity tests** (`test_entities.py`):
  - Entity state and attribute correctness
  - Availability handling when API data is missing or incomplete

- **Coordinator tests** (`test_coordinator.py`):
  - Successful data updates
  - API error handling

## Adding new tests

When adding new tests:

1. Follow the existing test structure and naming conventions
2. Use the fixtures defined in `conftest.py` for common setup
3. Mock external API calls using the `mock_aiohttp_session` fixture
4. Ensure tests are isolated and do not depend on each other
5. Add descriptive docstrings to test functions

## Continuous integration

These tests are designed to run in CI/CD pipelines and should be run before
merging any changes to ensure the integration continues to work correctly.
