# CI tool: pip-audit

**Status:** Approved by owner 2026-11-20, #51.

## Purpose

Fails CI when a locked dependency of any Python service under `services/` has a known
vulnerability. It is the Python half of the dependency audit; `npm audit` covers the student app.

## Pin and verification

- pip-audit 2.10.1 and every transitive dependency are pinned with sha256 hashes in
  `scripts/ci/pip-audit.requirements.txt`. That file is compiled from
  `scripts/ci/pip-audit.requirements.in` with
  `uv pip compile --universal --python-version 3.12 --generate-hashes --exclude-newer 2026-11-13`,
  so it excludes releases from the final week before the compile.
- CI installs it into a throwaway venv in `$RUNNER_TEMP` with
  `uv pip install --require-hashes`. A package whose hash does not match fails the install.
- It audits a hashed `uv export --frozen` of each service's `uv.lock` with
  `--strict --disable-pip --require-hashes`. It reads the pinned list as given and installs
  nothing from it.

## Data it sees

Dependency names, versions and hashes from the services' lock files, which are public
package metadata. No user data, session content or secrets.

## Network egress

- `pypi.org` and `files.pythonhosted.org` to install pip-audit's pinned wheels.
- The PyPI JSON API (`pypi.org`), its default vulnerability service, to look up advisories
  for each locked name and version.

## Upgrade

1. Edit the version in `scripts/ci/pip-audit.requirements.in`.
2. Re-run the compile command from the header of `scripts/ci/pip-audit.requirements.txt`, with
   `--exclude-newer` set to a date a week before the compile.
3. Run the audit locally (`docs/CI.md`) and confirm a clean result on `services/session`.
4. Update this record. The change needs the owner's review through CODEOWNERS.
