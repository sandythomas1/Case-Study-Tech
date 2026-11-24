# Report contract v1

Version 1.0.0 · Issue #59 · Status: **structural contract, no policy approval**

This contract fixes the shape of the feedback report and the score history, so that the
grader, the report screen, history and export can be built against it in parallel. It covers
structure only. It does not approve the rubric (`rubric/anchor-spec.v1.json` is `proposed`), the
weights, the rounding, the calibration or any clinical meaning. Nothing that follows the contract
may say otherwise.

`scripts/ci/check_report_contract.py` is the executable form. When this page and the checker
disagree, that is a bug in one of them, and CI fails until they agree.

## 1. Two documents

| Document | `contract` | What it holds | Where it may live |
|---|---|---|---|
| Report | `cst.report` | The result of one attempt: state, ratings, overall, safety result, evidence quotes, strengths, next steps, limitations | App memory while the report is open, request bodies in transit, the grading service's memory, and the PDF the student chooses to export (REP-1). **Never** Firestore, a cache, logs, analytics or crash reports (DAT-1). |
| History | `cst.history` | The signed-in student's score records, projected for the history screen | Firestore score records (#40), and the app while history is open (REP-3) |

The report is transient. Its narrative and evidence are gone when the student leaves it (REP-2),
and no field of it is persisted except through the score-record mapping in section 7. History never
carries narrative, evidence, quotes or a transcript.

The saved transcript (the DAT-1 exception) is not part of this contract.

## 2. Common fields

Every report has these fields, in every state.

| Field | Type | Rule |
|---|---|---|
| `contract` | `"cst.report"` | Fixed |
| `contract_version` | `"MAJOR.MINOR.PATCH"` | `1.x.y` for this contract (section 9) |
| `synthetic` | boolean | `true` only for fixtures and tests. It is true exactly when `provenance.grader.model` is `synthetic-fixture`. A production build refuses a synthetic report. |
| `state` | string | One of the six states in section 3 |
| `scenario` | `{id, version}` | `id` is `routine_intake`, `resistant_client` or `crisis_risk`. `version` is the scenario config's version (#27). The crisis scenario is `crisis_risk`, and nothing else is. |
| `modality` | `"voice"` or `"text"` | How the conversation ran |

## 3. States

