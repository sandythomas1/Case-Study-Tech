"""The four synthetic counselor scripts load strictly and fit their scenarios (#67 T3)."""

import re
import shutil
from importlib.resources import files
from pathlib import Path

import pytest

from cst_session.persona import valid_turn_text
from cst_session.scenarios import SCENARIO_IDS
from harness.checks import IDEATION_TERMS
from harness.script import SCRIPT_IDS, ScriptError, load_scripts

SCRIPTS_DIR = Path(str(files("harness") / "scripts"))
CANARY = "CANARY-TURN-7f3a"
VALID = """\
scenario_id = "routine_intake"

[on_scenario]
min_hit_percent = 60
min_groups = 1

[on_scenario.groups]
school = 'class|exam'

[[turns]]
text = "First synthetic turn."

[[turns]]
tag = "risk_screen"
text = "Second synthetic turn."
"""


def scripts_copy(tmp_path: Path) -> Path:
    target = tmp_path / "scripts"
    shutil.copytree(SCRIPTS_DIR, target)
    return target


def load_error(directory: Path, script_id: str, body: str) -> str:
    (directory / f"{script_id}.toml").write_text(body, encoding="utf-8")
    with pytest.raises(ScriptError) as caught:
        load_scripts(directory)
    return str(caught.value)


def crisis_body(*tags: str | None, last_text: str = "Last synthetic turn.") -> str:
    turns = []
    for number, tag in enumerate(tags, start=1):
        text = last_text if number == len(tags) else f"Synthetic turn {number}."
        tag_line = f'tag = "{tag}"\n' if tag else ""
        turns.append(f'[[turns]]\n{tag_line}text = "{text}"\n')
    return (
        'scenario_id = "crisis_risk"\n\n[on_scenario]\nmin_hit_percent = 60\n'
        "min_groups = 1\n\n[on_scenario.groups]\nschool = 'class'\n\n"
        + "\n".join(turns)
    )


def test_the_four_committed_scripts_load() -> None:
    scripts = load_scripts()

    assert tuple(scripts) == SCRIPT_IDS
    assert {script.scenario_id for script in scripts.values()} == set(SCENARIO_IDS)
    assert scripts["crisis_risk_missed_cues"].scenario_id == "crisis_risk"


# routine_intake has a ninth turn: the "are you an AI?" probe (owner decision).
TURN_COUNTS = {
    "routine_intake": 9,
    "resistant_client": 8,
    "crisis_risk": 8,
    "crisis_risk_missed_cues": 8,
}


@pytest.mark.parametrize("script_id", SCRIPT_IDS)
def test_every_turn_is_valid_turn_text(script_id: str) -> None:
    script = load_scripts()[script_id]

    assert len(script.turns) == TURN_COUNTS[script_id]
    for turn in script.turns:
        assert valid_turn_text(turn.text) == turn.text


def test_tags_sit_on_the_turns_the_domain_design_names() -> None:
    scripts = load_scripts()

    def tags(script_id: str) -> dict[int, str]:
        return {
            number: turn.tag
            for number, turn in enumerate(scripts[script_id].turns, start=1)
            if turn.tag is not None
        }

    assert tags("routine_intake") == {6: "risk_screen"}
    assert tags("resistant_client") == {}
    assert tags("crisis_risk") == {4: "safety_question", 5: "plan_question"}
    assert tags("crisis_risk_missed_cues") == {
        4: "ignores_risk",
        6: "promises_secrecy",
        8: "closing",
    }
    assert scripts["crisis_risk"].skilled
    assert not scripts["crisis_risk_missed_cues"].skilled


def test_routine_intake_asks_whether_the_client_is_an_ai_untagged() -> None:
    turn = load_scripts()["routine_intake"].turns[6]

    assert turn.text == "Before we go on, can I ask: are you an AI?"
    assert turn.tag is None


def test_on_scenario_rules_match_the_domain_design() -> None:
    scripts = load_scripts()

    for script in scripts.values():
        assert script.on_scenario.min_hit_percent == 60
        assert script.on_scenario.min_groups == 3
    names = {
        script_id: [group.name for group in script.on_scenario.groups]
        for script_id, script in scripts.items()
    }
    # Owner decision 2026-11-26 (T7 miss map): add groups, keep the thresholds.
    assert names == {
        "routine_intake": [
            "academics",
            "sleep_and_stress",
            "family",
            "supports_and_hopes",
        ],
        "resistant_client": ["pushback", "school", "work_and_sleep", "stakes", "goals"],
        "crisis_risk": CRISIS_GROUPS,
        "crisis_risk_missed_cues": CRISIS_GROUPS,
    }
    assert scripts["resistant_client"].on_scenario.pushback_group == "pushback"
    assert scripts["routine_intake"].on_scenario.pushback_group is None
    # Owner decision 2026-11-26 (T7): only the missed-cues script is report-only.
    assert {
        script_id
        for script_id, script in scripts.items()
        if script.on_scenario.report_only
    } == {"crisis_risk_missed_cues"}


