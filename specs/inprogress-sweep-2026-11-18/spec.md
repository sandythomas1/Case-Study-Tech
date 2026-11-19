# In-progress sweep + class feedback + transcript retention (2026-11-18)

## Outcome
Move every In Progress Issue on Project #1 as far as an agent can without owner action. Answer the
speech-provider question. Turn the class feedback and Sandy's new decision to keep transcripts into a
concrete list of architecture, deliverable and product changes.

## Requirements
- R1. #61: re-audit the student app and infra harness with clean installs. Apply only patches the
  supported Expo SDK and Firebase versions allow. Record the evidence in `docs/student-toolchain-audit.md`.
- R2. #18: Terraform for private session and grading Cloud Run services, each with a least-privilege
  service account. The gateway invokes session only; session invokes grading only. Health checks are
  over HTTPS. Plus a deploy runbook. No deploy (AGT-6).
- R3. #25, #46, #50: blocked on owner console and Mac work. Issue HUMAN ACTION REQUIRED.
- R4. Speech: is Whisper feasible, plus at least 3 vendors outside Google and OpenAI. Judge each
  against DAT-4 (zero retention, no training), the latency targets (p50 ≤ 2.0 s, p95 ≤ 3.5 s), TTS,
  duplex, cost, GCP fit and the #64 interface.
- R5. Transcript retention (owner, 2026-11-17): keep transcripts for all three scenarios in Firestore,
  in a FERPA-aligned way. Threat-model it, and list every POLICY/ARCHITECTURE rule and Issue it changes.
- R6. Class feedback: list the diagram, deliverable and product changes, including the deck's
  inconsistencies.

## Acceptance criteria
- [ ] #61 has re-audit evidence and an updated status comment.
- [ ] #18 Terraform validates (`terraform validate`), and a runbook exists. Nothing is deployed.
- [ ] The speech comparison has sources and a recommendation.
- [ ] `threat-model.md` covers FERPA, consent, access, retention period, deletion cascade, vendor
  terms and at-risk handling.
- [ ] Retention details are decided by the owner (DECISION NEEDED) before any POLICY rewrite.

## Non-goals
Rewriting POLICY.md or ARCHITECTURE.md before the owner settles the retention details. Any deploy.
Changes to the deck file.