| State | Meaning | Required beyond the common fields | Optional | Everything else |
|---|---|---|---|---|
| `pending` | Grading has not finished. The app shows progress. | None | None | Forbidden |
| `scored` | All six categories rated. A numerical result is enabled. In the crisis scenario, safety was met. | narrative, outcome, `scale`, `categories`, `overall` | `safety` (crisis only, and then required) | Forbidden |
| `safety_not_demonstrated` | Crisis scenario only. At least one critical failure. The safety result leads (SCO-5). | narrative, outcome, `scale`, `categories`, `safety` | `overall`, only when all six are rated | Forbidden |
| `insufficient_evidence` | At least one category abstained, so there is no overall (SCO-3). This is an assessment that abstained, not a failed attempt. | narrative, outcome, `scale`, `categories` | `safety` (required in the crisis scenario, and then `met`) | Forbidden |
| `narrative_only` | Numerical results are not enabled, because the configuration has not passed calibration (#47). Strengths and next steps only. | narrative, outcome | `safety` (required in the crisis scenario) | Forbidden |
| `failed` | The attempt could not be assessed. No score, no narrative, no evidence (SCO-3, REC-2 to REC-4). | outcome, `failure` | None | Forbidden |

"narrative" means `turn_count`, `provenance`, `disclaimer`, `strengths`, `next_steps` and
`limitations`. "outcome" means `score_record_saved` and `actions`.

An unknown field is forbidden in every state. A field that a state forbids is never sent with a
placeholder such as `null`, `0` or `""`: it is left out.

**A crisis report always carries its safety result** (owner, 2026-11-23; SCO-5, ETH-7). In the
`crisis_risk` scenario, `safety` is required in `scored`, `safety_not_demonstrated`,
`insufficient_evidence` and `narrative_only`, so a critical failure is never dropped because a
category abstained or numerical results are not enabled. The grader always runs the crisis override
(#37). Only `pending` and `failed` carry no safety result.

### Invariants per state

- **scored**: every category is `rated`. `overall.role` is `primary`. If the scenario is
  `crisis_risk`, `safety.result` is `met`. `score_record_saved` is `true`.
- **safety_not_demonstrated**: the scenario is `crisis_risk`. `safety.result` is
  `not_demonstrated` with at least one critical failure. `scenario_specific_competence` is rated
  level 1, however many turns it cites (anchor spec, crisis rule). `overall` is present exactly when
  every category is rated, and then `overall.role` is `secondary`. `score_record_saved` is `true`
  exactly when `overall` is present (decision D-3).
- **insufficient_evidence**: at least one category is `abstained`. There is no `overall`. A
  critical failure is never reported here: it is `safety_not_demonstrated`, even when categories
  abstain. `score_record_saved` is `false`.
- **narrative_only**: there is no `scale`, `categories` or `overall`. `score_record_saved` is
  `false`.
- **failed**: see section 6. `score_record_saved` is `false`.
- **pending**: nothing beyond the common fields.

A rated category in `insufficient_evidence`, or in `safety_not_demonstrated` without an average,
still carries its level. Whether the report shows those levels is decision D-2. Until it is
decided, #38 shows no category level in those two cases.

## 4. Field reference

| Field | Shape | Rule |
|---|---|---|
| `turn_count` | integer, 1 to 500 | The number of turns in the graded transcript. Every cited turn is within 1 to `turn_count`. |
| `provenance.rubric` | `{spec_id, spec_version, approval_status}` | Copied from the anchor spec. `approval_status` is the spec's own value, so a report can never claim an approval the spec doesn't have. |
| `provenance.scoring_policy_version` | `"MAJOR.MINOR.PATCH"` | The version of the grader's scoring policy (#35): evidence rules, the abstention logic and the overall rule. |
| `provenance.grader` | `{model, prompt_version}` | The model and prompt that produced the report. Fixtures use the model `synthetic-fixture`. |
| `disclaimer` | string | The anchor spec's `student_disclaimer`, word for word (SCO-8) |
| `scale` | `{min, max, levels[{level, label}]}` | The anchor spec's 1 to 5 levels and labels, in order |
| `categories` | list of 6 | The six RC-17 categories in anchor-spec order. Each has `id`, `name` and `weight_percent` from the anchor spec, and an `outcome`. |
| category, `rated` | `+ level, label, evidence` | `level` is a whole number 1 to 5, `label` is that level's anchor-spec label, and `evidence` cites at least 2 distinct student turns |
| category, `abstained` | `+ reason` | `reason` is one of the anchor spec's abstention reasons: `no_opportunity`, `too_few_cited_turns`, `uncertain_recognition` or `unresolved_conflict`. It has no level, label, evidence, zero or midpoint. |
| `overall` | `{value, display, role}` | Section 5 |
| `safety` | `{result, critical_failures[]}` | Crisis only. `result` is `met` (no critical failures) or `not_demonstrated` (at least one). Each failure is `{id, evidence}`, with a distinct id from `CF-IGNORE`, `CF-ENCOURAGE`, `CF-SECRECY` and `CF-NO-PRIORITY`. Its evidence includes the client's disclosure turn. |
| `strengths`, `next_steps` | list of 1 to 5 `{text, evidence}` | `text` is the grader's original wording, up to 500 characters (SCO-7). A strength cites at least one turn. A next step may cite none. |
| `limitations` | list of codes | Section 8 |
| `score_record_saved` | boolean | Whether the server kept a score record for this attempt. The report says so, and REC-4 requires it for every unscored outcome. |
| `actions` | list of codes | Section 6 |
| `failure` | `{reason, conversation_available}` | Section 6 |

**Evidence** is a list of `{turn, speaker, quote}`. `turn` is the 1-based index of a turn in the
graded transcript. `speaker` is `student` or `client`. `quote` is one line of up to 300 characters
from that turn. A report that cites a turn outside the transcript is invalid, and the grader
returns `failed` with `evidence_check` instead (SCO-4). A rating cites student turns only.

## 5. Overall score

- `overall.value` is the SCO-2 weighted mean, computed in code from the six levels and the anchor
  spec's fixed weights: sum(weight_percent × level) / 100. It is exact, for example `3.55`. A
  consumer never recomputes it, and never computes it from the report's own weights.
- `overall.display` is `value` rounded to one decimal, for example `"3.6"`. It is never a percent
  (SCO-9). The rounding method is **half-up**, provisionally (decision D-1). The fixtures include
  3.55 and 2.05, where half-up and half-even differ.
- `overall.role` is `primary`, except in `safety_not_demonstrated`, where it is `secondary` and the
  safety result leads (SCO-5).
- There is no overall unless all six categories are rated. Never a partial, reweighted, estimated
  or midpoint value (SCO-3).

## 6. Failures and actions

| `failure.reason` | Raised by | `conversation_available` | Actions |
|---|---|---|---|
| `lost_content` | App or session service: part of the conversation was lost (REC-2) | always `false` | `new_text_session`, `new_practice` |
| `speech` | Session flow: the voice path failed and the session could not continue in text (RC-08) | either | `new_text_session`, `new_practice` |
| `conduct` | Session service: conduct ended the session (SAF-1, SAF-2) | either | `new_practice` |
| `persona` | Session service: the persona failed and the conversation could not finish (SCO-1) | either | `new_practice` |
| `grading` | Grading service (#35): the grader failed (REC-3) | either | `retry_grading` when available, and `new_practice` |
| `timeout` | Grading service or app: grading took too long | either | `retry_grading` when available, and `new_practice` |
| `connectivity` | App: the grading service could not be reached | either | `retry_grading` when available, and `new_practice` |
| `evidence_check` | Grading service (#35): cited evidence did not trace to the transcript (SCO-4) | either | `retry_grading` when available, and `new_practice` |

- `conversation_available` says whether the conversation is still in app memory, which is what
  REC-4 tells the student. "Available" means in memory for this attempt only. It never means stored.
- `retry_grading` re-sends the same in-memory conversation. It is offered only for the last four
  reasons, and only while `conversation_available` is `true` (REC-3).
- Every report state except `pending` and `failed` offers exactly `export`,
  `leave_with_confirmation` and `new_practice` (REP-1, REP-2). Export renders the report in its
  current state, with its limitations, and adds no data the report doesn't carry.
- The report screen and the export also show fixed text that this contract doesn't carry: the
  ETH-1 statement of what the product is not, and, on every crisis report, the ETH-2 crisis
  resources, including the 988 Suicide & Crisis Lifeline. #38 and #42 own it.
- `pending` has no actions.

Action and limitation codes are identifiers. #38, #41 and #42 own the words a student sees.

## 7. History projection

A score record (POLICY §2, DAT-2) is written only when `score_record_saved` is `true`: a `scored`
report, or a `safety_not_demonstrated` report with an average. #40 owns the write, and the mapping
is:

| History entry field | From the report | Note |
|---|---|---|
| `record_id` | None: the server assigns it | The record's document id. Lowercase letters, digits and hyphens, up to 64 characters. |
| `scenario_id` | `scenario.id` | |
| `completed_at` | None: the server sets it | A real UTC time, for example `2026-11-20T15:04:05Z`. Used for ordering only and never displayed (REP-5). |
| `overall` | `{value, display}` | The same rule as section 5 |
| `categories` | `[{id, level}]` × 6 | Levels only: no name, label, evidence or abstention |
| `safety_result` | `safety.result` | Crisis entries only, and always present on them (REP-4). A `not_demonstrated` entry has the scenario-specific level 1. |
| `provenance` | `{rubric_spec_version, scoring_policy_version}` or `null` | **Proposed, not adopted** (decision D-5). #40 decides whether to persist it. A record without it has `null`, and its comparisons are `unknown`. |

The history document is `{contract: "cst.history", contract_version, synthetic, entries[]}`.
Entries are newest first by `completed_at`, with distinct `record_id` values and no ties (REP-5).
The fixture `history.json` gives most entries a provenance only to illustrate the D-5 proposal.
#41 builds the `null` path first.

Never in history: strengths, next steps, evidence, quotes, limitations, disclaimer, grader model or
prompt, the transcript, or any text the student or the persona wrote (REP-3, DAT-1).

### Comparison

History may tell the student whether two results can be compared. It is decided from these fields
only, in this order:

1. Different `scenario_id`: `incompatible` (decision D-6).
2. Either entry's `provenance` is `null`: `unknown`.
3. Different major version of `rubric_spec_version` or `scoring_policy_version`: `incompatible`.
4. Otherwise: `compatible`. A minor or patch difference stays compatible, because a minor rubric
   change never changes a rating (`rubric/README.md`, "Changing it").

## 8. Limitations

`limitations` lists exactly the codes that apply, without repeats.

| Code | Present when |
|---|---|
| `numerical_results_not_enabled` | The state is `narrative_only` |
| `categories_not_rated` | Any category abstained |
| `no_overall_score` | The report has no `overall` |
| `average_is_secondary` | `safety_not_demonstrated` with an average |
| `rubric_not_approved` | `provenance.rubric.approval_status` is not `approved`. True of every v1 report today. |
| `synthetic_example` | `synthetic` is `true` |

## 9. Producers, consumers and versions

| Who | Role |
|---|---|
| Grading service (#35, with the crisis override #37) | Produces every report state except `pending`, plus `failed` for `grading` and `evidence_check`. Validates its own output against this contract before returning it. |
| Session service and app | Produce `failed` for `lost_content`, `speech`, `conduct`, `persona`, `timeout` and `connectivity`. The app shows `pending` while it waits. |
| Report screen (#38) | Shows each state. Leads with the safety result when there is one. Shows no number that the report doesn't carry. |
| Score records (#40) | Writes the section 7 projection only. Raises D-3 and D-5 for the owner's decision. |
| History (#41) | Reads `cst.history`. Shows the safety result before the numbers (REP-4). Never shows the date. |
| Export (#42) | Renders the displayed report as it is, including its limitations |
| Verification (#60) | Uses the fixtures to check each screen state |

Versioning follows semver:

- A **patch** fixes wording on this page. A **minor** adds an optional field or a new limitation or
  action code that a reader may ignore. A **major** adds or removes a state, makes a field required,
  or changes a field's meaning or a rule in sections 3 to 7.
- A reader accepts any `1.x.y` and ignores the optional fields it doesn't know from a newer minor.
  It refuses a different major, an unknown `state` or an unknown `contract`, and shows the failure
  path. It never guesses a score, a state or a safety result.
- Fixtures are stricter than readers. They have no unknown fields, so a fixture always shows the
  exact v1 shape.
- A new major version gets a new file (`report-contract.v2.md`) and a new fixture folder
  (`fixtures/v2/`). v1 stays as it was.

## 10. Fixtures and validation cases

- `fixtures/v1/`: one synthetic, valid document for every state, plus `history.json`. Each one says
  `synthetic: true`. Each report that carries a narrative also names the `synthetic-fixture` grader
  and lists the `synthetic_example` limitation (`pending` and `failed` carry neither field). They are development and test inputs. They are never shown as a real student's
  assessment, and a production build refuses them.
- `validation-cases/v1/invalid/`: each case is a small JSON Patch (RFC 6902) applied to a valid
  fixture, plus the reason the checker must give for rejecting it. The cases include a fabricated
  turn, a version mismatch, a zero or midpoint for an abstention, an average that leads a safety
  failure, and narrative in history.
- `validation-cases/v1/comparisons.json`: pairs of history entries with the expected comparison.

Every conversation line in the fixtures is synthetic and written for them. None comes from a real
or recorded session (DAT-1, DAT-6).

## 11. Open decisions

None of these blocks building against v1. Each has an owner, and a change it causes is a new
version of this contract.

| ID | Decision | Owner | v1 assumes |
|---|---|---|---|
| D-1 | The rounding method for `overall.display` | #35 | Half-up |
| D-2 | Whether the report shows the rated categories' levels when there is no overall (SCO-3) | #35, with #38 | Carried, not shown |
| D-3 | Whether a crisis safety failure without an average writes a score record (REP-4) | Owner, raised by #40 | No record |
| D-4 | How #38 presents a safety result in `narrative_only`, before calibration passes. The result itself is always carried (owner, 2026-11-23). | #35 and #37, with #38 | Carried. Presentation is open. |
| D-5 | Whether score records may keep `rubric_spec_version` and `scoring_policy_version` for comparison. This amends DAT-2 and the ARCHITECTURE §7 score-record row. | Owner, raised by #40 | `null` |
| D-6 | Whether results from different scenarios are always incompatible | #41 | Incompatible |
