# Case-Study-Tech — Project Instructions

AI-powered counseling practice app: students counsel simulated client personas and get rubric-based
feedback. Discovery notes and architecture live in `docs/`. This file extends the workspace
`CLAUDE.md`; it does not repeat it.

- **Repo:** https://github.com/sandythomas1/Case-Study-Tech
- **Project board:** https://github.com/users/sandythomas1/projects/1 (Project #1, owner `sandythomas1`)
- **Branch flow:** `feature/<issue#>-<slug>` → `dev` → `staging` → `main` (default branch).
  `dev`, `staging`, and `main` are protected — all changes land through PRs.
- **Identities:** `sandythomas1` is the human; `sandytdev` is the AI dev identity (repo Write,
  Project Writer).

---

## GitHub Project Workflow (mandatory for every feature)

No code is written, changed, or reviewed without a GitHub Issue on Project #1 that reflects the
real state of the work. The board is the shared source of truth between humans and agents.

### 1. Before writing any code — find or create the ticket

1. Search for an existing issue first; never create duplicates:
   `gh issue list -R sandythomas1/Case-Study-Tech --state all --search "<keywords>"`
2. If none exists, create one with this body structure:
   - `## Description` — what and why, in user terms.
   - `## Implementation Requirements` — concrete, checkable bullets.
   - `## Acceptance Criteria` — `- [ ]` checkboxes that can be verified by a test or demo.
3. Add it to the Project and set **every** field (IDs in the reference section below):
   Status, Phase, Priority, Area, Sequence. Field values live on the Project — do not duplicate
   them in the issue body.
4. Large features: split into sub-issues under a parent issue so **Sub-issues progress** tracks
   completion.
5. Create the branch from `dev` as `feature/<issue#>-<short-slug>`.

### 2. Move Status as the work actually moves

| Status | Set it when… |
|---|---|
| Backlog | Issue is captured but not yet refined. |
| Ready | Requirements and acceptance criteria are clear; nothing blocks starting. |
| In Progress | **Before the first code change** on the issue. |
| Agent Review | A PR into `dev` is open and awaiting review/verification. |
| Done in Dev | The PR is merged into `dev`. |
| Staging Candidate | The change is merged into `staging` via a promotion PR. |
| Released | The change is merged into `main`. |

Rules:
- Never set a status ahead of reality. Unverified work is never Done in Dev or later.
- If review sends work back, move it from Agent Review to In Progress.
- If work is blocked, keep its status and post a comment explaining the blocker.

### 3. Post progress every time code is changed

After each working session or logical change that touches code (each commit/push at minimum),
post a comment on the issue:

```markdown
**Progress update — YYYY-MM-DD**
- **Changed:** <what was done, 1–3 bullets>
- **Files:** <key files touched>
- **Tests:** <added/updated; pass/fail with counts>
- **Status:** <old> → <new> (or "unchanged: In Progress")
- **Next:** <next step or blocker>
```

- Tick an acceptance-criteria checkbox in the issue body only once it is verified (test or demo).
- Report failures honestly — a failing test goes in the comment, not under the rug.

### 4. Pull requests

- Feature PRs target `dev` and reference the issue with `Refs #<n>` (closing keywords only fire
  on the default branch, so they do nothing in `dev`).
- Promotion PRs (`dev → staging`, `staging → main`) list every issue they carry. Use
  `Closes #<n>` only on the `staging → main` PR.
- After the `main` merge closes an issue, **confirm its Status is Released** and set it if not —
  the Project's built-in "Item closed" automation may move it elsewhere.

### 5. If the board can't be updated

If `gh` lacks the `project` scope or a board update fails, **stop and tell the user** — do not
continue coding with a stale board. Fix with `gh auth refresh -s project`.

---

## Project #1 Reference

| Item | ID |
|---|---|
| Project | `PVT_kwHOCK80dM4BnqMQ` |
| Status field | `PVTSSF_lAHOCK80dM4BnqMQzhmNu0Y` |
| Phase field | `PVTSSF_lAHOCK80dM4BnqMQzhmNu-s` |
| Priority field | `PVTSSF_lAHOCK80dM4BnqMQzhmNu-4` |
| Area field | `PVTSSF_lAHOCK80dM4BnqMQzhmNu-8` |
| Sequence field (number) | `PVTF_lAHOCK80dM4BnqMQzhmNu_A` |

| Field | Option IDs |
|---|---|
| Status | Backlog `f75ad846` · Ready `5daf57af` · In Progress `47fc9ee4` · Agent Review `4e1b35d9` · Done in Dev `98236657` · Staging Candidate `a8546aec` · Released `81727993` |
| Phase | Planning `95094290` · Design `8f692b70` · Implementation `4346f106` · Testing `c17022e6` · Deployment `2f147ee7` |
| Priority | Critical `1c0c1737` · High `e68906f0` · Medium `fa3e95de` · Low `a0d7eb8a` |
| Area | Frontend `487e38a4` · Backend `eb3eed31` · AI/ML `f40e696c` · Infrastructure `964aa312` · Documentation `0ebe01b1` |

If an ID stops working, re-read them with `gh project field-list 1 --owner sandythomas1 --format json`.

### Commands

```sh
# Create an issue, then add it to the Project (prints the project item ID)
gh issue create -R sandythomas1/Case-Study-Tech --title "<title>" --body-file <file.md> --label enhancement
gh project item-add 1 --owner sandythomas1 --url <issue-url> --format json

# Find the project item ID for an existing issue
gh project item-list 1 --owner sandythomas1 --format json

# Set a single-select field (Status, Phase, Priority, Area)
gh project item-edit --project-id PVT_kwHOCK80dM4BnqMQ --id <item-id> --field-id <field-id> --single-select-option-id <option-id>

# Set Sequence
gh project item-edit --project-id PVT_kwHOCK80dM4BnqMQ --id <item-id> --field-id PVTF_lAHOCK80dM4BnqMQzhmNu_A --number <n>

# Post a progress comment
gh issue comment <n> -R sandythomas1/Case-Study-Tech --body-file <comment.md>
```

### Windows gotchas

- `gh` may not be on PATH; call `"C:\Program Files\GitHub CLI\gh.exe"` directly.
- Windows PowerShell 5.1 mangles quotes in inline GraphQL. Write the query to a file and pass
  `gh api graphql -F query=@<file>`. Use `--body-file` instead of inline `--body` for multi-line text.
