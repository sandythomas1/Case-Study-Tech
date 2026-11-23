"""Tests for scripts/ci/deploy/gateway_config.py (stdlib unittest only).

The Terraform semantics these tests pin were checked with `terraform console` on 2026-11-22:
rendering the real template both ways was byte-identical to templatefile().
Run from the repository root: python -m unittest discover -s scripts/ci/tests
"""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "ci" / "deploy" / "gateway_config.py"
_SPEC = importlib.util.spec_from_file_location("gateway_config", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
gateway_config = importlib.util.module_from_spec(_SPEC)
sys.modules["gateway_config"] = gateway_config
_SPEC.loader.exec_module(gateway_config)

TEMPLATE = (
    "host: ${PROJECT_ID}\n"
    "paths:\n"
    "  /health:\n"
    "    address: ${ACCOUNTS_SERVICE_URL}\n"
    '%{ if SESSION_SERVICE_URL != "" ~}\n'
    "  /v1/sessions:\n"
    "    address: ${SESSION_SERVICE_URL}\n"
    "%{ endif ~}\n"
)
VALUES = {
    "PROJECT_ID": "p-1",
    "ACCOUNTS_SERVICE_URL": "https://a.run.app",
    "SESSION_SERVICE_URL": "https://s.run.app",
}
REAL_TEMPLATE = (_ROOT / "infra" / "gateway.yaml.template").read_text(encoding="utf-8")


def live_json(document: str) -> dict[str, object]:
    encoded = base64.b64encode(document.encode("utf-8")).decode("ascii")
    return {"openapiDocuments": [{"document": {"path": "accounts.yaml", "contents": encoded}}]}


class RenderTest(unittest.TestCase):
    def test_if_block_kept_and_directive_lines_dropped(self) -> None:
        self.assertEqual(
            gateway_config.render(TEMPLATE, VALUES),
            "host: p-1\npaths:\n  /health:\n    address: https://a.run.app\n"
            "  /v1/sessions:\n    address: https://s.run.app\n",
        )

    def test_empty_variable_drops_the_block(self) -> None:
        values = {**VALUES, "SESSION_SERVICE_URL": ""}
        self.assertEqual(
            gateway_config.render(TEMPLATE, values),
            "host: p-1\npaths:\n  /health:\n    address: https://a.run.app\n",
        )

    def test_crlf_template_renders_like_lf(self) -> None:
        crlf = TEMPLATE.replace("\n", "\r\n")
        self.assertEqual(gateway_config.render(crlf, VALUES), gateway_config.render(TEMPLATE, VALUES))

    def test_real_template_renders_completely_both_ways(self) -> None:
        with_session = gateway_config.render(REAL_TEMPLATE, VALUES)
        without = gateway_config.render(REAL_TEMPLATE, {**VALUES, "SESSION_SERVICE_URL": ""})
        for text in (with_session, without):
            self.assertNotIn("${", text)
            self.assertNotIn("%{", text)
        self.assertIn("/v1/sessions/health:", with_session)
        self.assertNotIn("/v1/sessions", without)
        routes = [line.strip() for line in with_session.splitlines() if line.startswith("  /")]
        self.assertFalse([r for r in routes if "grading" in r.lower()], "grading has no route (AD-3)")

    def test_unsupported_constructs_fail_closed(self) -> None:
        cases = {
            "unknown variable": "a: ${OTHER}\n",
            "expression interpolation": 'a: ${lower("X")}\n',
            "for directive": "%{ for x in y ~}\n%{ endfor ~}\n",
            "inline directive": 'a: %{ if PROJECT_ID != "" }x%{ endif }\n',
            "escaped interpolation": "a: $${PROJECT_ID}\n",
            "unclosed if": '%{ if SESSION_SERVICE_URL != "" ~}\na: b\n',
            "endif without if": "%{ endif ~}\n",
            "nested if": '%{ if PROJECT_ID != "" ~}\n%{ if PROJECT_ID != "" ~}\n',
            "if on unknown variable": '%{ if OTHER != "" ~}\n%{ endif ~}\n',
        }
        for label, template in cases.items():
            with self.subTest(label), self.assertRaises(gateway_config.TemplateError):
                gateway_config.render(template, VALUES)


class ValuesTest(unittest.TestCase):
    def test_accepts_cloud_run_urls_and_empty_session(self) -> None:
        values = gateway_config.template_values(
            "casestudy-tech-dev-2e03d0", "https://accounts-447ob3nwoa-uc.a.run.app", ""
        )
        self.assertEqual(values["SESSION_SERVICE_URL"], "")

    def test_rejects_unsafe_values(self) -> None:
        cases = [
            ("casestudy-tech-dev-2e03d0", "https://evil.example.com", ""),
            ("casestudy-tech-dev-2e03d0", "http://accounts-x.a.run.app", ""),
            ("casestudy-tech-dev-2e03d0", "https://accounts-x.a.run.app", "https://x.a.run.app/\n"),
            ("Bad Project", "https://accounts-x.a.run.app", ""),
        ]
        for case in cases:
            with self.subTest(case), self.assertRaises(gateway_config.TemplateError):
                gateway_config.template_values(*case)


class ChangedTest(unittest.TestCase):
    def test_same_content_with_crlf_and_trailing_newline_is_unchanged(self) -> None:
        rendered = "a: 1\nb: 2"
        self.assertFalse(gateway_config.changed(rendered, "a: 1\r\nb: 2\r\n"))

    def test_different_content_is_changed(self) -> None:
        self.assertTrue(gateway_config.changed("a: 1\nb: 2", "a: 1\nb: 3"))
        self.assertTrue(gateway_config.changed("a: 1\n  b: 2", "a: 1\nb: 2"))

    def test_live_document_decodes_the_single_document(self) -> None:
        self.assertEqual(gateway_config.live_document(live_json("x: 1")), "x: 1")

    def test_live_document_rejects_bad_shapes(self) -> None:
        two = live_json("x")
        two["openapiDocuments"] = two["openapiDocuments"] * 2  # type: ignore[operator]
        cases = {
            "no documents key": {},
            "two documents": two,
            "not base64": {"openapiDocuments": [{"document": {"contents": "%%%"}}]},
            "not an object": [],
        }
        for label, data in cases.items():
            with self.subTest(label), self.assertRaises(gateway_config.TemplateError):
                gateway_config.live_document(data)


class MainTest(unittest.TestCase):
    def call(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = gateway_config.main(["gateway_config.py", *args])
        return code, out.getvalue(), err.getvalue()

    def test_render_then_changed_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            template, rendered, live = (Path(tmp) / n for n in ("t", "accounts.yaml", "live.json"))
            template.write_text(TEMPLATE, encoding="utf-8")
            code, _, _ = self.call(
                "render", "--template", str(template), "--out", str(rendered),
                "--project-id", "casestudy-tech-dev-2e03d0",
                "--accounts-url", "https://accounts-x.a.run.app",
                "--session-url", "https://session-x.a.run.app",
            )
            self.assertEqual(code, 0)
            text = rendered.read_text(encoding="utf-8")
            live.write_text(json.dumps(live_json(text.replace("\n", "\r\n"))), encoding="utf-8")
            self.assertEqual(self.call("changed", "--rendered", str(rendered), "--live-json", str(live))[1],
                             "changed=false\n")
            live.write_text(json.dumps(live_json(text + "extra: 1\n")), encoding="utf-8")
            self.assertEqual(self.call("changed", "--rendered", str(rendered), "--live-json", str(live))[1],
                             "changed=true\n")

    def test_bad_value_fails_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            template, rendered = Path(tmp) / "t", Path(tmp) / "out.yaml"
            template.write_text(TEMPLATE, encoding="utf-8")
            code, out, err = self.call(
                "render", "--template", str(template), "--out", str(rendered),
                "--project-id", "casestudy-tech-dev-2e03d0",
                "--accounts-url", "https://evil.example.com", "--session-url", "",
            )
            self.assertEqual((code, out), (1, ""))
            self.assertIn("accounts URL", err)
            self.assertFalse(rendered.exists())


if __name__ == "__main__":
    unittest.main()
