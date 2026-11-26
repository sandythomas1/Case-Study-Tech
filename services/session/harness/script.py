"""The synthetic counselor scripts, loaded strictly from ``scripts/*.toml`` (#67 FR-4).

Each script is a TOML file named after its id. It holds the scenario it runs,
its ordered counselor turns and its on-scenario rule (topic groups, the share
of replies that must hit a group and how many groups a run must touch).

A turn's optional ``tag`` marks the turn a check looks at. Tags are metadata:
only a turn's ``text`` is ever sent to the model. Loading fails with
``ScriptError`` naming the file and key, never a turn's text, when a key is
missing or unknown, a value has the wrong type, the scenario id is unknown, or
the tags don't fit the scenario (for example, a crisis script with no
safety question and no missed cue).
"""

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Final, Literal, cast, get_args

from cst_session.handoff.contract import CRISIS_SCENARIO
from cst_session.persona import valid_turn_text
from cst_session.scenarios import SCENARIO_IDS

Tag = Literal[
    "risk_screen",
    "safety_question",
    "plan_question",
    "ignores_risk",
    "promises_secrecy",
    "closing",
]
TAGS: Final = frozenset(get_args(Tag))
SCRIPT_IDS: Final = (
    "routine_intake",
    "resistant_client",
    "crisis_risk",
    "crisis_risk_missed_cues",
)
MIN_TURNS: Final = 2
MAX_TURNS: Final = 12
MAX_TURN_CHARS: Final = 500
MAX_GROUPS: Final = 8

_CRISIS_ONLY_TAGS: Final = frozenset(
    {"safety_question", "plan_question", "ignores_risk", "promises_secrecy"}
)
_TOP_KEYS: Final = frozenset({"scenario_id", "on_scenario", "turns"})
_RULE_KEYS: Final = frozenset({"min_hit_percent", "min_groups", "groups"})
_OPTIONAL_RULE_KEYS: Final = frozenset({"pushback_group", "report_only"})
_TURN_KEYS: Final = frozenset({"text"})
_OPTIONAL_TURN_KEYS: Final = frozenset({"tag"})
_GROUP_NAME = re.compile(r"[a-z][a-z_]{0,31}", re.ASCII)


class ScriptError(Exception):
    """A script is missing, malformed or doesn't fit its scenario."""


@dataclass(frozen=True, slots=True)
class ScriptTurn:
    """One counselor turn. Only ``text`` is sent to the model."""

    text: str = field(repr=False)
    tag: Tag | None = None


@dataclass(frozen=True, slots=True)
class TopicGroup:
    """One on-scenario topic: a name and its terms, matched case-insensitively."""

    name: str
    pattern: re.Pattern[str] = field(repr=False)


@dataclass(frozen=True, slots=True)
class OnScenarioRule:
    """A run is on scenario when enough replies hit a group and enough groups are hit."""

    groups: tuple[TopicGroup, ...]
    min_hit_percent: int
    min_groups: int
    pushback_group: str | None = None
    # Shown as INFO, never failing the run. Only an extra script may set it.
    report_only: bool = False


@dataclass(frozen=True, slots=True)
class Script:
    script_id: str
    scenario_id: str
    turns: tuple[ScriptTurn, ...]
    on_scenario: OnScenarioRule

    @property
    def crisis(self) -> bool:
        return self.scenario_id == CRISIS_SCENARIO

    @property
    def skilled(self) -> bool:
        """A crisis script whose counselor asks directly about risk."""
        return self.index_of("safety_question") is not None

    def index_of(self, tag: Tag) -> int | None:
        """The 0-based index of the turn with ``tag``, or ``None``."""
        for index, turn in enumerate(self.turns):
            if turn.tag == tag:
                return index
        return None


def topic_pattern(terms: str) -> re.Pattern[str]:
    """Terms as one case-insensitive pattern that starts at a word boundary."""
    return re.compile(rf"\b(?:{terms})", re.IGNORECASE)


def load_scripts(directory: Traversable | None = None) -> Mapping[str, Script]:
    """Load and check every script from ``directory`` (default: ``scripts/``)."""
    root = directory if directory is not None else files("harness") / "scripts"
    found = sorted(
        entry.name for entry in root.iterdir() if entry.name.endswith(".toml")
    )
    expected = sorted(f"{script_id}.toml" for script_id in SCRIPT_IDS)
    if found != expected:
        raise ScriptError(f"expected exactly {expected}, found {found}")
    return {
        script_id: _parse(script_id, (root / f"{script_id}.toml").read_bytes())
        for script_id in SCRIPT_IDS
    }


def _parse(script_id: str, raw: bytes) -> Script:
    name = f"{script_id}.toml"
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ScriptError(f"{name}: not valid UTF-8 TOML") from exc
    data = _table(name, data, _TOP_KEYS)
    scenario_id = data["scenario_id"]
    if scenario_id not in SCENARIO_IDS:
        raise ScriptError(f"{name}: scenario_id must be one of {list(SCENARIO_IDS)}")
    script = Script(
        script_id=script_id,
        scenario_id=cast(str, scenario_id),
        turns=_turns(name, data["turns"]),
        on_scenario=_rule(name, data["on_scenario"]),
    )
    _check_tags(name, script)
    if script.on_scenario.report_only and script_id == script.scenario_id:
        # AC2: each scenario's own scripted run must gate on scenario.
        raise ScriptError(
            f"{name}: on_scenario report_only is only for an extra script, "
            "not a scenario's own scripted run"
        )
    return script


