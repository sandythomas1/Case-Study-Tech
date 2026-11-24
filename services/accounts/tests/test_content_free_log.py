"""The content-free logging helper emits only allow-listed, well-typed fields (AC1).

All values are synthetic. The turn text stands in for session content that must
never reach a log (POLICY DAT-1, DAT-7).
"""

import asyncio
import json
import traceback
from typing import Any

import pytest

from cst_accounts.content_free_log import ContentFreeErrors, log_error, log_event

SYNTHETIC_TURN = "SYNTHETIC-TURN: I feel hopeless"


def emitted(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    out = capsys.readouterr().out
    assert out.endswith("\n")
    return [json.loads(line) for line in out.splitlines()]


def only_line(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    lines = emitted(capsys)
    assert len(lines) == 1
    return lines[0]


def test_an_event_is_one_json_line_with_cloud_logging_fields(capsys):
    log_event("request_completed", status_code=200, duration_ms=12.5)

    assert only_line(capsys) == {
        "severity": "INFO",
        "message": "request_completed",
        "event": "request_completed",
        "status_code": 200,
        "duration_ms": 12.5,
    }


@pytest.mark.parametrize("field", ["transcript", "text", "body", "email", "name"])
def test_a_field_outside_the_allow_list_never_emits_its_value(capsys, field):
    fields: dict[str, Any] = {field: SYNTHETIC_TURN}
    log_event("turn_received", **fields)

    out = capsys.readouterr().out
    assert SYNTHETIC_TURN not in out
    assert "hopeless" not in out
    assert field not in json.loads(out)


SYNTHETIC_UUID = "3f2b8c1e-9d4a-4f6b-8e2c-7a1d5b9c0e4f"
SYNTHETIC_HEX = "0123456789abcdef0123456789abcdef"
ID_FIELDS = ("request_id", "session_id", "scenario_id", "scenario_version")
# Shapes an id field must never accept. The API-key-shaped value is built at run
# time so the secret scanner does not flag this file.
LEAKY_IDS = (
    "Xk3vQ9pL2mN8rT5wY7zA1bC4dE6f",  # Firebase-UID-shaped, 28 characters
    "i_feel_hopeless_about_my_mother",  # a sentence squashed into a slug
    "AIza" + "0" * 35,  # Google-API-key-shaped
)


def test_allowed_identifiers_and_counts_are_kept(capsys):
    log_event(
        "session_started",
        request_id=SYNTHETIC_UUID,
        session_id=SYNTHETIC_HEX,
        scenario_id="resistant_client",
        scenario_version="1.4.0",
        completed=3,
        failed=0,
        overdue=1,
    )

    line = only_line(capsys)
    assert line["request_id"] == SYNTHETIC_UUID
    assert line["session_id"] == SYNTHETIC_HEX
    assert line["scenario_id"] == "resistant_client"
    assert line["scenario_version"] == "1.4.0"
    assert (line["completed"], line["failed"], line["overdue"]) == (3, 0, 1)


@pytest.mark.parametrize("field", ID_FIELDS)
@pytest.mark.parametrize("value", LEAKY_IDS)
def test_a_uid_slug_or_key_shaped_value_is_dropped_from_every_id_field(
    capsys, field, value
):
    fields: dict[str, Any] = {field: value}
    log_event("check_id", **fields)

    out = capsys.readouterr().out
    assert value not in out
    assert field not in json.loads(out)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("request_id", SYNTHETIC_UUID.upper()),
        ("request_id", SYNTHETIC_HEX[:31]),
        ("session_id", SYNTHETIC_UUID + "\n"),
        ("session_id", "{" + SYNTHETIC_UUID + "}"),
        ("scenario_id", "resistant-client"),
        ("scenario_id", "Resistant_client"),
        ("scenario_id", "resistant_client "),
        ("scenario_id", "resistant_client_v2"),
        ("scenario_id", "crisis"),
        ("scenario_id", "anxious_new_student"),  # slug-shaped, not in the catalogue
        ("scenario_version", "v1.4.0"),
        ("scenario_version", "1.4"),
        ("scenario_version", "12345.0.0"),
        ("scenario_version", "\u0661.0.0"),  # an Arabic-Indic digit
    ],
)
def test_an_id_outside_its_exact_shape_is_dropped(capsys, field, value):
    fields: dict[str, Any] = {field: value}
    log_event("check_id", **fields)

    assert field not in only_line(capsys)


