#!/usr/bin/env python3
"""Launch the calcium analysis app.

Usage:
    uv run python app.py

Create sessions, edit protocols, run the analysis, edit ROIs and open the
viewer from one window. Sessions, ROI masks and results live in the workspace
folder (default ~/CalciumAnalysis; change it in the window).
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")      # this process draws no figures; jobs run separately

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from calcium.gui.tcltk import point_tcl_tk_at_base_python   # noqa: E402

# uv's Python inside a venv cannot find Tcl/Tk by itself (breaks when started
# from Finder); point it at the real install before the first Tk() window.
point_tcl_tk_at_base_python()

try:
    import tkinter  # noqa: F401
except ImportError:
    sys.exit("This Python has no tkinter. With uv, run:  uv python install 3.12"
             "\nthen recreate the environment:  rm -rf .venv && uv sync")

from calcium.gui.main_window import main   # noqa: E402

if __name__ == "__main__":
    main()
