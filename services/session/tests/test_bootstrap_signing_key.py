"""The bootstrap stores a key the session service accepts (T8, L2-2).

``infra/session-grading/bootstrap_signing_key.py`` adds the key to Secret
Manager as base64url text, which Cloud Run injects into
``CST_STATE_SIGNING_KEY``. The script is loaded from its path so these checks
run with the session suite; nothing here calls gcloud or the network.
"""

import base64
import importlib.util
from pathlib import Path
from types import ModuleType

from cst_session.state import KEY_BYTES, decode_signing_key

SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "infra"
    / "session-grading"
    / "bootstrap_signing_key.py"
)


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bootstrap_signing_key", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_t8_the_generated_key_decodes_through_the_service_rule() -> None:
    script = load_script()

    for _ in range(64):
        text = script.new_key_text()
        assert isinstance(text, bytes)
        assert len(decode_signing_key(text.decode("ascii"))) == KEY_BYTES


def test_t8_each_run_generates_a_different_key() -> None:
    script = load_script()

    assert len({script.new_key_text() for _ in range(16)}) == 16


def test_t8_secret_manager_receives_the_text_not_the_raw_bytes() -> None:
    script = load_script()
    text = script.new_key_text()

    body = script.add_version_body(text)

    assert set(body) == {"payload"} and set(body["payload"]) == {"data"}
    assert base64.b64decode(body["payload"]["data"], validate=True) == text
