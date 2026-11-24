"""Write the committed JSON Schema for the handoff contract.

Run from ``services/session`` after changing ``contract.py``::

    uv run python -m cst_session.handoff.export

``tests/test_handoff_schema.py`` fails while the committed copy differs.
"""

import json
from pathlib import Path

from cst_session.handoff.contract import json_schema

REPOSITORY = Path(__file__).resolve().parents[4]
SCHEMA_PATH = REPOSITORY / "handoff" / "completed-session.v1.schema.json"


def schema_text() -> str:
    return json.dumps(json_schema(), indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def main() -> None:
    SCHEMA_PATH.write_text(schema_text(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
