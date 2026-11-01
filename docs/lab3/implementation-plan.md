# CaseStudy Tech — Implementation Plan

CSCI 5520 — AI-Driven Software Development · Sandy Thomas · Draft started 2026-10-28

Markdown source for the course-template DOCX. Stable IDs (US-##, RC-##, DD-##, OQ-##, ASM-##,
RISK-##) refer to the SDD v1.0 (2026-10-04). This plan sequences the work; GitHub Project #1
becomes the authoritative work queue once Issues are created (Section 7).

## 1 Implementation Overview

### 1.1 Implementation Objective

Deliver the CaseStudy Tech MVP student practice loop defined in SDD §2.2:

- Google sign-in (US-01).
- One of three vetted scenarios with an informed start (US-02).
- A time-bounded voice-first session with text fallback (US-03, US-04).
- Safe recovery and conduct safeguards (US-05, US-06).
- A separate post-session grading pass producing an evidence-linked developmental report (US-07).
- Local report export (US-08).
- A scores-only history (US-09).

The deliverable is a working React Native build for web, iOS (TestFlight/internal only, RC-15) and
Android. It runs on the managed Google Cloud services in SDD §5.

Scope boundaries for every phase:

- Requirements RC-01 to RC-22 are hard constraints. When a technical choice conflicts with one, the
  requirement wins.
- The SDD §2.3 non-goals stay out. That means no instructor or institutional tools, no
  content authoring, no live coaching or live scores, no stored or replayable sessions, no model
  training or self-hosting, no clinical or emergency use, no enterprise or billing features, and no
  additional disciplines or localization.

### 1.2 Source Design Artifacts

| Artifact | Location | Authority |
|---|---|---|
| Software Design Document v1.0 (2026-10-04) | `output/CSCI_5520_CaseStudy_Tech_Software_Design_Document_Final.docx` | Authoritative for scope, stories, requirements, decisions |
| Interactive UI/UX prototype (Figma Make) | https://www.figma.com/make/liPGx5kd9Cb6LeVcHHgddH/Interactive-UI-Mockup-for-CaseStudy-Tech | Authoritative for screens and flow; not production code (RISK-05) |
| Architecture diagram — SDD Figure 1 | `docs/02-gcp-architecture.png` (Lucidchart source) | Authoritative for components and data flow |
| Experience flow — SDD Figure 2 | SDD §6.1 | Authoritative for the student journey and recovery branches |
| Screen figures — SDD Figures 3–10 | SDD §6.2 | Visual references for Issues |
| Discovery notes (2026-09-16) | `docs/01-discovery-notes.md` | Background only; superseded by the SDD |
| Account boundaries decision | `docs/decisions/0001-account-boundaries.md` (draft PR #62) | Authoritative for sign-in, token handling, Firestore ownership and deletion |
| Existing backlog | GitHub Project #1: 10 epics and 40 child Issues created from the SDD before Lab 3 | Reconciled in place by §5.1 |

### 1.3 Planning Assumptions & Scope Guardrails

These assumptions and decisions change the build order. Each was decided by the project owner
during Lab 3 planning unless it is marked **open**.

| ID | Assumption / guardrail | Effect on sequencing | Source |
|---|---|---|---|
| PA-1 | Solo builder, roughly six-week MVP window. If the schedule slips, cut polish, never data-retention or safety requirements. | Phases are ordered so each one leaves a demonstrable loop. | RISK-06 |
| PA-2 | **Speech provider is chosen first.** A provider evaluation spike compares voice quality, round-trip latency, cost per session and verified zero-retention terms before session work starts. The provider stays behind a replaceable interface. **Latency target:** voice round trip (end of student speech to first persona audio) at p50 ≤ 2.0 s and p95 ≤ 3.5 s. A provider that misses it is rejected, unless the owner records an exception under §6 CD-1. | The provider decision sits on the critical path ahead of voice session work. Voice-first per DD-08, with text always available. | OQ-01, RC-05, RC-16, RISK-02 |
| PA-3 | **Synthetic data until zero-retention is confirmed.** Development and testing use only synthetic transcripts and test accounts. No real student session runs until zero-retention and no-training terms are confirmed in writing for every model and speech API in use. | Persona and grading integration can proceed; written confirmation is a release gate. | OQ-02, RC-05, DD-04 |
| PA-4 | **Rubric anchors are hybrid and built from free sources.** The six categories and weights stay fixed (RC-17). The grader scores against observable behaviors for each 1-to-5 level (WHO EQUIP style); students see developmental level labels. Anchor text is original and cites only free instruments: EQUIP/ENACT, FIS, CTS-R, Bogo OSCE, CSWE EPAS and SIRI-2. Ivey microskills and MI principles appear only as cited concepts. CCS-R and the MITI manual are not used. Survey: `docs/lab3/rubric-survey.md`. | An early grading-phase Issue drafts the anchor spec. | OQ-03 (resolved), RC-17, RC-18 |
| PA-10 | **Calibration replaces faculty review.** *This supersedes SDD OQ-03 and the faculty-review requirement in RISK-03.* No faculty review gates the anchors or the crisis scenario. Instead, release requires (a) the grader to score a labeled calibration set of synthetic transcripts (strong, weak and harmful per category, plus crisis critical-failure cases) with every category within ±1 level of its label on at least 90% of transcripts, and with every crisis critical-failure case triggering the safety override; and (b) the conduct and crisis safeguards to pass every labeled test example (see §3.4). Calibration transcripts are drafted by a model family different from the grader's, and the owner approves every label before grader work starts (§6 CD-5). | Calibration-set creation is on the grading phase's critical path. | RISK-01, RISK-03, RISK-04, RC-19, RC-20 |
| PA-5 | **Session time limit: 10 minutes for all three scenarios.** The limit lives in per-scenario configuration, so changing it later is a config edit. | Session timer work must read the limit from scenario config. | OQ-04 (resolved) |
| PA-6 | **The report PDF is generated on the device.** After the report is delivered, the narrative never goes back to the server, so RC-03 holds by design. Web, iOS and Android each need a working PDF path. | The export deliverable sits in Phase 5. No server render endpoint exists. | OQ-05 (resolved), RC-03, US-08 |
| PA-7 | **Expo + FastAPI.** The client is Expo (React Native with react-native-web), giving one codebase for web, iOS and Android. The session and grading services are Python FastAPI on Cloud Run. The SDD fixes the managed GCP services but not these two choices. | The scaffold is the first Phase 1 deliverable. The stack is recorded in `docs/ARCHITECTURE.md`. | DD-06, DD-09, RC-14 |
| PA-8 | The prototype is a design reference, not code to copy. Its known defects (empty-state history, score-ring percent sign) are fixed during implementation. | UI Issues link figures, not prototype markup. | RISK-05 |
| PA-9 | Users are adult postsecondary students with Google accounts. A FERPA review is needed before institutional sales but does not block the MVP. | No MVP phase. | ASM-01, ASM-02 |
| PA-11 | **The plan follows the code.** Work already built in draft PR #62 stays where it is: the accounts service, Terraform, Firestore rules and account deletion are Phase 1. The existing Issues are reconciled in place, not recreated (§5). | Phase 1 is partly in progress. Account deletion moves from Phase 6 to Phase 1. | Owner decision, 2026-10-30 |
| PA-12 | **Invite-only access.** A Google sign-in creates an account that reaches nothing until the owner approves it from an admin queue. Each request emails the owner. Approval is enforced in every API and in the Firestore rules. This adds an admin role and an access record (name and Google email), both recorded exceptions to the SDD's single role and RC-04's "scores only" (`docs/POLICY.md` ACC-4 to ACC-9, DAT-2). Modelled on the system-design-course invite flow. | Five Phase 1 Issues (#72 to #76) sit between the identity guard and the library. The email needs OD-3 first. | Owner decision, 2026-10-31 (POLICY interview) |

## 2 Phase Summary

Six phases, each ending in a demonstrable increment. Phase 1 is partly in progress in draft PR #62
(PA-11). Phase 2 runs alongside Phase 1. Phase 5's anchor spec and calibration set are authored
from day one; its grader code starts after Phase 1 on synthetic transcripts and integrates with
real transcripts once Phase 3 lands (§4).

| Phase | Goal / Increment | Primary SDD Sources | Key Deliverables | Depends On | Candidate Issues |
|---|---|---|---|---|---|
| 1 | Foundation & access — an approved student signs in, browses the three scenarios, reviews preparation info and can delete their account | US-01, US-02, RC-01, RC-02, RC-04, RC-06, RC-13, RC-14, RC-22, DD-05, DD-06, DD-09, PA-12 | RN shell (web/iOS/Android), accounts service with Google sign-in, owner approval gate with admin queue, Terraform GCP baseline, Gateway + Cloud Run, Firestore owner rules, account deletion, Secret Manager, content-free logging, scenario config incl. per-scenario time limit | None | 10 — §3.1 |
| 2 | Provider & compliance spike — speech vendor chosen and zero-retention confirmed in writing | OQ-01, OQ-02, RC-05, RC-16, RISK-02, DD-04 | Provider comparison + decision record, Vertex zero-retention settings, replaceable speech interface | None (parallel to 1) | 5 — §3.2 |
| 3 | Practice session — timed voice-first session with text, persona replies, End session, offline check | US-03, US-04, RC-03, RC-07, RC-10, RC-12, DD-01, DD-08 | Session service, persona prompts, voice + text UI, timer, transient state | 1; 2 for voice | 6 — §3.3 |
| 4 | Safety & recovery — conduct safeguards, recovery paths, crisis disclosures that do not end the session | US-05, US-06, RC-08, RC-19, RC-20, RISK-04 | Conduct safeguard, recovery flows, labeled safeguard test set | 3 | 6 — §3.4 |
| 5 | Grading & report — evidence-linked report with crisis override, passing the calibration gate | US-07, US-08, RC-09, RC-10, RC-17, RC-18, RC-19, OQ-05, RISK-01 | Anchor spec, separate grader, citation validation, calibration set, report UI, on-device export | 1 (synthetic); 3 for integration | 7 — §3.5 |
| 6 | History & release — scores-only history, release gates met | US-09, RC-04, RC-11, RC-12, RC-14, RC-15, PA-3, PA-10 | Firestore score record and history, accessibility audit, platform parity, TestFlight build, release gate review | 4, 5 | 6 — §3.6 |

## 3 Detailed Implementation Phases

Figure numbers refer to SDD §6. "Prototype state" names a state in the Figma Make reviewer panel.
Every phase uses synthetic data only until the PA-3 release gate is met.

### 3.1 Phase 1 — Foundation & access

#### Goal

A student signs in with Google on web, iOS or Android. Once the owner approves the account (PA-12),
the student browses the three vetted scenarios and opens a scenario's preparation screen. The start controls follow the opt-in and connectivity rules. A
student can sign out or request account deletion. Starting a session is wired up in Phase 3.

**Status (2026-10-30): partly in progress.** Draft PR #62 (`feature/4-access-accounts`) carries the
Expo app, the accounts service, the Terraform baseline, the Firestore rules, account deletion and
58 passing tests. It still needs real OAuth clients, iOS evidence from a Mac, a fix for the #61
dependency findings, and alert destinations plus abuse controls for the unauthenticated
token-exchange routes. The plan follows that code (PA-11).

#### Source Requirements / Design References

US-01, US-02 · RC-01, RC-02, RC-04, RC-06, RC-07 (pre-session connectivity check), RC-13, RC-14,
RC-21, RC-22 · DD-05, DD-06, DD-07, DD-09 · PA-5, PA-7, PA-11, PA-12 · `docs/POLICY.md` ACC-4 to ACC-9 ·
`docs/decisions/0001-account-boundaries.md` · Architecture: client, Identity Platform, API Gateway,
Cloud Run, Firestore, Secret Manager, Cloud Logging (Fig. 1).

#### Deliverables

- An Expo project (React Native + react-native-web) at `apps/student` that produces web, iOS and
  Android builds. CI runs lint, typecheck, tests and a dependency audit.
- The GCP baseline in Terraform (`infra/`): Cloud Run, API Gateway generated from a template,
  Identity Platform, Firestore and Secret Manager.
- The accounts service (`services/accounts`), the first FastAPI service on Cloud Run behind API
  Gateway. The gateway validates the token. The service then re-verifies the original Firebase
  token, its revocation status and the Google provider. Later services reuse this pattern.
- Google sign-in, sign-out and a sign-in failure state. The server exchanges the Google token
  through Identity Platform, so no API key ships in the client. ID tokens live only in memory.
- Firestore security rules with emulator tests: a student reads only their own collection, and
  every client write is denied.
- Invite-only access (PA-12): an access record per account, an approval check in every protected
  API and rule, an owner email per request, the admin queue and the student's access-state screens.
- Account deletion on the Account screen. It needs confirmation and first writes a denial marker,
  so access fails closed even during an outage. Cleanup retries until the account and its data are
  gone, within 30 days.
- Provider credentials served from Secret Manager. A CI check scans the client bundle for secrets.
- Accessible UI primitives and the Figma visual tokens, so every screen starts accessible and on
  brand (RC-11, PA-8).
- A structured-logging helper that drops session-content fields, with a test that proves it.
- Read-only scenario configuration for the three scenarios: objective, format, time limit, feedback
  timing, content notice, crisis opt-in flag and a release flag. Each scenario has its own time
  limit, set to 10 minutes (PA-5). The release flag hides a scenario held back under §6 CD-3.
- Welcome, Library and Preparation screens. They include the "What this is not" educational
  boundary, the crisis opt-in checkbox and an offline check that disables both start buttons.

#### Phase Acceptance Criteria

- On all three builds, a valid Google sign-in from an approved account opens the library and
  sign-out returns to Welcome. No other sign-in method appears (US-01, RC-01).
- An unapproved account reaches only its access state, sign-out and account deletion, in the APIs
  and the rules as well as the UI. A revoke applies on the next request (PA-12).
- An unauthenticated client cannot reach the library. An unauthenticated API request gets a 401
  (RC-02).
- Rules tests deny cross-user reads and all client writes (RC-02).
- Deletion requires confirmation and blocks access as soon as it is confirmed. The account and its
  data are removed within 30 days, and an interrupted cleanup resumes (RC-04).
- The library shows the three vetted scenarios, minus any whose release flag is off, and offers no
  create or edit control (RC-22).
- Each preparation screen shows the objective, format, configured time limit and content notice. On
  the crisis scenario, both start buttons stay disabled until the student checks the opt-in. Every
  start button is disabled while the device is offline (US-02, RC-13, RC-07).
- CI fails when a credential pattern appears in the client bundle. The logging test shows that
  content fields are never written (RC-06, RC-03).

#### Dependencies & Sequence Notes

No phase dependencies; Phase 2 runs alongside. Human setup is required first: the GCP project,
billing, the Identity Platform Google provider and OAuth clients for each platform, and an Apple
Developer account for TestFlight (RC-15). The scaffold must merge before any other Phase 1 Issue.
Changing the PA-5 time limit later is a config edit, not a code change. PR #62 bundles several
Issues because it was already written. From here on, every PR closes out one Issue (§5).

#### Relevant UI/UX Artifacts

Fig. 1 (architecture), Fig. 2 (flow from Welcome to Preparation, and the Account path), Fig. 3
(welcome and library), Fig. 4 (crisis preparation and opt-in), Fig. 10 (native layouts with bottom
tabs). Prototype states: sign-in failure, offline.

#### Candidate GitHub Issues

- Scaffold the Expo app with web, iOS and Android builds and CI
- Provision the GCP baseline in Terraform
- Sign students in and out with Google through the accounts service
- Verify identity at the gateway and the service, and lock Firestore to the signed-in owner
- Let students delete their account with confirmation and fail-closed cleanup
- Require owner approval before an account reaches the app, with an admin queue and an owner email
  (added 2026-10-31, PA-12: #72 to #76)
- Keep secrets server-side and clear the dependency audit findings
- Keep session content out of logs with a content-free logging helper
- Define the configuration for the three vetted scenarios, including per-scenario time limits
- Build the accessible primitives and Figma visual tokens
- Build the library and preparation screens with the crisis opt-in and offline check

### 3.2 Phase 2 — Provider & compliance spike

#### Goal

A speech provider is chosen on measured evidence. Zero-retention and no-training terms are
confirmed in writing for every hosted speech and model API in use. If a confirmation is missing,
real-student use stays blocked and the record says so. All session code reaches speech through a
replaceable interface.

#### Source Requirements / Design References

OQ-01, OQ-02 · RC-05, RC-06, RC-16 · DD-01, DD-04, DD-08, DD-09 · RISK-02 · PA-2, PA-3 ·
Architecture: speech APIs and Vertex AI persona and scoring inference (Fig. 1).

#### Deliverables

- A speech provider interface in the session service (speech-to-text and text-to-speech, or
  speech-to-speech) with a fake implementation for tests.
- Prototype adapters for OpenAI and Google Cloud Speech behind that interface.
- A benchmark harness that drives scripted synthetic turns and records round-trip latency, voice
  quality ratings and cost per 10-minute session.
- A provider decision record (ADR) covering latency p50/p95, quality, cost, availability and
  data-use terms, with the decision and the rejected option.
- A Vertex AI data-governance record listing models, region, zero-retention settings and
  abuse-monitoring logging status. The record points to where the written confirmations are kept.
  Signed vendor documents stay out of the repo.

#### Phase Acceptance Criteria

- The chosen provider meets p50 ≤ 2.0 s and p95 ≤ 3.5 s round-trip latency, measured over at least
  30 scripted synthetic turns (PA-2, RISK-02).
- Written zero-retention and no-training terms are on file for the chosen speech provider and each
  Vertex AI model. For any that are missing, the record marks real-student use as blocked (RC-05,
  PA-3).
- A contract test passes against both the fake and the chosen adapter. Swapping providers changes
  only adapter code (RC-16).
- Provider credentials load from Secret Manager and do not appear in the client bundle (RC-06).

#### Dependencies & Sequence Notes

The research can start on day one. The adapters plug into the Phase 1 service skeleton. Vendor
confirmations are external and slow, so request them at the start of the phase. Missing
confirmations do not block Phases 3–5 on synthetic data, but they do block release (§3.6). Voice
work in Phase 3 cannot start until the decision record merges.

#### Relevant UI/UX Artifacts

Fig. 1: speech API and Vertex AI boxes and the zero-retention note. This phase has no screens.

#### Candidate GitHub Issues

- Define the replaceable speech provider interface and its fake
- Benchmark OpenAI and Google speech for latency, quality and cost
- Obtain written zero-retention and no-training terms for speech and Vertex AI
- Configure Vertex AI for zero data retention and record the settings
- Record the speech provider decision as an ADR

### 3.3 Phase 3 — Practice session

#### Goal

A student runs a timed session against a vetted persona, by voice or by text. The student can end
the session, or the timer ends it. The complete transcript is handed off for grading. No live
scores appear, and no session content persists.

#### Source Requirements / Design References

US-03, US-04 · RC-03, RC-07, RC-10, RC-12, RC-13 · DD-01, DD-02, DD-08 · PA-3, PA-5 ·
Architecture: session service, Vertex AI persona inference, speech APIs, temporary conversation
state (dashed path, Fig. 1).

#### Deliverables

- Session endpoints for start, turn and end. The server enforces the time limit from scenario config,
  and session state lives only in memory, discarded on end or abandon.
- A persona prompt harness with three vetted persona prompts on Vertex AI. In the crisis persona, a
  disclosure is a turn and never a session end.
- A text session screen with a remaining-time display and an End session control.
- A voice check for connection and microphone readiness, and a voice session screen with text
  fallback always visible. If the microphone is denied, the student continues in text.
- A memory-only turn store on the client, which the Phase 4 recovery flows read.
- A completed-session handoff contract to the grading service (complete transcript plus completion
  status). The session service does no grading.

#### Phase Acceptance Criteria

- Either mode can start on a connected build. Text mode never requests the microphone. Voice mode
  does not start after the microphone is denied and offers text instead (US-03).
- The persona stays in scenario. The session ends on End session and at the configured limit, and
  the server rejects turns after either end condition (US-04).
- No score, hint or correction appears during a session (RC-10).
- After a session ends, neither Firestore nor the logs contain audio or transcript content, and the
  service holds no session state. Automated tests cover this (RC-03).
- Session start is blocked offline, and no screen claims offline support (RC-07).
- A text session can be completed with VoiceOver and TalkBack (RC-12).

#### Dependencies & Sequence Notes

The text path depends only on Phase 1. The voice path also needs the Phase 2 decision record. The
handoff contract must be fixed early because Phase 5 builds against it.

#### Relevant UI/UX Artifacts

Fig. 2 (format choice, voice check, end conditions), Fig. 5 (voice and text sessions), Fig. 10 (iOS
voice session). Prototype states: offline, microphone denied.

#### Candidate GitHub Issues

- Run sessions with a server-enforced time limit and transient state
- Drive the three vetted personas through a prompt harness on Vertex AI
- Build the text session screen with timer and End session
- Build the voice check and voice session with text fallback
- Hand completed transcripts to the grading service
- Prove no session content persists after a session ends

### 3.4 Phase 4 — Safety & recovery

#### Goal

Sessions fail safely and enforce conduct rules:

- A dropped voice session continues in text when the conversation is intact.
- Lost content or a conduct violation ends the attempt unscored.
- Crisis disclosures never end the crisis scenario.

The safeguards pass the labeled test set.

#### Source Requirements / Design References

US-05, US-06 · RC-08, RC-09, RC-19, RC-20 · DD-08 · RISK-04 · PA-10(b) · Architecture:
conduct safeguards in the session service (Fig. 1).

#### Deliverables

- Recovery flows. A voice interruption with the conversation intact continues the same session in
  text. Lost content ends the attempt unscored and offers a new text session from the beginning.
  Neither flow stores the partial session.
- A conduct safeguard in the session service with three rules:
  - Immediate termination for high-confidence targeted threats, slurs or sexual harassment.
  - One warning, then termination, for repeated demeaning language.
  - Further evaluation instead of automatic termination for quoted case material, nondirected
    frustration and low-confidence speech recognition.
- A synthetic labeled safeguard test set with must-terminate, must-warn and must-not-terminate
  cases. The must-not-terminate cases include crisis disclosures.
- Screens for the conduct warning, conduct ended, voice interrupted and conversation lost states.
  Each says whether the conversation is safe and whether a score was saved.

#### Phase Acceptance Criteria

The safeguard must pass every labeled case (US-06, RC-20, RC-19, PA-10(b)):

- Every must-terminate case ends the session without a score.
- Every repeated-demeaning case gets exactly one warning before termination.
- No must-not-terminate case causes an automatic termination.

Recovery and failure handling:

- With the conversation intact, a voice interruption continues the same session in text. Lost
  content ends the attempt unscored, creates no history entry and offers a new text session
  (US-05, RC-08).
- No failure or termination path sends a transcript to grading or writes a score (RC-09).

#### Dependencies & Sequence Notes

This phase depends on Phase 3: the session service, the turn store and the voice path. The
labeled test set can be written while Phase 3 is in progress. Passing it is a release gate, checked
in §3.6.

#### Relevant UI/UX Artifacts

Fig. 2 (four recovery branches), Fig. 9 (recovery, conduct and failure states). Prototype states:
voice interrupted, conversation lost, conduct warning, conduct ended.

#### Candidate GitHub Issues

- Continue a dropped voice session in text when the conversation is intact
- End lost-content attempts unscored and offer a fresh text session
- Enforce conduct rules with one warning and immediate termination
- Build the labeled conduct and crisis safeguard test set
- Keep crisis disclosures from ending the crisis scenario
- Build the recovery and conduct state screens

### 3.5 Phase 5 — Grading & report

#### Goal

A completed session produces a validated, evidence-linked developmental report. The student sees it
immediately and can export it to the device. The grader passes the calibration gate.

#### Source Requirements / Design References

US-07, US-08 · RC-03, RC-09, RC-10, RC-17, RC-18, RC-19, RC-21 · DD-02, DD-03, DD-07 · RISK-01,
RISK-03, RISK-05 · PA-4, PA-6, PA-10(a) · `docs/lab3/rubric-survey.md` · Architecture: grading
and report service, Vertex AI rubric scoring (Fig. 1).

#### Deliverables

- A rubric anchor spec. It gives behavioral anchors for each category at each 1-to-5 level, plus
  the developmental labels students see, the MI principles for the resistant-client scenario and the
  crisis critical-failure criteria. It cites free instruments only (PA-4).
- A grading service: a separate Cloud Run FastAPI service with its own Vertex AI rubric prompt. It
  accepts only complete transcripts. Code computes the overall score from the RC-17 weights; the
  model does not.
- Evidence validation. Every cited turn must exist in the transcript and support its claim. A failed
  check yields no score and the grading-failed state.
- The crisis safety override: a critical safety failure becomes the primary outcome, and the average
  is shown as a secondary measure.
- A synthetic calibration set with labels: strong, weak and harmful transcripts per category and
  scenario, plus crisis critical-failure cases. A calibration runner reports agreement with the
  labels.
- Report screens for the standard and crisis reports. They include the developmental disclaimer and
  the 988 Lifeline on the crisis report, with the score-ring percent sign fixed (RISK-05).
- On-device PDF export on web, iOS and Android, and a leave-report confirmation that offers export
  first.

#### Phase Acceptance Criteria

- On the calibration set, every category is within ±1 level of its label on at least 90% of
  transcripts, and every crisis critical-failure case triggers the override (PA-10(a)).
- Every report has an overall score, six 1-to-5 ratings, strengths and improvements. A unit test
  shows that the overall score equals the RC-17 weighted formula (US-07, RC-17).
- Every cited example maps to an existing transcript turn. A report that fails validation shows the
  grading-failed state and saves nothing (RC-18, RISK-01).
- The grader rejects incomplete or failed transcripts (RC-09).
- The exported PDF matches the displayed report, and exporting sends no narrative to the server
  (US-08, RC-03, PA-6).
- No resistant-client report calls anything an MITI score (RC-18).

#### Dependencies & Sequence Notes

This chain is the longest path to release. The anchor spec and calibration set are documents and
data, so they start on day one in the critical-path lane (§4). The grader code starts once the
Phase 1 service skeleton merges. The calibration labels come from the anchor spec, never from
grader output. Wiring the grader into live
sessions needs the Phase 3 handoff contract. Phase 5 writes no scores; Phase 6 persists them.

#### Relevant UI/UX Artifacts

Fig. 6 (feedback report), Fig. 7 (crisis report with safety override), Fig. 8 left (leave-report
confirmation), Fig. 10 (Android crisis report). Prototype state: grading failed.

#### Candidate GitHub Issues

- Write the rubric anchor specification from free instruments
- Build the synthetic calibration set and calibration runner
- Grade completed transcripts with fixed weights and the crisis override
- Reject reports whose cited evidence is not in the transcript
- Build the feedback and crisis report screens
- Export the report as a PDF on the device
- Confirm before leaving an unexported report

### 3.6 Phase 6 — History & release

#### Goal

Completed sessions save only scores, and a student sees only their own history. Every release gate
is met before a real student uses the MVP on web, Android or iOS (TestFlight). Account deletion
already ships in Phase 1 (PA-11); this phase makes sure it also covers the scores.

#### Source Requirements / Design References

US-09 · RC-02, RC-03, RC-04, RC-05, RC-11, RC-12, RC-14, RC-15 · DD-03, DD-05 · RISK-05 ·
PA-3, PA-10, PA-11 · Architecture: Firestore (Fig. 1).

#### Deliverables

- A Firestore score record with the overall score and six category scores, stored under the
  student's collection from Phase 1. Any other field must be justified against RC-04 in the schema
  Issue.
- A server-side score write that happens only from a validated report. Clients still cannot write.
  In the same transaction, the writer checks the Phase 1 deletion marker, so a deleted account
  never gains a new score.
- A score history screen with the empty state fixed (RISK-05).
- An accessibility audit and fixes: WCAG 2.2 AA on web, plus VoiceOver and TalkBack walkthroughs.
- A platform parity check on web, iOS and Android.
- A separate production GCP project in Terraform, with its own credentials and the same
  zero-retention, rules and logging settings as development (`docs/ARCHITECTURE.md` AD-5, #77).
- A release gate checklist and release builds: web, Android and an iOS TestFlight build. Every
  deploy needs a human's approval, and no agent triggers one (AG-9).

#### Phase Acceptance Criteria

- A student sees only their own scores. The Phase 1 rules tests still pass with the score record
  in place (US-09, RC-02).
- Firestore and the history screen hold no audio, transcript, excerpt or narrative content (RC-03).
- An unscored or failed attempt creates no history entry (RC-09).
- Deletion cleanup removes saved scores, and a score write after the deletion marker is rejected
  (RC-04).
- The core flow has no open WCAG 2.2 AA failures and passes VoiceOver and TalkBack walkthroughs
  (RC-11, RC-12).
- The core session, feedback, export and history flow works the same on all three builds. iOS ships
  only through TestFlight or internal distribution (RC-14, RC-15).
- Every release gate is met: PA-3 written confirmations, PA-10 calibration and safeguard passes, a
  provisioned production project that shares no credentials with development (AD-5), and a clean
  secrets scan (RC-05, RC-06).

#### Dependencies & Sequence Notes

Release depends on Phases 4 and 5. The score schema can start right after Phase 1, because the
rules already exist. Each phase should run its own accessibility checks; Phase 6 is the final audit,
not the first one. The release gate review comes last.

#### Relevant UI/UX Artifacts

Fig. 8 right (score history), Fig. 10 (native layouts). Prototype state: empty score history.

#### Candidate GitHub Issues

- Save scores-only records from validated reports, honoring the deletion marker
- Build the score history screen with a correct empty state
- Audit and fix accessibility (WCAG 2.2 AA, VoiceOver, TalkBack)
- Verify Figma visual fidelity and cross-screen navigation
- Verify cross-platform parity and produce the release builds
- Provision the production GCP project for real-student use (added 2026-10-31, AD-5: #77)
- Review the release gates before real student use

## 4 Cross-Phase Dependencies & Implementation Sequence

### Critical path

The longest chain runs through grading. It starts with the anchor spec, then the labeled
calibration set and the grader. Evidence validation and the calibration pass follow. Then come
live integration with the Phase 3 handoff, the score write and the release gate review. Phase 1
foundations are on every path, but they are short. The provider spike and the session and safety
work (Phases 2–4) form a second, shorter chain that joins at release. A slip in the anchor spec or
calibration set moves the release date. A slip elsewhere usually does not.

One dependency sits outside the code. Written zero-retention and no-training confirmations from
vendors (PA-3) are slow and nobody on the project controls them. They are requested on day one.
They block release only, never development on synthetic data.

### Shared prerequisites

Many later Issues build on these. Each one merges before its consumers start:

- **Expo scaffold and CI.** Every client Issue builds on it.
- **Terraform GCP baseline and the accounts service behind API Gateway, with Secret Manager.**
  Every server Issue and every credential depends on it. The accounts service sets the
  identity-check pattern that the session and grading services copy.
- **Content-free logging helper.** It must exist before any endpoint handles session content
  (RC-03, RC-06).
- **Scenario configuration.** The preparation screens, the session timer, the personas and the
  safeguard test set all read it.
- **Contracts used across phases:**
  - the speech provider interface and its fake (Phase 2 → 3);
  - the completed-session handoff (Phase 3 → 5);
  - the report schema (Phase 5 grader → report screens and export);
  - the Firestore rules and the deletion marker (Phase 1), which the Phase 6 score write must
    honor.

### Parallel opportunities

Work runs in **two lanes** (Sequencing rule 1):

- **Lane 1, the critical path.** On day one it starts the anchor spec and then the calibration set.
  Grader code follows once the service skeleton merges.
- **Lane 2, everything else, in phase order.** It starts with the Phase 1 foundations and the Phase 2
  spike, then moves through the Phase 3, Phase 4 and Phase 6 Issues.

Inside lane 2, these Issues are independent of each other and can be taken in any order:

- the Phase 2 benchmark and the Phase 1 screens;
- the text session and the provider ADR;
- the safeguard test set and the Phase 3 UI;
- the score schema and any Phase 3 or 4 work.

### Sequencing rules for implementation agents

1. **Two lanes.** At most two implementation Issues are In Progress at once: one on the critical
   path and one off it. Waiting on vendors does not count against the limit (PA-1).
2. **Scaffold first.** The Expo scaffold merges before any other Phase 1 Issue. The Terraform
   baseline and the gateway pattern from the accounts service merge before any other server Issue.
3. **Contract before consumer.** A consumer starts only after its contract (listed above) is
   merged. Until the real producer exists, it builds against a fake.
4. **Voice waits for the decision record.** Voice session work starts only after the provider ADR
   merges. The text path does not wait (PA-2).
5. **Labels before the grader.** The calibration labels come from the anchor spec before the
   grader is tuned. They are never adjusted to match grader output (PA-10).
6. **Safeguard tests come first.** The labeled safeguard test set merges before the conduct
   safeguard implementation, and the implementation must pass every case (PA-10(b)).
7. **No score before validation.** Nothing writes a score until evidence validation and the
   score rules are both merged (RC-09, RC-18).
8. **Synthetic data until the gates.** No real student session runs until the release gate
   review passes (PA-3, PA-10).
9. **Accessibility in every phase.** Each UI Issue meets its own accessibility checks. The Phase 6
   audit is the final check, not the first one (RC-11, RC-12).

### 4.1 Dependency / Sequence Table

| Item / Capability | Must Follow | Reason | Can Run in Parallel With |
|---|---|---|---|
| Expo scaffold + CI | Human GCP/OAuth/Apple setup | Every client Issue builds on it | Anchor spec; provider research |
| Service skeleton: Terraform baseline + accounts service (Gateway, Secret Manager) | Scaffold CI; human GCP setup | Every server Issue and credential depends on it; in PR #62 | Anchor spec; calibration set |
| Content-free logging helper | Service skeleton | Must exist before any endpoint handles session content (RC-03, RC-06) | Sign-in; scenario config |
| Google sign-in + unauthenticated rejection | Service skeleton | Library and every API are auth-gated (RC-01, RC-02) | Scenario config; speech interface |
| Firestore owner rules | Sign-in | Owner-only reads and no client writes; the score write builds on them (RC-02) | Scenario config |
| Account deletion (denial marker + cleanup) | Sign-in; Firestore rules | Access fails closed at once; data gone within 30 days (RC-04) | Library + preparation screens |
| Access approval gate (#72) | Firestore rules; account deletion | Every protected API and rule checks approval; the access record is deleted with the account (PA-12) | Scenario config; logging helper |
| Admin decisions (#73) → admin queue screen (#76) | Access gate | Only the server-configured admin decides (PA-12) | Owner email; access-state screens |
| Owner email (#74) | Access gate; OD-3 | New data processor needs the owner's choice first (AG-3) | Admin decisions |
| Access-state screens (#75) | Access gate; shared presentation | The library mounts only after approval | Admin queue screen |
| Scenario configuration | Service skeleton | Prep screens, timer, personas and safeguard tests read it (PA-5) | Sign-in; logging helper |
| Library + preparation screens | Sign-in; access-state screens; scenario config | Screens need auth, approval and real config | Provider benchmark |
| Speech interface + fake | Service skeleton | Adapters and voice code target the interface (RC-16) | Phase 1 screens |
| Provider benchmark → ADR | Speech interface | Latency gate decides the provider (PA-2) | Text session; persona harness |
| Vendor zero-retention confirmations | Nothing — request day one | External and slow; release gate (PA-3) | Everything |
| Vertex AI zero-retention config | GCP project | Persona and grader inference run on the configured project | Phase 1 work |
| Session endpoints (timer, transient state) | Logging helper; scenario config; auth; OD-1 (resolved: ARCHITECTURE AD-1) | Server-enforced limit and no persistence (US-04, RC-03) | Calibration set |
| Persona prompt harness | Session endpoints; Vertex config | Personas run inside the session service | Text session screen |
| Text session screen | Session endpoints; prep screens | Text is the baseline and the fallback (DD-08) | Persona harness; provider ADR |
| Voice check + voice session | Provider ADR; text session screen | Voice needs the chosen provider and a working text fallback | Handoff contract |
| Completed-session handoff contract | Session endpoints | Phase 5 integration builds against it | Persona harness; voice session |
| No-persistence proof | Text and voice sessions | Proves RC-03 across both modes | Safeguard test set |
| Labeled safeguard test set | Scenario config | Tests come before the safeguard (PA-10(b)) | Phase 3 UI |
| Conduct safeguard + crisis non-termination | Safeguard test set; session endpoints | Must pass every labeled case (RC-19, RC-20) | Recovery flows |
| Recovery flows (voice→text, lost content) | Voice session; client turn store | Recovery reads the turn store (US-05, RC-08) | Conduct safeguard |
| Recovery + conduct state screens | Recovery flows; conduct safeguard | Screens report states those flows produce | Report screens |
| Rubric anchor spec | Nothing — documentation | Head of the critical path (PA-4) | All Phase 1 and 2 work |
| Calibration set + runner | Anchor spec (labels); grader (runner execution) | Labels must come from anchors, not grader output (PA-10(a)) | Phase 1 and 3 work |
| Grader (weights + crisis override) | Service skeleton; anchor spec | Scores against the anchors; code computes the weights (RC-17, RC-19) | Phase 3 session work |
| Evidence validation | Grader | Reports whose evidence fails validation are blocked (RC-18) | Report screens on a fake report |
| Feedback + crisis report screens | Report schema | Built against a fake report until the grader is live | Evidence validation |
| On-device PDF export + leave confirmation | Report screens | Export must match the displayed report (US-08, PA-6) | Score history screen |
| Live grading integration | Handoff contract; evidence validation | Real transcripts reach a validated grader only | Phase 4 work |
| Score record schema | Firestore owner rules; report schema | Holds only RC-04 fields under the owner's collection | Phase 3 and 4 work |
| Save scores only from validated reports | Evidence validation; score record; deletion marker | No score before validation (RC-09); no score after deletion (RC-04) | History screen |
| Score history screen | Score record | Reads only the student's own scores | PDF export |
| Accessibility audit | All Phase 3–6 UI | Final check across the core flow (RC-11, RC-12) | Parity check prep |
| Parity check + release builds | Accessibility audit; all features | Same core flow on all three builds (RC-14, RC-15) | Release gate checklist drafting |
| Production GCP project (#77) | Terraform baseline; Vertex zero-retention config | Real student data never shares a project or credentials with test data (AD-5) | Phases 3–6 work |
| Release gate review | Everything above, incl. vendor confirmations and the production project | Last step before real student use (PA-3, PA-10) | Nothing |

## 5 GitHub Issue Decomposition Guidance

Project #1 already holds 10 epics and 40 child Issues, written from the SDD before Lab 3. Some of
them already have branches, PR #62 and progress comments. The owner chose to **reconcile them in
place** (2026-10-30). Existing Issues keep their numbers and history. The ones that contradict
this plan are rewritten, and new Issues fill only the gaps. Nothing is duplicated.

### Sizing rules

1. **One Issue, one PR.** Each Issue should close in a single PR into `dev` that a reviewer can
   check in one sitting: roughly 400 changed lines or fewer, not counting lockfiles and generated
   files. PR #62 (80 files, 8 Issues) is the exception that set this rule (PA-11).
2. **One phase per Issue.** An Issue that crosses a phase boundary is split there. For example,
   scenario configuration is Phase 1 and persona prompts are Phase 3.
3. **Contracts are their own Issues.** The speech interface, the session handoff, the report
   contract and the score record each get an Issue that merges before any consumer (§4 rule 3).
4. **Test sets come before implementations.** Calibration labels and safeguard cases are separate
   Issues that merge first (§4 rules 5 and 6).
5. **Decisions are Issues too.** Spikes, vendor terms and the release gate review each end in a
   recorded decision. While an Issue waits on a vendor, it keeps its status, and a comment names
   the blocker (Project workflow §2).
6. **Epics only group work.** Code lands against child Issues. An epic tracks progress through its
   sub-issues.

### What an agent-ready Issue contains

The body extends the project `CLAUDE.md` structure. Board fields (Status, Plan Phase, Stage,
Priority, Area, Sequence, Human Review, Review Depth) live on the Project, not in the body (§7).

| Section | Contents |
|---|---|
| Title | One outcome, verb first, in user or system terms ("Reject reports whose cited evidence is not in the transcript") |
| `## Description` | What and why. The plan phase and the SDD IDs it satisfies (US, RC, DD), plus the plan IDs that constrain it (PA, CD, OD, AG) |
| `## Implementation Requirements` | Checkable bullets: the constraints, the files and directories it touches, the contracts it consumes or produces |
| `## Acceptance Criteria` | `- [ ]` items, each tied to a named test or demo, drawn from the phase acceptance criteria in §3 |
| `## Visual Context` | UI Issues only: SDD figure, prototype state and the Figma node from the #57 inventory. Backend Issues cite Fig. 1 |
| `## Dependencies` | `Blocked by #n` for each §4.1 predecessor and any open decision (OD-1, OD-2) |
| `## Non-goals` | What is out of scope, and which Issue owns it instead |
| `## Testing` | The test levels expected (unit, emulator, integration, e2e), synthetic data only, and the labeled set it must pass where one applies |
| `## Guardrails` | The §6.4 AG numbers that apply |

### Review depth

Every implementation PR is merged by a human (AG-9). Two Project fields carry review (§7).
**Human Review** records whether the owner has checked the Issue itself (Pending → Reviewed).
**Review Depth** tells the owner how deep to look:

| Level | Applies to | Owner does |
|---|---|---|
| Owner decision | ADRs, vendor terms, the anchor spec, calibration labels, the release gate review | Makes or approves the decision the Issue records |
| Deep review | Auth, Firestore rules, deletion, privacy, secrets, infrastructure, safeguards, grading | Reads the whole diff and runs or inspects the evidence |
| Standard review | Screens, shared UI, docs, tooling | Checks acceptance-criteria evidence and skims the diff |

### 5.1 Issue Map

Plan phase → GitHub Issue. Every row is a real Issue on Project #1. The new ones are #63–#70,
created 2026-10-30. **Change** is the reconciliation action: _keep_, _rewrite_ (the body
contradicted this plan), _re-phase_ (its plan phase or sequence moved), _new_ or _close_. The
board fields for each change, and the NEW-n IDs used while it was proposed, are in
`docs/lab3/backlog-proposal.md`.

| ID | Issue Title | Phase | SDD Sources | Depends On | Change | Notes / Visual Context |
|---|---|---|---|---|---|---|
| #17 | Scaffold React Native project with web, iOS, and Android builds | 1 | DD-06, RC-14, PA-7 | Human setup | keep | Draft PR #71 (`feature/17-cross-platform-scaffold`); overlaps PR #62 in `apps/student`, so the two must be reconciled. Fig. 10 |
| #51 | Set up CI/CD pipeline with automated checks and approved deploys | 1 | RC-06, AG-9 | #17 | keep | Deploys are automated but approved by a human, which matches AG-9 |
| #18 | Provision Google Cloud baseline for MVP services | 1 | DD-09, RC-06 | Human setup | keep | In Progress, PR #62 (`infra/`). Fig. 1 |
| #23 | Keep secrets server-side and enforce encrypted transport | 1 | RC-06 | #18, #51 | keep | Owns the client-bundle secret scan |
| #61 | Resolve remaining student app dependency audit findings | 1 | RC-06 | #17 | keep | Bug; must be fixed before PR #62 merges |
| #25 | Google Sign-In with Identity Platform and sign-out | 1 | US-01, RC-01, RC-06 | #17, #18 | keep | In Progress, PR #62; needs real OAuth clients. Fig. 3; state: sign-in failure |
| #26 | Verify identity tokens at API Gateway and scope data to the signed-in student | 1 | RC-02 | #25 | keep | Agent Review, PR #62; includes the Firestore owner rules |
| #46 | Account deletion request with confirmation | 1 | RC-04 | #26 | re-phase | In Progress, PR #62. Moved from Phase 6 (PA-11). Fig. 2 Account path |
| #72 | Require owner approval before a signed-in account reaches the app | 1 | RC-01, RC-02, RC-04, PA-12 | #26, #46 | new | Added 2026-10-31 (POLICY). Access record, guard and Firestore rule check. Fig. 1 |
| #73 | Let the admin list and decide access requests with an audit record | 1 | RC-02, RC-06, PA-12 | #72 | new | Admin set server-side; versioned decisions |
| #74 | Email the owner once for each new access request | 1 | RC-06, PA-12, AG-3 | #72, **OD-3** | new | New data processor; name and email only |
| #75 | Show students their access state and let them request access | 1 | US-01, RC-02, RC-11, PA-12 | #72, #58 | new | Blocks #28. No SDD figure; Fig. 2 flow |
| #76 | Build the admin access-request queue screen | 1 | RC-02, RC-11, PA-12 | #73, #58 | new | The only admin surface (POLICY §1) |
| #63 | Keep session content out of logs with a content-free logging helper | 1 | RC-03, RC-06 | #18 | new | Must merge before any session endpoint. #39 proves the whole flow later |
| #27 | Define the three vetted scenario configurations with time limits and release flags | 1 | RC-22, DD-07, PA-5, CD-3 | #18 | rewrite | Persona prompts move to #67. Adds the CD-3 release flag; time limit fixed at 10 min |
| #22 | Confirm session time limit for each scenario | — | OQ-04 | — | close | Settled by CD-4 (10 min, set in config) |
| #24 | Accessible component baseline for web and native | 1 | RC-11, RC-12 | #17 | keep | Primitives every screen uses |
| #57 | Record approved Figma reference and screen-state-route inventory | 1 | RISK-05, PA-8 | — | keep | Source of the Figma nodes cited in Visual Context |
| #58 | Implement Figma visual tokens, assets, and shared presentation components | 1 | PA-8 | #24, #57 | keep | |
| #28 | Scenario library screen | 1 | US-02, RC-22 | #25, #27, #58, #75 | keep | Hides scenarios whose release flag is off. Fig. 3 |
| #29 | Preparation screen with crisis opt-in and connectivity gate | 1 | US-02, RC-07, RC-13 | #28 | keep | Fig. 4; state: offline |
| #30 | State the educational boundary across the product | 1 | RC-21 | #28 | keep | The report disclaimer lands with #38. Figs. 3, 4, 6 |
| #19 | Verify zero-retention and no-training terms for AI and speech providers | 2 | RC-05, OQ-02, DD-04 | — (day one) | keep | Waits on vendors and blocks only the release. Feeds CD-1 and CD-2 |
| #64 | Define the replaceable speech provider interface and its fake | 2 | RC-16, DD-09 | #18 | new | Contract for #20 and #43; includes the contract test |
| #20 | Benchmark OpenAI and Google speech and record the provider ADR | 2 | OQ-01, RISK-02, PA-2 | #64; #19 only at the release gate (no link) | rewrite | The latency target is already set (PA-2). Measures from a device and web client (IR-3). Interface work moves to #64 |
| #65 | Configure Vertex AI for zero data retention and record the governance settings | 2 | RC-05, DD-04, OD-2 | #18; #19 for terms status only (no link) | new | Settles OD-2 (which models). Signed vendor documents stay out of the repo |
| #66 | Define the completed-session handoff contract | 3 | RC-09, RC-10, DD-02 | #63 | new | Phase 5 builds against it (§4 rule 3) |
| #31 | Session service for lifecycle, persona turns, and time limits | 3 | US-04, RC-03, RC-09, RC-10 | #63, #66, #26, #27, **OD-1** | keep | Went back to Backlog for OD-1. OD-1 was resolved on 2026-10-31 (ARCHITECTURE AD-1: signed, client-held state), so only its Issue blockers remain |
| #67 | Drive the three vetted personas through a prompt harness on Vertex AI | 3 | US-04, RC-19, DD-07 | #31, #65 | new | Split from #27. A crisis disclosure is a turn, never a session end |
| #32 | Text conversation screen with timer and End session | 3 | US-03, US-04, RC-10, RC-12 | #29, #31 | keep | Holds the memory-only client turn store. Fig. 5 |
| #43 | Voice mode with voice check and visible text fallback | 3 | US-03, DD-08 | #20 (ADR), #32 | keep | Stays in Backlog until the ADR merges (§4 rule 4). Fig. 5, 10; state: microphone denied |
| #39 | Enforce session-data minimization across storage, logs, analytics, and crash reports | 3 | RC-03, DD-03 | #32, #43 | re-phase | End-to-end no-persistence proof. Adds no crash-reporting SDK (AG-3) |
| #48 | Build the labeled conduct and crisis safeguard test set | 4 | RC-19, RC-20, RISK-04, PA-10(b) | #27 | rewrite | Every case must pass, with no rate thresholds. Adds crisis must-not-terminate cases. Merges before #33 |
| #33 | Conduct safeguards with one warning and termination without a score | 4 | US-06, RC-20 | #48, #31 | keep | Fig. 9; states: conduct warning, conduct ended |
| #34 | Crisis scenario in-session risk handling and post-session resources | 4 | RC-19 | #48, #67 | keep | The 988 Lifeline on the report lands with #38 |
| #44 | Recover from voice and transcription failures without scoring partial attempts | 4 | US-05, RC-08, RC-09 | #43 | keep | Includes the IR-2 state-loss test. Fig. 9; states: voice interrupted, conversation lost |
| #21 | Write the rubric anchor specification from free instruments | 5 | RC-17, RC-18, OQ-03, PA-4 | — (day one) | rewrite | Faculty review removed (PA-10). Head of the critical path |
| #47 | Build the labeled calibration set and calibration runner | 5 | RISK-01, PA-10(a), CD-5 | #21; #65; #35 to run | rewrite | Replaces the faculty-rating study. Lane 1, right after #21 |
| #59 | Define versioned report contract and synthetic fixtures for independent UI development | 5 | US-07, RC-17 | — | keep | Contract for #35, #38, #40, #41 and #42 |
| #35 | Grade completed transcripts with fixed weights against the anchor specification | 5 | US-07, RC-09, RC-17 | #21, #59, #65, #18 | rewrite | Faculty-review and #47 faculty-gate references removed |
| #37 | Crisis safety override in grading | 5 | RC-19, US-07 | #35 | keep | Every crisis critical-failure case in #47 must trigger it |
| #36 | Validate that every feedback example is grounded in the transcript | 5 | RC-18, RISK-01 | #35 | keep | State: grading failed |
| #38 | Feedback report screen for standard and crisis outcomes | 5 | US-07, RC-19, RC-21 | #59, #58 | keep | Figs. 6, 7, 10; score-ring percent sign fixed (RISK-05) |
| #42 | Export the feedback report to the device and confirm before leaving | 5 | US-08, RC-03, PA-6 | #38 | keep | On-device PDF on all three platforms (IR-4). Fig. 8 left |
| #68 | Send completed live sessions to the validated grader | 5 | RC-09, RC-10 | #66, #31, #36, #37 | new | Critical path. Only a complete transcript reaches the grader |
| #40 | Persist scores-only records for completed sessions | 6 | US-09, RC-04, RC-09 | #36, #68, #26, #46 | keep | Server write checks the deletion marker in the same transaction. Adds completion time and crisis safety result (POLICY REP-4, REP-5) |
| #41 | Score history screen | 6 | US-09, RISK-05 | #40, #58 | keep | Fig. 8 right; empty state fixed. Safety result first, newest first, no date (POLICY REP-4, REP-5) |
| #45 | Verify the core flow with VoiceOver, TalkBack, and keyboard-only web | 6 | RC-11, RC-12 | All Phase 3–6 UI | keep | Final audit (§4 rule 9) |
| #60 | Verify Figma visual fidelity and cross-screen navigation | 6 | RISK-05, PA-8 | All UI | keep | |
| #69 | Verify cross-platform parity and produce the web and Android release builds | 6 | RC-14 | #45 | new | Covers export parity (IR-4) |
| #50 | iOS distribution through TestFlight or internal builds | 6 | RC-15, DD-05 | #69 | keep | In Progress: Mac handoff in PR #62 |
| #77 | Provision the production GCP project for real-student use | 6 | AD-5, RC-05, RC-06, DD-09 | #18, #65 | new | Added 2026-10-31 (ROADMAP cross-check). Separate credentials; owner applies (AG-9) |
| #70 | Review the release gates before real-student use | 6 | RC-05, RC-06, PA-3, PA-10 | Everything above, incl. #19, #72–#76 and #77 | new | The owner runs it and invokes the CD rules |
| #49 | Faculty review of the crisis-risk scenario before release | — | RISK-03 | — | close | Superseded by PA-10: #47 crisis cases, #48 crisis cases and #70 |

Totals across the 40 existing child Issues and the new ones: 8 new, 6 rewritten, 2 re-phased,
2 closed and 30 kept. The POLICY interview (2026-10-31) added five more new Issues, #72 to #76
(PA-12), and policy sections to #38, #40 and #41. The ROADMAP cross-check the same day added #77
for the AD-5 production project. The epics (#4, #5, #6, #11–#16,
#56) stay as parents, and each new Issue joins the epic named in the backlog proposal.

## 6 Risks, Open Decisions & Agent Guardrails

This section adds to the SDD rather than repeating it. SDD RISK-01 to RISK-06 still apply. Below
are the risks this plan's own choices create, the contingency rules decided ahead of time, the
decisions still open and the limits an implementation agent must respect. `docs/POLICY.md` will
expand the guardrails into the full agent policy.

### 6.1 Implementation risks

| ID | Risk | Mitigation in this plan |
|---|---|---|
| IR-1 | **The grader check could test itself.** Without faculty review, one author's blind spots could shape the anchors, the labels and the grader alike. A pass would then show consistency, not validity. | A model family different from the grader's drafts the calibration transcripts. The owner approves every label, and labels are frozen before grader work starts (CD-5, §4 rule 5). |
| IR-2 | **In-memory session state on Cloud Run can vanish.** A restart, a scale-in, or a turn routed to another instance loses the conversation. | Settled by OD-1 → `docs/ARCHITECTURE.md` AD-1: the app holds the conversation with a server signature, so no instance owns it. A lost or rejected state takes the Phase 4 lost-content path, and a test simulates it. No external session store is added (AG-2). |
| IR-3 | **Real-time audio in Expo** may need a development build with native modules, and web audio behaves differently. A server-only benchmark would hide client latency. | The Phase 2 benchmark measures from a development-build client on a device and on web. |
| IR-4 | **On-device PDFs differ by platform.** Fonts, page breaks and the share flow vary across web, iOS and Android. | Export is built early in Phase 5 against a fake report. The Phase 6 parity check covers export. |
| IR-5 | **Content can leak indirectly.** The likely paths in this stack are request-body logging at the gateway or Cloud Run, error messages that echo a turn, client console logs and exception reports. RC-03 forbids all of these. | Request-body logging stays off. The logging-helper tests cover error paths. No telemetry or crash-reporting SDK is added without an owner decision (AG-3). |
| IR-6 | **Review becomes the bottleneck.** Agents can open PRs faster than one reviewer can check them. | Two-lane WIP limit (§4 rule 1) and small Issues (§5). |

### 6.2 Contingency rules (decided 2026-10-30)

| ID | Trigger | Rule |
|---|---|---|
| CD-1 | Written speech-vendor terms are missing at the release gate | Swap to the alternate provider through the RC-16 interface, if its written terms are on file and it meets the PA-2 latency target. If it fails either check, hold the release. Only the owner may then accept a latency miss, as a recorded exception. A terms gap is never accepted (RC-05). |
| CD-2 | Written Vertex AI terms are missing at the release gate | Hold the release. Personas and grading both run on Vertex AI, so there is nothing to swap (OQ-02). |
| CD-3 | The grader still fails the PA-10(a) gate after tuning | Spend one week tuning the anchor wording and the grader prompt. Labels never change. Then release only the scenarios that pass, with the failing ones flagged off in config. The 100% crisis-override rule is never relaxed. RC-22 allows a subset; this is a recorded exception to DD-07's "exactly three". |
| CD-4 | Session time limit (PA-5, OQ-04) | 10 minutes for all three scenarios, set in config. |
| CD-5 | Who labels the calibration set (PA-10) | A model family different from the grader's drafts each transcript to a target label from the anchor spec. The owner approves every label before grader work starts. |

An agent that sees a trigger reports it on the Issue and stops. The owner invokes the rule.

### 6.3 Open decisions

No agent may guess these. The Issues that depend on them stay blocked until the owner decides.

| ID | Decision | Decide by | Blocks |
|---|---|---|---|
| OD-1 | **Resolved 2026-10-31 (`docs/ARCHITECTURE.md` AD-1, AD-2).** The app holds the conversation and the session service signs it, so the services stay stateless. Rewind of a signed state is an accepted MVP risk. | Decided in the ARCHITECTURE.md interview | Nothing (it blocked the Phase 3 session endpoints) |
| OD-2 | Which Vertex AI models run the personas and the grader, and so which family drafts the calibration set | Phase 2 data-governance record | Persona harness, grader, calibration set drafting |
| OD-3 | Which email provider sends the owner's access-request emails, with its data-use record (it receives only the requester's name and Google email; AG-3) | Before #74 starts | #74 owner notification email |

### 6.4 Agent guardrails

1. **Requirements win.** If an Issue conflicts with an RC, a PA or an SDD non-goal, stop and ask.
   Never settle the conflict in code.
2. **No session content at rest.** Audio, transcripts, excerpts and narrative feedback never go to
   Firestore, logs, analytics, crash reports, caches, an external session store or test fixtures.
   All test data is synthetic (RC-03, PA-3).
3. **No new data processors.** Adding a third-party service, SDK or model API takes an owner
   decision and a zero-retention record first (RC-05). This includes telemetry and crash reporting.
4. **Grading integrity.** Code computes the overall score from the fixed RC-17 weights. Never change
   the weights or the crisis override. Never edit calibration labels or safeguard test cases to
   make a test pass.
5. **Licensed instruments.** Never reproduce CCS-R or MITI manual text, and never label a score as
   an MITI score (PA-4, RC-18).
6. **Fixed product scope.** Google sign-in only. No live scores or hints during a session. No
   scenario, persona or rubric editing. No instructor features (RC-01, RC-10, RC-22, SDD §2.3).
7. **Security defaults.** Secrets come only from Secret Manager, and none reach the client. Every
   endpoint checks the caller's identity at the gateway and again in the service (RC-02, RC-06).
8. **Prototype is a reference.** Build from the figures and states. Never copy Figma Make markup
   (PA-8).
9. **Humans own releases.** No deploys, no merges to `staging` or `main` and no real-student
   enablement. The owner runs the release gate review and invokes the CD rules.

## 7 Handoff to GitHub Project

The backlog lives on [Project #1](https://github.com/users/sandythomas1/projects/1): 10 epics,
46 child Issues and 90 dependency links, organized on 2026-10-31. The POLICY interview later that
day added 5 child Issues (#72 to #76, Human Review Pending) and 14 links, for 51 and 104. The
ROADMAP cross-check added #77 (production project) and 3 links, for 52 and 107, and moved four
pre-Lab 3 Sequence values into phase order (#43, #39, #44, #42). The final consistency pass
the same day brought 11 Issue bodies in line with PA-6, PA-10 and PA-12 (#4, #16, #25, #34, #38,
#42, #56 to #60), with a comment on each; no Status or link changed. From that date, **GitHub Issues
and Project #1 are the authoritative source for detailed work**: what an Issue requires, its
status, sequence, dependencies and review state. This plan stays the higher-level explanation of
why the work is phased and ordered as it is. If an Issue and this plan disagree, the agent stops
and asks (AG-1). The owner then fixes the Issue for a task detail, or this plan for phase intent.

### How the plan maps to the Project

| Plan concept | Project field or feature | Values |
|---|---|---|
| Plan phase (§2) | **Plan Phase** | 1 Foundation & access · 2 Provider & compliance spike · 3 Practice session · 4 Safety & recovery · 5 Grading & report · 6 History & release. Epics have none, because they span phases |
| SDLC activity | **Stage** (named "Phase" until 2026-10-31; renamed so it can't be confused with Plan Phase) | Planning, Design, Implementation, Testing, Deployment |
| Order (§4.1) | **Sequence** | Board order. Decimals slot new work between existing Issues |
| Dependencies (§4.1, §5.1 "Depends On") | Native **blocked by** links | 107 links (90 at handoff, then 14 for #72 to #76 and 3 for #77). #19 (vendor terms) is linked only to #70, because terms block the release, not development (§4) |
| Open decisions (§6.3) | Status stays Backlog, with a comment naming the OD | #31 waited on OD-1 until 2026-10-31 |
| Review state | **Human Review** | Pending → Reviewed |
| Review depth (§5) | **Review Depth** | Owner decision · Deep review · Standard review |
| Epics (§5 sizing rule 6) | Parent issue and **Sub-issues progress** | #4, #5, #6, #11–#16, #56 |
| Ownership and kind of work | **Priority**, **Area** | Unchanged from the backlog proposal |
| Two lanes (§4 rule 1) | Count of child Issues In Progress | At most one critical-path and one off-path Issue |

### Status rules

- **Backlog:** a blocker is still open, meaning a blocked-by Issue is neither merged nor in an open
  PR, or an open decision applies.
- **Ready:** every blocker is merged or in an open PR, and no open decision applies. On
  2026-10-31 that was 10 child Issues: #19, #21, #24, #27, #51, #57, #59, #63, #64 and #65.
  Twenty-one child Issues and three epics moved from Ready to Backlog. #72 joined them later that
  day, after the POLICY interview, for 11.
- **In Progress onward:** as in the project `CLAUDE.md`. The seven Issues in PR #62 (#17, #18, #25,
  #26, #46, #50, #61) kept their status.
- **Epics** follow their children. An epic is In Progress if any child is in flight, Ready if any
  child is Ready, and Backlog otherwise.
- **Promotion:** when a blocker merges, the next agent session moves the Issues it unblocked from
  Backlog to Ready and posts a comment saying which merge unblocked them.

### Human Review gate

1. Every open epic and child Issue starts at **Pending**: 56 items on 2026-10-31, and 62 once #72
   to #77 were added the same day. #7 (Lab 2
   process work, Released) and the closed #22 and #49 have no value.
2. The owner sets **Reviewed** only after checking the Issue's scope, requirements, acceptance
   criteria, visual references, dependencies, testing expectations and Project fields.
3. **An agent starts an Issue only when Status is Ready and Human Review is Reviewed.** It may read
   and refine a Pending Issue, but not implement it.
4. When an agent changes an Issue's scope or acceptance criteria, it resets Human Review to
   Pending and says why in a comment.
5. Work already in flight continues. PR #62 merges only after its Issues are Reviewed.

Suggested first reviews, one per depth and all Ready: **#21** (Owner decision, head of the
critical path), **#63** (Deep review, which every session endpoint needs) and **#57** (Standard
review, the source of the Figma nodes in every UI Issue).

### Traceability

Each step below can be followed on GitHub through the Issue body's SDD IDs, the Plan Phase field
and the blocked-by links.

- **US-07 / RC-17** (weighted, evidence-linked feedback) → Phase 5 (§3.5) → #21 anchor spec →
  #47 calibration set → #35 grader → #36 evidence validation → #68 live integration.
- **RC-03** (no session content at rest) → Phase 1 (§3.1) → #63 content-free logging helper →
  Phase 3 #39 no-persistence proof.

### Known gaps at handoff

- **Issue bodies.** The 14 new or rewritten Issues follow the §5 structure. The 32 kept or
  re-phased Issues predate it. They have acceptance criteria, but most lack Dependencies and Visual
  Context sections. Their dependencies are now native links, and their visual context is in the
  §5.1 Notes column. The owner chose links over body rewrites (2026-10-31). The Human Review pass
  is where an Issue gets flagged if that isn't enough.
- **Plan Phase view.** GitHub's API can create a Project view but cannot set its grouping. A view
  grouped by Plan Phase is a one-minute owner action in the GitHub UI.
- **OD-1** was resolved in the ARCHITECTURE.md interview on 2026-10-31 (AD-1). #31 and the Phase 3
  chain now wait only on their Issue blockers.
- **#50** is In Progress, but only for the Mac handoff in PR #62. The TestFlight build itself is
  blocked by #69.

### 7.1 Final Readiness Checklist

| Check | Result | Evidence |
|---|---|---|
| Every MVP user story is represented by at least one phase and Issue | Met | US-01 #25 · US-02 #28, #29 · US-03 #32, #43 · US-04 #31, #67 · US-05 #44 · US-06 #33 · US-07 #35, #37, #38 · US-08 #42 · US-09 #40, #41 |
| Every phase has concrete deliverables and objective acceptance criteria | Met | §3.1–§3.6 Deliverables and Phase Acceptance Criteria |
| Dependencies and sequencing are explicit enough that an agent does not guess the order of high-risk work | Met | §4 rules, §4.1 table, 107 blocked-by links, and Ready only when unblocked |
| Relevant UI/UX and architecture references are identified for future Issues | Met in the plan; partly met in Issue bodies | §3 "Relevant UI/UX Artifacts" and §5.1 Notes; Visual Context sections exist only in the 14 new or rewritten Issues (see Known gaps) |
| The Issue inventory is detailed enough to create Issues without redesigning the project | Met | All 52 child Issues exist on Project #1 (§5.1) |
| SDD, plan, Issues and the three docs agree | Met | Final consistency pass, 2026-10-31: every SDD override is a recorded PA (PA-4, PA-6, PA-10, PA-12) and no Issue body still contradicts one |
| Every implementation-ready Issue is human-reviewed | **Not yet** | All 62 items are Pending. The owner's review is the last step before agents start (gate rule 3) |
