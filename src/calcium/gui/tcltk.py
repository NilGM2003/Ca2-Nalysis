"""Make tkinter find its Tcl/Tk scripts when Python runs inside a venv.

uv's standalone Pythons keep the Tcl/Tk scripts in ``<install>/lib/tcl9.0``
and ``<install>/lib/tk9.0``. Inside a virtual environment Tcl looks relative
to the *venv* instead, finds nothing and fails with::

    TclError: Cannot find a usable init.tcl in the following directories: ...

It can go unnoticed when a shell happens to set ``TCL_LIBRARY`` and then breaks
when the app is started from Finder. The fix is to set ``TCL_LIBRARY`` and
``TK_LIBRARY`` to the real install before the first ``tkinter.Tk()``.
Variables that are already set are left alone.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_SPEC = {"TCL_LIBRARY": ("tcl", "init.tcl"), "TK_LIBRARY": ("tk", "tk.tcl")}


def point_tcl_tk_at_base_python(base_prefix=None, environ=None, versions=None):
    """Set TCL_LIBRARY / TK_LIBRARY if unset. Returns what was set."""
    env = os.environ if environ is None else environ
    base = Path(sys.base_prefix if base_prefix is None else base_prefix)

    if versions is None:                       # versions _tkinter was linked with
        try:
            import _tkinter
            versions = {"TCL_LIBRARY": str(_tkinter.TCL_VERSION),
                        "TK_LIBRARY": str(_tkinter.TK_VERSION)}
        except Exception:
            versions = {}

    changed = {}
    for var, (stem, marker) in _SPEC.items():
        if env.get(var):
            continue
        candidates = []
        if versions.get(var):
            candidates.append(base / "lib" / f"{stem}{versions[var]}")
        candidates += sorted((base / "lib").glob(f"{stem}[0-9]*"), reverse=True)
        for d in candidates:
            if (d / marker).is_file():
                env[var] = changed[var] = str(d)
                break
    return changed
