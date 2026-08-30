"""Genio Harness — root entry point.

Runs the Textual TUI front-end for the autonomous ReAct loop.

Usage::

    python3 genio.py

(in your interactive terminal, not in the background — the TUI needs a TTY.)
"""
from __future__ import annotations

from genio_harness.tui.app import GenioHarnessApp


def main() -> None:
    GenioHarnessApp().run()


if __name__ == "__main__":
    main()