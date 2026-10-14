"""Figure generation. All functions save a PNG and close the figure."""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm

import matplotlib.patheffects as pe

plt.rcParams.update({
    "text.usetex": False,
    "font.family": "serif",
    "font.size": 12
})

# NOTE: backend is chosen by the entry point — analyze.py forces "Agg" for
# headless batch rendering; the interactive viewer leaves the GUI backend.


# --------------------------------------------------------------------------- #
# Time-course helpers (used to cap traces/epochs at a max time, e.g. 10 min)
# --------------------------------------------------------------------------- #

def _truncate_time(t_min, t_max):
    """Boolean mask selecting samples with t_min <= t_max.

    Pass t_max=None to disable truncation (mask is all True).
    """
    t_min = np.asarray(t_min)
    if t_max is None:
        return np.ones_like(t_min, dtype=bool)
    return t_min <= t_max


def _clip_epochs(eps, t_max):
    """Drop/clip epoch tuples (s, e, v, dc, lab) so none extend past t_max."""
    if t_max is None:
        return eps
    out = []
    for (s, e, v, dc, lab) in eps:
        if s >= t_max:
            continue
        out.append((s, min(e, t_max), v, dc, lab))
    return out


def _dose_axis(ax, xs, log, dose_label):
    """Set the dose x-axis label and (for log axes) ticks at the real doses.

    Returns ``P``, a function mapping a dose value to its plotting position
    (identity for linear axes, ``log10`` for log axes — so decades are evenly
    spaced and violin widths / jitter stay legible).
    """
    P = (lambda d: float(np.log10(d))) if log else (lambda d: float(d))
    ax.set_xlabel(dose_label)
    if log:
        ax.set_xticks([P(x) for x in xs])
        ax.set_xticklabels([f"{x:g}" for x in xs])
    return P


def _epoch_labels(ax, eps):
    """Annotate epoch labels at the top of the axes (x in data coords)."""
    tr = ax.get_xaxis_transform()
    for (s, e, v, dc, lab) in eps:
        ax.text((s + e) / 2, 0.98, lab, transform=tr, ha="center", va="top",
                fontsize=7, color="black")


def _treatment_bars(ax, eps):

    tr = ax.get_xaxis_transform()

    for (s, e, v, dc, lab) in eps:

        color = "indigo"

        ax.plot(
            [s, e],
            [1.03, 1.03],
            transform=tr,
            color=color,
            linewidth=4,
            clip_on=False,
            path_effects=[
                pe.Stroke(linewidth=5, foreground="black"),
                pe.Normal()
            ]
        )

        ax.text(
            (s + e) / 2,
            1.05,
            lab,
            transform=tr,
            ha="center",
            va="bottom",
            fontsize=8
        )

