# Build log: 059-report-contract

## 2026-11-23 Phase 0 — Intake
- Standing request (Sandy): "continue working until we have one of the issues open and milestone 2
  complete." Owner choice, verbatim: "#27 and #59 (Recommended)". #27 is in PR #132, and #59 is next.
- Start gates 0–5 pass:
  - The config matches origin/dev becffd3.
  - Status is Ready, and Human Review is Reviewed (quoted on #59).
  - There are no blockers.
  - No open decision conflicts. The Issue's wording is interpreted in spec.md: weights fixed, no
    review path, and narrative_only.
- Base: origin/dev becffd3. Branch: `feature/59-report-contract`. Board: In Progress, with a comment
  on #59.

## Phase 1 — Frame and route
- Surfaces: a cross-service contract, the score-record projection, and report states (structure
  only).
- The deliverable is documentation plus fixtures, and its precedent is `rubric/` with
  `check_anchor_spec.py`. The lead holds the full POLICY, ARCHITECTURE and anchor-spec context, so
  the lead writes it.
- Roster:
  - qa-tester: gives independent proof of AC1–AC5 and tries to break the checker's invariants.
    Records the demo GIF.
  - policy-reviewer: required by CLAUDE.md, because the diff adds a contract touching scores and
    session data. It checks DAT-1/2, SCO-*, REP-* and REC-*.
  - Skipped:
    - architect: the contract shape follows the rubric precedent, and the lead has the context.
    - ux and domain: no wording or rule is decided here, and open items are recorded for their
      owners.
    - security-reviewer: no auth, rules or secrets change. Privacy is covered by policy-reviewer.
    - critic: there is no disagreement.
    - implementer: a small, doc-heavy diff.

## Phase 4 — Implement (lead)
- T1–T5 done: the contract page, the stdlib checker (reads the anchor spec), 12 fixtures, 33 invalid
  cases, 6 comparisons and 41 tests. L0 fixes along the way: an early return on missing or forbidden
  fields, unhashable-value guards, the overall computed from the rubric's weights, and 3.12-safe
  `dataclasses.replace`.
- Local checks: unittest discover on 3.12 OK, the checker passes, check_anchor_spec passes, ruff and
  mypy --strict clean on the two new files.
- Recorded interpretation: synthetic quotes in fixtures (DAT-6 vs ARCH §7), flagged for policy-reviewer.

## Phase 5 — Verify
- DONE qa-tester: PASS, AC 5/5. F1 Medium (a crisis safety result could be dropped), F2–F4 Low. Demo GIF
  recorded in specs/059-report-contract/demo/.
- DONE policy-reviewer: ESCALATE. Two blocking:
  - SCO-5/ETH-7: a crisis `narrative_only` report may leave out `safety`, so a critical failure can go
    unreported before calibration (D-4).
  - DAT-2/AGT-3: D-5 (persisting provenance) amends an owner rule, so #40 can't own it.
  Also routed to the owner: D-3. Non-blocking fixes applied by the lead (doc only): the D-3/D-5 owner
  wording, the ETH-1/ETH-2 fixed text owned by #38/#42, the fixture-marking scope, the README
  pointing at the allow-list, the history provenance illustration note. Deferred: the POLICY §2 and
  plan AC 405 wording for states without an overall, to route with #35.
  DAT-6 synthetic-quote interpretation: the reviewer agrees.
- ESCALATE → owner (CLAUDE.md: never settled by the lead). The #59 merge waits for the answer.

## Owner decisions (2026-11-23, verbatim)
- "Always require it (Recommended)", "Decide later, null now (Recommended)", "No record, decide at
  #40 (Recommended)".
- The lead applied them and fixed F1–F4: 4 new invalid cases and 5 new tests. Re-run: 196 tests OK,
  the checker passes, and all 22 QA mutations are rejected. review.md has no open blocking finding.

## Phase 6 — Ship
- Commit 8302248 on `feature/59-report-contract`, pushed. Demo re-recorded with a crisis-safety scene, on pr-media daa2a48.
- PR #133 into dev (Standard review: AiDev merges once CI is green). #59 → Agent Review; progress comment 7124487510. CI: all 8 jobs pass.

## Phase 7 — Learn and close
- Lessons appended: "An \"optional\" field in a contract can silently relax a safety invariant"; "Tool input decodes \uXXXX, so escape sequences written into source become raw characters".
- Final roster: qa-tester (1), policy-reviewer (1). 2 dispatches total. Owner decisions: 3 (crisis safety always carried, D-5 null, D-3 no record).
- After merge: delete docs/current_feature_plans/059-report-contract.md and set #59 Done in Dev.
