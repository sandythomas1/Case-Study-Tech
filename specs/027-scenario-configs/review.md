# Review: Three vetted scenario configurations (#27)

Review depth: **Deep** (owner merges). Reviewers: policy-reviewer (project) and qa-tester (verify).
Security, architect, UX and critic were not routed (see build-log.md). No blocking finding is open.

## Owner decisions
- **AC3 scope.** Proved at the shared `library()`/`startable()` seam. #28 and #31 add the
  endpoint-level tests. Sandy, 2026-11-23, verbatim: "Prove at the shared seam (Recommended)".
- **Release flags (POLICY §1).** All three ship `released = true`, per DD-07 ("exactly three"); CD-3 has
  not been triggered. Sandy, 2026-11-23, verbatim: "Approve now, record on PR (Recommended)".

## Findings and dispositions

| # | Sev | Source | Finding | Disposition |
|---|---|---|---|---|
| 1 | — | policy | POLICY §1: the owner approves release flags, including their first values | Approved by owner (above) |
| 2 | LOW | policy | README and spec reworded §1 as "any change to" a flag, which narrows the rule | Fixed: "The owner approves the release flags (POLICY §1)" |
| 3 | LOW | policy | `startable()` checks only the release flag. SES-2 also needs a server-side opt-in check at session start | Fixed for hand-off: the session README tells #31 to refuse a `requires_opt_in` scenario without the opt-in, checked on the server. No #27 code change |
| 4 | info | policy | Config wording matches the prototype behind SDD Fig. 3/4 (App.tsx). The reviewer could not compare it with the rendered figures | Owner checks against Fig. 3/4 in the Deep review |
| 5 | LOW | qa | `_text` let U+2028/U+2029 line separators into "one line" fields | Fixed: also rejects Zl/Zp, with two failing-first cases |
| 6 | info | qa | `specs/*/demo/` isn't gitignored | Not committed. Media is on `pr-media` |
| 7 | info | policy | The helper change touches services/accounts (from #63, outside #27's ACs) | Accepted: carried from #63 because PR #131 merged before the fix. Spec FR-8. The PR says Refs #63 |
| 8 | info | qa | A stray `*.TOML`/`*.toml.bak` file is ignored, not rejected | Accepted: it cannot add a scenario, because the loader requires exactly the three expected names |

## Residual
- The route check can't see a path built at run time. Code review covers that. The check scans every
  `services/*/cst_*` package, so the session and grading HTTP apps are covered when they land.
