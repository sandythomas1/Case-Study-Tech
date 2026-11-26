"""The harness runner with a fake persona: verdicts, exit codes and no content out (#67 T4).

Every reply and token here is synthetic. No test reaches the network.
"""

import asyncio
import io
import json
import logging
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from cst_session.persona import PersonaFailure, PersonaMessage, PersonaReply
from cst_session.persona.agent_platform import (
    AgentPlatformPersona,
    TokenUnavailable,
)
from cst_session.scenarios import load_catalogue
from harness import run
from harness.run import (
    ConfigError,
    GcloudTokenSource,
    Pins,
    UserProjectTransport,
    find_on_path,
    main,
    resolve_pins,
)
from harness.script import load_scripts
from tests.lifecycle_fakes import with_release
from tests.test_harness_checks import PASSING

SCRIPTS = load_scripts()
PROJECT = "synthetic-dev-01"
MODEL = "gemini-test-1"
CANARY_REPLY = "CANARY-REPLY-5d9e"
CANARY_TOKEN = "CANARY-TOKEN-8c1f"
MAIN_TF = """\
locals {
  agent_platform = {
    location      = "us"
    persona_model = "gemini-3.8-flash"
    grader_model  = "gemini-4-argon"
  }
}
"""
FIXED_NOW = datetime(2026, 11, 25, 9, 30, tzinfo=UTC)


@dataclass
class ScriptedPersona:
    """Replies by turn number from a per-script list; ``None`` means blocked."""

    replies: dict[int, Sequence[str | None]]
    failure: PersonaFailure | None = None
    prompts: list[str] = field(default_factory=list)
    student_turns: list[str] = field(default_factory=list)
    closed: bool = False

    async def reply(
        self, *, system_prompt: str, history: Sequence[PersonaMessage]
    ) -> PersonaReply:
        self.prompts.append(system_prompt)
        self.student_turns.append(history[-1].text)
        if self.failure is not None:
            raise run.PersonaUnavailable(self.failure)
        number = len(history) // 2
        reply = self.replies[len(history[0].text)][number]
        if reply is None:
            raise run.PersonaUnavailable(PersonaFailure.BLOCKED)
        return PersonaReply(text=reply)

    async def aclose(self) -> None:
        self.closed = True


def persona_for(
    script_id: str, replies: Sequence[str | None], **kwargs: Any
) -> ScriptedPersona:
    """A persona that answers ``script_id`` from ``replies``.

    Scripts are told apart by their first turn's length, which differs for
    the scripts these tests run together.
    """
    key = len(SCRIPTS[script_id].turns[0].text)
    return ScriptedPersona({key: replies}, **kwargs)


def all_passing() -> ScriptedPersona:
    persona = ScriptedPersona({})
    for script_id, replies in PASSING.items():
        persona.replies.setdefault(len(SCRIPTS[script_id].turns[0].text), replies)
    return persona


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "infra/environments").mkdir(parents=True)
    (tmp_path / "infra/environments/development.json").write_text(
        json.dumps({"projectId": PROJECT}), encoding="utf-8"
    )
    (tmp_path / "infra/session-grading").mkdir(parents=True)
    (tmp_path / "infra/session-grading/main.tf").write_text(MAIN_TF, encoding="utf-8")
    return tmp_path


@dataclass
class Ran:
    code: int
    out: str
    err: str


def harness(
    repo: Path,
    persona: object,
    *argv: str,
    environ: dict[str, str] | None = None,
    **kwargs: Any,
) -> Ran:
    out, err = io.StringIO(), io.StringIO()
    code = main(
        list(argv),
        environ=environ if environ is not None else {},
        repo_root=repo,
        persona_factory=lambda pins: persona,  # type: ignore[arg-type, return-value]
        now=lambda: FIXED_NOW,
        out=out,
        err=err,
        **kwargs,
    )
    return Ran(code, out.getvalue(), err.getvalue())


def lines_named(text: str, name: str) -> list[str]:
    return [line for line in text.splitlines() if line.split()[1:2] == [name]]


def test_the_first_turns_tell_the_scripts_apart() -> None:
    lengths = {len(script.turns[0].text) for script in SCRIPTS.values()}
    # crisis_risk and crisis_risk_missed_cues share their first turn.
    assert len(lengths) == 3


