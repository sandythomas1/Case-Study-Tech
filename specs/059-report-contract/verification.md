# Verification: report contract v1 (#59)

QA run 2026-11-23 on `feature/59-report-contract` (HEAD `becffd3` plus the untracked #59 files),
Windows, Python 3.12. Verdict: **PASS with findings**. All 5 criteria are proven. One Medium gap in
the crisis safety invariant (F1) and three Low hardening items (F2–F4) are reported. None was fixed
here, because the checker is the deliverable.

## Acceptance criteria

| AC | Proven by | Command | Result | Evidence |
|---|---|---|---|---|
| AC1 · Numerical, unscored, insufficient-evidence, pending, failure and primary crisis outcomes, with explicit field invariants | Contract §3 states table and invariants (`report/report-contract.v1.md:40-76`), matched by `FIELD_RULES` and `state_rules` (`scripts/ci/check_report_contract.py:108-127`, `:437-469`). One fixture per state (12 fixtures). Tests `test_there_is_a_fixture_for_every_state`, `test_safety_not_demonstrated_is_crisis_only`, `test_a_secondary_average_is_saved_but_none_without_an_average`, `test_a_safety_failure_without_an_average_must_not_carry_one`, `test_a_rated_category_in_insufficient_evidence_still_needs_an_abstention`. Invalid cases `crisis-failure-scored`, `crisis-average-primary`, `crisis-rating-not-capped`, `safety-outside-crisis`, `unknown-state`, `unknown-field`, `pending-with-score` | `py -3.12 scripts/ci/check_report_contract.py` and the unittest run | PASS | Checker exit 0: "fixtures valid, invalid cases rejected, comparisons as expected". See F1 for one crisis invariant gap. |
| AC2 · #38, #41 and #42 can develop and test against synthetic fixtures without a live grader or an approved scale | `report/fixtures/v1/` has every state plus `history.json`, all with grader `synthetic-fixture`. Contract §9 consumers (`report-contract.v1.md:187-197`) and §10 (`:212-225`). Tests `test_every_fixture_is_marked_synthetic_with_the_synthetic_grader`, `test_the_main_entry_point_passes_on_the_real_folder`. Comparison pairs in `validation-cases/v1/comparisons.json` (`test_comparison_indication`). | same | PASS | No fixture depends on a model call. The rubric is read as `proposed`, and every fixture lists `rubric_not_approved`. |
| AC3 · Unavailable or ineligible reports carry no publishable invented score, and synthetic numbers are clearly identified | `test_unavailable_states_carry_no_number` (8 fixtures, no `overall`, no level on abstentions, `score_record_saved` false). Invalid cases `zero-for-abstention`, `midpoint-overall-with-abstention`, `reweighted-overall`, `score-on-failure`, `insufficient-evidence-saved`, `narrative-only-with-level`, `unmarked-synthetic`, `percent-display`. Contract §2 `synthetic` rule (`:35`), §5 (`:104-115`), §8 `synthetic_example` (`:185`). | same | PASS | Each case is rejected with its stated reason (checker step 2). |
| AC4 · Transient narrative is separate from the history projection, and storage decisions are owned by #40 | Contract §1 (`:14-25`), §7 mapping and the "Never in history" list (`:141-161`), D-3 and D-5 owned by #40 (`:237-238`). Checker `entry` allow-list (`check_report_contract.py:566-596`). Tests `test_a_history_entry_never_carries_an_abstention_or_evidence`, `test_provenance_is_null_or_exactly_the_proposed_pair`. Invalid case `history-narrative`. Mutations M5a–M5d. | same, plus the mutation harness | PASS | Quotes or narrative put in a history entry's categories, overall or provenance, or at the top level, are all rejected. |
| AC5 · Producer and consumer roles, versioning and incompatibility behavior are documented, with no claim of clinical or grading approval | Contract §9 (`:187-210`), the status line and preamble (`:3-9`), §11 open decisions (`:227-240`). Tests `test_a_newer_minor_version_is_read`, `test_a_malformed_version_is_reported`, `test_limitations_follow_the_rubric_approval`. Invalid cases `version-major-mismatch`, `history-version-mismatch`, `claims-approval`, `changed-disclaimer`. Mutations M6a and M6b. | same | PASS | An approval claim is rejected, even when the `rubric_not_approved` limitation is also dropped to match it. |

## Checks

| Command | Result |
|---|---|
| `py -3.12 -m unittest discover -s scripts/ci/tests -v` | 191 run, 191 OK (41 of them in `test_check_report_contract.py`) |
| `py -3.12 scripts/ci/check_report_contract.py` | exit 0: 12 fixtures valid, 33 invalid cases rejected, comparisons as expected |
| `py -3.12 scripts/ci/check_anchor_spec.py` | exit 0 |
| `uvx ruff@latest check scripts/ci/check_report_contract.py scripts/ci/tests/test_check_report_contract.py` | All checks passed |
| `uvx mypy --strict --python-version 3.12 scripts/ci/check_report_contract.py` | Success: no issues found in 1 source file |
| `py -3.12 scripts/ci/check_synthetic_fixtures.py` | exit 0. It scans tracked files only, so the untracked #59 files were checked separately with its `classify()`: 0 of 53 flagged. |
| CI wiring | `.github/workflows/ci.yml:165-166` (the `fixtures` job) runs the unittest discover, and `test_the_main_entry_point_passes_on_the_real_folder` runs the checker over `report/`. This meets R9. |
| Contract and checker agreement | The states table, field rules (§4), limitations (§8), actions and failure reasons (§6), history fields (§7) and comparison order (§7: scenario, then null provenance, then major) all match the code, `check_report_contract.py:108-127, 397-542, 566-628, 651-660`. The one gap is F1, where the contract and checker agree with each other but both miss an anchor-spec rule. |

## Mutation testing

The harness is `<scratchpad>/mutate059.py`, not in the repo. For each mutation it copies `report/` to a
scratch folder, adds the mutated document as an extra fixture, and runs the real CLI with
`--report-dir`. Exit 0 means the mutation wrongly passed.

| # | Mutation | Result |
|---|---|---|
| M1a | Crisis `scored` with `safety` deleted | Rejected: "a crisis report needs safety met" |
| M1b | Crisis `scored` with `safety.result` `not_demonstrated` and a CF | Rejected: same reason |
| M2a | Crisis critical failure relabelled `insufficient_evidence`, keeping `safety` | Rejected: "a critical failure is safety_not_demonstrated" |
| M2b | Same, with `safety` removed (scenario category still rated level 1, 2 cited turns) | **Wrongly passed (F1)** |
| M2c | Same as M2b with the scenario category raised to level 3 | **Wrongly passed (F1)** |
| M2d | Crisis failure turned into `narrative_only` with no `safety` | Passed. By design: D-4 leaves safety optional there, and there are no categories to contradict. |
| M3a | `overall` added to `safety_not_demonstrated` with abstained categories, saved and limitations adjusted | Rejected: "overall is present exactly when every category is rated" |
| M3b | `overall` added to `insufficient_evidence` | Rejected: forbidden field `overall` |
| M4a–c | A turn beyond `turn_count` in `next_steps` and in a critical failure, and a turn given as `2.0` or `"2"` | Rejected: "a fabricated turn" |
| M4d | `turn_count: true` | Rejected |
| M5a–d | Evidence on a history category, a quote on a history `overall`, a grader prompt in history provenance, `next_steps` at the history top level | All rejected |
| M6a | `approval_status: "approved"`, with `rubric_not_approved` also dropped | Rejected: "never claim approval" |
| M6b | `rubric_not_approved` dropped alone | Rejected: limitations mismatch |
| M7 | The same turn cited twice in a rated category's evidence | **Wrongly passed (F2)** |
| M8a | `weight_percent: 20.0` | Passed (F4, informational) |
| M8b | A quote containing U+2028 LINE SEPARATOR | **Wrongly passed (F3)** |
| M8c | History `completed_at: "2026-11-99T99:99:99Z"` | **Wrongly passed (F4)** |

## Findings

- **F1 (Medium).** A crisis `insufficient_evidence` report may omit `safety` while still rating
  `scenario_specific_competence`, so a critical failure can be dropped with no structural tell. The anchor spec's
  `crisis_critical_failures.safety_result_rule` says: when no safety result is given, "the
  scenario-specific category abstains". The contract (`report-contract.v1.md:47`, `safety` listed as
  optional) and the checker (`check_report_contract.py:462-466`) don't encode that rule.
  Repro: take `safety-not-demonstrated-no-average.json`, set `state` to `insufficient_evidence`,
  delete `safety`, and add a second student turn to the scenario category's evidence. The checker
  exits 0. Suggested rule: in `crisis_risk`, a report with `categories` either carries `safety`, or
  its `scenario_specific_competence` is `abstained`. Add it to contract §3 and `state_rules`, with
  an invalid case. No regression test was added, because it would fail until the checker changes.
