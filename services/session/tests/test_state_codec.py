"""The signed state resists forgery and tampering (T1, FR-3, FR-4).

Every malformed, tampered or re-keyed token is the same ``state_invalid``. The
MAC is checked before anything is decoded or parsed, with
``hmac.compare_digest``, and the size caps hold in both directions (T9).
"""

import hmac
import json
from typing import Any

import pytest

from cst_session import state as state_module
from cst_session.state import (
    MAX_STATE_CHARS,
    MAX_STATE_TURNS,
    Rejection,
    SessionState,
    SigningKeyError,
    StateCodec,
    StateRejected,
    StateTooLarge,
    StateTurn,
)
from tests.state_fixtures import (
    KEY,
    OTHER_KEY,
    b64,
    encode_json,
    forge,
    payload_json,
    state,
    tag_for,
)

CODEC = StateCodec(KEY)


def rejected(token: object) -> StateRejected:
    with pytest.raises(StateRejected) as caught:
        CODEC.verify(token)
    error = caught.value
    assert error.reason is Rejection.INVALID
    assert error.code == "state_invalid" == str(error)
    assert error.__cause__ is None and error.__context__ is None
    return error


def parts(token: str) -> tuple[str, str, str]:
    prefix, payload_b64, tag_b64 = token.split(".")
    return prefix, payload_b64, tag_b64


def flip(text: str, index: int) -> str:
    replacement = "B" if text[index] != "B" else "C"
    return text[:index] + replacement + text[index + 1 :]


# Signing and the format


def test_t1_a_signed_state_verifies_to_an_equal_state() -> None:
    original = state()

    assert CODEC.verify(CODEC.sign(original)) == original


def test_t1_the_token_is_v1_payload_tag_with_a_domain_separated_hmac() -> None:
    token = CODEC.sign(state())
    prefix, payload_b64, tag_b64 = parts(token)

    assert prefix == "v1"
    assert "=" not in token
    assert tag_b64 == tag_for(payload_b64)
    payload = json.loads(state_module._strict_b64decode(payload_b64) or b"")
    assert payload == state().model_dump(mode="json")


def test_t1_signing_is_deterministic() -> None:
    assert CODEC.sign(state()) == CODEC.sign(state())


def test_t1_the_codec_needs_a_32_byte_key() -> None:
    for key in (b"", KEY[:31], KEY + b"\x00", "not-bytes"):
        with pytest.raises(SigningKeyError):
            StateCodec(key)  # type: ignore[arg-type]


def test_t1_the_codec_repr_hides_the_key() -> None:
    assert KEY.hex() not in repr(CODEC) and repr(KEY) not in repr(CODEC)


def test_t1_the_state_repr_hides_the_uid_and_text() -> None:
    shown = repr(state())

    assert "synthUid001" not in shown
    assert "School has been" not in shown


# Tampering: every case is state_invalid


def tampered_tokens() -> dict[str, str]:
    token = CODEC.sign(state())
    prefix, payload_b64, tag_b64 = parts(token)
    other = CODEC.sign(state(save_transcript=False))
    _, other_payload, other_tag = parts(other)
    return {
        "payload-bit-flip": f"{prefix}.{flip(payload_b64, 10)}.{tag_b64}",
        "payload-last-char": f"{prefix}.{flip(payload_b64, -1)}.{tag_b64}",
        "tag-bit-flip": f"{prefix}.{payload_b64}.{flip(tag_b64, 5)}",
        "tag-last-char": f"{prefix}.{payload_b64}.{flip(tag_b64, -1)}",
        "prefix-v2": f"v2.{payload_b64}.{tag_b64}",
        "prefix-V1": f"V1.{payload_b64}.{tag_b64}",
        "prefix-none": f"none.{payload_b64}.{tag_b64}",
        "prefix-missing": f"{payload_b64}.{tag_b64}",
        "prefix-empty": f".{payload_b64}.{tag_b64}",
        "padded-tag": f"{prefix}.{payload_b64}.{tag_b64}=",
        "padded-payload": f"{prefix}.{payload_b64}=.{tag_b64}",
        "plus-in-payload": f"{prefix}.{payload_b64[:-1]}+.{tag_b64}",
        "slash-in-tag": f"{prefix}.{payload_b64}.{tag_b64[:-1]}/",
        "space-in-payload": f"{prefix}.{payload_b64[:5]} {payload_b64[6:]}.{tag_b64}",
        "truncated-tag": f"{prefix}.{payload_b64}.{tag_b64[:-1]}",
        "empty-tag": f"{prefix}.{payload_b64}.",
        "truncated-payload": f"{prefix}.{payload_b64[:-1]}.{tag_b64}",
        "empty-payload": f"{prefix}..{tag_b64}",
        "extra-part": f"{token}.{tag_b64}",
        "two-parts": f"{prefix}.{payload_b64}",
        "swapped-payload": f"{prefix}.{other_payload}.{tag_b64}",
        "swapped-tag": f"{prefix}.{payload_b64}.{other_tag}",
        "other-key": f"{prefix}.{payload_b64}.{tag_for(payload_b64, OTHER_KEY)}",
        "trailing-newline": token + "\n",
        "leading-space": " " + token,
        "empty": "",
    }


