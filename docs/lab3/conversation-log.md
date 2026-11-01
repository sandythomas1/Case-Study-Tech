# CSCI 5520 Lab 3 — Decision Log

Trimmed record of the human decisions behind the Lab 3 artifacts (Implementation Plan, GitHub
Issues, `docs/ARCHITECTURE.md`, `docs/POLICY.md`, `docs/ROADMAP.md`). Every question was asked as
multiple choice with a recommended option; the answer column is the human's choice.

The full working log lives in a Claude Doc:
https://claude.ai/artifact/XjRY9Q6Y7H399vGb3rL5xp

## Setup — 2026-10-28

| Question | Answer | Why it matters |
|---|---|---|
| How should questions be asked? | Multiple choice only, recommended option first | Codified in workspace `CLAUDE.md` §9 and this project's `CLAUDE.md` |
| How is the conversation exported? | Claude Doc + this repo log | Doc = full log; this file = durable evidence |
| Where do we start? | Follow the Lab 3 checklist order | Docs cite the Plan's phase/guardrail IDs, so the Plan comes first |
| Which SDD is authoritative? | `output/CSCI_5520_CaseStudy_Tech_Software_Design_Document_Final.docx` | Single source for US / RC / DD IDs |
| How is Lab 3 itself tracked? | No GitHub Issue — homework track | Board stays reserved for the implementation backlog Lab 3 generates |

## Challenge 1 · Feature 1 — Implementation Plan §1.1–1.3 — 2026-10-28

| Question | Answer | Lands in |
|---|---|---|
| How is the Plan authored? | Markdown (`docs/lab3/implementation-plan.md`) → course-template DOCX | Workflow |
| OQ-01 speech provider — effect on phase order? | Provider spike first; stay voice-first (DD-08) | §1.3 PA-2 |
| OQ-02 / RC-05 zero-retention unconfirmed — gate? | Synthetic data only until written confirmation; release gate | §1.3 PA-3 |
| OQ-03 rubric anchors — handling? | Survey counseling, clinical psychology, social work and other therapy-skills rubrics first (`docs/lab3/rubric-survey.md`) | §1.3 PA-4 |
| Anchor style? | Hybrid: behavior-based levels for the grader, developmental labels for students | §1.3 PA-4 |
| Anchor source families? | Counseling core, common factors, social work/MFT, scenario-specific | §1.3 PA-4 |
| Copyrighted instruments? | Free instruments only; Ivey and MI as cited concepts; no CCS-R or MITI manual | §1.3 PA-4 |
| When are anchors written? | Early Issue in the grading phase | §1.3 PA-4 |
| Faculty review? | None for anchors or crisis scenario (overrides SDD OQ-03 / RISK-03); calibration set + labeled safeguard tests are the gate | §1.3 PA-10 |

## Challenge 1 · Feature 1 — §2 Phase Summary — 2026-10-28

| Question | Answer | Lands in |
|---|---|---|
| Phase split? | 6 phases: Foundation & access · Provider & compliance spike · Practice session · Safety & recovery · Grading & report · History, account & release | §2 |
| Grading in parallel? | Yes — Phase 5 starts after Phase 1 on synthetic transcripts | §2, §4 |
| Scenario library placement? | Phase 1 | §2 |

## Challenge 1 · Feature 1 — §3 Detailed Phases — 2026-10-29

| Question | Answer | Lands in |
|---|---|---|
| PA-7 stack (backend language, RN web tooling)? | Expo (RN + react-native-web) + Python FastAPI on Cloud Run | §1.3 PA-7, §3.1 |
| PA-10 calibration tolerance? | Each category within ±1 level on ≥90% of calibration transcripts; 100% of crisis critical-failure cases trigger the override | §1.3 PA-10, §3.5 |
| RISK-02 voice latency target? | p50 ≤ 2.0 s, p95 ≤ 3.5 s (end of student speech to first persona audio) | §1.3 PA-2, §3.2 |
| PA-6 / OQ-05 export location? | PDF generated on the device; no server render | §1.3 PA-6, §3.5 |

Derived without a question: the safeguard pass bar is the US-06/RC-20 pass/fail check applied to
every labeled case. The latency sample size (≥30 scripted turns) is a planning default. Text-mode
session work depends only on Phase 1; voice work waits for the Phase 2 decision record.

