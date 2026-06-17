"""Session 20260612 — HMC3 microglia, Calbryte / 10 mM CaCl2, 10X objective.

LIFUS PRF × duty-cycle matrix (not a voltage ramp). Each file is a single
6-min sonication: ON at min 2, OFF at min 8, recording STOP at min 10. The dose
variable is the pulse-repetition frequency (PRF), swept 1 / 10 / 100 / 1000 Hz
at three duty cycles. Protocol transcribed from ``20260612/Excels/Calcium_P2.xlsx``
(sheet GENERAL).

    File   PRF (Hz)   DC (%)        File   PRF (Hz)   DC (%)
    1      1          5             7      100        20
    2      10         5             8      1000       20
    3      100        5             9      1          40
    4      1000       5             10     10         40
    5      1          20            11     100        40
    6      10         20            12     1000       40

Labels encode "<PRF>Hz@DC<duty>"; the leading number is the dose. The
dose-response figures pool one duty cycle (``dose_dc``) and plot the PRF
sweep at that DC — set ``dose_dc`` to 5, 20 or 40 to switch curves. All 12
files appear regardless in the per-file figures and ``calcium_metrics.csv``.
"""
from pathlib import Path

from calcium.config import SessionConfig

ROOT = Path(__file__).resolve().parents[1]   # repo root (sessions/ lives here)

# Per file: one ON epoch from min 2 (LIFUS on) to min 8 (off); STOP at min 10.
_PRF = {"1": 1, "2": 10, "3": 100, "4": 1000,
        "5": 1, "6": 10, "7": 100, "8": 1000,
        "9": 1, "10": 10, "11": 100, "12": 1000}
_DC = {**{f: 5 for f in ("1", "2", "3", "4")},
       **{f: 20 for f in ("5", "6", "7", "8")},
       **{f: 40 for f in ("9", "10", "11", "12")}}

PROTOCOL = {
    fid: [(2, f"{_PRF[fid]}Hz@DC{_DC[fid]}"), (8, "STOP")]
    for fid in _PRF
}

CONFIG = SessionConfig(
    name="20260612",
    data_dir=ROOT / "20260612",
    out_dir=ROOT / "results" / "20260612",
    file_ids=[str(i) for i in range(1, 13)],
    protocol=PROTOCOL,
    dose_unit="Hz",
    dose_label="PRF (Hz)",
    dose_log=True,                   # PRF spans 1–1000 Hz: log-space the axis
    dose_dc=40,                      # dose-response curve uses the DC-40% files (9–12)
)
