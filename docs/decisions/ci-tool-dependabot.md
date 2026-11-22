# CI tool: Dependabot version updates

**Status:** Approved by owner 2026-11-21, #110 (GitHub Actions only).

## Purpose

Opens a pull request into `dev` when a GitHub Action that a workflow pins by commit SHA has a
newer release. The PR moves the SHA and its `# vX.Y.Z` comment and links the release notes.
Without it, nothing tells us when a pin falls behind a security fix.

## Configuration

`.github/dependabot.yml`:

- Ecosystem `github-actions`, directory `/`, which covers every file in `.github/workflows`.
- `target-branch: dev`, so update PRs follow the normal `dev` → `staging` → `main` flow.
- Weekly on Monday. All Action updates are grouped into one PR.
- A cooldown of 7 days, so a release is proposed only once it is a week old. This is the same rule
  as the other CI tool pins.
- Commit messages start with `ci`.

Dependabot reads this file **only from the default branch (`main`)**. A change to it takes effect
after it is promoted, not when it merges into `dev`.

Out of scope (owner decision, 2026-11-21): the `pip` ecosystem for `scripts/ci/*.requirements.txt`,
the `npm` and `uv` ecosystems for the app and services, and Dependabot security updates. Those
open against the default branch regardless of `target-branch`. The pins Dependabot does not cover
follow the checklist in `docs/CI.md` "Keeping pins current".

## Review of an update PR

Dependabot PRs change `.github/workflows`, so CODEOWNERS requires the owner's review. Before
approving:

1. Read the linked release notes for every action in the group. Look for changed defaults,
   removed inputs and new required permissions.
2. Check that each new SHA is the commit of the release tag in the action's own repository.
3. For `astral-sh/setup-uv`, confirm the `version` and `checksum` inputs still work as documented
   in [ci-tool-setup-uv.md](ci-tool-setup-uv.md).
4. CI gate must pass, including **Workflow lint (zizmor)**.

## Data it sees

The repository's workflow files, read by GitHub's own Dependabot service. No user data, session
content or secrets. Dependabot PRs run CI with a read-only token and without repository secrets,
and this CI uses none.

## Network egress

None from our runners. Dependabot runs on GitHub's infrastructure and reads action releases from
`github.com`.

## Upgrade

Nothing to pin. Dependabot is a GitHub service. A change to `.github/dependabot.yml` needs the
owner's review through CODEOWNERS, and zizmor lints the file in CI.