## Challenge 1 · Feature 1 — §4 / §4.1 Cross-Phase Dependencies — 2026-10-30

| Question | Answer | Lands in |
|---|---|---|
| WIP limit — how many implementation Issues In Progress at once? | Two lanes: one critical-path Issue plus one off-path Issue; vendor waits do not count | §4 Sequencing rule 1 |

Derived without a question:

- The critical path is the grading chain. It runs from the anchor spec through calibration, the
  grader, evidence validation, integration and the score write, and ends at the release gate.
- Lane 1 starts the anchor spec and the calibration set on day one, since both are docs and data.
  Grader code still waits for the Phase 1 service skeleton. The §2 intro and the §3.5 notes were
  tightened to match.
- The sequencing rules restate earlier decisions as rules an agent must not break: contract
  before consumer, labels before the grader, safeguard tests first, no score before validation,
  and synthetic data until the gates.

## Challenge 1 · Feature 1 — §6 Risks, Open Decisions & Agent Guardrails — 2026-10-30

| Question | Answer | Lands in |
|---|---|---|
| Speech-vendor terms missing at the release gate? | Swap to the alternate provider (RC-16 interface) | §6 CD-1 |
| …and if the alternate also fails terms or latency? | Hold the release. The owner may escalate to accepting a latency miss, never a terms gap | §6 CD-1, §1.3 PA-2 |
| Grader fails calibration after tuning? | One-week time box, then release only the passing scenarios. The crisis 100% rule never relaxes | §6 CD-3, §3.1 release flag |
| Who labels the calibration set? | Asked first as "split between model families", then clarified: a model family different from the grader's drafts, and the owner approves every label | §6 CD-5, §1.3 PA-10 |
| PA-5 / OQ-04 time limit? | 10 minutes for all three scenarios | §6 CD-4, §1.3 PA-5 (resolved) |

Derived without a question:

- A Vertex AI terms gap holds the release (CD-2), since there is no alternate.
- Releasing a subset of scenarios fits RC-22 ("limited to") and is recorded as an exception to
  DD-07 ("exactly three"). The Phase 1 acceptance criterion now honors a per-scenario release flag.
- Two decisions stay open. OD-1 (Cloud Run session state) goes to the ARCHITECTURE.md interview and
  blocks Phase 3 session endpoints. OD-2 (Vertex AI models) is settled by the Phase 2 governance
  record.

## Challenge 1 · Feature 2 — §5 / §5.1 Issue Decomposition and Backlog — 2026-10-30

| Question | Answer | Lands in |
|---|---|---|
| Project #1 already has 10 epics and 40 child Issues. What do we do with them? | Reconcile in place: keep the numbers and history, rewrite the conflicting Issues, add only the gaps | §5 intro, §5.1 |
| PR #62 already built accounts, Terraform, rules and deletion. Does the plan or the code move? | The plan follows the code (PA-11). Account deletion moves to Phase 1 | §1.3 PA-11, §2, §3.1, §3.6, §4 |
| #49 (faculty crisis review): close it or repurpose it? | Close it as superseded, and create a new release gate review Issue | #49 closed; #70 |
| Split #20 and #27 at the contract or phase line? | Split both | #64, #67 |
| Apply the backlog proposal? | Approve and apply, after reading `backlog-proposal.md` | Project #1 |

Applied to Project #1:

- **New Issues:** #63 to #70. Each has every board field set and is linked as a sub-issue of its epic.
- **Rewritten:** #20, #21, #27, #35, #47 and #48. Each kept its number and got a new title, a body in the §5 structure and a comment explaining the change.
- **Re-phased or re-statused:** #46 to Sequence 10.5; #39 to Sequence 27.5, with an AG-3 note; #31 to Backlog, blocked by OD-1.
- **Closed:** #22 as completed (CD-4) and #49 as not planned (PA-10).

Derived without a question:

- The deploy wording is now "every deploy needs a human's approval, and no agent triggers one". This matches #51 and AG-9.
- PR #62 stays as it is and is recorded as the exception that set sizing rule 1.
- The board's "Item closed" automation moved #22 and #49 to Done in Dev. Their Status was cleared, because no PR was merged for either.

