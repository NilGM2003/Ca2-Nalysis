#!/usr/bin/env python3
"""Manually correct the cell segmentation for one file.

Usage:
    python edit_rois.py [session] [file_id]      # default: 20260609 1

Opens an interactive editor seeded with the current ROIs (manual mask if one
exists, otherwise the automatic Otsu segmentation). Add / delete / merge /
split / reshape ROIs, then Save. The mask is written to
``rois/<session>_<file>.npy`` and is picked up automatically by both
``analyze.py`` and ``view.py`` — re-run ``analyze.py [session]`` afterwards to
regenerate traces and figures.

Needs an interactive matplotlib backend (a desktop session).
"""
import sys
from pathlib import Path

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

from calcium.roieditor import ROIEditor   # noqa: E402
from calcium.sessionstore import get_sessions    # noqa: E402


def main(argv):
    name = argv[1] if len(argv) > 1 else "20260609"
    fid = argv[2] if len(argv) > 2 else "1"
    SESSIONS = get_sessions()
    if name not in SESSIONS:
        sys.exit(f"Unknown session '{name}'. Available: {', '.join(SESSIONS)}")
    cfg = SESSIONS[name]
    if fid not in cfg.file_ids:
        sys.exit(f"Unknown file '{fid}'. Available: {', '.join(cfg.file_ids)}")
    ROIEditor(cfg, fid).show()


if __name__ == "__main__":
    main(sys.argv)
