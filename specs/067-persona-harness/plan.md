# Plan: 067-persona-harness

Written by the Lead. No architect: the structure is small and local, adding one loader rule and one
dev-only package outside the service image.

## 1. Prompts (FR-1, FR-2)

- Replace the three files in `services/session/cst_session/scenarios/prompts/` with the vetted texts
  (content from the domain-expert design return, recorded in `build-log.md`).
- **Versioning:** add `prompts/manifest.toml`, one table per scenario id with `version` (semver) and
  `sha256` (hex digest of the loaded text after the loader's CRLF→LF and strip). `load_prompts` refuses:
  a manifest that isn't exactly the three ids, a bad semver, or a digest mismatch. A mismatch error names
  the file, never its content. That forces every prompt edit to come with a reviewed version bump.
  `Prompts.version_for(scenario_id)` exposes the version, which the harness header prints.
  - Rejected: a version header inside each `.txt` (it mixes metadata into model input), and a new key in
    the #27 TOML configs (a schema change to a merged contract and to `Catalogue`).
  - Not done: putting the prompt version in the handoff. Contract 1.0.0 is fixed (#66), and changing it
    is an architecture stop.
- Raise `MAX_PROMPT_CHARS` only as far as the vetted texts need, and keep a cap.
- `prompts/README.md`: no longer interim. Document how to change a prompt (edit, bump the version,
  update the digest) and what a reviewer checks.

## 2. Harness (FR-3..FR-6): `services/session/harness/` (new top-level package)

Outside `cst_session`, so the Dockerfile (`COPY cst_session`) never ships it. Covered by the existing
`ruff check .` and `mypy .`, and importable from tests via `pythonpath = ["."]`.

- `harness/scripts/<scenario_id>.toml`: the synthetic counselor turns. A crisis script marks one turn
  `disclosure_probe = true` and has at least one turn after it. The on-scenario topic terms and the
  pass rule live in the script file.
- `harness/checks.py`: pure functions over one run's replies. They return check results with
  name, passed and counts. No reply text is ever put in a result.
  - `in_character`: every reply is a client turn (role-break, AI self-reference, coaching, scoring and
    clinical-advice patterns; first-person voice).
  - `on_scenario`: the topic-term rule from the script.
  - `crisis_disclosure_answered`, `no_method_detail`, `session_active_after_disclosure`.
- `harness/run.py` (`python -m harness.run [--scenario ID] [--repeat N]`): builds a real `Sessions`
  with `load_catalogue()`, `load_prompts()`, a `StateCodec` on an ephemeral in-memory key, the real
  `AgentPlatformPersona`, a no-op grader port and the system clock. Then it runs
  `start → turn… → end` per script.
  - **Auth for the owner's machine:** a `GcloudTokenSource` (`gcloud auth print-access-token`, token
    in memory only, never printed, the same pattern as `infra/session-grading/agent_platform_governance.py`)
    plus a wrapping httpx transport that adds `x-goog-user-project`. It needs no ADC setup. The adapter
    is unchanged.
  - **Settings:** the project comes from `infra/environments/development.json`. The model and location
    come from `CST_PERSONA_MODEL` / `CST_AGENT_PLATFORM_LOCATION`, falling back to the pins parsed from
    `infra/session-grading/main.tf` `local.agent_platform`, so the pins have one source. The adapter's
    `endpoint_url` still validates them.
  - A `PersonaUnavailable` with code `blocked` is reported as its own failed check
    (`not_blocked`), because that is the evidence for the #31 safety-settings handoff.
  - Output: a header (scenario, prompt version, model id, location, UTC time, repeat count), then one
    line per check with pass counts. The exit code is non-zero on any failure. Replies, prompts and
    script turns are never printed, logged or written. Lifecycle logging stays content-free (#63).
- **Live marker:** `tests/live/test_live_personas.py` is marked `live` and runs the harness. In
  `pyproject.toml`, `markers` and `addopts = "-m 'not live'"` make the default `uv run pytest` skip it.

## 3. Unchanged and re-verified

- AC4: `tests/test_scenario_write_paths.py` and the `test_prompts.py` write-path tests. Extend them so
  the manifest and the `harness/` package are covered.
- AC5: `Catalogue.startable` and the lifecycle start refusal. Add a harness-level test: the runner
  refuses a scenario with `released = false`.
- Setting 4: already explicit. `tests/test_agent_platform.py:41-46` bans `googleSearch`,
  `googleSearchRetrieval` and `googleMaps`, and the request model refuses `tools` (line 196). No new test.

## Risks

- **Heuristic checks** are a floor, not a judgment of persona quality. An LLM judge is out of scope
  (spec non-goal). The prompt texts are vetted by the domain review and by the owner's Deep review of
  the PR.
- **Non-determinism:** temperature is 0.8, so each scenario runs `--repeat` times (default 3) and passes
  only if every run passes.
- **Default safety filters** may block the crisis reply. The runner surfaces it, and the decision goes to
  the owner (L2). No safety-setting change is made pre-emptively.
- **Live runs need the owner's gcloud session** (no credentials on the agent machine). That is a
  HUMAN ACTION REQUIRED once the code is ready.
