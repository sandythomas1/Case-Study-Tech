# Review: #66 completed-session handoff contract

Review depth: Deep (the owner merges). Reviewers: qa-tester (verify), policy-reviewer, security-reviewer (audit).

## Owner decisions (2026-11-23, verbatim)

- "UID field in payload (Recommended)": the contract carries `owner_uid`, copied from the identity
  the session service already verified, and never logged.
- "Add save_transcript now (Recommended)": a required `save_transcript: bool` in v1, with no
  default. When it is false, the grader never stores the transcript (POLICY DAT-1,
  transcript-storage D4).
- "Approve (Recommended)": pydantic is approved as a new dependency of services/session
  (ARCHITECTURE §8).

## Findings

| # | Source | Severity | Finding | Disposition |
|---|---|---|---|---|
| 1 | policy | ESCALATE (blocking) | No per-session "don't save" field, so the grader can't honour DAT-1 / D4 | **Fixed** per the owner's decision: `save_transcript` is required, the fixtures carry it, `malformed--save-choice-missing.json` covers a missing one, and it is documented in the README |
| 2 | policy | ESCALATE | pydantic is a new dependency | **Approved** by the owner |
| 3 | policy | Blocking | The time-limit fixtures used 900000 ms, over the 10-minute limit (SES-5) | **Fixed**: 600000. The README says the session service enforces the configured limit, and the one-hour ceiling is a sanity bound |
| 4 | security, QA F1 | Medium | The 2 MiB cap was below the largest valid payload (non-ASCII text) | **Fixed**: 5 MiB, sized from 500 × 2000 × 4 bytes. `encode_handoff` writes raw UTF-8. A worst-case round-trip test covers ASCII, Latin, CJK and emoji |
| 5 | security, QA F2 | Low | Invisible-only text was accepted. The BOM split the Rust and ECMA engines | **Fixed**: bidi controls and the BOM are forbidden. Invisible characters can't be the visible character. Joiners and marks stay allowed beside visible text (Persian, Indic, emoji). A schema-pattern agreement test covers it |
| 6 | security, QA F3 | Low | UTF-16 and BOM bodies were accepted | **Fixed**: strict UTF-8 decode, so a BOM is rejected |
| 7 | security | Low | Python `re.search` `$` allows a trailing newline in schema-only consumers | **Fixed**: SessionId has length 36. The README requires full-match ECMA patterns and `validate_handoff` for the cross-field rules |
| 8 | security | Low | `HandoffRejected.__traceback__` frames hold the payload in their locals | **Deferred to #68 with a guard**: the README and the docstring say to catch it at the handler and return a fixed 4xx, never passing it to a reporter that captures locals (DAT-5) |
| 9 | security | Low | `model_copy` and `model_construct` skip validation | **Deferred to #68**: the README says the grader uses only what `parse_handoff` returns |
| 10 | security | Low (grader side) | Invoker IAM, idempotent writes, the scenario-version registry, the HTTP body cap, prompt injection, the UID source | **Deferred to #35/#68**: listed in README "For the grader" |
| 11 | policy | Non-blocking | "A text session has no speech turns" was cited as REC-1 | **Fixed**: now worded as a contract rule that follows from SES-6 and REC-1 |
| 12 | policy | Non-blocking | The version policy covered only major versions | **Fixed**: every version change ships grader support first, and the owner's deploy order enforces it (AG-9). The README and the contract.py comment were updated |
| 13 | QA F4 | Info | A completed session with no student turn is accepted | **Deferred** as a product question for #35. No AC covers it |
| 14 | security re-check | Low | More invisible characters (soft hyphen, CGJ, ALM, variation selectors, annotation and tag characters) could stand in for the visible character, and tag characters beside text can smuggle hidden text to the grading model | **Fixed**: they're added to the invisible set. Tags stay allowed beside text because the subdivision flags need them. The README tells the grader to strip tag and format characters before prompting and notes that ECMA consumers need the `u` flag. The schema-agreement test covers it |
| 15 | policy re-check | Optional | Make clear that `save_transcript: true` doesn't by itself start storage | **Done**: the README says storage starts only once `transcript-storage.md` takes effect |

No open blocking finding.

## Re-checks

- **policy-reviewer: CLEAR.** All four earlier findings are closed, both escalations are settled by the owner, and the fixes add no new conflict.
- **security-reviewer: no blockers.** All seven earlier findings are closed. The worst-case body is 4,065,746 B, under the 5,242,880 B cap. The encoding, save choice, bidi and BOM fixes are verified, and the Python and Rust regex engines disagree on no character in the probe ranges. Finding 14 is the one new Low, fixed as recommended. `git status` was unchanged before and after the review.
- Final run after fix round 2: 432 tests pass, ruff check and format are clean, mypy is clean, and the synthetic-fixture check passes.
