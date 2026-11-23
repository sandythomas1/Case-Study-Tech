# Saved transcripts for student self-review

**Status:** Accepted by the owner (2026-11-17 decision, details 2026-11-18). It takes effect when the
owner's SDD change note amends RC-03, RC-04 and DD-03 (and plan PA-6 and §6.4 rule 2). Until then
SDD v1.0 outranks this record (POLICY AGT-1), and nothing that stores a transcript is built or deployed.

**Rules this record changes:** POLICY DAT-1, DAT-2, DAT-3, §9 and §10 · ARCHITECTURE §1, §6, §7 and §8.

**Evidence:** `specs/inprogress-sweep-2026-11-18/threat-model.md` (branch
`docs/class-feedback-2026-11-17`) has the FERPA analysis, threats T1–T17, controls C1–C11 and
decisions D1–D9.

## Why

Class feedback asked students to be able to review and download what they said. The MVP forbade
storing any session content (RC-03), so a student lost the transcript when the report closed.

## Decision

| ID | Question | Decision |
|---|---|---|
| D1 | Purpose | Student self-review only. No training, calibration, evaluation or sale |
| D2 | Retention | 180-day expiry set by the server, plus delete at any time, plus account deletion |
| D3 | Crisis scenario | Same as the others. The crisis opt-in states that the transcript is saved |
| D4 | Consent | A first-use notice the student acknowledges, plus a per-session notice with a "don't save" option (saving is the default) |
| D5 | Audio | Never stored on the server. Saving audio on the device only is allowed |
| D6 | Encryption | Application-layer envelope encryption with Cloud KMS. The grading service encrypts, and only the accounts service decrypts for the owning student |
| D7 | What is saved | The transcript only. Narrative feedback is not saved |
| D8 | Which attempts | Completed (graded) sessions only |
| D9 | Authority | The owner amends the SDD by change note. The SDD PDF is the owner's to update |

D1, D6 and D8 were the lead's recommended defaults. The owner kept them.

## Consequences

- Never describe the app as "FERPA compliant". The bar is "FERPA-ready" (threat model §1).
- Saved transcripts never reach a model, a vendor, an eval or calibration set, or the development
  project as real data. No human principal decrypts one in production.
- The deletion job and account deletion remove transcripts too. Firestore TTL is a backstop, not the
  only mechanism, because TTL deletion can run up to a day late.
- Still to amend in follow-up Issues: POLICY §1, §2, SES-1/SES-2, REP-1 to REP-3, DAT-4, DAT-6,
  ETH-3 and ETH-6; ARCHITECTURE §3, §4, §5 and §9 (KMS, Data Access logs, PITR); ROADMAP Phases 3
  and 6; and Issues #18, #29, #30, #34, #41, #42, #70 and #72 (threat model §5).
- New Issues: the first-use notice, transcript read, export and delete endpoints, and KMS envelope
  encryption.
