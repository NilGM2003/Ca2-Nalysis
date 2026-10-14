"""Interactive manual ROI editor.

Correct the automatic segmentation by hand: add cells the Otsu step missed,
delete spurious blobs, reshape/split/merge ROIs. The result is saved as a
per-file label mask (``rois/<session>_<fid>.npy``) which the pipeline and the
trace viewer pick up automatically — re-run ``analyze.py`` afterwards to
regenerate traces and figures.

Run via ``edit_rois.py``::

    python edit_rois.py 20260612 4

Tools (buttons, or keys a/d/m/s/r):

* **Add** (a)     — draw a freehand loop; enclosed pixels become a new ROI.
* **Delete** (d)  — click an ROI to remove it.
* **Merge** (m)   — click one ROI then another; the second folds into the first.
* **Split** (s)   — draw a loop over part of an ROI; that part becomes a new ROI.
* **Reshape** (r) — draw a loop over an existing ROI to redefine its outline.

Plus **Undo** (z), **Reset** (reload auto-segmentation), **BG** (cycle the
background projection: mean / max / std-dev), and **Save**.
"""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.path import Path as MplPath
from matplotlib.widgets import Button, LassoSelector
from scipy import ndimage as ndi

from .dyes import load_session_recording
from .segmentation import (compact_labels, load_or_segment, manual_roi_path,
                           segment_cells)

_LASSO_MODES = {"add", "split", "reshape"}
_CLICK_MODES = {"delete", "merge"}


