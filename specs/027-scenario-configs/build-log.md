# Build log: 027-scenario-configs

## 2026-11-23 Phase 0 — Intake
- Request (Sandy): "continue working until we have one of the issues open and milestone 2 complete."
- No Milestone 2 Issue passed the Start gate (Human Review Pending). Sandy's choice, verbatim:
  "#27 and #59 (Recommended)". Set Reviewed on both; quoted in #27 comment 7123052510 and #59
  comment 7123053240 (AGT-4).
- Start gates 0–5 pass for #27 (config clean vs origin/dev; Ready; Reviewed; #18 closed; no OD).
- L2 asked: AC3 has no endpoint yet. Sandy, verbatim: "Prove at the shared seam (Recommended)".
- Resolved without asking: the wording comes from the prototype source behind SDD Figs. 3 and 4
  (`tmp/docx_section678/proto/App.tsx`), and all three release flags start on (plan Phase 1: the
  flag "hides a scenario held back under §6 CD-3").
- Found: the #63 helper accepted only hyphen-slug scenario ids, while the merged anchor spec uses
  snake_case. Fixed in bd329dc on feature/63, but PR #131 merged (becffd3) before the push, so the
  fix is carried on this branch (FR-8).
- Board: #63 Done in Dev; #66 Backlog → Ready (its last blocker closed); #27 In Progress.
- Base: origin/dev becffd3.

## Phase 1 — Frame and route
- Surfaces: session domain (a new module), user-visible wording (settled by the figures), logging id shape.
- Roster:
  - lead implements T1–T3. It is small and well defined, so an implementer hand-off adds no certainty.
  - qa-tester: independent mutation proof of AC1–AC4 and the demo.
  - policy-reviewer: CLAUDE.md requires it, because the diff touches a service, logging and user-visible text.
  - Skipped: security-reviewer (no auth, access, secrets or student data; the logging change only
    narrows an allow-list, which policy-reviewer covers), architect (one module inside an existing
    service, with no contract), ux (the wording is copied from the figures), critic (no disagreement).

## Dispatches
- L1 lead built T1–T3: session 252 passed; accounts 204 passed / 5 skipped; ruff, format and mypy clean.
- D1 PENDING qa-tester (verify). Routing: an independent mutation proof that each AC test fails when its behavior breaks, plus the demo transcript.
- D2 PENDING policy-reviewer. Routing: CLAUDE.md requires it, because the diff touches a service, logging (the scenario_id shape) and user-visible scenario wording against POLICY SES-1–SES-4, RC-22 and AG-6.
