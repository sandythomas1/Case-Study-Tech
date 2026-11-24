"""The handoff contract accepts only a completed session (#66 AC1, RC-09, SCO-1)."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from cst_session.handoff import (
    CompletedSession,
    HandoffRejected,
    RejectionReason,
    encode_handoff,
    parse_handoff,
    validate_handoff,
)
from cst_session.handoff.contract import MAX_TURN_CHARACTERS, MAX_TURNS, StudentTurn
from cst_session.handoff.validation import MAX_BODY_BYTES
from tests.handoff_fixtures import (
    ACCEPTED,
    REJECTED,
    crisis,
    expected_reason,
    load,
    routine,
    voice,
)

Payload = dict[str, Any]


def _reason(payload: object) -> RejectionReason:
    with pytest.raises(HandoffRejected) as caught:
        validate_handoff(payload)
    return caught.value.reason


def test_there_is_a_fixture_per_scenario_and_per_rejection_reason() -> None:
    scenarios = {load(path)["scenario"]["id"] for path in ACCEPTED}
    assert scenarios == {"routine_intake", "resistant_client", "crisis_risk"}
    assert {expected_reason(path) for path in REJECTED} == set(RejectionReason)


@pytest.mark.parametrize("path", ACCEPTED, ids=lambda path: path.stem)
def test_completed_fixtures_are_accepted(path: Path) -> None:
    session = validate_handoff(load(path))
    assert isinstance(session, CompletedSession)
    assert session.status == "completed"


@pytest.mark.parametrize("path", REJECTED, ids=lambda path: path.stem)
def test_rejected_fixtures_fail_with_their_reason(path: Path) -> None:
    assert _reason(load(path)) == expected_reason(path)


@pytest.mark.parametrize("path", ACCEPTED, ids=lambda path: path.stem)
def test_parsing_the_raw_body_gives_the_same_session(path: Path) -> None:
    assert parse_handoff(path.read_bytes()) == validate_handoff(load(path))


def test_per_turn_reliability_flags_reach_the_grader() -> None:
    session = validate_handoff(voice())
    flags = [
        (turn.index, turn.input, turn.uncertain_recognition)
        for turn in session.turns
        if isinstance(turn, StudentTurn)
    ]
    assert flags == [
        (1, "speech", False),
        (3, "speech", True),
        (5, "speech", False),
        (7, "text", False),
    ]


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        ("incomplete", RejectionReason.INCOMPLETE),
        ("content_lost", RejectionReason.CONTENT_LOST),
        ("ended_for_conduct", RejectionReason.ENDED_FOR_CONDUCT),
    ],
)
def test_a_status_reason_wins_even_when_the_rest_is_broken(
    status: str, reason: RejectionReason
) -> None:
    payload = routine()
    payload["status"] = status
    payload["turns"] = []
    assert _reason(payload) == reason


def test_a_wrong_version_wins_over_a_broken_body() -> None:
    payload = {"contract": "cst.completed_session", "contract_version": "1.1.0"}
    assert _reason(payload) == RejectionReason.VERSION_MISMATCH


@pytest.mark.parametrize("version", [None, 1, "1.0", "", "v1.0.0"])
def test_a_missing_or_unknown_version_is_a_version_mismatch(version: object) -> None:
    payload = routine()
    payload["contract_version"] = version
    assert _reason(payload) == RejectionReason.VERSION_MISMATCH


@pytest.mark.parametrize(
    "payload",
    [None, [], "completed", 1, {}, {"contract": "cst.report"}],
    ids=["null", "list", "string", "number", "empty", "other-contract"],
)
def test_input_that_is_not_this_contract_is_malformed(payload: object) -> None:
    assert _reason(payload) == RejectionReason.MALFORMED


@pytest.mark.parametrize("status", [None, "", "Completed", "graded", 1])
def test_an_unknown_status_is_malformed(status: object) -> None:
    payload = routine()
    payload["status"] = status
    assert _reason(payload) == RejectionReason.MALFORMED


def _set(path: tuple[str | int, ...], value: object) -> Callable[[Payload], None]:
    def change(payload: Payload) -> None:
        target: Any = payload
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def _drop(key: str) -> Callable[[Payload], None]:
    return lambda payload: payload.pop(key)


def _turns(count: int) -> Callable[[Payload], None]:
    def change(payload: Payload) -> None:
        first = payload["turns"][0]
        payload["turns"] = [
            {**first, "index": n, "at_ms": n} for n in range(1, count + 1)
        ]
        payload["duration_ms"] = count

    return change


MALFORMED_CHANGES: dict[str, Callable[[Payload], None]] = {
    "missing session id": _drop("session_id"),
    "uppercase session id": _set(
        ("session_id",), "00000000-0000-4000-8000-00000000010A"
    ),
    "session id not a uuid": _set(("session_id",), "session-101"),
    "missing owner uid": _drop("owner_uid"),
    "empty owner uid": _set(("owner_uid",), ""),
    "owner uid with a path": _set(("owner_uid",), "../synthStudent0001"),
    "owner uid too long": _set(("owner_uid",), "a" * 129),
    "unknown scenario": _set(("scenario", "id"), "routine-intake"),
    "scenario version not semver": _set(("scenario", "version"), "1.0"),
    "unknown modality": _set(("modality",), "video"),
    "unknown ending": _set(("ended_by",), "grader"),
    "negative duration": _set(("duration_ms",), -1),
    "duration over an hour": _set(("duration_ms",), 3_600_001),
    "no turns": _set(("turns",), []),
    "too many turns": _turns(MAX_TURNS + 1),
    "turns start at zero": _set(("turns", 0, "index"), 0),
    "turns out of order": _set(("turns", 1, "index"), 3),
    "turn time goes backwards": _set(("turns", 2, "at_ms"), 1),
    "turn after the session ended": _set(("duration_ms",), 1),
    "unknown speaker": _set(("turns", 0, "speaker"), "counselor"),
    "client turn with student flags": _set(("turns", 1, "conduct_warning"), False),
    "student turn missing a flag": lambda payload: payload["turns"][0].pop(
        "uncertain_recognition"
    ),
    "empty text": _set(("turns", 0, "text"), ""),
    "whitespace text": _set(("turns", 0, "text"), " \n\t "),
    "text with a control character": _set(("turns", 0, "text"), "hello\x00there"),
    "text with a carriage return": _set(("turns", 0, "text"), "hello\rthere"),
    "text with a c1 control": _set(("turns", 0, "text"), "hello\x85there"),
    "text too long": _set(("turns", 0, "text"), "a" * (MAX_TURN_CHARACTERS + 1)),
    "typed turn marked uncertain": _set(("turns", 0, "uncertain_recognition"), True),
    "warning count without a flagged turn": _set(("conduct", "warnings"), 1),
    "flagged turn without a warning count": _set(("turns", 0, "conduct_warning"), True),
    "crisis flags outside the crisis scenario": _set(("crisis",), {"opted_in": True}),
    "crisis key missing": _drop("crisis"),
    "index as a string": _set(("turns", 0, "index"), "1"),
    "index as a float": _set(("turns", 0, "index"), 1.0),
    "flag as a number": _set(("turns", 0, "conduct_warning"), 0),
    "duration as a bool": _set(("duration_ms",), True),
    "extra turn field": _set(("turns", 0, "audio"), "synthetic"),
    "session id with a trailing newline": _set(
        ("session_id",), "00000000-0000-4000-8000-000000000101\n"
    ),
    "missing save choice": _drop("save_transcript"),
    "save choice as a string": _set(("save_transcript",), "false"),
    "save choice as a number": _set(("save_transcript",), 0),
    "save choice as null": _set(("save_transcript",), None),
    "text with a bidi override": _set(("turns", 0, "text"), "pay ‮emos‬ now"),
    "text with a bidi isolate": _set(("turns", 0, "text"), "hello ⁧there⁩"),
    "text with a byte-order mark": _set(("turns", 0, "text"), "﻿hello"),
    "zero-width-space-only text": _set(("turns", 0, "text"), "​​"),
    "word-joiner-only text": _set(("turns", 0, "text"), " ⁠ "),
    "filler-letter-only text": _set(("turns", 0, "text"), "ㅤ⠀"),
}


@pytest.mark.parametrize("change", MALFORMED_CHANGES.values(), ids=MALFORMED_CHANGES)
def test_a_structurally_invalid_completed_session_is_malformed(
    change: Callable[[Payload], None],
) -> None:
    payload = routine()
    change(payload)
    assert _reason(payload) == RejectionReason.MALFORMED


def test_two_conduct_warnings_are_malformed() -> None:
    payload = voice()
    payload["turns"][2]["conduct_warning"] = True
    payload["conduct"]["warnings"] = 2
    assert _reason(payload) == RejectionReason.MALFORMED


@pytest.mark.parametrize("crisis_flags", [None, {"opted_in": False}, {}])
def test_the_crisis_scenario_requires_the_opt_in(crisis_flags: object) -> None:
    payload = crisis()
    payload["crisis"] = crisis_flags
    assert _reason(payload) == RejectionReason.MALFORMED


def test_a_voice_session_may_fall_back_to_typed_turns() -> None:
    payload = voice()
    for turn in payload["turns"]:
        if turn["speaker"] == "student":
            turn["input"] = "text"
            turn["uncertain_recognition"] = False
    assert validate_handoff(payload).modality == "voice"


def test_turns_may_share_a_start_time_and_the_limits_are_inclusive() -> None:
    payload = routine()
    payload["turns"][1]["at_ms"] = payload["turns"][0]["at_ms"]
    payload["turns"][0]["text"] = "a" * MAX_TURN_CHARACTERS
    payload["duration_ms"] = payload["turns"][-1]["at_ms"]
    assert validate_handoff(payload).duration_ms == payload["turns"][-1]["at_ms"]


def test_tabs_newlines_and_non_latin_text_are_allowed() -> None:
    payload = routine()
    payload["turns"][0]["text"] = "Line one\n\tLine two, déjà vu, 你好"
    assert validate_handoff(payload).turns[0].text == payload["turns"][0]["text"]


@pytest.mark.parametrize(
    "text",
    [
        "می‌خواهم",
        "Family \U0001f469‍\U0001f469‍\U0001f467 photo",
        "שלום ‏ok",
        "Okay​.",
    ],
    ids=["persian-zwnj", "emoji-zwj", "rtl-mark", "visible-with-zero-width"],
)
def test_joiners_and_marks_are_allowed_beside_visible_text(text: str) -> None:
    payload = routine()
    payload["turns"][0]["text"] = text
    assert validate_handoff(payload).turns[0].text == text


@pytest.mark.parametrize("path", ACCEPTED, ids=lambda path: path.stem)
def test_the_save_choice_reaches_the_grader(path: Path) -> None:
    payload = load(path)
    assert validate_handoff(payload).save_transcript is payload["save_transcript"]


def test_a_session_marked_dont_save_is_still_graded() -> None:
    session = validate_handoff(voice())
    assert session.save_transcript is False
    assert session.status == "completed"


def test_the_maximum_number_of_turns_is_accepted() -> None:
    payload = routine()
    _turns(MAX_TURNS)(payload)
    assert len(validate_handoff(payload).turns) == MAX_TURNS


def test_an_accepted_session_cannot_be_changed() -> None:
    session = validate_handoff(routine())
    with pytest.raises(ValueError, match="frozen"):
        session.owner_uid = "someoneElse"  # type: ignore[misc]


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"not json",
        b"\xff\xfe",
        b'{"contract": "cst.completed_session", "contract": "x"}',
        b'{"duration_ms": NaN}',
        b'{"duration_ms": Infinity}',
        b"[" * 100_000,
    ],
    ids=[
        "empty",
        "not-json",
        "not-utf8",
        "duplicate-key",
        "nan",
        "infinity",
        "too-deep",
    ],
)
def test_a_body_that_is_not_plain_json_is_malformed(body: bytes) -> None:
    with pytest.raises(HandoffRejected) as caught:
        parse_handoff(body)
    assert caught.value.reason == RejectionReason.MALFORMED


def test_a_duplicate_key_cannot_hide_a_status() -> None:
    body = json.dumps(routine())[:-1] + ', "status": "content_lost"}'
    with pytest.raises(HandoffRejected) as caught:
        parse_handoff(body.encode())
    assert caught.value.reason == RejectionReason.MALFORMED


@pytest.mark.parametrize(
    "encoding", ["utf-8-sig", "utf-16", "utf-16-le", "utf-32"], ids=str
)
def test_a_body_that_is_not_plain_utf8_is_malformed(encoding: str) -> None:
    body = json.dumps(routine()).encode(encoding)
    with pytest.raises(HandoffRejected) as caught:
        parse_handoff(body)
    assert caught.value.reason == RejectionReason.MALFORMED


@pytest.mark.parametrize("path", ACCEPTED, ids=lambda path: path.stem)
def test_an_encoded_session_parses_back_to_itself(path: Path) -> None:
    session = validate_handoff(load(path))
    assert parse_handoff(encode_handoff(session)) == session


@pytest.mark.parametrize("character", ["a", "é", "你", "\U0001f600"])
def test_the_largest_valid_session_fits_the_body_cap(character: str) -> None:
    # 500 turns of 2,000 characters, up to four UTF-8 bytes each, must reach
    # the grader. A cap below the contract's own limits would turn a valid
    # session into a malformed one.
    payload = routine()
    _turns(MAX_TURNS)(payload)
    for turn in payload["turns"]:
        turn["text"] = character * MAX_TURN_CHARACTERS
    body = encode_handoff(validate_handoff(payload))
    assert len(body) <= MAX_BODY_BYTES
    assert len(parse_handoff(body).turns) == MAX_TURNS


def test_the_encoder_writes_raw_utf8() -> None:
    payload = routine()
    payload["turns"][0]["text"] = "déjà vu 你好"
    body = encode_handoff(validate_handoff(payload))
    assert b"\\u" not in body
    assert "déjà vu 你好".encode() in body


def test_an_oversized_body_is_malformed_before_it_is_decoded() -> None:
    with pytest.raises(HandoffRejected) as caught:
        parse_handoff(b" " * (MAX_BODY_BYTES + 1))
    assert caught.value.reason == RejectionReason.MALFORMED


@pytest.mark.parametrize("path", REJECTED, ids=lambda path: path.stem)
def test_a_rejection_carries_only_its_reason(path: Path) -> None:
    with pytest.raises(HandoffRejected) as caught:
        parse_handoff(path.read_bytes())
    rejection = caught.value
    assert str(rejection) == expected_reason(path)
    assert rejection.args == (expected_reason(path),)
    assert rejection.__cause__ is None
    assert rejection.__context__ is None
