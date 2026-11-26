"""Security audit fixes for the harness runner (#67 fix round 2).

PATH lookups skip every relative entry, the model can't be overridden away from
the pin, the token must look like a token, a hung ``gcloud`` is killed as a
tree and TLS verification can't be loosened by the environment.
"""

import io
import json
import os
import ssl
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from cst_session.persona.agent_platform import TokenUnavailable
from harness import run
from harness.run import (
    ConfigError,
    GcloudTokenSource,
    Pins,
    UserProjectTransport,
    find_on_path,
    kill_process_tree,
    main,
    resolve_pins,
    run_gcloud,
)

PROJECT = "synthetic-dev-01"
PINNED_MODEL = "gemini-3.8-flash"
MAIN_TF = f"""\
locals {{
  agent_platform = {{
    location      = "us"
    persona_model = "{PINNED_MODEL}"
    grader_model  = "gemini-4-argon"
  }}
}}
"""
# Non-ASCII so the charset check, not the whitespace check, has to catch it.
CANARY_TOKEN = "CANARY-TOKé-3b7a"
CANARY_OUTPUT = "CANARY-PARTIAL-9e2d"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "infra/environments").mkdir(parents=True)
    (tmp_path / "infra/environments/development.json").write_text(
        json.dumps({"projectId": PROJECT}), encoding="utf-8"
    )
    (tmp_path / "infra/session-grading").mkdir(parents=True)
    (tmp_path / "infra/session-grading/main.tf").write_text(MAIN_TF, encoding="utf-8")
    return tmp_path


# 1. PATH lookups skip relative entries.


@pytest.mark.parametrize(
    "relative", ["bin", os.path.join(".", "bin"), os.path.join("..", "bin")]
)
def test_a_relative_path_entry_is_skipped_for_the_absolute_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    work = tmp_path / "work" / "cwd"
    for directory in (work / "bin", work.parent / "bin"):
        directory.mkdir(parents=True, exist_ok=True)
        for name in run.GCLOUD_NAMES:
            (directory / name).write_text("planted", encoding="utf-8")
    trusted = tmp_path / "sdk" / "bin"
    trusted.mkdir(parents=True)
    (trusted / "gcloud").write_text("trusted", encoding="utf-8")
    monkeypatch.chdir(work)

    found = find_on_path(run.GCLOUD_NAMES, f"{relative}{os.pathsep}{trusted}")

    assert found == str(trusted / "gcloud")
    assert Path(found).is_absolute()


def test_only_relative_entries_find_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "gcloud").write_text("planted", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert find_on_path(run.GCLOUD_NAMES, f"bin{os.pathsep}.{os.pathsep}") is None


# 2. The model is always the pin.


def test_a_model_env_equal_to_the_pin_is_accepted(repo: Path) -> None:
    pins = resolve_pins({"CST_PERSONA_MODEL": PINNED_MODEL}, repo)

    assert pins == Pins(project=PROJECT, model=PINNED_MODEL, location="us")


def test_no_model_env_uses_the_pin(repo: Path) -> None:
    assert resolve_pins({}, repo).model == PINNED_MODEL


@pytest.mark.parametrize(
    "model", ["gemini-test-1", "gemini-3.8-pro", "GEMINI-3.8-FLASH"]
)
def test_a_model_env_other_than_the_pin_is_refused(repo: Path, model: str) -> None:
    with pytest.raises(ConfigError) as caught:
        resolve_pins({"CST_PERSONA_MODEL": model}, repo)

    message = str(caught.value)
    assert "not an allowed model" in message
    assert model not in message


def test_main_exits_2_on_a_model_override_and_never_builds_a_persona(
    repo: Path,
) -> None:
    built: list[Pins] = []
    out, err = io.StringIO(), io.StringIO()

    code = main(
        [],
        environ={"CST_PERSONA_MODEL": "gemini-test-1"},
        repo_root=repo,
        persona_factory=lambda pins: built.append(pins),  # type: ignore[func-returns-value, arg-type, return-value]
        out=out,
        err=err,
    )

    assert code == 2
    assert built == []
    assert out.getvalue() == ""
    assert err.getvalue() == (
        "harness: CST_PERSONA_MODEL is not an allowed model: it must equal the "
        "persona_model pin in infra/session-grading/main.tf.\n"
    )


def test_the_location_env_still_cannot_be_global(repo: Path) -> None:
    with pytest.raises(ConfigError, match="never global"):
        resolve_pins({"CST_AGENT_PLATFORM_LOCATION": "global"}, repo)


# 3. The token must look like an access token.


class StdoutRunner:
    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode

    def __call__(
        self, argv: list[str], **kwargs: Any
    ) -> "subprocess.CompletedProcess[str]":
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, "")


