# Persona prompts

These are the vetted persona prompts for the three practice scenarios (#67). Each one is the system
instruction for the simulated client in its own scenario. Every client and every detail in them is
fictional and synthetic: no real client, name or case appears (PA-3).

- One file per scenario, named after its id in `../configs/`: `routine_intake.txt`,
  `resistant_client.txt` and `crisis_risk.txt`.
- `cst_session/scenarios/prompts.py` loads them once at startup. It accepts exactly these three
  files, UTF-8 with no byte-order mark, not blank, at most 3,000 characters, and no control or
  format characters except tab and newline. Anything else stops the service.
- `manifest.toml` records each prompt's `version` (`MAJOR.MINOR.PATCH`) and `sha256`: lowercase hex
  over the UTF-8 bytes of the text after CRLF becomes LF and surrounding whitespace is stripped. The
  loader refuses a manifest that isn't exactly the three ids with those two keys, and a prompt whose
  text doesn't match its digest.
- A prompt goes to the model only as the system instruction for its own scenario, the same text on
  every turn. It is never shown to the student and never stored in the session state.
- Nothing writes these files, and no API or screen can create or edit a prompt (AG-6).

## Changing a prompt

1. Edit the `.txt` file. Use LF line endings and straight quotes.
2. Bump its `version` in `manifest.toml`: MAJOR for a change to how the client behaves, MINOR for a
   new detail the client can share, PATCH for wording that changes nothing the client does.
3. Update its `sha256` in `manifest.toml` to the digest of the new text, as described above.
4. Run the live persona checks for that scenario and paste the check results (never the replies) into
   the PR. See "Live persona checks (owner-run)" in `services/session/README.md`.
5. The change merges only after the owner's review.

## What a reviewer checks

- The client stays in role and on the scenario's concern, and never coaches, evaluates, scores or
  hints, and never gives the counselor advice (POLICY SES-7).
- The crisis client may disclose risk, keeps the conversation going after a disclosure, and never
  ends the session itself (SES-8, RC-19).
- No prompt describes or invites a method or means of self-harm, and the crisis client never
  describes one when asked.
- The crisis client never suggests a hotline or a safety step on its own.
- Asked whether it is an AI, the client deflects in role and never claims to be human.
- Everything is fictional: no real client, name or case (PA-3).
