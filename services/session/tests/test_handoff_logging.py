"""Validating a handoff logs no session content (#66 AC2, DAT-1, DAT-7, AG-2)."""

import contextlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from cst_session.handoff import HandoffRejected, parse_handoff
from cst_session.handoff.contract import CompletedSession
from tests.handoff_fixtures import ACCEPTED, REJECTED, expected_reason, load, routine
from tests.test_handoff_contract import MALFORMED_CHANGES


def _content(payload: dict[str, Any]) -> list[str]:
    """Every value that must never reach a log: turn text and the owner UID."""
    texts = [turn["text"] for turn in payload.get("turns", [])]
    return [*texts, payload["owner_uid"]]


def _logged(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    captured = capsys.readouterr()
    assert captured.err == ""
    return [json.loads(line) for line in captured.out.splitlines()]


@pytest.mark.parametrize("path", ACCEPTED + REJECTED, ids=lambda path: path.stem)
def test_validating_a_fixture_logs_no_turn_text_or_owner_uid(
    path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = load(path)
    with contextlib.suppress(HandoffRejected):
        parse_handoff(path.read_bytes())
    output = capsys.readouterr()
    assert output.err == ""
    for value in _content(payload):
        assert value not in output.out


@pytest.mark.parametrize("path", ACCEPTED, ids=lambda path: path.stem)
def test_an_accepted_session_logs_one_content_free_event(
    path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = load(path)
    parse_handoff(path.read_bytes())
    assert _logged(capsys) == [
        {
            "severity": "INFO",
            "message": "handoff_accepted",
            "event": "handoff_accepted",
            "session_id": payload["session_id"],
            "duration_ms": payload["duration_ms"],
        }
    ]


@pytest.mark.parametrize("path", REJECTED, ids=lambda path: path.stem)
def test_a_rejection_logs_its_reason_and_the_session_id_only(
    path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = load(path)
    with pytest.raises(HandoffRejected):
        parse_handoff(path.read_bytes())
    event = f"handoff_rejected_{expected_reason(path)}"
    assert _logged(capsys) == [
        {
            "severity": "WARNING",
            "message": event,
            "event": event,
            "session_id": payload["session_id"],
        }
    ]


def test_a_session_id_that_is_not_an_id_is_not_logged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = routine()
    payload["session_id"] = payload["turns"][0]["text"]
    with pytest.raises(HandoffRejected):
        parse_handoff(json.dumps(payload).encode())
    assert _logged(capsys) == [
        {
            "severity": "WARNING",
            "message": "handoff_rejected_malformed",
            "event": "handoff_rejected_malformed",
        }
    ]


@pytest.mark.parametrize("change", MALFORMED_CHANGES.values(), ids=MALFORMED_CHANGES)
def test_a_malformed_session_logs_no_turn_text_or_owner_uid(
    change: Callable[[dict[str, Any]], None], capsys: pytest.CaptureFixture[str]
) -> None:
    payload = routine()
    content = _content(payload)
    change(payload)
    content += [turn["text"] for turn in payload["turns"] if turn.get("text")]
    with pytest.raises(HandoffRejected):
        parse_handoff(json.dumps(payload).encode())
    output = capsys.readouterr()
    assert output.err == ""
    for value in content:
        assert value not in output.out


def test_a_body_that_cannot_be_decoded_logs_only_the_reason(
    capsys: pytest.CaptureFixture[str],
) -> None:
    truncated = json.dumps(routine()).encode()[:-1]
    with pytest.raises(HandoffRejected):
        parse_handoff(truncated)
    assert _logged(capsys) == [
        {
            "severity": "WARNING",
            "message": "handoff_rejected_malformed",
            "event": "handoff_rejected_malformed",
        }
    ]


def test_validation_errors_never_echo_the_input() -> None:
    payload = routine()
    payload["turns"][0]["text"] = "Synthetic secret line\x00"
    payload["owner_uid"] = "synthOwner/../x"
    with pytest.raises(ValidationError) as caught:
        CompletedSession.model_validate(payload)
    rendered = str(caught.value) + repr(caught.value.errors(include_input=False))
    assert "Synthetic secret line" not in rendered
    assert "synthOwner" not in rendered


def test_raw_error_details_still_hold_the_input_so_validation_discards_them() -> None:
    # hide_input_in_errors covers str() only. .errors() returns the raw input,
    # which is why validate_handoff drops the ValidationError and raises a bare
    # reason instead. If this starts failing, pydantic changed and the comment
    # in validation.py should be revisited.
    payload = routine()
    payload["turns"][0]["text"] = "Synthetic secret line\x00"
    with pytest.raises(ValidationError) as caught:
        CompletedSession.model_validate(payload)
    assert "Synthetic secret line" in repr(caught.value.errors())


def test_the_repr_of_a_session_leaves_out_text_and_the_owner_uid() -> None:
    payload = routine()
    session = parse_handoff(json.dumps(payload).encode())
    rendered = repr(session) + str(session)
    assert "session_id=" in rendered
    for value in _content(payload):
        assert value not in rendered
