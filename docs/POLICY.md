# CaseStudy Tech — Policy

**Question this file answers:** what enduring rules must implementation obey? Read it before any
Issue that touches who gets in, what a student sees, what is scored, what is kept, or what an agent
may change.

Status: reviewed with the owner on 2026-10-31 (Lab 3 · Challenge 2 · Feature 2). Rules marked
**owner, 2026-10-31** came from that interview and are recorded in `docs/lab3/conversation-log.md`.

Authority, highest first: SDD v1.0 (`output/CSCI_5520_CaseStudy_Tech_Software_Design_Document_Final.docx`)
→ Implementation Plan (`docs/lab3/implementation-plan.md`) → this file → code. System structure
lives in `docs/ARCHITECTURE.md`, phase order in `docs/ROADMAP.md`, and task detail in GitHub Issues.
If an Issue conflicts with a rule here, stop and ask. Never settle the conflict in code.

## 1. Roles

| Role | May | May not |
|---|---|---|
| Visitor (signed out) | See the welcome, sign-in and informational screens | Reach anything else (RC-02) |
| Signed-in, not approved | See their access state, request access once, sign out, request account deletion | Reach the library, sessions, reports or history (ACC-4) |
| Student (approved) | Run the released scenarios; see, export and leave their own report; see their own history; sign out; delete their account | See another student's data; create or edit scenarios, personas, rubrics or weights (RC-22); see live scores or hints (RC-10) |
| Admin (the project owner only) | Approve, deny or revoke access requests | See any student's scores, reports or sessions |
| Project owner (human) | Approve vendors and data-use records, calibration labels, release flags, Human Review, merges past `dev` and every deploy | Waive a terms gap (CD-1) or relax the crisis rule (CD-3) |
| Implementation agent | Work Issues that are Ready and Reviewed, within §8 | Make any owner decision |

There is no instructor, supervisor or cohort role in the MVP (SDD §2.3). The access-request queue
is the only admin surface.

## 2. Terms

Use these meanings in code, copy and Issues. Student-facing text uses plain language, not clinical
or technical jargon (SDD §6.3).

| Term | Meaning |
|---|---|
| Access request | The record a signed-in account creates to ask the admin for access. States: pending, approved, denied. A revoked account is denied |
| Scenario | One of three vetted exercises: routine intake, resistant client, crisis risk. Each has an objective, format, time limit and content notice |
| Persona / simulated client | The vetted AI role the student talks to. It stays within its scenario |
| Session | One timed attempt at a scenario, by voice or text |
| Completed session | Ended by the student or by the time limit, with the full transcript intact. Only these are graded |
| Unscored attempt | Any attempt ended by lost content, conduct, or a speech, persona, grading, timeout or connectivity failure. It leaves no score and no history entry |
| Report | Overall score, six category ratings, transcript-grounded examples, strengths and next steps. Developmental, not an assessment |
| Category rating | A 1-to-5 developmental level in one of the six RC-17 categories, shown with its level label (PA-4) |
| Overall score | The RC-17 weighted combination of the six ratings, computed in code, shown as 1.0 to 5.0 |
| Critical safety failure | In the crisis scenario: ignoring explicit risk, encouraging harm, promising secrecy, or failing to prioritize immediate help (RC-19) |
| Safety result | For a crisis attempt only: "safety requirement met" or "not demonstrated" |
| Conduct warning | The single warning given for demeaning language before termination (RC-20) |
| Session content | Audio, transcripts, excerpts and narrative feedback. Never stored (§5) |
| Score record | What the server keeps per completed session: scenario, overall and category scores, completion time, and the safety result for crisis attempts |
| Release gate | The owner's review (#70) before any real student uses the system |

## 3. Session rules

**Before a session**

- SES-1. Every scenario shows its objective, format, time limit and content notice before it starts
  (RC-13, US-02).
- SES-2. The crisis scenario starts only after the student ticks an explicit opt-in on its
  preparation screen. No crisis content appears before that (RC-13).
- SES-3. Start is disabled while the device is offline. Never suggest sessions work offline (RC-07).
- SES-4. Only the three vetted scenarios exist. A scenario that fails the release gate is switched
  off by its release flag, never shipped with a lowered bar (RC-22, CD-3).

**During a session**

- SES-5. The time limit is 10 minutes for every scenario, read from scenario configuration (PA-5).
  The conversation stops at the limit or when the student ends it (US-04).
- SES-6. The student chooses voice or text. Text never needs microphone permission. Voice never starts
  after permission is denied, and text stays available throughout (US-03, RC-12, DD-08).
