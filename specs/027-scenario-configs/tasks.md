# Tasks: Three vetted scenario configurations (#27)

Status: building · Branch: `feature/27-scenario-configs` from origin/dev becffd3

## @lead
- [x] T1 (FR-1–FR-7, AC1–AC4) `cst_session/scenarios/`: the `Scenario` model, a strict loader,
  `Catalogue.library()`/`startable()`, `ScenarioUnavailable`, three TOML configs, and tests.
- [x] T2 (FR-8) Carry the `scenario_id` fix (bd329dc) into both helper copies, with tests.
- [x] T3 Docs: the session README, ARCHITECTURE §3 session row.

## @qa
- [ ] Q1 Independently prove AC1–AC4 (mutation-test each), run the checks, write `verification.md`,
  and record the transcript demo.
