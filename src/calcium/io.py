"""Loading TIF stacks and per-frame timing."""
from __future__ import annotations

import numpy as np
import tifffile


def load_tif(path, dt_s=None):
    """Return ``(frames [T,H,W] float32, t_s [T])``.
    
    Per-frame elapsed time comes from the AQUACOSMOS ``Software`` tag, whose
    third comma-separated field is the elapsed acquisition time in ms. This is
    the real cadence (~3.5 s/frame here), so we never assume a constant rate.
    """
    tf = tifffile.TiffFile(str(path))
    frames = tf.asarray().astype(np.float32)
    try:
        t_ms = [float(p.tags["Software"].value.split(",")[2]) for p in tf.pages]
        t_s = np.asarray(t_ms) / 1000.0
    except (KeyError, IndexError, ValueError):
        if dt_s is None:
            raise ValueError(
                f"{path}: no AQUACOSMOS timing tag; pass dt_s (seconds/frame)"
            )
        t_s = np.arange(frames.shape[0]) * dt_s
    return frames, t_s


def truncate(frames, t_s, max_min):
    """Crop a recording to frames with elapsed time <= ``max_min`` minutes."""
    keep = (t_s / 60.0) <= max_min
    return frames[keep], t_s[keep]
