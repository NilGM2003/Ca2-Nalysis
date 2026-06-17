#!/usr/bin/env python3
"""Run the calcium dose-response pipeline for a session.

Usage:
    python analyze.py [session]      # default: 20260609

Sessions are defined in ``sessions/``; the analysis code lives in
``src/calcium/``.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")               # headless batch rendering

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from calcium import run_session   # noqa: E402
from sessions import SESSIONS     # noqa: E402


def main(argv):
    name = argv[1] if len(argv) > 1 else "20260609"
    if name not in SESSIONS:
        sys.exit(f"Unknown session '{name}'. Available: {', '.join(SESSIONS)}")
    run_session(SESSIONS[name])


if __name__ == "__main__":
    main(sys.argv)
