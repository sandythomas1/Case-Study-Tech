"""Run the synthetic scripts against the live persona and print check results (#67 FR-4, FR-5).

    uv run python -m harness.run [--scenario SCRIPT_ID ...] [--repeat N]

Owner-run only, on the dev project, with synthetic scripts (PA-3). Each run is
the real lifecycle: ``Sessions`` with the committed catalogue and prompts, a
``StateCodec`` on a fresh random key, the real ``AgentPlatformPersona``, a
grader port that drops the session and the system clock. It goes start, one
turn per script turn, then end.

Auth uses the owner's ``gcloud`` login: ``GcloudTokenSource`` asks ``gcloud``
for an access token and holds it in memory only, and ``UserProjectTransport``
bills the dev project. The adapter is unchanged.

The report on stdout is a header and one line per check with pass counts and
numbers. A reply, a prompt, a script turn or a token is never printed, logged
or written. The lifecycle's own content-free log lines go to stderr. The exit
code is 0 only when every gating check passed on every repeat, 1 on any
failure and 2 when the settings are wrong.
"""

import argparse
import asyncio
import contextlib
import json
import logging
import os
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, TextIO

import httpx

from cst_session.handoff.contract import CompletedSession
from cst_session.lifecycle import InvalidTurn, Sessions, StartRefused, SystemClock
from cst_session.persona import PersonaFailure, PersonaPort, PersonaUnavailable
from cst_session.persona.agent_platform import (
    AgentPlatformPersona,
    PersonaConfigError,
    TokenUnavailable,
    endpoint_url,
)
from cst_session.scenarios import Catalogue, load_catalogue
from cst_session.scenarios.prompts import Prompts, load_prompts
from cst_session.state import StateCodec, StateRejected
from harness.checks import CheckResult, TurnRecord, evaluate
from harness.script import SCRIPT_IDS, Script, load_scripts

DEFAULT_REPEAT: Final = 3
MAX_REPEAT: Final = 10
OWNER_UID: Final = "synthHarness01"
GCLOUD_NAMES: Final = ("gcloud.cmd", "gcloud")
GCLOUD_TIMEOUT_S: Final = 15.0
KILL_TIMEOUT_S: Final = 5.0
TOKEN_TTL_S: Final = 600.0
DEVELOPMENT_ENV: Final = Path("infra/environments/development.json")
PINS_FILE: Final = Path("infra/session-grading/main.tf")
MODEL_ENV: Final = "CST_PERSONA_MODEL"
LOCATION_ENV: Final = "CST_AGENT_PLATFORM_LOCATION"
QUIET_LOGGERS: Final = ("httpx", "httpcore")
REPO_ROOT: Final = Path(__file__).resolve().parents[3]

_PINS_BLOCK: Final = re.compile(r"agent_platform = \{(.*?)\}", re.DOTALL)
_PIN: Final = re.compile(r'(\w+)\s*=\s*"([^"]+)"')
# An OAuth access token's charset. Anything else (a word, a quote, a non-ASCII
# letter) means gcloud printed something that isn't a token.
_TOKEN: Final = re.compile(r"[A-Za-z0-9._~+/=-]{1,4096}")

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class ConfigError(Exception):
    """The harness settings are missing or not allowed. The message is fixed."""


@dataclass(frozen=True, slots=True)
class Pins:
    """Where the persona runs: the dev project, the model and the location."""

    project: str
    model: str
    location: str


def resolve_pins(environ: Mapping[str, str], repo_root: Path) -> Pins:
    """The dev project, plus the model and location from the env or ``main.tf``.

    The location is never defaulted to ``global``: it is the env value or the
    committed pin, and the adapter's closed host map must allow it. The model
    is always the committed pin: ``CST_PERSONA_MODEL`` may only restate it, so
    an env value can't send the harness to an unvetted model.
    """
    project = _dev_project(repo_root / DEVELOPMENT_ENV)
    pinned = _terraform_pins(repo_root / PINS_FILE)
    model = pinned.get("persona_model", "")
    location = environ.get(LOCATION_ENV, "") or pinned.get("location", "")
    if not model or not location:
        raise ConfigError(f"{PINS_FILE.as_posix()}: no persona_model or location pin")
    override = environ.get(MODEL_ENV, "")
    if override and override != model:
        raise ConfigError(
            f"{MODEL_ENV} is not an allowed model: it must equal the persona_model "
            f"pin in {PINS_FILE.as_posix()}."
        )
    if location == "global":
        raise ConfigError("The persona location must be a regional pin, never global.")
    try:
        endpoint_url(project=project, location=location, model=model)
    except PersonaConfigError as error:
        raise ConfigError(str(error)) from None
    return Pins(project=project, model=model, location=location)