- **F2 (Low).** Duplicate evidence refs count toward the "at least 2 cited student turns" minimum
  (`check_report_contract.py:243`, `len(refs)`). The anchor spec's `category_rating_rule` asks for 2
  cited student turns. Repro: in `scored-standard.json`, set `categories[0].evidence[1]` to a copy of
  `evidence[0]`. The checker exits 0. Count distinct `turn` values instead.
- **F3 (Low).** `_single_line` (`check_report_contract.py:188-189`) checks only `\n` and `\r`. U+2028,
  U+2029, U+0085 and other control characters pass as one line. Repro: set a strength quote to
  `"Hi there second line"`.
- **F4 (Low, informational).** `completed_at` is checked by a regex only, so an impossible date
  passes (`check_report_contract.py:88, 593`). It is server-set and used only for ordering.
  `weight_percent: 20.0` passes because `20.0 == 20`, which is harmless in JSON.

## Notes

- `.gitignore` does not list `specs/*/demo/`, as also noted for #63. Don't commit the GIF or WebM.
  The `.webm` would also fail `check_synthetic_fixtures.py` once it is tracked. Publish both to
  `pr-media` only.
- The 33 invalid cases and 12 fixtures each contain only short synthetic lines. The spec's
  interpretation of ARCHITECTURE §7 and DAT-1 is flagged for policy-reviewer, and QA does not settle it.

