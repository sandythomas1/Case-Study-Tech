#!/usr/bin/env bash
# Run gitleaks with the repository's hardened settings.
#
# Usage: bash scripts/ci/run-gitleaks.sh git|dir <absolute source path>
#   git  scans every commit reachable from HEAD in <source> (a git checkout)
#   dir  scans the files under <source>
# Requires GITLEAKS_BIN to be an absolute path (install-gitleaks.sh sets it in Actions).
#
# Every run uses .github/gitleaks.toml (--config, so a planted .gitleaks.toml is ignored),
# .github/.gitleaksignore as the only ignore file, and ignores inline gitleaks:allow
# comments. Findings are redacted in the log.
set -euo pipefail

fail() {
  echo "run-gitleaks.sh: $*" >&2
  exit 2
}

[[ $# -eq 2 ]] || fail "usage: run-gitleaks.sh git|dir <absolute source path>"
mode="$1"
source_path="$2"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
config="$repo_root/.github/gitleaks.toml"
ignore_file="$repo_root/.github/.gitleaksignore"
gitleaks_bin="${GITLEAKS_BIN:-}"

[[ "$gitleaks_bin" == /* && -x "$gitleaks_bin" ]] \
  || fail "GITLEAKS_BIN must be the absolute path of the gitleaks binary (run install-gitleaks.sh)"
[[ "$source_path" == /* && -d "$source_path" ]] \
  || fail "source must be an absolute path to a directory: $source_path"
[[ -f "$config" ]] || fail "missing $config"

# gitleaks 8.30.1 also reads <source>/.gitleaksignore even when --gitleaks-ignore-path is
# set, so a planted file there could silence findings. Refuse to scan instead.
if [[ -e "$source_path/.gitleaksignore" ]]; then
  fail "$source_path/.gitleaksignore exists; ignore entries belong in .github/.gitleaksignore"
fi

common_flags=(
  --config "$config"
  --gitleaks-ignore-path "$ignore_file"
  --ignore-gitleaks-allow
  --redact
  --no-banner
  --verbose
)

case "$mode" in
  git) "$gitleaks_bin" git "${common_flags[@]}" --log-opts="--full-history HEAD" "$source_path" ;;
  dir) "$gitleaks_bin" dir "${common_flags[@]}" "$source_path" ;;
  *) fail "mode must be git or dir, got: $mode" ;;
esac