def plot_wholefield(path, fid, t_min, wf_dff, eps, t_max=10.0):

    mask = _truncate_time(t_min, t_max)
    t_min = np.asarray(t_min)[mask]
    wf_dff = np.asarray(wf_dff)[mask]
    eps = _clip_epochs(eps, t_max)

    fig, ax = plt.subplots(figsize=(10,5))

    ax.plot(
        t_min,
        wf_dff,
        color="darkslateblue",
        linewidth=2.5
    )

    ax.axhline(
        0,
        color="gray",
        linewidth=0.5,
        linestyle="--"
    )

    ax.set_xlabel("Time (min)")
    ax.set_ylabel(r"$\Delta F/F_0$")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    _treatment_bars(ax, eps)

    plt.tight_layout()

    fig.savefig(
        path,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close(fig)


def plot_cells(path, fid, proj, labels, c_dff, t_min, eps, ncells, t_max=10.0):

    mask = _truncate_time(t_min, t_max)
    t_min = np.asarray(t_min)[mask]
    if ncells:
        c_dff = np.asarray(c_dff)[:, mask]
    eps = _clip_epochs(eps, t_max)

    fig, (a0, a1) = plt.subplots(1, 2, figsize=(13, 5),
                                 gridspec_kw={"width_ratios": [1, 1.4]})
    a0.imshow(proj, cmap="gray",
              vmax=np.percentile(proj, 99.5), vmin=np.percentile(proj, 1))
    a0.contour(labels > 0, colors="lime", linewidths=0.5)
    a0.set_title(f"File {fid}: {ncells} ROIs")
    a0.axis("off")

    if ncells:
        order = np.argsort(c_dff.max(axis=1))[::-1]
        im = a1.imshow(c_dff[order], aspect="auto", cmap="inferno",
                       vmin=-0.1, vmax=np.percentile(c_dff, 99.5),
                       extent=[t_min[0], t_min[-1], 0, ncells])
        for (s, e, v, dc, lab) in eps:
            a1.axvline(s, color="cyan", lw=0.6, ls=":")
            a1.text(s, ncells, lab, color="cyan", fontsize=6, va="bottom")
        fig.colorbar(im, ax=a1, label=r"$\Delta F/F_0$", fraction=0.04)
    a1.set_title(r" Per cell $\Delta F/F_0$")
    a1.set_xlabel("Time (min)")
    a1.set_ylabel("Cell (sorted by peak)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_celltraces(path, fid, t_min, c_dff, eps, ncells, t_max=10.0):

    mask = _truncate_time(t_min, t_max)
    t_min = np.asarray(t_min)[mask]
    if ncells:
        c_dff = np.asarray(c_dff)[:, mask]
    eps = _clip_epochs(eps, t_max)

    fig, ax = plt.subplots(figsize=(10, 5))

    if ncells:

        mean_trace = c_dff.mean(axis=0)

        sem_trace = (
            c_dff.std(axis=0, ddof=1)
            / np.sqrt(ncells)
        )

        ax.fill_between(
            t_min,
            mean_trace - sem_trace,
            mean_trace + sem_trace,
            color="mediumpurple",
            alpha=0.30,
            zorder=2
        )

        for c in range(ncells):

            ax.plot(
                t_min,
                c_dff[c],
                color="thistle",
                linewidth=1,
                alpha=0.7,
                zorder=1
            )

        ax.plot(
            t_min,
            mean_trace,
            color="darkslateblue",
            linewidth=3,
            zorder=3,
            label=r"mean $\pm$ SEM (n={ncells})"
        )

    ax.axhline(
        0,
        color="gray",
        linewidth=0.5,
        linestyle="--"
    )

    ax.set_xlabel("Time (min)")
    ax.set_ylabel(r"$\Delta F/F_0$")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    _treatment_bars(ax, eps)

    ax.legend(frameon=False)

    plt.tight_layout()

    fig.savefig(
        path,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close(fig)


def plot_dose_pooled(path, pool_rows, ncell_tot, nfile_tot, extra="",
                     dose_label="LIFUS amplitude (V)", dc=40, log=False):
    xs = [r["dose"] for r in pool_rows]
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(13, 5))
    P0 = _dose_axis(a0, xs, log, dose_label)
    P1 = _dose_axis(a1, xs, log, dose_label)
    pos = np.array([P0(x) for x in xs])

    parts = a0.violinplot([r["peaks"] for r in pool_rows], positions=pos,
                          widths=0.6, showextrema=False)
    for b in parts["bodies"]:
        b.set_facecolor("steelblue")
        b.set_alpha(0.25)
    for r in pool_rows:
        jx = P0(r["dose"]) + (np.random.rand(len(r["peaks"])) - 0.5) * 0.18
        a0.scatter(jx, r["peaks"], s=4, color="0.4", alpha=0.35, zorder=2)
    a0.errorbar(pos, [r["mean_peak_dff"] for r in pool_rows],
                yerr=[r["sem_peak_dff"] for r in pool_rows], fmt="-o",
                color="crimson", lw=2, capsize=3, zorder=3, label=r"mean $\pm$ SEM")
    tr = a0.get_xaxis_transform()
    for r in pool_rows:
        a0.text(P0(r["dose"]), 0.99, f"n={r['n_cells']}", transform=tr,
                ha="center", va="top", fontsize=7, color="0.3")
    a0.set_ylabel(r"Single-cell peak $\Delta F/F_0$")
    a0.set_title("Pooled single-cell response amplitude")
    a0.legend(fontsize=8)
    a0.grid(alpha=0.3)

    a1.errorbar(pos, [r["frac_responding"] for r in pool_rows],
                yerr=[r["sem_frac"] for r in pool_rows], fmt="-o",
                color="darkgreen", lw=2, capsize=3)
    for r in pool_rows:
        a1.text(P1(r["dose"]), r["frac_responding"], f" n={r['n_cells']}",
                fontsize=7, va="bottom", color="0.3")
    a1.set_ylabel("Fraction responding cells")
    a1.set_title("Pooled responding fraction")
    a1.set_ylim(bottom=0)
    a1.grid(alpha=0.3)

    fig.suptitle(
    f"HMC3 microglia -- pooled single-cell response and recruitment vs dose, "
    f"by duty cycle ({ncell_tot} cell-epochs, {nfile_tot} files, DC {dc}%){extra}",
    fontsize=12)
    
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_by_dc(path, by_dc, extra="",
               dose_label="LIFUS amplitude (V)", log=False):
    """Response (peak + AUC) and recruitment vs dose, one line per duty cycle."""
    all_xs = sorted({r["dose"] for rows in by_dc.values() for r in rows})
    dcs = sorted(by_dc)
    cmap = plt.get_cmap("tab10")
    dcol = {dc: cmap(i) for i, dc in enumerate(dcs)}

    panels = [
        ("mean_peak_dff", "sem_peak_dff", r"Single-cell peak $\Delta F/F_0$",
         "Response amplitude (peak)"),
        ("mean_responder_auc", "sem_responder_auc", r"Responder AUC ($\Delta F/F_0 \cdot s$)",
         "Response integral (responders only)"),
        ("frac_responding", "sem_frac", "Fraction responding cells",
         "Recruitment"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    for ax, (mk, sk, ylab, title) in zip(axes, panels):
        P = _dose_axis(ax, all_xs, log, dose_label)
        for dc in dcs:
            rows = sorted(by_dc[dc], key=lambda r: r["dose"])
            if not rows:
                continue
            xs = [r["dose"] for r in rows]
            ax.errorbar([P(x) for x in xs], [r[mk] for r in rows],
                        yerr=[r[sk] for r in rows], fmt="-o",
                        color=dcol[dc], lw=2, capsize=3, label=f"DC {dc}%")
        ax.set_ylabel(ylab)
        ax.set_title(title)
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.3)
        ax.legend(title="duty cycle", fontsize=8)

    fig.suptitle("HMC3 microglia - pooled single-cell response and recruitment "
                 f"vs dose, by duty cycle{extra}", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_latency(path, lat_rows, extra="",
                 dose_label="LIFUS amplitude (V)", dc=40, log=False):
    """Responder latency-from-onset vs dose (onset + time-to-peak)."""
    xs = [r["dose"] for r in lat_rows]
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(13, 5))

    panels = [
        (a0, "onset", "mean_onset_s", "sem_onset_s", "steelblue", "crimson",
         "Onset latency (s)", "Responder onset latency"),
        (a1, "peak", "mean_peak_s", "sem_peak_s", "seagreen", "darkorange",
         "Time-to-peak (s)", "Responder time-to-peak"),
    ]
    for ax, key, mk, sk, fill, line, ylab, title in panels:
        P = _dose_axis(ax, xs, log, dose_label)
        pos = np.array([P(x) for x in xs])
        parts = ax.violinplot([r[key] for r in lat_rows], positions=pos,
                              widths=0.6, showextrema=False)
        for b in parts["bodies"]:
            b.set_facecolor(fill)
            b.set_alpha(0.25)
        for r in lat_rows:
            jx = P(r["dose"]) + (np.random.rand(len(r[key])) - 0.5) * 0.18
            ax.scatter(jx, r[key], s=5, color="0.4", alpha=0.35, zorder=2)
        ax.errorbar(pos, [r[mk] for r in lat_rows], yerr=[r[sk] for r in lat_rows],
                    fmt="-o", color=line, lw=2, capsize=3, zorder=3,
                    label=r"mean $\pm$ SEM")
        tr = ax.get_xaxis_transform()
        for r in lat_rows:
            ax.text(P(r["dose"]), 0.99, f"n={r['n_cells']}", transform=tr,
                    ha="center", va="top", fontsize=7, color="0.3")
        ax.set_ylabel(ylab)
        ax.set_title(title)
        ax.set_ylim(bottom=0)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    fig.suptitle("HMC3 microglia - responder latency from stimulation onset "
                 f"(pooled single cells, DC {dc}%){extra}", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_latency_byfile(path, lat_rows, file_ids, extra="",
                        dose_label="LIFUS amplitude (V)", dc=40, log=False):
    """Responder latency vs dose with file as replicate (per-dish points)."""
    xs = [r["dose"] for r in lat_rows]
    cmap = plt.get_cmap("tab10")
    fcol = {fid: cmap(i) for i, fid in enumerate(file_ids)}
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(13, 5))

    panels = [
        (a0, "file_onset", "mean_onset_s", "sem_onset_s",
         "Per-file mean onset latency (s)", "Onset latency - file as replicate"),
        (a1, "file_peak", "mean_peak_s", "sem_peak_s",
         "Per-file mean time-to-peak (s)", "Time-to-peak - file as replicate"),
    ]
    for ax, key, mk, sk, ylab, title in panels:
        P = _dose_axis(ax, xs, log, dose_label)
        pos = np.array([P(x) for x in xs])
        for r in lat_rows:
            for fid, val in r[key]:
                ax.scatter(P(r["dose"]), val, s=26, color=fcol[fid], zorder=2,
                           edgecolor="white", linewidth=0.4)
        ax.errorbar(pos, [r[mk] for r in lat_rows], yerr=[r[sk] for r in lat_rows],
                    fmt="-o", color="black", lw=2, capsize=3, zorder=3,
                    label="across-file mean ± SEM")
        tr = ax.get_xaxis_transform()
        for r in lat_rows:
            ax.text(P(r["dose"]), 0.99, f"N={r['n_files']}", transform=tr,
                    ha="center", va="top", fontsize=7, color="0.3")
        ax.set_ylabel(ylab)
        ax.set_title(title)
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.3)

    handles = [plt.Line2D([], [], marker="o", ls="", color=fcol[f], label=f"File {f}")
               for f in file_ids]
    a0.legend(fontsize=8, loc="upper left")
    a1.legend(handles=handles, fontsize=7, title="prep", ncol=2)
    fig.suptitle("HMC3 microglia - responder latency from onset, file as replicate "
                 f"(each dish weighs equally, DC {dc}%){extra}", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_dose_byfile(path, byfile_rows, file_ids, extra="",
                     dose_label="LIFUS amplitude (V)", dc=40, log=False):
    xs = [r["dose"] for r in byfile_rows]
    cmap = plt.get_cmap("tab10")
    fcol = {fid: cmap(i) for i, fid in enumerate(file_ids)}
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(13, 5))
    P0 = _dose_axis(a0, xs, log, dose_label)
    P1 = _dose_axis(a1, xs, log, dose_label)
    pos = np.array([P0(x) for x in xs])

    for r in byfile_rows:
        for fid, val in r["file_peaks"]:
            a0.scatter(P0(r["dose"]), val, s=26, color=fcol[fid], zorder=2,
                       edgecolor="white", linewidth=0.4)
    a0.errorbar(pos, [r["mean_peak_dff"] for r in byfile_rows],
                yerr=[r["sem_peak_dff"] for r in byfile_rows], fmt="-o",
                color="black", lw=2, capsize=3, zorder=3,
                label="across-file mean ± SEM")
    tr = a0.get_xaxis_transform()
    for r in byfile_rows:
        a0.text(P0(r["dose"]), 0.99, f"N={r['n_files']}", transform=tr,
                ha="center", va="top", fontsize=7, color="0.3")
    a0.set_ylabel(r"Per-file mean single-cell peak $\Delta F/F_0$")
    a0.set_title("Dose-response - file as replicate (amplitude)")
    a0.legend(fontsize=8)
    a0.grid(alpha=0.3)

    for r in byfile_rows:
        for fid, val in r["file_fracs"]:
            a1.scatter(P1(r["dose"]), val, s=26, color=fcol[fid], zorder=2,
                       edgecolor="white", linewidth=0.4)
    a1.errorbar(pos, [r["mean_frac_responding"] for r in byfile_rows],
                yerr=[r["sem_frac_responding"] for r in byfile_rows], fmt="-o",
                color="black", lw=2, capsize=3, zorder=3)
    for r in byfile_rows:
        a1.text(P1(r["dose"]), r["mean_frac_responding"], f" N={r['n_files']}",
                fontsize=7, va="bottom", color="0.3")
    a1.set_ylabel("Responding fraction")
    a1.set_title("Responding fraction - file as replicate")
    a1.set_ylim(bottom=0)
    a1.grid(alpha=0.3)

    handles = [plt.Line2D([], [], marker="o", ls="", color=fcol[f], label=f"File {f}")
               for f in file_ids]
    a1.legend(handles=handles, fontsize=7, title="prep", ncol=2)
    fig.suptitle("HMC3 microglia - dose-response with file as replicate unit "
                 f"(each dish weighs equally, DC {dc}%){extra}", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Duty-cycle x PRF grouped bar charts
#
# These match the style of recruitment_vs_DC_PRF.png / response_latency_vs_DC_PRF.png:
# x-axis groups are duty cycle, bars within a group are colored by PRF, with
# dashed gray separators between duty-cycle groups and a "PRF" color legend.
#
# They consume the same ``by_dc`` shape already built for plot_by_dc /
# plot_latency_byfile: a dict {duty_cycle: [row, ...]}, where each row's
# "dose" field holds the PRF (Hz) for sessions like yours where dose_unit
# is PRF. No re-analysis or renormalization happens here -- only rendering.
# --------------------------------------------------------------------------- #

def _purple_sequence(levels):
    """Map sorted levels (e.g. PRF values) to light->dark purple shades."""
    levels = sorted(levels)
    n = len(levels)
    cmap = cm.get_cmap("Purples")
    shades = [cmap(0.30 + 0.55 * i / max(n - 1, 1)) for i in range(n)]
    return dict(zip(levels, shades))


def _grouped_layout(dc_order, prf_order, slot_w=1.0, group_gap=1.2):
    """x positions for each (dc, prf) bar slot, group centers, and the
    x location of each dashed separator between duty-cycle groups."""
    xpos = {}
    centers = {}
    seps = []
    cursor = 0.0
    for gi, dc in enumerate(dc_order):
        start = cursor
        for prf in prf_order:
            xpos[(dc, prf)] = cursor
            cursor += slot_w
        end = cursor - slot_w
        centers[dc] = (start + end) / 2
        cursor += group_gap
        if gi < len(dc_order) - 1:
            seps.append(cursor - group_gap / 2)
    return xpos, centers, seps


def plot_recruitment_by_dc_prf(path, by_dc, prf_order=None, dc_order=None,
                               extra=""):
    """Recruitment (%) grouped by duty cycle, colored by PRF.

    Parameters
    ----------
    by_dc : dict
        {duty_cycle: [row, ...]}. Each row needs "dose" (PRF, Hz),
        "frac_responding", "n_cells", and optionally "n_responding"
        (falls back to round(frac_responding * n_cells) for the bar label).
    """
    dc_order = dc_order or sorted(by_dc)
    if prf_order is None:
        prf_order = sorted({r["dose"] for rows in by_dc.values() for r in rows})

    colors = _purple_sequence(prf_order)
    xpos, centers, seps = _grouped_layout(dc_order, prf_order)
    bar_w = 0.8

    fig, ax = plt.subplots(figsize=(10, 5))

    for dc in dc_order:
        rows_by_prf = {r["dose"]: r for r in by_dc.get(dc, [])}
        for prf in prf_order:
            row = rows_by_prf.get(prf)
            if row is None:
                continue
            x = xpos[(dc, prf)]
            n_cells = row["n_cells"]
            n_resp = row.get("n_responding")
            if n_resp is None:
                n_resp = int(round(row["frac_responding"] * n_cells))
            pct = row["frac_responding"] * 100

            ax.bar(x, pct, width=bar_w, color=colors[prf],
                   edgecolor="black", linewidth=1, zorder=2)
            ax.text(x, pct + 1.5 if pct > 0 else 1.5, f"{n_resp}/{n_cells}",
                    ha="center", va="bottom", fontsize=9)

    for s in seps:
        ax.axvline(s, color="0.7", linestyle="--", linewidth=1, zorder=0)

    ax.set_xticks([centers[dc] for dc in dc_order])
    ax.set_xticklabels([f"{dc:g}\\% DC" for dc in dc_order])
    ax.set_xlabel("Duty Cycle")
    ax.set_ylabel(r"Recruitment (\%)")
    ax.set_ylim(0, 100)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=colors[p],
                              edgecolor="black") for p in prf_order]
    ax.legend(handles, [f"{p:g} Hz" for p in prf_order], title="PRF",
              loc="upper left", frameon=False)

    if extra:
        fig.suptitle(extra, fontsize=12)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_latency_by_dc_prf(path, by_dc_lat, value_key="peak",
                           mean_key="mean_peak_s", sem_key="sem_peak_s",
                           ylabel="Time to peak response (min)",
                           title=None, prf_order=None, dc_order=None,
                           extra=""):
    """Responder latency metric (mean +/- SEM + per-cell points), grouped by
    duty cycle and colored by PRF.

    Parameters
    ----------
    by_dc_lat : dict
        {duty_cycle: [row, ...]}. Each row needs "dose" (PRF, Hz),
        value_key (list of per-cell latency values), mean_key, sem_key.
        Rows with an empty/missing value_key list are skipped (no bar is
        drawn for combinations with zero responders), matching the
        reference figure.
    """
    dc_order = dc_order or sorted(by_dc_lat)
    if prf_order is None:
        prf_order = sorted({r["dose"] for rows in by_dc_lat.values() for r in rows})

    colors = _purple_sequence(prf_order)
    xpos, centers, seps = _grouped_layout(dc_order, prf_order)
    bar_w = 0.8

    fig, ax = plt.subplots(figsize=(10, 5))

    for dc in dc_order:
        rows_by_prf = {r["dose"]: r for r in by_dc_lat.get(dc, [])}
        for prf in prf_order:
            row = rows_by_prf.get(prf)
            if row is None or not row.get(value_key):
                continue
            x = xpos[(dc, prf)]
            vals = row[value_key]

            ax.bar(x, row[mean_key], width=bar_w, color=colors[prf],
                   edgecolor="black", linewidth=1, zorder=2)
            ax.errorbar(x, row[mean_key], yerr=row.get(sem_key, 0),
                        fmt="none", ecolor="black", capsize=4,
                        linewidth=1.5, zorder=3)

            jitter = (np.random.rand(len(vals)) - 0.5) * bar_w * 0.3
            ax.scatter(x + jitter, vals, facecolor="white",
                       edgecolor="black", linewidth=0.8, s=28, zorder=4)

    for s in seps:
        ax.axvline(s, color="0.7", linestyle="--", linewidth=1, zorder=0)

    ax.set_xticks([centers[dc] for dc in dc_order])
    ax.set_xticklabels([f"{dc:g}\\% DC" for dc in dc_order])
    ax.set_xlabel("Duty Cycle")
    ax.set_ylabel(ylabel)
    ax.set_ylim(bottom=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=colors[p],
                              edgecolor="black") for p in prf_order]
    ax.legend(handles, [f"{p:g} Hz" for p in prf_order], title="PRF",
              loc="upper left", frameon=False)

    if title:
        ax.set_title(title)
    if extra:
        fig.suptitle(extra, fontsize=12)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
