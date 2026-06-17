"""Loading TIF stacks and per-frame timing."""
from __future__ import annotations

import numpy as np
import tifffile


def load_tif(path):
    """Return ``(frames [T,H,W] float32, t_s [T])``.

    Per-frame elapsed time comes from the AQUACOSMOS ``Software`` tag, whose
    third comma-separated field is the elapsed acquisition time in ms. This is
    the real cadence (~3.5 s/frame here), so we never assume a constant rate.
    """
    tf = tifffile.TiffFile(str(path))
    t_ms = [float(p.tags["Software"].value.split(",")[2]) for p in tf.pages]
    frames = tf.asarray().astype(np.float32)
    return frames, np.asarray(t_ms) / 1000.0


def truncate(frames, t_s, max_min):
    """Crop a recording to frames with elapsed time <= ``max_min`` minutes."""
    keep = (t_s / 60.0) <= max_min
    return frames[keep], t_s[keep]
