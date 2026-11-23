"""Unit tests for vertex_governance.py. No network: every API call goes to a fake sender.

Run: python -m unittest discover -s infra/session-grading -p "test_*.py" -v
"""

from __future__ import annotations

import email.message
import io
import os
import re
import tempfile
import unittest
import urllib.error
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest import mock

import vertex_governance as vg

MAIN_TF = Path(__file__).with_name("main.tf")
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


class FakeSender:
    """Records each call and answers from a {(method, url-suffix): (status, body)} table."""

    def __init__(
        self, answers: dict[tuple[str, str], tuple[int, dict[str, Any]]]
    ) -> None:
        self.answers = answers
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def __call__(
        self, method: str, url: str, body: dict[str, Any] | None
    ) -> tuple[int, dict[str, Any]]:
        self.calls.append((method, url, body))
        for (want_method, suffix), answer in self.answers.items():
            if method == want_method and url.endswith(suffix):
                return answer
        raise AssertionError(f"unexpected call {method} {url}")


Answers = dict[tuple[str, str], tuple[int, dict[str, Any]]]
CACHE_OFF: Answers = {("GET", "/cacheConfig"): (200, {"disableCache": True})}
NO_CACHES: Answers = {("GET", "/cachedContents"): (200, {})}
NO_LOGGING: Answers = {("GET", ":fetchPublisherModelConfig"): (404, {})}
MODEL_READS: Answers = {
    ("GET", f"/publishers/google/models/{model}"): (200, {})
    for model in ("gemini-3.8-flash", "gemini-4-argon")
}
US_HOST = "https://aiplatform.us.rep.googleapis.com/"


class PinsMatchTerraform(unittest.TestCase):
    def test_location_and_models_match_main_tf(self) -> None:
        source = MAIN_TF.read_text(encoding="utf-8")
        block = re.search(r"vertex = \{(.*?)\}", source, re.DOTALL)
        assert block is not None, "local.vertex not found in main.tf"
        pins = dict(re.findall(r'(\w+)\s*=\s*"([^"]+)"', block.group(1)))
        self.assertEqual(pins["location"], vg.LOCATION)
        self.assertEqual(pins["persona_model"], vg.MODELS["persona"])
        self.assertEqual(pins["grader_model"], vg.MODELS["grader"])


class Urls(unittest.TestCase):
    def test_every_model_and_cache_url_uses_the_us_multi_region_host(self) -> None:
        for url in (vg.cached_contents_url(), vg.generate_url("m")):
            self.assertTrue(url.startswith(US_HOST + "v1/projects/"), url)
        self.assertTrue(vg.logging_config_url("m").startswith(US_HOST + "v1beta1/"))
        self.assertEqual(
            vg.model_read_url("m"), US_HOST + "v1beta1/publishers/google/models/m"
        )

    def test_cache_config_uses_the_documented_project_host(self) -> None:
        self.assertEqual(
            vg.cache_config_url(),
            f"https://aiplatform.googleapis.com/v1/projects/{vg.PROJECT}/cacheConfig",
        )

    def test_only_allowlisted_locations_are_accepted(self) -> None:
        for location in ("global", "Global", "", "us-central1", "eu", "europe-west4"):
            with self.subTest(location=location), self.assertRaises(ValueError):
                vg.generate_url("m", location=location)

    def test_generate_url_names_the_publisher_model(self) -> None:
        self.assertTrue(
            vg.generate_url("gemini-4-argon").endswith(
                "/locations/us/publishers/google/models/gemini-4-argon:generateContent"
            )
        )

    def test_logging_config_url_names_the_publisher_model(self) -> None:
        self.assertTrue(
            vg.logging_config_url("gemini-4-argon").endswith(
                "/locations/us/publishers/google/models/gemini-4-argon:fetchPublisherModelConfig"
            )
        )


class CacheConfig(unittest.TestCase):
    def test_disabled_cache_passes(self) -> None:
        self.assertTrue(vg.evaluate_cache_config(200, {"disableCache": True}).passed)

    def test_default_durable_cache_fails(self) -> None:
        result = vg.evaluate_cache_config(200, {})
        self.assertFalse(result.passed)
        self.assertIn("DURABLE", result.detail)

    def test_ephemeral_only_still_fails(self) -> None:
        body = {
            "disableCache": False,
            "retentionConfig": {"retentionType": "EPHEMERAL"},
        }
        result = vg.evaluate_cache_config(200, body)
        self.assertFalse(result.passed)
        self.assertIn("EPHEMERAL", result.detail)

    def test_http_error_fails(self) -> None:
        self.assertFalse(vg.evaluate_cache_config(403, {}).passed)


