"""Export per-cell ΔF/F0 traces to CSV (time + stimulation + one column/cell)."""
from __future__ import annotations

import csv

import numpy as np

from .metrics import t_to_frame


def stim_columns(t_s, eps):
    """Per-frame stimulation state from the ON epochs.

    Returns ``(label, dose, dc)`` arrays of length T. Frames outside any
    epoch are labelled "OFF" with dose/dc = 0.
    """
    T = len(t_s)
    label = np.array(["OFF"] * T, dtype=object)
    dose = np.zeros(T)
    dc = np.zeros(T, int)
    for (s, e, v, d, lab) in eps:
        i0 = t_to_frame(t_s, s * 60)
        i1 = max(t_to_frame(t_s, e * 60), i0 + 1)
        label[i0:i1] = lab
        dose[i0:i1] = v
        dc[i0:i1] = d
    return label, dose, dc


def write_cell_traces(path, fid, t_s, c_dff, eps):
    """Wide CSV: frame, time_s, time_min, stim_label, dose, dc, cell_001..N.

    Cell columns hold the (detrended) ΔF/F0 value for each ROI at each frame,
    plus a ``cell_mean`` column (mean across cells).
    """
    ncells, T = c_dff.shape if c_dff.ndim == 2 else (0, len(t_s))
    label, dose, dc = stim_columns(t_s, eps)
    cell_cols = [f"cell_{i + 1:03d}" for i in range(ncells)]
    header = (["frame", "time_s", "time_min", "stim_label", "dose", "dc"]
              + cell_cols + ["cell_mean"])
    mean = c_dff.mean(axis=0) if ncells else np.zeros(T)

    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for k in range(T):
            row = [k, round(float(t_s[k]), 3), round(float(t_s[k] / 60), 4),
                   label[k], round(float(dose[k]), 2), int(dc[k])]
            row += [round(float(c_dff[i, k]), 5) for i in range(ncells)]
            row.append(round(float(mean[k]), 5))
            w.writerow(row)
