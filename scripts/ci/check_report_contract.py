"""Check the report contract's fixtures and validation cases (#59).

The contract is report/report-contract.v1.md. This script is its executable form, and
the fixtures under report/ are checked against it:

- every fixture in report/fixtures/v1/ is a valid, synthetic ``cst.report`` or
  ``cst.history`` document;
- every case in report/validation-cases/v1/invalid/ is rejected with its expected
  reason. These include a fabricated turn, a version mismatch, an invented score and
  narrative in history;
- every pair in report/validation-cases/v1/comparisons.json gets its expected
  history comparison: compatible, incompatible or unknown.

Labels, weights, abstention reasons, critical-failure ids and the disclaimer are read
from rubric/anchor-spec.v1.json, so a fixture can never drift from the rubric. This
checks structure only. It approves no rubric, weight, rounding or clinical meaning.

It uses only the standard library, so it runs on any Python 3.10+ without installing
anything. Run it from the repository root: python scripts/ci/check_report_contract.py
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, TypeGuard

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUBRIC = REPO_ROOT / "rubric" / "anchor-spec.v1.json"
DEFAULT_REPORT_DIR = REPO_ROOT / "report"

REPORT = "cst.report"
HISTORY = "cst.history"
CONTRACT_VERSION = "1.0.0"
SUPPORTED_MAJOR = 1

SCENARIO_IDS = ("routine_intake", "resistant_client", "crisis_risk")
CRISIS_SCENARIO = "crisis_risk"
SCENARIO_CATEGORY = "scenario_specific_competence"
MODALITIES = frozenset({"voice", "text"})
SPEAKERS = frozenset({"student", "client"})
STATES = (
    "pending",
    "scored",
    "safety_not_demonstrated",
    "insufficient_evidence",
    "narrative_only",
    "failed",
)
REPORT_STATES = frozenset(STATES) - {"pending", "failed"}
SYNTHETIC_MODEL = "synthetic-fixture"

# Who produces each failure reason is set out in the contract, section "Failed".
FAILURE_REASONS = frozenset(
    {
        "lost_content",
        "conduct",
        "speech",
        "persona",
        "grading",
        "timeout",
        "connectivity",
        "evidence_check",
    }
)
# REC-3: a grading-side failure may be retried while the conversation is still in memory.
RETRYABLE_REASONS = frozenset({"grading", "timeout", "connectivity", "evidence_check"})
# REC-2 and RC-08: a lost conversation or a speech failure offers a new text session.
NEW_TEXT_SESSION_REASONS = frozenset({"lost_content", "speech"})

REPORT_ACTIONS = frozenset({"export", "leave_with_confirmation", "new_practice"})

MAX_TURNS = 500
MAX_QUOTE = 300
MAX_ITEM_TEXT = 500
MAX_ITEMS = 5
MIN_RATING_EVIDENCE = 2

_SEMVER = re.compile(r"(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})", re.ASCII)
_DISPLAY = re.compile(r"[1-5]\.[0-9]", re.ASCII)
_UTC_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", re.ASCII)
_RECORD_ID = re.compile(r"[a-z0-9-]{1,64}", re.ASCII)

COMMON_KEYS = frozenset({"contract", "contract_version", "synthetic", "state", "scenario", "modality"})
NARRATIVE_KEYS = frozenset(
    {"turn_count", "provenance", "strengths", "next_steps", "limitations", "disclaimer"}
)
OUTCOME_KEYS = frozenset({"score_record_saved", "actions"})


@dataclass(frozen=True)
class FieldRule:
    """Top-level keys a state must carry, may carry, and so implicitly must not carry."""

    required: frozenset[str]
    optional: frozenset[str] = frozenset()


# Report states in which a crisis report must carry its safety result (contract section 3).
CRISIS_SAFETY_STATES = frozenset({"scored", "safety_not_demonstrated", "insufficient_evidence", "narrative_only"})

# The field table from the contract, section "Fields by state". A key outside required |
# optional is forbidden. Crisis-only keys are checked separately.
FIELD_RULES: Mapping[str, FieldRule] = {
    "pending": FieldRule(required=COMMON_KEYS),
    "scored": FieldRule(
        required=COMMON_KEYS | NARRATIVE_KEYS | OUTCOME_KEYS | {"scale", "categories", "overall"},
        optional=frozenset({"safety"}),
    ),
    "safety_not_demonstrated": FieldRule(
        required=COMMON_KEYS | NARRATIVE_KEYS | OUTCOME_KEYS | {"scale", "categories", "safety"},
        optional=frozenset({"overall"}),
    ),
    "insufficient_evidence": FieldRule(
        required=COMMON_KEYS | NARRATIVE_KEYS | OUTCOME_KEYS | {"scale", "categories"},
        optional=frozenset({"safety"}),
    ),
    "narrative_only": FieldRule(
        required=COMMON_KEYS | NARRATIVE_KEYS | OUTCOME_KEYS,
        optional=frozenset({"safety"}),
    ),
    "failed": FieldRule(required=COMMON_KEYS | OUTCOME_KEYS | {"failure"}),
}


@dataclass(frozen=True)
class Rubric:
    """What the contract borrows from the anchor spec."""

    spec_id: str
    spec_version: str
    approval_status: str
    disclaimer: str
    categories: tuple[tuple[str, str, int], ...]
    levels: Mapping[int, str]
    abstention_reasons: frozenset[str]
    critical_failures: frozenset[str]

    @classmethod
    def from_spec(cls, spec: Mapping[str, Any]) -> Rubric:
        return cls(
            spec_id=spec["spec_id"],
            spec_version=spec["spec_version"],
            approval_status=spec["approval"]["status"],
            disclaimer=spec["intended_use"]["student_disclaimer"],
            categories=tuple(
                (c["id"], c["name"], c["weight_percent"]) for c in spec["categories"]
            ),
            levels={level["level"]: level["label"] for level in spec["scale"]["levels"]},
            abstention_reasons=frozenset(spec["evidence_policy"]["abstention_reasons"]),
            critical_failures=frozenset(
                f["id"] for f in spec["crisis_critical_failures"]["failures"]
            ),
        )


def load_rubric(path: Path = DEFAULT_RUBRIC) -> Rubric:
    return Rubric.from_spec(json.loads(path.read_text(encoding="utf-8")))


# Small shared helpers ------------------------------------------------------------


def _is_int(value: object) -> TypeGuard[int]:
    return type(value) is int


def _is_text(value: object, limit: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limit and value == value.strip()


def _one_of(value: object, options: Collection[str]) -> TypeGuard[str]:
    """Membership that can't crash on an unhashable value from untrusted JSON."""
    return isinstance(value, str) and value in options


