from pathlib import Path

from calcium.config import SessionConfig

ROOT = Path(__file__).resolve().parents[1]

PROTOCOL = {
    "1":  [(2, "1Hz@DC20"),    (8, "STOP")],
    "2":  [(2, "10Hz@DC20"),   (8, "STOP")],
    "3":  [(2, "100Hz@DC20"),   (8, "STOP")],
    "4":  [(2, "1000Hz@DC20"), (8, "STOP")],
    "5":  [(2, "1Hz@DC40"),   (8, "STOP")],
    "6":  [(2, "10Hz@DC40"),   (8, "STOP")],
    "7":  [(2, "100Hz@DC40"),   (8, "STOP")],
    "8":  [(2, "1000Hz@DC40"),   (8, "STOP")],
    "9":  [(2, "100Hz@DC20"),  (8, "STOP")],
    "10": [(2, "100Hz@DC40"),  (8, "STOP")],
}

CONFIG = SessionConfig(
    name="20260623",
    data_dir=ROOT / "20260623",
    out_dir=ROOT / "results" / "20260623",
    file_ids=["1", "2", "3", "4","5", "6", "7", "8", "9", "10"],
    protocol=PROTOCOL,
    dose_unit="Hz",
    dose_label="PRF (Hz)",
    dose_log=True,
    dose_dc=20,
)