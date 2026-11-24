"""Every service's content-free logging helper is the accounts copy, byte for byte.

Owner decision 2026-11-23 (#63): the canonical module is
``services/accounts/cst_accounts/content_free_log.py`` and every other service
holds an identical copy in its ``cst_<service>`` package. CI runs each service
from its own directory with the whole repository checked out, so paths are
resolved from this file. Fix a failure by copying the accounts file over the
others, never by editing a copy.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICES = REPO_ROOT / "services"
CANONICAL = SERVICES / "accounts" / "cst_accounts" / "content_free_log.py"


def service_packages() -> list[Path]:
    return sorted(path.parent for path in SERVICES.glob("*/cst_*/__init__.py"))


def test_every_service_package_holds_the_helper() -> None:
    packages = service_packages()

    assert {package.name for package in packages} >= {"cst_accounts", "cst_session"}
    missing = [
        str(package.relative_to(REPO_ROOT))
        for package in packages
        if not (package / "content_free_log.py").is_file()
    ]
    assert missing == []


def test_every_copy_matches_the_accounts_copy_byte_for_byte() -> None:
    canonical = CANONICAL.read_bytes()

    drifted = [
        str(copy.relative_to(REPO_ROOT))
        for copy in sorted(SERVICES.glob("*/cst_*/content_free_log.py"))
        if copy.read_bytes() != canonical
    ]
    assert drifted == []