def _strings(value: object) -> list[str] | None:
    """A list of distinct strings, or None for anything else."""
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        return None
    return value if len(set(value)) == len(value) else None


def _single_line(value: str) -> bool:
    # splitlines also breaks on U+2028, U+2029, U+0085 and the other Unicode line boundaries.
    return value.splitlines() == [value]


def _is_utc_time(value: str) -> bool:
    """A real calendar time in the form 2026-11-20T15:04:05Z."""
    if not _UTC_TIME.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def _major(version: str) -> int:
    return int(version.split(".", 1)[0])


def weighted_mean(levels: Sequence[int], weights: Sequence[int]) -> Decimal:
    """The SCO-2 overall score: sum of weight_percent times level, divided by 100."""
    return Decimal(sum(level * weight for level, weight in zip(levels, weights, strict=True))) / 100


def display_of(value: Decimal) -> str:
    """One decimal, never a percent (SCO-9). Half-up is provisional: decision D-1."""
    return str(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _as_decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)


class _Checker:
    """Collects every problem in one document, so a failing fixture reports all of them."""

    def __init__(self, rubric: Rubric) -> None:
        self.rubric = rubric
        self.errors: list[str] = []

    def fail(self, message: str) -> None:
        self.errors.append(message)

    # Shared parts ---------------------------------------------------------------

    def header(self, doc: Mapping[str, Any], contract: str) -> bool:
        if doc.get("contract") != contract:
            self.fail(f"contract must be {contract!r}")
            return False
        version = doc.get("contract_version")
        if not isinstance(version, str) or not _SEMVER.fullmatch(version):
            self.fail("contract_version must be MAJOR.MINOR.PATCH")
            return False
        if _major(version) != SUPPORTED_MAJOR:
            self.fail(f"unsupported contract version {version}: this reader supports {SUPPORTED_MAJOR}.x")
            return False
        if type(doc.get("synthetic")) is not bool:
            self.fail("synthetic must be true or false")
        return True

    def evidence(self, refs: object, where: str, turn_count: int, *, minimum: int = 0) -> list[dict[str, Any]]:
        if not isinstance(refs, list):
            self.fail(f"{where}.evidence must be a list")
            return []
        valid: list[dict[str, Any]] = []
        for index, ref in enumerate(refs):
            at = f"{where}.evidence[{index}]"
            if not isinstance(ref, dict) or set(ref) != {"turn", "speaker", "quote"}:
                self.fail(f"{at} must have exactly turn, speaker and quote")
                continue
            turn = ref["turn"]
            if not _is_int(turn) or not 1 <= turn <= turn_count:
                self.fail(f"{at}.turn {turn!r} is outside the transcript (1 to {turn_count}): a fabricated turn")
            if not _one_of(ref["speaker"], SPEAKERS):
                self.fail(f"{at}.speaker must be student or client")
            quote = ref["quote"]
            if not _is_text(quote, MAX_QUOTE) or not _single_line(quote):
                self.fail(f"{at}.quote must be one trimmed line of 1 to {MAX_QUOTE} characters")
            valid.append(ref)
        # Citing one turn twice is still one turn of evidence.
        if len({ref["turn"] for ref in valid if _is_int(ref["turn"])}) < minimum:
            self.fail(f"{where}.evidence needs at least {minimum} cited turns")
        return valid

    # The report -----------------------------------------------------------------

    def report(self, doc: object) -> None:
        if not isinstance(doc, dict):
            self.fail("a report must be a JSON object")
            return
        if not self.header(doc, REPORT):
            return
        state = doc.get("state")
        if not _one_of(state, FIELD_RULES):
            self.fail(f"unknown state {state!r}: a reader shows the failure path, never a guess")
            return
        rule = FIELD_RULES[state]
        keys = set(doc)
        if missing := sorted(rule.required - keys):
            self.fail(f"{state}: missing {missing}")
        if forbidden := sorted(keys - rule.required - rule.optional):
            self.fail(f"{state}: forbidden or unknown fields {forbidden}")
        if missing or forbidden:
            # Reading further would guess at a shape this state does not have.
            return

        scenario_id = self.scenario(doc["scenario"])
        crisis = scenario_id == CRISIS_SCENARIO
        if not _one_of(doc["modality"], MODALITIES):
            self.fail("modality must be voice or text")
        if "safety" in keys and not crisis:
            self.fail(f"{state}: safety is for the crisis scenario only")
        if crisis and state in CRISIS_SAFETY_STATES and "safety" not in keys:
            # Owner decision 2026-11-23: a critical failure is never dropped (SCO-5, ETH-7).
            self.fail(f"{state}: a crisis report always carries its safety result (SCO-5)")

        if state == "pending":
            return
        self.outcome(doc, state)
        if state == "failed":
            self.failure(doc)
            return

        turn_count = doc["turn_count"]
        if not _is_int(turn_count) or not 1 <= turn_count <= MAX_TURNS:
            self.fail(f"turn_count must be 1 to {MAX_TURNS}")
            return
        self.provenance(doc["provenance"], synthetic=doc.get("synthetic") is True)
        if doc["disclaimer"] != self.rubric.disclaimer:
            self.fail("disclaimer must be the anchor spec's student_disclaimer (SCO-8)")
        self.narrative(doc, turn_count)

        categories: list[dict[str, Any]] = []
        if "categories" in doc:
            self.scale(doc["scale"])
            categories = self.categories(doc["categories"], turn_count, state)
        safety = self.safety(doc["safety"], turn_count) if "safety" in doc else None
        self.state_rules(doc, state, crisis, categories, safety)
        self.limitations(doc, state, categories)

    def scenario(self, scenario: object) -> str | None:
        if not isinstance(scenario, dict) or set(scenario) != {"id", "version"}:
            self.fail("scenario must have exactly id and version")
            return None
        if not _one_of(scenario["id"], SCENARIO_IDS):
            self.fail(f"scenario.id must be one of {list(SCENARIO_IDS)}")
        version = scenario["version"]
        if not isinstance(version, str) or not _SEMVER.fullmatch(version):
            self.fail("scenario.version must be MAJOR.MINOR.PATCH")
        return scenario["id"] if _one_of(scenario["id"], SCENARIO_IDS) else None

    def provenance(self, provenance: object, *, synthetic: bool) -> None:
        expected = {"rubric", "scoring_policy_version", "grader"}
        if not isinstance(provenance, dict) or set(provenance) != expected:
            self.fail("provenance must have exactly rubric, scoring_policy_version and grader")
            return
        rubric = provenance["rubric"]
        if not isinstance(rubric, dict) or set(rubric) != {"spec_id", "spec_version", "approval_status"}:
            self.fail("provenance.rubric must have exactly spec_id, spec_version and approval_status")
        elif (rubric["spec_id"], rubric["spec_version"]) != (self.rubric.spec_id, self.rubric.spec_version):
            self.fail("provenance.rubric must name the anchor spec this reader was built against")
        elif rubric["approval_status"] != self.rubric.approval_status:
            self.fail("provenance.rubric.approval_status must match the anchor spec, never claim approval")
        version = provenance["scoring_policy_version"]
        if not isinstance(version, str) or not _SEMVER.fullmatch(version):
            self.fail("provenance.scoring_policy_version must be MAJOR.MINOR.PATCH")
        grader = provenance["grader"]
        if not isinstance(grader, dict) or set(grader) != {"model", "prompt_version"}:
            self.fail("provenance.grader must have exactly model and prompt_version")
            return
        if not _is_text(grader["model"], 100) or not _is_text(grader["prompt_version"], 40):
            self.fail("provenance.grader model and prompt_version must be short text")
        if synthetic != (grader["model"] == SYNTHETIC_MODEL):
            self.fail(f"synthetic is true exactly when provenance.grader.model is {SYNTHETIC_MODEL!r}")

    def narrative(self, doc: Mapping[str, Any], turn_count: int) -> None:
        for key, minimum in (("strengths", 1), ("next_steps", 0)):
            items = doc[key]
            if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
                self.fail(f"{key} must list 1 to {MAX_ITEMS} items")
                continue
            for index, item in enumerate(items):
                at = f"{key}[{index}]"
                if not isinstance(item, dict) or set(item) != {"text", "evidence"}:
                    self.fail(f"{at} must have exactly text and evidence")
                    continue
                if not _is_text(item["text"], MAX_ITEM_TEXT):
                    self.fail(f"{at}.text must be trimmed text of 1 to {MAX_ITEM_TEXT} characters")
                self.evidence(item["evidence"], at, turn_count, minimum=minimum)

    def scale(self, scale: object) -> None:
        expected = {
            "min": min(self.rubric.levels),
            "max": max(self.rubric.levels),
            "levels": [{"level": n, "label": label} for n, label in sorted(self.rubric.levels.items())],
        }
        if scale != expected:
            self.fail("scale must be the anchor spec's 1-to-5 levels and labels")

    def categories(self, categories: object, turn_count: int, state: str) -> list[dict[str, Any]]:
        expected_ids = [category_id for category_id, _, _ in self.rubric.categories]
        if not isinstance(categories, list) or [
            c.get("id") if isinstance(c, dict) else None for c in categories
        ] != expected_ids:
            self.fail(f"categories must be the six RC-17 categories in order: {expected_ids}")
            return []
        for category, (category_id, name, weight) in zip(categories, self.rubric.categories, strict=True):
            at = f"categories.{category_id}"
            weight_percent = category.get("weight_percent")
            if category.get("name") != name or not _is_int(weight_percent) or weight_percent != weight:
                self.fail(f"{at}: name and weight_percent must match the anchor spec (weights are fixed, SCO-2)")
            outcome = category.get("outcome")
            if outcome == "rated":
                self.rated(category, at, turn_count, state)
            elif outcome == "abstained":
                if set(category) != {"id", "name", "weight_percent", "outcome", "reason"}:
                    self.fail(f"{at}: an abstained category carries only its reason, never a level or evidence")
                if not _one_of(category.get("reason"), self.rubric.abstention_reasons):
                    self.fail(f"{at}: reason must be one of {sorted(self.rubric.abstention_reasons)}")
            else:
                self.fail(f"{at}: outcome must be rated or abstained")
        return categories

    def rated(self, category: Mapping[str, Any], at: str, turn_count: int, state: str) -> None:
        if set(category) != {"id", "name", "weight_percent", "outcome", "level", "label", "evidence"}:
            self.fail(f"{at}: a rated category has exactly id, name, weight_percent, outcome, level, label and evidence")
            return
        level = category["level"]
        if not _is_int(level) or level not in self.rubric.levels:
            self.fail(f"{at}: level must be a whole number 1 to 5")
        elif category["label"] != self.rubric.levels[level]:
            self.fail(f"{at}: label must be the anchor spec's label for level {level}")
        # A crisis critical failure sets the scenario rating to 1 however many turns are cited.
        capped = state == "safety_not_demonstrated" and category["id"] == SCENARIO_CATEGORY
        refs = self.evidence(category["evidence"], at, turn_count, minimum=0 if capped else MIN_RATING_EVIDENCE)
        if any(ref.get("speaker") != "student" for ref in refs):
            self.fail(f"{at}: a rating cites student turns only")

    def safety(self, safety: object, turn_count: int) -> str | None:
        if not isinstance(safety, dict) or set(safety) != {"result", "critical_failures"}:
            self.fail("safety must have exactly result and critical_failures")
            return None
        result, failures = safety["result"], safety["critical_failures"]
        if not _one_of(result, {"met", "not_demonstrated"}) or not isinstance(failures, list):
            self.fail("safety.result must be met or not_demonstrated, with a list of critical_failures")
            return None
        if (result == "met") != (not failures):
            self.fail("safety: met has no critical failures, and not_demonstrated has at least one")
        seen: set[str] = set()
        for index, failure in enumerate(failures):
            at = f"safety.critical_failures[{index}]"
            if not isinstance(failure, dict) or set(failure) != {"id", "evidence"}:
                self.fail(f"{at} must have exactly id and evidence")
                continue
            if not _one_of(failure["id"], self.rubric.critical_failures) or failure["id"] in seen:
                self.fail(f"{at}.id must be a distinct id from {sorted(self.rubric.critical_failures)}")
            if isinstance(failure["id"], str):
                seen.add(failure["id"])
            refs = self.evidence(failure["evidence"], at, turn_count, minimum=1)
            if not any(ref.get("speaker") == "client" for ref in refs):
                self.fail(f"{at}: a critical failure cites the client's disclosure turn")
        return result if isinstance(result, str) else None

    def state_rules(
        self,
        doc: Mapping[str, Any],
        state: str,
        crisis: bool,
        categories: Sequence[Mapping[str, Any]],
        safety: str | None,
    ) -> None:
        rated = [c for c in categories if c.get("outcome") == "rated"]
        all_rated = bool(categories) and len(rated) == len(categories)
        if state == "scored":
            if not all_rated:
                self.fail("scored: every category must be rated")
            if crisis and safety != "met":
                self.fail("scored: a crisis report needs safety met; a failure is safety_not_demonstrated")
        elif state == "safety_not_demonstrated":
            if not crisis:
                self.fail("safety_not_demonstrated: crisis scenario only")
            if safety != "not_demonstrated":
                self.fail("safety_not_demonstrated: safety.result must be not_demonstrated")
            scenario = next((c for c in categories if c.get("id") == SCENARIO_CATEGORY), None)
            if scenario is not None and (scenario.get("outcome"), scenario.get("level")) != ("rated", 1):
                self.fail("safety_not_demonstrated: a critical failure sets scenario_specific_competence to level 1")
            if all_rated != ("overall" in doc):
                self.fail("safety_not_demonstrated: overall is present exactly when every category is rated")
        elif state == "insufficient_evidence":
            if all_rated or not categories:
                self.fail("insufficient_evidence: at least one category must abstain")
            if safety == "not_demonstrated":
                self.fail("insufficient_evidence: a critical failure is safety_not_demonstrated")
        if "overall" in doc and all_rated:
            role = "secondary" if state == "safety_not_demonstrated" else "primary"
            self.overall(doc["overall"], rated, role)

    def overall(self, overall: object, rated: Sequence[Mapping[str, Any]], role: str) -> None:
        if not isinstance(overall, dict) or set(overall) != {"value", "display", "role"}:
            self.fail("overall must have exactly value, display and role")
            return
        levels = [c.get("level") for c in rated]
        valid: list[int] = [level for level in levels if _is_int(level) and level in self.rubric.levels]
        if len(valid) != len(levels):
            return  # Each bad level is already reported, and no overall can be checked from it.
        # The rubric's weights, not the report's: a changed weight never moves the overall.
        expected = weighted_mean(valid, [w for _, _, w in self.rubric.categories])
        value = _as_decimal(overall["value"])
        if value != expected:
            self.fail(f"overall.value must be the SCO-2 weighted mean {expected}, computed in code")
        display = overall["display"]
        if not isinstance(display, str) or not _DISPLAY.fullmatch(display) or display != display_of(expected):
            self.fail(f"overall.display must be {display_of(expected)!r}: one decimal, no percent (SCO-9)")
        if overall["role"] != role:
            self.fail(f"overall.role must be {role!r} here (SCO-5: a safety failure leads)")

    def outcome(self, doc: Mapping[str, Any], state: str) -> None:
        saved = doc["score_record_saved"]
        expected_saved = state == "scored" or (state == "safety_not_demonstrated" and "overall" in doc)
        if saved is not expected_saved:
            self.fail(f"{state}: score_record_saved must be {str(expected_saved).lower()}")
        actions = _strings(doc["actions"])
        if actions is None:
            self.fail("actions must be a list of distinct action names")
            return
        if state == "failed":
            failure = doc.get("failure")
            expected = {"new_practice"}
            if isinstance(failure, dict):
                if failure.get("reason") in RETRYABLE_REASONS and failure.get("conversation_available") is True:
                    expected.add("retry_grading")
                if failure.get("reason") in NEW_TEXT_SESSION_REASONS:
                    expected.add("new_text_session")
        else:
            expected = set(REPORT_ACTIONS)
        if set(actions) != expected:
            self.fail(f"{state}: actions must be {sorted(expected)}")

    def failure(self, doc: Mapping[str, Any]) -> None:
        failure = doc["failure"]
        if not isinstance(failure, dict) or set(failure) != {"reason", "conversation_available"}:
            self.fail("failure must have exactly reason and conversation_available")
            return
        if not _one_of(failure["reason"], FAILURE_REASONS):
            self.fail(f"failure.reason must be one of {sorted(FAILURE_REASONS)}")
        if type(failure["conversation_available"]) is not bool:
            self.fail("failure.conversation_available must be true or false (REC-4)")
        elif failure["reason"] == "lost_content" and failure["conversation_available"]:
            self.fail("failure: lost_content means the conversation is not available (REC-2)")

    def limitations(self, doc: Mapping[str, Any], state: str, categories: Sequence[Mapping[str, Any]]) -> None:
        expected: set[str] = set()
        if state == "narrative_only":
            expected.add("numerical_results_not_enabled")
        if any(c.get("outcome") == "abstained" for c in categories):
            expected.add("categories_not_rated")
        if "overall" not in doc:
            expected.add("no_overall_score")
        elif state == "safety_not_demonstrated":
            expected.add("average_is_secondary")
        if self.rubric.approval_status != "approved":
            expected.add("rubric_not_approved")
        if doc.get("synthetic") is True:
            expected.add("synthetic_example")
        limitations = _strings(doc["limitations"])
        if limitations is None:
            self.fail("limitations must be a list of distinct limitation codes")
        elif set(limitations) != expected:
            self.fail(f"{state}: limitations must be {sorted(expected)}")

    # History --------------------------------------------------------------------

    def history(self, doc: object) -> None:
        if not isinstance(doc, dict):
            self.fail("a history must be a JSON object")
            return
        if not self.header(doc, HISTORY):
            return
        if set(doc) != {"contract", "contract_version", "synthetic", "entries"}:
            self.fail(f"history: forbidden or unknown fields {sorted(set(doc) - {'contract', 'contract_version', 'synthetic', 'entries'})}")
        entries = doc.get("entries")
        if not isinstance(entries, list):
            self.fail("history.entries must be a list")
            return
        times = [self.entry(entry, index) for index, entry in enumerate(entries)]
        known = [t for t in times if t is not None]
        if known != sorted(known, reverse=True) or len(set(known)) != len(known):
            self.fail("history.entries must be newest first by completed_at, with no ties (REP-5)")
        ids = [e.get("record_id") for e in entries if isinstance(e, dict)]
        if len(set(map(str, ids))) != len(ids):
            self.fail("history.entries must have distinct record_id values")

    def entry(self, entry: object, index: int) -> str | None:
        at = f"entries[{index}]"
        allowed = {"record_id", "scenario_id", "completed_at", "overall", "categories", "provenance", "safety_result"}
        if not isinstance(entry, dict):
            self.fail(f"{at} must be an object")
            return None
        if unknown := sorted(set(entry) - allowed):
            self.fail(f"{at}: forbidden or unknown fields {unknown}: history holds score-record fields only (REP-3)")
        if missing := sorted(allowed - {"safety_result"} - set(entry)):
            self.fail(f"{at}: missing {missing}")
            return None
        if not isinstance(entry["record_id"], str) or not _RECORD_ID.fullmatch(entry["record_id"]):
            self.fail(f"{at}.record_id must be 1 to 64 lowercase letters, digits or hyphens")
        crisis = entry["scenario_id"] == CRISIS_SCENARIO
        if not _one_of(entry["scenario_id"], SCENARIO_IDS):
            self.fail(f"{at}.scenario_id must be one of {list(SCENARIO_IDS)}")
        if crisis != ("safety_result" in entry):
            self.fail(f"{at}: a crisis entry has a safety_result and no other entry does (REP-4)")
        elif crisis and not _one_of(entry["safety_result"], {"met", "not_demonstrated"}):
            self.fail(f"{at}.safety_result must be met or not_demonstrated")
        levels = self.entry_categories(entry["categories"], at)
        if levels is not None:
            self.entry_overall(entry["overall"], levels, at)
            if crisis and entry.get("safety_result") == "not_demonstrated" and levels[-1] != 1:
                self.fail(f"{at}: a critical failure sets scenario_specific_competence to level 1")
        self.entry_provenance(entry["provenance"], at)
        completed_at = entry["completed_at"]
        if not isinstance(completed_at, str) or not _is_utc_time(completed_at):
            self.fail(f"{at}.completed_at must be a server-set UTC time like 2026-11-20T15:04:05Z")
            return None
        return completed_at

    def entry_categories(self, categories: object, at: str) -> list[int] | None:
        expected_ids = [category_id for category_id, _, _ in self.rubric.categories]
        if (
            not isinstance(categories, list)
            or not all(isinstance(c, dict) and set(c) == {"id", "level"} for c in categories)
            or [c["id"] for c in categories] != expected_ids
        ):
            self.fail(f"{at}.categories must be the six categories in order, each with only id and level")
            return None
        levels = [c["level"] for c in categories]
        if not all(_is_int(level) and level in self.rubric.levels for level in levels):
            self.fail(f"{at}.categories: every level must be a whole number 1 to 5")
            return None
        return levels

    def entry_overall(self, overall: object, levels: Sequence[int], at: str) -> None:
        expected = weighted_mean(levels, [weight for _, _, weight in self.rubric.categories])
        if not isinstance(overall, dict) or set(overall) != {"value", "display"}:
            self.fail(f"{at}.overall must have exactly value and display")
        elif _as_decimal(overall["value"]) != expected or overall["display"] != display_of(expected):
            self.fail(f"{at}.overall must be value {expected} and display {display_of(expected)!r}")

    def entry_provenance(self, provenance: object, at: str) -> None:
        if provenance is None:
            return
        if (
            not isinstance(provenance, dict)
            or set(provenance) != {"rubric_spec_version", "scoring_policy_version"}
            or not all(isinstance(v, str) and _SEMVER.fullmatch(v) for v in provenance.values())
        ):
            self.fail(f"{at}.provenance must be null or exactly rubric_spec_version and scoring_policy_version")


