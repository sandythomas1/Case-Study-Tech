# Persona prompt harness (#67)
Branch: feature/67-persona-harness · Lead run: 2026-11-25 · Status: ready (PR into dev, owner merges: Deep review)
Intent: Three vetted, versioned persona prompts replace the #31 interim ones, and a scripted synthetic
runner proves each persona stays in role and on scenario. The crisis persona replies to a disclosure,
and the session stays active. Prompts stay read-only, and a switched-off scenario can't start.
Change surfaces: persona prompt content (domain/safety), prompt loader and versioning, a live-model
runner outside the service image, test markers.
Likely touch points: services/session/cst_session/scenarios/prompts/, scenarios/prompts.py,
services/session/harness/ (new), services/session/tests/, services/session/pyproject.toml.
Coordination: 031-session-service is merged (stale plan file, to archive). No overlap with 004 or 019.
