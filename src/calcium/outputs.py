"""Which result files a session can produce, and which ones it should.

Every figure or CSV has a key ``<name>.<format>``, e.g. ``dose_pooled.png`` or
``traces.csv``. A session's ``outputs`` setting is either ``None`` (everything
that applies to its experiment type, the default, so older sessions are
unchanged) or the set of keys to produce. The Results tab of the app edits it;
the pipeline asks :func:`wanted` before computing or writing each file.
"""
from __future__ import annotations

from dataclasses import dataclass

BOTH = ("lifu", "chemical")


@dataclass(frozen=True)
class OutputSpec:
    name: str                       # key prefix: "dose_pooled"
    label: str                      # shown in the app
    formats: tuple[str, ...]        # subset of ("png", "csv")
    experiments: tuple[str, ...]    # experiment types it applies to
    group: str                      # heading in the app
    note: str = ""                  # extra hint shown in the app

    def keys(self) -> list[str]:
        return [f"{self.name}.{fmt}" for fmt in self.formats]


# Order = order in the app.
OUTPUTS: list[OutputSpec] = [
    OutputSpec("wholefield", "Whole-field ΔF/F₀ trace", ("png",), BOTH,
               "Per file"),
    OutputSpec("cells", "ROI overlay + per-cell heatmap", ("png",), BOTH,
               "Per file"),
    OutputSpec("celltraces", "All cell traces + mean", ("png",), BOTH,
               "Per file"),
    OutputSpec("traces", "Per-cell traces", ("csv",), BOTH, "Per file",
               note="needed by View traces"),
    OutputSpec("metrics", "Per-epoch metrics (calcium_metrics)", ("csv",),
               BOTH, "Whole session"),
    OutputSpec("condition_summary", "Per-condition summary", ("csv",),
               ("chemical",), "Whole session"),
    OutputSpec("dose_pooled", "Dose-response, cells pooled", ("png", "csv"),
               ("lifu",), "Dose-response"),
    OutputSpec("dose_byfile", "Dose-response, file as replicate",
               ("png", "csv"), ("lifu",), "Dose-response"),
    OutputSpec("by_dc", "Response and recruitment by duty cycle",
               ("png", "csv"), ("lifu",), "Dose-response",
               note="only if the session has more than one duty cycle"),
    OutputSpec("latency", "Responder latency, cells pooled", ("png", "csv"),
               ("lifu",), "Latency"),
    OutputSpec("latency_byfile", "Responder latency, per file",
               ("png", "csv"), ("lifu",), "Latency"),
]


def specs_for(experiment_type: str) -> list[OutputSpec]:
    """The outputs that exist for this experiment type, in display order."""
    return [s for s in OUTPUTS if experiment_type in s.experiments]


def all_keys() -> set[str]:
    return {k for s in OUTPUTS for k in s.keys()}


def applicable_keys(experiment_type: str) -> set[str]:
    return {k for s in specs_for(experiment_type) for k in s.keys()}


def wanted(cfg, key: str) -> bool:
    """Should this session produce ``key``?

    False for keys that do not apply to its experiment type (a chemical
    session never makes dose-response figures); otherwise True when
    ``cfg.outputs`` is None (everything) or contains the key.
    """
    if key not in applicable_keys(cfg.experiment_type):
        return False
    return cfg.outputs is None or key in cfg.outputs


def wants_any(cfg, *keys: str) -> bool:
    return any(wanted(cfg, k) for k in keys)
