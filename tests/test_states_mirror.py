"""State-machine lock: python STATES == TypeScript INSTALL_STATES."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from installer.core.states import STATES, validate_graph  # noqa: E402


def _parse_ts():
    text = (ROOT / "genio_client" / "src" / "lib" / "installStates.ts").read_text()
    ids = re.findall(r"^\s{2}(\w+): \{", text, re.M)
    return ids


def test_graph_valid():
    assert validate_graph() == []


def test_all_charter_states_present():
    expected = {"idle", "detecting", "checking", "ready", "downloading",
                "verifying", "installing", "configuring", "securing",
                "health_check", "complete", "degraded", "failed", "blocked",
                "requires_user_action", "rolling_back", "rolled_back", "cancelled"}
    assert set(STATES) == expected


def test_ts_mirror_in_sync():
    assert _parse_ts() == list(STATES.keys())


def test_terminal_states_have_no_transitions():
    for sid in ("complete", "rolled_back", "cancelled"):
        assert STATES[sid]["transitions"] == []
