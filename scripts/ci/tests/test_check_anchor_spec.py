"""Tests for scripts/ci/check_anchor_spec.py.

Each failure test mutates a fresh copy of the real spec, so the test also proves the
real spec does not break the rule it checks. Standard library only.
Run from the repository root: python -m unittest discover -s scripts/ci/tests -v
"""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

_SCRIPT = Path(__file__).resolve().parents[1] / "check_anchor_spec.py"
_SPEC = importlib.util.spec_from_file_location("check_anchor_spec", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
checker = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = checker
_SPEC.loader.exec_module(checker)

REAL_SPEC: dict[str, Any] = checker.load_spec(checker.DEFAULT_SPEC)


def fresh() -> dict[str, Any]:
    return copy.deepcopy(REAL_SPEC)


def category(spec: dict[str, Any], category_id: str) -> dict[str, Any]:
    return next(c for c in spec["categories"] if c["id"] == category_id)


def variant(spec: dict[str, Any], scenario: str) -> dict[str, Any]:
    scenario_category = category(spec, checker.SCENARIO_CATEGORY)
    return next(v for v in scenario_category["scenario_variants"] if v["scenario"] == scenario)


class RealSpecTest(unittest.TestCase):
    def test_real_spec_is_valid(self) -> None:
        self.assertEqual(checker.validate(REAL_SPEC), [])

    def test_weights_sum_to_100(self) -> None:
        self.assertEqual(sum(c["weight_percent"] for c in REAL_SPEC["categories"]), 100)

    def test_every_rated_unit_has_five_levels(self) -> None:
        units = [c for c in REAL_SPEC["categories"] if "levels" in c]
        units += category(REAL_SPEC, checker.SCENARIO_CATEGORY)["scenario_variants"]
        self.assertEqual(len(units), 8)  # five general categories and three scenarios
        for unit in units:
            self.assertEqual([lvl["level"] for lvl in unit["levels"]], [1, 2, 3, 4, 5])

    def test_crisis_requires_every_safety_criterion(self) -> None:
        self.assertEqual(
            variant(REAL_SPEC, "crisis_risk")["required_criteria"], ["CR-1", "CR-2", "CR-3"]
        )

    def test_crisis_failure_always_rates_the_crisis_category(self) -> None:
        # SCO-5 and ETH-7: an abstention elsewhere must never drop a critical failure.
        rule = REAL_SPEC["crisis_critical_failures"]["safety_result_rule"]
        self.assertIn("whatever any category or other rule yields", rule)
        harm_cap = REAL_SPEC["evidence_policy"]["harm_cap_rule"]
        self.assertIn("even when CR-1, CR-2 or CR-3 is insufficient", harm_cap)
        self.assertIn("regardless of how many student turns are cited", harm_cap)
        # Owner escalation 4 is open: the spec must not exempt uncertain-recognition turns.
        self.assertNotIn("is not found", rule)

    def test_only_pa4_instruments_are_cited(self) -> None:
        cited = {s["id"] for s in REAL_SPEC["sources"] if s["family"] != "project_requirement"}
        self.assertLessEqual(cited, checker.PA4_SOURCES)

    def test_markdown_copy_is_current(self) -> None:
        markdown = checker.markdown_path_for(checker.DEFAULT_SPEC)
        current = markdown.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(
            current,
            checker.render_markdown(REAL_SPEC),
            "run: python scripts/ci/check_anchor_spec.py --write-markdown",
        )

    def test_markdown_shows_every_criterion_and_failure(self) -> None:
        rendered = checker.render_markdown(REAL_SPEC)
        for cat in REAL_SPEC["categories"]:
            for criterion in cat.get("criteria", []):
                self.assertIn(f"##### {criterion['id']} ", rendered)
        for scenario_variant in category(REAL_SPEC, checker.SCENARIO_CATEGORY)["scenario_variants"]:
            for criterion in scenario_variant["criteria"]:
                self.assertIn(f"##### {criterion['id']} ", rendered)
        for failure in REAL_SPEC["crisis_critical_failures"]["failures"]:
            self.assertIn(f"### {failure['id']} ", rendered)


class SpecRuleTestCase(unittest.TestCase):
    def assertBreaks(self, spec: object, fragment: str) -> None:
        errors = checker.validate(spec)
        self.assertTrue(
            any(fragment in error for error in errors),
            f"expected an error containing {fragment!r}, got {errors}",
        )


class RuleViolationTest(SpecRuleTestCase):
    def test_top_level_must_be_an_object(self) -> None:
        self.assertBreaks([], "top level must be a JSON object")

    def test_missing_top_level_key(self) -> None:
        spec = fresh()
        del spec["crisis_critical_failures"]
        self.assertBreaks(spec, "missing top-level keys")

    def test_bad_semver(self) -> None:
        spec = fresh()
        spec["spec_version"] = "v1"
        self.assertBreaks(spec, "not MAJOR.MINOR.PATCH")

    def test_bad_approval_status(self) -> None:
        spec = fresh()
        spec["approval"]["status"] = "final"
        self.assertBreaks(spec, "approval.status")

    def test_wrong_weight(self) -> None:
        spec = fresh()
        category(spec, "structure_professionalism")["weight_percent"] = 15
        self.assertBreaks(spec, "SCO-2")

    def test_categories_out_of_order(self) -> None:
        spec = fresh()
        spec["categories"][0], spec["categories"][1] = spec["categories"][1], spec["categories"][0]
        self.assertBreaks(spec, "RC-17")

    def test_missing_category(self) -> None:
        spec = fresh()
        spec["categories"].pop()
        self.assertBreaks(spec, "expected")

    def test_missing_level(self) -> None:
        spec = fresh()
        category(spec, "empathic_engagement")["levels"].pop(2)
        self.assertBreaks(spec, "levels are (1, 2, 4, 5)")

    def test_missing_scenario_level(self) -> None:
        spec = fresh()
        variant(spec, "resistant_client")["levels"].pop()
        self.assertBreaks(spec, "resistant_client: levels are")

    def test_empty_anchor(self) -> None:
        spec = fresh()
        category(spec, "questioning_exploration")["levels"][0]["behavior_anchor"] = " "
        self.assertBreaks(spec, "behavior_anchor is empty")

    def test_missing_scenario_variant(self) -> None:
        spec = fresh()
        category(spec, checker.SCENARIO_CATEGORY)["scenario_variants"].pop()
        self.assertBreaks(spec, "scenario variants are")

    def test_required_criterion_must_exist(self) -> None:
        spec = fresh()
        variant(spec, "crisis_risk")["required_criteria"].append("CR-9")
        self.assertBreaks(spec, "required_criteria ['CR-9']")

    def test_general_category_needs_three_criteria(self) -> None:
        spec = fresh()
        category(spec, "empathic_engagement")["criteria"].pop()
        self.assertBreaks(spec, "has 2 criteria")

    def test_criterion_needs_insufficient_evidence_rule(self) -> None:
        spec = fresh()
        del category(spec, "active_listening_responding")["criteria"][0]["insufficient_evidence"]
        self.assertBreaks(spec, "insufficient_evidence is empty")

    def test_criterion_needs_examples(self) -> None:
        spec = fresh()
        category(spec, "active_listening_responding")["criteria"][0]["negative_examples"] = []
        self.assertBreaks(spec, "negative_examples must list")

    def test_duplicate_criterion_id(self) -> None:
        spec = fresh()
        category(spec, "questioning_exploration")["criteria"][0]["id"] = "EE-1"
        self.assertBreaks(spec, "duplicate id 'EE-1'")

    def test_bad_criterion_id(self) -> None:
        spec = fresh()
        category(spec, "questioning_exploration")["criteria"][0]["id"] = "question-1"
        self.assertBreaks(spec, "id must look like AB-1")

    def test_unknown_source(self) -> None:
        spec = fresh()
        category(spec, "empathic_engagement")["criteria"][0]["citations"][0]["source"] = "nope"
        self.assertBreaks(spec, "unknown source 'nope'")

    def test_excluded_source_cited(self) -> None:
        spec = fresh()
        category(spec, "empathic_engagement")["criteria"][0]["citations"][0]["source"] = "ccs-r"
        self.assertBreaks(spec, "excluded source 'ccs-r'")

    def test_excluded_source_listed_as_source(self) -> None:
        spec = fresh()
        spec["sources"].append(dict(spec["sources"][0], id="miti-manual"))
        self.assertBreaks(spec, "excluded and cannot be sources")

    def test_exclusion_cannot_be_dropped(self) -> None:
        spec = fresh()
        spec["excluded_sources"] = [e for e in spec["excluded_sources"] if e["id"] != "miti-manual"]
        self.assertBreaks(spec, "must keep excluding ['miti-manual']")

    def test_duplicate_source_id(self) -> None:
        spec = fresh()
        spec["sources"].append(dict(spec["sources"][0]))
        self.assertBreaks(spec, "duplicate source id")

    def test_bad_relation_marker(self) -> None:
        spec = fresh()
        category(spec, "empathic_engagement")["criteria"][0]["citations"][0]["relation"] = "copied"
        self.assertBreaks(spec, "relation 'copied'")

    def test_citation_required(self) -> None:
        spec = fresh()
        category(spec, "empathic_engagement")["criteria"][0]["citations"] = []
        self.assertBreaks(spec, "must cite at least one source")

    def test_source_needs_https(self) -> None:
        spec = fresh()
        spec["sources"][0]["url"] = "http://example.com"
        self.assertBreaks(spec, "https")

    def test_unknown_source_family(self) -> None:
        spec = fresh()
        spec["sources"][0]["family"] = "blogs"
        self.assertBreaks(spec, "family 'blogs'")

    def test_crisis_failure_removed(self) -> None:
        spec = fresh()
        spec["crisis_critical_failures"]["failures"].pop()
        self.assertBreaks(spec, "RC-19")

    def test_crisis_failure_added(self) -> None:
        spec = fresh()
        failures = spec["crisis_critical_failures"]["failures"]
        failures.append(dict(failures[0], id="CF-EXTRA"))
        self.assertBreaks(spec, "RC-19")

    def test_crisis_failure_needs_non_examples(self) -> None:
        spec = fresh()
        spec["crisis_critical_failures"]["failures"][0]["not_a_failure"] = []
        self.assertBreaks(spec, "not_a_failure must list")

    def test_crisis_override_scoped_to_crisis(self) -> None:
        spec = fresh()
        spec["crisis_critical_failures"]["applies_to"] = "routine_intake"
        self.assertBreaks(spec, "applies_to must be 'crisis_risk'")

    def test_instrument_name_in_student_text(self) -> None:
        spec = fresh()
        category(spec, "empathic_engagement")["levels"][4]["student_description"] = (
            "Your MITI empathy score is high."
        )
        self.assertBreaks(spec, "'MITI'")

    def test_instrument_name_in_scale_label(self) -> None:
        spec = fresh()
        spec["scale"]["levels"][2]["label"] = "ENACT competent"
        self.assertBreaks(spec, "'ENACT'")

    def test_percent_in_student_text(self) -> None:
        spec = fresh()
        spec["scale"]["levels"][4]["meaning"] = "Top 10% of students."
        self.assertBreaks(spec, "'%'")

    def test_banned_terms_respect_word_boundaries(self) -> None:
        spec = fresh()
        spec["scale"]["levels"][4]["meaning"] = "Your first emphasis was clear."
        self.assertEqual(checker.validate(spec), [])

    def test_scale_must_be_one_to_five(self) -> None:
        spec = fresh()
        spec["scale"]["max"] = 4
        self.assertBreaks(spec, "must run from 1 to 5")

    def test_wrong_scenarios(self) -> None:
        spec = fresh()
        spec["scenarios"][2]["id"] = "crisis"
        self.assertBreaks(spec, "scenarios: ids are")

    def test_forbidden_fallbacks_required(self) -> None:
        spec = fresh()
        spec["evidence_policy"]["forbidden_fallbacks"] = []
        self.assertBreaks(spec, "forbidden_fallbacks")

    def test_reports_every_error_at_once(self) -> None:
        spec = fresh()
        spec["spec_version"] = "one"
        category(spec, "structure_professionalism")["weight_percent"] = 11
        self.assertGreaterEqual(len(checker.validate(spec)), 2)


class ApprovalTest(unittest.TestCase):
    """Only the owner approves a version (Issue #21), so approval must say who and when."""

    def approve(self, by: object, on: object) -> list[str]:
        spec = fresh()
        spec["approval"] = {"status": "approved", "approved_by": by, "approved_on": on}
        errors: list[str] = checker.validate(spec)
        return errors

    def test_full_approval_is_valid(self) -> None:
        self.assertEqual(self.approve("Project owner", "2026-11-22"), [])

    def test_approval_needs_an_approver(self) -> None:
        self.assertTrue(any("name the approver" in e for e in self.approve(None, "2026-11-22")))

    def test_approval_needs_a_date(self) -> None:
        for bad_date in (None, "22 Nov 2026", 20261122):
            with self.subTest(bad_date=bad_date):
                errors = self.approve("Project owner", bad_date)
                self.assertTrue(any("YYYY-MM-DD" in e for e in errors), errors)

    def test_proposal_has_no_approver(self) -> None:
        spec = fresh()
        spec["approval"] = {"status": "proposed", "approved_by": "Someone", "approved_on": None}
        self.assertTrue(any("a proposed spec has no" in e for e in checker.validate(spec)))


class HardeningTest(SpecRuleTestCase):
    """Rules added after review: malformed values, PA-4 and the wider student-text scope."""

    def test_unhashable_values_are_errors_not_crashes(self) -> None:
        cases: list[tuple[str, Any]] = [
            ("approval.status", lambda s: s["approval"].__setitem__("status", ["approved"])),
            ("family", lambda s: s["sources"][0].__setitem__("family", ["common_factors"])),
            (
                "unknown source",
                lambda s: category(s, "empathic_engagement")["criteria"][0]["citations"][
                    0
                ].__setitem__("source", {"id": "fis"}),
            ),
            (
                "relation",
                lambda s: category(s, "empathic_engagement")["criteria"][0]["citations"][
                    0
                ].__setitem__("relation", ["direct"]),
            ),
            (
                "required_criteria",
                lambda s: variant(s, "crisis_risk")["required_criteria"].append(["CR-1"]),
            ),
            (
                "RC-19",
                lambda s: s["crisis_critical_failures"]["failures"][0].__setitem__("id", ["CF"]),
            ),
        ]
        for fragment, mutate in cases:
            with self.subTest(fragment=fragment):
                spec = fresh()
                mutate(spec)
                self.assertBreaks(spec, fragment)

    def test_bool_and_float_are_not_levels_or_weights(self) -> None:
        cases: list[tuple[str, Any]] = [
            (
                "RC-17",
                lambda s: category(s, "empathic_engagement")["levels"][0].__setitem__(
                    "level", True
                ),
            ),
            ("RC-17", lambda s: s["scale"]["levels"][0].__setitem__("level", 1.0)),
            (
                "SCO-2",
                lambda s: category(s, "empathic_engagement").__setitem__("weight_percent", 20.0),
            ),
            ("must run from 1 to 5", lambda s: s["scale"].__setitem__("min", True)),
        ]
        for fragment, mutate in cases:
            with self.subTest(fragment=fragment):
                spec = fresh()
                mutate(spec)
                self.assertBreaks(spec, fragment)

    def test_source_outside_pa4_fails(self) -> None:
        spec = fresh()
        spec["sources"].append(dict(spec["sources"][0], id="bsed", family="social_work_mft"))
        self.assertBreaks(spec, "'bsed' is not a free instrument listed in plan PA-4")

    def test_project_requirement_family_cannot_admit_an_instrument(self) -> None:
        spec = fresh()
        sdd = next(s for s in spec["sources"] if s["family"] == "project_requirement")
        spec["sources"].append(dict(sdd, id="bsed"))
        self.assertBreaks(spec, "'bsed' is not a known project requirement source")

    def test_excluded_instrument_under_another_id_fails(self) -> None:
        for name in ("MITI 4.2.1 coding manual", "Counselor Competencies Scale-Revised"):
            with self.subTest(name=name):
                spec = fresh()
                spec["sources"][0]["citation"] = name
                self.assertBreaks(spec, "excluded instrument under another id")

    def test_required_sections_are_checked_before_rendering(self) -> None:
        cases: list[tuple[str, Any]] = [
            (
                "assessment_boundaries.assess_only",
                lambda s: s["assessment_boundaries"].pop("assess_only"),
            ),
            (
                "assessment_boundaries.never_penalize",
                lambda s: s["assessment_boundaries"].__setitem__("never_penalize", []),
            ),
            (
                "criterion_outcomes.insufficient",
                lambda s: s["evidence_policy"]["criterion_outcomes"].pop("insufficient"),
            ),
            ("scenarios[crisis_risk]", lambda s: s["scenarios"][2].pop("name")),
            ("excluded_sources[0]", lambda s: s["excluded_sources"][0].pop("name")),
            ("title", lambda s: s.__setitem__("title", 7)),
            ("satisfies", lambda s: s.__setitem__("satisfies", "RC-17")),
        ]
        for fragment, mutate in cases:
            with self.subTest(fragment=fragment):
                spec = fresh()
                mutate(spec)
                self.assertBreaks(spec, fragment)

    def test_only_the_scenario_category_has_variants(self) -> None:
        spec = fresh()
        scenario_variants = category(spec, checker.SCENARIO_CATEGORY)["scenario_variants"]
        category(spec, "empathic_engagement")["scenario_variants"] = copy.deepcopy(
            scenario_variants
        )
        self.assertBreaks(spec, "only scenario_specific_competence may have scenario_variants")

    def test_banned_terms_in_every_visible_name(self) -> None:
        cases: list[tuple[str, Any]] = [
            (
                "scenarios[routine_intake].name",
                lambda s: s["scenarios"][0].__setitem__("name", "MITI intake"),
            ),
            (
                "EE-1.name",
                lambda s: category(s, "empathic_engagement")["criteria"][0].__setitem__(
                    "name", "ENACT empathy"
                ),
            ),
            (
                "crisis_risk.focus",
                lambda s: variant(s, "crisis_risk").__setitem__(
                    "focus", "Scored as in the Suicide Intervention Response Inventory."
                ),
            ),
            (
                "CR-1.name",
                lambda s: variant(s, "crisis_risk")["criteria"][0].__setitem__(
                    "name", "Motivational Interviewing Treatment Integrity safety"
                ),
            ),
        ]
        for fragment, mutate in cases:
            with self.subTest(fragment=fragment):
                spec = fresh()
                mutate(spec)
                self.assertBreaks(spec, fragment)


class CommandLineTest(unittest.TestCase):
    def run_main(self, *args: str) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = checker.main(list(args))
        return code, out.getvalue() + err.getvalue()

    def write_spec(self, directory: Path, spec: object) -> Path:
        path = directory / "anchor-spec.v1.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        return path

    def test_real_spec_passes(self) -> None:
        code, output = self.run_main()
        self.assertEqual(code, 0, output)

    def test_write_then_check_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_spec(Path(tmp), REAL_SPEC)
            self.assertEqual(self.run_main("--spec", str(path))[0], 1)  # no copy yet
            self.assertEqual(self.run_main("--spec", str(path), "--write-markdown")[0], 0)
            self.assertEqual(self.run_main("--spec", str(path))[0], 0)

    def test_stale_markdown_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_spec(Path(tmp), REAL_SPEC)
            self.run_main("--spec", str(path), "--write-markdown")
            markdown = checker.markdown_path_for(path)
            markdown.write_text(markdown.read_text(encoding="utf-8") + "edit\n", encoding="utf-8")
            code, output = self.run_main("--spec", str(path))
            self.assertEqual(code, 1)
            self.assertIn("out of date", output)

    def test_crlf_checkout_still_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_spec(Path(tmp), REAL_SPEC)
            markdown = checker.markdown_path_for(path)
            markdown.write_bytes(checker.render_markdown(REAL_SPEC).replace("\n", "\r\n").encode())
            self.assertEqual(self.run_main("--spec", str(path))[0], 0)

    def test_invalid_spec_fails_and_writes_nothing(self) -> None:
        spec = fresh()
        spec["spec_version"] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_spec(Path(tmp), spec)
            code, output = self.run_main("--spec", str(path), "--write-markdown")
            self.assertEqual(code, 1)
            self.assertIn("breaks 1 rule", output)
            self.assertFalse(checker.markdown_path_for(path).exists())

    def test_unreadable_json_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anchor-spec.v1.json"
            path.write_text("{not json", encoding="utf-8")
            code, output = self.run_main("--spec", str(path))
            self.assertEqual(code, 1)
            self.assertIn("Cannot read", output)


if __name__ == "__main__":
    unittest.main()
