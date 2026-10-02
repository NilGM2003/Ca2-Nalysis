"""Session 20261001 — HEK cells, Fura-2, ISO / Yoda1 (chemical stimulation).

Protocol: ISO at min 2, Yoda1 at min 4, ISO at min 6. Times are minutes;
"mm.ss" = mm min ss s. The loader finds 001_340.TIF and 001_380.TIF itself.
"""
from pathlib import Path

from calcium.config import SessionConfig

ROOT = Path(__file__).resolve().parents[1]   # repo root (sessions/ lives here)

PROTOCOL = {
    "001": [(2, "ISO"), (4, "Yoda1"), (6, "ISO")],
}

CONFIG = SessionConfig(
    name="20261001",
    data_dir=ROOT / "Calci" / "Hek Experiments",
    out_dir=ROOT / "results" / "20261001",
    file_ids=["001"],                  # NOT "001_340": the dye adds _340/_380
    protocol=PROTOCOL,                 # keys must match file_ids
    dye="fura2",
    experiment_type="chemical",
    off_labels={"STOP", "ISO"},      # uncomment if ISO is a wash/bath condition,
                                       # not an epoch to analyse
    # detrend=False,                   # the ratio mostly cancels photobleaching
    dose_label="Yoda1 (1:1000)",
)