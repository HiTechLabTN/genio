#!/usr/bin/env python3
"""Genio desktop Client runner.

Launches the standalone PySide6 client::

    python genio_client.py

If no desktop display is available the client still loads (it degrades to the
"offscreen" Qt platform if ``QT_QPA_PLATFORM`` is not already set).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))


def main() -> None:
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        pass
    elif os.environ.get("QT_QPA_PLATFORM") is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

    from genio_harness.client.app_window import main as app_main

    sys.exit(app_main())


if __name__ == "__main__":
    main()