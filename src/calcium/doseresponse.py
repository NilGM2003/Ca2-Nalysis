"""Pooled and per-file (file-as-replicate) dose-response aggregation."""
from __future__ import annotations

import numpy as np


def pooled_stats(cell_records, exclude_files, exclude_doses, dc=40):
    """Pool single cells across files, grouped by dose.

    Returns ``(pooled_records, rows)``. ``rows`` has, per dose, the mean /
    SEM / median single-cell peak dF/F0 and the responding fraction.
    """
    pooled = [r for r in cell_records
              if r["dc"] == dc
              and r["file"] not in exclude_files
              and r["dose"] not in exclude_doses]
    doses = sorted({r["dose"] for r in pooled})
    rows = []
    for d in doses:
        cells = [r for r in pooled if r["dose"] == d]
        peaks = np.array([c["peak_dff"] for c in cells])
        aucs = np.array([c["auc"] for c in cells])
        resp = np.array([c["responder"] for c in cells])
        n = len(cells)
        p = resp.mean()
        r_aucs = aucs[resp.astype(bool)]          # AUC over responders only
        nr = len(r_aucs)
        rows.append(dict(
            dose=d, n_cells=n, n_files=len({c["file"] for c in cells}),
            mean_peak_dff=round(float(peaks.mean()), 4),
            sem_peak_dff=round(float(peaks.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0, 4),
            median_peak_dff=round(float(np.median(peaks)), 4),
            mean_auc=round(float(aucs.mean()), 3),
            sem_auc=round(float(aucs.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0, 3),
            median_auc=round(float(np.median(aucs)), 3),
            n_responders=nr,
            mean_responder_auc=round(float(r_aucs.mean()) if nr else 0.0, 3),
            sem_responder_auc=round(float(r_aucs.std(ddof=1) / np.sqrt(nr)) if nr > 1 else 0.0, 3),
            frac_responding=round(float(p), 3),
            sem_frac=round(float(np.sqrt(p * (1 - p) / n)) if n else 0.0, 3),
            peaks=peaks,
        ))
    return pooled, rows


def by_dc_stats(cell_records, exclude_files, exclude_doses):
    """Pooled single-cell dose curves split by duty cycle.

    Returns ``{dc: rows}`` where ``rows`` is :func:`pooled_stats` output (one
    dict per dose) for that duty cycle — i.e. response amplitude and recruitment
    vs dose, one series per DC.
    """
    dcs = sorted({r["dc"] for r in cell_records
                  if r["file"] not in exclude_files
                  and r["dose"] not in exclude_doses})
    return {dc: pooled_stats(cell_records, exclude_files, exclude_doses, dc)[1]
            for dc in dcs}


def latency_stats(cell_records, exclude_files, exclude_doses, dc=40):
    """Pool responder latencies (s from stim onset) across files, by dose.

    Returns one row per dose with the per-responder onset-latency and
    time-to-peak arrays plus their mean / SEM / median. Only responding cells
    contribute (non-responders have no defined latency).
    """
    resp = [r for r in cell_records
            if r["responder"]
            and r["dc"] == dc
            and r["file"] not in exclude_files
            and r["dose"] not in exclude_doses
            and np.isfinite(r["onset_lat_s"])]
    doses = sorted({r["dose"] for r in resp})
    rows = []
    for d in doses:
        cells = [r for r in resp if r["dose"] == d]
        onset = np.array([c["onset_lat_s"] for c in cells])
        peak = np.array([c["t_to_peak_s"] for c in cells])
        n = len(cells)
        sem = lambda a: round(float(a.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0, 2)
        rows.append(dict(
            dose=d, n_cells=n, n_files=len({c["file"] for c in cells}),
            mean_onset_s=round(float(onset.mean()), 2), sem_onset_s=sem(onset),
            median_onset_s=round(float(np.median(onset)), 2),
            mean_peak_s=round(float(peak.mean()), 2), sem_peak_s=sem(peak),
            median_peak_s=round(float(np.median(peak)), 2),
            onset=onset, peak=peak,
        ))
    return rows


def latency_byfile_stats(cell_records, file_ids, exclude_files, exclude_doses, dc=40):
    """Per-file mean responder latency per dose, then averaged across files.

    Mirrors :func:`byfile_stats`: each dish contributes one onset and one
    time-to-peak value per dose (its responder mean), and those are averaged
    across files so every prep weighs equally. Returns one row per dose.
    """
    resp = [r for r in cell_records
            if r["responder"]
            and r["dc"] == dc
            and r["file"] not in exclude_files
            and r["dose"] not in exclude_doses
            and np.isfinite(r["onset_lat_s"])]
    groups = {}
    for r in resp:
        groups.setdefault((r["file"], r["dose"]), []).append(r)
    fstats = {key: (float(np.mean([c["onset_lat_s"] for c in cells])),
                    float(np.mean([c["t_to_peak_s"] for c in cells])))
              for key, cells in groups.items()}

    doses = sorted({d for _, d in fstats})
    rows = []
    for d in doses:
        fvals = [(fid, fstats[(fid, d)]) for fid in file_ids if (fid, d) in fstats]
        onset = np.array([s[0] for _, s in fvals])
        peak = np.array([s[1] for _, s in fvals])
        nf = len(fvals)
        sem = lambda a: round(float(a.std(ddof=1) / np.sqrt(nf)) if nf > 1 else 0.0, 2)
        rows.append(dict(
            dose=d, n_files=nf,
            files=",".join(f for f, _ in fvals),
            mean_onset_s=round(float(onset.mean()), 2), sem_onset_s=sem(onset),
            mean_peak_s=round(float(peak.mean()), 2), sem_peak_s=sem(peak),
            file_onset=list(zip([f for f, _ in fvals], onset)),
            file_peak=list(zip([f for f, _ in fvals], peak)),
        ))
    return rows


def byfile_stats(pooled, file_ids, doses):
    """Summarise each file per dose, then average across files (file = replicate).

    Removes prep/file confound: every dish weighs equally regardless of how
    many cells it contributed.
    """
    groups = {}
    for r in pooled:
        groups.setdefault((r["file"], r["dose"]), []).append(r)
    fstats = {}
    for key, cells in groups.items():
        peaks = np.array([c["peak_dff"] for c in cells])
        resp = np.array([c["responder"] for c in cells])
        fstats[key] = (float(peaks.mean()), float(resp.mean()))

    rows = []
    for d in doses:
        fvals = [(fid, fstats[(fid, d)]) for fid in file_ids if (fid, d) in fstats]
        peaks = np.array([s[0] for _, s in fvals])
        fracs = np.array([s[1] for _, s in fvals])
        nf = len(fvals)
        rows.append(dict(
            dose=d, n_files=nf, files=",".join(f for f, _ in fvals),
            mean_peak_dff=round(float(peaks.mean()), 4),
            sem_peak_dff=round(float(peaks.std(ddof=1) / np.sqrt(nf)) if nf > 1 else 0.0, 4),
            mean_frac_responding=round(float(fracs.mean()), 3),
            sem_frac_responding=round(float(fracs.std(ddof=1) / np.sqrt(nf)) if nf > 1 else 0.0, 3),
            file_peaks=list(zip([f for f, _ in fvals], peaks)),
            file_fracs=list(zip([f for f, _ in fvals], fracs)),
        ))
    return rows