## Demo

- `specs/059-report-contract/demo/059-report-contract.gif`: 14.5 s, 1280 px, 10 fps, 3.5 MB (3,505,072 bytes)
- `specs/059-report-contract/demo/059-report-contract.webm`: full quality, 0.87 MB (874,459 bytes)
- Recorder: `specs/059-report-contract/demo-recording.py`, Python Playwright 1.58.0, following the
  #63 and #4 precedent, so the repo gains no `@playwright/test`. Each scene runs the real command,
  asserts its exit code, and replays only the result lines:
  1. AC1–AC3: the checker passes over every fixture and 33 invalid cases (exit 0).
  2. SCO-4: the `fabricated-turn` case is applied to a scratch copy and rejected with "turn 40 is
     outside the transcript (1 to 12): a fabricated turn" (exit 1).
  3. Tests: 41 report-contract tests, "Ran 41 tests: OK".
- QA opened frames 2, 4 and 7. Each caption matches its scene, the outcome is on screen, and no local
  paths or real data appear. Three lint-only edits made after recording (a removed `noqa`, an explicit
  `check=False` and a merged `startswith`) don't change the output.

## Re-verification after the lead's fixes (2026-11-23)

The owner decided, 2026-11-23: "Always require it (Recommended)". A crisis report carries its safety
result in every assessed state. This closes F1. The lead also fixed F2–F4.

| Finding | Fix | Evidence |
|---|---|---|
| F1 (Medium) | In `crisis_risk`, `safety` is required in `scored`, `safety_not_demonstrated`, `insufficient_evidence` and `narrative_only` (`CRISIS_SAFETY_STATES`), contract §3 | `CrisisSafetyTest` (3 tests). Invalid cases `crisis-narrative-only-without-safety` and `crisis-abstention-drops-safety`. Mutations `crisis_failure_hidden_*` and `crisis_failure_level_raised_insufficient` are now rejected. |
| F2 (Low) | The evidence minimum counts distinct turns | Invalid case `repeated-cited-turn` |
| F3 (Low) | Quotes are one line under `str.splitlines`, so U+2028, U+2029 and U+0085 are rejected | `test_a_unicode_line_break_in_a_quote_is_rejected`, mutation `quote_line_separator` |
| F4 (Low) | `completed_at` must parse as a real time. `weight_percent` must be an integer. | Invalid case `impossible-completion-time`, `test_a_fractional_weight_is_rejected`, mutations `completed_at_impossible` and `weight_float` |

Re-run results:
- unittest discover: 196 run, all OK.
- Checker: exit 0, with 12 fixtures and 37 invalid cases.
- ruff and mypy --strict: clean.
- The QA mutation harness: all 22 mutations are rejected.
