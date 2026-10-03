#!/usr/bin/env python3
"""Run the calcium analysis pipeline for a session.

Usage:
    python analyze.py [session]      # default: 20260609

Sessions are the built-in ones in ``sessions/`` plus the JSON sessions in the
workspace folder (``<workspace>/sessions/``); the analysis code lives in
``src/calcium/``.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")               # headless batch rendering

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from calcium import run_session                  # noqa: E402
from calcium.sessionstore import get_sessions    # noqa: E402


def main(argv):
    name = argv[1] if len(argv) > 1 else "20260609"
    sessions = get_sessions()
    if name not in sessions:
        sys.exit(f"Unknown session '{name}'. Available: {', '.join(sessions)}")
    run_session(sessions[name])


if __name__ == "__main__":
    main(sys.argv)
