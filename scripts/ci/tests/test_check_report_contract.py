"""Tests for scripts/ci/check_report_contract.py (#59).

Most failure tests change one field of a real fixture, so each also proves that the
fixture is valid apart from the broken rule. Standard library only.
Run from the repository root: python -m unittest discover -s scripts/ci/tests -v
"""

from __future__ import annotations

import copy
import dataclasses
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from pathlib import Path
from typing import Any

_SCRIPT = Path(__file__).resolve().parents[1] / "check_report_contract.py"
_SPEC = importlib.util.spec_from_file_location("check_report_contract", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
checker = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = checker
_SPEC.loader.exec_module(checker)

RUBRIC = checker.load_rubric()
FIXTURES = checker.DEFAULT_REPORT_DIR / "fixtures" / "v1"


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def errors(doc: object) -> list[str]:
    return checker.check_document(doc, RUBRIC)


class RealFolderTest(unittest.TestCase):
    def test_every_fixture_is_valid_and_every_invalid_case_is_rejected(self) -> None:
        self.assertEqual(checker.run(), [])

    def test_there_is_a_fixture_for_every_state(self) -> None:
        states = {
            json.loads(p.read_text(encoding="utf-8")).get("state") for p in FIXTURES.glob("*.json")
        }
        self.assertTrue(set(checker.STATES) <= states)

    def test_every_fixture_is_marked_synthetic_with_the_synthetic_grader(self) -> None:
        for path in FIXTURES.glob("*.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(path.name):
                self.assertIs(doc["synthetic"], True)
                if "provenance" in doc:
                    self.assertEqual(doc["provenance"]["grader"]["model"], checker.SYNTHETIC_MODEL)
                    self.assertIn("synthetic_example", doc["limitations"])

    def test_unavailable_states_carry_no_number(self) -> None:
        # AC3: no publishable invented score in an unavailable or ineligible report.
        for name in ("pending", "narrative-only", "insufficient-evidence",
                     "safety-not-demonstrated-no-average", "failed-grading", "failed-conduct",
                     "failed-lost-content", "failed-evidence-check"):
            doc = fixture(name)
            with self.subTest(name):
                self.assertNotIn("overall", doc)
                for category in doc.get("categories", []):
                    if category["outcome"] == "abstained":
                        self.assertNotIn("level", category)
                self.assertIs(doc.get("score_record_saved", False), False)

    def test_the_main_entry_point_passes_on_the_real_folder(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(checker.main([]), 0)
        self.assertIn("fixtures valid", out.getvalue())


class ScoringTest(unittest.TestCase):
    def test_overall_is_the_fixed_weighted_mean(self) -> None:
        weights = [w for _, _, w in RUBRIC.categories]
        self.assertEqual(checker.weighted_mean([4, 4, 3, 4, 3, 3], weights), Decimal("3.55"))
        self.assertEqual(checker.weighted_mean([5] * 6, weights), Decimal(5))

    def test_display_rounds_half_up_to_one_decimal(self) -> None:
        # Half-up is provisional (decision D-1). Half-even would show 2.0 and 3.6 here.
        self.assertEqual(checker.display_of(Decimal("2.05")), "2.1")
        self.assertEqual(checker.display_of(Decimal("3.55")), "3.6")
        self.assertEqual(checker.display_of(Decimal("2.25")), "2.3")
        self.assertEqual(checker.display_of(Decimal(3)), "3.0")

    def test_a_changed_weight_does_not_move_the_expected_overall(self) -> None:
        doc = fixture("scored-standard")
        doc["categories"][0]["weight_percent"] = 25
        found = errors(doc)
        self.assertTrue(any("weights are fixed" in e for e in found))
        self.assertFalse(any("weighted mean" in e for e in found))

    def test_an_integer_overall_value_is_accepted_when_exact(self) -> None:
        doc = fixture("scored-standard")
        for category in doc["categories"]:
            category["level"], category["label"] = 3, RUBRIC.levels[3]
        doc["overall"] = {"value": 3, "display": "3.0", "role": "primary"}
        self.assertEqual(errors(doc), [])

    def test_a_boolean_level_or_turn_is_not_a_number(self) -> None:
        doc = fixture("scored-standard")
        doc["categories"][0]["level"] = True
        self.assertTrue(any("whole number" in e for e in errors(doc)))
        doc = fixture("scored-standard")
        doc["strengths"][0]["evidence"][0]["turn"] = True
        self.assertTrue(any("fabricated turn" in e for e in errors(doc)))


class StateRulesTest(unittest.TestCase):
    def test_a_rated_category_in_insufficient_evidence_still_needs_an_abstention(self) -> None:
        doc = fixture("insufficient-evidence")
        for index in (2, 3):
            doc["categories"][index] = copy.deepcopy(doc["categories"][0]) | {
                "id": RUBRIC.categories[index][0],
                "name": RUBRIC.categories[index][1],
                "weight_percent": RUBRIC.categories[index][2],
            }
        self.assertTrue(any("at least one category must abstain" in e for e in errors(doc)))

    def test_safety_not_demonstrated_is_crisis_only(self) -> None:
        doc = fixture("safety-not-demonstrated")
        doc["scenario"]["id"] = "routine_intake"
        self.assertTrue(any("crisis scenario only" in e for e in errors(doc)))

    def test_a_secondary_average_is_saved_but_none_without_an_average(self) -> None:
        with_average = fixture("safety-not-demonstrated")
        without = fixture("safety-not-demonstrated-no-average")
        self.assertIs(with_average["score_record_saved"], True)
        self.assertIs(without["score_record_saved"], False)
        without["score_record_saved"] = True
        self.assertTrue(any("score_record_saved must be false" in e for e in errors(without)))

    def test_a_safety_failure_without_an_average_must_not_carry_one(self) -> None:
        doc = fixture("safety-not-demonstrated-no-average")
        doc["overall"] = {"value": 2.0, "display": "2.0", "role": "secondary"}
        self.assertTrue(any("overall is present exactly when" in e for e in errors(doc)))

    def test_met_safety_cannot_list_a_critical_failure(self) -> None:
        doc = fixture("scored-crisis-met")
        doc["safety"]["critical_failures"] = fixture("safety-not-demonstrated")["safety"]["critical_failures"]
        self.assertTrue(any("met has no critical failures" in e for e in errors(doc)))

    def test_a_critical_failure_cites_the_client_disclosure(self) -> None:
        doc = fixture("safety-not-demonstrated")
        doc["safety"]["critical_failures"][0]["evidence"] = doc["safety"]["critical_failures"][0]["evidence"][1:]
        self.assertTrue(any("client's disclosure turn" in e for e in errors(doc)))

    def test_retry_is_offered_only_while_the_conversation_is_available(self) -> None:
        doc = fixture("failed-grading")
        doc["failure"]["conversation_available"] = False
        self.assertTrue(any("actions must be ['new_practice']" in e for e in errors(doc)))
        doc["actions"] = ["new_practice"]
        self.assertEqual(errors(doc), [])

    def test_a_failure_reason_outside_the_list_is_rejected(self) -> None:
        doc = fixture("failed-conduct")
        doc["failure"]["reason"] = "unknown"
        self.assertTrue(any("failure.reason must be one of" in e for e in errors(doc)))

    def test_a_real_report_is_valid_without_the_synthetic_marker(self) -> None:
        # The shape a production grader returns: not synthetic, a real model, no synthetic limitation.
        doc = fixture("scored-standard")
        doc["synthetic"] = False
        doc["provenance"]["grader"]["model"] = "a-production-model"
        doc["limitations"].remove("synthetic_example")
        self.assertEqual(errors(doc), [])

    def test_limitations_follow_the_rubric_approval(self) -> None:
        approved = dataclasses.replace(RUBRIC, approval_status="approved")
        doc = fixture("scored-standard")
        doc["provenance"]["rubric"]["approval_status"] = "approved"
        doc["limitations"].remove("rubric_not_approved")
        self.assertEqual(checker.check_report(doc, approved), [])

    def test_a_quote_must_be_one_line(self) -> None:
        doc = fixture("scored-standard")
        doc["strengths"][0]["evidence"][0]["quote"] = "two\nlines"
        self.assertTrue(any("one trimmed line" in e for e in errors(doc)))


class CrisisSafetyTest(unittest.TestCase):
    """Owner decision 2026-11-23: every crisis report carries its safety result (SCO-5, ETH-7)."""

    def crisis(self, name: str) -> dict[str, Any]:
        doc = fixture(name)
        doc["scenario"]["id"] = "crisis_risk"
        return doc

    def test_a_crisis_report_without_safety_is_rejected_in_every_assessed_state(self) -> None:
        # safety_not_demonstrated already lists safety as required, so only these three needed the rule.
        for name in ("narrative-only", "insufficient-evidence", "scored-crisis-met"):
            doc = self.crisis(name)
            doc.pop("safety", None)
            with self.subTest(name):
                self.assertTrue(any("always carries its safety result" in e for e in errors(doc)))

    def test_a_crisis_narrative_only_report_with_safety_passes(self) -> None:
        doc = self.crisis("narrative-only")
        doc["safety"] = {"result": "met", "critical_failures": []}
        self.assertEqual(errors(doc), [])

    def test_pending_and_failed_crisis_reports_need_no_safety(self) -> None:
        for name in ("pending", "failed-lost-content"):
            with self.subTest(name):
                self.assertEqual(errors(self.crisis(name)), [])


class UntrustedShapeTest(unittest.TestCase):
    """Malformed JSON shapes are reported, never raised."""

    def test_a_unicode_line_break_in_a_quote_is_rejected(self) -> None:
        for separator in ("\u2028", "\u2029", "\x85"):
            doc = fixture("scored-standard")
            quote = doc["categories"][0]["evidence"][0]["quote"]
            doc["categories"][0]["evidence"][0]["quote"] = quote + separator + "more"
            with self.subTest(separator=repr(separator)):
                self.assertTrue(any("one trimmed line" in e for e in errors(doc)))

    def test_a_fractional_weight_is_rejected(self) -> None:
        doc = fixture("scored-standard")
        doc["categories"][0]["weight_percent"] = 20.0
        self.assertTrue(any("weights are fixed" in e for e in errors(doc)))

    def test_unhashable_values_are_reported_not_raised(self) -> None:
        cases: list[tuple[str, Any]] = [
            ("/state", {}),
            ("/modality", []),
            ("/scenario/id", []),
            ("/actions", [["export"]]),
            ("/limitations", [{}]),
            ("/categories/2/reason", []),
            ("/strengths/0/evidence/0/speaker", []),
        ]
        for path, value in cases:
            base = "insufficient-evidence" if "categories/2" in path else "scored-standard"
            with self.subTest(path):
                doc = checker.apply_patch(fixture(base), [{"op": "replace", "path": path, "value": value}])
                self.assertNotEqual(errors(doc), [])

    def test_wrong_top_level_types_are_reported(self) -> None:
        for doc in ([], "report", None, 3, {"contract": "cst.other"}):
            with self.subTest(doc=doc):
                self.assertNotEqual(errors(doc), [])

    def test_a_malformed_version_is_reported(self) -> None:
        for version in ("1", "1.0", "v1.0.0", "01.0.0", 1):
            doc = fixture("scored-standard")
            doc["contract_version"] = version
            with self.subTest(version=version):
                self.assertTrue(any("MAJOR.MINOR.PATCH" in e for e in errors(doc)))

    def test_a_newer_minor_version_is_read(self) -> None:
        doc = fixture("scored-standard")
        doc["contract_version"] = "1.4.0"
        self.assertEqual(errors(doc), [])

    def test_a_level_given_as_text_does_not_crash_the_overall_check(self) -> None:
        doc = fixture("scored-standard")
        doc["categories"][0]["level"] = "4"
        self.assertTrue(any("whole number" in e for e in errors(doc)))

    def test_nan_is_not_valid_json_here(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.json"
            path.write_text('{"value": NaN}', encoding="utf-8")
            with self.assertRaises(ValueError):
                checker._load(path)


class HistoryTest(unittest.TestCase):
    def test_duplicate_ids_and_tied_times_are_rejected(self) -> None:
        doc = fixture("history")
        doc["entries"][1]["record_id"] = doc["entries"][0]["record_id"]
        self.assertTrue(any("distinct record_id" in e for e in errors(doc)))
        doc = fixture("history")
        doc["entries"][1]["completed_at"] = doc["entries"][0]["completed_at"]
        self.assertTrue(any("newest first" in e for e in errors(doc)))

    def test_a_crisis_failure_entry_keeps_the_scenario_rating_at_one(self) -> None:
        doc = fixture("history")
        failure = next(e for e in doc["entries"] if e.get("safety_result") == "not_demonstrated")
        failure["categories"][-1]["level"] = 3
        failure["overall"] = {"value": 2.45, "display": "2.5"}
        self.assertTrue(any("level 1" in e for e in errors(doc)))

    def test_a_history_entry_never_carries_an_abstention_or_evidence(self) -> None:
        doc = fixture("history")
        doc["entries"][0]["categories"][0] = {"id": "empathic_engagement", "level": None}
        self.assertTrue(any("whole number" in e for e in errors(doc)))
        doc = fixture("history")
        doc["entries"][0]["categories"][0]["evidence"] = []
        self.assertTrue(any("only id and level" in e for e in errors(doc)))

    def test_completed_at_must_be_a_server_utc_time(self) -> None:
        doc = fixture("history")
        doc["entries"][0]["completed_at"] = "Nov 20, 2026"
        self.assertTrue(any("server-set UTC time" in e for e in errors(doc)))

    def test_provenance_is_null_or_exactly_the_proposed_pair(self) -> None:
        doc = fixture("history")
        doc["entries"][0]["provenance"] = {"rubric_spec_version": "1.0.0"}
        self.assertTrue(any("provenance must be null or" in e for e in errors(doc)))

    def test_comparison_indication(self) -> None:
        entries = {e["record_id"]: e for e in fixture("history")["entries"]}
        self.assertEqual(checker.compare(entries["h-0005"], entries["h-0004"]), "compatible")
        self.assertEqual(checker.compare(entries["h-0005"], entries["h-0001"]), "incompatible")
        self.assertEqual(checker.compare(entries["h-0005"], entries["h-0002"]), "unknown")
        self.assertEqual(checker.compare(entries["h-0002"], entries["h-0006"]), "incompatible")

    def test_a_scoring_policy_major_change_is_incompatible(self) -> None:
        entries = {e["record_id"]: e for e in fixture("history")["entries"]}
        newer = copy.deepcopy(entries["h-0005"])
        newer["provenance"]["scoring_policy_version"] = "2.0.0"
        self.assertEqual(checker.compare(newer, entries["h-0004"]), "incompatible")


class PatchTest(unittest.TestCase):
    def test_add_remove_replace_and_append(self) -> None:
        doc = {"a": {"b": [1, 2]}, "c": 1}
        out = checker.apply_patch(doc, [
            {"op": "add", "path": "/a/b/-", "value": 3},
            {"op": "add", "path": "/a/b/0", "value": 0},
            {"op": "remove", "path": "/c"},
            {"op": "replace", "path": "/a/b/1", "value": 9},
            {"op": "add", "path": "/x~1y", "value": True},
        ])
        self.assertEqual(out, {"a": {"b": [0, 9, 2, 3]}, "x/y": True})
        self.assertEqual(doc, {"a": {"b": [1, 2]}, "c": 1})

    def test_bad_operations_raise(self) -> None:
        with self.assertRaises(ValueError):
            checker.apply_patch({}, [{"op": "move", "path": "/a"}])
        with self.assertRaises(KeyError):
            checker.apply_patch({}, [{"op": "replace", "path": "/a", "value": 1}])
        with self.assertRaises(ValueError):
            checker.apply_patch({}, [{"op": "add", "path": "a", "value": 1}])


class FolderFailureTest(unittest.TestCase):
    """The runner reports a broken folder instead of passing it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "report"
        shutil.copytree(checker.DEFAULT_REPORT_DIR, self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_a_missing_state_fixture_is_reported(self) -> None:
        (self.root / "fixtures" / "v1" / "pending.json").unlink()
        (self.root / "validation-cases" / "v1" / "invalid" / "pending-with-score.json").unlink()
        self.assertIn("fixtures: no fixture for states ['pending']", checker.run(self.root))

    def test_an_invalid_case_that_passes_is_reported(self) -> None:
        case_path = self.root / "validation-cases" / "v1" / "invalid" / "fabricated-turn.json"
        case = json.loads(case_path.read_text(encoding="utf-8"))
        case["patch"][0]["value"] = 3
        case_path.write_text(json.dumps(case), encoding="utf-8")
        problems = checker.run(self.root)
        self.assertEqual(len(problems), 1)
        self.assertIn("fabricated-turn.json: expected a rejection", problems[0])

    def test_a_wrong_comparison_expectation_is_reported(self) -> None:
        path = self.root / "validation-cases" / "v1" / "comparisons.json"
        cases = json.loads(path.read_text(encoding="utf-8"))
        cases["pairs"][0]["expected"] = "unknown"
        path.write_text(json.dumps(cases), encoding="utf-8")
        self.assertEqual(len(checker.run(self.root)), 1)

    def test_an_unmarked_fixture_fails_and_main_exits_nonzero(self) -> None:
        path = self.root / "fixtures" / "v1" / "failed-conduct.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["synthetic"] = False
        path.write_text(json.dumps(doc), encoding="utf-8")
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(checker.main(["--report-dir", str(self.root)]), 1)
        self.assertIn("a fixture must say synthetic: true", err.getvalue())

    def test_an_empty_folder_is_reported(self) -> None:
        shutil.rmtree(self.root / "fixtures" / "v1")
        (self.root / "fixtures" / "v1").mkdir()
        problems = checker.check_fixtures(self.root, RUBRIC)
        self.assertEqual(len(problems), 1)
        self.assertIn("no fixtures found", problems[0])


if __name__ == "__main__":
    unittest.main()
