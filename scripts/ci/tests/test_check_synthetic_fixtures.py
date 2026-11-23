"""Unit tests for scripts/ci/check_synthetic_fixtures.py (stdlib unittest only).

Run from the repository root: python -m unittest discover -s scripts/ci/tests
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "check_synthetic_fixtures.py"
_SPEC = importlib.util.spec_from_file_location("check_synthetic_fixtures", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
checker = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = checker
_SPEC.loader.exec_module(checker)

ALLOWLIST = ".github/synthetic-fixtures.allow"
SHA_A = "a" * 40
SHA_B = "b" * 40


def tracked(path: str, blob: str = SHA_A, mode: str = "100644"):
    return checker.TrackedFile(path=path, mode=mode, blob=blob)


class ClassifyByNameTests(unittest.TestCase):
    def test_flags_audio_and_video_extensions(self) -> None:
        for path in ("a/b.wav", "c.mp3", "d.m4a", "e.webm", "f.mp4", "g.mov", "h.pcm",
                     "i.mka", "j.mpga"):
            with self.subTest(path=path):
                self.assertIn("audio/video file", checker.classify(path) or "")

    def test_flags_caption_extensions(self) -> None:
        for path in ("session.vtt", "x/y.srt"):
            with self.subTest(path=path):
                self.assertIn("caption/subtitle file", checker.classify(path) or "")

    def test_flags_archives(self) -> None:
        for path in ("a.zip", "b.tar", "c.tar.gz", "d.tgz", "e.7z", "f.RAR"):
            with self.subTest(path=path):
                self.assertIn("archive (", checker.classify(path) or "")

    def test_extensions_are_case_insensitive(self) -> None:
        self.assertEqual(checker.classify("Fixtures/TURN.WAV"), "audio/video file (.wav)")
        self.assertEqual(checker.classify("a/B.Vtt"), "caption/subtitle file (.vtt)")

    def test_flags_content_names_on_data_files(self) -> None:
        cases = {
            "tests/fixtures/session_transcript.json": "transcript",
            "data/Transcripts.txt": "transcript",
            "fixtures/recording-01.bin": "recording",
            "fixtures/captions.md": "caption",
            "fixtures/turn_excerpts.json": "excerpt",
            "fixtures/Narrative-Feedback.txt": "feedback",
        }
        for path, marker in cases.items():
            with self.subTest(path=path):
                self.assertEqual(checker.classify(path), f"file name suggests a {marker}")

    def test_name_rule_skips_source_code(self) -> None:
        for path in (
            "services/session/cst_session/transcript.py",
            "apps/student/src/TranscriptView.tsx",
            "lib/recording_state.ts",
            "services/grading/feedback.py",
            "apps/student/src/ExcerptCard.tsx",
        ):
            with self.subTest(path=path):
                self.assertIsNone(checker.classify(path))

    def test_name_rule_skips_markdown_in_docs_and_specs(self) -> None:
        for path in ("docs/feedback-rubric.md", "specs/012-x/class-feedback-nudges.md",
                     "docs/transcript-retention.md"):
            with self.subTest(path=path):
                self.assertIsNone(checker.classify(path))

    def test_docs_and_specs_still_get_the_other_rules(self) -> None:
        self.assertIn("audio/video file", checker.classify("docs/demo-recording.wav") or "")
        self.assertIn("transcript", checker.classify("docs/transcript.json") or "")

    def test_name_rule_uses_file_name_not_directories(self) -> None:
        self.assertIsNone(checker.classify("specs/040-transcript-signing/spec.md"))

    def test_ignores_ordinary_files(self) -> None:
        for path in ("README.md", "app.json", "docs/diagram.png", "tests/synthetic_audio.py"):
            with self.subTest(path=path):
                self.assertIsNone(checker.classify(path))


class SniffMediaTests(unittest.TestCase):
    def test_detects_each_audio_video_signature(self) -> None:
        cases = {
            b"RIFF\x24\x00\x00\x00WAVEfmt ": "WAVE",
            b"RIFF\x24\x00\x00\x00AVI LIST": "AVI",
            b"FORM\x00\x00\x00\x00AIFFCOMM": "AIFF",
            b"ID3\x04\x00\x00\x00\x00\x00\x00": "MP3 (ID3)",
            b"\xff\xfb\x90\x64\x00\x00": "MPEG audio frame",
            b"\xff\xf1\x50\x80\x00\x1f": "MPEG audio frame",
            b"OggS\x00\x02\x00\x00": "Ogg",
            b"fLaC\x00\x00\x00\x22": "FLAC",
            b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00": "MP4/QuickTime",
            b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00": "MP4/QuickTime",
            b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81": "Matroska/WebM",
            b"caff\x00\x01\x00\x00": "Core Audio",
            b"#!AMR\n": "AMR",
        }
        for header, label in cases.items():
            with self.subTest(label=label, header=header):
                self.assertEqual(checker.sniff_media(header), label)

    def test_signature_flags_file_with_innocent_name(self) -> None:
        rule = checker.classify("tests/data/blob.bin", b"OggS\x00\x02\x00\x00")
        self.assertEqual(rule, "audio/video content detected by file signature (Ogg)")

    def test_common_repo_files_are_not_media(self) -> None:
        headers = {
            "png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
            "jpeg": b"\xff\xd8\xff\xe0\x00\x10JFIF\x00",
            "pdf": b"%PDF-1.7\n%\xe2\xe3\xcf\xd3",
            "docx (zip container)": b"PK\x03\x04\x14\x00\x06\x00",
            "utf-16le bom": b"\xff\xfe#\x00 \x00T\x00",
            "utf-8 bom": b"\xef\xbb\xbf# Title",
            "webp (RIFF image)": b"RIFF\x24\x00\x00\x00WEBPVP8 ",
            "heic (ftyp image)": b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00",
            "avif (ftyp image)": b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00",
            "markdown": b"# Case-Study-Te",
            "empty": b"",
            "mpeg sync with invalid bitrate": b"\xff\xfb\xf0\x00",
            "mpeg sync with reserved rate": b"\xff\xfb\x9c\x00",
        }
        for label, header in headers.items():
            with self.subTest(label=label):
                self.assertIsNone(checker.sniff_media(header))


class SuppressionFileTests(unittest.TestCase):
    def test_gitleaks_files_outside_github_are_misplaced(self) -> None:
        for path in (".gitleaks.toml", ".gitleaksignore", "apps/student/.gitleaksignore",
                     "apps/x/.github/.gitleaks.toml"):
            with self.subTest(path=path):
                self.assertTrue(checker.is_misplaced_suppression_file(path))

    def test_gitleaks_files_inside_github_are_allowed(self) -> None:
        for path in (".github/.gitleaksignore", ".github/gitleaks.toml", ".github/.gitleaks.toml"):
            with self.subTest(path=path):
                self.assertFalse(checker.is_misplaced_suppression_file(path))


class AllowlistParsingTests(unittest.TestCase):
    def test_skips_blank_lines_and_comment_lines(self) -> None:
        allowlist = checker.parse_allowlist(
            "# header comment\n\n   \n  # indented comment\n"
            f"tests/a.wav {SHA_A}  # synthetic: generated sine tone\n"
        )
        self.assertEqual(dict(allowlist.entries), {"tests/a.wav": SHA_A})
        self.assertEqual(allowlist.errors, ())

    def test_accepts_paths_with_spaces_and_uppercase_sha(self) -> None:
        allowlist = checker.parse_allowlist(f"tests/my tone.wav {SHA_A.upper()}  # synthetic\n")
        self.assertEqual(dict(allowlist.entries), {"tests/my tone.wav": SHA_A})

    def test_entry_without_justification_is_an_error(self) -> None:
        allowlist = checker.parse_allowlist(f"tests/a.wav {SHA_A}\ntests/b.wav {SHA_B}   #   \n")
        self.assertEqual(dict(allowlist.entries), {})
        self.assertEqual(len(allowlist.errors), 2)
        self.assertIn("line 1: 'tests/a.wav' has no justification", allowlist.errors[0])
        self.assertIn("line 2: 'tests/b.wav'", allowlist.errors[1])

    def test_entry_without_valid_sha_is_an_error(self) -> None:
        allowlist = checker.parse_allowlist(
            "tests/a.wav  # synthetic\ntests/b.wav deadbeef  # synthetic\n"
        )
        self.assertEqual(dict(allowlist.entries), {})
        self.assertEqual(len(allowlist.errors), 2)
        self.assertIn("must be '<path> <git blob sha>  # why'", allowlist.errors[0])

    def test_missing_allowlist_file_means_no_exemptions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            allowlist = checker.load_allowlist(Path(tmp) / "missing.allow")
        self.assertEqual(dict(allowlist.entries), {})
        self.assertEqual(allowlist.errors, ())


class LsFilesParsingTests(unittest.TestCase):
    def test_parses_mode_blob_and_path_with_spaces(self) -> None:
        output = (
            f"100644 {SHA_A} 0\tREADME.md\x00120000 {SHA_B} 0\tdocs/my link\x00".encode()
        )
        self.assertEqual(
            checker.parse_ls_files_stage(output),
            [tracked("README.md", SHA_A), tracked("docs/my link", SHA_B, "120000")],
        )


class ReadHeaderTests(unittest.TestCase):
    def test_reads_only_the_first_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "big.bin").write_bytes(b"OggS" + b"\x00" * 10_000)
            header = checker.read_header(root, tracked("big.bin"))
        self.assertEqual(len(header), checker.HEADER_BYTES)
        self.assertTrue(header.startswith(b"OggS"))

    def test_symlinks_submodules_and_missing_files_read_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real.bin").write_bytes(b"OggS\x00\x00")
            self.assertEqual(checker.read_header(root, tracked("real.bin", mode="120000")), b"")
            self.assertEqual(checker.read_header(root, tracked("sub", mode="160000")), b"")
            self.assertEqual(checker.read_header(root, tracked("missing.bin")), b"")
            try:
                os.symlink(root / "real.bin", root / "link.bin")
            except (OSError, NotImplementedError):
                return
            self.assertEqual(checker.read_header(root, tracked("link.bin")), b"")


class RunTests(unittest.TestCase):
    def _run(
        self,
        files: list,
        allowlist_text: str | None,
        contents: dict[str, bytes] | None = None,
    ) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            if allowlist_text is not None:
                (root / ".github").mkdir()
                (root / ALLOWLIST).write_text(allowlist_text, encoding="utf-8")
            for path, data in (contents or {}).items():
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_bytes(data)
            return checker.run(root, ALLOWLIST, list_files=lambda _root: files)

    def test_passes_on_clean_tree(self) -> None:
        code, message = self._run([tracked("README.md"), tracked("src/app.tsx")], "# none\n")
        self.assertEqual(code, 0)
        self.assertIn("passed: 2 tracked files, 0 allowlisted", message)

    def test_fails_and_names_file_rule_and_policy(self) -> None:
        code, message = self._run([tracked("README.md"), tracked("tests/fixtures/turn.wav")], "")
        self.assertEqual(code, 1)
        self.assertIn("1 tracked file(s) look like session content", message)
        self.assertIn("  tests/fixtures/turn.wav: audio/video file (.wav)", message)
        self.assertIn("docs/POLICY.md DAT-1 and DAT-6", message)
        self.assertIn("docs/ARCHITECTURE.md section 7", message)
        self.assertIn(f"pin its path and blob sha in {ALLOWLIST}", message)
        self.assertIn("git ls-files -s -- tests/fixtures/turn.wav", message)
        self.assertIn("requests the owner's review", message)

    def test_magic_bytes_flag_a_renamed_recording(self) -> None:
        code, message = self._run(
            [tracked("tests/data/notes.txt")],
            "",
            contents={"tests/data/notes.txt": b"RIFF\x24\x00\x00\x00WAVEfmt "},
        )
        self.assertEqual(code, 1)
        self.assertIn("notes.txt: audio/video content detected by file signature (WAVE)", message)

    def test_allowlisted_path_with_matching_sha_passes(self) -> None:
        code, message = self._run(
            [tracked("tests/fixtures/turn.wav", SHA_A)],
            f"tests/fixtures/turn.wav {SHA_A}  # synthetic: generated 440 Hz tone\n",
        )
        self.assertEqual(code, 0)
        self.assertIn("1 allowlisted", message)

    def test_allowlisted_path_with_changed_content_fails(self) -> None:
        code, message = self._run(
            [tracked("tests/fixtures/turn.wav", SHA_B)],
            f"tests/fixtures/turn.wav {SHA_A}  # synthetic: generated 440 Hz tone\n",
        )
        self.assertEqual(code, 1)
        self.assertIn("changed since they were pinned", message)
        self.assertIn(f"tests/fixtures/turn.wav: pinned {SHA_A}, tracked file is now {SHA_B}",
                      message)
        self.assertIn("git ls-files -s -- <path>", message)

    def test_allowlist_matches_exact_path_only(self) -> None:
        code, message = self._run(
            [tracked("tests/fixtures/turn.wav"), tracked("tests/fixtures/other/turn.wav")],
            f"tests/fixtures/turn.wav {SHA_A}  # synthetic: generated tone\n",
        )
        self.assertEqual(code, 1)
        self.assertIn("tests/fixtures/other/turn.wav", message)
        self.assertNotIn("  tests/fixtures/turn.wav:", message)

    def test_missing_allowlist_still_enforces(self) -> None:
        code, message = self._run([tracked("a.mp3")], None)
        self.assertEqual(code, 1)
        self.assertIn("a.mp3: audio/video file (.mp3)", message)

    def test_malformed_entry_fails_even_without_violations(self) -> None:
        code, message = self._run([tracked("a.mp3")], "a.mp3  # synthetic\n")
        self.assertEqual(code, 1)
        self.assertIn("malformed entries", message)
        self.assertIn("a.mp3: audio/video file (.mp3)", message)

    def test_stale_entry_fails(self) -> None:
        code, message = self._run([tracked("README.md")], f"gone.wav {SHA_A}  # synthetic\n")
        self.assertEqual(code, 1)
        self.assertIn("not tracked files", message)
        self.assertIn("  gone.wav", message)

    def test_misplaced_suppression_file_fails_and_cannot_be_allowlisted(self) -> None:
        code, message = self._run(
            [tracked(".gitleaksignore"), tracked(".github/.gitleaksignore")],
            f".gitleaksignore {SHA_A}  # trying to allowlist it\n",
        )
        self.assertEqual(code, 1)
        self.assertIn("gitleaks suppression files must live in .github/", message)
        self.assertIn("  .gitleaksignore", message)
        self.assertNotIn("  .github/.gitleaksignore", message)

    def test_reports_every_violation_sorted(self) -> None:
        code, message = self._run(
            [tracked("z.srt"), tracked("a.wav"), tracked("m_transcript.json")], ""
        )
        self.assertEqual(code, 1)
        self.assertIn("3 tracked file(s)", message)
        self.assertLess(message.index("a.wav"), message.index("m_transcript.json"))
        self.assertLess(message.index("m_transcript.json"), message.index("z.srt"))


if __name__ == "__main__":
    unittest.main()
