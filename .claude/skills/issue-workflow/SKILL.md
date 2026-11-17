---
name: issue-workflow
description: Gate checks and steps for starting or shipping a GitHub Issue on Project #1. Use before the first code change on an Issue ("work on #n", "start", "pick up") and when its work is ready for a PR into dev.
---

# Issue workflow

Two procedures: **Start** and **Ship**. The rules they apply live in `CLAUDE.md`. Field IDs, option IDs
and `gh` commands live in `docs/PROJECT_BOARD.md`. This Skill sets the order and the checks.

## Start

Run checks 1–5 before you branch, edit a file or change the board, and run all of them even after
one fails. If any fail, stop. Change nothing, and tell the owner every check that failed, with its
evidence: the field value or the blocker's number and state. Never fix a failed gate yourself.

1. Read the Issue body, then its gates with "Check an Issue's gates" in `docs/PROJECT_BOARD.md`.
2. **Human Review is Reviewed.** If it is Pending, refuse. Only the owner sets Reviewed.
3. **Status is Ready.** Backlog means it is not refined. In Progress or later means someone else may
   own it.
4. **Every blocker is clear.** Each blocked-by Issue is closed or has Status Agent Review or later.
   Run the same query on each open blocker to read its Status. Name each blocker that fails, for
   example "#17 is open and In Progress".
5. **No open decision applies.** The Issue's open decisions (OD-n) are settled, and nothing in it
   conflicts with `docs/POLICY.md` or `docs/ARCHITECTURE.md`. On a conflict, stop and ask
   (POLICY AGT-1).
6. Run `git fetch origin` and branch from `origin/dev` as `feature/<n>-<short-slug>`.
7. Set Status to In Progress, then post a progress comment that says what you will do first.

## Ship

1. Run the checks in `CLAUDE.md` "Commands" for each component you touched. Fix failures, or report
   them with their output. Never leave a failure out of the report.
2. Get evidence for every acceptance criterion: a test, command output or screenshot. A criterion
   with no evidence stays unticked, and the PR says so.
3. Commit only this Issue's files, then open the PR into `dev` as `CLAUDE.md` "Git and PRs" says.
   The body lists each criterion with its evidence, the checks you ran with pass and fail counts,
   and any decision a reviewer should look at.
4. Set Status to Agent Review.
5. Route review by the Issue's Review Depth field. Run the reviewers that the `CLAUDE.md` "Agents"
   table names for this diff. Who may merge is set in `CLAUDE.md` "Git and PRs", and any change
   to `CLAUDE.md`, `.claude/` or `.github/` always waits for the owner.
6. Post a progress comment with the evidence. Tick only the criteria you verified.
7. After the merge into `dev`, set Done in Dev. If the merge clears the last blocker on another
   Issue, move that Issue from Backlog to Ready and comment which merge did it.