def _table(
    where: str,
    data: object,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> dict[str, object]:
    """``data`` as a table with every ``required`` key and no unknown one."""
    if not isinstance(data, dict):
        raise ScriptError(f"{where}: must be a table")
    keys = set(data)
    if missing := sorted(required - keys):
        raise ScriptError(f"{where}: missing {missing}")
    if unknown := sorted(keys - required - optional):
        raise ScriptError(f"{where}: unknown {unknown}")
    return data


def _turns(name: str, value: object) -> tuple[ScriptTurn, ...]:
    if not isinstance(value, list) or not MIN_TURNS <= len(value) <= MAX_TURNS:
        raise ScriptError(f"{name}: turns must be {MIN_TURNS} to {MAX_TURNS} tables")
    turns: list[ScriptTurn] = []
    for number, entry in enumerate(value, start=1):
        where = f"{name}: turn {number}"
        table = _table(where, entry, _TURN_KEYS, _OPTIONAL_TURN_KEYS)
        text = table["text"]
        if (
            not isinstance(text, str)
            or valid_turn_text(text) is None
            or text != text.strip()
            or len(text) > MAX_TURN_CHARS
        ):
            raise ScriptError(
                f"{where}: text must be trimmed turn text of at most "
                f"{MAX_TURN_CHARS} characters"
            )
        tag = table.get("tag")
        if tag is not None and tag not in TAGS:
            raise ScriptError(f"{where}: tag must be one of {sorted(TAGS)}")
        turns.append(ScriptTurn(text=text, tag=cast(Tag | None, tag)))
    return tuple(turns)


def _rule(name: str, value: object) -> OnScenarioRule:
    where = f"{name}: on_scenario"
    rule = _table(where, value, _RULE_KEYS, _OPTIONAL_RULE_KEYS)
    groups = _groups(where, rule["groups"])
    percent = rule["min_hit_percent"]
    if type(percent) is not int or not 1 <= percent <= 100:
        raise ScriptError(f"{where}: min_hit_percent must be 1 to 100")
    minimum = rule["min_groups"]
    if type(minimum) is not int or not 1 <= minimum <= len(groups):
        raise ScriptError(f"{where}: min_groups must be 1 to {len(groups)}")
    pushback = rule.get("pushback_group")
    if pushback is not None and pushback not in {group.name for group in groups}:
        raise ScriptError(f"{where}: pushback_group must name one of the groups")
    report_only = rule.get("report_only", False)
    if type(report_only) is not bool:
        raise ScriptError(f"{where}: report_only must be true or false")
    return OnScenarioRule(
        groups, percent, minimum, cast(str | None, pushback), report_only
    )


def _groups(where: str, value: object) -> tuple[TopicGroup, ...]:
    if not isinstance(value, dict) or not 1 <= len(value) <= MAX_GROUPS:
        raise ScriptError(f"{where}: groups must be a table of 1 to {MAX_GROUPS}")
    groups: list[TopicGroup] = []
    for group_name, terms in value.items():
        if not _GROUP_NAME.fullmatch(group_name):
            raise ScriptError(f"{where}: a group name must be lowercase letters and _")
        if not isinstance(terms, str) or not terms.strip():
            raise ScriptError(f"{where}: {group_name} must be a non-empty string")
        try:
            pattern = topic_pattern(terms)
        except re.error as exc:
            raise ScriptError(f"{where}: {group_name} is not a valid pattern") from exc
        groups.append(TopicGroup(group_name, pattern))
    return tuple(groups)


def _check_tags(name: str, script: Script) -> None:
    tags = [turn.tag for turn in script.turns if turn.tag is not None]
    if len(tags) != len(set(tags)):
        raise ScriptError(f"{name}: each tag may appear at most once")
    closing = script.index_of("closing")
    if closing is not None and closing != len(script.turns) - 1:
        raise ScriptError(f"{name}: closing must tag the last turn")
    if script.crisis:
        _check_crisis_tags(name, script, set(tags))
    elif crisis_tags := sorted(_CRISIS_ONLY_TAGS & set(tags)):
        raise ScriptError(f"{name}: {crisis_tags} only fit the crisis scenario")


def _check_crisis_tags(name: str, script: Script, tags: set[str]) -> None:
    if "risk_screen" in tags:
        raise ScriptError(f"{name}: risk_screen doesn't fit the crisis scenario")
    safety = script.index_of("safety_question")
    plan = script.index_of("plan_question")
    missed = script.index_of("ignores_risk")
    if safety is not None:
        if missed is not None:
            raise ScriptError(
                f"{name}: a script either asks the safety question or ignores risk"
            )
        if plan is None or plan <= safety:
            raise ScriptError(
                f"{name}: a plan_question must follow the safety_question"
            )
        return
    if missed is None:
        raise ScriptError(
            f"{name}: a crisis script needs a safety_question or an ignores_risk turn"
        )
    if plan is not None:
        raise ScriptError(f"{name}: a plan_question needs a safety_question first")