@pytest.mark.parametrize(
    "scenario_id", ["routine_intake", "resistant_client", "crisis_risk"]
)
def test_each_catalogue_scenario_id_is_kept(capsys, scenario_id):
    log_event("check_id", scenario_id=scenario_id)

    assert only_line(capsys)["scenario_id"] == scenario_id


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("session_id", SYNTHETIC_TURN),
        ("session_id", ""),
        ("session_id", 42),
        ("request_id", [SYNTHETIC_UUID]),
        ("status_code", "500"),
        ("status_code", True),
        ("status_code", 99),
        ("status_code", 600),
        ("completed", 2.0),
        ("failed", -1),
        ("overdue", False),
        ("duration_ms", "12"),
        ("duration_ms", -0.5),
        ("duration_ms", float("nan")),
        ("duration_ms", float("inf")),
        ("duration_ms", True),
        ("completed", 2**63),
        ("duration_ms", 2**63),
        ("duration_ms", 1e300),
    ],
)
def test_a_wrong_typed_or_malformed_value_is_dropped(capsys, field, value):
    log_event("check_value", **{field: value})

    line = only_line(capsys)
    assert field not in line
    assert "hopeless" not in json.dumps(line)


@pytest.mark.parametrize("field", ["completed", "failed", "overdue", "duration_ms"])
def test_a_number_too_large_to_serialise_is_dropped_without_raising(capsys, field):
    # 10**5000 exceeds Python's int-to-str digit limit, so json.dumps would raise.
    fields: dict[str, Any] = {field: 10**5000, "status_code": 200}
    log_event("check_value", **fields)

    line = only_line(capsys)
    assert field not in line
    assert line["status_code"] == 200


def test_an_integer_duration_is_kept(capsys):
    log_event("request_completed", duration_ms=40)

    assert only_line(capsys)["duration_ms"] == 40


@pytest.mark.parametrize(
    "event", [SYNTHETIC_TURN, "Turn Received", "", "x" * 65, "9starts_with_digit"]
)
def test_an_invalid_event_name_is_replaced_and_never_emitted(capsys, event):
    log_event(event)

    line = only_line(capsys)
    assert line["event"] == line["message"] == "invalid_event"
    assert "hopeless" not in json.dumps(line)


def test_an_unknown_severity_falls_back_to_default(capsys):
    log_event("check_severity", severity="LOUD")  # type: ignore[arg-type]

    assert only_line(capsys)["severity"] == "DEFAULT"


def test_the_helper_cannot_be_used_to_set_reserved_keys(capsys):
    log_event(
        "check_reserved",
        message=SYNTHETIC_TURN,
        error_class="ValueError",
        error_code="forged",
    )

    line = only_line(capsys)
    assert line["message"] == "check_reserved"
    assert "error_class" not in line and "error_code" not in line


def test_an_error_logs_only_the_class_name_and_stable_code(capsys):
    try:
        raise ValueError(SYNTHETIC_TURN)
    except ValueError as exc:
        log_error("turn_failed", exc, code="persona_unavailable", status_code=503)

    out = capsys.readouterr().out
    assert "hopeless" not in out and "Traceback" not in out
    assert json.loads(out) == {
        "severity": "ERROR",
        "message": "turn_failed",
        "event": "turn_failed",
        "status_code": 503,
        "error_class": "ValueError",
        "error_code": "persona_unavailable",
    }


