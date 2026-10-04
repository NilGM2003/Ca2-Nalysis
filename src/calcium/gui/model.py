"""Logic behind the app's session form. No Tk here, so it is fully testable.

The window keeps the form as a plain dict of strings/bools (see
``default_form``). ``build_config`` turns it into a validated
``SessionConfig`` (or raises ``FormError`` listing *every* problem at once),
and ``form_from_config`` goes the other way when a saved session is opened.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

from ..config import EXPERIMENT_TYPES, SessionConfig
from ..dyes import DYES
from ..protocol import build_epochs, mmss
from ..sessionstore import validate_session_name
from ..workspace import results_dir, rois_dir


class FormError(ValueError):
    """The form has one or more problems; ``.problems`` lists them all."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


# --------------------------------------------------------------- defaults
def default_form() -> dict:
    return dict(
        name="", data_dir="", dye="calbryte", experiment_type="lifu",
        file_ids=[], protocols={},
        off_labels="STOP", default_dc="40",
        dose_unit="V", dose_label="LIFUS amplitude (V)", dose_log=False,
        dose_dc="40", dose_exclude_files="", dose_exclude_dose="",
        truncate="", detrend=True, detrend_sec="200", detrend_pct="20",
        resp_dff="0.10", resp_k="3.0", min_area="15", max_area="4000")


# ---------------------------------------------------------- protocol text
def _fmt_time(t: float) -> str:
    return str(int(t)) if t == int(t) else f"{t:.2f}"


def protocol_to_text(events) -> str:
    """[(2, 'ISO'), (18.3, 'ISO')] -> '2, ISO\\n18.30, ISO'."""
    return "\n".join(f"{_fmt_time(t)}, {lab}" for t, lab in events)


def parse_protocol_text(text: str) -> list[tuple[float, str]]:
    """One event per line: ``time, label``. Times are mm.ss (5.30 = 5 min 30 s).

    ``#`` starts a comment; blank lines are ignored. Raises ValueError naming
    the offending line.
    """
    events: list[tuple[float, str]] = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = re.split(r"[,\s]+", line, maxsplit=1)
        if len(parts) != 2 or not parts[1].strip():
            raise ValueError(f"line {n}: expected 'time, label' "
                             f"(e.g. '2, 4.5V'), got {raw.strip()!r}")
        try:
            t = float(parts[0])
        except ValueError:
            raise ValueError(f"line {n}: time {parts[0]!r} is not a number")
        if t < 0:
            raise ValueError(f"line {n}: time cannot be negative")
        secs = round((t - int(t)) * 100)
        if secs >= 60:
            raise ValueError(f"line {n}: time {parts[0]} means {secs} seconds; "
                             f"times are mm.ss (5.30 = 5 min 30 s)")
        events.append((int(t) if t == int(t) else t, parts[1].strip()))
    for (t0, _), (t1, _) in zip(events, events[1:]):
        if mmss(t1) <= mmss(t0):
            raise ValueError(f"times must increase: {_fmt_time(t1)} comes "
                             f"after {_fmt_time(t0)}")
    return events


# ------------------------------------------------------ small text parsers
def _items(text: str) -> list[str]:
    return [t.strip() for t in re.split(r"[,;\n]+", str(text)) if t.strip()]


def parse_truncate(text: str) -> dict[str, float]:
    """'6: 27, 1: 15' -> {'6': 27.0, '1': 15.0} (file id: minutes)."""
    out: dict[str, float] = {}
    for item in _items(text):
        m = re.fullmatch(r"(.+?)\s*[:=]\s*([-+]?\d*\.?\d+)", item)
        if not m:
            raise ValueError(f"cannot read {item!r}; use 'file: minutes' "
                             f"(e.g. '6: 27')")
        out[m.group(1).strip()] = float(m.group(2))
    return out


def format_truncate(d: dict) -> str:
    return ", ".join(f"{k}: {v:g}" for k, v in d.items())


