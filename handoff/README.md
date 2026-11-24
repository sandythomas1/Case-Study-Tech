# Completed-session handoff contract

The versioned payload that the session service hands the grader when a session ends (Issue #66,
ARCHITECTURE AD-3 and flow 4). The grader (#35, #68) builds against these files and doesn't need
a running session service.

| Path | What it is |
|---|---|
| `completed-session.v1.schema.json` | The JSON Schema, generated from `services/session/cst_session/handoff/contract.py` |
| `fixtures/v1/accepted/` | One synthetic completed session per scenario: routine intake (text), resistant client (voice, with a fallback turn, an uncertain turn, one conduct warning, ended by the time limit and marked "don't save") and crisis risk (voice, opted in) |
| `fixtures/v1/rejected/` | One synthetic payload per rejection reason, named `<reason>.json` or `<reason>--<case>.json` |

Every fixture line is invented for testing. None comes from a real session, a real student or a
real client (AG-2, POLICY DAT-6).

## The contract

- **Only `completed` is graded** (RC-09, POLICY SCO-1). The validator returns one reason for
  anything else, checking in this order so the most specific reason wins:
  1. `malformed`: the input isn't a JSON object naming `cst.completed_session`.
  2. `version_mismatch`: `contract_version` is missing or unknown.
  3. `incomplete`, `content_lost` or `ended_for_conduct`: the session's own status.
  4. `malformed`: any other break in the schema, or a consistency rule below.
- **Turns** are numbered 1 to n with no gaps. `at_ms` is milliseconds from the session start and
  never goes backwards, and no turn starts after `duration_ms`. A session has 1 to 500 turns.
- **Text** is 1 to 2,000 characters with at least one visible character. It has no control
  characters except tab and newline, no bidi embedding, override or isolate controls, and no
  byte-order mark. Zero-width joiners, direction marks and similar invisible characters are
  allowed beside visible text, because Persian, Indic scripts and emoji need them, but they don't
  count as the visible character.
- **Time limit.** The session service enforces the scenario's configured limit (10 minutes, POLICY
  SES-5) before it hands a session over. `duration_ms` has a ceiling of one hour as a sanity
  bound, not as the time-limit check.
- **Per-turn reliability.** Each student turn says how it was given (`input`: `text` or `speech`)
  and whether speech recognition marked it uncertain (`uncertain_recognition`). The grader never
  treats an uncertain turn as the only evidence for a level 1 behavior, a harm cap or a crisis
  critical failure (`rubric/anchor-spec.v1.json`, `uncertain_recognition_rule`). A typed turn is
  never uncertain. A text session has no speech turns: this is a contract rule, not a policy
  quote. It follows from POLICY SES-6 (text never needs the microphone) and REC-1 (only a voice
  session falls back to text).
- **Conduct.** `conduct.warnings` is 0 or 1 and matches the turns with `conduct_warning`. A
  second incident ends the session, so it arrives as `ended_for_conduct` (POLICY SAF-1, SAF-2).
- **Crisis.** `crisis` is `{"opted_in": true}` in the `crisis_risk` scenario and `null` in the
  others (POLICY SES-2).
- **Owner.** `owner_uid` is the UID the session service already verified, taken from the verified
  token or the server-signed state and never from the client. The grader stores the score under
  it. It is never logged (owner decision, 2026-11-23).
- **Save choice.** `save_transcript` is the student's per-session choice, which defaults to saving
  in the app. When it is `false` the grader grades the session but never stores the transcript
  (POLICY DAT-1, `docs/decisions/transcript-storage.md` D4; owner decision, 2026-11-23). It has
  no default in the contract, so a payload without it is `malformed` and the grader fails closed.
  `true` is a necessary condition, not an instruction: storage itself starts only once
  `docs/decisions/transcript-storage.md` takes effect.
- **No credential in the payload** (AG-7). Only the session service's account may invoke the
  grader, and the grader checks that identity at its edge (#68).
- **Unknown fields are refused** at every level, and every field is required. `crisis` is
  required too, as `null` where it doesn't apply.

**Encoding.** The body is UTF-8 JSON with no byte-order mark, at most 5 MiB. The producer sends
exactly what `encode_handoff` returns: raw UTF-8 with no `\u` escapes, so the largest valid session
(500 turns of 2,000 four-byte characters) fits. Identifier and text patterns are full-match
ECMA-262 patterns, and the text pattern holds astral characters, so it needs the `u` flag. A
consumer that validates with the schema alone must compile them that way. With
Python's `re.search`, `$` also matches before a trailing newline. The cross-field rules (turn
order, conduct count, crisis flags, text sessions) live only in `validate_handoff`, so a consumer
uses this package, not the schema alone.

The payload holds the whole conversation, so it lives only in memory. Neither service writes it
to storage, a cache or a log. The validator logs only `handoff_accepted` or
`handoff_rejected_<reason>`, with the session ID (ARCHITECTURE §7, POLICY DAT-7).

## For the grader (#35, #68)

The contract can't enforce these, so the grader's edge must:

- Accept calls only from the session service's account: Cloud Run invoker IAM, internal ingress,
  and a check of the token's audience and service-account email. That's the only reason to trust
  `owner_uid` (AG-7).
- Cap the request body at `MAX_BODY_BYTES` before reading it into memory, and require
  `Content-Type: application/json`.
- Catch `HandoffRejected` in the handler and answer with a fixed 4xx that carries only the reason.
  Its traceback references frames that hold the payload, so it never reaches an error reporter
  that captures locals (POLICY DAT-5).
- Use only the session `parse_handoff` returns. Never build one with `model_copy`,
  `model_construct` or a second `model_validate`, because `model_copy` and `model_construct` skip
  validation.
- Write the score record create-only, keyed on `session_id`, so a retried handoff can't re-grade
  or overwrite it.
- Resolve `scenario.version` against the vetted configuration registry and reject unknown versions.
  The contract accepts any version that has the right shape.
- Treat turn text as untrusted input to the grading model. Delimit it as data, strip Unicode tag
  characters (U+E0000–U+E007F) and other invisible format characters before building the prompt,
  because the contract allows them beside visible text, and check that cited evidence points to
  real turns.

## Changing it

1. Change `contract.py`, then run `uv run python -m cst_session.handoff.export` in
   `services/session`. `tests/test_handoff_schema.py` fails while the committed schema differs.
2. The grader accepts only the exact versions it knows and rejects any other as
   `version_mismatch`. So every version change, minor and patch included, ships grader support
   first, and the owner deploys the grader before the session service (AG-9). A breaking change is
   also a new major version with its own schema file and fixture folder.
3. Add or update a fixture for each new rule. `tests/test_handoff_contract.py` runs every fixture
   and requires one per scenario and one per rejection reason.
