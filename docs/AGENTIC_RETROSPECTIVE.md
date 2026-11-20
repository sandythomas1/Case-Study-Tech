# Agentic retrospective: first run, Issue #64

**Run:** 2026-11-17, AiDev (`sandytdev`) in one Claude Code session on Windows.
**Outcome:** #64 shipped. PR #91 had 2 commits and was squash-merged by the owner into `dev` as
66f33d4. Its tree is identical to the verified head 4d63057. #64 is Done in Dev. 44 tests passed, and
ruff and mypy were clean. AiDev did not merge, as Deep review requires.

## What worked without correction

| Behavior | Evidence |
|---|---|
| Gates checked before any code | Ready and Human Review = Reviewed confirmed, then In Progress and a start comment at 16:34 PST, 8 minutes before the first commit |
| Merge rule held | PR #91 opened into `dev` with `Refs #64` and left for the owner |
| Evidence-based PR | Each criterion is mapped to named tests. QA's 8 mutant providers and planted vendor imports were all caught |
| Review loop | The owner's non-blocking finding was fixed on the branch as wording only, rechecked and commented |
| Honest gaps | The evidence report flagged the missing CI, the stand-in reviewer and the #31 follow-up instead of hiding them |

## Problems

| # | Observation | Evidence | Root cause |
|---|---|---|---|
| 1 | **The session ran on stale configuration.** It started at 16:32 on local `dev` at aa6ea60 (2026-10-18), which predates every Lab 4 config file. AiDev checked out 0cb78fb at 16:33 but kept the old instructions | Reflog shows `aa6ea60 → 0cb78fb` at 16:33. The project `CLAUDE.md` loaded at session start was the pre-Lab 4 version. `Agent type 'policy-reviewer' not found`. `issue-workflow` was read as a file, never loaded as a Skill | Claude Code loads `CLAUDE.md`, Skills and agents at session start and did not pick up the checkout's versions. Nothing checks that the loaded config matches `origin/dev`, and the launch kit's preflight was skipped |
| 2 | **A reviewer was mislabelled.** The policy review ran as a general-purpose stand-in, but the PR body said "policy-reviewer" until the owner's pass | The PR body before 4d63057, and the transcript | Consequence of #1. No rule says to report the agent type that actually ran |
| 3 | **Human-process contamination.** The whole launch-kit email was pasted, observer notes included ("If it tries to merge, stop it") | The first user message | Launch procedure, not config |
| 4 | **Environment gaps.** `uv` was missing, and a PowerShell here-string commit failed, so the push sent no new commits | Two owner interventions, then a recommit from a message file | Preflight item still open. The Windows gotchas don't cover `git commit` |
| 5 | **No CI on PRs.** Every result was local | PR #91 had 0 status checks | Not set up yet |

Problem 1 matters most. The run went well partly by luck: the older `CLAUDE.md` already had board
rules, and AiDev re-read the new files by hand. Problems 2 and part of 4 came from it.

## Recommended improvement (one)

Add check 0 to the `issue-workflow` Skill's **Start** procedure. It confirms that the session's
loaded configuration is current before any gate check.

> 0. **The session's configuration is current.** Run `git fetch origin`. If `CLAUDE.md` or `.claude/`
>    on `HEAD` differs from `origin/dev`, or a checkout, pull or merge in this session changed them,
>    stop. Tell the owner to update the checkout and restart Claude Code in it, because these files
>    may not be picked up by a running session.

**Why this should help:** it catches the exact failure in this run. The 16:33 checkout changed
`.claude/` and `CLAUDE.md`, so AiDev would have stopped before 16:34 and the real `policy-reviewer`
would have run. It costs one `git diff --quiet` and adds no new mechanism. It also covers future config
changes that merge while a local checkout lags. A Skill can't help a checkout that predates the Skill,
so the launch kit's preflight (update `dev`, then start Claude) still matters for that case.

## Other candidates (not recommended now)

- A `SessionStart` hook that warns when `HEAD` is behind `origin/dev`. It catches drift earlier but
  adds an executable hook. Revisit if check 0 proves too late.
- Ship rule: the PR body names the agent type that actually ran. Problem 2 goes away once check 0
  makes stand-ins rare.
- Windows gotcha in `docs/PROJECT_BOARD.md`: commit with `git commit -F <file>`, never a piped
  here-string.
- Add `uv` and Python 3.12 to the launch preflight list. Keep observer notes out of the paste.
- CI for `services/*` (lint, type check, test), as a normal Issue, not a config change.

## Final change made

The owner approved the recommended change on 2026-11-17. `.claude/skills/issue-workflow/SKILL.md`
**Start** now begins with check 0 as quoted above, plus the exact command
`git diff --quiet HEAD origin/dev -- CLAUDE.md .claude`. "Run checks 1–5" now reads "Run checks
0–5". Nothing else changed.
