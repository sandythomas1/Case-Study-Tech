"""Fail CI when a tracked file looks like recorded or transcribed session content.

Session audio, transcripts, excerpts and feedback may never be committed, not even as
test fixtures (docs/ARCHITECTURE.md section 7, docs/POLICY.md DAT-1 and DAT-6). This
check lists every tracked file and flags:

- audio/video and caption files, by extension or by their leading magic bytes;
- archives, which can hide any of the above;
- non-source files whose name suggests a transcript, recording, excerpt or feedback;
- gitleaks suppression files (.gitleaks.toml, .gitleaksignore) outside .github/.

It is a heuristic. Review stays the control for DAT-6.

A synthetic file can be exempted by pinning its exact path and git blob sha, with a
justification, in .github/synthetic-fixtures.allow. CODEOWNERS requests the owner's
review of that file; the rulesets enforce it only once "Require review from Code
Owners" is on. Suppression files can never be allowlisted.

Standard library only, so it runs on any Python 3.10+ without installing anything.
Run from the repository root: python scripts/ci/check_synthetic_fixtures.py
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEFAULT_ALLOWLIST = ".github/synthetic-fixtures.allow"
POLICY_REFERENCE = "docs/ARCHITECTURE.md section 7, docs/POLICY.md DAT-1 and DAT-6"
HEADER_BYTES = 16

AUDIO_VIDEO_EXTENSIONS = frozenset(
    {
        # Audio, including the raw PCM the speech contract uses.
        ".wav", ".mp3", ".mpga", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".flac",
        ".weba", ".wma", ".aif", ".aiff", ".caf", ".amr", ".mka", ".pcm", ".raw",
        # Video.
        ".webm", ".mp4", ".m4v", ".mov", ".mkv", ".avi", ".3gp",
    }
)
CAPTION_EXTENSIONS = frozenset({".vtt", ".srt", ".ttml", ".sbv", ".ass", ".ssa"})
ARCHIVE_EXTENSIONS = frozenset({".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"})
CONTENT_NAME_MARKERS = (
    "transcript", "recording", "caption", "subtitle", "excerpt", "feedback",
)
# Code that handles transcripts (for example transcript_signing.py) is not session
# content, so the name rule skips source files. The other rules still apply.
SOURCE_CODE_EXTENSIONS = frozenset(
    {".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
)
# Design docs and specs discuss transcripts and feedback by nature (for example
# specs/<n>-feedback-nudges/spec.md), so Markdown there also skips the name rule.
# Every other rule still applies, and review stays the control for DAT-6.
DOCUMENTATION_DIRS = ("docs/", "specs/")


def _skips_name_rule(path: str, suffix: str) -> bool:
    if suffix in SOURCE_CODE_EXTENSIONS:
        return True
    return suffix == ".md" and path.startswith(DOCUMENTATION_DIRS)
GITLEAKS_SUPPRESSION_FILES = frozenset({".gitleaks.toml", ".gitleaksignore"})
OWNER_REVIEWED_DIR = ".github/"
# ISO base media files (ftyp) that are still images, not audio or video.
IMAGE_FTYP_BRANDS = frozenset(
    {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1",
     b"avif", b"avis"}
)
# Symlinks and submodules have no readable content of their own.
UNREADABLE_MODES = frozenset({"120000", "160000"})
BLOB_SHA = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")


@dataclass(frozen=True)
class TrackedFile:
    path: str
    mode: str
    blob: str


@dataclass(frozen=True)
class Violation:
    path: str
    rule: str


@dataclass(frozen=True)
class PinMismatch:
    path: str
    pinned: str
    actual: str


@dataclass(frozen=True)
class Allowlist:
    entries: Mapping[str, str]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class Findings:
    violations: tuple[Violation, ...] = ()
    suppression_files: tuple[str, ...] = ()
    mismatches: tuple[PinMismatch, ...] = ()
    allowlist_errors: tuple[str, ...] = ()
    stale_entries: tuple[str, ...] = ()

    def failed(self) -> bool:
        return any(
            (
                self.violations,
                self.suppression_files,
                self.mismatches,
                self.allowlist_errors,
                self.stale_entries,
            )
        )


def _is_mpeg_audio_frame(header: bytes) -> bool:
    """MP3 (Layer III) or ADTS AAC frame sync, with field checks to avoid noise."""
    if len(header) < 3 or header[0] != 0xFF:
        return False
    second, third = header[1], header[2]
    if second in (0xFB, 0xFA, 0xF3, 0xF2):
        bitrate_index, sample_rate_index = third >> 4, (third >> 2) & 0b11
        return bitrate_index not in (0x0, 0xF) and sample_rate_index != 0b11
    if second in (0xF1, 0xF9):
        return (third >> 2) & 0b1111 < 13
    return False


_LEADING_SIGNATURES = {
    b"ID3": "MP3 (ID3)",
    b"OggS": "Ogg",
    b"fLaC": "FLAC",
    b"\x1a\x45\xdf\xa3": "Matroska/WebM",
    b"caff": "Core Audio",
    b"#!AMR": "AMR",
}


def sniff_media(header: bytes) -> str | None:
    """Name the audio/video container a file's leading bytes identify, if any."""
    if header[:4] == b"RIFF" and header[8:12] in (b"WAVE", b"AVI "):
        return header[8:12].decode().strip()
    if header[:4] == b"FORM" and header[8:12] in (b"AIFF", b"AIFC"):
        return header[8:12].decode()
    if header[4:8] == b"ftyp" and header[8:12] not in IMAGE_FTYP_BRANDS:
        return "MP4/QuickTime"
    for magic, label in _LEADING_SIGNATURES.items():
        if header.startswith(magic):
            return label
    if _is_mpeg_audio_frame(header):
        return "MPEG audio frame"
    return None


