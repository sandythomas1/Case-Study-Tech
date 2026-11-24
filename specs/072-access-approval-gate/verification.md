# Verification: #72 owner approval gate

QA run on 2026-11-24 (T10), branch `feature/72-access-approval-gate`, uncommitted working tree, including the
lead's mid-run fix (a race that finds a denial raises `AccessDenied`). The Firestore emulator ran on
`127.0.0.1:8085`, project `demo-casestudy-tech`. Accounts commands run in `services/accounts` with
`FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 GOOGLE_CLOUD_PROJECT=demo-casestudy-tech`.

## Acceptance criteria

| AC | Proven by | Command | Result | Evidence |
|---|---|---|---|---|
| AC1. First request creates one `pending` record; repeated or concurrent requests leave exactly one; a `denied` request is rejected and creates nothing | `test_access.py`: `test_a_first_request_creates_one_pending_record_from_the_token`, `test_a_repeated_request_returns_the_existing_state_and_adds_nothing`, `test_a_denied_account_cannot_request_again`, `test_a_racing_request_that_finds_a_denial_is_rejected_not_reported`, **QA** `test_a_racing_request_reports_the_record_the_winner_created[pending,approved]`. `test_store_emulator.py`: `test_a_first_access_request_creates_one_pending_record`, `test_a_repeated_access_request_keeps_the_original_record`, `test_concurrent_access_requests_leave_exactly_one_record`, `test_a_denied_account_request_is_rejected_and_changes_nothing` | `uv run pytest tests/test_access.py tests/test_store_emulator.py` | **PASS** (D1 fixed by the lead) | The stored record has exactly the six DAT-2 fields, `version` 1. Exactly one record was created in every run. After the D1 fix, the concurrency test (16 requests, 8 threads, fresh UID per run) passed 15 of 15 runs. Mutation P5 (denied may re-request) was killed. Demo scene 2. |
| AC2. The guard rejects `missing`, `pending` and `denied` on a protected route and admits `approved`; a store failure during the check is rejected | `test_the_guard_rejects_every_unapproved_state[*]` (6: `/v1/me` and `/v1/scores` × 3 states), `test_the_guard_admits_an_approved_account[*]` (2), `test_a_store_failure_during_the_check_is_rejected_not_admitted[*]` (2), `test_every_route_outside_the_allow_list_depends_on_the_approval_guard`, `test_no_setting_turns_the_gate_off`; emulator `test_the_http_guard_with_the_real_store_follows_the_access_record`, `test_a_malformed_access_record_fails_closed[*]` (5) | `uv run pytest tests/test_access.py tests/test_store_emulator.py` | PASS | Mutations killed: P1 (`/v1/scores` on `signed_in`, 11 tests fail), P2 (guard admits pending, 3), P3 (store failure treated as approved, 2), P7 (malformed record read as missing, 5). Demo scenes 1, 3 and 4 show 403 `access_not_approved` for missing, then 200 after approval, then 503 on an injected read failure. |
| AC3. A forged UID, name, email or state in the request body has no effect | `test_a_forged_uid_name_email_or_state_in_the_body_has_no_effect[*]` (6), `test_a_forged_uid_in_the_query_is_rejected[*]` (2), `test_an_unapproved_caller_cannot_read_another_accounts_state`, `test_an_empty_json_body_is_accepted`; `test_firebase.py::test_profile_takes_name_and_email_from_the_verified_token` | `uv run pytest tests/test_access.py tests/test_firebase.py` | PASS | A non-empty body gets 400 `Invalid request.` with no echo, the store is never called, and the next empty request records only the token's claims. Demo scene 2: a forged `{"uid","state":"approved","email"}` gets 400, and the record stays `pending`, version 1. |
| AC4. A revoke between two requests makes the second fail | `test_a_revoke_between_two_requests_makes_the_second_fail`, `test_approval_is_read_on_every_protected_request`, `test_approval_on_one_request_does_not_carry_to_another_account`; emulator `test_the_http_guard_with_the_real_store_follows_the_access_record` | same | PASS | Mutation P4 (a positive approval cache) was killed (3 tests). Demo scene 3, against the real store: `approved` gives 200, the owner sets `denied`, and the next `/v1/scores` is 403. A re-request is then 403 `access_denied` and the record is unchanged. |
| AC5. Rules: an unapproved owner can't read their scores, an approved owner can, another user can't read either, and no client can write the access record | `infra/rules.test.mjs`: `an unapproved owner cannot read their own scores (AC5)` (missing, pending, denied and 5 malformed shapes), `an approved owner can read and another user cannot read either (AC5)`, `no client can read the access record, its own included (AC5)`, `no client can write the access record (AC5)`, `approval does not outrank a queued deletion` | `cd infra && npm test` | PASS (9/9) | QA mutations ran in a copy against a separate emulator project (`demo-qa-mutation-072`), so the shared rules were never replaced. R1 (missing record counts as approved), R2 (owner reads own `access/`) and R3 (owner creates own `access/`) were each killed by exactly the matching AC5 test. Demo scene 6. |
| AC6. After cleanup, the access record is gone along with the scores | emulator `test_deletion_cleanup_removes_the_access_record_with_the_scores`; `test_access.py::test_the_deletion_sweep_removes_the_access_record_with_the_scores`, `test_a_revoke_keeps_the_scores` | `uv run pytest tests/test_store_emulator.py tests/test_access.py` | PASS | Another owner's record and scores are untouched. Mutation P6 (`erase_student_data` keeps `access/{uid}`) was killed. Demo scene 4: the real `process_deletions` against the emulator leaves `access/<peer>` missing and 0 scores. |
| AC7. A log-capture test shows no name or email in logs on success and error paths | `test_no_name_or_email_reaches_logs_on_success_or_error`, `test_a_profile_repr_never_shows_the_name_or_email`, `test_firebase.py::test_profile_outage_is_unavailable_and_hides_the_provider_error` | `uv run pytest tests/test_access.py -k "logs or repr"` | PASS | Independent check in the demo: stdout and Python `logging` were captured across all HTTP scenes, including an injected crash whose message holds the name and email. 0 lines contain the name, `test.invalid` or `@`. The only service line is `{"event":"unhandled_error","error_class":"RuntimeError",…}`. Demo scene 5. |

