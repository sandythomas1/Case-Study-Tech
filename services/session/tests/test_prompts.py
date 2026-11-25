"""The interim persona prompts load strictly and read-only (FR-5, AC1).

One synthetic prompt per scenario lives in ``scenarios/prompts/<id>.txt`` until
#67 replaces them. Loading works like ``load_catalogue``: exactly the three
ids, UTF-8, non-empty and within the cap, or ``PromptError`` naming the file.
"""

import shutil
from importlib.resources import files
from pathlib import Path

import pytest

from cst_session.scenarios import SCENARIO_IDS
from cst_session.scenarios.prompts import MAX_PROMPT_CHARS, PromptError, load_prompts

PROMPTS = Path(str(files("cst_session.scenarios") / "prompts"))


def prompts_copy(tmp_path: Path) -> Path:
    target = tmp_path / "prompts"
    shutil.copytree(PROMPTS, target)
    return target


def test_the_committed_prompts_load_one_per_scenario() -> None:
    prompts = load_prompts()

    assert MAX_PROMPT_CHARS == 1500
    for scenario_id in SCENARIO_IDS:
        text = prompts.for_scenario(scenario_id)
        assert 0 < len(text) <= MAX_PROMPT_CHARS
        assert text == text.strip()


def test_each_scenario_gets_its_own_prompt() -> None:
    prompts = load_prompts()

    assert len({prompts.for_scenario(s) for s in SCENARIO_IDS}) == len(SCENARIO_IDS)


def test_every_prompt_keeps_the_persona_in_role_and_never_coaches() -> None:
    prompts = load_prompts()

    for scenario_id in SCENARIO_IDS:
        text = prompts.for_scenario(scenario_id).lower()
        assert "client" in text, scenario_id
        assert "never" in text and "score" in text and "hint" in text, scenario_id


def test_the_crisis_prompt_keeps_going_after_a_disclosure() -> None:
    text = load_prompts().for_scenario("crisis_risk").lower()

    assert "keep" in text and "conversation" in text


def test_a_readme_marks_the_prompts_interim() -> None:
    readme = (PROMPTS / "README.md").read_text(encoding="utf-8").lower()

    assert "interim" in readme and "#67" in readme


def test_an_unknown_scenario_has_no_prompt() -> None:
    with pytest.raises(PromptError):
        load_prompts().for_scenario("other")


def test_crlf_prompts_load_exactly_like_lf_prompts(tmp_path: Path) -> None:
    directory = prompts_copy(tmp_path)
    for scenario_id in SCENARIO_IDS:
        path = directory / f"{scenario_id}.txt"
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        path.write_bytes(raw.replace(b"\n", b"\r\n"))

    loaded, committed = load_prompts(directory), load_prompts()
    for scenario_id in SCENARIO_IDS:
        assert loaded.for_scenario(scenario_id) == committed.for_scenario(scenario_id)


def test_a_missing_prompt_stops_loading(tmp_path: Path) -> None:
    directory = prompts_copy(tmp_path)
    (directory / "crisis_risk.txt").unlink()

    with pytest.raises(PromptError, match="expected exactly"):
        load_prompts(directory)


def test_an_extra_prompt_stops_loading(tmp_path: Path) -> None:
    directory = prompts_copy(tmp_path)
    (directory / "free_chat.txt").write_text("You are anyone.", encoding="utf-8")

    with pytest.raises(PromptError, match="expected exactly"):
        load_prompts(directory)


@pytest.mark.parametrize("content", [b"", b"   \n\t  \n"])
def test_an_empty_prompt_stops_loading(tmp_path: Path, content: bytes) -> None:
    directory = prompts_copy(tmp_path)
    (directory / "routine_intake.txt").write_bytes(content)

    with pytest.raises(PromptError, match=r"routine_intake\.txt: "):
        load_prompts(directory)


def test_a_prompt_over_the_cap_stops_loading(tmp_path: Path) -> None:
    directory = prompts_copy(tmp_path)
    (directory / "resistant_client.txt").write_text(
        "x" * (MAX_PROMPT_CHARS + 1), encoding="utf-8"
    )

    with pytest.raises(PromptError, match=r"resistant_client\.txt: "):
        load_prompts(directory)


def test_a_prompt_at_the_cap_loads(tmp_path: Path) -> None:
    directory = prompts_copy(tmp_path)
    (directory / "resistant_client.txt").write_text(
        "y" * MAX_PROMPT_CHARS, encoding="utf-8"
    )

    assert load_prompts(directory).for_scenario("resistant_client") == "y" * 1500


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"\xff\xfe not utf-8", id="not-utf8"),
        pytest.param(b"\xef\xbb\xbfYou play a client.", id="byte-order-mark"),
        pytest.param(b"You play\x00 a client.", id="nul"),
        pytest.param("You play a client.‮".encode(), id="bidi-override"),
        pytest.param("You play a client.\U000e0041".encode(), id="tag-character"),
    ],
)
def test_a_malformed_prompt_stops_loading(tmp_path: Path, content: bytes) -> None:
    directory = prompts_copy(tmp_path)
    (directory / "crisis_risk.txt").write_bytes(content)

    with pytest.raises(PromptError, match=r"crisis_risk\.txt: ") as caught:
        load_prompts(directory)
    assert "client" not in str(caught.value)


def test_the_loaded_prompts_have_no_write_path() -> None:
    prompts = load_prompts()

    with pytest.raises(AttributeError):
        prompts.extra = "x"  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        prompts.texts["routine_intake"] = "x"  # type: ignore[index]
    assert not [
        name
        for name in dir(prompts)
        if not name.startswith("_") and name not in {"for_scenario", "texts"}
    ]