@pytest.fixture
def gcloud_path(tmp_path: Path) -> str:
    directory = tmp_path / "sdk"
    directory.mkdir()
    (directory / "gcloud").write_text("fake", encoding="utf-8")
    return str(directory)


@pytest.mark.parametrize(
    "stdout",
    [
        f"{CANARY_TOKEN}\n",
        "ya29.ok\x00tail\n",
        'ya29."quoted"\n',
        "ya29.a;b\n",
        "x" * 4097 + "\n",
        "\n",
    ],
    ids=["non-ascii", "nul", "quote", "semicolon", "too-long", "empty"],
)
def test_a_token_outside_the_charset_is_unavailable(
    gcloud_path: str, capsys: pytest.CaptureFixture[str], stdout: str
) -> None:
    source = GcloudTokenSource(path=gcloud_path, runner=StdoutRunner(stdout))

    with pytest.raises(TokenUnavailable) as caught:
        source.token()

    seen = capsys.readouterr()
    shown = f"{caught.value}{caught.value!r}{source!r}{seen.out}{seen.err}"
    assert str(caught.value) == "token_unavailable"
    assert CANARY_TOKEN not in shown
    assert "é" not in shown


@pytest.mark.parametrize(
    "token", ["ya29.a0Af-_~+/=", "A" * 4096, "1//0g-refresh.like_token="]
)
def test_a_token_in_the_charset_is_returned(gcloud_path: str, token: str) -> None:
    source = GcloudTokenSource(path=gcloud_path, runner=StdoutRunner(f"{token}\n"))

    assert source.token() == token


# 4. A hung gcloud is killed as a tree.


class HangingPopen:
    """A ``Popen`` whose ``communicate`` times out once, holding partial output."""

    instances: list["HangingPopen"] = []

    def __init__(self, argv: list[str], **kwargs: Any) -> None:
        self.argv = argv
        self.kwargs = kwargs
        self.pid = 4242
        self.returncode: int | None = None
        self.timeout: float | None = None
        HangingPopen.instances.append(self)

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        raise subprocess.TimeoutExpired(self.argv, timeout or 0, output=CANARY_OUTPUT)


def as_popen(fake: type) -> Callable[..., "subprocess.Popen[str]"]:
    return cast(Callable[..., "subprocess.Popen[str]"], fake)


