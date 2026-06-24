"""Interactive viewer: scrub TIF frames alongside per-cell ΔF/F0 traces.

Features
--------
* Frame viewer with a slider and play/pause; cell numbers overlaid on the image.
* Click a cell in the image to plot/unplot its trace; shown cells are marked
  (number highlighted in the cell's colour) so image and plot stay linked.
* Trace plot is shaded by LIFUS epoch and carries a moving vertical cursor at
  the current frame/time.

Run via ``view.py``::

    python view.py 20260609 5
"""
from __future__ import annotations

import csv

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.widgets import Button, Slider
from scipy import ndimage as ndi

from .io import load_tif, truncate
from .protocol import build_epochs
from .segmentation import load_or_segment


class TraceViewer:
    def __init__(self, cfg, fid):
        self.cfg = cfg
        self.fid = str(fid)

        # ---- data ----
        frames, t_s = load_tif(cfg.data_dir / f"{self.fid}.TIF")
        if self.fid in cfg.truncate_min:
            frames, t_s = truncate(frames, t_s, cfg.truncate_min[self.fid])
        self.frames = frames
        self.t_s = t_s
        self.t_min = t_s / 60.0
        self.T, self.H, self.W = frames.shape
        self.eps = build_epochs(cfg.protocol[self.fid], self.t_min[-1], cfg.default_dc)

        self.labels, self.proj = load_or_segment(cfg, frames, self.fid)
        self.ncells = int(self.labels.max())
        self.centroids = ndi.center_of_mass(
            np.ones_like(self.labels), self.labels, range(1, self.ncells + 1))

        self.traces = self._load_traces(cfg.out_dir / f"{self.fid}_traces.csv")

        # contrast from a temporal sample (fast, stable)
        sample = frames[:: max(1, self.T // 30)]
        self.vmin = float(np.percentile(sample, 1))
        self.vmax = float(np.percentile(sample, 99.5))

        # ---- state ----
        self.k = 0
        self.shown: set[int] = set()
        self.lines: dict[int, object] = {}
        self.playing = False

        self._build_gui()

    # ------------------------------------------------------------------ data
    def _load_traces(self, path):
        with open(path) as f:
            r = csv.reader(f)
            hdr = next(r)
            data = list(r)
        col = {h: i for i, h in enumerate(hdr)}
        cell_cols = [h for h in hdr if h.startswith("cell_") and h != "cell_mean"]
        arr = np.array(data, dtype=object)
        traces = np.array([arr[:, col[c]].astype(float) for c in cell_cols])
        if traces.shape[0] != self.ncells:
            raise ValueError(
                f"CSV has {traces.shape[0]} cells but segmentation found "
                f"{self.ncells}. Re-run analyze.py for session {self.cfg.name}.")
        return traces

    def color_for(self, c):
        return cm.tab20((c - 1) % 20)

    def _stim_at(self, k):
        tm = self.t_min[k]
        for (s, e, v, dc, lab) in self.eps:
            if s <= tm < e:
                return lab
        return "OFF"

    # ------------------------------------------------------------------- gui
    def _build_gui(self):
        self.fig = plt.figure(figsize=(15, 7))
        self.fig.canvas.manager.set_window_title(f"Calcium viewer — {self.fid}")
        gs = self.fig.add_gridspec(2, 2, width_ratios=[1, 1.3],
                                   height_ratios=[24, 1], wspace=0.12, hspace=0.18)
        self.ax_img = self.fig.add_subplot(gs[0, 0])
        self.ax_plot = self.fig.add_subplot(gs[0, 1])
        self.ax_slider = self.fig.add_subplot(gs[1, :])

        # image + cell numbers
        self.im = self.ax_img.imshow(self.frames[0], cmap="gray",
                                     vmin=self.vmin, vmax=self.vmax)
        self.ax_img.axis("off")
        self.texts = {}
        for c in range(1, self.ncells + 1):
            y, x = self.centroids[c - 1]
            self.texts[c] = self.ax_img.text(
                x, y, str(c), color="0.6", fontsize=7, ha="center", va="center")

        # trace plot: epoch shading + cursor
        vmax = max((v for *_, v, _, _ in self.eps), default=1)
        for (s, e, v, dc, lab) in self.eps:
            self.ax_plot.axvspan(s, e, color=cm.autumn_r(0.15 + 0.7 * v / vmax),
                                 alpha=0.25, zorder=0)
        tr = self.ax_plot.get_xaxis_transform()
        for (s, e, v, dc, lab) in self.eps:
            self.ax_plot.text((s + e) / 2, 0.99, lab, transform=tr, ha="center",
                              va="top", fontsize=7, color="0.3")
        self.ax_plot.axhline(0, color="gray", lw=0.5, ls="--")
        self.cursor = self.ax_plot.axvline(self.t_min[0], color="k", lw=1.0, zorder=5)
        self.ax_plot.set_xlabel("Time (min)")
        self.ax_plot.set_ylabel(r"$\Delta F/F_0$")
        self.ax_plot.set_ylim(-0.2, 1.0)

        # slider
        self.slider = Slider(self.ax_slider, "Frame", 0, self.T - 1,
                             valinit=0, valstep=1)
        self.slider.on_changed(self._on_slider)

        # buttons
        self.btn_play = Button(self.fig.add_axes([0.01, 0.94, 0.07, 0.05]), "Play")
        self.btn_all = Button(self.fig.add_axes([0.09, 0.94, 0.09, 0.05]), "Show all")
        self.btn_none = Button(self.fig.add_axes([0.19, 0.94, 0.09, 0.05]), "Hide all")
        self.btn_play.on_clicked(self._toggle_play)
        self.btn_all.on_clicked(lambda e: self._set_all(True))
        self.btn_none.on_clicked(lambda e: self._set_all(False))

        # events + timer
        self.fig.canvas.mpl_connect("button_press_event", self._on_click)
        self.fig.canvas.mpl_connect("pick_event", self._on_pick)
        self.timer = self.fig.canvas.new_timer(interval=80)
        self.timer.add_callback(self._advance)

        self._set_frame(0)
        self.fig.suptitle(
            f"File {self.fid} — click cells to plot their traces "
            f"({self.ncells} cells)", fontsize=11)

    # --------------------------------------------------------------- updates
    def _set_frame(self, k):
        self.k = int(k)
        self.im.set_data(self.frames[self.k])
        self.cursor.set_xdata([self.t_min[self.k], self.t_min[self.k]])
        self.ax_img.set_title(
            f"frame {self.k}/{self.T - 1}   t={self.t_min[self.k]:.2f} min   "
            f"LIFUS: {self._stim_at(self.k)}", fontsize=10)
        self.fig.canvas.draw_idle()

    def _on_slider(self, val):
        self._set_frame(val)

    def _mark(self, c, on):
        t = self.texts[c]
        if on:
            t.set_color(self.color_for(c))
            t.set_fontweight("bold")
            t.set_bbox(dict(boxstyle="circle,pad=0.2", fc="white",
                            ec=self.color_for(c), lw=1.3, alpha=0.85))
        else:
            t.set_color("0.6")
            t.set_fontweight("normal")
            t.set_bbox(None)

    def _toggle_cell(self, c):
        if c in self.shown:
            self.shown.discard(c)
            self.lines[c].set_visible(False)
            self._mark(c, False)
        else:
            self.shown.add(c)
            if c in self.lines:
                self.lines[c].set_visible(True)
            else:
                ln, = self.ax_plot.plot(self.t_min, self.traces[c - 1],
                                        color=self.color_for(c), lw=1.2,
                                        label=f"cell {c}", picker=5)
                self.lines[c] = ln
            self._mark(c, True)
        self._refresh_plot()

    def _set_all(self, on):
        for c in range(1, self.ncells + 1):
            if on and c not in self.shown:
                self._toggle_cell(c)
            elif not on and c in self.shown:
                self._toggle_cell(c)

    def _refresh_plot(self):
        if self.shown:
            allv = np.concatenate([self.traces[c - 1] for c in self.shown])
            lo, hi = float(np.nanmin(allv)), float(np.nanmax(allv))
            pad = 0.1 * (hi - lo + 1e-6)
            self.ax_plot.set_ylim(lo - pad, hi + pad)
            handles = [self.lines[c] for c in sorted(self.shown)]
            self.ax_plot.legend(handles=handles, fontsize=7, ncol=2,
                                loc="upper left")
        else:
            leg = self.ax_plot.get_legend()
            if leg:
                leg.remove()
            self.ax_plot.set_ylim(-0.2, 1.0)
        self.fig.canvas.draw_idle()

    def _on_click(self, event):
        if event.inaxes is not self.ax_img or event.xdata is None:
            return
        x, y = int(round(event.xdata)), int(round(event.ydata))
        if 0 <= y < self.H and 0 <= x < self.W:
            c = int(self.labels[y, x])
            if c > 0:
                self._toggle_cell(c)

    def _on_pick(self, event):
        # Click a trace in the plot to isolate it (keep only that one).
        for c, ln in self.lines.items():
            if event.artist is ln:
                self._isolate_cell(c)
                break

    def _isolate_cell(self, c):
        for other in list(self.shown):
            if other != c:
                self.shown.discard(other)
                self.lines[other].set_visible(False)
                self._mark(other, False)
        if c not in self.shown:
            self.shown.add(c)
            self.lines[c].set_visible(True)
            self._mark(c, True)
        self._refresh_plot()

    def _toggle_play(self, event):
        self.playing = not self.playing
        self.btn_play.label.set_text("Pause" if self.playing else "Play")
        (self.timer.start if self.playing else self.timer.stop)()

    def _advance(self):
        self.slider.set_val((self.k + 1) % self.T)

    def show(self):
        plt.show()
