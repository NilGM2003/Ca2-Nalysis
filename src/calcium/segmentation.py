"""Cell ROI segmentation and trace extraction."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from skimage.filters import gaussian, threshold_otsu
from skimage.measure import label, regionprops
from skimage.morphology import binary_opening

# Repo root = two levels above src/calcium/ (independent of where the raw data
# lives, so sessions with data_dir outside the repo root still find rois/).
REPO_ROOT = Path(__file__).resolve().parents[2]


def segment_cells(frames, min_area=1, max_area=4000):
    """Otsu on the temporal-mean projection -> labelled ROIs.

    Returns ``(labels [H,W] int, proj [H,W])`` where ``labels`` is 0 for
    background and 1..n for cells passing the area filter.
    """
    proj = frames.mean(axis=0)
    sm = gaussian(proj, sigma=1.5, preserve_range=True)
    thresh = threshold_otsu(sm)
    mask = binary_opening(sm > thresh)
    lbl = label(mask)
    keep = np.zeros_like(lbl)
    n = 0
    for r in regionprops(lbl):
        if min_area <= r.area <= max_area:
            n += 1
            keep[lbl == r.label] = n
    return keep, proj


def compact_labels(labels):
    """Renumber labels to a gapless 1..n (0 stays background)."""
    out = np.zeros_like(labels)
    for i, lab in enumerate(sorted(int(u) for u in np.unique(labels) if u > 0), 1):
        out[labels == lab] = i
    return out


def manual_roi_path(cfg, fid) -> Path:
    """Where the hand-corrected ROI mask for ``fid`` lives (one .npy per file).

    Sessions created in the app carry ``cfg.rois_dir`` (inside the user's
    workspace). Older sessions have ``rois_dir=None`` and keep using ``rois/``
    at the repo root. The name is a flat ``<session>_<fid>.npy`` (a
    per-session subdir would be caught by the ``2026*/`` gitignore).
    """
    base = Path(cfg.rois_dir) if cfg.rois_dir else REPO_ROOT / "rois"
    return base / f"{cfg.name}_{fid}.npy"


def load_or_segment(cfg, frames, fid):
    """Manual ROI mask if one exists for ``fid``, else auto Otsu segmentation.

    ``frames`` is the stack used for segmentation and the projection image
    (the F380 stack for Fura-2). Returns ``(labels [H,W] int, proj [H,W])``.
    Manual masks are used verbatim (no area filter) so hand-drawn ROIs are
    never silently dropped.
    """
    proj = frames.mean(axis=0)
    path = manual_roi_path(cfg, fid)
    if path.exists():
        labels = np.load(path)
        if labels.shape != frames.shape[1:]:
            raise ValueError(
                f"manual ROI mask {path} is {labels.shape} but frames are "
                f"{frames.shape[1:]}. Re-edit ROIs for session {cfg.name} "
                f"file {fid}.")
        return compact_labels(labels), proj
    return segment_cells(frames, cfg.min_area, cfg.max_area)


def roi_traces(frames, labels):
    """Mean fluorescence trace per ROI -> ``[n_cells, T]``."""
    n = int(labels.max())
    T = frames.shape[0]
    traces = np.zeros((n, T), np.float32)
    flat = labels.ravel()
    fr = frames.reshape(T, -1)
    for c in range(1, n + 1):
        traces[c - 1] = fr[:, flat == c].mean(axis=1)
    return traces


def roi_signal_traces(stacks, labels):
    """Per-ROI signal trace -> ``[n_cells, T]``.

    ``stacks`` is ``(frames,)`` for a single-channel dye (plain ROI mean) or
    ``(numerator, denominator)`` for a ratiometric dye. For the ratio, each
    channel is averaged over the ROI first and the means are divided
    (F340_mean / F380_mean), which is less noisy and less biased than
    averaging per-pixel ratios.
    """
    if len(stacks) == 1:
        return roi_traces(stacks[0], labels)
    num = roi_traces(stacks[0], labels)
    den = roi_traces(stacks[1], labels)
    return num / np.maximum(den, 1.0)
