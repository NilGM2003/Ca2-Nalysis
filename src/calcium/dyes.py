"""Calcium dyes: which TIF file(s) a recording has and how to get a signal."""
from __future__ import annotations

import sys
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

    def paths(self, data_dir: Path, fid: str, prefix: str = "") -> list[Path]:
        """The TIF file(s) of recording ``fid`` (file name = prefix + fid)."""
        stem = f"{prefix}{fid}"
        if not self.channels:
            return [find_tif(data_dir, stem)]
        return [find_tif(data_dir, f"{stem}_{c}") for c in self.channels]


# To support another dye, add one line here.
DYES = {
    "calbryte": DyeSpec("calbryte"),                                  # <fid>.TIF
    "fura2": DyeSpec("fura2", channels=("340", "380"), ratiometric=True),
}


def _drop_untimed_frames(frames, t_s, name: str):
    """Drop trailing frames that have no timestamp (time 0).

    When an acquisition is stopped early the file can end with frames whose
    timing tag is empty. Their time is 0, which would make the recording look
    zero minutes long, so they are cut off (with a warning).
    """
    n = len(t_s)
    positive = np.flatnonzero(t_s > 0)
    if positive.size == 0:
        raise ValueError(f"{name}: no frame has a timestamp, so there is no "
                         f"time axis (is this an AQUACOSMOS file?)")
    n_valid = int(positive[-1]) + 1
    bad = np.flatnonzero(np.diff(t_s[:n_valid]) <= 0)
    if bad.size:
        raise ValueError(f"{name}: frame times do not increase (first problem "
                         f"at frame {int(bad[0]) + 1}); the file may be damaged")
    if n_valid < n:
        print(f"warning: {name}: the last {n - n_valid} of {n} frame(s) have "
              f"no timestamp (acquisition stopped early?) and were dropped",
              file=sys.stderr)
    return frames[:n_valid], t_s[:n_valid]


def _align_channels(stacks, dye: "DyeSpec", fid: str):
    """Give all channels of a recording the same number of frames.

    Channels are acquired alternately (340, 380, 340, ...), so if the run was
    stopped after a 340 frame, that channel has one frame more. A difference
    of one frame is trimmed; a larger one means something is wrong.
    """
    if len(stacks) < 2:
        return stacks
    shapes = [f.shape[1:] for f, _ in stacks]
    if len(set(shapes)) > 1:
        raise ValueError(f"{fid}: the {' and '.join(dye.channels)} images "
                         f"differ in size {shapes}")
    counts = [len(t) for _, t in stacks]
    n = min(counts)
    if max(counts) - n > 1:
        raise ValueError(
            f"{fid}: the channels have very different numbers of timed "
            f"frames ({dict(zip(dye.channels, counts))}); check that the "
            f"{' and '.join(dye.channels)} files belong to the same recording")
    if max(counts) != n:
        print(f"warning: {fid}: channels have {counts} frames; using the "
              f"first {n} of each", file=sys.stderr)
    return [(f[:n], t[:n]) for f, t in stacks]


def session_paths(cfg, fid: str) -> list[Path]:
    """Where the TIF file(s) of ``fid`` are expected for this session."""
    return DYES[cfg.dye].paths(cfg.data_dir, fid, cfg.file_prefix)


def load_session_recording(cfg, fid: str):
    """:func:`load_recording` with everything taken from the session config
    (dye, data folder, file-name prefix, truncation)."""
    return load_recording(DYES[cfg.dye], cfg.data_dir, fid,
                          cfg.truncate_min.get(fid), cfg.file_prefix)


def load_recording(dye: DyeSpec, data_dir: Path, fid: str, max_min=None,
                   prefix: str = ""):
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
    paths = dye.paths(data_dir, fid, prefix)
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"dye '{dye.name}' expects these file(s) for id '{fid}': "
            f"{[p.name for p in paths]}; not found in {data_dir}: {missing}")

    stacks = [_drop_untimed_frames(*load_tif(p), name=p.name) for p in paths]
    stacks = _align_channels(stacks, dye, fid)

    if max_min is not None:
        # one mask from the first channel's times, so channels stay aligned
        keep = (stacks[0][1] / 60.0) <= max_min
        stacks = [(f[keep], t[keep]) for f, t in stacks]

    if not dye.ratiometric:
        frames, t_s = stacks[0]
        return (frames,), frames, frames.mean(axis=(1, 2)), t_s

    (num, t_s), (den, _) = stacks
    wf = num.mean(axis=(1, 2)) / np.maximum(den.mean(axis=(1, 2)), 1.0)
    return (num, den), den, wf, t_s