class CachedContents(unittest.TestCase):
    def test_none_passes(self) -> None:
        self.assertTrue(vg.evaluate_cached_contents(200, {}).passed)
        self.assertTrue(vg.evaluate_cached_contents(200, {"cachedContents": []}).passed)

    def test_any_cache_fails_and_reports_only_a_count(self) -> None:
        body = {"cachedContents": [{"name": "c1", "contents": "SECRET-SESSION-TEXT"}]}
        result = vg.evaluate_cached_contents(200, body)
        self.assertFalse(result.passed)
        self.assertEqual(result.detail, "1 found")

    def test_http_error_fails(self) -> None:
        self.assertFalse(vg.evaluate_cached_contents(500, {}).passed)


class LoggingConfig(unittest.TestCase):
    def test_never_configured_passes_when_the_model_read_succeeds(self) -> None:
        result = vg.evaluate_logging_config("m", 404, {}, 200)
        self.assertTrue(result.passed)
        self.assertIn("never configured", result.detail)
        self.assertIn("model read HTTP 200", result.detail)

    def test_404_fails_when_the_model_read_also_fails(self) -> None:
        # A wrong host, version or model ID: the 404 says nothing about logging.
        for model_read_status in (404, 403, 0):
            result = vg.evaluate_logging_config("m", 404, {}, model_read_status)
            self.assertFalse(result.passed, model_read_status)
            self.assertIn("proves nothing", result.detail)

    def test_explicitly_disabled_passes(self) -> None:
        body = {"loggingConfig": {"enabled": False}}
        self.assertTrue(vg.evaluate_logging_config("m", 200, body, 200).passed)

    def test_sharing_only_config_with_empty_logging_passes(self) -> None:
        body = {"loggingConfig": {}, "dataSharingEnabledProvider": "NONE"}
        self.assertTrue(vg.evaluate_logging_config("m", 200, body, 200).passed)

    def test_enabled_logging_fails(self) -> None:
        body = {"loggingConfig": {"enabled": True, "samplingRate": 1}}
        result = vg.evaluate_logging_config("m", 200, body, 200)
        self.assertFalse(result.passed)
        self.assertEqual(result.detail, "loggingConfig.enabled: true")

    def test_permission_or_network_error_fails(self) -> None:
        self.assertFalse(vg.evaluate_logging_config("m", 403, {}, 200).passed)
        self.assertFalse(vg.evaluate_logging_config("m", 0, {}, 200).passed)


