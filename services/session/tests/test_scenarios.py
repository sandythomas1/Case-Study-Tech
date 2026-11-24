"""The three vetted scenario configurations (#27, RC-22, DD-07).

AC1: exactly three configurations load and pass schema validation.
AC2: the time limit is read from config and is 10 minutes for each.
AC3: a release flag that is off hides the scenario from the library and blocks
it from starting. Owner decision 2026-11-23: proved on ``library()`` and
``startable()``, which the library endpoint (#28) and session start (#31) call.
AC4: no API path creates or edits a scenario.
"""

import dataclasses
import json
import re
import shutil
from importlib.resources import files
from pathlib import Path

import pytest

from cst_session.content_free_log import log_event
from cst_session.scenarios import (
    SCENARIO_IDS,
    Catalogue,
    CatalogueError,
    Scenario,
    ScenarioUnavailable,
    load_catalogue,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIGS = Path(str(files("cst_session.scenarios") / "configs"))


def config_copy(tmp_path: Path) -> Path:
    """A writable copy of the real configs, for tests that change one."""
    target = tmp_path / "configs"
    shutil.copytree(CONFIGS, target)
    return target


def edit(directory: Path, scenario_id: str, old: str, new: str) -> None:
    path = directory / f"{scenario_id}.toml"
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{old!r} not found once in {path.name}"
    path.write_text(text.replace(old, new), encoding="utf-8")


# AC1 ----------------------------------------------------------------------


def test_exactly_the_three_vetted_scenarios_load_in_library_order() -> None:
    catalogue = load_catalogue()

    assert [scenario.id for scenario in catalogue.scenarios] == [
        "routine_intake",
        "resistant_client",
        "crisis_risk",
    ]
    assert all(isinstance(scenario, Scenario) for scenario in catalogue.scenarios)


def test_the_scenario_ids_match_the_rubric_anchor_spec() -> None:
    anchor_spec = json.loads(
        (REPO_ROOT / "rubric" / "anchor-spec.v1.json").read_text(encoding="utf-8")
    )

    assert [s["id"] for s in anchor_spec["scenarios"]] == list(SCENARIO_IDS)


def test_every_scenario_carries_the_preparation_fields() -> None:
    for scenario in load_catalogue().scenarios:
        assert scenario.version == "1.0.0"
        for value in (
            scenario.title,
            scenario.summary,
            scenario.learning_objective,
            scenario.session_format,
            scenario.feedback_timing,
            scenario.content_notice,
        ):
            assert isinstance(value, str) and value.strip() == value and value


def test_only_the_crisis_scenario_is_crisis_and_it_requires_opt_in() -> None:
    by_id = {s.id: s for s in load_catalogue().scenarios}

    assert [s.id for s in by_id.values() if s.crisis] == ["crisis_risk"]
    crisis = by_id["crisis_risk"]
    assert crisis.requires_opt_in and crisis.opt_in_statement
    for scenario_id in ("routine_intake", "resistant_client"):
        assert not by_id[scenario_id].requires_opt_in
        assert by_id[scenario_id].opt_in_statement is None


def test_all_three_start_released() -> None:
    assert [s.id for s in load_catalogue().library()] == list(SCENARIO_IDS)


def test_every_scenario_id_and_version_is_kept_by_the_logging_helper(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for scenario in load_catalogue().scenarios:
        log_event(
            "scenario_check", scenario_id=scenario.id, scenario_version=scenario.version
        )
        line = json.loads(capsys.readouterr().out)
        assert (line["scenario_id"], line["scenario_version"]) == (
            scenario.id,
            scenario.version,
        )


@pytest.mark.parametrize(
    ("scenario_id", "old", "new", "message"),
    [
        ("routine_intake", 'title = "Routine intake"\n', "", "missing ['title']"),
        (
            "routine_intake",
            "released = true\n",
            'released = true\nnotes = "x"\n',
            "unknown",
        ),
        (
            "routine_intake",
            'id = "routine_intake"',
            'id = "resistant_client"',
            "file name",
        ),
        ("routine_intake", 'version = "1.0.0"', 'version = "1.0"', "version"),
        ("routine_intake", 'version = "1.0.0"', "version = 1", "version"),
        (
            "routine_intake",
            "time_limit_minutes = 10",
            'time_limit_minutes = "10"',
            "time_limit",
        ),
        (
            "routine_intake",
            "time_limit_minutes = 10",
            "time_limit_minutes = 10.0",
            "time_limit",
        ),
        (
            "routine_intake",
            "time_limit_minutes = 10",
            "time_limit_minutes = true",
            "time_limit",
        ),
        (
            "routine_intake",
            "time_limit_minutes = 10",
            "time_limit_minutes = 0",
            "time_limit",
        ),
        (
            "routine_intake",
            "time_limit_minutes = 10",
            "time_limit_minutes = 61",
            "time_limit",
        ),
        ("routine_intake", "released = true", 'released = "true"', "released"),
        ("routine_intake", "released = true", "released = 1", "released"),
        ("routine_intake", "crisis = false", "crisis = 0", "crisis"),
        ("routine_intake", 'title = "Routine intake"', 'title = ""', "title"),
        (
            "routine_intake",
            'title = "Routine intake"',
            'title = " Routine intake"',
            "title",
        ),
        (
            "routine_intake",
            'title = "Routine intake"',
            'title = "Routine\\nintake"',
            "title",
        ),
        (
            "routine_intake",
            'title = "Routine intake"',
            'title = "Routine\\u200bintake"',
            "title",
        ),
        (
            "routine_intake",
            'title = "Routine intake"',
            f'title = "{"a" * 301}"',
            "title",
        ),
        ("routine_intake", 'title = "Routine intake"', "title = 3", "title"),
        ("routine_intake", "id = ", "id == ", "TOML"),
        ("crisis_risk", "requires_opt_in = true", "requires_opt_in = false", "opt-in"),
        (
            "routine_intake",
            "requires_opt_in = false",
            "requires_opt_in = true",
            "opt_in_statement",
        ),
        (
            "routine_intake",
            "released = true",
            'released = true\nopt_in_statement = "I agree."',
            "opt_in_statement",
        ),
        (
            "crisis_risk",
            'opt_in_statement = "I understand',
            'opt_in_statement = " I understand',
            "opt_in_statement",
        ),
    ],
)
def test_a_malformed_configuration_fails_loading(
    tmp_path: Path, scenario_id: str, old: str, new: str, message: str
) -> None:
    directory = config_copy(tmp_path)
    edit(directory, scenario_id, old, new)

    with pytest.raises(CatalogueError, match=re.escape(message)) as raised:
        load_catalogue(directory)
    assert f"{scenario_id}.toml" in str(raised.value)


def test_a_file_that_is_not_utf8_fails_loading(tmp_path: Path) -> None:
    directory = config_copy(tmp_path)
    (directory / "routine_intake.toml").write_bytes(b'title = "\xff"\n')

    with pytest.raises(CatalogueError, match="UTF-8"):
        load_catalogue(directory)


def test_a_fourth_scenario_fails_loading(tmp_path: Path) -> None:
    directory = config_copy(tmp_path)
    shutil.copy(directory / "routine_intake.toml", directory / "anxious_student.toml")

    with pytest.raises(CatalogueError, match="exactly"):
        load_catalogue(directory)


def test_a_missing_scenario_fails_loading(tmp_path: Path) -> None:
    directory = config_copy(tmp_path)
    (directory / "resistant_client.toml").unlink()

    with pytest.raises(CatalogueError, match="exactly"):
        load_catalogue(directory)


# AC2 ----------------------------------------------------------------------


def test_the_time_limit_is_10_minutes_for_every_scenario() -> None:
    assert {s.id: s.time_limit_minutes for s in load_catalogue().scenarios} == {
        scenario_id: 10 for scenario_id in SCENARIO_IDS
    }


def test_the_time_limit_is_read_from_config(tmp_path: Path) -> None:
    directory = config_copy(tmp_path)
    edit(
        directory,
        "resistant_client",
        "time_limit_minutes = 10",
        "time_limit_minutes = 15",
    )

    limits = {s.id: s.time_limit_minutes for s in load_catalogue(directory).scenarios}

    assert limits == {"routine_intake": 10, "resistant_client": 15, "crisis_risk": 10}


# AC3 ----------------------------------------------------------------------


@pytest.mark.parametrize("held_back", SCENARIO_IDS)
def test_a_release_flag_off_hides_the_scenario_and_blocks_its_start(
    tmp_path: Path, held_back: str
) -> None:
    directory = config_copy(tmp_path)
    edit(directory, held_back, "released = true", "released = false")
    catalogue = load_catalogue(directory)

    assert held_back not in [s.id for s in catalogue.library()]
    with pytest.raises(ScenarioUnavailable):
        catalogue.startable(held_back)
    for other in (s for s in SCENARIO_IDS if s != held_back):
        assert catalogue.startable(other).id == other
    assert held_back in [s.id for s in catalogue.scenarios]


def test_every_released_scenario_can_start() -> None:
    catalogue = load_catalogue()

    for scenario_id in SCENARIO_IDS:
        assert catalogue.startable(scenario_id).id == scenario_id


@pytest.mark.parametrize(
    "scenario_id", ["anxious_student", "", "ROUTINE_INTAKE", "routine-intake"]
)
def test_an_unknown_scenario_cannot_start(scenario_id: str) -> None:
    with pytest.raises(ScenarioUnavailable):
        load_catalogue().startable(scenario_id)


def test_held_back_and_unknown_scenarios_fail_the_same_way(tmp_path: Path) -> None:
    directory = config_copy(tmp_path)
    edit(directory, "crisis_risk", "released = true", "released = false")
    catalogue = load_catalogue(directory)

    with pytest.raises(ScenarioUnavailable) as held_back:
        catalogue.startable("crisis_risk")
    with pytest.raises(ScenarioUnavailable) as unknown:
        catalogue.startable("anxious_student")
    assert str(held_back.value) == str(unknown.value)
    assert "crisis" not in str(held_back.value)


# AC4: no create or edit path in code ---------------------------------------


def test_a_loaded_scenario_cannot_be_changed() -> None:
    scenario = load_catalogue().scenarios[0]

    with pytest.raises(dataclasses.FrozenInstanceError):
        scenario.released = False  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        scenario.time_limit_minutes = 30  # type: ignore[misc]


def test_the_catalogue_offers_only_reads() -> None:
    catalogue = load_catalogue()
    public = {name for name in dir(Catalogue) if not name.startswith("_")}

    assert public == {"scenarios", "library", "startable"}
    assert isinstance(catalogue.scenarios, tuple)
    assert isinstance(catalogue.library(), tuple)
    with pytest.raises(AttributeError):
        catalogue.scenarios = ()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        catalogue.extra = ()  # type: ignore[attr-defined]


def test_the_scenarios_package_exports_no_write_function() -> None:
    import cst_session.scenarios as package

    assert set(package.__all__) == {
        "SCENARIO_IDS",
        "Catalogue",
        "CatalogueError",
        "Scenario",
        "ScenarioUnavailable",
        "load_catalogue",
    }
