# Spec: Three vetted scenario configurations (#27)

Issue: #27 · Review depth: Deep (owner merges) · Satisfies RC-22, DD-07 · Constrained by PA-5, CD-3, CD-4, AG-6

## Outcome
The session service holds exactly three vetted, version-controlled scenario configurations. Its code
can list the released ones for the library and refuse to start one that is not released. Nothing
in the product can create or edit a scenario.

## Requirements
- FR-1. Each configuration has: id, version, title, a short summary (the library card, #28), the
  learning objective, the session format, the time limit in minutes, the feedback timing, the
  content notice, the crisis flag, the opt-in flag and its statement, and the release flag.
- FR-2. The ids are `routine_intake`, `resistant_client` and `crisis_risk`, the same ids as
  `rubric/anchor-spec.v1.json`. The version is `MAJOR.MINOR.PATCH`.
- FR-3. The configurations are TOML files inside the `cst_session` package. They are read with the
  stdlib only. A missing, unknown or wrong-typed key fails loading, and so does any set of files
  other than the three expected ids.
- FR-4. The time limit is read from configuration and is 10 minutes for every scenario (PA-5, CD-4).
- FR-5. A crisis scenario must require opt-in and carry an opt-in statement. A scenario carries an
  opt-in statement if and only if it requires opt-in (SES-2).
- FR-6. `Catalogue.library()` returns the released scenarios in a fixed order.
  `Catalogue.startable(id)` returns a released scenario, or raises `ScenarioUnavailable`. It raises
  the same error for an unknown id and an unreleased one, so a held-back scenario can't be probed (CD-3).
- FR-7. Loaded scenarios and the catalogue are immutable. The module offers no create, edit or write
  function, and no service declares a write route for scenarios (AG-6).
- FR-8. The logging helper's `scenario_id` accepts exactly these three ids (fix carried from #63).
- FR-9. The content is synthetic. The wording comes from the prototype behind SDD Figures 3 and 4.

## Acceptance criteria (from #27)
- AC1. Exactly three configurations load and pass schema validation.
- AC2. A test confirms that the time limit is read from config and is 10 minutes for each scenario.
- AC3. A test shows that turning a release flag off hides the scenario from the library and blocks
  it from starting. Owner decision, 2026-11-23, verbatim: "Prove at the shared seam (Recommended)".
  The proof is on `library()`/`startable()`, which #28 and #31 must call, and those Issues add
  endpoint-level tests.
- AC4. A test shows that no API path creates or edits a scenario.

## Non-goals
- Persona prompts and client names (#67). The library and preparation screens (#28, #29). Session
  start and the timer (#31). An HTTP endpoint (owner decision above).

## Release flags
All three start released. The plan says the flag "hides a scenario held back under §6 CD-3", and
none is held back yet. The owner approves the release flags (POLICY §1). Owner decision 2026-11-23, verbatim: "Approve now, record on PR (Recommended)". All three ship released.
