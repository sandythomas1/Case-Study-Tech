# Build log: 019-provider-zdr-terms (#19)

- 2026-11-22 10:45 · Overnight run (brief `C:/Users/sandy/Desktop/dev/docs/overnight/2026-11-22.md`). Worktree
  `applied_ai_behavioral_sciences-overnight-19-provider-zdr-terms`, branch `feature/19-provider-zdr-terms` from origin/dev a365ed4.
- Gates (issue-workflow Start): 0 config current ✔ · Human Review Reviewed ✔ · Status Ready ✔ · no blockers ✔ · no open OD ✔.
  Review Depth: **Owner decision** (AiDev never merges).
- Board: Ready → In Progress. Comment https://github.com/sandythomas1/Case-Study-Tech/issues/19#issuecomment-7083834985
- Change surfaces: security/data (third-party processors), domain/policy (DAT-4, PA-3). Docs only, no code.
- Prior art: draft PR #100 `specs/inprogress-sweep-2026-11-18/speech-providers.md` (speech research 2026-11-18). Reuse it, re-verify.
- Roster: general-purpose researcher (web) · policy-reviewer (review). Skipped: architect (no structure), implementer/qa (no code),
  ux (no UI), security-reviewer (no auth/rules/secrets change; policy-reviewer covers third-party data rules).
- Expected outcome: park. AC1 needs vendor written confirmation, and AC2 needs the owner to apply settings in consoles. Both are owner-only.

## Dispatches
- 10:50 SENT · general-purpose (research) → specs/019-provider-zdr-terms/research.md
- DONE (by 10:55) · research: Vertex needs abuse-monitoring exemption or MA (ToS §4.3, 90-day flagged logs); Google STT/TTS can meet
  with settings; OpenAI file STT can meet by default, Realtime/TTS need ZDR approval. 8 UNVERIFIED items listed.
- Lead wrote docs/decisions/provider-zero-retention.md (Draft, nothing confirmed or applied).
- (research routing, 10:50: "Reduces the uncertainty about what each vendor's current published terms actually say (retention,
  abuse logging, training, tier dependence), with primary-source URLs, which I can't settle from the repo.")
- SENT · policy-reviewer · routing: "Checks that the record's verdicts and rejections match DAT-4/DAT-5, PA-3, CD-2 and #19's
  ACs, and that it claims no confirmation or setting that doesn't exist — an independent read of a policy-gating doc."
- DONE · policy-reviewer: ESCALATE. 2 blocking (Chirp 3 `us` region vs ARCHITECTURE §6; AC1 "Pending" is neither confirmation
  nor rejection, and "what counts as written" is an owner call), 8 non-blocking. No overclaimed confirmation or applied setting.
- Lead fixed all 8 non-blocking findings and removed "Use `us`" from Required settings (now open item 6, owner decision).
  The two blocking findings are owner decisions, so they're parked, not settled.
- PARKED · 4 DECISION NEEDED + 3 HUMAN ACTION REQUIRED in the overnight brief. Worktree left uncommitted and unpushed.
  Resume: `/build 019-provider-zdr-terms` in this worktree once the decisions are recorded.

## Resumed with the owner (2026-11-22, same session)
- Owner decisions:
  - (4) Drop OpenAI.
  - (2) C, split the ACs.
  - (3) Chirp 3 runs in the `us` multi-region; recorded in ARCHITECTURE §6.
  - (1) Published terms plus settings evidence for Google speech. One support case for the Vertex
    exemption.
- Lead edits:
  - Record: OpenAI rows collapsed to Dropped; setting 12 added; the written-terms rule added; the
    request narrowed to one Vertex case; "Owner decisions" section added.
  - ARCHITECTURE §6 Cloud row now has the Chirp 3 exception.
  - spec.md: ACs and the open question updated.
- Created #115, "Confirm provider terms and apply zero-retention settings". It covers the confirmations,
  the applied settings and the final verdicts. Board: Backlog, Human Review Pending, Review Depth Owner
  decision.
- #19 body: ACs rewritten to the documentation scope. Because the scope changed, Human Review was reset
  to Pending (AGT-4).
- policy-reviewer was not dispatched again. Every change since its review records an owner decision,
  and Review Depth is Owner decision, so the owner reviews the PR anyway.
- Shipped as a docs-only PR into `dev`. It has no demo GIF, and the PR says why.
