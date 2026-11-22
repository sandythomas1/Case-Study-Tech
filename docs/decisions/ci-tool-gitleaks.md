# CI tool: gitleaks

**Status:** Approved by owner 2026-11-20, #51.

## Purpose

Fails CI when a secret is committed or would ship to a device or browser. It scans git
history, the checked-out tree and the exported Expo bundles in `apps/student/dist`
(ARCHITECTURE §7: provider credentials and the state-signing key never reach the client
bundle or git).

## Pin and verification

- gitleaks 8.30.1, the `linux_x64` release tarball from `github.com/gitleaks/gitleaks`.
- sha256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`, pinned in
  `scripts/ci/install-gitleaks.sh` and checked with `sha256sum --check --strict` before
  extraction. It matched the release's `gitleaks_8.30.1_checksums.txt` on 2026-11-20.
- We run the binary directly, not `gitleaks-action`, which needs a license key for
  organizations.
- `scripts/ci/run-gitleaks.sh` calls the binary by absolute path with
  `--config .github/gitleaks.toml` (default rules, no allowlist),
  `--gitleaks-ignore-path .github/.gitleaksignore` and `--ignore-gitleaks-allow`. It refuses to
  scan if a `.gitleaksignore` sits at the scan root, because gitleaks 8.30.1 reads that file even
  when `--gitleaks-ignore-path` is set. The synthetic-fixture check fails on any tracked
  `.gitleaks.toml` or `.gitleaksignore` outside `.github/`.

## Data it sees

Repository code, its git history and the built client bundles, all on the GitHub-hosted
runner. No user data, session content or secrets are given to it. Findings are redacted
(`--redact`) in the log, and no report is uploaded.

## Network egress

One HTTPS download of the release tarball from `github.com` (release assets on
`objects.githubusercontent.com`). The scan itself makes no network calls.

## Upgrade

1. Pick a release at least a week old and read its notes.
2. Update `GITLEAKS_VERSION` and `GITLEAKS_SHA256` in `scripts/ci/install-gitleaks.sh` from the
   release's checksums file.
3. Re-run the canary checks in `docs/CI.md`. A planted secret must still fail, including with a
   planted `.gitleaks.toml` allow-all, a root `.gitleaksignore` and inline `gitleaks:allow`.
4. Update this record. The change needs the owner's review through CODEOWNERS.
