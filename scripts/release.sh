#!/usr/bin/env bash
set -euo pipefail

MANIFEST="custom_components/envoy_web/manifest.json"

if [[ ! -f "$MANIFEST" ]]; then
  echo "Error: manifest not found at $MANIFEST" >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Error: git working tree is not clean. Commit or stash changes first." >&2
  exit 1
fi

current_version="$(python3 - <<'PY'
import json
with open("custom_components/envoy_web/manifest.json", "r", encoding="utf-8") as fh:
    data = json.load(fh)
print(data.get("version", ""))
PY
)"

if [[ -z "$current_version" ]]; then
  echo "Error: failed to read current version from manifest." >&2
  exit 1
fi

new_version="${1:-}"
if [[ -z "$new_version" ]]; then
  IFS="." read -r major minor patch <<<"$current_version"
  if [[ -z "${major:-}" || -z "${minor:-}" || -z "${patch:-}" ]]; then
    echo "Error: current version is not semver: $current_version" >&2
    exit 1
  fi
  if ! [[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ && "$patch" =~ ^[0-9]+$ ]]; then
    echo "Error: current version is not numeric semver: $current_version" >&2
    exit 1
  fi
  patch=$((patch + 1))
  new_version="${major}.${minor}.${patch}"
fi

python3 - <<PY
import json
from collections import OrderedDict

path = "custom_components/envoy_web/manifest.json"
with open(path, "r", encoding="utf-8") as fh:
    data = json.load(fh, object_pairs_hook=OrderedDict)

data["version"] = "${new_version}"

with open(path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=True)
    fh.write("\\n")
PY

git add "$MANIFEST"
git commit -m "Release v${new_version}"
git tag -a "v${new_version}" -m "v${new_version}"

git push origin HEAD
git push origin "v${new_version}"

echo "Release complete: v${new_version}"
