"""Session 20260623 — HMC3 microglia, Calbryte / 10 mM CaCl2, 10X objective.

LIFUS PRF x duty-cycle matrix. Each file contains a single 6-min sonication:
ON at min 2, OFF at min 8, recording STOP at min 10.

    File   PRF (Hz)   DC (%)
    1      1          20
    2      10         20
    4      1000       20
    6      10         40
    9      100        20
    10     100        40

Labels encode "<PRF>Hz@DC<duty>"; the leading number is the dose. The
dose-response figures pool one duty cycle (``dose_dc``) and plot the PRF
sweep at that DC. All files appear in the per-file figures and
``calcium_metrics.csv``.
"""

from pathlib import Path

from calcium.config import SessionConfig

ROOT = Path(__file__).resolve().parents[1]

_PRF = {
    "1": 1,
    "2": 10,
    "4": 1000,
    "6": 10,
    "9": 100,
    "10": 100,
}

_DC = {
    "1": 20,
    "2": 20,
    "4": 20,
    "6": 40,
    "9": 20,
    "10": 40,
}

PROTOCOL = {
    fid: [(2, f"{_PRF[fid]}Hz@DC{_DC[fid]}"), (8, "STOP")]
    for fid in _PRF
}

CONFIG = SessionConfig(
    name="20260623",
    data_dir=ROOT / "20260623",
    out_dir=ROOT / "results" / "20260623",
    file_ids=["1", "2", "4", "6", "9", "10"],
    protocol=PROTOCOL,
    dose_unit="Hz",
    dose_label="PRF (Hz)",
    dose_log=True,
    dose_dc=20,
)