def test_an_error_ignores_caller_supplied_class_and_chained_causes(capsys):
    class TurnError(Exception):
        pass

    try:
        try:
            raise KeyError(SYNTHETIC_TURN)
        except KeyError as cause:
            raise TurnError(SYNTHETIC_TURN) from cause
    except TurnError as exc:
        exc.add_note(SYNTHETIC_TURN)
        log_error("turn_failed", exc, code="internal_error", error_class="KeyError")

    line = only_line(capsys)
    assert line["error_class"] == "TurnError"
    assert "hopeless" not in json.dumps(line)


def test_a_malformed_error_code_is_replaced(capsys):
    log_error("turn_failed", RuntimeError(), code=SYNTHETIC_TURN)

    line = only_line(capsys)
    assert line["error_code"] == "invalid_code"
    assert "hopeless" not in json.dumps(line)


def test_a_closed_stdout_never_breaks_the_caller(monkeypatch):
    class ClosedStream:
        def write(self, text: str) -> int:
            raise ValueError("I/O operation on closed file.")

        def flush(self) -> None:
            raise ValueError("I/O operation on closed file.")

    monkeypatch.setattr("sys.stdout", ClosedStream())

    log_event("still_running")


class FakeServer:
    """Records what a middleware sends; ``fail_sends`` makes every send raise."""

    def __init__(self, fail_sends: bool = False) -> None:
        self.sent: list[dict[str, Any]] = []
        self.fail_sends = fail_sends

    async def receive(self) -> dict[str, Any]:
        return {"type": "http.request", "body": b""}

    async def send(self, message: Any) -> None:
        if self.fail_sends:
            raise OSError("client went away")
        self.sent.append(dict(message))


def run_middleware(app: Any, scope_type: str, server: FakeServer) -> None:
    middleware = ContentFreeErrors(app)
    asyncio.run(middleware({"type": scope_type}, server.receive, server.send))


async def turn_echoing_app(scope: Any, receive: Any, send: Any) -> None:
    raise ValueError(SYNTHETIC_TURN)


def assert_logged_by_class_only(
    capsys: pytest.CaptureFixture[str], **expected: object
) -> None:
    captured = capsys.readouterr()
    for text in (captured.out, captured.err):
        assert "hopeless" not in text and "Traceback" not in text
    assert json.loads(captured.out) == {
        "severity": "ERROR",
        "message": "unhandled_error",
        "event": "unhandled_error",
        "error_class": "ValueError",
        **expected,
    }


def test_an_unhandled_http_error_gets_the_raw_generic_500(capsys):
    server = FakeServer()
    run_middleware(turn_echoing_app, "http", server)

    start, body = server.sent
    assert start["type"] == "http.response.start" and start["status"] == 500
    headers = dict(start["headers"])
    assert headers[b"content-type"] == b"application/json"
    assert int(headers[b"content-length"]) == len(body["body"])
    assert json.loads(body["body"]) == {"detail": "Internal server error."}
    assert_logged_by_class_only(capsys, status_code=500, error_code="internal_error")


