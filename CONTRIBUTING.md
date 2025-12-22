# Contribution guidelines

Contributing to this project should be as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features

## GitHub is used for everything

GitHub is used to host code, to track issues and feature requests, and to accept pull requests.
Pull requests are the best way to propose changes to the codebase.

1. Fork the repo and create your branch from `main`.
2. If you've changed something, update the documentation.
3. Make sure your code lints (using `scripts/lint`).
4. Test your contribution (using `scripts/test`).
5. Open that pull request.

## Any contributions you make will be under the MIT License

In short, when you submit code changes, your submissions are understood to be under the same
[MIT License](http://choosealicense.com/licenses/mit/) that covers the project. Feel free to
contact the maintainers if that's a concern.

## Report bugs using GitHub issues

GitHub issues are used to track public bugs.
Report a bug by [opening a new issue](../../issues/new/choose); it's that easy.

## Write bug reports with detail, background, and sample code

**Great bug reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific
  - Give sample code if you can
- What you expected would happen
- What actually happens
- Notes (including what you tried)

People *love* thorough bug reports. I'm not even kidding.

## Use a consistent coding style

Use [Ruff formatter](https://docs.astral.sh/ruff/formatter/) to keep formatting consistent:

```bash
./scripts/lint
```

## Development environment (direnv + Nix flakes)

This repo includes a `flake.nix` to provide Python, uv, and ruff, and a `.envrc`
to load it via direnv. The flake tracks `nixos-unstable` to provide Python 3.13.2+
for Home Assistant 2025.12.x.

### Quick start

```bash
direnv allow .
./scripts/setup
./scripts/lint
./scripts/develop
```

- `scripts/setup` installs runtime and test requirements into `.venv` (via `uv` when available).
- `scripts/develop` runs Home Assistant using `config/configuration.yaml` and loads the
  integration from the repo root.

### Home Assistant dev container (optional)

This custom component is based on the
[integration_blueprint template](https://github.com/ludeeus/integration_blueprint).
It includes a dev container setup for Visual Studio Code. With this container you will
have a standalone Home Assistant instance running and already configured with the
included [`configuration.yaml`](./config/configuration.yaml) file.

## Running tests

The project includes a test suite to ensure the integration works correctly. Before
submitting a pull request, please:

1. Install test dependencies (if not already installed):
   ```bash
   ./scripts/setup
   ```

2. Run the tests:
   ```bash
   ./scripts/test
   ```

   Or manually:
   ```bash
   pytest tests/
   ```

3. Ensure all tests pass and add new tests for any new functionality.

For more information about the test suite, see [tests/README.md](tests/README.md).

## Release process

If you're preparing a release, follow `RELEASING.md`.

## License

By contributing, you agree that your contributions will be licensed under its MIT License.
