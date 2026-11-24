# Review: report contract v1 (#59)

Review depth: Standard. The reviewers were policy-reviewer (ESCALATE) and qa-tester (PASS with
findings).

## Owner decisions (2026-11-23, verbatim)

- Crisis safety: "Always require it (Recommended)". Every crisis report in an assessed state carries
  its safety result.
- Provenance: "Decide later, null now (Recommended)". D-5 is an owner decision raised by #40. v1
  keeps the field as a proposal, and a record without it compares as `unknown`.
- Crisis record: "No record, decide at #40 (Recommended)". D-3 stays "no record" until #40 brings a
  POLICY §2 change.

## Findings

| # | Source | Severity | Finding | Disposition |
|---|---|---|---|---|
| 1 | policy | BLOCKING | A crisis `narrative_only` report could leave out `safety`, so a critical failure could go unreported (SCO-5, ETH-7) | Fixed by the owner's decision: safety is required in every assessed crisis state, in the contract §3 and the checker |
| 2 | policy | BLOCKING | D-5 (persisting provenance) amends DAT-2, so #40 can't own it (AGT-3) | Fixed: D-5 and D-3 are now "Owner, raised by #40", and history.json's provenance is marked as illustrating the proposal |
| 3 | policy | NON-BLOCKING | Line 194 said #40 decides D-3 | Fixed |
| 4 | policy | NON-BLOCKING | Crisis `insufficient_evidence` could omit safety | Fixed with #1 |
| 5 | policy | NON-BLOCKING | ETH-1/ETH-2 static text is not named for the report and export | Fixed: contract §6 says #38 and #42 own it |
| 6 | policy | NON-BLOCKING | The fixture-marking claim was overstated for `pending` and `failed` | Fixed: contract §10 |
| 7 | policy | NON-BLOCKING | The README advised naming files around the content check | Fixed: it now points to `.github/synthetic-fixtures.allow` |
| 8 | policy | NON-BLOCKING | POLICY §2 terms and plan AC 405 assume every graded session has an overall | Deferred: route with #35, which owns the wording amendment. No live conflict, because the Issue and the merged anchor spec define abstention. |
| 9 | qa F1 | Medium | The crisis safety result could be dropped while rating the scenario category | Fixed with #1 |
| 10 | qa F2 | Low | A repeated turn counted towards the two-turn minimum | Fixed |
| 11 | qa F3 | Low | Unicode line separators passed the one-line quote check | Fixed |
| 12 | qa F4 | Low | An impossible `completed_at` and a fractional weight passed | Fixed |

The DAT-6 synthetic-quote interpretation was agreed by the policy-reviewer, with no escalation.

No blocking finding remains open.