def test_an_error_after_the_response_started_sends_nothing_more(capsys):
    async def streaming_app(scope: Any, receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise ValueError(SYNTHETIC_TURN)

    server = FakeServer()
    run_middleware(streaming_app, "http", server)

    assert [message["type"] for message in server.sent] == ["http.response.start"]
    assert_logged_by_class_only(capsys, error_code="internal_error_after_start")


def test_an_unhandled_websocket_error_closes_with_1011(capsys):
    async def socket_app(scope: Any, receive: Any, send: Any) -> None:
        await send({"type": "websocket.accept"})
        raise ValueError(SYNTHETIC_TURN)

    server = FakeServer()
    run_middleware(socket_app, "websocket", server)

    assert server.sent == [
        {"type": "websocket.accept"},
        {"type": "websocket.close", "code": 1011},
    ]
    assert_logged_by_class_only(capsys, error_code="internal_error")


@pytest.mark.parametrize("scope_type", ["http", "websocket"])
def test_a_failed_error_reply_never_raises_or_chains_the_original(capsys, scope_type):
    # A raise here would print a traceback with the turn as its context.
    run_middleware(turn_echoing_app, scope_type, FakeServer(fail_sends=True))

    captured = capsys.readouterr()
    assert "hopeless" not in captured.out + captured.err
    assert json.loads(captured.out)["error_class"] == "ValueError"


def mixed_group_app(started: bool) -> Any:
    async def app(scope: Any, receive: Any, send: Any) -> None:
        if started:
            await send({"type": "http.response.start", "status": 200, "headers": []})
        raise BaseExceptionGroup(
            SYNTHETIC_TURN,
            [asyncio.CancelledError(), ValueError(SYNTHETIC_TURN)],
        )

    return app


@pytest.mark.parametrize(
    ("scope_type", "started", "sent", "expected"),
    [
        (
            "http",
            False,
            ["http.response.start", "http.response.body"],
            {"status_code": 500, "error_code": "internal_error"},
        ),
        (
            "http",
            True,
            ["http.response.start"],
            {"error_code": "internal_error_after_start"},
        ),
        ("websocket", False, ["websocket.close"], {"error_code": "internal_error"}),
    ],
)
def test_a_group_re_raises_only_the_cancellation_without_content(
    capsys, scope_type, started, sent, expected
):
    server = FakeServer()
    with pytest.raises(BaseExceptionGroup) as raised:
        run_middleware(mixed_group_app(started), scope_type, server)

    group = raised.value
    assert [type(leaf) for leaf in group.exceptions] == [asyncio.CancelledError]
    printed = "".join(traceback.format_exception(group))
    assert "hopeless" not in printed and SYNTHETIC_TURN not in printed
    assert [message["type"] for message in server.sent] == sent
    captured = capsys.readouterr()
    assert "hopeless" not in captured.out + captured.err
    line = json.loads(captured.out)
    assert line["error_class"] == "ExceptionGroup"
    assert {key: line[key] for key in expected} == expected


def test_a_nested_group_and_a_chained_cancellation_print_no_content(capsys):
    async def app(scope: Any, receive: Any, send: Any) -> None:
        try:
            raise ValueError(SYNTHETIC_TURN)
        except ValueError:
            cancelled = asyncio.CancelledError()
            try:
                raise cancelled
            except asyncio.CancelledError as chained:
                cancelled = chained
        inner = BaseExceptionGroup(SYNTHETIC_TURN, [cancelled])
        raise BaseExceptionGroup(SYNTHETIC_TURN, [inner, KeyError(SYNTHETIC_TURN)])

    with pytest.raises(BaseExceptionGroup) as raised:
        run_middleware(app, "http", FakeServer())

    assert [type(leaf) for leaf in raised.value.exceptions] == [asyncio.CancelledError]
    printed = "".join(traceback.format_exception(raised.value))
    assert "hopeless" not in printed
    assert "hopeless" not in capsys.readouterr().out


def test_a_group_of_plain_errors_is_handled_like_one_error(capsys):
    async def app(scope: Any, receive: Any, send: Any) -> None:
        raise ExceptionGroup(
            SYNTHETIC_TURN, [ValueError(SYNTHETIC_TURN), KeyError(SYNTHETIC_TURN)]
        )

    server = FakeServer()
    run_middleware(app, "http", server)

    assert server.sent[0]["status"] == 500
    captured = capsys.readouterr()
    assert "hopeless" not in captured.out + captured.err
    line = json.loads(captured.out)
    assert (line["error_class"], line["status_code"]) == ("ExceptionGroup", 500)


def test_other_scopes_pass_through_untouched():
    seen: list[str] = []

    async def lifespan_app(scope: Any, receive: Any, send: Any) -> None:
        seen.append(scope["type"])

    run_middleware(lifespan_app, "lifespan", FakeServer())

    assert seen == ["lifespan"]
