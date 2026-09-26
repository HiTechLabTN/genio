"""Install-completeness regression (clean-room finding: psutil missing).

Asserts every HARD (module top-level, non-optional) third-party import of
the runtime (genio_server/**, core/*.py hors legacy evolution, config.py)
is pinned in requirements.txt — so a fresh prefix venv can boot the API.

Lazy function-level imports (faster_whisper/whisper/mss/pyautogui/yaml)
are honest optionals (features degrade, documented) and are NOT asserted.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DIST_MAP = {
    "multipart": "python-multipart",
    "yaml": "pyyaml",
    "PIL": "pillow",
}

INTRA_REPO = {"genio_server", "core", "config", "genio_executive_core",
              "installer"}

OPTIONAL_LAZY_DOCUMENTED = {"faster_whisper", "whisper", "mss",
                            "pyautogui", "yaml", "PIL", "requests"}


def _hard_imports(path):
    """Top-level imports not guarded by try/except."""
    try:
        tree = ast.parse(path.read_text())
    except (OSError, SyntaxError):
        return set()
    found = set()

    def visit(node, guarded):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Try):
                for sub in (child.body + child.handlers + child.orelse + child.finalbody):
                    visit(sub, True) if isinstance(sub, ast.AST) else None
                for sub in child.body:
                    _collect(sub, True)
                continue
            _collect(child, guarded)
            visit(child, guarded)

    def _collect(node, guarded):
        if guarded:
            return
        if isinstance(node, ast.Import):
            for a in node.names:
                found.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])

    for node in tree.body:
        if isinstance(node, ast.Try):
            continue
        _collect(node, False)
    return found


def _pins():
    pins = set()
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)(\[.*\])?==([^\s;]+)", line.strip())
        if m:
            pins.add(m.group(1).lower().replace("_", "-"))
    return pins


def test_hard_imports_pinned():
    stdlib = sys.stdlib_module_names
    scopes = [ROOT / "genio_server", ROOT / "core"]
    files = [ROOT / "config.py"]
    for base in scopes:
        for p in base.rglob("*.py"):
            if "evolution" in p.parts or "tests" in p.parts:
                continue
            files.append(p)
    missing = {}
    pins = _pins()
    for f in files:
        for mod in _hard_imports(f):
            if mod in stdlib or mod in INTRA_REPO:
                continue
            dist = DIST_MAP.get(mod, mod).lower().replace("_", "-")
            if dist not in pins:
                missing.setdefault(f.relative_to(ROOT).as_posix(), []).append(mod)
    assert not missing, f"hard imports not pinned in requirements.txt: {missing}"


def test_psutil_pinned_explicitly():
    # The exact clean-room failure: main.py imports psutil at module level.
    assert "psutil" in _pins()
