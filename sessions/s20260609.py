"""Session 20260609 — HMC3 microglia, Calbryte / 10 mM CaCl2, 10X objective.

Stepped LIFUS dose-response (PRF 100 Hz, DC 40% unless noted). LIFUS is ON from
each voltage entry until the next "STOP". Protocol transcribed from
``20260609/Calci_P1.xlsx``. Times are minutes; "mm.ss" = mm min ss s.
"""
from pathlib import Path

from calcium.config import SessionConfig

ROOT = Path(__file__).resolve().parents[1]   # repo root (sessions/ lives here)

PROTOCOL = {
    "1": [(2, "0.5V"), (4, "STOP"), (6, "1.5V"), (8, "STOP"),
          (10, "3V"), (12, "STOP"), (16, "4.5V"), (17, "STOP")],
    "2": [(2, "2V"), (4, "STOP"), (6, "2.5V"), (8, "STOP"),
          (10, "3V"), (12, "STOP"), (13, "4.5V"), (15, "6V")],
    "3": [(2, "2V"), (4, "STOP"), (6, "2.5V"), (8, "STOP"),
          (10, "3V"), (12, "STOP"), (13, "6V"), (15, "STOP"),
          (17, "7.5V"), (18.30, "9V")],
    "4": [(2, "2V"), (4, "STOP"), (6, "2.5V"), (8, "STOP"),
          (10, "3V"), (12, "STOP"), (14, "4V"), (16, "STOP")],
    "5": [(2, "4V"), (4, "STOP"), (5.30, "6V"), (8, "STOP"), (12, "8V")],
    # Last two stimulations (8V@DC60 min28:30, 9V@DC60 min29:30) dropped per request.
    "6": [(2, "4V"), (5, "STOP"), (10, "6V"), (17, "STOP"), (19, "8V"), (27, "STOP")],
}

CONFIG = SessionConfig(
    name="20260609",
    data_dir=ROOT / "20260609",
    out_dir=ROOT / "results" / "20260609",
    file_ids=["1", "2", "3", "4", "5", "6"],
    protocol=PROTOCOL,
    truncate_min={"6": 27, "1": 15},          # crop File 6 at min 27 (drops DC-60% tail)
    dose_unit="V",
    dose_label="LIFUS amplitude (V)",
    # dose_exclude_files={"1"},        # File 1 = hyper-responder outlier
    dose_exclude_dose={9.0},         # 9V present in File 3 only (N=1)
)
