"""Figure generation. All functions save a PNG and close the figure."""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm

# NOTE: backend is chosen by the entry point — analyze.py forces "Agg" for
# headless batch rendering; the interactive viewer leaves the GUI backend.


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


def plot_wholefield(path, fid, t_min, wf_dff, eps):
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(t_min[3:], wf_dff[3:], color="steelblue", lw=1.3, zorder=3)
    ax.axhline(0, color="gray", lw=0.5, ls="--")
    vmax = max(v for *_, v, _, _ in eps)
    for (s, e, v, dc, lab) in eps:
        ax.axvspan(s, e, color=cm.autumn_r(0.15 + 0.7 * v / vmax), alpha=0.35, zorder=1)
    _epoch_labels(ax, eps)
    ax.set_title(f"File {fid} — HMC3 whole-field ΔF/F₀ (LIFUS dose-response)")
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("ΔF/F₀")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_cells(path, fid, proj, labels, c_dff, t_min, eps, ncells):
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
        fig.colorbar(im, ax=a1, label="ΔF/F₀", fraction=0.04)
    a1.set_title("Per-cell ΔF/F₀")
    a1.set_xlabel("Time (min)")
    a1.set_ylabel("Cell (sorted by peak)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_celltraces(path, fid, t_min, c_dff, eps, ncells):
    fig, ax = plt.subplots(figsize=(11, 4.5))
    vmax = max(v for *_, v, _, _ in eps)
    for (s, e, v, dc, lab) in eps:
        ax.axvspan(s, e, color=cm.autumn_r(0.15 + 0.7 * v / vmax), alpha=0.30, zorder=0)
    for c in range(ncells):
        ax.plot(t_min[3:], c_dff[c, 3:], color="black", lw=0.4, alpha=1, zorder=1)
    if ncells:
        ax.plot(t_min[3:], c_dff.mean(axis=0)[3:], color="crimson", lw=2.0,
                label=f"mean of {ncells} cells", zorder=3)
    ax.axhline(0, color="gray", lw=0.5, ls="--")
    _epoch_labels(ax, eps)
    ax.set_title(f"File {fid} — HMC3 per-cell ΔF/F₀ traces + mean")
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("ΔF/F₀")
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
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
                color="crimson", lw=2, capsize=3, zorder=3, label="mean ± SEM")
    tr = a0.get_xaxis_transform()
    for r in pool_rows:
        a0.text(P0(r["dose"]), 0.99, f"n={r['n_cells']}", transform=tr,
                ha="center", va="top", fontsize=7, color="0.3")
    a0.set_ylabel("Single-cell peak ΔF/F₀")
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

    fig.suptitle(f"HMC3 microglia — pooled single-cell LIFUS dose-response "
                 f"({ncell_tot} cell-epochs, {nfile_tot} files, DC {dc}%){extra}",
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
        ("mean_peak_dff", "sem_peak_dff", "Single-cell peak ΔF/F₀",
         "Response amplitude (peak)"),
        ("mean_responder_auc", "sem_responder_auc", "Responder AUC (ΔF/F₀·s)",
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

    fig.suptitle("HMC3 microglia — pooled single-cell response & recruitment "
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
                    label="mean ± SEM")
        tr = ax.get_xaxis_transform()
        for r in lat_rows:
            ax.text(P(r["dose"]), 0.99, f"n={r['n_cells']}", transform=tr,
                    ha="center", va="top", fontsize=7, color="0.3")
        ax.set_ylabel(ylab)
        ax.set_title(title)
        ax.set_ylim(bottom=0)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    fig.suptitle("HMC3 microglia — responder latency from stimulation onset "
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
         "Per-file mean onset latency (s)", "Onset latency — file as replicate"),
        (a1, "file_peak", "mean_peak_s", "sem_peak_s",
         "Per-file mean time-to-peak (s)", "Time-to-peak — file as replicate"),
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
    fig.suptitle("HMC3 microglia — responder latency from onset, file as replicate "
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
    a0.set_ylabel("Per-file mean single-cell peak ΔF/F₀")
    a0.set_title("Dose-response — file as replicate (amplitude)")
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
    a1.set_title("Responding fraction — file as replicate")
    a1.set_ylim(bottom=0)
    a1.grid(alpha=0.3)

    handles = [plt.Line2D([], [], marker="o", ls="", color=fcol[f], label=f"File {f}")
               for f in file_ids]
    a1.legend(handles=handles, fontsize=7, title="prep", ncol=2)
    fig.suptitle("HMC3 microglia — dose-response with file as replicate unit "
                 f"(each dish weighs equally, DC {dc}%){extra}", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