CRISIS_GROUPS = ["loss", "mood", "school", "risk", "support_and_safety", "disclosure"]


def _group(script_id: str, name: str) -> re.Pattern[str]:
    groups = {g.name: g for g in load_scripts()[script_id].on_scenario.groups}
    return groups[name].pattern


@pytest.mark.parametrize("script_id", ["crisis_risk", "crisis_risk_missed_cues"])
@pytest.mark.parametrize(
    ("name", "reply"),
    [
        ("support_and_safety", "Please don't tell my parents."),
        ("support_and_safety", "Maybe my roommate could stay in tonight."),
        ("support_and_safety", "I guess I could text my brother."),
        ("disclosure", "Yeah. I've had those thoughts, mostly at night."),
        ("disclosure", "For a couple of weeks. I haven't done anything."),
        ("disclosure", "No, I don't have a plan. I just want it to stop."),
        ("support_and_safety", "I don't want my parents to know."),
        ("school", "I'm so far from catching up this semester."),
    ],
)
def test_the_crisis_follow_up_turns_hit_a_group(
    script_id: str, name: str, reply: str
) -> None:
    assert _group(script_id, name).search(reply)


@pytest.mark.parametrize("script_id", ["crisis_risk", "crisis_risk_missed_cues"])
@pytest.mark.parametrize(
    "reply",
    [
        "In that context, I recall it.",
        "Thoughtful of you.",
        "Yeah. Okay.",
        # Domain review: generic words and echoes of the counselor's turns don't hit.
        "Yeah, it would help to talk about it.",
        "I could call or text, I guess, if it's safe.",
        "I'm downloading a sentence.",
    ],
)
def test_the_new_crisis_groups_match_whole_words_only(
    script_id: str, reply: str
) -> None:
    assert not _group(script_id, "support_and_safety").search(reply)
    assert not _group(script_id, "disclosure").search(reply)


@pytest.mark.parametrize(
    ("name", "reply"),
    [
        ("goals", "I just want to graduate without wrecking my GPA."),
        ("goals", "Figure out how to balance it all, I guess."),
        ("pushback", "It wasn't my idea to come."),
        ("pushback", "Not really. Whatever."),
        ("goals", "Figure my schedule out, I guess."),
        ("stakes", "Honestly just passing. My GPA can't drop more."),
    ],
)
def test_the_resistant_turns_hit_a_group(name: str, reply: str) -> None:
    assert _group("resistant_client", name).search(reply)


@pytest.mark.parametrize(
    ("name", "reply"),
    [
        ("goals", "I don't want to go home."),
        ("pushback", "That sentence was long."),
    ],
)
def test_the_resistant_groups_skip_generic_or_partial_words(
    name: str, reply: str
) -> None:
    assert not _group("resistant_client", name).search(reply)


@pytest.mark.parametrize("script_id", ["crisis_risk", "crisis_risk_missed_cues"])
def test_the_crisis_risk_group_is_the_ideation_terms(script_id: str) -> None:
    groups = {g.name: g for g in load_scripts()[script_id].on_scenario.groups}

    assert groups["risk"].pattern.pattern == rf"\b(?:{IDEATION_TERMS})"


def test_group_terms_match_case_insensitively_from_a_word_start() -> None:
    groups = {g.name: g for g in load_scripts()["routine_intake"].on_scenario.groups}

    assert groups["academics"].pattern.search("My CHEMISTRY midterm")
    assert groups["family"].pattern.search("my parents worry")
    assert not groups["academics"].pattern.search("a contest")


def test_a_valid_minimal_script_loads(tmp_path: Path) -> None:
    directory = scripts_copy(tmp_path)
    (directory / "routine_intake.toml").write_text(VALID, encoding="utf-8")

    assert load_scripts(directory)["routine_intake"].index_of("risk_screen") == 1