@pytest.mark.parametrize("case", sorted(tampered_tokens()))
def test_t1_a_tampered_token_is_state_invalid(case: str) -> None:
    rejected(tampered_tokens()[case])


@pytest.mark.parametrize("value", [None, 7, b"v1.a.b", ["v1"], {"state": "v1"}])
def test_t1_a_token_that_is_not_text_is_state_invalid(value: object) -> None:
    rejected(value)


ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


@pytest.mark.parametrize("trailing_spaces", [0, 1, 2])
def test_t1_a_non_canonical_payload_encoding_fails_even_with_a_valid_mac(
    trailing_spaces: int,
) -> None:
    body = encode_json(payload_json()) + b" " * trailing_spaces
    while len(body) % 3 == 0:
        body += b" "
    payload_b64 = b64(body)
    assert CODEC.verify(f"v1.{payload_b64}.{tag_for(payload_b64)}") == state()
    # Setting a spare bit of the last character leaves the bytes a lax decoder
    # returns unchanged, so only the round-trip check can catch it.
    variant = payload_b64[:-1] + ALPHABET[ALPHABET.index(payload_b64[-1]) | 1]

    rejected(f"v1.{variant}.{tag_for(variant)}")


def test_t1_a_payload_of_impossible_length_fails_with_a_valid_mac() -> None:
    payload_b64 = b64(encode_json(payload_json()))
    while len(payload_b64) % 4 != 1:
        payload_b64 += "A"

    rejected(f"v1.{payload_b64}.{tag_for(payload_b64)}")


# Under a valid MAC, the payload is still parsed strictly


def duplicate_key_payload() -> bytes:
    body = encode_json(payload_json())
    return body[:-1] + b',"save_transcript":false}'


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(duplicate_key_payload(), id="duplicate-key"),
        pytest.param(encode_json(payload_json(extra="x")), id="extra-key"),
        pytest.param(
            encode_json({k: v for k, v in payload_json().items() if k != "turns"}),
            id="missing-key",
        ),
        pytest.param(
            encode_json(payload_json()).replace(
                b'"conduct_warnings":0', b'"conduct_warnings":NaN'
            ),
            id="nan",
        ),
        pytest.param(
            encode_json(payload_json()).replace(
                b'"conduct_warnings":0', b'"conduct_warnings":Infinity'
            ),
            id="infinity",
        ),
        pytest.param(encode_json(payload_json(crisis_opt_in="true")), id="string-bool"),
        pytest.param(encode_json(payload_json(conduct_warnings=0.0)), id="float-int"),
        pytest.param(encode_json(payload_json(conduct_warnings=2)), id="two-warnings"),
        pytest.param(encode_json(payload_json(modality="voice")), id="voice"),
        pytest.param(encode_json(payload_json(scenario_id="other")), id="scenario"),
        pytest.param(encode_json(payload_json(owner_uid="")), id="empty-uid"),
        pytest.param(encode_json(payload_json(session_id="ABC")), id="session-id"),
        pytest.param(encode_json(payload_json(started_at_ms=-1)), id="negative-start"),
        pytest.param(
            encode_json(
                payload_json(turns=[{"speaker": "client", "text": " ", "at_ms": 0}])
            ),
            id="blank-turn",
        ),
        pytest.param(
            encode_json(
                payload_json(
                    turns=[{"speaker": "x", "text": "hi", "at_ms": 0, "more": 1}]
                )
            ),
            id="bad-turn",
        ),
        pytest.param(encode_json([payload_json()]), id="array"),
        pytest.param(b"\xff\xfe{}", id="not-utf8"),
        pytest.param(b"[" * 100_000, id="deep-nesting"),
        pytest.param(b"", id="empty"),
    ],
)
def test_t1_a_bad_payload_under_a_valid_mac_is_state_invalid(payload: bytes) -> None:
    rejected(forge(payload))