## Checks (final rerun after the lead's changes)

| Command | Result |
|---|---|
| `uv run pytest` (accounts, emulator) | Final run by the lead after the D1 and D2 fixes: 299 passed, 0 skipped. Concurrency test: 15 of 15 runs passed. |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 17 files already formatted |
| `uv run mypy .` | Success: no issues found in 16 source files |
| `cd infra && npm test` | 9 tests, 9 pass, 0 fail |
| `python -m unittest discover -s scripts/ci/tests` (repo root, the CI runner) | Ran 196 tests, OK |
| `python scripts/ci/check_synthetic_fixtures.py` | Passed: 378 tracked files, 0 allowlisted |
| Coverage (`uv run --with pytest-cov==6.0.0 pytest --cov=cst_accounts --cov-branch`, ephemeral, not added to the lock) | Total 93%. `api.py` 99%, `store.py` 96%, `domain.py` and `deletion.py` 100%, `firebase.py` 83% (the token-exchange paths, which predate #72). `store.py:109` (a race that ends non-denied) was uncovered, and the QA test now covers it. |
| Mutations (10, run in throwaway copies, never in the working tree) | 10/10 killed: P1–P7 (Python) and R1–R3 (rules). |

## Defects

- **D1 (Medium). Concurrent access requests for one account can return 503, and the AC1 concurrency test
  is flaky.** `services/accounts/cst_accounts/store.py:103`. `create_once` runs as a Firestore transaction
  with the default 5 attempts. When 8 same-account requests run 4 at a time, the transactions contend on
  `access/{uid}` and `account_deletions/{uid}`. One can exhaust its retries (`ValueError: Failed to commit
  transaction in 5 attempts`), and `storage_operation` (`store.py:41-44`) maps that to `Unavailable`
  (503). It fails closed and the single-record invariant holds, but a double tap can show an error, and
  `tests/test_store_emulator.py:169` failed in about 4 of 9 runs, which will flake CI. Likely fix: after
  contention exhaustion, re-read the record and return its state if it exists (as the `AlreadyExists`
  branch does), or raise `max_attempts`. Then re-run the test at least 10 times.
- **D2 (Low, pre-existing, test-only).** `tests/test_store_emulator.py:28`
  `test_request_is_idempotent_and_keeps_original_deadline` uses the fixed UID `delete-test-a`. On an
  emulator that a previous run already used, it finds the old marker and fails. CI uses a fresh emulator,
  so this only affects local re-runs. QA deleted the stale synthetic markers `delete-test-a` and
  `retry-test` from the emulator to get a clean run.

## Demo

`specs/072-access-approval-gate/demo/072-access-approval-gate.gif` (27.4 s, 3.3 MB, 1280 px, 10 fps) and
`072-access-approval-gate.webm`. Script: `specs/072-access-approval-gate/demo-recording.py`. It drives
the real router, the real Firestore adapter (emulator) and the real `FirebaseIdentity`, with only the
Google signature check stubbed to return synthetic claims. It then runs `npm test` and the full checks.
It refuses to record if any step fails. The take shown passed on the first attempt, with all 8 parallel
requests returning `200 pending`. The script would show a 503 if one occurred (D1). QA checked frames
from scenes 2, 3, 5, 6 and 7: the captions match their ACs, and there are only synthetic UIDs (`<me>`,
`<peer>`), `@test.invalid` values, and no tokens or local paths.

## Lead follow-up (after QA)
- **D1 fixed.** The transaction no longer reads `access/{uid}`. On the emulator, racing transactions each locked the missing document and deadlocked until every one ran out of retries. `request_access` now reads the record outside the transaction. If none exists, a transaction reads only the deletion marker and creates the record. A racer that loses gets `AlreadyExists`, or runs out of retries, and reports what the winner wrote. If nothing was written, the request returns 503. Unit tests in `test_access.py` cover every branch. The emulator concurrency test now uses a fresh UID with 16 requests on 8 threads, and passed 15 of 15 runs.
- **D2 fixed.** The test uses a fresh UID.
- **Demo re-recorded on the final code.** The lead checked frames for AC2/AC4 and AC7: synthetic IDs and `@test.invalid` only.
- **Final checks:**
  - accounts: 299 passed, 0 skipped
  - ruff: clean, 17 files formatted
  - mypy: clean
  - rules: 9/9
  - scripts/ci: 196 OK