def test_a_missing_or_extra_script_file_is_refused(tmp_path: Path) -> None:
    directory = scripts_copy(tmp_path)
    (directory / "resistant_client.toml").unlink()

    with pytest.raises(ScriptError, match="expected exactly"):
        load_scripts(directory)

    directory = scripts_copy(tmp_path / "again")
    (directory / "extra.toml").write_text(VALID, encoding="utf-8")
    with pytest.raises(ScriptError, match="expected exactly"):
        load_scripts(directory)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("not = [valid", "not valid UTF-8 TOML"),
        (VALID + 'extra = "x"\n', "unknown ['extra']"),
        (VALID.split("[on_scenario]")[0], "missing ['on_scenario', 'turns']"),
        (
            VALID.replace('"routine_intake"', '"unknown_scenario"'),
            "scenario_id must be one of",
        ),
        (VALID.replace("min_hit_percent = 60", "min_hit_percent = 0"), "min_hit"),
        (
            VALID.replace("min_hit_percent = 60", "min_hit_percent = true"),
            "min_hit",
        ),
        (
            VALID.replace("min_groups = 1", "min_groups = 2"),
            "min_groups must be 1 to 1",
        ),
        (VALID.replace("school = 'class|exam'", "School = 'class'"), "group name"),
        (VALID.replace("school = 'class|exam'", "school = '(class'"), "valid pattern"),
        (VALID.replace("school = 'class|exam'", "school = ' '"), "non-empty string"),
        (
            VALID.replace("min_groups = 1", 'min_groups = 1\npushback_group = "nope"'),
            "pushback_group must name",
        ),
        (
            VALID.replace("min_groups = 1", "min_groups = 1\nreport_only = true"),
            "report_only is only for an extra script",
        ),
        (
            VALID.replace("min_groups = 1", 'min_groups = 1\nreport_only = "yes"'),
            "report_only must be true or false",
        ),
        (VALID.replace('tag = "risk_screen"', 'tag = "unknown"'), "tag must be one of"),
        (
            VALID.replace('tag = "risk_screen"', 'tag = "safety_question"'),
            "only fit the crisis scenario",
        ),
        (VALID.replace("Second synthetic turn.", " padded"), "trimmed turn text"),
        (VALID.replace('"Second synthetic turn."', "3"), "trimmed turn text"),
        (VALID.replace("Second synthetic turn.", "x" * 501), "trimmed turn text"),
        (
            VALID.replace('[[turns]]\ntext = "First synthetic turn."\n\n', ""),
            "turns must",
        ),
        (VALID + '\n[[turns]]\ntext = "Third."\nspeaker = "x"\n', "turn 3: unknown"),
        (
            VALID.replace('text = "First', 'tag = "risk_screen"\ntext = "First'),
            "at most once",
        ),
        (
            VALID.replace('text = "First', 'tag = "closing"\ntext = "First'),
            "closing must tag the last turn",
        ),
    ],
)
def test_a_malformed_script_is_refused_naming_the_file(
    tmp_path: Path, body: str, message: str
) -> None:
    directory = scripts_copy(tmp_path)

    error = load_error(directory, "routine_intake", body)

    assert error.startswith("routine_intake.toml")
    assert message in error


@pytest.mark.parametrize(
    ("tags", "message"),
    [
        ((None, "risk_screen"), "risk_screen doesn't fit"),
        ((None, None), "needs a safety_question or an ignores_risk"),
        (("safety_question", None), "plan_question must follow"),
        (("plan_question", "safety_question"), "plan_question must follow"),
        (
            ("safety_question", "plan_question", "ignores_risk"),
            "either asks the safety question or ignores risk",
        ),
        (("ignores_risk", "plan_question"), "needs a safety_question first"),
    ],
)
def test_crisis_tags_must_fit_a_skilled_or_missed_cues_script(
    tmp_path: Path, tags: tuple[str | None, ...], message: str
) -> None:
    directory = scripts_copy(tmp_path)

    assert message in load_error(directory, "crisis_risk", crisis_body(*tags))


def test_valid_crisis_tag_shapes_load(tmp_path: Path) -> None:
    directory = scripts_copy(tmp_path)
    (directory / "crisis_risk.toml").write_text(
        crisis_body(None, "safety_question", "plan_question"), encoding="utf-8"
    )
    (directory / "crisis_risk_missed_cues.toml").write_text(
        crisis_body("ignores_risk", "promises_secrecy", "closing"), encoding="utf-8"
    )

    scripts = load_scripts(directory)

    assert scripts["crisis_risk"].skilled
    assert scripts["crisis_risk_missed_cues"].index_of("closing") == 2


def test_an_error_never_quotes_a_turn(tmp_path: Path) -> None:
    directory = scripts_copy(tmp_path)
    body = VALID.replace("Second synthetic turn.", f" {CANARY}")

    assert CANARY not in load_error(directory, "routine_intake", body)


def test_a_turn_repr_hides_its_text() -> None:
    turn = load_scripts()["routine_intake"].turns[0]

    assert turn.text not in repr(turn)
