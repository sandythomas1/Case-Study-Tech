# CI tool: astral-sh/setup-uv and uv

**Status:** Approved by owner 2026-11-20, #51.

## Purpose

Installs uv on the runner. The Python jobs use uv to create each service's environment
from its `uv.lock` and run ruff, mypy and pytest. It also exports the locked dependency list
for pip-audit and installs pip-audit's pinned environment.

## Pin and verification

- `astral-sh/setup-uv` v10.3.3, pinned by full commit SHA
  `68559e99cc807c1eb7e9238fd43a15bba460eec2` in `.github/workflows/ci.yml`. We skipped v10.4.0,
  which was published the same day.
- uv 0.13.8, set by the action's `version` input. The action's `checksum` input pins the
  sha256 of `uv-x86_64-unknown-linux-gnu.tar.gz`,
  `5acfd9177cfecf0bf87578f059728215ccc884388988f55f7a65041b57387d91`. That matched the release's
  `.sha256` file on 2026-11-20. A different archive fails the step.
- `uv sync --locked` fails if `uv.lock` is out of date. Packages are checked against the hashes
  in `uv.lock`.

## Data it sees

Repository code, each service's `pyproject.toml` and `uv.lock`, and public package metadata
and wheels. No user data, session content or secrets. The action receives the workflow's
default read-only `GITHUB_TOKEN`, which is used only if it falls back to downloading from
GitHub Releases.

## Network egress

- The uv archive from Astral's release mirror (`releases.astral.sh`, the action's default),
  falling back to GitHub Releases.
- `pypi.org` and `files.pythonhosted.org` for locked packages.
- A managed Python 3.12 build if the runner has none.
- The GitHub Actions cache, keyed on each service's `uv.lock`.

## Upgrade

1. Pick an action release at least a week old. Resolve its tag to a commit with
   `gh api repos/astral-sh/setup-uv/commits/<tag> --jq .sha` and update the SHA and the
   `# vX` comment.
2. For a new uv version, update `version` and `checksum` from the release's
   `uv-x86_64-unknown-linux-gnu.tar.gz.sha256`. Check that `uv lock --check` passes for every
   service with that version.
3. Update this record. The change needs the owner's review through CODEOWNERS.
