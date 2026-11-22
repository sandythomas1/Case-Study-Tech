# Rubric anchor spec

The versioned behavior anchors the grader scores against. It covers the six RC-17 categories, the
three scenario variants of scenario-specific competence, and the RC-19 crisis critical failures
(Issue #21, OQ-03).

| File | What it is |
|---|---|
| `anchor-spec.v1.json` | The source of truth. The grader (#35) and the calibration set (#47) read it. |
| `anchor-spec.v1.md` | A readable copy generated from the JSON. Never edit it by hand. |

## Who reads it

- **Grader (#35):** scores each category against the behavior anchors. Uses the criteria's
  opportunity and minimum-evidence rules to decide when to abstain, and never computes the overall
  score itself.
- **Calibration set (#47):** labels synthetic sessions with these levels, criteria and critical
  failure IDs, so grader agreement can be measured (PA-10).
- **Safeguard tests (#37):** test each crisis critical failure ID (`CF-IGNORE`, `CF-ENCOURAGE`,
  `CF-SECRECY`, `CF-NO-PRIORITY`).
- **Students:** see only the scale labels, each level's `student_description` and the disclaimer.
  The `behavior_anchor` text is for the grader.

## Rules the spec keeps

- Free instruments only (PA-4). CCS-R and the MITI manual are listed as excluded, and nothing may
  cite them. No item text from any instrument is reproduced (SCO-7). Each citation says whether
  the criterion uses the source's concept **directly**, **adapts** it into original words, or is
  **original** to this project.
- No score is ever called an MITI, ENACT or CTRS-R score, and no student text shows a percent
  (SCO-6, SCO-9, AG-5).
- The grader assesses only what a transcript shows. It never infers tone, body language or the
  client's outcome, and it never rewards keyword counts.
- A category with too little evidence abstains. It never becomes a midpoint, a zero or a
  reweighting, and any abstention means no overall score (SCO-3).
- Every example in the spec is synthetic and written for it. None comes from a real or recorded
  session (DAT-1, DAT-6).

## Changing it

1. Edit `anchor-spec.v1.json`.
2. Regenerate the readable copy: `python scripts/ci/check_anchor_spec.py --write-markdown`.
3. Check it: `python scripts/ci/check_anchor_spec.py` and
   `python -m unittest discover -s scripts/ci/tests -v`. CI's fixtures job runs those tests.
4. Bump `spec_version`. Use a patch for wording, a minor for an added criterion or example, and a
   major for anything that changes a rating, such as a level anchor, an evidence rule or a
   critical failure. A major change means the calibration set (#47) must be re-run.
5. The owner approves each version in review. On approval, set `approval.status` to `approved`
   with the approver and date. A change to an approved version is a new version, and a new major
   version gets a new file (`anchor-spec.v2.json`), so it stays clear which version a score
   came from.

The category weights, the scenario list and the four critical failures are fixed by RC-17, SCO-2
and RC-19. The validator fails if they change, because changing them is a policy decision for the
owner, not a rubric edit.