class Commands(unittest.TestCase):
    def test_check_reads_settings_1_to_3_without_writing(self) -> None:
        send = FakeSender({**CACHE_OFF, **NO_LOGGING, **MODEL_READS, **NO_CACHES})
        report, passed = vg.run("check", send, NOW)
        self.assertTrue(passed)
        self.assertEqual({call[0] for call in send.calls}, {"GET"})
        self.assertEqual(len(send.calls), 2 + 2 * len(vg.MODELS))
        for model in vg.MODELS.values():
            self.assertIn(
                f"setting 2, request-response logging off for {model}", report
            )
        self.assertIn("2026-11-22T12:00:00Z", report)

    def test_check_fails_when_any_model_logs_requests(self) -> None:
        logging_on = {"loggingConfig": {"enabled": True}}
        send = FakeSender(
            {
                **CACHE_OFF,
                ("GET", "gemini-4-argon:fetchPublisherModelConfig"): (200, logging_on),
                **NO_LOGGING,
                **MODEL_READS,
                **NO_CACHES,
            }
        )
        report, passed = vg.run("check", send, NOW)
        self.assertFalse(passed)
        self.assertIn(
            "FAIL  setting 2, request-response logging off for gemini-4-argon", report
        )

    def test_check_fails_when_the_model_read_misses(self) -> None:
        send = FakeSender(
            {
                **CACHE_OFF,
                **NO_LOGGING,
                **MODEL_READS,
                # Later keys replace the 200 answer for this one model.
                ("GET", "/publishers/google/models/gemini-3.8-flash"): (404, {}),
                **NO_CACHES,
            }
        )
        report, passed = vg.run("check", send, NOW)
        self.assertFalse(passed)
        self.assertIn(
            "FAIL  setting 2, request-response logging off for gemini-3.8-flash", report
        )
        self.assertIn(
            "PASS  setting 2, request-response logging off for gemini-4-argon", report
        )

    def test_disable_cache_patches_then_reads_back(self) -> None:
        send = FakeSender(
            {("PATCH", "/cacheConfig"): (200, {"name": "op"}), **CACHE_OFF}
        )
        _, passed = vg.run("disable-cache", send, NOW)
        self.assertTrue(passed)
        method, _, body = send.calls[0]
        self.assertEqual(method, "PATCH")
        self.assertEqual(
            body, {"name": f"projects/{vg.PROJECT}/cacheConfig", "disableCache": True}
        )
        self.assertEqual(send.calls[1][0], "GET")

    def test_disable_cache_fails_when_patch_is_refused(self) -> None:
        send = FakeSender({("PATCH", "/cacheConfig"): (403, {})})
        report, passed = vg.run("disable-cache", send, NOW)
        self.assertFalse(passed)
        self.assertIn("HTTP 403", report)
        self.assertEqual(len(send.calls), 1)

    def test_disable_cache_fails_when_read_back_shows_cache_on(self) -> None:
        send = FakeSender(
            {("PATCH", "/cacheConfig"): (200, {}), ("GET", "/cacheConfig"): (200, {})}
        )
        _, passed = vg.run("disable-cache", send, NOW)
        self.assertFalse(passed)

    def test_probe_calls_each_pinned_model_with_the_synthetic_prompt(self) -> None:
        send = FakeSender(
            {
                ("POST", "gemini-3.8-flash:generateContent"): (
                    200,
                    {"candidates": ["x"]},
                ),
                ("POST", "gemini-4-argon:generateContent"): (404, {}),
            }
        )
        report, passed = vg.run("probe", send, NOW)
        self.assertFalse(passed)
        self.assertIn("PASS  location, persona model gemini-3.8-flash", report)
        self.assertIn("FAIL  location, grader model gemini-4-argon", report)
        self.assertIn("not served on this endpoint", report)
        for _, _, body in send.calls:
            assert body is not None
            self.assertEqual(body["contents"][0]["parts"][0]["text"], vg.PROBE_PROMPT)

    def test_report_never_contains_a_model_response(self) -> None:
        send = FakeSender(
            {
                ("POST", "gemini-3.8-flash:generateContent"): (
                    200,
                    {"text": "MODEL-OUTPUT"},
                ),
                ("POST", "gemini-4-argon:generateContent"): (
                    200,
                    {"text": "MODEL-OUTPUT"},
                ),
            }
        )
        report, passed = vg.run("probe", send, NOW)
        self.assertTrue(passed)
        self.assertNotIn("MODEL-OUTPUT", report)


class Describe(unittest.TestCase):
    def test_status_zero_reads_as_no_response(self) -> None:
        self.assertIn("no response", vg.describe(0))
        self.assertIn("no response", vg.evaluate_cache_config(0, {}).detail)
        self.assertEqual(vg.describe(403), "HTTP 403")


class FakeResponse(io.BytesIO):
    status = 200


class HttpSender(unittest.TestCase):
    def send_with(self, failure: BaseException) -> tuple[int, dict[str, Any]]:
        with mock.patch("urllib.request.urlopen", side_effect=failure):
            return vg.http_sender("TOKEN")("GET", vg.cached_contents_url(), None)

    def test_network_error_returns_status_zero(self) -> None:
        self.assertEqual(self.send_with(urllib.error.URLError("down")), (0, {}))

    def test_timeout_returns_status_zero(self) -> None:
        self.assertEqual(self.send_with(TimeoutError()), (0, {}))

    def test_http_error_keeps_only_the_status(self) -> None:
        error = urllib.error.HTTPError(
            "u",
            403,
            "Forbidden",
            email.message.Message(),
            io.BytesIO(b"ECHOED-REQUEST"),
        )
        self.assertEqual(self.send_with(error), (403, {}))

    def test_non_json_body_returns_status_zero(self) -> None:
        response = mock.MagicMock()
        response.__enter__.return_value = FakeResponse(b"<html>not json</html>")
        with mock.patch("urllib.request.urlopen", return_value=response):
            sent = vg.http_sender("TOKEN")("GET", vg.cached_contents_url(), None)
        self.assertEqual(sent, (0, {}))


class FindOnPath(unittest.TestCase):
    def test_skips_empty_and_current_directory_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "gcloud.cmd").write_text("", encoding="utf-8")
            path = f"{''}{os.pathsep}{os.curdir}{os.pathsep}{directory}"
            found = vg.find_on_path(("gcloud.cmd",), path)
            self.assertEqual(found, str(Path(directory) / "gcloud.cmd"))

    def test_never_falls_back_to_the_current_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "gcloud.cmd").write_text("", encoding="utf-8")
            with mock.patch("os.getcwd", return_value=directory):
                self.assertIsNone(vg.find_on_path(("gcloud.cmd",), os.curdir))


if __name__ == "__main__":
    unittest.main()