- SES-7. No live score, hint, correction or coaching appears during a session (RC-10).
- SES-8. A simulated disclosure of self-harm, abuse or imminent danger does not end the crisis
  scenario. The student must be able to respond (RC-19).

**Conduct safeguards (RC-20, US-06)**

- SAF-1. High-confidence targeted threats, slurs or sexual harassment end the session at once, with
  no score.
- SAF-2. Repeated demeaning language gets one warning, then ends the session with no score.
- SAF-3. Quoted case material, frustration not aimed at anyone, and uncertain speech recognition
  never end a session on their own. They get further evaluation first.

**Failure and recovery (RC-08, RC-09, US-05)**

- REC-1. If voice fails and the whole conversation is still in app memory, the student may continue
  the same session in text.
- REC-2. If any content was lost, the attempt ends unscored, leaves no history entry, and offers a
  new text session from the beginning. Recovery never uses stored session content.
- REC-3. A grading failure saves nothing and offers a retry or a new practice.
- REC-4. Every unscored outcome tells the student plainly whether the conversation is safe and that
  no score was saved (SDD §6.3).

## 4. Scoring, report and history rules

- SCO-1. Only a completed session with a complete transcript is graded (RC-09).
- SCO-2. Six categories, each rated 1 to 5, with fixed weights: empathic engagement 20%, active
  listening and responding 20%, purposeful questioning and exploration 15%, collaboration, autonomy
  and cultural humility 15%, session structure and professionalism 10%, scenario-specific
  competence 20% (RC-17). Weights never change in the MVP.
- SCO-3. Never produce a partial, estimated or fabricated score (RC-09).
- SCO-4. Every quoted or paraphrased example must trace to a turn in the transcript. If validation
  fails, show no score (RC-18, RISK-01).
- SCO-5. In the crisis scenario, a critical safety failure overrides the average. The report leads
  with "safety requirement not demonstrated" and shows the average only as a secondary measure
  (RC-19, US-07).
- SCO-6. Resistant-client feedback may apply selected motivational interviewing principles but is
  never called an MITI score (RC-18).
- SCO-7. Anchors and feedback text are original. They cite only the free instruments in plan PA-4.
  Never reproduce CCS-R or MITI manual text.
- SCO-8. Every report says it is developmental feedback, not a validated assessment (SDD §6.3).
- SCO-9. The overall score is shown as 1.0 to 5.0 with one decimal, on the same scale as the
  categories. It is never shown as a percent (**owner, 2026-10-31**).

**Report, export and history**

- REP-1. The report shows right after grading. The student may export it to their device as a PDF
  built on the device (US-08, PA-6). The export matches the displayed report.
- REP-2. Leaving the report asks for confirmation, offers export first, and says the written
  feedback will not be available again (SDD §6.3).
- REP-3. Score history shows only the signed-in student's own score records from completed
  sessions. It never shows audio, transcripts, excerpts, narrative feedback or replay (US-09, RC-02).
- REP-4. A crisis attempt's score record keeps its safety result. History shows that result before
  the numbers, as the report does, so a good average never hides a safety failure
  (**owner, 2026-10-31**; SCO-5).
- REP-5. The server sets each record's completion time. History is ordered newest first, and the
  date is not displayed (**owner, 2026-10-31**; SDD Fig. 8).

## 5. Data handling and privacy

- DAT-1. Session content exists only in app memory and in transient processing, long enough to run
  the session and build the report. It never reaches a database, cache, log, analytics, crash
  report, test fixture or device storage, and it is gone after the report or an abandoned attempt
  (RC-03). The one exception is the report PDF the student chooses to export (REP-1). Where it may
  live in transit is fixed in `docs/ARCHITECTURE.md` §7.
- DAT-2. The server keeps only two things per student: score records (§2) and one access request
  holding the Google display name, Google email, state, and request and decision times
  (**owner, 2026-10-31**). Both stay until account deletion. These are recorded exceptions to
  RC-04's "scores only".
- DAT-3. Account deletion needs explicit confirmation. Access ends as soon as it is confirmed, and
  the account, score records and access request are gone within 30 days (RC-04).
- DAT-4. A speech or AI provider may process session content only under written terms and settings
  that forbid retention and training. Without them the provider is rejected (RC-05, DD-04). This
  outranks quality and cost.
- DAT-5. No new data processor without an owner decision and a written data-use record (zero-retention
  for anything that sees session content). This includes telemetry, crash reporting, analytics and
  email (plan AG-3; the email provider is plan OD-3).
- DAT-6. Development and testing use synthetic data and test accounts only. No real student session
  runs before the release gate confirms written zero-retention terms for every model and speech API
  (PA-3).
