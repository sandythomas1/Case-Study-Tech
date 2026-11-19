# Threat model: keep practice transcripts (owner, 2026-11-17)

Scope: R5 of `spec.md`. Transcripts for all three scenarios are kept server-side in a "FERPA-aligned" way.
The owner floated audio storage, and class feedback asks for a student download. Evidence comes from
`C:/cst18` (feature/4 + dev): `infra/firestore.rules`, `infra/accounts/main.tf`,
`services/accounts/cst_accounts/{store,deletion}.py`. Legal points are an engineering reading of
34 CFR Part 99, not legal advice. The university privacy office confirms them before adoption.

## 1. FERPA: what applies, and when
- **Education record** (34 CFR 99.3): a record *directly related to a student* and *maintained by an
  educational agency or institution, or by a party acting for it*. A practice transcript is directly
  related to the student. The open question is who maintains it.
- **Today (class project, direct-to-student):** the app runs in an owner-held GCP project. No institution
  directs it, contracts for it, or receives its records. The admin sees no content. So these records are
  very likely **not** education records, and FERPA does not bind the app. Other law still applies:
  FTC Act §5 (privacy claims must be true, so never say "FERPA compliant"). If a real student discloses
  their own mental-health information, state health-data laws may also apply
  (e.g. WA My Health My Data Act; SUSPECTED, needs legal review). COPPA and HIPAA do not apply.
- **Grey zone:** if an instructor *requires* a course to use the app, or receives any student data, the
  app may become "a party acting for" the institution. Get privacy-office review before any course adopts it.
- **Once a university adopts it,** transcripts, scores and access records become education records.
  The institution owns the FERPA duties, and the app must make them possible:
  - School-official exception (99.31(a)(1)(i)(B)): the vendor performs an outsourced function, is under
    the institution's *direct control* over use and maintenance, uses data only for that purpose, and
    does not redisclose (99.33). This is written into a **DPA**.
  - The institution's annual notice (99.7) must name vendors as school officials with a legitimate
    educational interest.
  - The student (an eligible student, 99.5) may **inspect** records within 45 days (99.10) and
    **request amendment** (99.20). Disclosures need consent (99.30) or an exception, and are logged (99.32).
  - The institution must use "reasonable methods" so that only officials with a legitimate interest
    get access (99.31(a)(1)(ii)). On contract end, the data is returned or destroyed.
- **"FERPA-ready" MVP bar** (cheap now, expensive to retrofit):
  - purpose limitation: student self-review only, with no training, calibration or sale;
  - no admin or human content access;
  - an access audit trail;
  - self-serve export (inspection) and per-item delete (in place of amending a verbatim record);
  - a retention schedule with automatic expiry, and deletion that provably completes, backups included;
  - US region (`us-central1`), a separate prod project, a breach runbook, and a DPA-ready data map.

## 2. Assets, boundaries, entry points
- **Assets:** the saved transcript (student turns, persona turns, scenario, safety result). Crisis
  transcripts are the most sensitive. Also: the KMS key, audit logs, and the downloaded file on the device.
- **Boundaries:** device (untrusted) → gateway → accounts and session services → private grader →
  Firestore and KMS. Humans with GCP IAM in prod are a boundary too: **the admin is also the GCP owner.**
- **New entry points:** the grader's transcript write; `GET`/`DELETE` of the student's own transcripts;
  the export; the deletion job; TTL expiry; the Firestore console and exports; PITR and backups.

