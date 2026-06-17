"""Session configuration schema."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# A protocol is, per file id, a list of (time_minutes, label) events.
# Labels are a dose value with a unit ("4.5V", "8V@DC60", "100Hz@DC20") or
# "STOP". The leading number is the dose (volts, PRF in Hz, ...); an optional
# "@DC" suffix overrides the duty cycle. "mm.ss" times (e.g. 18.30 = 18 min
# 30 s) are accepted; a LIFUS epoch runs from each dose entry to the next event
# (STOP, next dose, or recording end).
Protocol = dict[str, list[tuple[float, str]]]


@dataclass
class SessionConfig:
    """Everything needed to analyse one imaging session."""

    name: str
    data_dir: Path
    out_dir: Path
    file_ids: list[str]
    protocol: Protocol

    # acquisition / preprocessing
    default_dc: int = 40                       # duty cycle (%) unless label says otherwise
    truncate_min: dict[str, float] = field(default_factory=dict)

    # cell segmentation (pixels)
    min_area: int = 15
    max_area: int = 4000

    # dF/F0 photobleach detrending
    detrend: bool = True
    detrend_sec: float = 200.0                 # rolling-window length for F0(t)
    detrend_pct: int = 20                      # percentile used as slow baseline

    # responder criterion: peak dF/F0 > max(resp_k * baseline_SD, resp_dff)
    resp_dff: float = 0.10
    resp_k: float = 3.0

    # dose-response curve construction (per-file figures are unaffected)
    dose_unit: str = "V"                       # dose unit, e.g. "V" or "Hz"
    dose_label: str = "LIFUS amplitude (V)"    # x-axis label for dose figures
    dose_log: bool = False                     # log-space the dose axis (e.g. PRF)
    dose_dc: int = 40                          # only pool epochs at this duty cycle
    dose_exclude_files: set[str] = field(default_factory=set)
    dose_exclude_dose: set[float] = field(default_factory=set)