def classify(path: str, header: bytes = b"") -> str | None:
    """Return the rule a tracked path breaks, or None if it looks harmless."""
    name = PurePosixPath(path).name.lower()
    suffix = PurePosixPath(name).suffix
    if suffix in AUDIO_VIDEO_EXTENSIONS:
        return f"audio/video file ({suffix})"
    if suffix in CAPTION_EXTENSIONS:
        return f"caption/subtitle file ({suffix})"
    if suffix in ARCHIVE_EXTENSIONS:
        return f"archive ({suffix}); archives can hide session content"
    container = sniff_media(header)
    if container is not None:
        return f"audio/video content detected by file signature ({container})"
    if not _skips_name_rule(path, suffix):
        for marker in CONTENT_NAME_MARKERS:
            if marker in name:
                return f"file name suggests a {marker}"
    return None


def is_misplaced_suppression_file(path: str) -> bool:
    """gitleaks reads these from the scan root, so only .github/ may hold them."""
    return (
        PurePosixPath(path).name in GITLEAKS_SUPPRESSION_FILES
        and not path.startswith(OWNER_REVIEWED_DIR)
    )


def parse_allowlist(text: str) -> Allowlist:
    """Parse `<path> <blob sha>  # justification` lines; blank and `#` lines are skipped."""
    entries: dict[str, str] = {}
    errors: list[str] = []
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        entry, _, justification = line.partition("#")
        fields = entry.rsplit(maxsplit=1)
        if len(fields) != 2 or not BLOB_SHA.fullmatch(fields[1].lower()):
            errors.append(
                f"line {number}: '{entry.strip()}' must be '<path> <git blob sha>  # why'"
            )
            continue
        path, blob = fields[0], fields[1].lower()
        if not justification.strip():
            errors.append(
                f"line {number}: '{path}' has no justification comment "
                "(write it as: <path> <git blob sha>  # <why this file is synthetic>)"
            )
            continue
        entries[path] = blob
    return Allowlist(entries=entries, errors=tuple(errors))


def load_allowlist(path: Path) -> Allowlist:
    """A missing allowlist means no exemptions, never a skipped check."""
    if not path.is_file():
        return Allowlist(entries={}, errors=())
    return parse_allowlist(path.read_text(encoding="utf-8"))


def read_header(repo_root: Path, tracked: TrackedFile) -> bytes:
    """Read only the first bytes of a regular tracked file; anything else is empty."""
    if tracked.mode in UNREADABLE_MODES:
        return b""
    file_path = repo_root / tracked.path
    if file_path.is_symlink() or not file_path.is_file():
        return b""
    with file_path.open("rb") as handle:
        return handle.read(HEADER_BYTES)


