"""Parsing the acquisition protocol into stimulation epochs."""
from __future__ import annotations
import math
import re

_LEADING_NUM = re.compile(r"[-+]?\d*\.?\d+")
_NAMED_DOSE = re.compile(r"^[A-Za-z][\w-]*[@\s]+\s*([-+]?\d*\.?\d+)")


def mmss(x):
    """'mm.ss' -> decimal minutes (18.30 -> 18.5, the '.30' meaning 30 s)."""
    m = int(x)
    s = round((x - m) * 100)
    return m + s / 60.0


def parse_dose(label, default_dc=40):
    """Parse a dose label into ``(dose_value, dc)``.

    Sonication labels: the leading number is the dose.
    ``'4.5V' -> (4.5, 40)``, ``'100Hz@DC20' -> (100.0, 20)``.

    Chemical labels (start with a name): an optional number after the name is
    the dose, otherwise the dose is NaN.
    ``'Yoda1@10uM' -> (10.0, dc)``, ``'Yoda1' -> (nan, dc)``, ``'ISO' -> (nan, dc)``.

    An optional ``@DC`` suffix overrides the duty cycle (sonication only).
    """
    dc = default_dc
    if "@DC" in label:
        label, dcpart = label.split("@DC")
        dc = int(dcpart)
    label = label.strip()

    m = _LEADING_NUM.match(label)
    if m:
        return float(m.group()), dc

    m = _NAMED_DOSE.match(label)
    if m:
        return float(m.group(1)), dc

    if label:                              # a name with no dose, e.g. "ISO", "Yoda1"
        return math.nan, dc
    raise ValueError("empty dose label")


def build_epochs(events, t_end_min, default_dc=40, off_labels=("STOP",)):
    """Convert (time, label) events into ON epochs.

    Returns a list of ``(start_min, end_min, dose, dc, label)``. Each epoch
    runs from an entry to the next event (an off label, the next entry, or the
    end of the recording). Labels in ``off_labels`` (default just "STOP") end
    the previous epoch but do not start one of their own. Epochs starting
    at/after ``t_end_min`` (e.g. cut off by truncation) are dropped, and epoch
    ends are clamped to ``t_end_min``.
    """
    ev = [(mmss(t), lab) for t, lab in events]
    out = []
    for i, (t, lab) in enumerate(ev):
        if lab in off_labels or t >= t_end_min:
            continue
        end = ev[i + 1][0] if i + 1 < len(ev) else t_end_min
        end = min(end, t_end_min)
        dose, dc = parse_dose(lab, default_dc)
        out.append((t, end, dose, dc, lab))
    return out