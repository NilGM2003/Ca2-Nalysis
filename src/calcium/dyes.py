"""Calcium dyes: which TIF file(s) a recording has and how to get a signal."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .io import load_tif

TIF_SUFFIXES = (".tif", ".tiff")


def find_tif(data_dir: Path, stem: str) -> Path:
    """Path of ``<stem>.tif`` in ``data_dir``, ignoring case and .tif/.tiff.

    Falls back to ``<stem>.TIF`` when nothing matches, so the "file not found"
    error names the file the microscope normally writes.
    """
    data_dir = Path(data_dir)
    want = stem.lower()
    try:
        for p in sorted(data_dir.iterdir()):
            if (p.is_file() and not p.name.startswith(".")
                    and p.suffix.lower() in TIF_SUFFIXES
                    and p.stem.lower() == want):
                return p
    except OSError:
        pass
    return data_dir / f"{stem}.TIF"


@dataclass(frozen=True)
class DyeSpec:
    name: str
    # Filename suffixes, in (numerator, denominator) order for ratiometric
    # dyes. Empty tuple = a single file named "<fid>.TIF".
    channels: tuple[str, ...] = ()
    ratiometric: bool = False

    def paths(self, data_dir: Path, fid: str) -> list[Path]:
        if not self.channels:
            return [find_tif(data_dir, fid)]
        return [find_tif(data_dir, f"{fid}_{c}") for c in self.channels]


# To support another dye, add one line here.
DYES = {
    "calbryte": DyeSpec("calbryte"),                                  # <fid>.TIF
    "fura2": DyeSpec("fura2", channels=("340", "380"), ratiometric=True),
}


def load_recording(dye: DyeSpec, data_dir: Path, fid: str, max_min=None):
    """Load one recording and return ``(stacks, seg_img, wf, t_s)``.

    stacks   tuple   ``(frames,)`` for single-channel dyes, or
                     ``(numerator, denominator)`` = ``(F340, F380)`` for
                     Fura-2; ROI traces are built from these (see
                     ``segmentation.roi_signal_traces``)
    seg_img  [T,H,W] stack used for cell segmentation and the projection image
                     (F380 for Fura-2: bright, stable, cell-shaped)
    wf       [T]     whole-field trace (ratio of the channel means for Fura-2)
    t_s      [T]     per-frame time in seconds (taken from the first file)
    """
    paths = dye.paths(data_dir, fid)
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"dye '{dye.name}' expects these file(s) for id '{fid}': "
            f"{[p.name for p in paths]}; not found in {data_dir}: {missing}")

    stacks = [load_tif(p) for p in paths]

    if max_min is not None:
        cropped = []
        for frames, t_s in stacks:
            keep = (t_s / 60.0) <= max_min
            cropped.append((frames[keep], t_s[keep]))
        stacks = cropped

    if not dye.ratiometric:
        frames, t_s = stacks[0]
        return (frames,), frames, frames.mean(axis=(1, 2)), t_s

    (num, t_s), (den, _) = stacks
    if num.shape != den.shape:
        raise ValueError(
            f"{fid}: {dye.channels[0]} stack {num.shape} and "
            f"{dye.channels[1]} stack {den.shape} differ in shape")
    wf = num.mean(axis=(1, 2)) / np.maximum(den.mean(axis=(1, 2)), 1.0)
    return (num, den), den, wf, t_s
