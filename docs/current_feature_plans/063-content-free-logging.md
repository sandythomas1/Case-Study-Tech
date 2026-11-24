# Content-free logging helper (#63)
Branch: feature/63-content-free-logging · Lead run: 2026-11-23 · Status: ready
Intent: one allow-listed JSON logging helper per service; errors logged by class and code only; body logging off at gateway and Cloud Run (tested); CI flags print/root-logger calls.
Change surfaces: logging of user data (security), services/accounts API error handling, shared-module copy rule.
Likely touch points: services/accounts/cst_accounts/{content_free_log,api,main}.py, services/session/cst_session/content_free_log.py, both pyproject.toml (ruff), tests, READMEs.
Coordination: none active. #66 and #31 consume the helper after merge.
