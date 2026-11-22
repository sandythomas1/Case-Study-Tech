# Continuous integration

All pull-request checks live in one workflow, `.github/workflows/ci.yml` (Issue #51). Deploys are
a separate workflow, tracked in #105.

## When it runs

- Every pull request into `dev`, `staging` or `main`.
- Every push to `dev`, which covers merges.
- On demand, from **Actions → CI → Run workflow**.

The workflow has no path filters, so every job runs on every trigger and the required check never
waits on a job that was filtered out. A new push to a pull request cancels that PR's run in
progress. Runs for pushes to `dev` are never cancelled, so every merge gets a result.

## What runs

| Job | What it checks | Fails when |
|---|---|---|
| Student app | In `apps/student`: `npm audit --audit-level=high` on the lockfile, then `npm ci`, lint, typecheck, `npm test`, `npx expo install --check`, the web, Android and iOS exports, and a gitleaks scan of the exported bundles in `dist/` | Any step fails. The audit fails only on high or critical advisories. The bundle scan fails on any secret that would ship to a device or browser. |
| Discover Python services | Lists the `services/*` directories | A `services/*` directory has no `pyproject.toml`. A new service is picked up without editing the workflow. |
| Python (`services/<name>`) | One job per service: `uv sync --locked --python 3.12`, `ruff check`, `mypy`, `pytest`, then pip-audit over the locked dependencies | Any step fails, the lock file is out of date, or a locked dependency has a known vulnerability |
| Secret scan (history and tree) | gitleaks over every commit reachable from the checked-out ref (for a PR, the merge commit), then over the checked-out tree | Any finding. The tree scan also covers a merge result that no single commit contains. Values are redacted in the log. |
| Synthetic-fixture check | Unit tests for the checker, then `scripts/ci/check_synthetic_fixtures.py` over all tracked files | See [Synthetic-fixture check](#synthetic-fixture-check) |
| Workflow lint (zizmor) | zizmor, offline, over `.github/workflows`, any composite action and `.github/dependabot.yml` | Any finding, such as template injection, broad permissions, an action not pinned by SHA or checkout that keeps credentials. Ignore comments and config files are not honored. A file that does not parse also fails. |
| CI gate | Collects every job result | Any job did not succeed. Python jobs may be skipped only when no service exists. |

Python services have no package "build" step. Their container build and image scan come with the
deploy workflow in #105.

The workflow uses no secrets. The token is read-only (`contents: read`), checkout does not keep
credentials, and every action is pinned to a full commit SHA. Every `run` step uses bash with
`-eo pipefail`.

## Tools and their records

| Tool | Pin | Record |
|---|---|---|
| gitleaks | 8.30.1, sha256-verified tarball | [ci-tool-gitleaks.md](decisions/ci-tool-gitleaks.md) |
| pip-audit | 2.10.1, hashed requirements file | [ci-tool-pip-audit.md](decisions/ci-tool-pip-audit.md) |
| setup-uv and uv | action by commit SHA; uv 0.13.8 with sha256 | [ci-tool-setup-uv.md](decisions/ci-tool-setup-uv.md) |
| zizmor | 1.32.0, hashed requirements file | [ci-tool-zizmor.md](decisions/ci-tool-zizmor.md) |
| Dependabot version updates | GitHub service; config in `.github/dependabot.yml` | [ci-tool-dependabot.md](decisions/ci-tool-dependabot.md) |

A new CI tool is judged by the data it sees. It needs an owner decision (ARCHITECTURE §8) and a
record in `docs/decisions/`.

## Keeping pins current

Every action and tool is pinned, so a hijacked tag or release cannot change what runs. A pin
does not move on its own, though, so each one has a way to stay current:

| Pin | Where | Kept current by |
|---|---|---|
| Every action `uses:` SHA | `.github/workflows/*.yml` | Dependabot: one grouped PR into `dev` each Monday, for releases at least 7 days old. Reviewed as in [ci-tool-dependabot.md](decisions/ci-tool-dependabot.md#review-of-an-update-pr). |
| gitleaks version and sha256 | `scripts/ci/install-gitleaks.sh` | The monthly check below, then the steps in [ci-tool-gitleaks.md](decisions/ci-tool-gitleaks.md#upgrade) |
| uv version and sha256 | the `version` and `checksum` inputs of both `setup-uv` steps in `ci.yml` (Python and Workflow lint jobs) | The monthly check below, then the steps in [ci-tool-setup-uv.md](decisions/ci-tool-setup-uv.md). Change both steps together. |
| pip-audit and its dependencies | `scripts/ci/pip-audit.requirements.in` and `.txt` | The monthly check below, then the steps in [ci-tool-pip-audit.md](decisions/ci-tool-pip-audit.md#upgrade) |
| zizmor | `scripts/ci/zizmor.requirements.in` and `.txt` | The monthly check below, then the steps in [ci-tool-zizmor.md](decisions/ci-tool-zizmor.md#upgrade) |

Dependabot cannot update a version in a shell script or in an action's `with:` input, so those
pins get a check on the first Monday of each month:

1. Compare each pin with the tool's latest release:
   [gitleaks](https://github.com/gitleaks/gitleaks/releases),
   [uv](https://github.com/astral-sh/uv/releases),
   [pip-audit](https://pypi.org/project/pip-audit/) and
   [zizmor](https://pypi.org/project/zizmor/).
2. Read the notes of every newer release. A security fix is a reason to upgrade now. Otherwise,
   upgrade when a release is at least a week old.
3. Upgrade one tool per PR into `dev`, following the steps in its record. Each change needs the
   owner's review through CODEOWNERS.

## Owner actions

In **Settings → Rules → Rulesets**, for each of the `dev`, `staging` and `main` rulesets:

1. Under **Require status checks to pass**, add **CI gate** (source: GitHub Actions) and make it
   the only required check. It fails whenever any other job fails, so service jobs can be added
   or renamed without editing the rulesets.
2. When this change merges, replace any required check from the old `student-checks` workflow
   ("checks" / "Student application checks") with **CI gate**. Otherwise PRs wait on a check
   that no longer runs.
3. Under **Require a pull request before merging**, turn on **Require review from Code Owners**.
   `.github/CODEOWNERS` only *requests* the owner's review of `CLAUDE.md`, `.github/` (workflows,
   the gitleaks config and the fixture allowlist), `scripts/ci/`, `.gitattributes` and any
   gitleaks file. GitHub *enforces* that review only once this setting is on.

## Secret scan hardening

`scripts/ci/run-gitleaks.sh` runs every scan:

- It calls gitleaks by absolute path (`GITLEAKS_BIN`, set by `scripts/ci/install-gitleaks.sh`).
- It uses `--config .github/gitleaks.toml` (default rules, no allowlist), so a
  `.gitleaks.toml` planted elsewhere is ignored.
- `--gitleaks-ignore-path .github/.gitleaksignore` is the only intended ignore file.
  `--ignore-gitleaks-allow` disables inline `gitleaks:allow` comments.
- It refuses to scan if a `.gitleaksignore` exists at the scan root, because gitleaks 8.30.1
  still reads that file. The synthetic-fixture check also fails on any tracked `.gitleaks.toml` or
  `.gitleaksignore` outside `.github/`.

A true false positive goes in `.github/.gitleaksignore` as its gitleaks fingerprint, with the
owner's review. Never ignore a real secret: rotate it first, then remove it from history. Never
paste one into an issue or PR.

## Synthetic-fixture check

The check fails when a tracked file:

- is audio, video or a caption file by extension, including the raw `.pcm` the speech contract
  uses;
- starts with an audio/video signature, whatever its name: RIFF/WAVE, AVI, AIFF, ID3, MPEG and
  AAC frame sync, Ogg, FLAC, MP4/QuickTime `ftyp` (HEIC and AVIF images excepted), Matroska/WebM,
  Core Audio or AMR;
- is an archive (`.zip .tar .gz .tgz .7z .rar`);
- is not source code (or Markdown under `docs/` or `specs/`) and has a file name containing
  transcript, recording, caption, subtitle, excerpt or feedback;
- is a `.gitleaks.toml` or `.gitleaksignore` outside `.github/`. These can never be allowlisted.

It is a heuristic. It reads only file names and the first 16 bytes. Review is still the control
for DAT-6: no real session content in fixtures (ARCHITECTURE §7, POLICY DAT-1 and DAT-6).

### Allowlisting a synthetic fixture

Prefer generating test data inside the test, as `services/session/tests/synthetic_audio.py`
does. If a flagged file really must be committed and is synthetic, stage it, get its blob sha,
and pin both in `.github/synthetic-fixtures.allow` with a justification:

```sh
git add services/session/tests/fixtures/sine-440hz.wav
git ls-files -s -- services/session/tests/fixtures/sine-440hz.wav   # second column is the blob sha
```

```text
services/session/tests/fixtures/sine-440hz.wav 0123456789abcdef0123456789abcdef01234567  # synthetic: generated tone, no speech
```

Each entry pins one exact path and its content. If the file changes, the check fails with the old
and new sha. Update the entry so the new content gets reviewed. An entry without a justification
or a valid sha, or one for a path that is no longer tracked, fails the check. CODEOWNERS requests
the owner's review of the allowlist; the rulesets enforce it once Code Owner review is required.

## Reproduce locally

Run from the repository root unless noted. Commands are the same in PowerShell and in a POSIX
shell unless shown separately.

### Student app

```sh
cd apps/student
npm audit --audit-level=high
npm ci
npm run lint
npm run typecheck
npm test
npx expo install --check
npm run export:web
npm run export:android
npm run export:ios
```

### Python services

```sh
cd services/session
uv sync --locked --python 3.12
uv run --frozen ruff check .
uv run --frozen mypy .
uv run --frozen pytest
```

The dependency audit, POSIX (from the repository root):

```sh
uv venv --python 3.12 /tmp/pip-audit-venv
uv pip install --python /tmp/pip-audit-venv --require-hashes -r scripts/ci/pip-audit.requirements.txt
cd services/session
uv export --frozen --all-groups --no-emit-project --format requirements-txt --quiet --output-file /tmp/requirements.txt
/tmp/pip-audit-venv/bin/pip-audit --strict --disable-pip --require-hashes -r /tmp/requirements.txt
```

The dependency audit, PowerShell (from the repository root):

```powershell
uv venv --python 3.12 "$env:TEMP\pip-audit-venv"
uv pip install --python "$env:TEMP\pip-audit-venv" --require-hashes -r scripts/ci/pip-audit.requirements.txt
cd services/session
uv export --frozen --all-groups --no-emit-project --format requirements-txt --quiet --output-file "$env:TEMP\requirements.txt"
& "$env:TEMP\pip-audit-venv\Scripts\pip-audit.exe" --strict --disable-pip --require-hashes -r "$env:TEMP\requirements.txt"
```

### Secret scan

On Linux x86_64, install the pinned binary and run the same scans CI runs:

```sh
eval "$(bash scripts/ci/install-gitleaks.sh)"   # prints: export GITLEAKS_BIN=...
bash scripts/ci/run-gitleaks.sh git "$PWD"
bash scripts/ci/run-gitleaks.sh dir "$PWD"
bash scripts/ci/run-gitleaks.sh dir "$PWD/apps/student/dist"
```

A local tree scan also reads untracked folders such as `node_modules` and `.venv`. Scan a clean
clone for a result that matches CI.

On Windows or macOS, download gitleaks 8.30.1 for your platform from the
[release page](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1), check its hash against
`gitleaks_8.30.1_checksums.txt`, and keep it outside the repository. In Git Bash on Windows, set
`GITLEAKS_BIN` to its absolute path (for example `/c/tools/gitleaks.exe`) and run the same
`run-gitleaks.sh` commands.

To prove the scan still fails closed after an upgrade, commit a fake token in a scratch repo
together with an allow-all `.gitleaks.toml` and an inline `gitleaks:allow`. Both
`run-gitleaks.sh` modes must report it. Then add a root `.gitleaksignore` holding its fingerprint;
the script must refuse to scan (exit 2).

### Workflow lint

POSIX (from the repository root):

```sh
uv venv --python 3.12 /tmp/zizmor-venv
uv pip install --python /tmp/zizmor-venv --require-hashes -r scripts/ci/zizmor.requirements.txt
/tmp/zizmor-venv/bin/zizmor --offline --no-config --no-ignores --strict-collection --persona=pedantic --collect=workflows,actions,dependabot .
```

PowerShell (from the repository root):

```powershell
uv venv --python 3.12 "$env:TEMP\zizmor-venv"
uv pip install --python "$env:TEMP\zizmor-venv" --require-hashes -r scripts/ci/zizmor.requirements.txt
& "$env:TEMP\zizmor-venv\Scripts\zizmor.exe" --offline --no-config --no-ignores --strict-collection --persona=pedantic --collect=workflows,actions,dependabot .
```

To prove the lint still fails closed after an upgrade, run it in a scratch repo over a workflow
that uses `actions/checkout@v4` with default credentials, echoes
`${{ github.event.pull_request.title }}` in a `run` step and sets `permissions: write-all`. Mark
each line with a `# zizmor: ignore[...]` comment and add a `zizmor.yml` that disables those
audits. It must still report template injection, unpinned uses, credential persistence and
excessive permissions, and exit non-zero.

### Synthetic-fixture check

```sh
python -m unittest discover -s scripts/ci/tests -v
python scripts/ci/check_synthetic_fixtures.py
```

The script uses only the standard library and needs Python 3.10 or later.
