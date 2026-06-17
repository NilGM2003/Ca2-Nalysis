"""dF/F0 computation with photobleach detrending."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import percentile_filter


def baseline_f0(traces, win, pct=20):
    """Slowly varying F0(t) via a rolling low-percentile filter.

    Tracks photobleach decay but stays below calcium transients. Accepts a 1D
    trace ``[T]`` or a 2D stack ``[n_cells, T]`` (filtered along time only).
    """
    win = max(5, win | 1)  # force odd, >= 5
    if traces.ndim == 1:
        return percentile_filter(traces, pct, size=win, mode="nearest")
    return percentile_filter(traces, pct, size=(1, win), mode="nearest")


def compute_dff(traces, t_s, base_mask, detrend=True, detrend_sec=200.0, pct=20):
    """dF/F0 for a 1D trace or 2D ``[n_cells, T]`` stack.

    With ``detrend`` the baseline is a time-varying F0(t) (removes bleaching);
    otherwise it is the static mean over ``base_mask`` (the pre-stim window).
    """
    win = int(round(detrend_sec / np.median(np.diff(t_s))))
    if detrend:
        f0 = baseline_f0(traces, win, pct)
    elif traces.ndim == 1:
        f0 = np.full_like(traces, traces[base_mask].mean())
    else:
        f0 = np.broadcast_to(traces[:, base_mask].mean(axis=1, keepdims=True),
                             traces.shape)
    return (traces - f0) / np.maximum(f0, 1e-6)
