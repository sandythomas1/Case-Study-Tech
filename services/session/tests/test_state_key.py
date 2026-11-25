"""The state-signing key decodes one documented way, or startup stops (T8, FR-3).

``CST_STATE_SIGNING_KEY`` is 43 characters of unpadded base64url that decode to
exactly 32 bytes and encode back to the same text (L2-2, owner decided
2026-11-25). Every refusal carries one fixed message that names neither the
value nor its length.
"""

import base64

import pytest

from cst_session.state import KEY_BYTES, SigningKeyError, decode_signing_key

RAW = bytes(range(1, 33))
GOOD = base64.urlsafe_b64encode(RAW).rstrip(b"=").decode("ascii")


def encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def refusal_message(text: object) -> str:
    with pytest.raises(SigningKeyError) as caught:
        decode_signing_key(text)  # type: ignore[arg-type]
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    return str(caught.value)


def test_t8_a_canonical_key_decodes_to_its_32_bytes() -> None:
    assert len(GOOD) == 43
    assert decode_signing_key(GOOD) == RAW
    assert KEY_BYTES == 32


def test_t8_every_byte_value_round_trips() -> None:
    for raw in (bytes(32), b"\xff" * 32, b"\xfb\xef\xbe" * 10 + b"\xff\xfe"):
        assert decode_signing_key(encode(raw)) == raw


# The standard alphabet's "+" and "/" sit where base64url has "-" and "_".
STANDARD_ALPHABET = base64.b64encode(b"\xfb\xff" * 16).rstrip(b"=").decode("ascii")


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(GOOD + "=", id="padded"),
        pytest.param(base64.urlsafe_b64encode(RAW).decode("ascii"), id="padded-44"),
        pytest.param(STANDARD_ALPHABET, id="standard-alphabet"),
        pytest.param(encode(RAW[:31]), id="31-bytes"),
        pytest.param(encode(RAW + b"\x00"), id="33-bytes"),
        pytest.param(GOOD[:-1] + "\x00", id="nul-inside"),
        pytest.param(GOOD + "\x00", id="nul-after"),
        pytest.param(" " + GOOD, id="leading-space"),
        pytest.param(GOOD + "\n", id="trailing-newline"),
        pytest.param(GOOD[:20] + " " + GOOD[21:], id="inner-space"),
        pytest.param(GOOD[:-1] + "é", id="non-ascii-letter"),
        pytest.param(GOOD[:-1] + "٣", id="non-ascii-digit"),
        pytest.param(GOOD[:-1] + "\udcff", id="surrogate-escape"),
        # The 43rd character holds 2 spare bits; only zero bits re-encode the same.
        pytest.param(GOOD[:-1] + "B", id="non-canonical-tail"),
        pytest.param("", id="empty"),
        pytest.param("A" * 64, id="long"),
    ],
)
def test_t8_a_malformed_key_is_refused(text: str) -> None:
    assert decode_signing_key(GOOD) == RAW
    refusal_message(text)


@pytest.mark.parametrize("value", [GOOD.encode("ascii"), None, 32])
def test_t8_a_key_that_is_not_text_is_refused(value: object) -> None:
    refusal_message(value)


@pytest.mark.parametrize(
    "text",
    [
        "CanaryKeyValueCanaryKeyValueCanaryKeyValue",
        GOOD[:-1] + "B",
        encode(RAW[:31]),
        GOOD + "=",
    ],
)
def test_t8_the_message_never_carries_the_value_or_its_length(text: str) -> None:
    message = refusal_message(text)

    assert text not in message
    assert text[:8] not in message
    assert str(len(text)) not in message
    assert message == refusal_message("x")
