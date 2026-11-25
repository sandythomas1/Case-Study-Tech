# Session service (#31)
Branch: feature/31-session-service · Lead run: 2026-11-25 · Status: ready (PR open, merges after #138)
Intent: approved student starts a vetted scenario, exchanges text turns with the persona, ends manually or at 10 min; stateless signed state (AD-1); no content stored or logged; failures end unscored.
Change surfaces: new FastAPI HTTP layer in services/session, copied accounts identity + approved guard, HMAC signed state, Agent Platform persona adapter, interim persona prompts, grader port.
Likely touch points: services/session/cst_session/** (new api, state, persona, grading port), services/session/tests/**, services/session/pyproject.toml + uv.lock, services/session/README.md.
Coordination: the Vertex → Agent Platform rename PR (chore branch) lands first; #31 uses CST_AGENT_PLATFORM_LOCATION. #67 rewrites the interim prompts; #68 adds the HTTP grader client.
