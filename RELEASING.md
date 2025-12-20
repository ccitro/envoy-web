# Releasing for HACS

HACS expects tagged GitHub releases with a version that matches the integration
manifest. This repository is structured for HACS with `custom_components/` at the
root and `hacs.json` present.

## Automated Release (recommended)

This repo includes:

- `scripts/release.sh` to bump the version, commit, tag, and push.
- `.github/workflows/release.yml` to validate the manifest version and create
  a GitHub Release when a tag is pushed.

### One-command release

From a clean working tree:

```bash
# Bump patch version automatically
./scripts/release.sh

# Or release a specific version
./scripts/release.sh 0.2.0
```

The script updates `custom_components/envoy_web/manifest.json`, commits the
change, tags `vX.Y.Z`, and pushes both the commit and tag.

GitHub Actions then creates the GitHub Release and HACS picks it up as an update.

## Notes

- For HACS custom repositories, users can install from the default branch, but
  release tags are required for update tracking and best practice.
- Keep `hacs.json` in the repo root with `content_in_root: false` so HACS finds
  the integration under `custom_components/`.
