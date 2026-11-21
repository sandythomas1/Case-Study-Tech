#!/usr/bin/env bash
# Install a pinned gitleaks release binary after verifying its sha256.
#
# Usage: bash scripts/ci/install-gitleaks.sh [install-dir]
# Defaults to $RUNNER_TEMP/gitleaks in GitHub Actions, otherwise ${TMPDIR:-/tmp}/gitleaks.
# In Actions it exports GITLEAKS_BIN (the binary's absolute path) through $GITHUB_ENV for
# scripts/ci/run-gitleaks.sh. Nothing is added to PATH.
#
# To upgrade: change GITLEAKS_VERSION, then copy the linux_x64 tarball hash from
# gitleaks_<version>_checksums.txt on the release page into GITLEAKS_SHA256, and update
# docs/decisions/ci-tool-gitleaks.md.
set -euo pipefail

readonly GITLEAKS_VERSION="8.30.1"
readonly GITLEAKS_SHA256="551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "install-gitleaks.sh supports Linux x86_64 only; see docs/CI.md for other platforms." >&2
  exit 1
fi

default_dir="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/gitleaks"
mkdir -p "${1:-$default_dir}"
install_dir="$(cd "${1:-$default_dir}" && pwd)"
archive="gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
url="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${archive}"

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 --retry 3 \
  --output "$work_dir/$archive" "$url"
echo "${GITLEAKS_SHA256}  $work_dir/$archive" | sha256sum --check --strict -

tar -xzf "$work_dir/$archive" -C "$install_dir" gitleaks
chmod 0755 "$install_dir/gitleaks"
"$install_dir/gitleaks" version

if [[ -n "${GITHUB_ENV:-}" ]]; then
  echo "GITLEAKS_BIN=$install_dir/gitleaks" >> "$GITHUB_ENV"
else
  echo "export GITLEAKS_BIN=$install_dir/gitleaks"
fi
