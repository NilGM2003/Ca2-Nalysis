"""Session-level orchestration: per-file analysis -> figures + CSVs."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import SessionConfig
from .dff import compute_dff
from .doseresponse import (byfile_stats, by_dc_stats, latency_byfile_stats,
                           latency_stats, pooled_stats)
from .io import load_tif, truncate
from .metrics import epoch_metrics
from .protocol import build_epochs
from .segmentation import load_or_segment, roi_traces
from . import plotting
from .export import write_cell_traces


@dataclass
class FileResult:
    fid: str
    t_s: np.ndarray
    t_min: np.ndarray
    eps: list
    wf_dff: np.ndarray
    c_dff: np.ndarray
    labels: np.ndarray
    proj: np.ndarray
    ncells: int
    epoch_rows: list
    cell_rows: list


def _baseline_mask(t_min, first_on):
    """Pre-stim window (before first epoch), skipping 3 settling frames."""
    mask = t_min < first_on
    mask[:3] = False
    if mask.sum() < 3:                      # fallback for very early first stim
        mask = np.zeros_like(mask)
        mask[3:8] = True
    return mask


def analyze_file(cfg: SessionConfig, fid: str) -> FileResult:
    frames, t_s = load_tif(cfg.data_dir / f"{fid}.TIF")
    if fid in cfg.truncate_min:
        frames, t_s = truncate(frames, t_s, cfg.truncate_min[fid])
    t_min = t_s / 60.0
    eps = build_epochs(cfg.protocol[fid], t_min[-1], cfg.default_dc)
    base_mask = _baseline_mask(t_min, eps[0][0])

    wf = frames.mean(axis=(1, 2))
    wf_dff = compute_dff(wf, t_s, base_mask, cfg.detrend,
                         cfg.detrend_sec, cfg.detrend_pct)
    wf_base_sd = float(wf_dff[base_mask].std())

    labels, proj = load_or_segment(cfg, frames, fid)
    traces = roi_traces(frames, labels)
    ncells = traces.shape[0]
    c_dff = compute_dff(traces, t_s, base_mask, cfg.detrend,
                        cfg.detrend_sec, cfg.detrend_pct)
    c_base_sd = c_dff[:, base_mask].std(axis=1) if ncells else np.array([])

    epoch_rows, cell_rows = epoch_metrics(
        fid, eps, t_s, wf_dff, c_dff, c_base_sd, ncells,
        cfg.resp_dff, cfg.resp_k, wf_base_sd)

    return FileResult(fid, t_s, t_min, eps, wf_dff, c_dff, labels, proj,
                      ncells, epoch_rows, cell_rows)


def _write_csv(path: Path, cols, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows([{k: r[k] for k in cols} for r in rows])


def run_session(cfg: SessionConfig):
    """Run the full pipeline for one session, writing all outputs."""
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    records, cell_records = [], []

    for fid in cfg.file_ids:
        res = analyze_file(cfg, fid)
        records += res.epoch_rows
        cell_records += res.cell_rows

        plotting.plot_wholefield(cfg.out_dir / f"{fid}_dff.png", fid,
                                 res.t_min, res.wf_dff, res.eps)
        plotting.plot_cells(cfg.out_dir / f"{fid}_cells.png", fid, res.proj,
                            res.labels, res.c_dff, res.t_min, res.eps, res.ncells)
        plotting.plot_celltraces(cfg.out_dir / f"{fid}_celltraces.png", fid,
                                 res.t_min, res.c_dff, res.eps, res.ncells)
        write_cell_traces(cfg.out_dir / f"{fid}_traces.csv", fid,
                          res.t_s, res.c_dff, res.eps)
        print(f"File {fid}: {len(res.t_min)} frames, {res.ncells} cells, "
              f"{len(res.eps)} epochs")

    # ---- dose-response (suffix encodes excluded files) ----
    excl = sorted(cfg.dose_exclude_files)
    sfx = "" if not excl else "_no" + "".join("F" + f for f in excl)
    extra = "" if not excl else f"  [excluding File {', '.join(excl)}]"

    pooled, pool_rows = pooled_stats(cell_records, cfg.dose_exclude_files,
                                     cfg.dose_exclude_dose, cfg.dose_dc)
    doses = [r["dose"] for r in pool_rows]
    byfile_rows = byfile_stats(pooled, cfg.file_ids, doses)
    ncell_tot = len(pooled)
    nfile_tot = len({r["file"] for r in pooled})
    dkw = dict(dose_label=cfg.dose_label, dc=cfg.dose_dc, log=cfg.dose_log)

    plotting.plot_dose_pooled(cfg.out_dir / f"dose_response_pooled{sfx}.png",
                              pool_rows, ncell_tot, nfile_tot, extra, **dkw)
    _write_csv(cfg.out_dir / f"dose_response_pooled{sfx}.csv",
               ["dose", "n_cells", "n_files", "mean_peak_dff", "sem_peak_dff",
                "median_peak_dff", "mean_auc", "sem_auc", "median_auc",
                "n_responders", "mean_responder_auc", "sem_responder_auc",
                "frac_responding", "sem_frac"], pool_rows)

    plotting.plot_dose_byfile(cfg.out_dir / f"dose_response_byfile{sfx}.png",
                              byfile_rows, cfg.file_ids, extra, **dkw)
    _write_csv(cfg.out_dir / f"dose_response_byfile{sfx}.csv",
               ["dose", "n_files", "files", "mean_peak_dff", "sem_peak_dff",
                "mean_frac_responding", "sem_frac_responding"], byfile_rows)

    # ---- response & recruitment vs dose, split by duty cycle ----
    # Only meaningful when the session sweeps more than one duty cycle (e.g.
    # the PRF×DC matrix); single-DC sessions skip it.
    by_dc = by_dc_stats(cell_records, cfg.dose_exclude_files,
                        cfg.dose_exclude_dose)
    if len(by_dc) > 1:
        plotting.plot_by_dc(cfg.out_dir / f"response_recruitment_by_dc{sfx}.png",
                            by_dc, extra, dose_label=cfg.dose_label,
                            log=cfg.dose_log)
        flat = [dict(dc=dc, **{k: r[k] for k in
                               ("dose", "n_cells", "n_files", "mean_peak_dff",
                                "sem_peak_dff", "mean_auc", "sem_auc",
                                "n_responders", "mean_responder_auc",
                                "sem_responder_auc", "frac_responding", "sem_frac")})
                for dc in sorted(by_dc) for r in by_dc[dc]]
        _write_csv(cfg.out_dir / f"response_recruitment_by_dc{sfx}.csv",
                   ["dc", "dose", "n_cells", "n_files", "mean_peak_dff",
                    "sem_peak_dff", "mean_auc", "sem_auc", "n_responders",
                    "mean_responder_auc", "sem_responder_auc",
                    "frac_responding", "sem_frac"], flat)

    # ---- responder latency from stimulation onset ----
    lat_rows = latency_stats(cell_records, cfg.dose_exclude_files,
                             cfg.dose_exclude_dose, cfg.dose_dc)
    if lat_rows:
        plotting.plot_latency(cfg.out_dir / f"latency{sfx}.png", lat_rows, extra,
                              **dkw)
        _write_csv(cfg.out_dir / f"latency{sfx}.csv",
                   ["dose", "n_cells", "n_files",
                    "mean_onset_s", "sem_onset_s", "median_onset_s",
                    "mean_peak_s", "sem_peak_s", "median_peak_s"], lat_rows)

        lat_byfile = latency_byfile_stats(cell_records, cfg.file_ids,
                                          cfg.dose_exclude_files,
                                          cfg.dose_exclude_dose, cfg.dose_dc)
        plotting.plot_latency_byfile(cfg.out_dir / f"latency_byfile{sfx}.png",
                                     lat_byfile, cfg.file_ids, extra, **dkw)
        _write_csv(cfg.out_dir / f"latency_byfile{sfx}.csv",
                   ["dose", "n_files", "files",
                    "mean_onset_s", "sem_onset_s",
                    "mean_peak_s", "sem_peak_s"], lat_byfile)

    _write_csv(cfg.out_dir / "calcium_metrics.csv",
               ["file", "label", "dose", "dc", "t_start_min", "t_end_min",
                "dur_min", "n_cells", "wf_peak_dff", "wf_mean_dff", "wf_auc",
                "wf_onset_lat_s", "wf_t_to_peak_s",
                "n_responders", "frac_responding", "mean_responder_peak_dff",
                "mean_responder_onset_lat_s", "mean_responder_t_to_peak_s"],
               records)

    print(f"\n{len(records)} epoch rows, {len(pool_rows)} doses "
          f"-> {cfg.out_dir}")