## 3. Threats (STRIDE, ranked by likelihood × impact)
| ID | Sev | STRIDE | Threat | Mitigation |
|---|---|---|---|---|
| T1 | HIGH | I | The **admin/owner or a GCP insider reads content** in the Firestore console, a managed export or a PITR read. Owner/Editor include `datastore.entities.get`, and CMEK decrypts transparently, so CMEK does not stop this | C5 app-layer envelope encryption. No standing human data roles in prod (PAM just-in-time). C7 alerts on any human decrypt or read |
| T2 | HIGH | I/E | **Cross-student read (IDOR)** on the new read, export or delete endpoints, e.g. a caller-supplied `uid` or a guessable session ID | Path is built only from the verified token's UID (as in `store.scores`). Random 128-bit session IDs. The AEAD associated data binds `uid`+`sessionId`. Non-owner, unauthenticated and admin tests |
| T3 | HIGH | I | **Deletion leaves copies.** VERIFIED: `store.py:92-102` `erase_scores` deletes only `scores`, then the parent doc. Firestore never cascades to subcollections, so `students/{uid}/sessions` would be orphaned. PITR, backups, managed exports and GCS soft delete (7-day default) also survive | C8 cascade |
| T4 | HIGH | I | **Crisis content.** A simulated-crisis transcript plus "safety not demonstrated" is reputationally sensitive. A student's *real* distress (ETH-3) may now be stored, which raises duty-of-care questions | Crisis opt-in states that the transcript is saved. Per-session "don't save" (D4). Shorter crisis retention if D3=B. ETH-3 revisit moves to "before storing real transcripts" |
| T5 | MEDIUM | E | **Over-broad service IAM.** VERIFIED: `main.tf:37-46` role `cstAccounts` grants project-wide `datastore.entities.get/list/create/update`. Firestore IAM cannot scope by collection, so the accounts service could read any student's transcripts after one code bug | C5. Only the accounts SA gets `useToDecrypt`, and only the grader SA gets `useToEncrypt`. Drop `entities.create/update` from accounts unless a write needs it |
| T6 | MEDIUM | I | **Real transcripts copied to dev** (AD-5) for debugging or grader calibration | DAT-6 rewrite. Separate KMS keys per project. Prod SAs and keys never granted in dev. Ban managed exports from prod |
| T7 | MEDIUM | I | **Content in logs** (validation errors, exceptions, Firestore client errors) | Unchanged DAT-7 and #63. #39's scan adds the transcript write path. Pydantic errors return no input (as `api.py:62-67` does) |
| T8 | MEDIUM | R | **No record of who read what.** Firestore Data Access logs are off by default | C7 |
| T9 | MEDIUM | I | **Re-identification** from text (the student says their name or school) or, if audio is kept, from voice (a biometric: Illinois BIPA lists voiceprints) | No server audio (C10). The notice says not to use real names. Optional redaction later needs a DAT-5 decision |
| T10 | MEDIUM | I | **Third-party real client data** typed in by practicum students | The notice forbids real client details. ETH-1 copy |
| T11 | MEDIUM | I | **Export leaks:** a file on a shared device, a revealing filename, or a long-lived link | C9 |
| T12 | MEDIUM | I | **Vendor retention or purpose creep.** Keeping transcripts tempts reuse for evaluation or training, and stored text sent back to Vertex is a new processing purpose | DAT-4 stands unchanged. Saved transcripts are never sent to any model, never used for calibration, and never reach a vendor (D1) |
| T13 | MEDIUM | T | **Forged or partial transcript stored**: an unsigned state, a client write, or a mid-session save | Only the grader writes, from the verified #66 handoff, in one transaction with the score and the deletion-marker check. Rules deny client writes |
| T14 | MEDIUM | S/R | **Deceptive notice or claims:** "FERPA compliant", or a missing notice | C1. Copy reviewed against §1. Notice version recorded |

LOW:
- **T15 (D):** an oversize doc (1 MiB limit) or index fan-out (40k entries/doc) fails the write.
  Fix: cap and index exemption (C3).
- **T16:** conduct-terminated transcripts would retain abuse. Fix: don't save unscored attempts (D8).
- **T17:** TTL is late (typically within 24 h, not guaranteed). Fix: the deletion job sweep is the backstop.
- **T18:** a CMEK key is lost or disabled and the database becomes unreadable. Fix: only if CMEK is chosen.

