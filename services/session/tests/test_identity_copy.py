"""T2: the session identity guard is a verbatim copy of the accounts guard (FR-1).

Each pair below is compared by AST, so a change to either copy that alters
behavior (or a docstring) fails here until both services change together.
"""

import ast
from pathlib import Path

import pytest

SESSION = Path(__file__).resolve().parents[1] / "cst_session"
ACCOUNTS = Path(__file__).resolve().parents[2] / "accounts" / "cst_accounts"

# (accounts file, accounts qualified name, session file, session qualified name)
COPIES = [
    *(
        ("domain.py", name, "identity/domain.py", name)
        for name in (
            "Rejected",
            "DeletionPending",
            "Unavailable",
            "AccessNotApproved",
            "AccessState",
            "Student",
        )
    ),
    (
        "firebase.py",
        "FirebaseIdentity._claims",
        "identity/firebase.py",
        "FirebaseIdentity._claims",
    ),
    (
        "firebase.py",
        "FirebaseIdentity.verify",
        "identity/firebase.py",
        "FirebaseIdentity.verify",
    ),
    ("store.py", "ACCESS", "identity/store.py", "ACCESS"),
    ("store.py", "_STORED_STATES", "identity/store.py", "_STORED_STATES"),
    ("store.py", "_stored_state", "identity/store.py", "_stored_state"),
    ("store.py", "storage_operation", "identity/store.py", "storage_operation"),
    (
        "store.py",
        "FirestoreAccounts.pending",
        "identity/store.py",
        "FirestoreAccess.pending",
    ),
    (
        "store.py",
        "FirestoreAccounts.access_state",
        "identity/store.py",
        "FirestoreAccess.access_state",
    ),
    *(
        ("api.py", f"create_app.{name}", "api.py", f"create_app.{name}")
        for name in (
            "eligible",
            "bearer",
            "token_owner",
            "signed_in",
            "approved",
            "rejected",
            "deletion_pending",
            "access_not_approved",
            "unavailable",
        )
    ),
]


def definitions(path: Path) -> dict[str, ast.AST]:
    """Every class, function and module-level assignment, by qualified name."""
    found: dict[str, ast.AST] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                name = f"{prefix}{child.name}"
                found[name] = child
                visit(child, f"{name}.")
            elif isinstance(child, ast.Assign) and not prefix:
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        found[target.id] = child

    visit(ast.parse(path.read_text(encoding="utf-8")), "")
    return found


@pytest.mark.parametrize(("source", "name", "copy", "copy_name"), COPIES)
def test_t2_copy_matches_accounts(
    source: str, name: str, copy: str, copy_name: str
) -> None:
    original = definitions(ACCOUNTS / source).get(name)
    copied = definitions(SESSION / copy).get(copy_name)
    assert original is not None, f"accounts no longer defines {name}"
    assert copied is not None, f"session does not define {copy_name}"
    assert ast.dump(copied) == ast.dump(original), (
        f"{copy}:{copy_name} drifted from accounts {source}:{name}"
    )


def test_t2_drift_is_detected(tmp_path: Path) -> None:
    changed = tmp_path / "store.py"
    changed.write_text(
        (ACCOUNTS / "store.py")
        .read_text(encoding="utf-8")
        .replace("return AccessState.MISSING", "return AccessState.APPROVED"),
        encoding="utf-8",
    )
    original = definitions(ACCOUNTS / "store.py")["FirestoreAccounts.access_state"]
    assert ast.dump(definitions(changed)["FirestoreAccounts.access_state"]) != ast.dump(
        original
    )