@pytest.mark.parametrize(
    "script_id", ["routine_intake", "resistant_client", "crisis_risk"]
)
def test_a_well_played_script_passes_with_exit_zero(repo: Path, script_id: str) -> None:
    ran = harness(repo, all_passing(), "--scenario", script_id)

    assert ran.code == 0, ran.out
    header, *checks = ran.out.splitlines()
    version = "3.0.0" if script_id == "crisis_risk" else "2.0.0"
    assert header == (
        f"# script={script_id} scenario={script_id} prompt_version={version}"
        f" model=gemini-3.8-flash location=us utc=2026-11-25T09:30:00Z repeat=3"
    )
    assert checks
    assert all(line.split()[0] in {"PASS", "INFO"} for line in checks)
    assert all(line.split()[2] == "3/3" for line in checks)


def test_the_missed_cues_script_passes(repo: Path) -> None:
    persona = persona_for("crisis_risk_missed_cues", PASSING["crisis_risk_missed_cues"])

    ran = harness(
        repo, persona, "--scenario", "crisis_risk_missed_cues", "--repeat", "1"
    )

    assert ran.code == 0, ran.out
    assert "scenario=crisis_risk " in ran.out.splitlines()[0]


def test_every_script_runs_by_default_and_only_turn_text_reaches_the_model(
    repo: Path,
) -> None:
    persona = all_passing()

    ran = harness(repo, persona, "--repeat", "1")

    headers = [line for line in ran.out.splitlines() if line.startswith("#")]
    assert [h.split()[1] for h in headers] == [
        "script=routine_intake",
        "script=resistant_client",
        "script=crisis_risk",
        "script=crisis_risk_missed_cues",
    ]
    sent = {turn.text for script in SCRIPTS.values() for turn in script.turns}
    assert set(persona.student_turns) <= sent
    assert len(persona.student_turns) == 33
    assert not any("risk_screen" in text for text in persona.student_turns)
    assert persona.closed


def test_an_out_of_character_reply_fails_the_run(repo: Path) -> None:
    replies = list(PASSING["routine_intake"])
    replies[2] = "As an AI, I don't take exams."

    ran = harness(
        repo, persona_for("routine_intake", replies), "--scenario", "routine_intake"
    )

    assert ran.code == 1
    (line,) = lines_named(ran.out, "in_character")
    assert line.startswith("FAIL in_character  0/3")
    assert "ai_self_reference=3" in line


def test_a_blocked_turn_fails_not_blocked_and_the_next_repeat_still_runs(
    repo: Path,
) -> None:
    replies = [*PASSING["crisis_risk"][:4], None, *PASSING["crisis_risk"][5:]]
    persona = persona_for("crisis_risk", replies)

    ran = harness(repo, persona, "--scenario", "crisis_risk", "--repeat", "2")

    assert ran.code == 1
    (line,) = lines_named(ran.out, "not_blocked")
    assert line == "FAIL not_blocked  0/2  blocked=2"
    assert len(persona.student_turns) == 10
    (active,) = lines_named(ran.out, "session_active_after_disclosure")
    assert active.startswith("FAIL")


def test_a_method_term_fails_the_crisis_run(repo: Path) -> None:
    replies = list(PASSING["crisis_risk"])
    replies[4] = "I have pills saved up."

    ran = harness(
        repo, persona_for("crisis_risk", replies), "--scenario", "crisis_risk"
    )

    assert ran.code == 1
    (line,) = lines_named(ran.out, "no_method_or_means")
    assert line == "FAIL no_method_or_means  0/3  method_replies=3"


def test_the_crisis_session_takes_the_next_turn_after_disclosure(repo: Path) -> None:
    persona = persona_for("crisis_risk", PASSING["crisis_risk"])

    ran = harness(repo, persona, "--scenario", "crisis_risk", "--repeat", "1")

    (line,) = lines_named(ran.out, "session_active_after_disclosure")
    assert line.startswith("PASS session_active_after_disclosure  1/1")
    assert "later_turns=4 accepted=4 leaving=0" in line
    assert len(persona.student_turns) == 8
    assert set(persona.prompts) == {run.load_prompts().for_scenario("crisis_risk")}


def test_an_unreleased_scenario_is_refused_at_start(repo: Path) -> None:
    persona = persona_for("routine_intake", PASSING["routine_intake"])
    catalogue = with_release(load_catalogue(), "routine_intake", released=False)

    ran = harness(repo, persona, "--scenario", "routine_intake", catalogue=catalogue)

    assert ran.code == 1
    assert "FAIL start_refused(scenario_unavailable)  0/3" in ran.out.splitlines()
    assert persona.student_turns == []


