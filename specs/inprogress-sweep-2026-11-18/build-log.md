# Build log — inprogress-sweep-2026-11-18

Base: origin/dev (3b8a6f6). Worktrees: C:/cst-fb (docs/class-feedback-2026-11-17), C:/cst18
(feature/18-gcp-baseline = feature/4 + dev merge 22afae1, local only).

## Owner decisions (verbatim)
- 2026-11-17 (in the /build request): "We're going to save all three transcriptions of the different persona
  characters. At first we're thinking of discarding all of them, but we're going to keep all of them,
  and we want to keep that reliant with FERPA standards as well."
  This conflicts with RC-03, DAT-1, REP-3, ARCHITECTURE §7/§8 and POLICY §9. The owner holds
  authority over the policy, so this is a policy change. Details are still open (L2).

- 2026-11-18 (AskUserQuestion, verbatim picks): Audio = "Transcript only (Recommended)";
  Retention = "180 days + delete anytime (Recommended)"; Consent = "Notice + per-session opt-out
  (Recommended)"; Crisis = "Same rules + explicit wording (Recommended)".
- Lead-resolved (threat-model defaults, reported in the brief): D1 purpose = the student's own review only;
  D6 = app-layer Cloud KMS encryption; D8 = only graded sessions are saved. D9 (amend SDD RC-03/RC-04
  and plan PA-6/§6.4) is owner deliverable work, not an agent edit.

## Triage
- #25, #46: need OAuth clients registered in the Google console → HUMAN ACTION.
- #46: scope grows. Deletion must cascade to transcripts. Human Review resets to Pending (AGT-4) once the
  retention details are written into the issue.
- #50: needs Sandy's Mac → HUMAN ACTION.
- #4, #11: epics; they track their children.

## Dispatches
1. general-purpose (web research) — reduces: Whisper feasibility and vendor terms are factual
   unknowns that change OQ-01/#20.
2. security-reviewer (threat-model) — reduces: keeping student transcripts is a sensitive-data and
   access-rule change (mandatory trigger). FERPA obligations are unknown.
3. implementer (#61 re-audit) — reduces: whether upstream fixes now clear the advisories.
4. devops (#18 Terraform) — reduces: new IAM and service-to-service invoke boundaries need IaC
   built to the least-privilege rule.

## Outcomes
- 2: security-reviewer → threat-model.md. Gave 4 HIGH findings (store.py erase_scores misses future
  subcollections; admin = GCP owner can read content; IDOR on new endpoints; crisis sensitivity), owner
  decisions D1–D9 and the rule/Issue rewrite list. Blocking until decided → decided 2026-11-18 (above).
- 4: devops → PARTIAL at maxTurns, continued via SendMessage → DONE. infra/session-grading/ module,
  conditional gateway session routes, runbook. fmt+validate pass. Notes: session needs Firestore read for
  the identity check; predict-only custom Vertex role; the 190 s end-session deadline is untested; #18's
  criterion 1 needs rewording (grading has no gateway route).
- 5: security-reviewer (audit, reused via SendMessage) — reduces: new IAM and invoke boundaries are a
  mandatory audit trigger. → No blocking findings. 2 MEDIUM (unpinned default image with the signing key; grader
  can't read the deletion marker) + LOW URL check, fixed in round 1 via devops. Deferred LOWs: grading
  internal ingress (needs VPC egress), gateway rate limits, never give session KMS decrypt.
  Lead re-ran fmt -check and validate: pass.
- 3: implementer #61 → PARTIAL (high findings 0 in both trees via `expo install --fix` + in-range eslint
  update; moderate residuals are build/test-only). Left uncommitted. AC4 re-checks + AC5 linking remain.
- Board: progress comments posted on #61 and #18 (2026-11-18). Statuses unchanged: In Progress.

## Close (2026-11-18)
Ship choice (owner, verbatim): "Push all, PRs as drafts (Recommended)". #61 commits pushed to feature/4 (#62) and feature/17 (#71). #18 → draft PR #99 (base feature/4). Notes → draft PR #100 (base dev). Roster: research, security-reviewer (threat-model + audit), implementer, devops (3 rounds). Dispatches: 4 spawns + 4 SendMessage continuations. Lessons: 3 appended.
