# CaseStudy Tech — Architecture

**Question this file answers:** how must the system be organized? Read it before any Issue that
adds a component, endpoint, data store, external call or cross-service contract.

Status: reviewed with the owner on 2026-10-31 (Lab 3 · Challenge 2 · Feature 1). Items marked
**OPEN** are not decided. Do not guess them; stop and ask on the Issue.

Authority, highest first: SDD v1.0 (`output/CSCI_5520_CaseStudy_Tech_Software_Design_Document_Final.docx`)
→ Implementation Plan (`docs/lab3/implementation-plan.md`) → this file → code. Product rules live in
`docs/POLICY.md`, phase order in `docs/ROADMAP.md`, and task detail in GitHub Issues.

## 1. At a glance

CaseStudy Tech is a practice tool. A counseling student holds a timed, voice-first conversation
with a simulated client. When the conversation ends, a separate grader turns the complete
transcript into a developmental report. The report goes to the device. The server keeps only the
scores. The backend is a headless, stateless API: any instance can serve any request, and web, iOS
and Android share one contract.

```text
Student device (Expo app: web / iOS / Android) — holds the signed conversation state
   │  HTTPS + Firebase ID token
   ▼
API Gateway (one config, per-route backends; validates JWT)
   ├──► accounts service : sign-in exchange, refresh, /me, access requests + admin decisions, scores read, deletion
   └──► session service  : persona turns, speech, timer, conduct safeguard, end of session
              │  private service-to-service call (no gateway route)
              ▼
         grading service  : rubric scoring, evidence validation, score write, report

Vertex AI (persona, grader) · speech provider (behind an interface) · Firestore (scores + access records)
Secret Manager (credentials, state-signing key) · Cloud Logging (no session content) · email provider (owner only, OD-3)
```

Diagram: `docs/02-gcp-architecture.png` (SDD Figure 1, Lucidchart source). Where the diagram and this
file differ, this file records the decisions and the code as built (plan PA-11).

## 2. Architecture decisions (owner interview, 2026-10-31)