## Challenge 1 · Feature 3 — Project Integration, Human Review and §7 — 2026-10-31

| Question | Answer | Lands in |
|---|---|---|
| The checklist needs Human Review = Pending/Reviewed, but §5 already had three review levels. How should the board model both? | Two fields: Human Review (Pending, Reviewed) and Review Depth (Owner decision, Deep review, Standard review) | Project #1; §5, §7 |
| How do plan phases map onto the board, given the existing "Phase" field is SDLC? | Rename the SDLC field to Stage and add a Plan Phase field (1–6) | Project #1; §7; `CLAUDE.md` |
| About 35 Issues were Ready even though their predecessors weren't built. How should Status be set? | Ready only when every predecessor is merged or in an open PR and no open decision applies. Agents start only Ready + Reviewed | Project #1; §7; `CLAUDE.md` |
| How are dependencies recorded? | Native GitHub blocked-by links from §5.1. The 32 kept Issue bodies are not rewritten | Project #1; §7 |

Applied to Project #1:

- **Fields:** Human Review, Review Depth and Plan Phase were created, and Phase was renamed to Stage. Option IDs are unchanged.
- **Values:** 56 open epics and child Issues got Human Review = Pending and a Review Depth. The 46 child Issues also got a Plan Phase.
- **Status:** 21 child Issues and 3 epics moved from Ready to Backlog, and epic #11 moved to In Progress. 10 child Issues are Ready: #19, #21, #24, #27, #51, #57, #59, #63, #64 and #65.
- **Dependencies:** 90 blocked-by links. A script bug added 51 wrong links on the first pass. They were removed, and a second run confirmed that the live set equals the §5.1 set.

Derived without a question:

- #19 (vendor terms) blocks only #70, because §4 says terms block the release, not development.
- Epics have no Plan Phase, because they span phases. Their Status follows their children.
- #7 (Lab 2 process work) and the closed #22 and #49 have no Human Review value.
- No Issue was set to Reviewed. Only the owner sets it (checklist C1 F3). The suggested first reviews are #21, #63 and #57.

## Challenge 2 · Feature 1 — `docs/ARCHITECTURE.md` — 2026-10-31

Inputs: SDD §4 (RC items), §5 and §7; Figure 1 (`docs/02-gcp-architecture.png`); plan §1.3, §2,
§4 and §6; and the code in PR #62 (`docs/decisions/0001-account-boundaries.md`,
`infra/firestore.rules`, `infra/gateway.yaml.template`, `infra/environments/development.json`). A
draft was written first. The interview then settled the open items.

| Question | Answer | Lands in |
|---|---|---|
| OD-1: where does the conversation live between turns? | The owner asked which option headless-architecture practice favours. Answer: a stateless API, and the stateless option RC-03 allows is client-held state with a server signature. Confirmed: the app holds the conversation and the session service signs each turn | AD-1; plan §6.3 |
| A stateless server can't detect a resent older state ("rewind"). Accept or add a per-turn counter? | The owner asked whether the counter scales better. Answer: no, it is the integrity option; it adds a Firestore transaction and a dependency to every turn. Decision: accept rewind for the MVP and record it | AD-2 |
| How is the grader invoked and how does the report reach the app? | The session service calls the grader privately and returns the report on the end-session response | AD-3 |
| How are session and grading routes exposed? | One API Gateway config with per-route backends. The grader gets no route | AD-4 |
| How do branches map to GCP environments? | `dev` and `staging` use the development project (synthetic data). `main` uses a new production project, created before the release gate | AD-5 |
| Post the decisions to the board? | Yes, and update the docs | Comments on #31, #66, #67, #68 and #51 |

Derived without a question:

- The client has no Firebase SDK, so score history reads go through the accounts service. The
  Firestore rules are a second line of defence.
- The end-session route needs a gateway deadline and Cloud Run timeouts above the grading time
  (gateway default 15 s).
- No Issue moved to Ready. #31 still waits on #27, #63 and #66, which are neither merged nor in a PR.
- OD-2 (Vertex models) and the speech vendor and turn transport stay open. Phase 2 settles them.
- The production project has no Issue yet. That was flagged to the owner.

## Challenge 2 · Feature 2 — `docs/POLICY.md` — 2026-10-31

