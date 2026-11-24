# Tasks: 059-report-contract

Status: done

- [x] T1 @lead: Write the contract (`report/report-contract.v1.md`). It covers the states, the field
  table, invariants, the transient-versus-retained mapping, ownership, versioning, comparison and
  open decisions (R1–R8, R10).
- [x] T2 @lead: Write the checker `scripts/ci/check_report_contract.py`. It uses the standard library
  and cross-checks against `rubric/anchor-spec.v1.json` (R2–R5, R7, R9).
- [x] T3 @lead: Add synthetic fixtures for every state and the history projection
  (`report/fixtures/v1/`), and invalid cases (`report/validation-cases/v1/`) (R9).
- [x] T4 @lead: Write unit tests in `scripts/ci/tests/test_check_report_contract.py`, which CI's
  fixtures job runs (R9).
- [x] T5 @lead: Write `report/README.md`, add the ARCHITECTURE §5 pointer, and confirm the
  synthetic-fixture name check passes.
- [x] T6 @qa: Independently prove AC1–AC5, try to break the checker, and record the demo
  transcript GIF.
- [x] T7 @policy-reviewer: Review the diff against POLICY and ARCHITECTURE (contract, scores,
  session data).