def check_report(doc: object, rubric: Rubric) -> list[str]:
    checker = _Checker(rubric)
    checker.report(doc)
    return checker.errors


def check_history(doc: object, rubric: Rubric) -> list[str]:
    checker = _Checker(rubric)
    checker.history(doc)
    return checker.errors


def check_document(doc: object, rubric: Rubric) -> list[str]:
    """Check a report or a history, chosen by its ``contract`` field."""
    contract = doc.get("contract") if isinstance(doc, dict) else None
    if contract == HISTORY:
        return check_history(doc, rubric)
    return check_report(doc, rubric)


def compare(a: Mapping[str, Any], b: Mapping[str, Any]) -> str:
    """The history comparison indication between two entries (contract, "Comparison")."""
    if a["scenario_id"] != b["scenario_id"]:
        return "incompatible"
    if a["provenance"] is None or b["provenance"] is None:
        return "unknown"
    for key in ("rubric_spec_version", "scoring_policy_version"):
        if _major(a["provenance"][key]) != _major(b["provenance"][key]):
            return "incompatible"
    return "compatible"


# JSON Patch (RFC 6902): add, remove and replace, enough to express each invalid case
# as a small change to a valid fixture.


def _pointer(path: str) -> list[str]:
    if not path.startswith("/"):
        raise ValueError(f"JSON Pointer must start with '/': {path!r}")
    return [part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/")]


def _step(container: Any, part: str) -> Any:
    return container[int(part)] if isinstance(container, list) else container[part]


def apply_patch(document: Any, operations: Sequence[Mapping[str, Any]]) -> Any:
    result = copy.deepcopy(document)
    for operation in operations:
        *parents, last = _pointer(operation["path"])
        target = result
        for part in parents:
            target = _step(target, part)
        op = operation["op"]
        if op == "remove":
            del target[int(last) if isinstance(target, list) else last]
        elif op in {"add", "replace"}:
            value = copy.deepcopy(operation["value"])
            if isinstance(target, list):
                index = len(target) if last == "-" else int(last)
                if op == "add":
                    target.insert(index, value)
                else:
                    target[index] = value
            else:
                if op == "replace" and last not in target:
                    raise KeyError(f"replace needs an existing member: {operation['path']}")
                target[last] = value
        else:
            raise ValueError(f"unsupported patch op {op!r}")
    return result


# Running over the report/ folder -----------------------------------------------


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON")


def _load(path: Path) -> Any:
    """Strict JSON: NaN and Infinity are rejected, as RFC 8259 requires."""
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)


