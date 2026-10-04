#!/usr/bin/env python3
"""Draw the app icon: a calcium transient on a dark rounded square.

Usage:
    python scripts/make_icon.py OUT.iconset     # all sizes macOS needs
    python scripts/make_icon.py icon.png        # just the 1024 px master

``make_mac_app.sh`` calls this and turns the iconset into an .icns file.
Only matplotlib, numpy and Pillow are needed (all already installed).
"""
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch  # noqa: E402
from PIL import Image                                  # noqa: E402

# (file name, pixel size) pairs of a macOS .iconset
ICONSET = [("icon_16x16.png", 16), ("icon_16x16@2x.png", 32),
           ("icon_32x32.png", 32), ("icon_32x32@2x.png", 64),
           ("icon_128x128.png", 128), ("icon_128x128@2x.png", 256),
           ("icon_256x256.png", 256), ("icon_256x256@2x.png", 512),
           ("icon_512x512.png", 512), ("icon_512x512@2x.png", 1024)]


def _transient(x, x0, amp, tau):
    """Fast rise at x0, slow exponential decay (a calcium transient)."""
    y = np.zeros_like(x)
    m = x >= x0
    y[m] = amp * (1 - np.exp(-(x[m] - x0) / 10)) * np.exp(-(x[m] - x0) / tau)
    return y


def draw_master(path):
    fig = plt.figure(figsize=(10.24, 10.24), dpi=100)
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1024)
    ax.set_ylim(0, 1024)
    ax.axis("off")

    # macOS-style rounded square (824 px inside the 1024 px canvas)
    ax.add_patch(FancyBboxPatch((100, 100), 824, 824,
                                boxstyle="round,pad=0,rounding_size=185",
                                fc="#12304d", ec="none"))
    # faint "cells"
    for x, y, r in [(330, 735, 92), (560, 770, 66), (720, 700, 80)]:
        ax.add_patch(Circle((x, y), r, fc="#5dffb0", ec="none", alpha=0.20))
    # calcium trace: two transients
    x = np.linspace(205, 820, 500)
    y = 300 + _transient(x, 330, 330, 95) + _transient(x, 580, 215, 80)
    ax.plot(x, y, color="#5dffb0", lw=19, solid_capstyle="round",
            solid_joinstyle="round")
    fig.savefig(path, dpi=100, transparent=True)
    plt.close(fig)


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    out = Path(argv[1])
    if out.suffix.lower() == ".png":
        draw_master(out)
        return
    out.mkdir(parents=True, exist_ok=True)
    master = out / "_master.png"
    draw_master(master)
    img = Image.open(master).convert("RGBA")
    for name, size in ICONSET:
        img.resize((size, size), Image.LANCZOS).save(out / name)
    master.unlink()


if __name__ == "__main__":
    main(sys.argv)
