#!/usr/bin/env python3
"""Genio Server runner.

Starts the distributed Genio backend daemon::

    python genio_server.py               # 0.0.0.0:8000
    python genio_server.py --host 127.0.0.1 --port 9000 --api-key secret

Equivalent to ``uvicorn genio_harness.server.main:app`` with the repo root on
``sys.path`` so ``genio_harness`` resolves from any working directory.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the Genio backend daemon.")
    parser.add_argument("--host", default=os.environ.get("GENIO_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GENIO_PORT", "8000")))
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GENIO_API_KEY", ""),
        help="require this key via the X-API-Key header (default: from GENIO_API_KEY)",
    )
    args = parser.parse_args()

    if args.api_key:
        os.environ["GENIO_API_KEY"] = args.api_key

    import uvicorn

    uvicorn.run(
        "genio_harness.server.main:app",
        host=args.host,
        port=args.port,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()