# CaseStudy Tech — Roadmap

**Question this file answers:** where is the project going at a high level? Read it to see which
phase a piece of work belongs to and what has to land before it.

Status: written 2026-10-31 (Lab 3 · Challenge 2 · Feature 3). This file changes only when the
direction changes: a phase is added, removed or reordered, a release gate changes, or scope moves.
It does not change when an Issue moves columns.

> **GitHub is the source of truth for the work itself.**
> [Project #1](https://github.com/users/sandythomas1/projects/1) and its Issues are authoritative
> for task definitions, acceptance criteria, sequencing, dependencies, status and review state.
> This file only summarizes them. If this file and an Issue disagree, stop and ask (AG-1).

Authority, highest first: SDD v1.0 → Implementation Plan (`docs/lab3/implementation-plan.md`) →
`docs/ARCHITECTURE.md` / `docs/POLICY.md` / this file → GitHub Issues for task detail.

## 1. Direction

CaseStudy Tech lets counseling students practice with simulated clients. A student signs in with
Google, is approved by the owner, picks one of three vetted scenarios and holds a timed session by
voice or text. A separate grader then produces an evidence-linked developmental report. The report
lives only on the device; the server keeps scores only.

The MVP ships as one Expo app for web, Android and iOS (TestFlight only), backed by FastAPI
services on Google Cloud. No real student uses it until every release gate in §3 is met. Until
then all work runs on synthetic data.

## 2. Phases

Phases group work by outcome. They overlap. The board's **Sequence** field gives the working
order, and its **Plan Phase** field puts each Issue in a phase.

| # | Phase | Outcome when done | Needs first |
|---|---|---|---|
| 1 | Foundation & access | An approved student signs in on any platform, browses the three scenarios, reads the preparation screen and can delete their account. The services, infrastructure, security rules and content-free logging are in place. | Owner setup: GCP, OAuth clients, Apple account |
| 2 | Provider & compliance spike | A speech provider is chosen on measured latency, quality and cost. Speech sits behind a replaceable interface. Vertex AI is set for zero retention, and written vendor terms have been requested. | Runs alongside Phase 1 |
| 3 | Practice session | A timed session with a vetted persona works by text and by voice. Nothing from it persists, and the complete transcript is handed to grading. | Phase 1; Phase 2's provider decision for voice only |
| 4 | Safety & recovery | Conduct rules, voice-to-text recovery and lost-content handling work, and crisis disclosures never end the crisis scenario. The safeguards pass every labeled test case. | Phase 3 |
| 5 | Grading & report | The grader produces a validated, evidence-linked report with the crisis override and passes the calibration gate. The report shows on screen and exports as a PDF on the device. | Phase 1 for the grader; Phase 3 to grade live sessions |
| 6 | History & release | Scores-only history works, the accessibility and parity checks pass, the production project exists and the release gates are reviewed. | Phases 4 and 5 |

### How they connect

```text
Day one:  rubric anchor spec ─► calibration set ─► grader ─► evidence check ─┐   (critical path)
          vendor terms requested (external, slow) ───────────────────────────┤
Phase 1 foundation ─► Phase 3 session ─► Phase 4 safety ─────────────────────┼─► Phase 6 release
Phase 2 spike ──────► (voice only) ──────────────────────────────────────────┘
```

- **Critical path:** grading. A slip in the anchor spec or the calibration set moves the release
  date. Most other slips do not.
- **Two lanes:** at most one critical-path Issue and one other Issue are in progress at a time.
- **Contracts come before the work that uses them:** the speech interface (2 → 3), the session
  handoff (3 → 5), the report contract (5 → screens) and the deletion marker (1 → 6).
- **Voice waits for the provider decision. Text does not.**

The Implementation Plan §4 has the full sequencing rules. The board's blocked-by links put them
into practice.

## 3. Release gates

A real student uses the MVP only after the owner confirms all of these in the release gate review
([#70](https://github.com/sandythomas1/Case-Study-Tech/issues/70)):

- Written zero-retention and no-training terms are on file for every speech and model API (PA-3).
- The grader passes calibration, and every crisis critical-failure case triggers the override
  (PA-10a).
- The conduct and crisis safeguards pass every labeled case (PA-10b).
- There are no open WCAG 2.2 AA failures, and the core flow passes VoiceOver and TalkBack.
- The core flow works the same on web, Android and iOS TestFlight.
- A separate production GCP project exists ([#77](https://github.com/sandythomas1/Case-Study-Tech/issues/77),
  AD-5), and the secrets scan is clean.

If a gate fails, the owner applies the contingency rules in plan §6.2. Agents report the failure
and stop.

## 4. Open decisions that affect the plan

| ID | Decision | Holds up |
|---|---|---|
| OD-2 | Which Vertex AI models run the personas and the grader | Persona harness, grader, calibration drafting |
| OD-3 | Which email provider sends access-request emails | Owner notification email (#74) |

Plan §6.3 tracks these. When one is decided, it is removed here.

## 5. Where the work lives

Epics group Issues by product area, not by phase, so most epics span several phases. Filter the
board by **Plan Phase** to see a phase.

| Area | Epic | Main phases |
|---|---|---|
| Access & accounts | [#4](https://github.com/sandythomas1/Case-Study-Tech/issues/4) | 1, 6 |
| Scenario library & preparation | [#5](https://github.com/sandythomas1/Case-Study-Tech/issues/5) | 1 |
| Platform, privacy & security | [#11](https://github.com/sandythomas1/Case-Study-Tech/issues/11) | 1, 2, 3, 6 |
| Figma screens & journeys | [#56](https://github.com/sandythomas1/Case-Study-Tech/issues/56) | 1, 5, 6 |
| Practice session | [#6](https://github.com/sandythomas1/Case-Study-Tech/issues/6) | 2, 3, 4 |
| Safety & conduct | [#12](https://github.com/sandythomas1/Case-Study-Tech/issues/12) | 1, 4 |
| Grading & feedback | [#13](https://github.com/sandythomas1/Case-Study-Tech/issues/13) | 5 |
| Report export & score history | [#14](https://github.com/sandythomas1/Case-Study-Tech/issues/14) | 5, 6 |
| Accessibility | [#15](https://github.com/sandythomas1/Case-Study-Tech/issues/15) | 1, 6 |
| Pre-launch validation | [#16](https://github.com/sandythomas1/Case-Study-Tech/issues/16) | 4, 5, 6 |

## 6. Beyond the MVP

No post-MVP features are approved. One step is already committed for later: a **FERPA review**
must happen before any institutional sale. It will revisit the access record kept beyond "scores
only" (PA-9, POLICY ETH-6, DAT-2).

These SDD §2.3 non-goals stay out unless the SDD changes: instructor or institutional tools,
content authoring, live coaching or scores, stored or replayable sessions, model training or
self-hosting, clinical or emergency use, enterprise or billing features, and other disciplines or
languages.
