# Completed-session handoff contract (#66)
Branch: feature/66-handoff-contract · Lead run: 2026-11-23 · Status: ready (PR open, owner merges: Deep review)
Intent: a versioned payload that the session service hands to the grader. Only `completed` is accepted. Rejection reasons are fixed. The payload is logged content-free. The JSON Schema is committed and checked, and there are synthetic fixtures per scenario and per rejection.
Change surfaces: contract (ARCH §5 "contracts merge before consumers"), session data in memory, logging.
Likely touch points: services/session/cst_session/handoff/, services/session/tests/, services/session/pyproject.toml (pydantic), handoff/ (schema + fixtures), docs/ARCHITECTURE.md §5, services/session/README.md
Coordination: #27 (PR #132) also touches services/session (scenarios/), and #132 changes the log helper's scenario_id to underscores. There is no file overlap. Merge whichever comes second onto dev.