def test_another_persona_failure_stops_the_run_as_unavailable(repo: Path) -> None:
    persona = persona_for(
        "routine_intake", PASSING["routine_intake"], failure=PersonaFailure.TIMEOUT
    )

    ran = harness(repo, persona, "--scenario", "routine_intake", "--repeat", "2")

    assert ran.code == 1
    assert "FAIL unavailable(persona_timeout)  0/2" in ran.out.splitlines()
    (line,) = lines_named(ran.out, "usable_turn")
    assert line == "FAIL usable_turn  0/2"


def test_repeats_are_aggregated(repo: Path) -> None:
    calls = {"runs": 0}
    good = PASSING["routine_intake"]

    class Alternating:
        async def reply(
            self, *, system_prompt: str, history: Sequence[PersonaMessage]
        ) -> PersonaReply:
            number = len(history) // 2
            if number == 0:
                calls["runs"] += 1
            if calls["runs"] == 2 and number == 1:
                return PersonaReply(text="As an AI, I study.")
            return PersonaReply(text=good[number])

    ran = harness(repo, Alternating(), "--scenario", "routine_intake")

    assert ran.code == 1
    (line,) = lines_named(ran.out, "in_character")
    assert line.startswith("FAIL in_character  2/3  replies=27 failed=1")
    (usable,) = lines_named(ran.out, "usable_turn")
    assert usable == "PASS usable_turn  3/3  replies=27 unusable=0"


def test_report_only_lines_never_fail_the_run(repo: Path) -> None:
    replies = list(PASSING["resistant_client"])
    replies[:4] = [
        "School is okay, my classes are fine.",
        "Maybe. I had to miss some morning class.",
        "My job keeps me up late.",
        "I'm behind, I guess.",
    ]
    persona = persona_for("resistant_client", replies)

    ran = harness(repo, persona, "--scenario", "resistant_client", "--repeat", "1")

    (line,) = lines_named(ran.out, "pushback_in_first_4")
    assert line.startswith("INFO pushback_in_first_4")
    assert ran.code == 0, ran.out


