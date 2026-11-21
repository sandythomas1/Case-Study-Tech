"""CI proof for #51: a deliberately failing test (do not merge)."""


def test_ci_proof_deliberate_failure() -> None:
    assert 1 + 1 == 3, "deliberate failure to prove CI runs pytest"