def test_t1_a_valid_payload_under_a_valid_test_mac_verifies() -> None:
    assert CODEC.verify(forge(encode_json(payload_json()))) == state()


# The MAC comes first, and with compare_digest


class Spy:
    def __init__(self, real: Any = None) -> None:
        self.real = real
        self.calls = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        if self.real is None:
            raise AssertionError("must not be called")
        return self.real(*args, **kwargs)


def test_t1_nothing_is_parsed_or_validated_on_a_mac_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loads, validate = Spy(), Spy()
    monkeypatch.setattr(state_module.json, "loads", loads)
    monkeypatch.setattr(SessionState, "model_validate", validate)

    for case, token in tampered_tokens().items():
        with pytest.raises(StateRejected):
            CODEC.verify(token)
        assert (loads.calls, validate.calls) == (0, 0), case


def test_t1_the_tag_is_compared_with_compare_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compare = Spy(hmac.compare_digest)
    monkeypatch.setattr(state_module.hmac, "compare_digest", compare)
    token = CODEC.sign(state())

    CODEC.verify(token)
    assert compare.calls == 1

    with pytest.raises(StateRejected):
        CODEC.verify(tampered_tokens()["tag-bit-flip"])
    assert compare.calls == 2


def test_t1_an_over_long_token_is_refused_before_the_mac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compare = Spy()
    monkeypatch.setattr(state_module.hmac, "compare_digest", compare)

    rejected("v1." + "A" * MAX_STATE_CHARS + "." + "A" * 43)
    assert compare.calls == 0


# Size caps (T9)


def turns(count: int, text: str = "Synthetic turn text.") -> list[StateTurn]:
    speakers = ("student", "client")
    return [
        StateTurn(speaker=speakers[i % 2], text=text, at_ms=i)  # type: ignore[arg-type]
        for i in range(count)
    ]


def test_t9_a_state_at_the_turn_cap_signs_and_verifies() -> None:
    at_cap = state(turns=turns(MAX_STATE_TURNS))

    assert MAX_STATE_TURNS == 200
    assert CODEC.verify(CODEC.sign(at_cap)) == at_cap


def test_t9_a_state_over_the_turn_cap_cannot_be_built_or_signed() -> None:
    with pytest.raises(ValueError):
        state(turns=turns(MAX_STATE_TURNS + 1))

    over = SessionState.model_construct(
        **{**state().__dict__, "turns": turns(MAX_STATE_TURNS + 1)}
    )
    with pytest.raises(StateTooLarge):
        CODEC.sign(over)


def sized_state(characters: int) -> SessionState:
    """Turns of three-byte characters, ``characters`` in total, 2,000 per turn."""
    full, rest = divmod(characters, 2000)
    texts = ["語" * 2000] * full + (["語" * rest] if rest else [])
    speakers = ("student", "client")
    return state(
        turns=[
            StateTurn(speaker=speakers[i % 2], text=text, at_ms=i)  # type: ignore[arg-type]
            for i, text in enumerate(texts)
        ]
    )


def test_t9_the_largest_signable_state_verifies_and_one_more_character_is_refused() -> (
    None
):
    low, high = 1, 2000 * MAX_STATE_TURNS
    with pytest.raises(StateTooLarge):
        CODEC.sign(sized_state(high))
    assert len(CODEC.sign(sized_state(low))) <= MAX_STATE_CHARS
    while high - low > 1:
        middle = (low + high) // 2
        try:
            CODEC.sign(sized_state(middle))
        except StateTooLarge:
            high = middle
        else:
            low = middle

    largest = CODEC.sign(sized_state(low))
    assert MAX_STATE_CHARS - 4 <= len(largest) <= MAX_STATE_CHARS
    assert CODEC.verify(largest) == sized_state(low)
    with pytest.raises(StateTooLarge):
        CODEC.sign(sized_state(low + 1))