## 4. Required controls
| ID | Sev | Control |
|---|---|---|
| C1 | HIGH | **Notice and consent.** A blocking first-use notice: what is kept, why (self-review only), how long, who sees it (only you, no admin or instructor), how to download or delete, and no real names or client details. Record `notice_version` and `accepted_at`. Before each session, one line on the preparation screen plus a "don't save this session" option (D4). The crisis opt-in (SES-2) names saving explicitly |
| C2 | HIGH | **Retention and expiry.** A server-set `expire_at` (D2), a Firestore TTL policy on the session collection group, a deletion-job sweep of anything past `expire_at`, and per-item student delete |
| C3 | MEDIUM | **Storage shape.** One doc `students/{uid}/sessions/{sessionId}` with no subcollections, written by the grader in the score's transaction. Fields: scenario, completed_at, expire_at, key version, ciphertext. Cap the plaintext at 256 KiB (10 min of text is roughly 10–40 KB) and reject larger at #66. Single-field index exemption on the ciphertext. No Cloud Storage unless audio is approved (D5) |
| C4 | HIGH | **Access rules.** Only the grading SA writes, and only via `useToEncrypt` plus a Firestore create. Only the accounts service reads, and only for the verified UID. The admin and humans read nothing. Rules: `match /students/{s}/sessions/{d} { allow read, write: if false; }`. The client still has no Firebase SDK. Rules tests: owner, non-owner, unauthenticated, admin all denied. API tests: non-owner and admin get 404 |
| C5 | HIGH | **Encryption.** Google default AES-256 at rest stays. Add **app-layer envelope encryption** (Tink AEAD, one Cloud KMS KEK per project, associated data = `uid|sessionId`, annual rotation). Firestore CMEK is optional (LOW). It can only be set when the database is created, and it does not stop T1 |
| C6 | HIGH | **Prod IAM.** No standing human `datastore.*` or `cloudkms.*Decrypt` roles in prod. Use break-glass via Privileged Access Manager. Organisation policy or written runbook: no `gcloud firestore export` of prod |
| C7 | MEDIUM | **Audit.** Enable Data Access logs (DATA_READ/WRITE) for `datastore.googleapis.com` and `cloudkms.googleapis.com` in prod. Route them to a dedicated log bucket kept ≥ the transcript retention. Alert on any principal outside {grader, accounts, deletion} SAs |
| C8 | HIGH | **Deletion cascade (#46, DAT-3).** The job erases `sessions` before `scores`, then the access record, then `auth.delete`, inside the 30-day deadline. PITR ≤ 7 days. No scheduled backups, or backup retention ≤ 21 days. GCS soft delete ≤ 7 days if any bucket holds content. Disclose Google's backend deletion tail in the DPA. Emulator test: deleting a student leaves zero docs under `students/{uid}/**` |
| C9 | MEDIUM | **Export.** `GET /v1/sessions/{id}/transcript` (own only, `no-store`, rate-limited). The file is built on the device (like PA-6) as text or PDF. Filename has the scenario and date only, no name or email. Crisis files carry a content header. No server-hosted or shareable links |
| C10 | HIGH | **Audio: do not keep it server-side.** If students want recordings, offer an on-device "save my recording" built from audio already on the device. It is never uploaded beyond the transient turn and needs a DAT-1 exception. If server audio is ever approved: a dedicated CMEK bucket, PAP enforced, lifecycle = retention, soft delete 0, signed URLs ≤ 5 min, uid-prefixed for the cascade, and a BIPA review |
| C11 | MEDIUM | **Purpose lock.** Saved transcripts never go to any model, eval set, calibration set, dev project or vendor. Enforced by IAM (only the accounts SA decrypts) and by policy |

## 5. Rules and Issues to change (do not edit until D1–D9 are settled)
Higher authority first: SDD **RC-03, RC-04, DD-03** and plan **PA-6, §6.4 rule 2, IR-5** forbid content
at rest. The owner records a change note there (D9), or POLICY loses its footing (AGT-1).

POLICY:
- **§1** Student row: "…see, download and delete their own saved transcripts". Admin row: "…scores,
  reports, sessions or transcripts".
- **§2** "Session content": "…Audio and narrative are never stored. Completed-session transcripts are
  stored encrypted per DAT-1". Add "Saved transcript" as a new term.
- **SES-1/SES-2**: "…and states whether the transcript will be saved; the crisis opt-in names saving".
- **REC-2**: keep, and add "Recovery never reads a saved transcript."
- **REP-1**: "…may also download their own saved transcript, built on the device".
- **REP-2**: "…the written feedback will not be available again; the transcript stays until it expires
  or is deleted".
- **REP-3**: "History shows only the student's own records and their own saved transcripts; never
  audio, narrative or replay".
- **DAT-1**: "Audio, excerpts and narrative live only in memory or transit. A completed session's
  transcript is stored once, encrypted, by the grader, until expiry or deletion. The device keeps only
  student-initiated exports".
- **DAT-2**: "The server keeps score records, saved transcripts, and one access record with notice
  acknowledgement".
- **DAT-3**: "…the account, scores, transcripts and access request are gone within 30 days, including
  PITR and backups".
- **DAT-4**: keep, and add "Saved transcripts are never sent to any provider".
- **DAT-6**: "…No real transcript ever enters the development project, a test fixture or a calibration set".
- **ETH-3**: revisit trigger becomes "before storing real-student transcripts".
- **ETH-6**: "MVP meets the FERPA-ready bar (threat-model §1). Never claim FERPA compliance".
- **§9**: "storage or replay of session content" → "server storage of audio or narrative; any
  non-student access to transcripts".
- **§10**: add a row, "Real distress may be stored in a transcript (ETH-3), revisit before institutional use".

ARCHITECTURE:
- **§1**: "The server keeps the scores and an encrypted transcript per completed session".
- **AD-1**: add "Saved transcripts are post-session records, never session state".
- **§3**: Firestore row "…`students/{uid}/sessions/{id}` (encrypted)". Grader row "…writes scores
  and the encrypted transcript". Accounts row "…own transcript read, export, delete". New row for Cloud KMS.
- **§4**: flow 4 "writes scores and the encrypted transcript in one transaction"; flow 6 "…and
  `/v1/sessions`"; flow 7 "deletes sessions, scores, access record".
- **§5**: "Only the grading service writes scores and transcripts; only the accounts service decrypts".
- **§6 Data**: "Firestore: scores, encrypted transcripts, access record; Cloud KMS envelope keys".
- **§7**: row 1 drops Firestore from "must never reach" for transcripts only, and adds "humans, the
  admin, any model, the dev project".
- **§8**: invariant 1 becomes "Never persist audio, excerpts or narrative; persist transcripts only via
  the grader, encrypted". Add "Never let a human principal decrypt a transcript in prod".
- **§9**: add "Data Access logs on; PITR ≤ 7 days; no prod exports".

ROADMAP: Phase 3 "Nothing from it persists" and Phase 6 "scores-only history".

Issues (scope changes reset Human Review to Pending per AGT-4):
- **#39**: "Prove no content in logs, analytics or crash reports; transcripts exist only as ciphertext in the session doc".
- **#40**: "Persist the score record and the encrypted transcript in one transaction".
- **#46**: "Cascade deletion to transcripts, plus the PITR/backup limits".
- **#18**: "Add the KMS keyring and per-SA encrypt/decrypt grants, plus Data Access logs".
- **#41**: "History lists saved transcripts with view, download and delete".
- **#42**: "Add transcript download; REP-2 copy".
- **#59**: "Data map: retained = score + transcript".
- **#66**: "Handoff carries the save flag and size cap".
- **#68 / #35**: "Grader writes the transcript".
- **#29 / #30**: "Per-session notice, don't-save toggle, first-use notice copy".
- **#34**: "Crisis save notice".
- **#44**: "Recovery never reads saved transcripts".
- **#72**: "Access record gains notice acknowledgement".
- **#77**: "Prod: PAM, audit logs, no backups beyond 21 days".
- **#70**: "Gate adds the FERPA-ready checklist and the DPA template".
- **New Issues**: first-use notice; transcript read/download/delete endpoints; KMS envelope encryption.

## 6. Open owner decisions (L2)
| ID | Decision | Options (recommended first) |
|---|---|---|
| D1 | Purpose | **A. Student self-review only.** B. Plus future instructor review under a DPA (adds a role and consent). C. Plus product calibration (needs opt-in and de-identification; conflicts with DAT-6) |
| D2 | Retention | **A. 180-day TTL, plus student delete anytime, plus account deletion.** B. Until account deletion (like scores). C. 30 days |
| D3 | Crisis transcripts | **A. Same as D2, with explicit save wording in the opt-in.** B. Shorter (30 days). C. Never saved |
| D4 | Consent model | **A. First-use acknowledgement, plus a per-session notice with a "don't save" toggle (default save).** B. First-use only. C. Per-session opt-in (default off) |
| D5 | Audio | **A. No server audio; on-device save only.** B. No audio anywhere. C. GCS audio for selected scenarios (needs a BIPA review and C10 controls) |
| D6 | Encryption | **A. App-layer KMS envelope encryption.** B. Firestore CMEK plus PAM plus alerts. C. Google default only |
| D7 | What is saved | **A. Transcript only.** B. Transcript plus narrative report (REP-2 changes) |
| D8 | Which attempts | **A. Completed (graded) sessions only.** B. Plus unscored attempts except conduct-terminated |
| D9 | Authority | **A. Owner amends SDD RC-03/RC-04 and plan PA-6/§6.4 by change note.** B. A recorded POLICY exception only |
