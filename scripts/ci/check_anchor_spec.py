"""Validate the rubric anchor spec and keep its readable Markdown copy in sync.

The anchor spec (rubric/anchor-spec.v1.json) is the versioned contract that the grader
(#35) and the calibration set (#47) read. This check enforces the rules a reviewer
would otherwise have to re-check by hand on every edit:

- the six RC-17 categories, in order, with the SCO-2 weights (20/20/15/15/10/20);
- five behavior anchors per category and per scenario variant (RC-17);
- every criterion has a definition, an opportunity, minimum evidence, examples and an
  insufficient-evidence rule, so the grader can abstain instead of guessing (SCO-3);
- every citation points at a listed free source, never an excluded one (PA-4);
- the crisis critical failures are exactly the four RC-19 types;
- no instrument name or percent sign appears in score labels or student-facing text
  (SCO-6, SCO-9, AG-5).

It also renders rubric/anchor-spec.v1.md from the JSON. The Markdown is generated, so
the JSON stays the single source of truth.

Standard library only, so it runs on any Python 3.10+ without installing anything.
Run from the repository root:

    python scripts/ci/check_anchor_spec.py                   # validate and check the copy
    python scripts/ci/check_anchor_spec.py --write-markdown  # regenerate the copy
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, TypeGuard

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "rubric" / "anchor-spec.v1.json"

# RC-17 order and SCO-2 weights. A change here is a policy change, not a refactor.
EXPECTED_CATEGORIES: tuple[tuple[str, int], ...] = (
    ("empathic_engagement", 20),
    ("active_listening_responding", 20),
    ("questioning_exploration", 15),
    ("collaboration_autonomy_cultural_humility", 15),
    ("structure_professionalism", 10),
    ("scenario_specific_competence", 20),
)
SCENARIO_CATEGORY = "scenario_specific_competence"
EXPECTED_SCENARIOS = ("routine_intake", "resistant_client", "crisis_risk")
CRISIS_SCENARIO = "crisis_risk"
# RC-19 names exactly these four critical safety failures.
EXPECTED_CRISIS_FAILURES = frozenset({"CF-IGNORE", "CF-ENCOURAGE", "CF-SECRECY", "CF-NO-PRIORITY"})
EXPECTED_LEVELS = (1, 2, 3, 4, 5)
GENERAL_CRITERIA_PER_CATEGORY = 3

# PA-4: these must stay listed as excluded, and nothing may cite them.
REQUIRED_EXCLUSIONS = frozenset({"ccs-r", "miti-manual"})
SOURCE_FAMILIES = frozenset(
    {
        "counseling_core_skills",
        "common_factors",
        "social_work_mft",
        "scenario_specific",
        "project_requirement",
    }
)
CITATION_RELATIONS = frozenset({"direct", "adapted", "original"})
APPROVAL_STATUSES = frozenset({"proposed", "approved", "superseded"})
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
CRITERION_ID = re.compile(r"[A-Z]{2}-[1-9]\d*")

# SCO-6 and AG-5: a score or a student-facing label never names an instrument.
# SCO-9: the score is never a percent. Word boundaries keep "fist" or "phase" safe.
BANNED_LABEL_TERMS = re.compile(
    r"\b(MITI|ENACT|EQUIP|CTRS|CTS-R|CCS-R|FIS|SIRI|OSCE|EPAS|BSED)\b|%|\bpercent\b",
    re.IGNORECASE,
)

CRITERION_TEXT_FIELDS = (
    "id",
    "name",
    "definition",
    "opportunity",
    "minimum_evidence",
    "insufficient_evidence",
)
LEVEL_TEXT_FIELDS = ("behavior_anchor", "student_description")
REQUIRED_TOP_LEVEL = (
    "spec_id",
    "spec_version",
    "title",
    "approval",
    "intended_use",
    "scale",
    "scenarios",
    "assessment_boundaries",
    "evidence_policy",
    "sources",
    "excluded_sources",
    "categories",
    "crisis_critical_failures",
)


def _is_text(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and value.strip() != ""


def _is_text_list(value: object) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(_is_text(v) for v in value)


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class _Validator:
    """Collects every problem in one pass, so a reviewer sees them all at once."""

    def __init__(self, spec: Mapping[str, Any]) -> None:
        self.spec = spec
        self.errors: list[str] = []
        self.source_ids: set[str] = set()
        self.excluded_ids: set[str] = set()
        self.seen_ids: set[str] = set()

    def fail(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def run(self) -> list[str]:
        missing = [key for key in REQUIRED_TOP_LEVEL if key not in self.spec]
        if missing:
            self.fail("spec", f"missing top-level keys {missing}")
            return self.errors
        self._check_header()
        self._check_scale()
        self._check_scenarios()
        self._check_sources()
        self._check_categories()
        self._check_crisis_failures()
        self._check_student_text()
        return self.errors

    def _check_header(self) -> None:
        version = self.spec["spec_version"]
        if not (isinstance(version, str) and SEMVER.fullmatch(version)):
            self.fail("spec_version", f"{version!r} is not MAJOR.MINOR.PATCH")
        status = _as_dict(self.spec["approval"]).get("status")
        if status not in APPROVAL_STATUSES:
            self.fail("approval.status", f"{status!r} is not one of {sorted(APPROVAL_STATUSES)}")
        intended = _as_dict(self.spec["intended_use"])
        for key in ("purpose", "student_disclaimer"):
            if not _is_text(intended.get(key)):
                self.fail(f"intended_use.{key}", "must be non-empty text")
        if not _is_text_list(intended.get("not_for")):
            self.fail("intended_use.not_for", "must list what the scores are not for")
        policy = _as_dict(self.spec["evidence_policy"])
        for key in (
            "evidence_unit",
            "category_rating_rule",
            "harm_cap_rule",
            "conflicting_evidence_rule",
            "uncertain_recognition_rule",
            "abstention_rule",
            "overall_score_rule",
        ):
            if not _is_text(policy.get(key)):
                self.fail(f"evidence_policy.{key}", "must be non-empty text")
        for key in ("abstention_reasons", "forbidden_fallbacks"):
            if not _is_text_list(policy.get(key)):
                self.fail(f"evidence_policy.{key}", "must be a non-empty list of text")

    def _check_scale(self) -> None:
        scale = _as_dict(self.spec["scale"])
        if scale.get("min") != 1 or scale.get("max") != 5:
            self.fail("scale", "must run from 1 to 5 (RC-17)")
        levels = _as_list(scale.get("levels"))
        numbers = tuple(_as_dict(level).get("level") for level in levels)
        if numbers != EXPECTED_LEVELS:
            self.fail("scale.levels", f"levels are {numbers}, expected {EXPECTED_LEVELS}")
        for level in levels:
            for key in ("label", "meaning"):
                if not _is_text(_as_dict(level).get(key)):
                    self.fail(f"scale.levels[{_as_dict(level).get('level')}]", f"{key} is empty")

    def _check_scenarios(self) -> None:
        ids = tuple(_as_dict(s).get("id") for s in _as_list(self.spec["scenarios"]))
        if ids != EXPECTED_SCENARIOS:
            self.fail("scenarios", f"ids are {ids}, expected {EXPECTED_SCENARIOS}")

    def _check_sources(self) -> None:
        for index, source in enumerate(_as_list(self.spec["sources"])):
            source = _as_dict(source)
            where = f"sources[{index}]"
            source_id = source.get("id")
            if not _is_text(source_id):
                self.fail(where, "id is empty")
                continue
            if source_id in self.source_ids:
                self.fail(where, f"duplicate source id {source_id!r}")
            self.source_ids.add(source_id)
            if source.get("family") not in SOURCE_FAMILIES:
                self.fail(where, f"family {source.get('family')!r} is not a known family")
            for key in ("citation", "use"):
                if not _is_text(source.get(key)):
                    self.fail(where, f"{key} is empty")
            url = source.get("url")
            if not (isinstance(url, str) and url.startswith("https://")):
                self.fail(where, "url must be an https link")
        for index, excluded in enumerate(_as_list(self.spec["excluded_sources"])):
            excluded = _as_dict(excluded)
            if not _is_text(excluded.get("reason")):
                self.fail(f"excluded_sources[{index}]", "reason is empty")
            if _is_text(excluded.get("id")):
                self.excluded_ids.add(excluded["id"])
        missing = REQUIRED_EXCLUSIONS - self.excluded_ids
        if missing:
            self.fail("excluded_sources", f"must keep excluding {sorted(missing)} (PA-4)")
        overlap = self.source_ids & self.excluded_ids
        if overlap:
            self.fail("sources", f"{sorted(overlap)} are excluded and cannot be sources (PA-4)")

    def _check_categories(self) -> None:
        categories = _as_list(self.spec["categories"])
        found = tuple(
            (_as_dict(c).get("id"), _as_dict(c).get("weight_percent")) for c in categories
        )
        if found != EXPECTED_CATEGORIES:
            self.fail(
                "categories",
                f"ids and weights are {found}, expected {EXPECTED_CATEGORIES} (RC-17, SCO-2)",
            )
        for category in categories:
            category = _as_dict(category)
            where = f"categories[{category.get('id')}]"
            for key in ("name", "definition"):
                if not _is_text(category.get(key)):
                    self.fail(where, f"{key} is empty")
            if category.get("id") == SCENARIO_CATEGORY:
                self._check_scenario_variants(category, where)
                continue
            criteria = _as_list(category.get("criteria"))
            if len(criteria) != GENERAL_CRITERIA_PER_CATEGORY:
                self.fail(
                    where,
                    f"has {len(criteria)} criteria, expected {GENERAL_CRITERIA_PER_CATEGORY} "
                    "(the rating rule needs 2 of 3)",
                )
            self._check_criteria(criteria, where)
            self._check_levels(category.get("levels"), where)

    def _check_scenario_variants(self, category: Mapping[str, Any], where: str) -> None:
        variants = _as_list(category.get("scenario_variants"))
        scenarios = tuple(_as_dict(v).get("scenario") for v in variants)
        if scenarios != EXPECTED_SCENARIOS:
            self.fail(where, f"scenario variants are {scenarios}, expected {EXPECTED_SCENARIOS}")
        for variant in variants:
            variant = _as_dict(variant)
            variant_where = f"{where}.{variant.get('scenario')}"
            if not _is_text(variant.get("focus")):
                self.fail(variant_where, "focus is empty")
            criteria = _as_list(variant.get("criteria"))
            if not criteria:
                self.fail(variant_where, "has no criteria")
            self._check_criteria(criteria, variant_where)
            criterion_ids = {_as_dict(c).get("id") for c in criteria}
            required = _as_list(variant.get("required_criteria"))
            if not required:
                self.fail(variant_where, "required_criteria is empty")
            unknown = [r for r in required if r not in criterion_ids]
            if unknown:
                self.fail(variant_where, f"required_criteria {unknown} are not its criteria")
            self._check_levels(variant.get("levels"), variant_where)

    def _check_criteria(self, criteria: Sequence[Any], where: str) -> None:
        for criterion in criteria:
            criterion = _as_dict(criterion)
            criterion_id = criterion.get("id")
            criterion_where = f"{where}.{criterion_id}"
            for key in CRITERION_TEXT_FIELDS:
                if not _is_text(criterion.get(key)):
                    self.fail(criterion_where, f"{key} is empty")
            if _is_text(criterion_id):
                if not CRITERION_ID.fullmatch(criterion_id):
                    self.fail(criterion_where, "id must look like AB-1")
                self._claim_id(criterion_id, criterion_where)
            for key in ("positive_examples", "negative_examples"):
                if not _is_text_list(criterion.get(key)):
                    self.fail(criterion_where, f"{key} must list at least one example")
            self._check_citations(criterion.get("citations"), criterion_where)

    def _check_levels(self, levels: object, where: str) -> None:
        levels = _as_list(levels)
        numbers = tuple(_as_dict(level).get("level") for level in levels)
        if numbers != EXPECTED_LEVELS:
            self.fail(where, f"levels are {numbers}, expected {EXPECTED_LEVELS} (RC-17)")
        for level in levels:
            level = _as_dict(level)
            for key in LEVEL_TEXT_FIELDS:
                if not _is_text(level.get(key)):
                    self.fail(f"{where}.level{level.get('level')}", f"{key} is empty")

    def _check_crisis_failures(self) -> None:
        block = _as_dict(self.spec["crisis_critical_failures"])
        where = "crisis_critical_failures"
        if block.get("applies_to") != CRISIS_SCENARIO:
            self.fail(where, f"applies_to must be {CRISIS_SCENARIO!r} (RC-19)")
        for key in ("precedence", "safety_result_rule", "evidence_rule"):
            if not _is_text(block.get(key)):
                self.fail(f"{where}.{key}", "must be non-empty text")
        failures = _as_list(block.get("failures"))
        ids = [_as_dict(f).get("id") for f in failures]
        if len(ids) != len(set(ids)) or set(ids) != EXPECTED_CRISIS_FAILURES:
            self.fail(
                where,
                f"failures are {ids}, expected exactly {sorted(EXPECTED_CRISIS_FAILURES)} (RC-19)",
            )
        for failure in failures:
            failure = _as_dict(failure)
            failure_where = f"{where}.{failure.get('id')}"
            if _is_text(failure.get("id")):
                self._claim_id(failure["id"], failure_where)
            for key in ("name", "definition"):
                if not _is_text(failure.get(key)):
                    self.fail(failure_where, f"{key} is empty")
            for key in ("indicators", "not_a_failure"):
                if not _is_text_list(failure.get(key)):
                    self.fail(failure_where, f"{key} must list at least one item")
            self._check_citations(failure.get("citations"), failure_where)

    def _check_citations(self, citations: object, where: str) -> None:
        citations = _as_list(citations)
        if not citations:
            self.fail(where, "must cite at least one source")
        for citation in citations:
            citation = _as_dict(citation)
            source = citation.get("source")
            if source in self.excluded_ids:
                self.fail(where, f"cites excluded source {source!r} (PA-4)")
            elif source not in self.source_ids:
                self.fail(where, f"cites unknown source {source!r}")
            if citation.get("relation") not in CITATION_RELATIONS:
                self.fail(
                    where,
                    f"relation {citation.get('relation')!r} is not one of "
                    f"{sorted(CITATION_RELATIONS)}",
                )

    def _check_student_text(self) -> None:
        for where, text in _label_texts(self.spec):
            match = BANNED_LABEL_TERMS.search(text)
            if match:
                self.fail(
                    where,
                    f"uses {match.group(0)!r}; score labels and student text never name an "
                    "instrument or a percent (SCO-6, SCO-9, AG-5)",
                )

    def _claim_id(self, item_id: str, where: str) -> None:
        if item_id in self.seen_ids:
            self.fail(where, f"duplicate id {item_id!r}")
        self.seen_ids.add(item_id)


def _all_levels(spec: Mapping[str, Any]) -> Iterator[tuple[str, Mapping[str, Any]]]:
    for category in _as_list(spec.get("categories")):
        category = _as_dict(category)
        for level in _as_list(category.get("levels")):
            yield f"categories[{category.get('id')}]", _as_dict(level)
        for variant in _as_list(category.get("scenario_variants")):
            variant = _as_dict(variant)
            for level in _as_list(variant.get("levels")):
                yield f"categories[{category.get('id')}].{variant.get('scenario')}", _as_dict(level)


def _label_texts(spec: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    """Yield every score label, anchor and line of text a student can see."""
    disclaimer = _as_dict(spec.get("intended_use")).get("student_disclaimer")
    if isinstance(disclaimer, str):
        yield "intended_use.student_disclaimer", disclaimer
    for level in _as_list(_as_dict(spec.get("scale")).get("levels")):
        level = _as_dict(level)
        for key in ("label", "meaning"):
            if isinstance(level.get(key), str):
                yield f"scale.levels[{level.get('level')}].{key}", level[key]
    for category in _as_list(spec.get("categories")):
        category = _as_dict(category)
        if isinstance(category.get("name"), str):
            yield f"categories[{category.get('id')}].name", category["name"]
    for where, level in _all_levels(spec):
        for key in LEVEL_TEXT_FIELDS:
            if isinstance(level.get(key), str):
                yield f"{where}.level{level.get('level')}.{key}", level[key]


def validate(spec: object) -> list[str]:
    """Return every rule the spec breaks. An empty list means the spec is valid."""
    if not isinstance(spec, dict):
        return ["spec: top level must be a JSON object"]
    return _Validator(spec).run()


# --- Markdown rendering -------------------------------------------------------------


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _bullets(items: Sequence[Any], indent: str = "") -> list[str]:
    return [f"{indent}- {item}" for item in items]


def _render_criterion(criterion: Mapping[str, Any]) -> list[str]:
    lines = [
        f"##### {criterion['id']} {criterion['name']}",
        "",
        f"- **Definition:** {criterion['definition']}",
        f"- **Opportunity:** {criterion['opportunity']}",
        f"- **Minimum evidence:** {criterion['minimum_evidence']}",
        f"- **Insufficient evidence:** {criterion['insufficient_evidence']}",
        "- **Shows it:**",
        *_bullets(criterion["positive_examples"], "  "),
        "- **Does not show it:**",
        *_bullets(criterion["negative_examples"], "  "),
        "- **Sources:**",
    ]
    for citation in criterion["citations"]:
        note = citation.get("note", "")
        lines.append(f"  - {citation['source']} ({citation['relation']}). {note}".rstrip())
    lines.append("")
    return lines


def _render_levels(levels: Sequence[Mapping[str, Any]], labels: Mapping[int, str]) -> list[str]:
    lines = [
        "| Level | Behavior anchor (grader) | Student sees |",
        "|---|---|---|",
    ]
    for level in levels:
        label = labels.get(level["level"], "")
        lines.append(
            f"| {level['level']} {label} | {_cell(level['behavior_anchor'])} "
            f"| {_cell(level['student_description'])} |"
        )
    lines.append("")
    return lines


def render_markdown(spec: Mapping[str, Any]) -> str:
    """Render the readable copy. Call only on a spec that validates."""
    labels = {level["level"]: level["label"] for level in spec["scale"]["levels"]}
    scenario_names = {s["id"]: s["name"] for s in spec["scenarios"]}
    approval = spec["approval"]
    policy = spec["evidence_policy"]
    boundaries = spec["assessment_boundaries"]
    intended = spec["intended_use"]

    lines = [
        f"# {spec['title']}",
        "",
        (
            "<!-- Generated from rubric/anchor-spec.v1.json by scripts/ci/check_anchor_spec.py."
            " Do not edit by hand: change the JSON and run the script with --write-markdown. -->"
        ),
        "",
        f"- **Spec:** `{spec['spec_id']}` version {spec['spec_version']}",
        f"- **Status:** {approval['status']}"
        + (
            f", approved by {approval['approved_by']} on {approval['approved_on']}"
            if approval.get("approved_by")
            else ""
        ),
        f"- **Satisfies:** {', '.join(spec.get('satisfies', []))}",
        f"- **Constrained by:** {', '.join(spec.get('constrained_by', []))}",
        "",
        "## Intended use",
        "",
        intended["purpose"],
        "",
        "Not for:",
        "",
        *_bullets(intended["not_for"]),
        "",
        f'Shown to students: "{intended["student_disclaimer"]}"',
        "",
        "## Scale",
        "",
        "| Level | Label | Meaning |",
        "|---|---|---|",
        *[
            f"| {level['level']} | {level['label']} | {_cell(level['meaning'])} |"
            for level in spec["scale"]["levels"]
        ],
        "",
        "## What the grader may assess",
        "",
        boundaries["assess_only"],
        "",
        "Never infer:",
        "",
        *_bullets(boundaries["never_infer"]),
        "",
        "Never reward:",
        "",
        *_bullets(boundaries["never_reward"]),
        "",
        "Never penalize:",
        "",
        *_bullets(boundaries["never_penalize"]),
        "",
        "## Evidence and scoring rules",
        "",
        f"- **Evidence unit:** {policy['evidence_unit']}",
        f"- **Sufficient criterion:** {policy['criterion_outcomes']['sufficient']}",
        f"- **Insufficient criterion:** {policy['criterion_outcomes']['insufficient']}",
        f"- **Category rating:** {policy['category_rating_rule']}",
        f"- **Harm cap:** {policy['harm_cap_rule']}",
        f"- **Conflicting evidence:** {policy['conflicting_evidence_rule']}",
        f"- **Uncertain speech recognition:** {policy['uncertain_recognition_rule']}",
        f"- **Abstention:** {policy['abstention_rule']}",
        f"- **Abstention reasons:** {', '.join(f'`{r}`' for r in policy['abstention_reasons'])}",
        f"- **Never used as a fallback:** {', '.join(policy['forbidden_fallbacks'])}",
        f"- **Overall score:** {policy['overall_score_rule']}",
        "",
        "## Categories",
        "",
        "| Category | Weight |",
        "|---|---|",
        *[f"| {c['name']} | {c['weight_percent']}% |" for c in spec["categories"]],
        "",
    ]

    for category in spec["categories"]:
        lines += [
            f"### {category['name']} ({category['weight_percent']}%)",
            "",
            category["definition"],
            "",
        ]
        if "scenario_variants" in category:
            for variant in category["scenario_variants"]:
                required = ", ".join(variant["required_criteria"])
                lines += [
                    (
                        f"#### {scenario_names.get(variant['scenario'], variant['scenario'])}"
                        f" (`{variant['scenario']}`)"
                    ),
                    "",
                    variant["focus"],
                    "",
                    f"Required for a rating: {required}.",
                    "",
                ]
                for criterion in variant["criteria"]:
                    lines += _render_criterion(criterion)
                lines += _render_levels(variant["levels"], labels)
            continue
        lines += ["#### Criteria", ""]
        for criterion in category["criteria"]:
            lines += _render_criterion(criterion)
        lines += ["#### Levels", "", *_render_levels(category["levels"], labels)]

    crisis = spec["crisis_critical_failures"]
    lines += [
        "## Crisis critical failures",
        "",
        f"Applies to `{crisis['applies_to']}` only.",
        "",
        f"- **Precedence:** {crisis['precedence']}",
        f"- **Safety result:** {crisis['safety_result_rule']}",
        f"- **Evidence:** {crisis['evidence_rule']}",
        "",
    ]
    for failure in crisis["failures"]:
        lines += [
            f"### {failure['id']} {failure['name']}",
            "",
            failure["definition"],
            "",
            "Indicators:",
            "",
            *_bullets(failure["indicators"]),
            "",
            "Not a failure:",
            "",
            *_bullets(failure["not_a_failure"]),
            "",
            "Sources: "
            + "; ".join(f"{c['source']} ({c['relation']})" for c in failure["citations"])
            + ".",
            "",
        ]

    lines += [
        "## Sources",
        "",
        (
            "Relation markers: **direct** names the source's concept as is, **adapted** rewrites"
            " a concept in original words for a transcript, **original** is written for this"
            " project. No item text is reproduced from any instrument."
        ),
        "",
    ]
    for source in spec["sources"]:
        lines += [
            f"- **{source['id']}** ({source['family']}). {source['citation']} <{source['url']}>",
            f"  - Use: {source['use']}",
        ]
    lines += ["", "## Excluded sources", ""]
    for excluded in spec["excluded_sources"]:
        lines.append(f"- **{excluded['id']}**, {excluded['name']}. {excluded['reason']}")
    lines.append("")
    return "\n".join(lines)


# --- CLI ----------------------------------------------------------------------------


def markdown_path_for(spec_path: Path) -> Path:
    return spec_path.with_suffix(".md")


def load_spec(spec_path: Path) -> object:
    with spec_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC, help="path to the JSON spec")
    parser.add_argument(
        "--write-markdown",
        action="store_true",
        help="regenerate the Markdown copy instead of checking it",
    )
    args = parser.parse_args(argv)

    try:
        spec = load_spec(args.spec)
    except (OSError, json.JSONDecodeError) as read_error:
        print(f"Cannot read {args.spec}: {read_error}", file=sys.stderr)
        return 1

    errors = validate(spec)
    if errors or not isinstance(spec, dict):
        print(f"{args.spec} breaks {len(errors)} rule(s):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    rendered = render_markdown(spec)
    markdown_path = markdown_path_for(args.spec)
    if args.write_markdown:
        markdown_path.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Wrote {markdown_path}")
        return 0

    try:
        current = markdown_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError:
        current = None
    if current != rendered:
        print(
            f"{markdown_path} is out of date. Run: "
            "python scripts/ci/check_anchor_spec.py --write-markdown",
            file=sys.stderr,
        )
        return 1

    print(f"{args.spec.name} is valid and {markdown_path.name} is current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