def evaluate(
    files: Sequence[TrackedFile],
    allowlist: Allowlist,
    header_of: Callable[[TrackedFile], bytes],
) -> Findings:
    violations: list[Violation] = []
    suppression: list[str] = []
    mismatches: list[PinMismatch] = []
    for tracked in sorted(files, key=lambda f: f.path):
        if is_misplaced_suppression_file(tracked.path):
            suppression.append(tracked.path)
            continue
        rule = classify(tracked.path, header_of(tracked))
        if rule is None:
            continue
        pinned = allowlist.entries.get(tracked.path)
        if pinned is None:
            violations.append(Violation(path=tracked.path, rule=rule))
        elif pinned != tracked.blob:
            mismatches.append(PinMismatch(tracked.path, pinned, tracked.blob))
    tracked_paths = {f.path for f in files}
    return Findings(
        violations=tuple(violations),
        suppression_files=tuple(suppression),
        mismatches=tuple(mismatches),
        allowlist_errors=allowlist.errors,
        stale_entries=tuple(sorted(set(allowlist.entries) - tracked_paths)),
    )


def parse_ls_files_stage(output: bytes) -> list[TrackedFile]:
    """Parse `git ls-files -s -z` records: '<mode> <blob> <stage>\\t<path>'."""
    files = []
    for record in output.decode("utf-8").split("\0"):
        if not record:
            continue
        meta, _, path = record.partition("\t")
        mode, blob, _stage = meta.split(" ")
        files.append(TrackedFile(path=path, mode=mode, blob=blob))
    return files


def list_tracked_files(repo_root: Path) -> list[TrackedFile]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-s", "-z"],
        check=True,
        capture_output=True,
    )
    return parse_ls_files_stage(result.stdout)


def _section(lines: list[str], heading: Iterable[str], items: Iterable[str]) -> None:
    if lines:
        lines.append("")
    lines.extend(heading)
    lines.extend(f"  {item}" for item in items)


def format_report(findings: Findings, allowlist_path: str) -> str:
    lines: list[str] = []
    if findings.violations:
        first = findings.violations[0].path
        _section(
            lines,
            [
                f"Synthetic-fixture check failed: {len(findings.violations)} tracked "
                "file(s) look like session content.",
                "Session audio, video, transcripts, excerpts and feedback must never be "
                f"committed, not even as test fixtures ({POLICY_REFERENCE}).",
                "",
            ],
            [f"{v.path}: {v.rule}" for v in findings.violations],
        )
        lines += [
            "",
            "Fix: remove the file, or generate the data in the test instead.",
            "If the file is synthetic (generated, with no real student content), stage it "
            f"and pin its path and blob sha in {allowlist_path}, for example:",
            f"  {first} <blob sha>  # synthetic: generated by <script>; no real session "
            "content",
            f"Get the blob sha with: git ls-files -s -- {first}  (the second column)",
            "CODEOWNERS requests the owner's review of that file.",
        ]
    if findings.mismatches:
        _section(
            lines,
            [f"Allowlisted files changed since they were pinned in {allowlist_path}:"],
            [
                f"{m.path}: pinned {m.pinned}, tracked file is now {m.actual}"
                for m in findings.mismatches
            ],
        )
        lines += [
            "If the new content is still synthetic, replace the pinned sha with the new "
            "one.",
            "Get it with: git ls-files -s -- <path>  (the second column, after staging)",
        ]
    if findings.suppression_files:
        _section(
            lines,
            [
                "gitleaks suppression files must live in .github/, where CODEOWNERS "
                "requests the owner's review. Remove or move:"
            ],
            findings.suppression_files,
        )
    if findings.allowlist_errors:
        _section(
            lines, [f"{allowlist_path} has malformed entries:"], findings.allowlist_errors
        )
    if findings.stale_entries:
        _section(
            lines,
            [
                f"{allowlist_path} lists paths that are not tracked files. "
                "Remove these entries:"
            ],
            findings.stale_entries,
        )
    return "\n".join(lines)


def run(
    repo_root: Path,
    allowlist_path: str,
    list_files: Callable[[Path], list[TrackedFile]] = list_tracked_files,
    header_of: Callable[[Path, TrackedFile], bytes] = read_header,
) -> tuple[int, str]:
    """Return (exit code, message) so tests can drive the check without git."""
    files = list_files(repo_root)
    allowlist = load_allowlist(repo_root / allowlist_path)
    findings = evaluate(files, allowlist, lambda tracked: header_of(repo_root, tracked))
    if not findings.failed():
        return 0, (
            f"Synthetic-fixture check passed: {len(files)} tracked files, "
            f"{len(allowlist.entries)} allowlisted."
        )
    return 1, format_report(findings, allowlist_path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--allowlist", default=DEFAULT_ALLOWLIST)
    args = parser.parse_args(argv)
    code, message = run(args.repo_root, args.allowlist)
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
