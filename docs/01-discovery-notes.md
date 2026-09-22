# Discovery Notes — AI Persona Practice App for Behavioral Science Students

**Date:** 2026-09-16
**Status:** Raw capture from initial brainstorm. Feeds into the software project plan.

---

## The Idea (one paragraph)

An app for behavioral science students (psychology, social work, counseling, and related
majors) where they talk to a configurable AI persona that plays a client. The student
practices case work and case studies by counseling the persona. While the session runs,
the AI scores the student's performance. At the end of the session the student receives
a score and concrete feedback on how they did and how to improve.

**Origin of the idea:** The founder uses ChatGPT voice mode to practice technical and
system design interviews. The same "talk to an AI and get graded" loop applied to
clinical / case-work practice.

---

## Core Pain Point

Before behavioral science students get real clinical case studies or real clients, there
is real uneasiness about jumping straight into working with actual people. There is no
low-stakes place to practice.

---

## Problems and Solutions

### Problem 1 — No low-stakes environment to practice
Social workers, psychology students, and behavioral science students as a whole have no
safe, low-stakes environment to practice counseling and case work before real clients.

**Solution:** A configurable AI persona that the student can practice different case
studies against.

### Problem 2 — Students don't know how well they are doing
When students do have real clients or case studies, they lack a real grasp of how well
they are performing in the moment or afterward.

**Solution:** The AI persona (or a grading layer around it) gives real, specific feedback
on what went well and concrete ways to improve, plus a session score.

### Problem 3 — Real practice involves many personality types
In real case work, students encounter many different personalities, presentations, and
case types. Exposure to that variety is limited during training.

**Solution:** The persona is fully configurable so it can simulate different
personalities, conditions, and case scenarios ("what's wrong with them" is a knob the
student or instructor can set).

---

## Model / Engine Questions (open)

- Is there an existing model that is already trained for this kind of simulated-client
  or counseling-practice use case?
- **Option A:** Use an existing general-purpose LLM, driven by prompts, persona
  configuration, and a grading harness.
- **Option B:** If nothing suitable exists, configure or fine-tune our own LLM for this
  domain and build the agent around it.

---

## Guardrails, Harness, and Compliance

- Counseling has domain-specific rules, ethics codes, and compliance requirements
  (differs between social work, psychology, counseling, etc.).
- These rules should be baked into the guardrails and the scoring harness so that the
  score is accurate and grounded in each domain's standards, not just generic "good
  conversation" heuristics.

---

## Feature Sketch (as stated so far)

1. Fully configurable AI persona (personality, presenting problem, background).
2. Voice-first conversation with the persona (modeled on ChatGPT voice mode).
3. Real-time scoring while the student counsels the persona.
4. End-of-session feedback: score plus specific improvement suggestions.
5. Domain-aware guardrails and rubric per behavioral science discipline.

---

## Open Questions (to resolve in interview)

- Who is the primary user: individual students, or instructors/programs assigning
  scenarios?
- Voice-only, text-only, or both?
- Who defines the scoring rubric, and against which standards?
- Scope of the MVP vs. later phases.
- Safety: what happens when a simulated client presents crisis content (self-harm,
  abuse disclosures)?
- Privacy and data retention for session recordings and transcripts.
- Platform: web, mobile, or both?
- Business model, if any.

---

## Interview Answers (2026-09-16)

### Users and go-to-market
- **Primary user:** Both students and instructors, **students first**. Self-serve student
  MVP; instructor / cohort tooling in a later phase.
- **Business model:** Free MVP, monetization deferred. **Overarching goal is
  institutional sales to universities and programs**, so instructor tooling and cohort
  reporting should be designed for, even if not built in v1.

### Product decisions
- **Modality:** Voice-first with a text fallback (accessibility and cheaper testing).
- **Discipline for MVP:** Counseling / clinical psychology. Other disciplines
  (social work, etc.) later.
- **Rubric source:** Published, citable frameworks (e.g., counseling microskills,
  MITI for motivational interviewing). Custom or instructor-defined rubrics later.
- **Feedback timing:** End of session only. No live hints in MVP.
- **Persona setup:** Library only in MVP. Fixed, vetted personas; no student tweaking.
  Configurability comes in a later phase.
- **Crisis content:** Allowed, opt-in per scenario. Student explicitly selects crisis
  scenarios, sees a content notice, and receives crisis-resource links after the session.

### Platform and data
- **Platform:** React Native, targeting both web and mobile from one codebase.
- **Data retention (MVP):** Scores only. Audio and transcripts are discarded once
  feedback is generated. No session replay in v1.

### Model strategy
- **Path:** Hosted LLM plus a prompt harness (persona agent + separate grading pass).
  Fine-tuning is a later phase only if scoring quality demands it.
- **Hard constraint:** Session data must not be retained or used for training by any
  third party. Resolved as: hosted LLM is acceptable **only under zero-data-retention
  / enterprise terms**. Self-hosting is not required for MVP; revisit if institutional
  customers demand it.
- **Speech providers:** Same rule. Speech-to-text and text-to-speech may be hosted
  (Deepgram, ElevenLabs, OpenAI Realtime, etc.) only under zero-retention terms.

### Constraints
- **Team:** Solo builder, full-time.
- **Timeline:** ~6 weeks to MVP.

### Still open
- Which specific STT / TTS vendors actually offer zero-retention terms at solo-builder
  pricing (needs a vendor survey in the plan).
- Which specific counseling framework(s) anchor the v1 rubric.
- Size of the v1 persona library (how many vetted personas ship in the MVP).