# ------------------------------------------------------------- the config
def build_config(form: dict, workspace) -> SessionConfig:
    """Validate ``form`` and build a SessionConfig, or raise FormError."""
    problems: list[str] = []
    ws = Path(workspace)

    def num(key, label, cast=float, minimum=None):
        try:
            v = cast(float(str(form[key]).strip()))
        except (ValueError, TypeError, OverflowError):
            problems.append(f"{label} must be a number")
            return cast(0)
        if cast is int and float(str(form[key]).strip()) != v:
            problems.append(f"{label} must be a whole number")
        if minimum is not None and v < minimum:
            problems.append(f"{label} must be at least {minimum:g}")
        return v

    name = str(form["name"]).strip()
    try:
        validate_session_name(name)
    except ValueError as e:
        problems.append(str(e))

    data_dir = str(form["data_dir"]).strip()
    if not data_dir:
        problems.append("choose the data folder")
    elif not Path(data_dir).is_dir():
        problems.append(f"data folder does not exist: {data_dir}")

    dye = form["dye"]
    if dye not in DYES:
        problems.append(f"dye must be one of {sorted(DYES)}")
    etype = form["experiment_type"]
    if etype not in EXPERIMENT_TYPES:
        problems.append(f"experiment type must be one of {EXPERIMENT_TYPES}")

    file_ids = [str(f) for f in form["file_ids"]]
    if not file_ids:
        problems.append("no files in the session (scan the data folder)")
    if len(set(file_ids)) != len(file_ids):
        problems.append("duplicate file ids")

    off_labels = set(_items(form["off_labels"]))
    default_dc = num("default_dc", "Default duty cycle", int, 0)

    # ---- per-file protocols
    protocol: dict[str, list] = {}
    for fid in file_ids:
        try:
            events = parse_protocol_text(form["protocols"].get(fid, ""))
        except ValueError as e:
            problems.append(f"file {fid}: {e}")
            continue
        if not events:
            problems.append(f"file {fid}: protocol is empty")
            continue
        try:
            eps = build_epochs(events, 1e9, default_dc, off_labels)
        except ValueError as e:
            problems.append(f"file {fid}: {e}")
            continue
        if not eps:
            problems.append(f"file {fid}: every label is an 'off' label, so "
                            f"there is nothing to analyse")
            continue
        if etype == "lifu":
            for _s, _e, dose, _dc, lab in eps:
                if math.isnan(dose):
                    problems.append(
                        f"file {fid}: label {lab!r} has no number; LIFU "
                        f"labels look like '4.5V' or '100Hz@DC20'")
        protocol[fid] = events

    # ---- optional settings
    try:
        truncate = parse_truncate(form["truncate"])
    except ValueError as e:
        problems.append(f"Truncate: {e}")
        truncate = {}
    for fid in truncate:
        if fid not in file_ids:
            problems.append(f"Truncate: no file '{fid}' in this session")

    excl_files = set(_items(form["dose_exclude_files"]))
    try:
        excl_dose = {float(x) for x in _items(form["dose_exclude_dose"])}
    except ValueError:
        problems.append("Excluded doses must be numbers")
        excl_dose = set()

    values = dict(
        dose_dc=num("dose_dc", "Dose duty cycle", int, 0),
        detrend_sec=num("detrend_sec", "Detrend window (s)", float, 1),
        detrend_pct=num("detrend_pct", "Detrend percentile", int, 0),
        resp_dff=num("resp_dff", "Responder min ΔF/F₀", float, 0),
        resp_k=num("resp_k", "Responder k (× baseline SD)", float, 0),
        min_area=num("min_area", "Min cell area", int, 1),
        max_area=num("max_area", "Max cell area", int, 1))

    if problems:
        raise FormError(problems)

    try:
        return SessionConfig(
            name=name, data_dir=Path(data_dir),
            out_dir=results_dir(ws) / name, rois_dir=rois_dir(ws),
            file_ids=file_ids, protocol=protocol,
            experiment_type=etype, dye=dye, off_labels=off_labels,
            default_dc=default_dc, truncate_min=truncate,
            dose_unit=str(form["dose_unit"]),
            dose_label=str(form["dose_label"]),
            dose_log=bool(form["dose_log"]),
            dose_exclude_files=excl_files, dose_exclude_dose=excl_dose,
            detrend=bool(form["detrend"]), **values)
    except ValueError as e:                    # SessionConfig's own checks
        raise FormError([str(e)])


def form_from_config(cfg: SessionConfig) -> dict:
    """Inverse of :func:`build_config`, used when a session is opened."""
    return dict(
        name=cfg.name, data_dir=str(cfg.data_dir), dye=cfg.dye,
        experiment_type=cfg.experiment_type,
        file_ids=list(cfg.file_ids),
        protocols={fid: protocol_to_text(cfg.protocol.get(fid, []))
                   for fid in cfg.file_ids},
        off_labels=", ".join(sorted(cfg.off_labels)),
        default_dc=str(cfg.default_dc),
        dose_unit=cfg.dose_unit, dose_label=cfg.dose_label,
        dose_log=cfg.dose_log, dose_dc=str(cfg.dose_dc),
        dose_exclude_files=", ".join(sorted(cfg.dose_exclude_files)),
        dose_exclude_dose=", ".join(f"{d:g}" for d in sorted(cfg.dose_exclude_dose)),
        truncate=format_truncate(cfg.truncate_min),
        detrend=cfg.detrend, detrend_sec=f"{cfg.detrend_sec:g}",
        detrend_pct=str(cfg.detrend_pct),
        resp_dff=f"{cfg.resp_dff:g}", resp_k=f"{cfg.resp_k:g}",
        min_area=str(cfg.min_area), max_area=str(cfg.max_area))


# ------------------------------------------------------- form operations
def apply_scan(form: dict, scan) -> list[str]:
    """Fill dye and file ids from a ``ScanResult``; returns messages to show.

    Protocols of files that are still present are kept; new files start empty.
    """
    msgs = list(scan.warnings)
    if scan.dye is None:
        return msgs
    form["dye"] = scan.dye
    form["file_ids"] = list(scan.file_ids)
    form["protocols"] = {fid: form["protocols"].get(fid, "")
                         for fid in scan.file_ids}
    msgs.append(f"found {len(scan.file_ids)} file(s), dye: {scan.dye}")
    return msgs


def copy_protocol_to_all(form: dict, fid: str) -> None:
    """Give every file the same protocol text as ``fid``."""
    text = form["protocols"].get(fid, "")
    for other in form["file_ids"]:
        form["protocols"][other] = text
