"""Sessions as JSON files in the workspace, plus the built-in ``.py`` sessions.

A JSON session stores every ``SessionConfig`` setting except the two paths
that depend on the workspace (``out_dir``, ``rois_dir``); those are filled in
when the session is loaded, so a session file keeps working if the workspace
is moved or shared. The older ``sessions/sYYYYMMDD.py`` files keep working
unchanged and keep their own paths.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import sys
from pathlib import Path

from .config import SessionConfig
from .workspace import (REPO_ROOT, ensure_workspace, get_workspace,
                        results_dir, rois_dir, sessions_dir)

SCHEMA_VERSION = 1
_NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def validate_session_name(name: str) -> None:
    """Names become file names (``<name>.json``, ``<name>_<fid>.npy``)."""
    if not isinstance(name, str) or not _NAME_OK.match(name):
        raise ValueError(
            f"invalid session name {name!r}: use letters, digits, '_', '-' "
            f"or '.', starting with a letter or digit")


def session_path(name: str, workspace=None) -> Path:
    ws = Path(workspace) if workspace is not None else get_workspace()
    return sessions_dir(ws) / f"{name}.json"


def save_session(cfg: SessionConfig, workspace=None) -> Path:
    """Write ``cfg`` to ``<workspace>/sessions/<name>.json`` and return the path."""
    validate_session_name(cfg.name)
    ws = ensure_workspace(workspace)

    d = cfg.to_dict()
    # Derived paths are left out when they are just the workspace defaults.
    if Path(cfg.out_dir) == results_dir(ws) / cfg.name:
        d.pop("out_dir")
    if cfg.rois_dir is not None and Path(cfg.rois_dir) == rois_dir(ws):
        d.pop("rois_dir")

    path = session_path(cfg.name, ws)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"schema_version": SCHEMA_VERSION, **d},
                              indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)                      # atomic: never a half-written file
    return path


def load_session(path, workspace=None) -> SessionConfig:
    """Load one session JSON, filling in the workspace-dependent paths."""
    path = Path(path)
    ws = Path(workspace) if workspace is not None else get_workspace()
    d = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise ValueError("not a session file (expected a JSON object)")

    version = d.pop("schema_version", None)
    if version != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version {version!r} "
                         f"(this version reads {SCHEMA_VERSION})")

    d.setdefault("name", path.stem)
    validate_session_name(d["name"])
    d.setdefault("out_dir", str(results_dir(ws) / d["name"]))
    if d.get("rois_dir") is None:
        d["rois_dir"] = str(rois_dir(ws))
    return SessionConfig.from_dict(d)


def _legacy_sessions() -> dict:
    """The built-in sessions from the repo's ``sessions/`` package."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return dict(importlib.import_module("sessions").SESSIONS)


def load_all_sessions(workspace=None):
    """All sessions: built-in ``.py`` ones plus the workspace JSON ones.

    Returns ``(sessions, problems)``: a ``{name: SessionConfig}`` dict and a
    list of human-readable messages for anything that could not be loaded
    (one broken session never hides the others). A JSON session whose name is
    already taken by a built-in one is ignored, with a message.
    """
    ws = Path(workspace) if workspace is not None else get_workspace()
    sessions: dict[str, SessionConfig] = {}
    problems: list[str] = []

    try:
        sessions.update(_legacy_sessions())
    except Exception as e:                     # broken/missing built-in sessions
        problems.append(f"built-in sessions/ could not be loaded: "
                        f"{type(e).__name__}: {e}")

    sdir = sessions_dir(ws)
    if sdir.is_dir():
        for p in sorted(sdir.glob("*.json")):
            try:
                cfg = load_session(p, ws)
            except Exception as e:
                problems.append(f"{p.name}: {e}")
                continue
            if cfg.name in sessions:
                problems.append(f"{p.name}: the name '{cfg.name}' is already "
                                f"used by a built-in session; ignored")
                continue
            sessions[cfg.name] = cfg
    return sessions, problems


def get_sessions(workspace=None, verbose=True) -> dict:
    """:func:`load_all_sessions` for command-line scripts (prints problems)."""
    sessions, problems = load_all_sessions(workspace)
    if verbose:
        for msg in problems:
            print(f"warning: {msg}", file=sys.stderr)
    return sessions
