# Class feedback + transcript retention: what to change (2026-11-18)

Sources: the class critique PDF, Sandy's edited proposal deck, `threat-model.md` (in this folder) and
`speech-providers.md` (in this folder). Owner decisions are recorded in `build-log.md`.

## 1. Architecture

| # | Nudge | Why |
|---|---|---|
| A1 | Name every box precisely: the Gemini model and version on Vertex AI, the STT/TTS vendor and model, Firestore Native us-central1, Cloud KMS, Identity Platform. Label anything still open "chosen by bake-off #20 / OD-2" instead of leaving it generic. | The professors' main critique was "which model, which version?" |
| A2 | Split the diagram into two layers. **App layer** ("Persona interface"): student app, session engine, persona harness, conduct safeguard, grader, report. **Cloud services** it runs on: API Gateway, Cloud Run, Identity Platform, Vertex AI, speech vendor, Firestore, KMS, Secret Manager, Logging. | Feedback: separate what *you* built from what you *use*. |
| A3 | Regroup into lanes: Client → Edge → App services → AI providers → Data → Ops. Draw grading as private and reachable only from session (AD-3). | Feedback: decouple and regroup the components. |
| A4 | Add the new transcript path: grader → KMS-encrypted `students/{uid}/sessions/{id}` → 180-day TTL → accounts-service read/delete. Add Data Access audit logs. | Transcript retention is new data at rest. |
| A5 | One region everywhere: **us-central1** (ARCHITECTURE §6). Deck slide 6 says us-west1. | Inconsistency a grader will spot. |
| A6 | Relabel Vertex AI as **Gemini Enterprise Agent Platform** ("Agent Platform"; the rename is in the release notes of 2026-04-22). "GEAP" is not Google's abbreviation. If Chirp 3 stays in the bake-off, note that it runs only in the `us`/`eu` multi-regions, not us-central1. | Verified in `speech-providers.md`. |
| A7 | Fix a deletion bug before transcripts exist: `services/accounts/cst_accounts/store.py` `erase_scores` deletes only `scores`. Firestore never deletes subcollections on its own, so transcripts would survive account deletion. | Threat model HIGH. Breaks DAT-3/RC-04. |
| A8 | Admin = GCP owner = can read Firestore in the console. Encrypt in the app with KMS: the grader encrypts, the accounts service decrypts. Production uses just-in-time human access. | Keeps "admin never sees content" true. |

## 2. Deliverables

| # | Nudge |
|---|---|
| D1 | **Amend the SDD to v1.1 first.** RC-03 (never store content), RC-04 (scores only) and the §2.3 non-goal "stored or replayable sessions" all forbid the new decision. The SDD outranks POLICY, so agents must not rewrite POLICY until the SDD and Implementation Plan (PA-6, §6.4 rule 2) say so. |
| D2 | Rewrite POLICY: §1, §2 (the "Session content … never stored" line), SES-1/2, REC-2, REP-1/2/3, DAT-1/2/3/4/6, ETH-3, ETH-6, §9 and §10. Rewrite ARCHITECTURE: §1, AD-1, §3, §4 flows 4/6/7, §5, §6, §7, §8 and §9. Rewrite ROADMAP Phases 3 and 6. Proposed wording: `threat-model.md`. |
| D3 | Fix the deck so it states one retention story. Slides 3 and 6 say "routine and resistant only"; slide 7 says "scores only"; slide 9 says "transcripts never stored"; slide 10 says "nothing stored"; slide 12 says "Firestore holds no transcript". All should become: *transcripts for all three scenarios, encrypted, 180-day expiry, deletable anytime, no server audio*. |
| D4 | New deliverable: a short **terms of use / privacy notice**: what is saved, why, for how long, who can see it (only the student), how to delete or export it, and the "don't save this session" option. Class feedback asked for exactly this. |
| D5 | Never write "FERPA compliant". Write "designed to be FERPA-ready". Until a university adopts the app, FERPA doesn't formally apply, and a compliance claim is an FTC §5 risk. |

## 3. What the app does (MVP changes)

- First-use notice, and a **"Don't save this session"** toggle on every preparation screen. Grading
  and the score are unaffected.
- The crisis opt-in screen says plainly that the transcript is saved (owner: same rules + explicit wording).
- History gains a **transcript view, delete and on-device export** for the student's own sessions only.
- Only graded sessions are saved. Unscored attempts still leave nothing (REC-2 unchanged).
- Leaving the report: the warning changes to "written feedback won't be available again; your
  transcript stays in history for 180 days".
- No audio on the server. Students may save their own audio on the device (class feedback).

## 4. Post-MVP backlog (from class feedback; not approved)

Tone/prosody and sarcasm detection · video / facial-expression analysis · full-duplex voice ·
Canvas/Blackboard gradebook plug-in · institutional SSO. SSO and the LMS plug-in are the point where
FERPA formally applies (school-official exception, a DPA, inspect/amend rights).

## 5. Issues whose scope changes (each resets Human Review → Pending)

#39, #40, #46, #18, #41, #42, #59, #66, #68, #35, #29, #30, #34, #44, #72, #77, #70, plus three new
Issues: the transcript store and encryption, transcript history/delete/export UI, and the privacy notice.
One-line wording for each: `threat-model.md`.