def _dev_project(path: Path) -> str:
    where = DEVELOPMENT_ENV.as_posix()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ConfigError(f"{where}: missing or not valid JSON") from None
    project = data.get("projectId") if isinstance(data, dict) else None
    if not isinstance(project, str) or not project:
        raise ConfigError(f"{where}: no projectId")
    return project


def _terraform_pins(path: Path) -> dict[str, str]:
    where = PINS_FILE.as_posix()
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise ConfigError(f"{where}: missing or unreadable") from None
    block = _PINS_BLOCK.search(source)
    if block is None:
        raise ConfigError(f"{where}: no local.agent_platform block")
    return dict(_PIN.findall(block.group(1)))


def find_on_path(names: Sequence[str], path: str) -> str | None:
    """Search absolute PATH entries only, never the current directory.

    ``shutil.which`` on Windows also tries the current directory, and a
    relative entry (``""``, ``.``, ``bin``, ``..\\tools``) resolves against
    the current directory, so every entry that isn't absolute is skipped.
    """
    for directory in path.split(os.pathsep):
        if not directory or not Path(directory).is_absolute():
            continue
        for name in names:
            candidate = Path(directory) / name
            if candidate.is_file():
                return str(candidate)
    return None


def kill_process_tree(proc: "subprocess.Popen[str]") -> None:
    """Kill ``proc`` and its children, then reap it. Every failure is dropped.

    ``gcloud.cmd`` on Windows starts ``python`` under ``cmd``, so killing only
    ``proc`` would leave the child holding the pipes. ``taskkill`` comes from
    ``%SystemRoot%\\System32`` by absolute path, never from PATH.
    """
    if os.name == "nt":
        root = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
        taskkill = root / "System32" / "taskkill.exe"
        with contextlib.suppress(subprocess.SubprocessError, OSError, ValueError):
            subprocess.run(
                [str(taskkill), "/T", "/F", "/PID", str(proc.pid)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=KILL_TIMEOUT_S,
                check=False,
            )
    else:
        killpg = getattr(os, "killpg", None)
        if killpg is not None:
            with contextlib.suppress(OSError):
                killpg(proc.pid, getattr(signal, "SIGKILL", signal.SIGTERM))
    with contextlib.suppress(OSError):
        proc.kill()
    with contextlib.suppress(subprocess.SubprocessError, OSError, ValueError):
        proc.communicate(timeout=KILL_TIMEOUT_S)


def run_gcloud(
    argv: Sequence[str],
    *,
    timeout: float,
    popen: Callable[..., "subprocess.Popen[str]"] = subprocess.Popen,
    kill_tree: Callable[["subprocess.Popen[str]"], None] = kill_process_tree,
    **_unused: object,
) -> "subprocess.CompletedProcess[str]":
    """Run ``argv`` with no shell and a hard ``timeout`` that kills the tree.

    ``subprocess.run``'s timeout kills only the direct child, which on Windows
    is ``cmd`` and not ``gcloud``'s ``python``, so it can hang on the pipes.
    ``gcloud``'s stderr goes nowhere. On timeout the whole tree is killed and
    ``TokenUnavailable`` is raised; the partial output is dropped.
    """
    group: dict[str, object] = (
        {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    proc = popen(
        list(argv),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        **group,
    )
    try:
        stdout, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        raise TokenUnavailable() from None
    return subprocess.CompletedProcess(list(argv), proc.returncode, stdout, "")


class GcloudTokenSource:
    """A ``TokenSource`` from ``gcloud auth print-access-token``.

    The token lives in memory only, for at most ``ttl_s``, and is never logged
    or printed. Every failure raises ``TokenUnavailable``, whose message is
    fixed. ``gcloud``'s own output on failure is dropped.
    """

    def __init__(
        self,
        *,
        path: str | None = None,
        runner: Runner = run_gcloud,
        timeout_s: float = GCLOUD_TIMEOUT_S,
        ttl_s: float = TOKEN_TTL_S,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._path = path if path is not None else os.environ.get("PATH", "")
        self._runner = runner
        self._timeout_s = timeout_s
        self._ttl_s = ttl_s
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at = 0.0

    def __repr__(self) -> str:
        return "GcloudTokenSource()"

    def token(self) -> str:
        with self._lock:
            if self._token is None or self._monotonic() >= self._expires_at:
                self._token = self._fetch()
                self._expires_at = self._monotonic() + self._ttl_s
            return self._token

    def _fetch(self) -> str:
        gcloud = find_on_path(GCLOUD_NAMES, self._path)
        if gcloud is None:
            raise TokenUnavailable()
        try:
            done = self._runner(
                [gcloud, "auth", "print-access-token", "--quiet"],
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
                check=False,
            )
        except (subprocess.SubprocessError, OSError, ValueError):
            raise TokenUnavailable() from None
        token = done.stdout.strip() if isinstance(done.stdout, str) else ""
        if done.returncode != 0 or _TOKEN.fullmatch(token) is None:
            raise TokenUnavailable()
        return token


class UserProjectTransport(httpx.AsyncBaseTransport):
    """Adds ``x-goog-user-project`` so user credentials bill the dev project.

    It only delegates: it never follows a redirect, and the adapter's client
    doesn't either.
    """

    def __init__(
        self, project: str, inner: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._project = project
        self._inner = (
            inner
            if inner is not None
            else httpx.AsyncHTTPTransport(verify=True, trust_env=False)
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request.headers["x-goog-user-project"] = self._project
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


class NoopGrader:
    """The harness grades nothing: an ended session is dropped."""

    async def submit(self, session: CompletedSession) -> None:
        return None


def live_persona(pins: Pins) -> PersonaPort:
    """The real adapter on the owner's ``gcloud`` login."""
    return AgentPlatformPersona(
        project=pins.project,
        location=pins.location,
        model=pins.model,
        tokens=GcloudTokenSource(),
        transport=UserProjectTransport(pins.project),
    )


PersonaFactory = Callable[[Pins], PersonaPort]


@dataclass(frozen=True, slots=True)
class RunOutcome:
    """One repeat of one script: its check results, or the error that stopped it."""

    results: tuple[CheckResult, ...] = ()
    error: str | None = None


async def run_once(sessions: Sessions, script: Script) -> RunOutcome:
    """Start, one turn per script turn, then end. A blocked turn stops the run."""
    try:
        started = sessions.start(
            owner_uid=OWNER_UID,
            scenario_id=script.scenario_id,
            crisis_opt_in=script.crisis,
            save_transcript=False,
        )
    except StartRefused as refused:
        return RunOutcome(error=f"start_refused({refused.code})")
    state = started.state
    records: list[TurnRecord] = []
    for turn in script.turns:
        try:
            turned = await sessions.turn(
                owner_uid=OWNER_UID, state=state, text=turn.text
            )
        except PersonaUnavailable as failure:
            if failure.code is not PersonaFailure.BLOCKED:
                return RunOutcome(error=f"unavailable({failure.code.value})")
            records.append(TurnRecord(turn.tag, None, accepted=False, blocked=True))
            break
        except StateRejected as rejected:
            return RunOutcome(error=f"turn_rejected({rejected.reason.value})")
        except InvalidTurn as invalid:
            return RunOutcome(error=f"turn_rejected({invalid.code})")
        records.append(TurnRecord(turn.tag, turned.reply, accepted=True))
        state = turned.state
    try:
        await sessions.end(owner_uid=OWNER_UID, state=state)
    except StateRejected as rejected:
        return RunOutcome(error=f"end_rejected({rejected.reason.value})")
    return RunOutcome(results=evaluate(script, records))


@dataclass(slots=True)
class _Tally:
    report_only: bool
    passed: int = 0
    counts: dict[str, int] = field(default_factory=dict)


def report(
    script: Script,
    outcomes: Sequence[RunOutcome],
    *,
    prompt_version: str,
    pins: Pins,
    at: datetime,
) -> tuple[list[str], bool]:
    """The report lines for one script's repeats, and whether every gating check passed.

    Each line is ``PASS|FAIL|INFO name  passed_runs/total_runs`` and summed
    counts. A run stopped by an error fails every gating check, and the error
    gets its own ``FAIL`` line with the runs it didn't stop.
    """
    total = len(outcomes)
    header = (
        f"# script={script.script_id} scenario={script.scenario_id}"
        f" prompt_version={prompt_version} model={pins.model}"
        f" location={pins.location} utc={at.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f" repeat={total}"
    )
    # Evaluating no turns gives this script's checks in their fixed order.
    tallies = {r.name: _Tally(r.report_only) for r in evaluate(script, ())}
    errors: dict[str, int] = {}
    for outcome in outcomes:
        if outcome.error is not None:
            errors[outcome.error] = errors.get(outcome.error, 0) + 1
        for result in outcome.results:
            tally = tallies[result.name]
            tally.passed += result.passed
            for key, value in result.detail_counts.items():
                tally.counts[key] = tally.counts.get(key, 0) + value
    lines = [header]
    ok = not errors
    for name, tally in tallies.items():
        clean = tally.passed == total
        ok = ok and (clean or tally.report_only)
        verdict = "INFO" if tally.report_only else "PASS" if clean else "FAIL"
        counts = " ".join(f"{key}={value}" for key, value in tally.counts.items())
        lines.append(f"{verdict} {name}  {tally.passed}/{total}  {counts}".rstrip())
    for error, hit in errors.items():
        lines.append(f"FAIL {error}  {total - hit}/{total}")
    return lines, ok


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m harness.run",
        description="Run the synthetic persona scripts and print check results only.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        choices=SCRIPT_IDS,
        metavar="SCRIPT_ID",
        help=f"a script to run, repeatable (default: all of {', '.join(SCRIPT_IDS)})",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=DEFAULT_REPEAT,
        help=f"runs per script, 1 to {MAX_REPEAT} (default {DEFAULT_REPEAT})",
    )
    return parser


async def _run_all(
    scripts: Sequence[Script],
    repeat: int,
    *,
    pins: Pins,
    catalogue: Catalogue,
    prompts: Prompts,
    persona_factory: PersonaFactory,
    now: Callable[[], datetime],
    out: TextIO,
) -> bool:
    persona = persona_factory(pins)
    sessions = Sessions(
        catalogue=catalogue,
        prompts=prompts,
        codec=StateCodec(secrets.token_bytes(32)),
        persona=persona,
        grader=NoopGrader(),
        clock=SystemClock(),
    )
    ok = True
    try:
        for script in scripts:
            at = now()
            outcomes = [await run_once(sessions, script) for _ in range(repeat)]
            lines, passed = report(
                script,
                outcomes,
                prompt_version=prompts.version_for(script.scenario_id),
                pins=pins,
                at=at,
            )
            out.write("\n".join(lines) + "\n")
            out.flush()
            ok = ok and passed
    finally:
        close = getattr(persona, "aclose", None)
        if close is not None:
            await close()
    return ok


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    repo_root: Path = REPO_ROOT,
    persona_factory: PersonaFactory = live_persona,
    catalogue: Catalogue | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Run the chosen scripts. Every keyword is a seam for tests."""
    stdout = out if out is not None else sys.stdout
    stderr = err if err is not None else sys.stderr
    parser = _parser()
    args = parser.parse_args(argv)
    if not 1 <= args.repeat <= MAX_REPEAT:
        parser.error(f"--repeat must be 1 to {MAX_REPEAT}")
    try:
        pins = resolve_pins(os.environ if environ is None else environ, repo_root)
    except ConfigError as error:
        stderr.write(f"harness: {error}\n")
        return 2
    scripts = load_scripts()
    chosen = [scripts[script_id] for script_id in args.scenario or SCRIPT_IDS]
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    # The lifecycle's content-free log lines go to stderr, so stdout is the report.
    with contextlib.redirect_stdout(stderr):
        ok = asyncio.run(
            _run_all(
                chosen,
                args.repeat,
                pins=pins,
                catalogue=catalogue if catalogue is not None else load_catalogue(),
                prompts=load_prompts(),
                persona_factory=persona_factory,
                now=now,
                out=stdout,
            )
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
