"""The user's workspace: one folder holding sessions, ROI masks and results.

Layout::

    <workspace>/
        sessions/   <name>.json      session settings (created by the app)
        rois/       <name>_<fid>.npy hand-corrected ROI masks
        results/    <name>/          figures + CSVs

Which folder is the workspace is decided, in order, by:

1. the ``CALCIUM_WORKSPACE`` environment variable,
2. the folder saved with :func:`set_workspace` (kept in ``~/.calcium_analysis``),
3. the default ``~/CalciumAnalysis``.

Only ``pathlib`` is used, so the same code works on macOS and Windows.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ENV_VAR = "CALCIUM_WORKSPACE"
DEFAULT_WORKSPACE = Path.home() / "CalciumAnalysis"
SETTINGS_FILE = Path.home() / ".calcium_analysis" / "settings.json"

# Repo root = two levels above src/calcium/.
REPO_ROOT = Path(__file__).resolve().parents[2]


def get_workspace() -> Path:
    """The workspace folder (not created; see :func:`ensure_workspace`)."""
    env = os.environ.get(ENV_VAR)
    if env:
        return Path(env).expanduser()
    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if saved.get("workspace"):
            return Path(saved["workspace"]).expanduser()
    except (OSError, ValueError, AttributeError):
        pass
    return DEFAULT_WORKSPACE


def set_workspace(path) -> Path:
    """Remember ``path`` as the workspace for future runs."""
    path = Path(path).expanduser().resolve()
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps({"workspace": str(path)}, indent=2),
                             encoding="utf-8")
    return path


def sessions_dir(workspace: Path) -> Path:
    return Path(workspace) / "sessions"


def rois_dir(workspace: Path) -> Path:
    return Path(workspace) / "rois"


def results_dir(workspace: Path) -> Path:
    return Path(workspace) / "results"


def ensure_workspace(workspace=None) -> Path:
    """Create the workspace folders if needed and return the workspace path."""
    ws = Path(workspace) if workspace is not None else get_workspace()
    for d in (sessions_dir(ws), rois_dir(ws), results_dir(ws)):
        d.mkdir(parents=True, exist_ok=True)
    return ws
