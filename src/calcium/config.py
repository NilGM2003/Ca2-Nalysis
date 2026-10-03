"""Session configuration schema."""
from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields
from pathlib import Path

from .dyes import DYES

# A protocol is, per file id, a list of (time_minutes, label) events.
# Labels are either a numeric dose with a unit ("4.5V", "8V@DC60",
# "100Hz@DC20"), or a condition name ("Yoda1", "ISO", optionally with a dose
# such as "Yoda1@10uM"), or an "off" label such as "STOP". For numeric labels
# the leading number is the dose (volts, PRF in Hz, ...); an optional "@DC"
# suffix overrides the duty cycle. "mm.ss" times (e.g. 18.30 = 18 min 30 s)
# are accepted; an epoch runs from each entry to the next event (STOP, next
# label, or recording end).
Protocol = dict[str, list[tuple[float, str]]]

EXPERIMENT_TYPES = ("lifu", "chemical")


@dataclass
class SessionConfig:
    """Everything needed to analyse one imaging session."""

    name: str
    data_dir: Path
    out_dir: Path
    file_ids: list[str]
    protocol: Protocol

    # Folder holding the hand-corrected ROI masks (<name>_<fid>.npy).
    # None = legacy location, <repo>/rois (sessions created before workspaces).
    rois_dir: Path | None = None

    # What kind of experiment this is; decides which summary outputs are made.
    #   "lifu":     numeric dose (V, PRF...) + duty cycle -> dose-response figures
    #   "chemical": named conditions (ISO, Yoda1...)      -> per-condition summary
    experiment_type: str = "lifu"

    # Calcium dye: decides which TIF file(s) are loaded per file id.
    #   "calbryte": <fid>.TIF            (single channel, F/F0)
    #   "fura2":    <fid>_340.TIF and <fid>_380.TIF  (ratio F340/F380)
    # More dyes can be added in dyes.py (DYES).
    dye: str = "calbryte"

    # Protocol labels that end an epoch without starting a new one.
    # NOTE: not yet read by build_epochs (protocol.py); wire it in there.
    off_labels: set[str] = field(default_factory=lambda: {"STOP"})

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

    # dose-response curve construction (LIFU only; per-file figures are unaffected)
    dose_unit: str = "V"                       # dose unit, e.g. "V" or "Hz"
    dose_label: str = "LIFUS amplitude (V)"    # x-axis label for dose figures
    dose_log: bool = False                     # log-space the dose axis (e.g. PRF)
    dose_dc: int = 40                          # only pool epochs at this duty cycle
    dose_exclude_files: set[str] = field(default_factory=set)
    dose_exclude_dose: set[float] = field(default_factory=set)

    def __post_init__(self):
        if self.experiment_type not in EXPERIMENT_TYPES:
            raise ValueError(
                f"experiment_type must be one of {EXPERIMENT_TYPES}, "
                f"got {self.experiment_type!r}")
        if self.dye not in DYES:
            raise ValueError(
                f"dye must be one of {sorted(DYES)}, got {self.dye!r}")
        missing = [f for f in self.file_ids if f not in self.protocol]
        if missing:
            raise ValueError(
                f"session {self.name}: no protocol entry for file id(s) "
                f"{missing}; protocol keys are {sorted(self.protocol)}")

    # ---------------------------------------------------------------- JSON
    def to_dict(self) -> dict:
        """JSON-safe dict of every setting (paths as str, sets as sorted lists)."""
        out = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, Path):
                v = str(v)
            elif f.name == "protocol":
                v = {fid: [[t, lab] for t, lab in evs] for fid, evs in v.items()}
            elif isinstance(v, (set, frozenset)):
                v = sorted(v)
            elif isinstance(v, dict):
                v = dict(v)
            elif isinstance(v, (list, tuple)):
                v = list(v)
            out[f.name] = v
        return out

    @classmethod
    def from_dict(cls, d: dict) -> "SessionConfig":
        """Inverse of :meth:`to_dict`. Raises ValueError with a clear message."""
        known = {f.name: f for f in fields(cls)}
        unknown = sorted(set(d) - set(known))
        if unknown:
            raise ValueError(f"unknown setting(s): {unknown}")
        required = [n for n, f in known.items()
                    if f.default is MISSING and f.default_factory is MISSING]
        missing = [n for n in required if n not in d]
        if missing:
            raise ValueError(f"missing required setting(s): {missing}")

        kw = dict(d)
        for k in ("data_dir", "out_dir", "rois_dir"):
            if kw.get(k) is not None:
                kw[k] = Path(kw[k])
        kw["protocol"] = {str(fid): [(t, str(lab)) for t, lab in evs]
                          for fid, evs in kw["protocol"].items()}
        kw["file_ids"] = [str(f) for f in kw["file_ids"]]
        for k in ("off_labels", "dose_exclude_files", "dose_exclude_dose"):
            if k in kw:
                kw[k] = set(kw[k])
        if "truncate_min" in kw:
            kw["truncate_min"] = {str(k): v for k, v in kw["truncate_min"].items()}
        return cls(**kw)