Inputs: SDD §1.2, §2.2–2.3, §3 (US-01–09), §4 (RC-01–22), §6.1–6.3 and §7; plan §1.3, §6.2 and
§6.4; `docs/ARCHITECTURE.md` §7–8; the PR #62 score model and deletion job. A draft was written
first, with four open questions. Two rounds of multiple-choice questions settled them.

| Question | Answer | Lands in |
|---|---|---|
| History shows scores only, but the crisis report leads with the safety result. How does history show a crisis safety failure? | Add a safety-result flag to the score record (recommended) | REP-4; #40, #41 |
| What happens if a student shows real distress of their own during a session? | Out of scope for the MVP; record it as a risk | ETH-3, §10 |
| Who may sign up? | Verbatim: "For the MVP that would be released, we will do it as a user signs up with Gmail to replicate this single-student sign-on and then it sends me an email. Then I will approve for them. Basically what my system design course site does and what I'm trying to replicate. Implement what Reservoir now does as well." Read "Reservoir" as Resuvant (ResiMax), whose spec 024 is the same flow: request, owner email, admin queue, server-enforced approval | ACC-4 to ACC-9; PA-12; #72–#76 |
| Does a score keep a date? | Store a date, use it for order only (recommended) | REP-5; #40, #41 |
| What does the access record keep? | Name and Google email, deleted with the account (recommended) | DAT-2, DAT-3 |
| How is the overall score shown? | 1.0–5.0 with one decimal (recommended). The percent display is dropped | SCO-9; #38, #41 |
| When does the access work reach the board? | Now, with POLICY.md (recommended) | #72–#76 created; comments on #26, #28, #38, #40, #41, #46, #74 |

Derived without a question:

- The access record and the score record's completion time and safety result are recorded
  exceptions to RC-04's "scores only" (DAT-2). The FERPA review revisits the access record.
- An email provider is a new data processor, so it needs an owner decision first (OD-3, AG-3).
  #74 stays Backlog until it is made.
- The admin queue is the only admin surface. It is an exception to the SDD's single student role
  and "no administrative" scope, recorded in POLICY §1 and §9.
- DAT-1 names the one exception to "no session content at rest": the PDF the student chooses to
  export.
- `docs/ARCHITECTURE.md` was updated to match: Firestore holds access records too, the email
  provider is a component, and the identity check includes approval.
- #72 went to Ready, because its blockers (#26, #46) are in open PR #62. #73–#76 are Backlog. All
  five are Human Review Pending.

## Challenge 2 · Feature 3 — `docs/ROADMAP.md` — 2026-10-31

Inputs: SDD §2.2–2.3 (MVP scope and non-goals); plan §2, §3 goals, §4 and §4.1, §6.3; the live
Project #1 board (Plan Phase, Sequence, blocked-by links, epic sub-issues); open PRs #62 and #71.
No Issue export was used. The draft was written after the cross-check below.

Plan ↔ Project mismatches found:

| Mismatch | Decision | Lands in |
|---|---|---|
| AD-5 needs a production GCP project before the release gate, but no Issue covered it | New Phase 6 Issue (recommended): #77, Pending, Deep review, Critical, Infrastructure, under epic #11, blocked by #18 and #65, blocks #70 | #77; plan §3.6, §4.1, §5.1, §7; ARCHITECTURE AD-5; ROADMAP §3 |
| Board Sequence kept pre-Lab 3 numbers for voice #43 (27), no-persistence proof #39 (27.5), recovery #44 (28) and export #42 (26), putting them after Phase 6 history #40/#41 | Renumber to phase order (recommended): #43 → 16.2, #39 → 16.3, #44 → 18.5, #42 → 22.5 | Project #1 Sequence; plan §7 |

Fixed without a question (documentation only):

- §5.1 said #17 was in PR #62. It is in its own draft PR #71, which overlaps PR #62 in
  `apps/student`. The note was corrected.
- §5.1 listed #19 under "Depends On" for #20 and #65, but §7 and the board link #19 only to #70.
  Both rows now say #19 matters for the terms status or the release gate only, with no link.

Derived without a question:

