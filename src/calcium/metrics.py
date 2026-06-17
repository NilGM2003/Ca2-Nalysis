"""Per-epoch and per-cell response metrics."""
from __future__ import annotations

import numpy as np
from scipy.integrate import trapezoid


def t_to_frame(t_s, sec):
    return int(np.searchsorted(t_s, sec))


def _first_crossing(seg, thr, t_seg, onset_s):
    """Latency (s from ``onset_s``) of the first frame of ``seg`` above ``thr``.

    ``seg`` is 1D ``[T]``; returns ``np.nan`` if the trace never crosses ``thr``.
    """
    above = seg > thr
    if not above.any():
        return np.nan
    return float(t_seg[above.argmax()] - onset_s)


def epoch_metrics(fid, eps, t_s, wf_dff, c_dff, c_base_sd, ncells,
                  resp_dff, resp_k, wf_base_sd=0.0):
    """Compute whole-field + per-cell responder metrics for each epoch.

    Latency metrics are measured in seconds from stimulation onset (the epoch
    start time): *onset latency* is when the trace first crosses the responder
    threshold; *time-to-peak* is when it reaches its maximum. Per-cell latencies
    are reported only for responders.

    Returns ``(epoch_rows, cell_rows)`` where ``epoch_rows`` is one dict per
    epoch (for the metrics CSV) and ``cell_rows`` is one dict per cell-epoch
    (pooled for the dose-response).
    """
    epoch_rows, cell_rows = [], []
    for (s, e, dose, dc, lab) in eps:
        i0 = t_to_frame(t_s, s * 60)
        i1 = max(t_to_frame(t_s, e * 60), i0 + 1)
        seg = wf_dff[i0:i1]
        t_seg = t_s[i0:i1]
        onset_s = s * 60.0

        # whole-field latency: onset (threshold crossing) + time-to-peak
        wf_thr = max(resp_k * wf_base_sd, resp_dff)
        wf_onset_s = _first_crossing(seg, wf_thr, t_seg, onset_s)
        wf_peak_s = float(t_seg[seg.argmax()] - onset_s)

        if ncells:
            c_seg = c_dff[:, i0:i1]
            c_peak = c_seg.max(axis=1)
            c_auc = trapezoid(np.maximum(c_seg, 0), t_seg, axis=1)
            thr = np.maximum(resp_k * c_base_sd, resp_dff)
            responders = c_peak > thr
            # per-cell latencies (frames -> seconds from onset)
            onset_lat = t_seg[(c_seg > thr[:, None]).argmax(axis=1)] - onset_s
            peak_lat = t_seg[c_seg.argmax(axis=1)] - onset_s
        else:
            c_peak = c_auc = np.array([])
            responders = np.array([], bool)
            onset_lat = peak_lat = np.array([])

        r_onset = onset_lat[responders]
        r_peak = peak_lat[responders]
        epoch_rows.append(dict(
            file=fid, label=lab, dose=dose, dc=dc,
            t_start_min=round(s, 2), t_end_min=round(e, 2),
            dur_min=round(e - s, 2), n_cells=ncells,
            wf_peak_dff=round(float(seg.max()), 4),
            wf_mean_dff=round(float(seg.mean()), 4),
            wf_auc=round(float(trapezoid(np.maximum(seg, 0), t_seg)), 3),
            wf_onset_lat_s=round(wf_onset_s, 2) if np.isfinite(wf_onset_s) else "",
            wf_t_to_peak_s=round(wf_peak_s, 2),
            n_responders=int(responders.sum()),
            frac_responding=round(float(responders.mean()) if ncells else 0.0, 3),
            mean_responder_peak_dff=round(
                float(c_peak[responders].mean()) if responders.any() else 0.0, 4),
            mean_responder_onset_lat_s=round(float(r_onset.mean()), 2)
                if responders.any() else "",
            mean_responder_t_to_peak_s=round(float(r_peak.mean()), 2)
                if responders.any() else "",
        ))
        for cp, ca, rb, ol, pl in zip(c_peak, c_auc, responders, onset_lat, peak_lat):
            cell_rows.append(dict(
                file=fid, dose=dose, dc=dc, peak_dff=float(cp), auc=float(ca),
                responder=bool(rb),
                onset_lat_s=float(ol) if rb else np.nan,
                t_to_peak_s=float(pl) if rb else np.nan))
    return epoch_rows, cell_rows
