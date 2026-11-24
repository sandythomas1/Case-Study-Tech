# Tasks: Content-free logging helper (#63)

Status: in progress · Branch: `feature/63-content-free-logging` from origin/dev db68e91

## @implementer (one batch)
- [x] T1 (FR-1, FR-2, FR-3, AC1) `services/accounts/cst_accounts/content_free_log.py`: stdlib only,
  no FastAPI import. `log_event(event, *, severity="INFO", **fields)` and
  `log_error(event, exc, *, code, **fields)`. Allow-list with per-field types (str ids with a length
  cap and a safe charset, int status/counts, float/int duration). Unknown or wrong-typed fields are
  dropped. Error class is `type(exc).__name__` only. Writes one JSON line to stdout with Cloud
  Logging's `severity` and `message`. Unit tests: unknown field (`transcript`, `text`) value never
  appears; wrong type dropped; event name validated; output is a single JSON line.
- [x] T2 (FR-3, FR-4, AC2) accounts `api.py`: catch-all for unhandled exceptions that logs via
  `log_error` and returns the generic 500 envelope. It must not let the exception reach Starlette's
  `ServerErrorMiddleware` re-raise (which makes uvicorn log the traceback), e.g. a pure ASGI
  middleware. Existing handlers keep their status codes and bodies. Tests with a synthetic turn in
  the exception message: response and captured stdout/stderr and `caplog` contain no turn text and
  no traceback.
- [x] T3 (FR-6) accounts `main.py`: deletion sweep logs via `log_event("account_deletion_sweep",
  completed=…, failed=…, overdue=…)`. The JSON must keep `event`, `failed`, `overdue` at top level so
  `infra/accounts/main.tf` metrics still match. Test asserts the shape.
- [x] T4 (FR-7) byte-identical copy at `services/session/cst_session/content_free_log.py`, plus a
  drift test in both services that compares every `services/*/cst_*/content_free_log.py` to the
  accounts copy. Session's import-boundary test must stay green.
- [x] T5 (AC4) Ruff: enable `T20` (print) and `LOG015` (root-logger call) in both services'
  `pyproject.toml`, and/or an AST test that fails on `print(` / `logging.info(` etc. in `cst_*`
  packages. Fix any hits (the sweep's `print` goes away in T3).
- [x] T6 (FR-5, AC3) test that reads `infra/` (gateway template, Terraform for Cloud Run services)
  and the accounts Dockerfile: no body/payload logging settings, `--no-access-log` present. If
  Terraform cannot express it, assert absence and document why in the test docstring.
- [x] T7 docs: `services/accounts/README.md` and `services/session/README.md` say how to log and
  the copy rule; ARCHITECTURE §3 Cloud Logging row already names the helper (no change unless wrong).

## @qa
- [x] Q1 Run each touched component's checks (`uv run pytest`, `ruff check .`, `mypy .`) and prove
  AC1–AC4 in `verification.md`. Demo: transcript GIF of the AC tests per `pr-demo`.
