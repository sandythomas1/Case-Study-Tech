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
  `uv pip install --require-hashes --no-build` and `UV_NO_CONFIG=1`. A wheel whose hash does not
  match fails the install, a source build is refused, and a planted `uv.toml` cannot change the
  index.
- It runs as
  `zizmor --offline --no-config --no-ignores --strict-collection --persona=pedantic --collect=all .`
  - `--offline` disables the online audits and every network call, so it gets no token.
  - `--no-config` ignores any `zizmor.yml` or `.github/zizmor.yml`, so a planted config cannot
    turn an audit off. `--no-ignores` ignores inline `# zizmor: ignore[...]` comments. Without
    these flags, a planted config plus inline comments hid every finding in a test workflow on
    2026-11-21. With them, the same workflow failed.
  - `--collect=all` collects workflows, actions and the Dependabot config, and also ignores
    `.gitignore`. Any narrower `--collect` honors `.gitignore`. On 2026-11-22, a tracked workflow
    with template injection, listed in `.gitignore`, was skipped with
    `--collect=workflows,actions,dependabot` and failed with `--collect=all`. GitHub runs a tracked
    workflow whatever `.gitignore` says.
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
because they would hand the job token to a third-party tool and call `api.github.com`. That
leaves a gap that nothing automated fills:

- Dependabot version updates propose new releases, but only after the 7-day cooldown, and
  Dependabot security updates are off ([ci-tool-dependabot.md](ci-tool-dependabot.md)). A fix for
  a vulnerable action therefore waits at least a week plus review.
- No check catches an impostor commit, a SHA from a fork that is not the tag's commit. The
  reviewer checks that by hand for every SHA change (`docs/CI.md` "Keeping pins current").

## Upgrade

1. Pick a release at least a week old and read its notes, especially any new or changed audits.
2. Edit the version in `scripts/ci/zizmor.requirements.in`.
3. Re-run the compile command from the header of `scripts/ci/zizmor.requirements.txt`, with
   `--exclude-newer` set to a date a week before the compile.
4. Run zizmor locally (`docs/CI.md`). `ci.yml` must stay clean, and the canary workflow in
   `docs/CI.md` must still fail.
5. Update this record. The change needs the owner's review through CODEOWNERS.
