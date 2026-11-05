"""Opt-in live deletion probe using two synthetic, unidentifiable accounts.

Run seed, execute the deployed scheduled worker, then run verify with the same
ignored fixture file. No production authentication bypass is added. This proves
worker cleanup and owner isolation, not Google sign-in or the client flow.
"""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import firebase_admin
from firebase_admin import auth, credentials
from google.cloud import firestore
from google.oauth2.credentials import Credentials

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "accounts"))

PROJECT = "casestudy-tech-dev-2e03d0"


class GcloudCredential(credentials.Base):
    def __init__(self, token: str):
        self.credential = Credentials(token, quota_project_id=PROJECT)

    def get_credential(self):
        return self.credential


def main() -> None:
    from cst_accounts.store import FirestoreAccounts

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["seed", "verify"])
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()
    token = subprocess.check_output(
        ["gcloud.cmd", "auth", "print-access-token", "--project=" + PROJECT, "--quiet"],
        text=True,
    ).strip()
    credential = GcloudCredential(token)
    app = firebase_admin.initialize_app(credential, options={"projectId": PROJECT})
    client = firestore.Client(project=PROJECT, credentials=credential.get_credential())
    store = FirestoreAccounts(client)
    if args.stage == "seed":
        if args.fixture.exists():
            raise SystemExit("Fixture already exists; verify/clean that probe first.")
        suffix = uuid4().hex
        fixture = {
            "delete": "cst-probe-delete-" + suffix,
            "keep": "cst-probe-keep-" + suffix,
        }
        args.fixture.parent.mkdir(parents=True, exist_ok=True)
        # Persist synthetic IDs before creation so a failed setup is recoverable.
        args.fixture.write_text(json.dumps(fixture), encoding="utf-8")
        for uid in fixture.values():
            auth.create_user(uid=uid, app=app)
            client.collection("students").document(uid).collection("scores").document(
                "synthetic"
            ).set({"scenario_id": "routine", "overall": 3, "categories": [3] * 6})
        store.request_deletion(fixture["delete"], datetime.now(UTC))
        print("Seeded two synthetic owners and one durable deletion request.")
        return

    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    if set(fixture) != {"delete", "keep"} or not all(
        isinstance(uid, str) and uid.startswith("cst-probe-")
        for uid in fixture.values()
    ):
        raise SystemExit("Invalid synthetic fixture; no cleanup attempted.")
    try:
        auth.get_user(fixture["delete"], app=app)
    except auth.UserNotFoundError:
        pass
    else:
        raise SystemExit("Deletion worker has not removed the synthetic account.")
    if store.scores(fixture["delete"]):
        raise SystemExit("Synthetic scores remain after cleanup.")
    marker = client.collection("account_deletions").document(fixture["delete"]).get()
    data = marker.to_dict() or {}
    if data.get("state") != "completed" or not store.pending(fixture["delete"]):
        raise SystemExit("Completed denial marker missing.")
    if datetime.now(UTC) >= data["deadline"]:
        raise SystemExit("Cleanup exceeded its original 30-day deadline.")
    auth.get_user(fixture["keep"], app=app)
    if len(store.scores(fixture["keep"])) != 1:
        raise SystemExit("Other owner's synthetic record was affected.")
    print(
        "PASS: deleted account/scores, retained denial marker, met deadline, preserved other owner."
    )
    store.erase_scores(fixture["keep"])
    auth.delete_user(fixture["keep"], app=app)
    marker.reference.delete()
    args.fixture.unlink()
    print("Synthetic fixtures cleaned up.")


if __name__ == "__main__":
    main()
