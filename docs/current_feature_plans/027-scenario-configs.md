# Three vetted scenario configurations (#27)
Branch: feature/27-scenario-configs · Lead run: 2026-11-23 · Status: verifying
Intent: three read-only, schema-validated scenario configs (10-minute limit, release flag); library() hides and startable() refuses an unreleased scenario; no API path creates or edits one.
Change surfaces: session service domain (new module), user-visible scenario wording (from the SDD Fig. 3/4 prototype), logging helper scenario_id shape.
Likely touch points: services/session/cst_session/scenarios/, services/session/tests/, both content_free_log.py copies, READMEs, ARCHITECTURE §3 session row.
Coordination: #28 (library screen) and #31 (session start) consume library()/startable(). #67 owns persona prompts.