- ROADMAP.md holds no Issue lists, statuses or acceptance criteria. It has six phase outcomes, a
  dependency sketch, the release gates, the open decisions (OD-2, OD-3), an epic table and the
  approved post-MVP step (the FERPA review).
- Epics group Issues by product area and span phases, so the roadmap points readers to the Plan
  Phase field for phase views.
- Minor, left unchanged: #50 (iOS TestFlight) sits under epic #4 Access & Accounts, and #21 (anchor
  spec) under #16 Pre-launch Validation.
- #77 is Backlog because #65 is Ready but not yet in a PR.

## Final consistency pass — SDD → Plan → Issues → docs — 2026-10-31

Inputs: the SDD text, all 63 open Issue bodies (exported fresh), plan §1.3, §2, §3.1 and §7, and
`docs/ARCHITECTURE.md`, `docs/POLICY.md` and `docs/ROADMAP.md`. Method: search for terms that an
owner decision made stale (faculty review, #49, OQ-04/OQ-05 still open, percent scores, server
session state, server-side PDF, open sign-up), then check counts and cross-references.

No question was needed. Every contradiction followed from a decision the owner had already made,
so each fix applied that decision. The SDD itself is not edited; its overrides are recorded as
plan PAs.

| Contradiction | Source of truth | Fix |
|---|---|---|
| Epic #16 still required faculty review of the anchors and the crisis scenario, and listed OQ-04 as open | PA-10, PA-5 | Rewrote #16: #21 owner-approved anchors, #47, #48, #70; OQ-04 settled |
| #34 and #56 said crisis release waits on the closed faculty Issue #49 | PA-10 | Now the owner's release gate review #70, backed by #47 and #48 |
| #42 said "Decide OQ-05 first" (device or server PDF) | PA-6, ARCHITECTURE §6 | On-device PDF stated as settled; no ADR |
| #4 and #25 said any valid Google sign-in opens the library | PA-12, POLICY ACC-4 | Only an approved account does; #25's criterion applies once #72 lands |
| #38, #56–#60 told work not to wait for "faculty rubric approval" | PA-10 | Wording now says rubric approval |
| Plan §2 and §3.1 (Phase 1) omitted invite-only access | PA-12 | Added to the phase row, goal, sources, a deliverable and an acceptance criterion |
| Plan §7 counts still showed 46 child Issues, 90 links, 56 Pending items | Live board | 52 Issues, 107 links, 62 Pending; #72 added to Ready; new readiness row for this pass |
| ARCHITECTURE §10 "do not guess" table lacked OD-3 | ROADMAP §4, plan §6.3 | Added the OD-3 row |

Checked and consistent: the PA-2 latency target, the PA-10 calibration tolerance, 1.0–5.0 scores
with no percent (SCO-9), AD-1 client-held signed state (no Issue assumes a session store), the
10-minute limit in #27, free instruments only (#21, #35, #36), history fields REP-4/REP-5 (#40,
#41), and the open decisions (OD-2, OD-3) across all three docs.

Board effects: 11 Issue bodies edited, each with a planning comment. No Status, field or link
changed. Human Review was already Pending on every edited Issue, so the AC changes on #4, #16, #25
and #42 needed no reset.

## Submission prep (2026-10-31)

The owner asked whether the working log was ready for the video and whether the lab was complete.
A check against the lab handout found three gaps: nothing was on GitHub yet, no Issue was Reviewed,
and the plan existed only as Markdown, while the handout asks for DOCX or PDF from the course
template. The owner chose all four follow-ups:

- **Recording script.** It was added to the Claude Doc working log as a section of about 7
  minutes, one subsection per checklist feature (C1 F1–F3, C2 F1–F3).
- **Review checklist.** Also in the Claude Doc: per-Issue checks for #21, #63 and #57 (#77
  optional). The owner sets Human Review = Reviewed; the agent never does.
- **Plan as DOCX.** `output/CSCI_5520_CaseStudy_Tech_Implementation_Plan.docx` (and `.pdf`) is
  generated from this folder's `implementation-plan.md` into the course template's styles, title
  block and page setup, with the gray template instructions removed. This Markdown file stays
  the source. Regenerate the DOCX if the plan changes.
- **Commit + PR into `dev`.** This branch carries the Lab 3 files only. Merging and promotion to
  `main` are owner actions.