| ID | Decision | Why | Cost accepted |
|---|---|---|---|
| AD-1 | **The app holds the conversation and the session service signs it** (resolves plan OD-1). Each reply returns a signed state the app sends back with the next turn. | Stateless services survive Cloud Run restarts, scale-in and rerouting. The SDD already keeps recoverable turn state on the device (§5.1, RC-08). An external session store is forbidden (RC-03). | Signing code, a signing key and requests that grow to tens of KB by minute 10. |
| AD-2 | **Rewind is an accepted MVP risk.** A stateless server cannot detect an app resending an older signed state. | Only the student's own developmental score is affected. Threats, slurs and harassment still end the session at once. A per-turn Firestore counter would add latency and a dependency to every turn. | A student could undo a turn or reset the one conduct warning. Revisit before any instructor feature makes scores matter to others. |
| AD-3 | **The session service calls the grader privately** and returns the report on the end-session response. | The grader has no public surface and receives only transcripts the session service has verified. | The end-session request waits for grading, so its timeouts must cover it. |
| AD-4 | **One API Gateway config with per-route backends** for the accounts and session services. | One host, one JWT and CORS setup, one base URL for the app. | Every service deploy touches one shared gateway config. |
| AD-5 | **Two GCP projects.** The existing development project serves the `dev` and `staging` branches with synthetic data only. A separate production project serves `main` and is created before the release gate review (#77). | Real student data never shares a project, credentials or logs with test data. | A second Terraform environment to build and keep in step. |

## 3. Components

| Component | Responsibility | Code | State |
|---|---|---|---|
| Student app | Screens, voice and text input, the signed conversation state, on-device report PDF, score history view | `apps/student` (Expo Router) | Built in PR #62 (shell, sign-in, account) |
| Identity Platform | Google sign-in only; issues Firebase ID and refresh tokens | `infra/accounts` | Built in PR #62 |
| API Gateway | The one public HTTPS entry; validates Firebase JWTs on protected routes; routes per path (AD-4) | `infra/gateway.yaml.template` | Built for accounts only |
| Accounts service | Server-side Google token exchange and refresh, current student, own scores read, account deletion; access requests, the approval check and admin decisions (POLICY ACC-4 to ACC-9) | `services/accounts` | Built in PR #62; access approval is #72, #73 |
| Session service | Verifies and signs conversation state, persona turns, speech calls, time limit, conduct safeguard, end of session, grader call | not yet | Phase 3–4 |
| Grading service | Private. Accepts only complete transcripts from the session service, scores against the anchor spec, validates evidence, writes scores, returns the report | not yet | Phase 5 |
| Vertex AI | Persona inference and grader inference, as separate calls with separate prompts | — | Models open (OD-2) |
| Speech provider | Speech-to-text and text-to-speech behind a replaceable interface | not yet | Vendor open (Phase 2 ADR) |
| Firestore | `students/{uid}/scores/{scoreId}`, `account_deletions/{uid}` and one server-only access record per account | `infra/firestore.rules` | Built in PR #62; access record is #72 |
| Email provider | Sends the owner one email per access request (name and Google email only) | not yet | Vendor open (OD-3, #74) |
| Secret Manager | Every provider credential, the Identity Platform API key and the state-signing key | `infra/` | Built in PR #62 |
| Cloud Logging | Operational metadata and errors, never session content | content-free helper | Phase 1 (#63) |

## 4. Key flows

1. **Sign-in.** The app gets a Google ID token (native Google Sign-In, web Google Identity
   Services). It posts the token to `/v1/auth/google`. The accounts service exchanges it with
   Identity Platform using the server-held API key and returns Firebase tokens. The ID token lives
   only in memory. The refresh token goes to SecureStore on native and stays in memory on web.
   Source: `docs/decisions/0001-account-boundaries.md`.
2. **Protected request.** The gateway validates the JWT and calls the private Cloud Run service as
   its service account. The service re-verifies the original token from the forwarded
   authorization header. It also checks revocation, the `google.com` provider, the deletion
   marker and that the account is approved (read on every request, failing closed; #72). Decoded
   gateway user info and caller-supplied UIDs are never trusted.
   Before approval, only access state, request access, sign-out and deletion are reachable. A
   request emails the owner (#74), who decides in the admin queue (#73, #76). The admin is server
   configuration, never a client claim.
3. **Practice turn (AD-1).** The app sends the student's turn (audio or text) together with the
   signed state from the previous reply. Before doing anything else, the session service checks the
   signature, that the state belongs to the verified UID, and that the time limit has not passed.
   It then transcribes speech if needed, applies the conduct safeguard and gets the persona reply
   from Vertex AI. It synthesizes speech if needed and returns the reply with a new signed state.
   The state covers the owner UID, scenario, start time, every turn and the conduct-warning count.
   Text mode makes no speech calls. Any instance can serve any turn.
4. **End and grade (AD-3).** Manual end or the time limit closes the session. The session service
   verifies the final signed state is complete and calls the grading service privately, with its
   own service identity, through the completed-session handoff contract (#66). The grader scores
   the transcript and validates every cited turn. It applies the fixed weights and the crisis
   override, writes the overall and six category scores to Firestore, and returns the report. The
   session service passes the report back on the end-session response. The gateway deadline and
   both Cloud Run timeouts on this route must exceed the grading time. The gateway default is 15 s.
5. **Report and export.** The app shows the report and builds the PDF on the device (PA-6). The
   narrative never goes back to the server.
6. **Score history.** The app reads `/v1/scores` through the accounts service. The client has no
   Firebase SDK. The Firestore rules are a second line of defence, not a read path.
7. **Account deletion.** After confirmation, the accounts service writes `account_deletions/{uid}`
   first, so access fails closed, then revokes tokens and deletes the account, its scores and its
   access record.
   Cleanup retries until done, within 30 days (RC-04).
8. **Failure.** Any speech, persona, grading, timeout or connectivity failure ends without a score
   and offers a retry or a new text session (RC-08, RC-09). An invalid, expired or foreign signed
   state is rejected, and the app takes the same lost-content path.

## 5. Boundaries and dependency rules

- **Client → gateway only.** The app calls nothing but the gateway and Google sign-in. It never
  calls Vertex AI, the speech provider, the grader or Firestore, and it holds no API keys (RC-06).
- **Session and grading are separate services with separate prompts** (RC-10, DD-02). The session
  service never computes or shows a score. The grader never runs during a session.
- **The grader has no gateway route.** Only the session service's service account may invoke it
  (AD-3). It accepts nothing but the completed-session contract (#66).
- **Only the grading service writes scores.** Client writes are denied by the rules. The accounts
  service reads and deletes but never creates scores.
- **Speech goes through the provider interface** (#64). No session code imports a vendor SDK
  directly, so the vendor can be swapped (RC-16, plan §6 CD-1).
- **Inside each service:** HTTP layer → application logic → adapters (Firestore, Vertex AI,
  speech, Identity Platform, Secret Manager). Domain logic such as score weights, safeguard rules
  and state verification has no framework or vendor imports and is unit-tested without the network.
- **Every new service copies the accounts service's identity check** (flow 2) rather than writing
  its own.
- **Contracts merge before consumers** (plan §4 rule 3): speech interface, signed-state format,
  session handoff, report schema, Firestore rules and deletion marker.

## 6. Technology decisions

Do not replace these without an owner decision and a new decision record.

| Decision | Choice | Source |
|---|---|---|
| Client | Expo (React Native + react-native-web), one codebase, Expo Router, custom dev builds (Expo Go cannot do native Google sign-in) | DD-06, RC-14, PA-7, ADR 0001 |
| Backend | Python 3.12, FastAPI, one private Cloud Run service per responsibility | PA-7, DD-09 |
| Session state | Client-held, server-signed; no server-side session store | AD-1, AD-2 |
| Cloud | GCP, `us-central1`, managed services only; development and production projects | DD-09, AD-5 |
| Edge | One API Gateway config, per-route backends | AD-4 |
| Identity | Identity Platform with Google sign-in only; server-side token exchange | RC-01, DD-05, ADR 0001 |
| Models | Hosted Vertex AI with a prompt harness; no fine-tuning or self-hosting | DD-01, SDD §2.3 |
| Speech | Replaceable interface; vendor chosen by the Phase 2 ADR | RC-16, PA-2 |
| Data | Firestore: score records and one access record per account (POLICY DAT-2 exception) | DD-03, RC-04, PA-12 |
| Infrastructure | Terraform under `infra/`; gateway config generated from a template | PA-11 |
| Report export | PDF built on the device; no server render endpoint | PA-6 |
| iOS | TestFlight or internal distribution only | RC-15 |

## 7. Trust and data boundaries

| Data | May exist in | Must never reach |
|---|---|---|
| Audio, transcript, excerpts, narrative feedback | App memory during the session and report view, including the signed state; request bodies in transit; service memory while processing; the speech provider and Vertex AI under written zero-retention terms | Firestore, any database or cache, logs, analytics, crash reports, test fixtures, an external session store, device storage |
| Score record: overall and category scores, completion time, crisis safety result | Firestore under the owner's UID; the app | Any other student; the admin |
| Access record: display name, Google email, state, times | Firestore (server-only); the admin queue; the owner's email (name and email only) | Logs; any account other than its owner and the admin |
| Firebase ID token | App memory; request headers | Disk on any platform, logs |
| Refresh token | Native SecureStore; web memory | Logs, web storage |
| Provider credentials and the state-signing key | Secret Manager; service runtime | The client bundle, git, logs |

Trust boundaries: the device is untrusted. The gateway checks the token, and each service checks
it again. A transcript is trusted only if the session service signed it. Vendors are trusted only
after a written zero-retention record (RC-05). Request-body logging stays off at the gateway and in
Cloud Run (plan IR-5).

## 8. Invariants

- **Never** persist session content anywhere (RC-03). State loss takes the lost-content path; it is
  never patched with storage.
- **Never** process a turn or grade a transcript whose signed state fails verification, belongs to
  another UID or is past its time limit.
- **Never** produce a score from an incomplete transcript or an unvalidated grader result (RC-09,
  RC-18).
- **Never** let a client write to Firestore, call the grader or pick the UID it acts as (RC-02).
- **Never** add a third-party service, SDK or model API without an owner decision and a
  zero-retention record. This includes telemetry and crash reporting (RC-05, plan AG-3).
- **Never** expose a service to the internet except through the gateway.
- **Never** let real student data into the development project (AD-5).
- **Always** compute the overall score in code from the fixed RC-17 weights.
- **Always** verify identity twice: at the gateway and in the service.
- **Always** read secrets from Secret Manager at runtime.

## 9. Deployment and runtime

| Branch | GCP project | Data |
|---|---|---|
| `dev`, `staging` | Development (`infra/environments/development.json`) | Synthetic only |
| `main` | Production (created before the release gate review) | Real students, after the gate |

- Cloud Run services are private (no unauthenticated invoke). The gateway service account invokes
  the accounts and session services. Only the session service account invokes the grader.
- Every deploy needs a human's approval. No agent triggers a deploy (plan AG-9).
- Real students use the system only after the release gate review (#70): written zero-retention
  terms (PA-3) and the calibration and safeguard gates (PA-10).

## 10. Open questions — do not guess

| ID | Question | Blocks | Settled by |
|---|---|---|---|
| OD-2 | Which Vertex AI models run the personas and the grader | Persona harness, grader, calibration drafting | Phase 2 governance record (#65) |
| OQ-01 | Speech vendor and turn transport (one request per turn, or streaming) | Voice session work | Phase 2 ADR (#20) |
| OD-3 | Which email provider sends the owner's access-request emails | Owner notification email (#74) | Owner decision with a data-use record (POLICY DAT-5) |

Known risk: AD-2 (rewind). Revisit it before any instructor or cohort feature.
