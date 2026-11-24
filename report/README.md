# Report contract

The versioned shape of the feedback report and the score history (Issue #59). The grader (#35)
produces it, and the report screen (#38), history (#41), export (#42) and verification (#60) build
against it with synthetic fixtures, without a live grader.

| Path | What it is |
|---|---|
| `report-contract.v1.md` | The contract: states, fields, invariants, the history projection, versioning and open decisions |
| `fixtures/v1/` | One synthetic, valid report per state, and a synthetic history |
| `validation-cases/v1/invalid/` | Changes to a valid fixture that the checker must reject, each with its reason |
| `validation-cases/v1/comparisons.json` | History pairs with their expected comparison |

The contract is structural. It approves no rubric, weight, rounding, calibration or clinical
meaning. Every fixture is marked synthetic and is never shown as a real student's assessment.

## Checking it

```
python scripts/ci/check_report_contract.py
python -m unittest discover -s scripts/ci/tests -v
```

CI's fixtures job runs the tests, and they run the checker over this folder. The checker reads
labels, weights, abstention reasons, critical failures and the disclaimer from
`rubric/anchor-spec.v1.json`, so a fixture can't drift from the rubric.

## Changing it

1. Change the contract page and the checker together.
2. Update or add fixtures and invalid cases, then run both commands above.
3. Bump the version as section 9 of the contract says. A new major version gets new files
   (`report-contract.v2.md`, `fixtures/v2/`).
4. If `scripts/ci/check_synthetic_fixtures.py` flags a new synthetic file, list it in
   `.github/synthetic-fixtures.allow` with its justification. That list is owner-reviewed. Never
   rename a file only to get past the check.