def check_fixtures(report_dir: Path, rubric: Rubric) -> list[str]:
    problems: list[str] = []
    fixtures_dir = report_dir / "fixtures" / "v1"
    fixtures = sorted(fixtures_dir.glob("*.json"))
    if not fixtures:
        return [f"{fixtures_dir}: no fixtures found"]
    states = set()
    for path in fixtures:
        doc = _load(path)
        if not isinstance(doc, dict) or doc.get("synthetic") is not True:
            problems.append(f"{path.name}: a fixture must say synthetic: true")
        problems += [f"{path.name}: {error}" for error in check_document(doc, rubric)]
        if isinstance(doc, dict) and doc.get("contract") == REPORT:
            states.add(doc.get("state"))
    if missing := sorted(set(STATES) - states):
        problems.append(f"fixtures: no fixture for states {missing}")
    return problems


def check_invalid_cases(report_dir: Path, rubric: Rubric) -> list[str]:
    problems: list[str] = []
    cases_dir = report_dir / "validation-cases" / "v1" / "invalid"
    cases = sorted(cases_dir.glob("*.json"))
    if not cases:
        return [f"{cases_dir}: no invalid cases found"]
    for path in cases:
        case = _load(path)
        base = _load(report_dir / "fixtures" / "v1" / case["base"])
        errors = check_document(apply_patch(base, case["patch"]), rubric)
        if not any(case["rejects_because"] in error for error in errors):
            problems.append(f"{path.name}: expected a rejection containing {case['rejects_because']!r}, got {errors}")
    return problems


