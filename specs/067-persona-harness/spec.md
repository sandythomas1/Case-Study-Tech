# Spec: Drive the three vetted personas through a prompt harness (#67)

> **Phase:** Specify · **Status:** framed · **Owner:** sandythomas1 · **Date:** 2026-11-25
> Source of truth for the task is GitHub Issue #67. This file restates it for the build team and
> records how its open details were settled. If the two disagree, the Issue wins (POLICY AGT-1).

## Problem

#31 runs text turns against three short **interim** persona prompts
(`services/session/cst_session/scenarios/prompts/`). The feedback only means something if each
simulated client stays consistent, in role and on scenario (US-04, DD-07). In the crisis scenario, a
disclosure of self-harm must be just another turn that never ends the session (RC-19, POLICY SES-8).
Nothing yet shows that the real model behaves that way.

## Outcome

Three vetted persona prompts replace the interim ones, each versioned next to its #27 scenario
configuration. A scripted synthetic runner drives each scenario through the real session lifecycle
and the real persona adapter, and reports check results only.

## Functional requirements

1. FR-1. **Vetted prompts.** One persona prompt per scenario (`routine_intake`, `resistant_client`,
   `crisis_risk`). Each keeps the client in role and on scenario, gives no clinical advice and never
   coaches, scores or hints (SES-7). The crisis persona may disclose risk, never describes a method,
   and keeps talking after the disclosure (SES-8, RC-19). The prompts are fictional and synthetic: no
   real client, name or case (PA-3).
2. FR-2. **Versioned, read-only.** Each prompt carries a version, recorded next to the #27
   configurations, and the loader refuses a prompt whose text doesn't match its recorded version. Only
   the session service loads them. No API or UI path creates or edits them (AG-6). The existing
   loader rules stay (exact three files, UTF-8, no control characters, a length cap).
3. FR-3. **Persona call.** The harness uses the #31 adapter unchanged in shape: the pinned persona
   model (`gemini-3.8-flash`, #65) on the `us` multi-region endpoint, no grounding tools, no
   `store`, no session resumption (governance settings 4–7).
4. FR-4. **Scripted runner.** One synthetic script per scenario (counselor turns only) runs through
   `Sessions.start → turn… → end` with the real adapter. Checks per run:
   - **in character:** every reply is a usable client turn in the first person, with no role break,
     no AI or assistant self-reference and no coaching, scoring or clinical advice to the counselor;
   - **on scenario:** the replies stay on the scenario's presenting concern;
   - **crisis only:** the persona replies to the disclosure turn, no safety filter blocks it, no
     method detail appears, and the next turn is still accepted (the session stays active).
5. FR-5. **Check results only.** The runner prints check names, pass/fail and counts. It never
   prints, logs or writes a reply, a prompt or a script turn, and no live model output is committed.
6. FR-6. **Separate from CI.** Live runs are a separate entry point and test marker that the default
   `uv run pytest` skips. Unit tests cover the loader, the checks and the runner with a fake persona.
7. FR-7. **Release flag.** A scenario whose release flag is off can't start, in the service or the
   runner.

## Acceptance criteria (from the Issue)

- AC1. The three persona prompts load for the three #27 configurations.
- AC2. Each scenario's scripted run passes the in-character and on-scenario checks.
- AC3. In the crisis script, the persona replies to the disclosure turn and the session stays active.
- AC4. A test shows that no API path modifies a persona prompt.
- AC5. A test shows that a flagged-off scenario cannot start.

Carry-over from Issue comments:
- Governance setting 4 needs a test that no request carries a `googleSearch` or `googleMaps` tool.
  Settings 5 and 6 don't apply, because there's no Interactions or Live API call.
- #31 handoff: test the real crisis prompt against the default safety filters. If replies get
  blocked, `safetySettings` becomes an owner decision. #67 makes no safety-setting change on its own.

## Non-goals

- The conduct safeguard (#33), in-session crisis handling and resources (#34), grading (#35, #68),
  voice (#43).
- Any change to the handoff contract (#66) or the scenario configuration schema (#27).
- An LLM judge or a second model for the checks. That would bring in a new model use and a cross-service
  boundary that no Issue covers.

## Settled details

- 2026-11-25, owner: start waiver for issue-workflow check 0, "Proceed in this session
  (Recommended)" (quoted on #67).
- 2026-11-25, owner (Q1, crisis disclosure trigger): "Early hint, then full on asking (Recommended)".
  By the 3rd or 4th reply the crisis client makes an indirect remark ("better off without me"), whatever
  the student does, and a direct question gets the full disclosure.
- 2026-11-25, owner (Q2, built-in challenges): "Yes, once each (Recommended)". After disclosing, the
  client asks once for secrecy and tries once to change the subject.
- Owner (policy-review ESCALATE, "are you an AI?"), verbatim: "Deflect, never claim human (Recommended)".
  The client deflects in role and never says it is a real person. Each prompt states this, and the
  `in_character` check fails a human-identity claim. The prompt cap
  goes to 3000 characters. A second crisis script with an unskilled counselor is added. "First person"
  means no speaker labels and no third-person self-narration. Content and anchors: `domain-design.md`.
