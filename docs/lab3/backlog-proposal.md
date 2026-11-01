# CSCI 5520 Lab 3 — Proposed Backlog Changes

Status: **approved by the owner and applied to Project #1 (2026-10-30).** This file is the change
set behind Implementation Plan §5.1.

Field names changed on 2026-10-31 (C1 F3, plan §7). "Board Phase" below is now the **Stage**
field. The "Human Review" column below holds review depths, which now live in the **Review Depth**
field. The new **Human Review** field holds Pending/Reviewed, and every Issue starts at Pending.
Statuses below are as proposed. §7's "Ready only when unblocked" rule later moved several of them
to Backlog.

Created Issues: NEW-1 = #63 · NEW-2 = #64 · NEW-3 = #65 · NEW-4 = #66 · NEW-5 = #67 · NEW-6 = #68 ·
NEW-7 = #69 · NEW-8 = #70. Each one has every board field set and is linked as a sub-issue of its
epic. The six rewrites, the re-phases and the two closes each carry a comment that explains the
change. The board's "Item closed" automation moved #22 and #49 to Done in Dev, so their Status
was cleared, because no PR was merged for either.

Field values: Phase is the board's SDLC field (Planning, Design, Implementation, Testing,
Deployment), not the plan phase. The plan phase goes in each Issue body. Sequence uses the board's
existing numbering, with decimals to slot new work between existing Issues.

## New Issues

| ID | Title | Plan phase | Epic | Status | Board Phase | Priority | Area | Sequence | Human Review |
|---|---|---|---|---|---|---|---|---|---|
| NEW-1 | Keep session content out of logs with a content-free logging helper | 1 | #11 | Ready | Implementation | Critical | Backend | 7.5 | Deep review |
| NEW-2 | Define the replaceable speech provider interface and its fake | 2 | #6 | Ready | Design | High | Backend | 3.5 | Deep review |
| NEW-3 | Configure Vertex AI for zero data retention and record the governance settings | 2 | #11 | Ready | Implementation | Critical | AI/ML | 4.5 | Owner decision |
| NEW-4 | Define the completed-session handoff contract | 3 | #6 | Ready | Design | Critical | Backend | 14.5 | Deep review |
| NEW-5 | Drive the three vetted personas through a prompt harness on Vertex AI | 3 | #6 | Backlog (until #31 is unblocked) | Implementation | Critical | AI/ML | 15.5 | Deep review |
| NEW-6 | Send completed live sessions to the validated grader | 5 | #13 | Backlog | Implementation | Critical | Backend | 21.5 | Deep review |
| NEW-7 | Verify cross-platform parity and produce the web and Android release builds | 6 | #16 | Backlog | Testing | High | Frontend | 33.5 | Standard review |
| NEW-8 | Review the release gates before real-student use | 6 | #16 | Backlog | Deployment | Critical | Documentation | 35 | Owner decision |

## Rewrites

Each rewrite keeps the Issue number, its comments and its PR references. The body is replaced
with the §5 structure, and a progress comment records what changed and why.

| Issue | New title | What changes | Field changes |
|---|---|---|---|
| #21 | Write the rubric anchor specification from free instruments | Removes faculty review (PA-10). Hybrid anchors: behavior levels for the grader, developmental labels for students. Free instruments only, with no CCS-R or MITI manual (PA-4). Cites `docs/lab3/rubric-survey.md` | Human Review: Owner decision |
| #47 | Build the labeled calibration set and calibration runner | Replaces independent faculty ratings with the PA-10(a) gate: ±1 level on ≥90% of transcripts and 100% of crisis overrides. A different model family drafts the transcripts, and the owner approves every label (CD-5). Labels freeze before grader work | Status Backlog → Ready; Sequence 31 → 5.5; Board Phase stays Testing; Human Review: Owner decision |
| #35 | Grade completed transcripts with fixed weights against the anchor specification | Removes the "faculty-approved rubric" and "#47 faculty gate" references. Code computes the RC-17 weights. Grading accepts only complete transcripts | Human Review: Deep review |
| #48 | Build the labeled conduct and crisis safeguard test set | Replaces "measure rates; set thresholds" with "every labeled case passes" (PA-10(b)). Adds crisis-disclosure must-not-terminate cases. Merges before #33 | Sequence 32 → 16.5; Board Phase Testing → Design; Human Review: Owner decision |
| #27 | Define the three vetted scenario configurations with time limits and release flags | Persona prompts move to NEW-5. The time limit is fixed at 10 min (CD-4). Adds the release flag (CD-3) | Board Phase Design → Implementation; Human Review: Deep review |
| #20 | Benchmark OpenAI and Google speech and record the provider ADR | Interface work moves to NEW-2. The latency target is already set (PA-2), so the "set a target" bullet goes. Benchmarks run from a device and web client (IR-3). CD-1 swap rule referenced | Human Review: Owner decision |

## Re-phase, status and close

| Issue | Action | Why |
|---|---|---|
| #46 | Plan phase 6 → 1; Sequence 30 → 10.5 | Already built in PR #62 (PA-11) |
| #39 | Sequence 23 → 27.5; note "no crash-reporting SDK" (AG-3) | It proves no persistence across both modes, so it follows #43 |
| #31 | Status Ready → Backlog, with a comment naming OD-1 as the blocker | "Ready" means nothing blocks starting, and OD-1 does |
| #22 | Close as completed, with a comment pointing to CD-4 | Decision made: 10 min for all three, set in config |
| #49 | Close as not planned, with a comment pointing to PA-10, #47, #48 and NEW-8 | The owner removed faculty review. The crisis checks live in the calibration and safeguard sets |

## Human Review for kept Issues

- **Deep review:** #17, #18, #23, #25, #26, #31, #33, #34, #36, #37, #39, #40, #44, #46, #51, #61
- **Standard review:** #24, #28, #29, #30, #32, #38, #41, #42, #43, #45, #57, #58, #59, #60
- **Owner decision:** #19, #50

## Ambiguities flagged for the owner

1. **#49, close or repurpose.** Proposed: close it as superseded and create NEW-8. Repurposing #49
   as the release-gate review would keep one fewer Issue, but its history describes a different
   job.
2. **Splits of #20 and #27.** Proposed: split both at the contract or phase line (NEW-2, NEW-5).
   Keeping each whole means one Issue spans two plan phases, which breaks sizing rule 2.
3. **Deploy wording.** #51 automates deploys behind human approval, but the plan said "manual". The
   plan now says every deploy needs a human's approval and no agent triggers one. This was derived
   rather than asked, because both readings keep humans in control.
4. **PR #62 size.** It covers 8 Issues. Proposed: leave it as it is, since it is already built, and
   apply sizing rule 1 from here on.