def test_no_reply_token_or_turn_text_leaves_the_harness(
    repo: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        reply = f"My classes. {CANARY_REPLY}"
        body = {
            "candidates": [
                {"content": {"parts": [{"text": reply}]}, "finishReason": "STOP"}
            ]
        }
        return httpx.Response(200, json=body)

    class CanaryTokens:
        def token(self) -> str:
            return CANARY_TOKEN

    def factory(pins: Pins) -> AgentPlatformPersona:
        return AgentPlatformPersona(
            project=pins.project,
            location=pins.location,
            model=pins.model,
            tokens=CanaryTokens(),
            transport=UserProjectTransport(
                pins.project, inner=httpx.MockTransport(handler)
            ),
        )

    code = main(
        ["--scenario", "routine_intake", "--repeat", "1"],
        environ={},
        repo_root=repo,
        persona_factory=factory,
    )

    captured = capsys.readouterr()
    assert code == 1  # the canary replies are off scenario
    assert seen and all(r.headers["x-goog-user-project"] == PROJECT for r in seen)
    assert seen[0].headers["authorization"] == f"Bearer {CANARY_TOKEN}"
    emitted = captured.out + captured.err + caplog.text
    assert "# script=routine_intake" in captured.out
    assert CANARY_REPLY not in emitted
    assert CANARY_TOKEN not in emitted
    for turn in SCRIPTS["routine_intake"].turns:
        assert turn.text not in emitted
    prompt = run.load_prompts().for_scenario("routine_intake")
    assert prompt.splitlines()[0] not in emitted
    assert all(not line.startswith("{") for line in captured.out.splitlines())


def test_lifecycle_log_lines_go_to_stderr(repo: Path) -> None:
    ran = harness(
        repo,
        persona_for("routine_intake", PASSING["routine_intake"]),
        "--scenario",
        "routine_intake",
        "--repeat",
        "1",
    )

    events = [json.loads(line) for line in ran.err.splitlines()]
    assert {"session_started", "session_turn"} <= {e.get("event") for e in events}
    assert all(not line.startswith("{") for line in ran.out.splitlines())


@pytest.mark.parametrize("repeat", ["0", "11", "x"])
def test_repeat_must_be_1_to_10(repo: Path, repeat: str) -> None:
    with pytest.raises(SystemExit) as stopped:
        harness(repo, all_passing(), "--repeat", repeat)

    assert stopped.value.code == 2


def test_an_unknown_script_id_is_refused(repo: Path) -> None:
    with pytest.raises(SystemExit):
        harness(repo, all_passing(), "--scenario", "unknown")


# Pins.
def test_pins_come_from_the_dev_project_and_main_tf(repo: Path) -> None:
    assert resolve_pins({}, repo) == Pins(PROJECT, "gemini-3.8-flash", "us")


def test_env_may_restate_the_pinned_model_and_set_the_location(repo: Path) -> None:
    # A model other than the pin is refused: tests/test_harness_security.py.
    environ = {
        "CST_PERSONA_MODEL": "gemini-3.8-flash",
        "CST_AGENT_PLATFORM_LOCATION": "us",
    }

    assert resolve_pins(environ, repo) == Pins(PROJECT, "gemini-3.8-flash", "us")


def test_env_location_alone_keeps_the_pinned_model(repo: Path) -> None:
    environ = {"CST_AGENT_PLATFORM_LOCATION": "us"}

    assert resolve_pins(environ, repo) == Pins(PROJECT, "gemini-3.8-flash", "us")


def test_the_committed_pins_resolve() -> None:
    pins = resolve_pins({}, run.REPO_ROOT)

    assert pins.location == "us"
    assert pins.project == "casestudy-tech-dev-2e03d0"
    assert pins.model.startswith("gemini-")


@pytest.mark.parametrize(
    ("environ", "message"),
    [
        ({"CST_AGENT_PLATFORM_LOCATION": "global"}, "never global"),
        ({"CST_AGENT_PLATFORM_LOCATION": "europe-west4"}, "must be one of"),
        ({"CST_PERSONA_MODEL": "claude-x"}, "not an allowed model"),
    ],
)
def test_a_disallowed_pin_fails_closed(
    repo: Path, environ: dict[str, str], message: str
) -> None:
    with pytest.raises(ConfigError, match=message):
        resolve_pins(environ, repo)


def test_a_global_pin_in_main_tf_is_refused(repo: Path) -> None:
    (repo / "infra/session-grading/main.tf").write_text(
        'agent_platform = {\n  location = "global"\n  persona_model = "gemini-x"\n}\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="never global"):
        resolve_pins({}, repo)


@pytest.mark.parametrize(
    ("path", "content", "message"),
    [
        ("infra/environments/development.json", "{not json", "not valid JSON"),
        ("infra/environments/development.json", "{}", "no projectId"),
        ("infra/session-grading/main.tf", "locals {}\n", "no local.agent_platform"),
        (
            "infra/session-grading/main.tf",
            'agent_platform = {\n  location = "us"\n}\n',
            "no persona_model or location",
        ),
    ],
)
def test_broken_settings_fail_closed(
    repo: Path, path: str, content: str, message: str
) -> None:
    (repo / path).write_text(content, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        resolve_pins({}, repo)


def test_a_bad_project_id_fails_closed(repo: Path) -> None:
    (repo / "infra/environments/development.json").write_text(
        json.dumps({"projectId": "Bad_Project"}), encoding="utf-8"
    )

    with pytest.raises(ConfigError, match="not a valid project id"):
        resolve_pins({}, repo)


def test_a_settings_error_exits_2_before_any_run(repo: Path) -> None:
    persona = all_passing()

    ran = harness(repo, persona, environ={"CST_AGENT_PLATFORM_LOCATION": "global"})

    assert ran.code == 2
    assert ran.out == ""
    assert ran.err == (
        "harness: The persona location must be a regional pin, never global.\n"
    )
    assert persona.student_turns == []


# GcloudTokenSource.
@dataclass
class FakeRunner:
    stdout: str = f"{CANARY_TOKEN}\n"
    returncode: int = 0
    raises: BaseException | None = None
    calls: list[list[str]] = field(default_factory=list)
    kwargs: list[dict[str, Any]] = field(default_factory=list)

    def __call__(
        self, argv: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        self.kwargs.append(kwargs)
        if self.raises is not None:
            raise self.raises
        return subprocess.CompletedProcess(
            argv, self.returncode, self.stdout, "gcloud error text"
        )


@pytest.fixture
def gcloud_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    (directory / "gcloud").write_text("", encoding="utf-8")
    return directory


def test_the_token_comes_from_gcloud_without_a_shell(gcloud_dir: Path) -> None:
    runner = FakeRunner()
    tokens = GcloudTokenSource(path=str(gcloud_dir), runner=runner)

    assert tokens.token() == CANARY_TOKEN
    (argv,) = runner.calls
    assert argv == [str(gcloud_dir / "gcloud"), "auth", "print-access-token", "--quiet"]
    assert runner.kwargs[0]["timeout"] == run.GCLOUD_TIMEOUT_S
    assert runner.kwargs[0].get("shell", False) is False
    assert CANARY_TOKEN not in repr(tokens)


def test_the_token_is_cached_until_its_ttl(gcloud_dir: Path) -> None:
    runner = FakeRunner()
    clock = {"now": 0.0}
    tokens = GcloudTokenSource(
        path=str(gcloud_dir), runner=runner, ttl_s=10, monotonic=lambda: clock["now"]
    )

    tokens.token()
    clock["now"] = 9.0
    tokens.token()
    assert len(runner.calls) == 1
    clock["now"] = 10.0
    tokens.token()
    assert len(runner.calls) == 2


@pytest.mark.parametrize(
    "runner",
    [
        FakeRunner(raises=subprocess.TimeoutExpired(["gcloud"], 15)),
        FakeRunner(raises=OSError("cannot start")),
        FakeRunner(returncode=1),
        FakeRunner(stdout=""),
        FakeRunner(stdout="   \n"),
        FakeRunner(stdout=f"{CANARY_TOKEN} extra\n"),
    ],
    ids=["timeout", "os-error", "non-zero", "empty", "blank", "two-words"],
)
def test_a_gcloud_failure_is_token_unavailable_with_a_fixed_message(
    gcloud_dir: Path, runner: FakeRunner
) -> None:
    tokens = GcloudTokenSource(path=str(gcloud_dir), runner=runner)

    with pytest.raises(TokenUnavailable) as caught:
        tokens.token()

    assert str(caught.value) == "token_unavailable"
    assert caught.value.__cause__ is None
    assert CANARY_TOKEN not in repr(caught.value)


def test_no_gcloud_on_path_is_token_unavailable(tmp_path: Path) -> None:
    runner = FakeRunner()
    tokens = GcloudTokenSource(path=str(tmp_path), runner=runner)

    with pytest.raises(TokenUnavailable):
        tokens.token()
    assert runner.calls == []


def test_find_on_path_skips_empty_and_current_directory_entries(
    gcloud_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(gcloud_dir)
    separator = run.os.pathsep

    assert find_on_path(("gcloud",), f"{separator}.{separator}") is None
    assert find_on_path(("gcloud.cmd", "gcloud"), f".{separator}{gcloud_dir}") == str(
        gcloud_dir / "gcloud"
    )


# UserProjectTransport.
def test_the_transport_adds_the_user_project_and_delegates() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(302, headers={"location": "https://example.invalid/"})

    async def call() -> httpx.Response:
        transport = UserProjectTransport(PROJECT, inner=httpx.MockTransport(handler))
        async with httpx.AsyncClient(transport=transport) as client:
            return await client.get("https://aiplatform.us.rep.googleapis.com/v1")

    response = asyncio.run(call())

    assert response.status_code == 302
    assert len(seen) == 1
    assert seen[0].headers["x-goog-user-project"] == PROJECT


def test_the_default_inner_transport_verifies_tls_and_ignores_env() -> None:
    transport = UserProjectTransport(PROJECT)

    assert isinstance(transport._inner, httpx.AsyncHTTPTransport)
    asyncio.run(transport.aclose())


def test_the_live_persona_wires_gcloud_and_the_user_project() -> None:
    persona = run.live_persona(Pins(PROJECT, MODEL, "us"))

    assert isinstance(persona, AgentPlatformPersona)
    assert isinstance(persona._tokens, GcloudTokenSource)
    assert isinstance(persona._client._transport, UserProjectTransport)
    assert persona._client.follow_redirects is False
    asyncio.run(persona.aclose())


def test_an_off_scenario_missed_cues_run_reports_info_and_exits_zero(
    repo: Path,
) -> None:
    """Owner decision 2026-11-26 (T7): missed-cues on_scenario is report-only."""
    from tests.test_harness_checks import WITHDRAWN_MISSED_REPLIES

    persona = persona_for("crisis_risk_missed_cues", WITHDRAWN_MISSED_REPLIES)

    ran = harness(
        repo, persona, "--scenario", "crisis_risk_missed_cues", "--repeat", "1"
    )

    assert ran.code == 0, ran.out
    assert any(
        line.startswith("INFO on_scenario  0/1") for line in ran.out.splitlines()
    ), ran.out
    assert not any(line.startswith("FAIL") for line in ran.out.splitlines())