class ROIEditor:
    def __init__(self, cfg, fid):
        self.cfg = cfg
        self.fid = str(fid)

        # raw frames (Calbryte) or the F380 stack (Fura-2), truncated as the
        # session says -- the same image the pipeline segments on
        _stacks, frames, _wf, _t = load_session_recording(cfg, self.fid)
        self.frames = frames
        self.T, self.H, self.W = frames.shape

        self.labels, _proj = load_or_segment(cfg, frames, self.fid)

        # background projections + pixel-centre grid for polygon tests
        self._bg = {
            "mean": frames.mean(axis=0),
            "max": frames.max(axis=0),
            "std": frames.std(axis=0),
        }
        self._bg_order = ["mean", "max", "std"]
        self._bg_i = 0
        xx, yy = np.meshgrid(np.arange(self.W), np.arange(self.H))
        self._grid = np.column_stack([xx.ravel(), yy.ravel()])

        self.mode = "add"
        self.merge_first: int | None = None
        self.history: list[np.ndarray] = []

        self._build_gui()

    # --------------------------------------------------------------- helpers
    @property
    def ncells(self):
        return int(self.labels.max())

    def _color(self, c):
        return cm.tab20((c - 1) % 20)

    def _snapshot(self):
        self.history.append(self.labels.copy())
        if len(self.history) > 50:
            self.history.pop(0)

    def _poly_mask(self, verts):
        inside = MplPath(verts).contains_points(self._grid)
        return inside.reshape(self.H, self.W)

    def _dominant_roi(self, mask):
        """Label that occupies the most pixels under ``mask`` (0 if none)."""
        vals = self.labels[mask]
        vals = vals[vals > 0]
        if vals.size == 0:
            return 0
        u, counts = np.unique(vals, return_counts=True)
        return int(u[counts.argmax()])

    # ------------------------------------------------------------ operations
    def _add(self, mask):
        if not mask.any():
            return
        self._snapshot()
        self.labels[mask] = self.ncells + 1
        self._finish_edit()

    def _reshape(self, mask):
        if not mask.any():
            return
        target = self._dominant_roi(mask)
        self._snapshot()
        if target == 0:                       # drawn over background -> new ROI
            self.labels[mask] = self.ncells + 1
        else:
            self.labels[self.labels == target] = 0
            self.labels[mask] = target
        self._finish_edit()

    def _split(self, mask):
        target = self._dominant_roi(mask)
        if target == 0:
            self._flash("split: draw over an existing ROI")
            return
        piece = mask & (self.labels == target)
        if not piece.any():
            return
        self._snapshot()
        self.labels[piece] = self.ncells + 1
        self._finish_edit()

    def _delete(self, c):
        self._snapshot()
        self.labels[self.labels == c] = 0
        self._finish_edit()

    def _merge(self, a, b):
        self._snapshot()
        self.labels[self.labels == b] = a
        self._finish_edit()

    def _finish_edit(self):
        self.labels = compact_labels(self.labels)
        self.merge_first = None
        self._render()

    def _undo(self, _evt=None):
        if not self.history:
            self._flash("nothing to undo")
            return
        self.labels = self.history.pop()
        self.merge_first = None
        self._render()

    def _reset(self, _evt=None):
        self._snapshot()
        self.labels, _ = segment_cells(self.frames, self.cfg.min_area,
                                       self.cfg.max_area)
        self._finish_edit()
        self._flash("reset to auto-segmentation")

    def _save(self, _evt=None):
        path = manual_roi_path(self.cfg, self.fid)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, self.labels.astype(np.int32))
        self._flash(f"saved {self.ncells} ROIs -> {path.name}  "
                    f"(re-run analyze.py {self.cfg.name})")

    # ------------------------------------------------------------------- gui
    def _build_gui(self):
        self.fig = plt.figure(figsize=(9, 9))
        self.fig.canvas.manager.set_window_title(
            f"ROI editor — {self.cfg.name} file {self.fid}")
        self.ax = self.fig.add_axes([0.04, 0.10, 0.92, 0.82])
        self.ax.axis("off")

        self.bg_im = self.ax.imshow(self._bg["mean"], cmap="gray")
        self.ov_im = self.ax.imshow(np.zeros((self.H, self.W, 4)))
        self._apply_bg()
        self.texts: list = []
        self.status = self.fig.text(0.04, 0.955, "", fontsize=10)

        # tool buttons along the bottom
        specs = [("Add", lambda e: self._set_mode("add")),
                 ("Delete", lambda e: self._set_mode("delete")),
                 ("Merge", lambda e: self._set_mode("merge")),
                 ("Split", lambda e: self._set_mode("split")),
                 ("Reshape", lambda e: self._set_mode("reshape")),
                 ("Undo", self._undo),
                 ("Reset", self._reset),
                 ("BG", self._cycle_bg),
                 ("Save", self._save)]
        self.buttons = {}
        n = len(specs)
        for i, (label, cb) in enumerate(specs):
            ax = self.fig.add_axes([0.04 + i * 0.92 / n, 0.02, 0.92 / n - 0.01, 0.05])
            b = Button(ax, label)
            b.on_clicked(cb)
            self.buttons[label.lower()] = b

        self.lasso = LassoSelector(self.ax, onselect=self._on_lasso)
        self.fig.canvas.mpl_connect("button_press_event", self._on_click)
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)

        self._set_mode("add")
        self._render()

    def _apply_bg(self):
        img = self._bg[self._bg_order[self._bg_i]]
        self.bg_im.set_data(img)
        self.bg_im.set_clim(np.percentile(img, 1), np.percentile(img, 99.5))

    def _cycle_bg(self, _evt=None):
        self._bg_i = (self._bg_i + 1) % len(self._bg_order)
        self._apply_bg()
        self._render()

    def _set_mode(self, mode):
        self.mode = mode
        self.merge_first = None
        self.lasso.set_active(mode in _LASSO_MODES)
        for name, b in self.buttons.items():
            active = name == mode
            b.label.set_fontweight("bold" if active else "normal")
            b.color = "0.75" if active else "0.85"
            b.ax.set_facecolor("0.75" if active else "0.85")
        self._render()

    def _render(self):
        ov = np.zeros((self.H, self.W, 4))
        for c in range(1, self.ncells + 1):
            m = self.labels == c
            if m.any():
                col = list(self._color(c))
                col[3] = 0.40
                ov[m] = col
        self.ov_im.set_data(ov)

        for t in self.texts:
            t.remove()
        self.texts = []
        if self.ncells:
            cents = ndi.center_of_mass(np.ones_like(self.labels), self.labels,
                                       range(1, self.ncells + 1))
            for c, (y, x) in enumerate(cents, 1):
                fc = "yellow" if c == self.merge_first else "white"
                self.texts.append(self.ax.text(
                    x, y, str(c), color="black", fontsize=8, ha="center",
                    va="center", bbox=dict(boxstyle="circle,pad=0.15", fc=fc,
                                           ec=self._color(c), lw=1.2, alpha=0.9)))

        hint = {"add": "draw a loop to add a cell",
                "delete": "click a cell to delete",
                "merge": "click two cells to merge"
                          + (f" (first={self.merge_first})" if self.merge_first else ""),
                "split": "draw a loop over part of a cell to split it off",
                "reshape": "draw a loop over a cell to redefine it"}[self.mode]
        self.status.set_text(f"[{self.mode.upper()}] {hint}    "
                             f"— {self.ncells} ROIs")
        self.fig.canvas.draw_idle()

    def _flash(self, msg):
        self.status.set_text(msg)
        self.fig.canvas.draw_idle()

    # ---------------------------------------------------------------- events
    def _on_lasso(self, verts):
        if self.mode not in _LASSO_MODES or len(verts) < 3:
            return
        mask = self._poly_mask(verts)
        {"add": self._add, "split": self._split,
         "reshape": self._reshape}[self.mode](mask)

    def _on_click(self, event):
        if self.mode not in _CLICK_MODES:
            return
        if event.inaxes is not self.ax or event.xdata is None:
            return
        x, y = int(round(event.xdata)), int(round(event.ydata))
        if not (0 <= y < self.H and 0 <= x < self.W):
            return
        c = int(self.labels[y, x])
        if c == 0:
            return
        if self.mode == "delete":
            self._delete(c)
        elif self.mode == "merge":
            if self.merge_first is None:
                self.merge_first = c
                self._render()
            elif c != self.merge_first:
                self._merge(self.merge_first, c)

    def _on_key(self, event):
        keymap = {"a": "add", "d": "delete", "m": "merge", "s": "split",
                  "r": "reshape"}
        if event.key in keymap:
            self._set_mode(keymap[event.key])
        elif event.key == "z":
            self._undo()

    def show(self):
        plt.show()