def check_comparisons(report_dir: Path) -> list[str]:
    cases = _load(report_dir / "validation-cases" / "v1" / "comparisons.json")
    history = _load(report_dir / "fixtures" / "v1" / cases["history"])
    by_id = {entry["record_id"]: entry for entry in history["entries"]}
    problems = []
    for pair in cases["pairs"]:
        got = compare(by_id[pair["a"]], by_id[pair["b"]])
        if got != pair["expected"] or compare(by_id[pair["b"]], by_id[pair["a"]]) != got:
            problems.append(f"comparisons: {pair['a']} vs {pair['b']} gave {got}, expected {pair['expected']}")
    return problems


def run(report_dir: Path = DEFAULT_REPORT_DIR, rubric_path: Path = DEFAULT_RUBRIC) -> list[str]:
    rubric = load_rubric(rubric_path)
    steps: tuple[Callable[[], list[str]], ...] = (
        lambda: check_fixtures(report_dir, rubric),
        lambda: check_invalid_cases(report_dir, rubric),
        lambda: check_comparisons(report_dir),
    )
    return [problem for step in steps for problem in step()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--rubric", type=Path, default=DEFAULT_RUBRIC)
    args = parser.parse_args(argv)
    problems = run(args.report_dir, args.rubric)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(f"report contract check: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    print("report contract check: fixtures valid, invalid cases rejected, comparisons as expected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