- DAT-7. Errors, logs and messages never echo a student's turn, a persona reply, a name, an email or
  a token (plan IR-5).

## 6. Access and security

- ACC-1. Google sign-in is the only method. No passwords, password resets or other providers
  (RC-01, US-01).
- ACC-2. A student reaches only their own data. Identity always comes from a verified token, never
  from a UID or name the client supplies (RC-02).
- ACC-3. Secrets and provider keys stay server-side. None ship in the app (RC-06). All traffic is
  encrypted.

**Access approval (owner, 2026-10-31; plan PA-12).** Modelled on Resuvant spec 024 and the
system-design-course invite flow.

- ACC-4. A new account starts with no access. It may request access once. Until the admin approves
  it, it reaches nothing but its access state, sign-out and account deletion.
- ACC-5. Each request sends the owner one email with the requester's name, Google email and a link
  to the admin queue. Opening the email decides nothing. A failed email never loses the request,
  and retries are rate-limited. The email never contains scores or session content.
- ACC-6. Only the admin can list or decide requests. The admin is configured on the server, never by
  a client. The admin may approve, deny, revoke, or re-approve a denied account. A denied account
  cannot re-request or trigger more email.
- ACC-7. Approval is enforced by every protected API and by the database rules, not only by the UI.
  It is checked on every protected request, with no cached approval, so a revoke applies on the next
  request. A failed access check fails closed, never as approved.
- ACC-8. Revoking access does not delete scores. Only account deletion does (DAT-3).
- ACC-9. The same gate runs in every environment. Development uses approved test accounts.

## 7. Ethical, legal and compliance rules

- ETH-1. The product is a practice and reflection tool. The welcome screen and reports state that it
  does not serve real clients, diagnose, recommend treatment, provide emergency services, conduct a
  validated suicide-risk assessment, certify competence, or replace a licensed instructor or
  supervisor (RC-21).
- ETH-2. The crisis report includes crisis resources, including the 988 Suicide & Crisis Lifeline
  (SDD Fig. 7).
- ETH-3. The MVP does not detect a student's own real distress during a session. The persona stays
  in role. This is an accepted risk (**owner, 2026-10-31**); revisit before institutional use. Do
  not add a detector or pause behavior without an owner decision.
- ETH-4. Web targets WCAG 2.2 AA. Native builds expose equivalent accessibility semantics and work
  with VoiceOver and TalkBack. Text mode stays usable without AI speech or a microphone (RC-11,
  RC-12).
- ETH-5. iOS ships through TestFlight or internal distribution only, while Google is the only sign-in
  (RC-15).
- ETH-6. Users are assumed to be adult postsecondary students. A FERPA review is required before any
  institutional sale (ASM-02, PA-9).
- ETH-7. Release needs the calibration gate and the safeguard gate (PA-10). Every crisis
  critical-failure case must trigger the override, with no exceptions.

## 8. Rules for implementation agents

These expand plan §6.4 (AG-1 to AG-9).

- AGT-1. Requirements win. An RC, a PA, an SDD non-goal or a rule here beats an Issue. Stop and ask.
- AGT-2. Never edit calibration labels, safeguard test cases or RC-17 weights to make a test pass.
- AGT-3. Never make an owner decision (§1). Report it on the Issue and stop. When a contingency
  trigger (plan §6.2) appears, report it and stop; the owner invokes the rule.
- AGT-4. Start only Issues that are Ready with Human Review = Reviewed. Never set Reviewed. A change
  to an Issue's scope or acceptance criteria resets it to Pending.
- AGT-5. Build from the prototype's figures and states, never its markup (PA-8).
- AGT-6. No deploys, no merges past `dev`, no access approvals and no real-student enablement
  (plan AG-9).

## 9. Not in the MVP — do not build

Instructor, cohort or reporting tools; scenario, persona, rubric or weight editing; live coaching;
storage or replay of session content; model training or fine-tuning on sessions, or self-hosted
models; real clients, diagnosis, treatment advice, risk assessment or emergency contact; SSO, LMS or
EHR integration, billing or payments; other disciplines and languages (SDD §2.3).

## 10. Accepted risks — do not "fix" without an owner decision

| Risk | Rule | Revisit |
|---|---|---|
| A student may resend an older signed state and undo a turn or reset the conduct warning | `docs/ARCHITECTURE.md` AD-2 | Before any instructor or cohort feature |
| A student's own real distress goes undetected | ETH-3 | Before institutional use |
| Name and email are kept beyond RC-04's "scores only" | DAT-2 | At the FERPA review (ETH-6) |
