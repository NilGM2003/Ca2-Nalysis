#!/usr/bin/env python3
import argparse
import sys
import subprocess
import numpy as np
import tifffile

def convert(tif_path, mp4_path, fps=12.5):
    frames = tifffile.imread(tif_path)
    # Handle single frame case
    if frames.ndim == 2:
        frames = frames[np.newaxis]
    n, h, w = frames.shape[:3]
    print(f"{tif_path}: {n} frames, {w}x{h}, dtype={frames.dtype}, output fps={fps}")

    if frames.dtype != np.uint8:
        vmin = frames.min()
        vmax = frames.max()
        frames = ((frames - vmin) / (vmax - vmin) * 255).astype(np.uint8)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{w}x{h}",
        "-pix_fmt", "gray",
        "-r", str(fps),
        "-i", "-",
        "-vf", "format=yuv420p",
        "-c:v", "libx264",
        "-crf", "18",
        mp4_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for frame in frames:
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        print(proc.stderr.read().decode(), file=sys.stderr)
    else:
        print(f"  -> {mp4_path}")

parser = argparse.ArgumentParser()
parser.add_argument("inputs", nargs="*", help="TIF files to convert")
parser.add_argument("--fps", type=float, default=12.5)
args = parser.parse_args()

base = "/home/agustin/Documentos/FUS/MS-GLIA/cell-stimulation/experiments"

if args.inputs:
    for tif_path in args.inputs:
        mp4_path = tif_path.rsplit(".", 1)[0] + "_half.mp4"
        convert(tif_path, mp4_path, fps=args.fps)
else:
    convert(f"{base}/HeLa3.TIF",  f"{base}/HeLa3_half.mp4", fps=args.fps)
    convert(f"{base}/HMC3_1.TIF", f"{base}/HMC3_1_half.mp4", fps=args.fps)
