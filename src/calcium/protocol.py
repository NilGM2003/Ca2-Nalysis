"""Parsing the acquisition protocol into LIFUS epochs."""
from __future__ import annotations

import re

_LEADING_NUM = re.compile(r"[-+]?\d*\.?\d+")


def mmss(x):
    """'mm.ss' -> decimal minutes (18.30 -> 18.5, the '.30' meaning 30 s)."""
    m = int(x)
    s = round((x - m) * 100)
    return m + s / 60.0


def parse_dose(label, default_dc=40):
    """Parse a dose label into ``(dose_value, dc)``.

    The leading number is the dose, regardless of its unit suffix:
    ``'4.5V' -> (4.5, 40)``, ``'8V@DC60' -> (8.0, 60)``,
    ``'100Hz@DC20' -> (100.0, 20)``. An optional ``@DC`` suffix overrides the
    duty cycle.
    """
    dc = default_dc
    if "@DC" in label:
        label, dcpart = label.split("@DC")
        dc = int(dcpart)
    m = _LEADING_NUM.match(label.strip())
    if not m:
        raise ValueError(f"cannot parse dose from label {label!r}")
    return float(m.group()), dc


def build_epochs(events, t_end_min, default_dc=40):
    """Convert (time, label) events into ON epochs.

    Returns a list of ``(start_min, end_min, dose, dc, label)``. Each epoch
    runs from a dose entry to the next event (STOP, next dose, or the end of
    the recording). Epochs starting at/after ``t_end_min`` (e.g. cut off by
    truncation) are dropped, and epoch ends are clamped to ``t_end_min``.
    """
    ev = [(mmss(t), lab) for t, lab in events]
    out = []
    for i, (t, lab) in enumerate(ev):
        if lab == "STOP" or t >= t_end_min:
            continue
        end = ev[i + 1][0] if i + 1 < len(ev) else t_end_min
        end = min(end, t_end_min)
        dose, dc = parse_dose(lab, default_dc)
        out.append((t, end, dose, dc, lab))
    return out
