# Review: 019-provider-zdr-terms (#19)

Review Depth: **Owner decision**. AiDev never merges this. Diff: docs only, uncommitted.

## policy-reviewer: ESCALATE

| # | Finding | Severity | Resolution |
|---|---|---|---|
| 1 | "Use `us`" for Chirp 3 makes a region exception to ARCHITECTURE §6 (`us-central1`) and gets ahead of OQ-01 / #20 | Blocking | **Resolved by owner decision, 2026-11-22.** Chirp 3 runs in `us`. The exception is recorded in ARCHITECTURE §6 and is setting 12. |
| 2 | AC1 asks for "confirmation or rejection". "Pending" is neither, and whether published terms count as written is an owner call (AGT-3) | Blocking | **Resolved by owner decisions, 2026-11-22.** The ACs are split: #19 documents and #115 confirms. A written-terms rule is now in the record. |
| 3 | STT row said "Yes" despite two UNVERIFIED items | Non-blocking | Fixed: "Likely, see open items 4 and 5" |
| 4 | TTS row said "Yes" when the training part is only inferred | Non-blocking | Fixed: retention and training stated separately |
| 5 | OpenAI file STT row left out the general abuse logging, §11.3 and CSAM-scan caveats | Non-blocking | Fixed: caveats and open item 8 |
| 6 | The Frontier rejection missed Argon Cyber Permissive and Model Garden partner models | Non-blocking | Fixed: both rows are rejected |
| 7 | The Agent Platform cell left out implicit caching as a second barrier | Non-blocking | Fixed |
| 8 | Three research open items were missing | Non-blocking | Fixed: open items 5, 8 and 9 |
| 9 | research.md cited ETH-7 for crisis role-play | Non-blocking | Fixed: SES-2, SES-8, RC-19 |
| 10 | Setting 1 had two owners and prescribed #65's design | Non-blocking | Fixed: #65 decides how |

The reviewer confirmed that the record claims no confirmation or applied setting, contains no secret or
session data, and correctly makes OpenAI conditional on DAT-5 and #20. The owner has since dropped OpenAI.

I didn't send it back to the policy-reviewer. Every change since that review only records an owner decision,
and with Review Depth set to Owner decision, the owner reviews the PR anyway.