def test_a_timeout_kills_the_tree_and_leaks_nothing(
    gcloud_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    HangingPopen.instances = []
    killed: list[object] = []

    def runner(argv: list[str], **kwargs: Any) -> "subprocess.CompletedProcess[str]":
        return run_gcloud(
            argv, popen=as_popen(HangingPopen), kill_tree=killed.append, **kwargs
        )

    source = GcloudTokenSource(path=gcloud_path, runner=runner)

    with pytest.raises(TokenUnavailable) as caught:
        source.token()

    [proc] = HangingPopen.instances
    assert killed == [proc]
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
    assert str(caught.value) == "token_unavailable"
    seen = capsys.readouterr()
    assert CANARY_OUTPUT not in f"{caught.value!r}{seen.out}{seen.err}"


def test_run_gcloud_passes_the_timeout_and_uses_no_shell() -> None:
    calls: list[HangingPopen] = []

    class DonePopen(HangingPopen):
        def __init__(self, argv: list[str], **kwargs: Any) -> None:
            super().__init__(argv, **kwargs)
            calls.append(self)

        def communicate(self, timeout: float | None = None) -> tuple[str, str]:
            self.timeout = timeout
            self.returncode = 0
            return "ya29.token\n", ""

    done = run_gcloud(
        ["/sdk/gcloud", "auth"], timeout=run.GCLOUD_TIMEOUT_S, popen=as_popen(DonePopen)
    )

    [proc] = calls
    assert proc.argv == ["/sdk/gcloud", "auth"]
    assert proc.timeout == run.GCLOUD_TIMEOUT_S
    assert "shell" not in proc.kwargs
    assert proc.kwargs["stdin"] is subprocess.DEVNULL
    assert proc.kwargs["stderr"] is subprocess.DEVNULL
    assert (done.returncode, done.stdout, done.stderr) == (0, "ya29.token\n", "")


def test_the_default_token_source_runner_is_the_tree_killing_one() -> None:
    assert GcloudTokenSource()._runner is run_gcloud


class KillablePopen:
    def __init__(self) -> None:
        self.pid = 4242
        self.events: list[str] = []

    def kill(self) -> None:
        self.events.append("kill")

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        self.events.append("reap")
        return "", ""


def test_on_windows_taskkill_runs_by_absolute_path_on_the_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(argv: list[str], **kwargs: Any) -> "subprocess.CompletedProcess[str]":
        ran.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(run.os, "name", "nt")
    monkeypatch.setenv("SYSTEMROOT", str(tmp_path / "Windows"))
    monkeypatch.setattr(run.subprocess, "run", fake_run)
    proc = KillablePopen()

    kill_process_tree(proc)  # type: ignore[arg-type]

    [(argv, kwargs)] = ran
    assert argv == [
        str(tmp_path / "Windows" / "System32" / "taskkill.exe"),
        "/T",
        "/F",
        "/PID",
        "4242",
    ]
    assert Path(argv[0]).is_absolute()
    assert "shell" not in kwargs
    assert proc.events == ["kill", "reap"]


def test_on_windows_a_taskkill_failure_still_kills_the_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_run(argv: list[str], **kwargs: Any) -> None:
        raise OSError("no taskkill")

    monkeypatch.setattr(run.os, "name", "nt")
    monkeypatch.setattr(run.subprocess, "run", failing_run)
    proc = KillablePopen()

    kill_process_tree(proc)  # type: ignore[arg-type]

    assert proc.events == ["kill", "reap"]


def test_on_posix_the_process_group_is_killed(monkeypatch: pytest.MonkeyPatch) -> None:
    groups: list[tuple[int, int]] = []

    def fake_killpg(pid: int, sig: int) -> None:
        groups.append((pid, sig))

    monkeypatch.setattr(run.os, "name", "posix")
    monkeypatch.setattr(run.os, "killpg", fake_killpg, raising=False)
    proc = KillablePopen()

    kill_process_tree(proc)  # type: ignore[arg-type]

    assert [pid for pid, _ in groups] == [4242]
    assert proc.events == ["kill", "reap"]


def test_on_posix_gcloud_starts_its_own_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    HangingPopen.instances = []
    monkeypatch.setattr(run.os, "name", "posix")

    with pytest.raises(TokenUnavailable):
        run_gcloud(
            ["/sdk/gcloud"],
            timeout=1,
            popen=as_popen(HangingPopen),
            kill_tree=lambda proc: None,
        )

    [proc] = HangingPopen.instances
    assert proc.kwargs.get("start_new_session") is True


# 5. TLS verification can't be loosened.


def _ssl_context(transport: UserProjectTransport) -> ssl.SSLContext:
    inner = transport._inner
    assert isinstance(inner, httpx.AsyncHTTPTransport)
    context = inner._pool._ssl_context  # type: ignore[attr-defined]
    assert isinstance(context, ssl.SSLContext)
    return context


def test_the_default_inner_transport_requires_a_verified_certificate() -> None:
    context = _ssl_context(UserProjectTransport(PROJECT))

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_ssl_env_variables_are_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # With trust_env on, httpx would load these and raise on the missing file.
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "missing" / "bogus.pem"))
    monkeypatch.setenv("SSL_CERT_DIR", str(tmp_path / "missing"))

    context = _ssl_context(UserProjectTransport(PROJECT))

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_a_trusting_transport_would_have_read_the_bogus_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proves the test above is sensitive: trust_env=True fails on the same env."""
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "missing" / "bogus.pem"))

    with pytest.raises(OSError):
        httpx.AsyncHTTPTransport(verify=True, trust_env=True)
