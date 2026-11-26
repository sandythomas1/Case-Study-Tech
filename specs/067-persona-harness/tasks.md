# Tasks: 067-persona-harness

Status: done

- [x] T1 @implementer: vetted prompts. Replace the three `.txt` files with the texts in `domain-design.md`. Size `MAX_PROMPT_CHARS` to fit them. Update `prompts/README.md`. (FR-1, AC1)
- [x] T2 @implementer: `prompts/manifest.toml` (version + sha256) and the loader checks, plus
  `Prompts.version_for`. Tests: digest mismatch, a missing or extra id, a bad semver, CRLF digest parity,
  and an error that never holds content. (FR-2, AC1)
- [x] T3 @implementer: `harness/scripts/*.toml` and `harness/checks.py`, with table-driven unit tests,
  including the domain expert's false-positive cases. (FR-4, AC2, AC3)
- [x] T4 @implementer: `harness/run.py`, wired to the real `Sessions`, `GcloudTokenSource`, the
  user-project transport and pin resolution from `main.tf`. Unit tests with a fake persona cover: all
  pass, an in-character failure, a blocked reply → `not_blocked`, the crisis next turn
  accepted, a released=false scenario refused (AC5), a canary reply text never in stdout or stderr,
  and a non-zero exit on failure. (FR-3..FR-7)
- [x] T5 @implementer: the `live` marker, `addopts`, and `tests/live/test_live_personas.py`. Extend the
  write-path tests to the manifest and `harness/` (AC4). Setting 4 is already covered
  (`test_agent_platform.py:41-46,196`). `services/session/README.md`: how the owner runs the harness. (FR-6, AC4)
- [x] T6 @qa: the suite, ruff, mypy. `verification.md` with evidence per AC. A transcript demo GIF
  (pr-demo) of the unit-level runner and, once available, the owner's live output.
- [x] T7 owner (HUMAN ACTION REQUIRED, run 2026-11-26): the live run on the development project, with check results
  pasted into the session. (AC2, AC3)
