# Spec: Verify zero-retention and no-training terms for AI and speech providers (#19)

> **Phase:** Specify · **Status:** clarified · **Owner:** Sandy (owner decision review) · **Date:** 2026-11-22
> Source: GitHub Issue #19. Rules: POLICY DAT-4, DAT-5; plan PA-3, CD-1, CD-2; SDD RC-05, DD-04, OQ-02.

## Problem
No hosted model or speech provider may process session content until its written terms and account
settings forbid retention and training (RC-05, POLICY DAT-4). Today nobody has recorded what each
candidate's terms actually say, which settings are needed, or what is still missing. So the release
gate (#70) can't be checked, and #65 has no terms status to record.

## Goals
- One decision record that shows, for each provider and model, its retention and training status, with
  links to the governing terms.
- The exact account and project settings each provider needs, and whether each one has been applied.
- A clear verdict for each provider (confirmed, pending written confirmation, or rejected) that #65, #20
  and #70 can cite.

## Non-Goals
- Choosing the persona and grader models (OD-2, #65) or the speech vendor (#20).
- Applying Terraform or changing cloud settings. Only the owner touches cloud consoles and accounts, and
  the GCP baseline (#18) is not merged.
- Committing signed vendor documents. They stay outside the repo (#65).

## Functional Requirements
1. The record MUST list every candidate in scope: Vertex AI (Gemini models for persona inference and
   grading, region `us-central1`), Google Cloud Speech-to-Text and Text-to-Speech, and OpenAI speech
   (current transcription and speech models, given the 2026–27 deprecations). The owner dropped OpenAI
   on 2026-11-22, and the record now marks it Dropped.
2. For each one it MUST state: the published retention behavior (including caching and abuse-monitoring
   logging), the training-use behavior, the pricing tier or agreement the terms depend on, the settings
   needed, and the source URL with the date it was read.
3. It MUST separate *published terms* (public pages) from *written confirmation* (a signed agreement or
   vendor reply on the project's account), because PA-3 and DAT-4 require the second.
4. It MUST mark a provider **rejected** when its published terms show it cannot meet RC-05 at the tier
   the project will use, and say it is not used.
5. It MUST give the owner the exact request to send and the exact settings to apply.

## Acceptance Criteria (from #19, as split by the owner on 2026-11-22)
- [ ] AC1. For each provider and model, the terms status is recorded: published terms with the date read, the confirmation each one needs, and a verdict.
- [ ] AC2. The required account and project settings are documented, with how to verify each one.
- [ ] AC3. Any provider that can't meet RC-05 is marked rejected and is not used.

Getting the confirmations, applying the settings and giving each row its final verdict moved to #115.

## Open Questions
None. Owner answer, 2026-11-22: for Google Speech-to-Text and Text-to-Speech, published terms plus dated
settings evidence count as "in writing". Vertex AI needs written confirmation, from one support case or a
Master Agreement.
