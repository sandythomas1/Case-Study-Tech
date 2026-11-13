# Case-Study-Tech — Project Instructions

AI-powered counseling practice app: students counsel simulated client personas and get rubric-based
feedback. This file holds what every session needs. It points to the details and does not copy them.

- **Stage:** Planning docs are on `dev`. No application code is merged yet. `services/accounts` and
  `apps/student` exist only in draft PRs #62 and #71.
- **Stack:** Expo client; Python 3.12 + FastAPI on Cloud Run; Firestore; Vertex AI; GCP `us-central1`.
- **Repo:** https://github.com/sandythomas1/Case-Study-Tech
- **Board:** https://github.com/users/sandythomas1/projects/1 (Project #1)
- **Identities:** `sandythomas1` is the human owner. `sandytdev` (AiDev) is the AI development
  identity, with repo Write and Project Writer access.

## Sources of truth

| You need | Read | When |
|---|---|---|
| What to build now | The GitHub Issue | Before any work |
| Components, boundaries, invariants | `docs/ARCHITECTURE.md` | Before changing a service, contract, data flow or dependency |
| Product, privacy, scoring and agent rules | `docs/POLICY.md` | Before touching session data, scores, access or user-visible text |
| Direction and phase order | `docs/ROADMAP.md` | To understand why; it never authorizes work |
| Guardrails and decisions (AG, PA, CD, OD) | `docs/lab3/implementation-plan.md` | When an Issue cites them |
| Requirements (RC, US, DD) | `output/CSCI_5520_CaseStudy_Tech_Software_Design_Document_Final.pdf` | When an Issue cites them |
| Board rules, field IDs, `gh` commands | `docs/PROJECT_BOARD.md` | Before any Issue or board update |

A requirement, a recorded owner decision or a policy rule beats an Issue (POLICY AGT-1). When sources
conflict, stop and ask. Never pick one quietly.

## Starting work

- A reviewed GitHub Issue defines the task, and its acceptance criteria define the scope.
- `docs/ROADMAP.md` is direction only. It is never a substitute for an Issue.
- Start an Issue only when Status is Ready and Human Review is Reviewed.
- Only the owner sets Reviewed. An agent that changes an Issue's scope or acceptance criteria resets
  it to Pending.
- Search before creating an Issue. Work on one Issue per branch.
- Exception: course lab configuration and documents need no Issue when the owner says so. They use a
  `chore/` or `docs/` branch.

## Commands

Nothing runs on `dev` yet. These are the standards from PRs #62 and #71. A new Python service copies
the `services/accounts` layout and tooling.

| Component | Install | Check |
|---|---|---|
| Python service, `services/<name>` | `uv sync --python 3.12` | `uv run pytest`, `uv run ruff check .`, `uv run mypy .` |
| Student app, `apps/student` | `npm ci` | `npm test`, `npm run lint`, `npm run typecheck` |
| Firestore rules, `infra` | `npm ci` | `npm test` |

## Git and PRs

- Flow: `feature/<issue#>-<slug>` from `dev` → `dev` → `staging` → `main`. All three are protected,
  so every change lands through a PR.
- Feature PRs target `dev` and say `Refs #<n>`. Commit only that Issue's files.
- AiDev may merge its own Standard review PR into `dev` once QA passes and no blocking finding
  remains. Deep review and Owner decision PRs wait for the owner's review before merging.
- Changes to `CLAUDE.md`, `.claude/` or `.github/` always wait for the owner's review. AiDev never
  merges a change to its own instructions.
- Only the owner may merge into `staging` or `main`, deploy, change Rulesets, touch production,
  approve access or enable real students (POLICY AGT-6).
- These instructions are guidance. Rulesets and the separate AiDev account are the real boundary.
  Never ask to weaken them to get unblocked.

## Definition of done

- Every acceptance criterion has evidence: a test, command output or screenshot. Put it in the PR
  body and in the Issue's progress comment. This project has no `specs/` folder.
- New logic has tests for behavior, edge cases and failure modes.
- Tests, lint and type checks pass. Report any failure with its output.
- Review matches the Issue's Review Depth field. The levels are defined in
  `docs/lab3/implementation-plan.md` under "Review depth".
- User-visible changes include screenshots of the running app.
- Docs are updated when behavior, commands or a decision changed.
- The PR is open, the Issue has a progress comment, and the board matches reality.

## Proceed or stop

**Proceed without asking:** routine fixes, refactors inside the Issue, test repairs, formatting, and
implementation details the Issue and docs leave open. Mention anything noteworthy in the PR.

**Stop and ask** when a decision affects:

- **Architecture:** a new service, dependency, data store or contract, or anything in ARCHITECTURE §5–§8.
- **Security or privacy:** auth, access rules, secrets, logging of user data or any third party.
- **Policy:** an owner decision (POLICY §1), an accepted risk (§10) or an open question (ARCHITECTURE §10).
- **Scope:** a missing requirement, a criterion that cannot be met as written, or conflicting sources.
- **UX:** user-visible wording or flow that the Issue and its figures do not settle.

**Stop the line:** do nothing further until the owner resolves it. This covers possible persistence of
session content, real student data outside production, an exposed secret, destructive operations on
data or history, production access and any irreversible action.

Ask as multiple choice: 2–4 concrete options, recommended option first, one-line trade-off each. If
AiDev lacks permission for a needed step, give the owner the exact steps and continue other work.

## Board workflow

The board is the shared record. Full rules are in `docs/PROJECT_BOARD.md`.

- Set In Progress before the first code change, and Agent Review when the PR opens.
- Set Done in Dev only after the merge into `dev`. Never set a status ahead of reality.
- Post a progress comment for each push. Tick a criterion only after verifying it.
- If the board cannot be updated, stop and tell the owner.

## Agents and capabilities

Keep work in the lead session unless a specialist reduces a real uncertainty. The lead owns the Issue,
the PR and the board, and merges findings that point to the same `file:line`.

| Agent | Where | Use when |
|---|---|---|
| `implementer` | global | Optional. The lead may hand it a well-defined slice of the Issue |
| `qa-tester` | global | After every code change, to prove each acceptance criterion with evidence |
| `policy-reviewer` | `.claude/agents/` | Before leaving Agent Review, when the diff touches a service, contract, dependency, session data, scores, access, logging or user-visible text |
| `security-reviewer` | global | Also, when auth, access rules, secrets or student data change |

Reviewers are read-only. An `ESCALATE` from any of them goes to the owner and is never settled by the
lead.
