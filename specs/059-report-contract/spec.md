# Spec: Versioned report contract and synthetic fixtures (#59)

Issue: https://github.com/sandythomas1/Case-Study-Tech/issues/59 · Review depth: Standard ·
Human Review: Reviewed (owner, 2026-11-23: "#27 and #59 (Recommended)").

## Outcome

The report screen (#38), history (#41) and export (#42) can be built and tested against a
fixed, versioned report shape and synthetic fixtures, without a live grader, an approved rubric or a
passed calibration. The grader (#35) has one shape to produce and the score record (#40) one
projection to keep.

## Requirements

- R1. One versioned contract (`cst.report` and `cst.history`, version 1.0.0) with six report states:
  pending, scored, safety not demonstrated, insufficient evidence, narrative only and failed. Each
  state has explicit required and forbidden fields.
- R2. An unavailable value is never a number. No overall score appears unless all six categories are
  rated, and it is the SCO-2 weighted mean computed in code. Abstentions and failures carry reason
  codes, never zero, a midpoint or a reweighted average (SCO-3, anchor spec).
- R3. In the crisis scenario, a critical safety failure leads. Any average it carries is marked
  secondary (SCO-5, REP-4).
- R4. A failed attempt carries no score, no narrative and no evidence. It says whether the
  conversation is still available and that no score was saved (REC-2 to REC-4).
- R5. Evidence cites turns inside the transcript's turn count. A report citing any other turn is
  invalid (SCO-4).
- R6. The transient report (narrative, evidence) is kept separate from the history projection
  (score-record fields only, DAT-1/DAT-2). Any new persisted provenance field is a proposal owned
  by #40 and is not adopted here.
- R7. History comparison is compatible, incompatible or unknown, decided from non-content
  provenance only.
- R8. Versioning and compatibility rules for producers and consumers, and what a consumer does with
  a version or state it cannot read.
- R9. Synthetic fixtures for every state and the history projection, plus invalid validation
  cases. A standard-library checker proves each fixture is valid and each invalid case is rejected.
  CI runs it through the existing fixtures job.
- R10. Unresolved policy and schema decisions are recorded, each with its owner Issue. Nothing
  claims clinical, rubric, weighting or calibration approval.

## Acceptance criteria (from #59)

- AC1. The contract covers the numerical, unscored, insufficient-evidence, pending, failure and
  primary crisis outcomes, with explicit field invariants.
- AC2. #38, #41 and #42 can develop and test presentation using synthetic fixtures, without a live
  grader or an approved numerical scale.
- AC3. Example unavailable or ineligible reports contain no publishable invented score. Synthetic
  numerical examples are clearly identified.
- AC4. Transient narrative data and the permitted history projection are separated. Any required
  storage-policy decision has an owner in #40.
- AC5. Producer and consumer responsibilities, versioning and incompatibility behavior are
  documented without claiming clinical or grading-policy approval.

## Non-goals

- No grader, report screen, history screen, export or Firestore change. Those belong to #35, #38,
  #41, #42 and #40.
- No user-visible wording. The report carries rubric labels and the anchor-spec disclaimer, and
  screen copy stays with #38, #41 and #42.
- No transcript, excerpt, narrative or prompt retention. The DAT-1 saved transcript is outside this
  contract.
- No new dependency. The checker uses the standard library, like `check_anchor_spec.py`.

## Interpretations (no conflict with POLICY; recorded for review)

- The Issue says "optional policy-defined weights". POLICY SCO-2 fixes the weights, so the report
  carries them as rubric provenance and the consumer never computes with them.
- The Issue says "insufficient-evidence/review-required". The MVP has no human reviewer: the admin
  may not see reports (POLICY §1), and faculty review was removed (PA-10). The state is
  `insufficient_evidence`, with no review path.
- The Issue says "unscored formative feedback". This is `narrative_only`. It is named so that it
  can't be confused with POLICY's "unscored attempt", which is a failure that carries no feedback.
- ARCHITECTURE §7 keeps transcripts and excerpts out of test fixtures, and DAT-1 lists test
  fixtures among the places session content never reaches. Both are about real session content.
  The fixtures hold short synthetic quotes written for them, as DAT-6 requires of dev and test data,
  because SCO-4 traceability can't be tested without a quote to trace. Each fixture says
  `synthetic: true`. Flagged for policy-reviewer.
