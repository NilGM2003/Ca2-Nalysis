# Cell-stimulation calcium imaging

Analysis of LIFUS (low-intensity focused ultrasound) calcium-imaging
experiments on cultured cells.

## Layout

```
analyze.py            CLI entry point:  python analyze.py [session]
view.py               interactive frame + trace viewer
edit_rois.py          interactive manual ROI editor
src/calcium/          analysis package (session-agnostic)
  io.py                 load TIF stacks + per-frame timing (AQUACOSMOS tag)
  protocol.py           parse acquisition protocol into LIFUS epochs
  segmentation.py       Otsu cell ROIs (+ manual-mask loader) + per-ROI traces
  roieditor.py          interactive manual ROI correction
  dff.py                dF/F0 with rolling-percentile photobleach detrending
  metrics.py            per-epoch whole-field + per-cell responder metrics
  doseresponse.py       pooled and file-as-replicate aggregation
  plotting.py           all figures
  pipeline.py           orchestration: run_session(config)
sessions/             dataset-specific configs (protocol, exclusions, knobs)
  s20260609.py
scripts/              standalone utilities (e.g. tif_to_mp4.py)
20260609/             raw data (TIF stacks + protocol xlsx)
rois/                 hand-corrected ROI masks (<session>_<file>.npy)
results/<session>/    generated figures + CSVs
```

## Usage

```bash
uv run python analyze.py 20260609     # or: .venv/bin/python analyze.py 20260609
```

Per session this writes to `results/<session>/`:

- `{file}_dff.png` — whole-field ΔF/F₀ trace, voltage epochs shaded
- `{file}_cells.png` — ROI overlay + per-cell ΔF/F₀ heatmap
- `{file}_celltraces.png` — all per-cell traces + across-cell mean
- `dose_response_pooled[_noFx].png/.csv` — single cells pooled across files
- `dose_response_byfile[_noFx].png/.csv` — file-as-replicate dose-response
- `calcium_metrics.csv` — per-epoch metrics table

## Correcting the segmentation manually

The automatic Otsu segmentation often misses or merges cells. To fix a file by
hand:

```bash
uv run python edit_rois.py 20260612 4      # session, file id
```

The editor opens on the projection image seeded with the current ROIs. Pick a
tool (buttons or keys) and edit:

- **Add** (`a`) — draw a freehand loop to create a new ROI.
- **Delete** (`d`) — click an ROI to remove it.
- **Merge** (`m`) — click two ROIs to combine them.
- **Split** (`s`) — loop over part of an ROI to break it off.
- **Reshape** (`r`) — loop over an ROI to redraw its outline.
- **Undo** (`z`), **Reset** (back to auto), **BG** (mean / max / std-dev
  background), **Save**.

Save writes `rois/<session>_<file>.npy`. Both `analyze.py` and `view.py` load
that mask automatically (verbatim, no area filter), so **re-run
`analyze.py <session>`** afterwards to regenerate traces and figures. Delete the
`.npy` to fall back to automatic segmentation.

## Adding a session

Create `sessions/sYYYYMMDD.py` defining a `CONFIG = SessionConfig(...)`
(data dir, file ids, protocol, and optional truncation / dose-response
exclusions), then register it in `sessions/__init__.py`.

The **dose axis** is generic: a protocol label's leading number is the dose,
whatever its unit. Set `dose_unit`, `dose_label`, and `dose_log` to describe it
— e.g. a voltage ramp uses `"4.5V"` labels with `dose_unit="V"`; the PRF×DC
matrix in `s20260612.py` uses `"100Hz@DC20"` labels with `dose_unit="Hz"`,
`dose_label="PRF (Hz)"`, `dose_log=True`. `dose_dc` selects which duty cycle the
pooled dose-response figures aggregate; all files always appear in the per-file
figures and `calcium_metrics.csv`.
