# Review: Content-free logging helper (#63)

Review depth: **Deep** (owner merges). Reviewers: policy-reviewer (project), security-reviewer (audit),
qa-tester (verify). No blocking finding is open.

## Owner decision
- **Allow-list counts.** Issue #63 IR2 lists the allowed fields as "only" event, ids, status,
  duration and error class/code. The build also allows the non-negative integer counts `completed`,
  `failed` and `overdue`, because the existing alert metrics in `infra/accounts/main.tf` filter on
  them. Sandy, 2026-11-23, verbatim: "Accept as built (Recommended)". The Issue text and its ACs stay
  as they are, and Human Review stays Reviewed.

## Findings and dispositions

| # | Sev | Source | Finding | Disposition |
|---|---|---|---|---|
| 1 | — | policy | IR2 says "only" the listed fields; the counts widen it | Accepted by owner (above) |
| 2 | MEDIUM | security | All id fields shared one loose shape; slugged free text, a UID or an API-key-shaped value passed as an id was emitted | Fixed: per-field shapes (UUID/32-hex ids, hyphen slug scenario id, semver version) with drop tests |
| 3 | MEDIUM | security, policy | The static check missed named-logger `warning`/`exception` (these reach `logging.lastResort` on stderr with a traceback), `logging.root`, `traceback`, `warnings` and `from sys import stderr` | Fixed: `logging`/`traceback`/`warnings` imports allowed in `cst_*` only in a named per-service list with reasons; `logging.root` and `from sys import` stdout/stderr flagged |
| 4 | MEDIUM | security, policy | The catch-all lived in accounts `api.py`, outside the copied module, and passed websocket scopes through | Fixed: stdlib-only ASGI middleware moved into `content_free_log.py` (copied byte-identically), websocket scope logs by class and closes with 1011 |
| 5 | LOW | security | After the response started, the log said `status_code=500` while the wire had a truncated 200 | Fixed: distinct code `internal_error_after_start`, no status code |
| 6 | LOW | security | `json.dumps` ran outside the `try`; a huge int count raised into the caller | Fixed: inside the `try`; counts and duration capped below 2**63 |
| 7 | LOW | security | AC3 Dockerfile check read one line at a time | Fixed: continuation lines joined, JSON-array CMD parsed |
| 8 | LOW | security, qa | CORS and `no_cache` sit outside the catch-all; their own framework-constant failures still reach uvicorn | Accepted: messages are framework constants, tracebacks carry no locals, and no request content passes through them |
| 9 | LOW | security | `dependencies(Settings())` runs outside the sweep's `try` | Accepted: startup messages are content-free (`hide_input_in_errors=True`, constant SDK errors), and stderr still fires the failure alert |
| 10 | info | policy, qa | A logger name built at run time, or a named logger's `.info(<content>)`, is not statically detectable | Accepted residual: `.info` never prints under uvicorn's default config, the import allow-list (3) now bounds where `logging` can be used, and the module docstring says so |
| 12 | LOW | security re-check | `BaseExceptionGroup` (a cancellation plus a content-bearing error) escaped `except Exception` | Fixed in round 2: the group is split and its Exception part logged by class. The cancellation remainder is re-raised as a new group with a fixed message, flattened, with each leaf's chain suppressed. The implementer found that `split()` copies the original message onto `rest`, so a plain `raise rest from None` still leaked |
| 13 | LOW | security re-check | The std-stream exemption matched by file name; attribute references and `os.write` were not flagged | Fixed in round 2: exact-path exemption, any `sys.stdout`/`sys.stderr` reference and `os.write` flagged |
| 14 | LOW | security re-check | `CMD sh -c "exec uvicorn ..."` was not parsed | Fixed in round 2: nested shlex split |
| 15 | LOW | security re-check | `scenario_id` accepts a hyphen-slug phrase; event names and codes accept snake-case phrases | `scenario_id` fixed after the PR opened: it now accepts only the three catalogue ids from `rubric/anchor-spec.v1.json` (`routine_intake`, `resistant_client`, `crisis_risk`). The hyphen slug would have dropped every real id. Event names and codes: accepted, they come from code, never from user input |
| 16 | LOW | security re-check | Run-time evasions (`importlib`, `__import__`, `getattr(sys, ...)`, `os`-level writes beyond `os.write`) defeat a static check | Accepted residual: they require deliberate evasion, which review catches; documented in the check's docstring |
| 11 | info | qa | Session has no HTTP app yet, so FR-4/AC2 are proven on accounts only | Accepted: session and grading inherit the catch-all through the copied module (4) when #31/#66 add their apps |

## Verification
See `verification.md`: AC1–AC4 proven 4/4, each mutation-tested (removing the fix fails its tests).
