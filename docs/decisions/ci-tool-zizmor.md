# CI tool: zizmor

**Status:** Approved by owner 2026-11-21, #110 (offline mode).

## Purpose

Fails CI when a workflow, composite action or the Dependabot config has a risky pattern:
template injection, broad `permissions`, an action not pinned to a commit SHA, checkout that
keeps credentials, dangerous triggers, a Dependabot config without a cooldown, and the rest
of zizmor's offline audits. It runs as the **Workflow lint (zizmor)** job, which CI gate
requires.

## Pin and verification

- zizmor 1.32.0 (released 2026-11-02), pinned with sha256 hashes in
  `scripts/ci/zizmor.requirements.txt`. That file is compiled from
  `scripts/ci/zizmor.requirements.in` with
  `uv pip compile --universal --python-version 3.12 --generate-hashes --exclude-newer 2026-11-14`,
  so it excludes releases from the final week before the compile. zizmor is a single binary wheel
  with no Python dependencies.
- CI installs it into a throwaway venv in `$RUNNER_TEMP` with
  `uv pip install --require-hashes`. A wheel whose hash does not match fails the install.
- It runs as
  `zizmor --offline --no-config --no-ignores --strict-collection --persona=pedantic --collect=workflows,actions,dependabot .`
  - `--offline` disables the online audits and every network call, so it gets no token.
  - `--no-config` ignores any `zizmor.yml` or `.github/zizmor.yml`, so a planted config cannot
    turn an audit off. `--no-ignores` ignores inline `# zizmor: ignore[...]` comments. Without
    these flags, a planted config plus inline comments hid every finding in a test workflow on
    2026-11-21. With them, the same workflow failed.
  - `--strict-collection` fails on a workflow that does not parse, instead of skipping it with a
    warning.
  - `--persona=pedantic` also flags code smells. Today it adds the single-job
    `permissions: write-all` case, which the regular persona lets through. `ci.yml` was clean under
    the pedantic and auditor personas on 2026-11-21.
- A true false positive is fixed in the workflow itself, or the flags are changed in `ci.yml`.
  Either way the change goes through CODEOWNERS review. There is no ignore file.

## Data it sees

The workflow, action and Dependabot files in the checked-out repository, on the GitHub-hosted
runner. No user data, session content, secrets or token.

## Network egress

- `pypi.org` and `files.pythonhosted.org` to install the pinned wheel.
- None while it scans (`--offline`).

The online audits (known-vulnerable actions, impostor commits, stale refs) were declined,
because they would hand the job token to a third-party tool and call `api.github.com`.
Dependabot keeps the Action pins current instead
([ci-tool-dependabot.md](ci-tool-dependabot.md)).

## Upgrade

1. Pick a release at least a week old and read its notes, especially any new or changed audits.
2. Edit the version in `scripts/ci/zizmor.requirements.in`.
3. Re-run the compile command from the header of `scripts/ci/zizmor.requirements.txt`, with
   `--exclude-newer` set to a date a week before the compile.
4. Run zizmor locally (`docs/CI.md`). `ci.yml` must stay clean, and the canary workflow in
   `docs/CI.md` must still fail.
5. Update this record. The change needs the owner's review through CODEOWNERS.
