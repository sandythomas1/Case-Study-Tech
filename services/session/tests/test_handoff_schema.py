"""The committed JSON Schema matches the models (#66 AC3)."""

import json
import re

import pytest

from cst_session.handoff import (
    CONTRACT,
    CONTRACT_VERSION,
    HandoffRejected,
    json_schema,
    validate_handoff,
)
from cst_session.handoff.export import SCHEMA_PATH, schema_text
from tests.handoff_fixtures import routine


def test_the_committed_schema_matches_the_models() -> None:
    committed = SCHEMA_PATH.read_text(encoding="utf-8")
    assert committed == schema_text(), (
        "handoff/completed-session.v1.schema.json is stale. Run "
        "`uv run python -m cst_session.handoff.export` in services/session."
    )


def test_the_schema_names_its_contract_and_version() -> None:
    schema = json_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["contract"]["const"] == CONTRACT
    assert schema["properties"]["contract_version"]["const"] == CONTRACT_VERSION
    assert schema["properties"]["status"]["const"] == "completed"


def test_the_schema_refuses_unknown_fields_at_every_level() -> None:
    schema = json_schema()
    objects = [schema, *schema["$defs"].values()]
    assert all(item["additionalProperties"] is False for item in objects)


def test_every_field_is_required() -> None:
    schema = json_schema()
    for item in [schema, *schema["$defs"].values()]:
        assert set(item["required"]) == set(item["properties"])


def test_student_turns_carry_per_turn_reliability_flags() -> None:
    student = json_schema()["$defs"]["StudentTurn"]["properties"]
    assert student["input"]["enum"] == ["text", "speech"]
    assert student["uncertain_recognition"]["type"] == "boolean"


def test_the_schema_file_is_plain_ascii_json() -> None:
    raw = SCHEMA_PATH.read_bytes()
    assert raw.isascii()
    assert json.loads(raw) == json_schema()


def test_the_save_choice_is_a_required_boolean() -> None:
    schema = json_schema()
    assert schema["properties"]["save_transcript"]["type"] == "boolean"
    assert "default" not in schema["properties"]["save_transcript"]
    assert "save_transcript" in schema["required"]


@pytest.mark.parametrize(
    ("text", "valid"),
    [
        ("Okay.", True),
        ("Okay\u200b.", True),
        ("Family \U0001f469\u200d\U0001f467", True),
        ("pay \u202eemos\u202c now", False),
        ("\ufeffhello", False),
        ("\u200b\u2060\u3164", False),
        ("\u00ad\u034f\u061c\ufe0f", False),
        ("\U000e0041\U000e0042", False),
        ("\U0001d173\U000e0100", False),
        (
            "Flag \U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f",
            True,
        ),
        ("hello\x00", False),
        (" \t\n", False),
    ],
)
def test_the_schema_text_pattern_agrees_with_the_validator(
    text: str, valid: bool
) -> None:
    # A consumer that has only the schema enforces the same text rule. Python's
    # re reads the same escapes as ECMA-262 and Rust here.
    turn = json_schema()["$defs"]["StudentTurn"]["properties"]["text"]
    assert (re.fullmatch(turn["pattern"], text) is not None) is valid
    payload = routine()
    payload["turns"][0]["text"] = text
    try:
        validate_handoff(payload)
        accepted = True
    except HandoffRejected:
        accepted = False
    assert accepted is valid


def test_the_session_id_is_bounded_in_length() -> None:
    session_id = json_schema()["properties"]["session_id"]
    assert (session_id["minLength"], session_id["maxLength"]) == (36, 36)
