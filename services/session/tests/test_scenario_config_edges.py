"""Scenario config edge cases from checkouts and editors (#27 AC1, QA).

A Windows checkout with ``core.autocrlf=true`` writes the TOML files with CRLF
line endings, and some editors save UTF-8 with a byte-order mark. TOML also
lets a text key hold an array or a table. Each case must either load exactly as
the committed files do or fail with a ``CatalogueError`` naming the file, never
crash with another exception or load a non-string value.
"""

import shutil
from importlib.resources import files
from pathlib import Path

import pytest

from cst_session.scenarios import SCENARIO_IDS, CatalogueError, load_catalogue

CONFIGS = Path(str(files("cst_session.scenarios") / "configs"))


def config_copy(tmp_path: Path) -> Path:
    target = tmp_path / "configs"
    shutil.copytree(CONFIGS, target)
    return target


def with_line_endings(raw: bytes, ending: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\n", ending)


def test_crlf_configs_load_exactly_like_lf_configs(tmp_path: Path) -> None:
    directory = config_copy(tmp_path)
    for scenario_id in SCENARIO_IDS:
        path = directory / f"{scenario_id}.toml"
        path.write_bytes(with_line_endings(path.read_bytes(), b"\r\n"))

    assert load_catalogue(directory).scenarios == load_catalogue().scenarios


def test_a_byte_order_mark_fails_loading_with_the_file_named(tmp_path: Path) -> None:
    directory = config_copy(tmp_path)
    path = directory / "crisis_risk.toml"
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())

    with pytest.raises(CatalogueError, match=r"crisis_risk\.toml: not valid"):
        load_catalogue(directory)


@pytest.mark.parametrize(
    "replacement",
    [
        'title = ["Routine intake"]',
        'title = {text = "Routine intake"}',
        'title.text = "Routine intake"',
    ],
)
def test_an_array_or_table_in_a_text_field_fails_loading(
    tmp_path: Path, replacement: str
) -> None:
    directory = config_copy(tmp_path)
    path = directory / "routine_intake.toml"
    text = path.read_text(encoding="utf-8")
    assert text.count('title = "Routine intake"') == 1
    path.write_text(
        text.replace('title = "Routine intake"', replacement), encoding="utf-8"
    )

    with pytest.raises(CatalogueError, match=r"routine_intake\.toml: title"):
        load_catalogue(directory)


def test_a_table_header_in_place_of_a_text_field_fails_loading(
    tmp_path: Path,
) -> None:
    directory = config_copy(tmp_path)
    path = directory / "resistant_client.toml"
    text = path.read_text(encoding="utf-8")
    old = 'summary = "Practice collaboration"\n'
    assert text.count(old) == 1
    path.write_text(
        text.replace(old, "") + '[summary]\ntext = "Practice collaboration"\n',
        encoding="utf-8",
    )

    with pytest.raises(CatalogueError, match=r"resistant_client\.toml: summary"):
        load_catalogue(directory)
