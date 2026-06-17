#!/usr/bin/env python3
"""Launch the interactive frame + trace viewer.

Usage:
    python view.py [session] [file_id]      # default: 20260609 1

Needs an interactive matplotlib backend (a desktop session). Requires the
session's trace CSVs to exist — run ``analyze.py`` first.
"""
import sys
from pathlib import Path

# Select a working interactive backend before anything imports pyplot,
# otherwise matplotlib may fall back to the non-interactive Agg backend.
import matplotlib


def _select_backend():
    for bk in ("QtAgg", "TkAgg", "GTK3Agg"):
        try:
            matplotlib.use(bk, force=True)
            import matplotlib.pyplot as plt
            fig = plt.figure()            # actually instantiate the GUI canvas
            plt.close(fig)
            return bk
        except Exception:
            continue
    sys.exit("No interactive matplotlib backend available. Install one, e.g.:"
             "\n    uv add pyqt6")


_BACKEND = _select_backend()

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from calcium.viewer import TraceViewer   # noqa: E402
from sessions import SESSIONS            # noqa: E402


def main(argv):
    name = argv[1] if len(argv) > 1 else "20260609"
    fid = argv[2] if len(argv) > 2 else "1"
    if name not in SESSIONS:
        sys.exit(f"Unknown session '{name}'. Available: {', '.join(SESSIONS)}")
    cfg = SESSIONS[name]
    if fid not in cfg.file_ids:
        sys.exit(f"Unknown file '{fid}'. Available: {', '.join(cfg.file_ids)}")
    TraceViewer(cfg, fid).show()


if __name__ == "__main__":
    main(sys.argv)
